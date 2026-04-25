"""
Couvre la passerelle carte interne :
- Luhn : valides/invalides
- détection de marque (Visa, MC, Amex)
- process_card_payment succès → ACTIVE + email + last4 + brand stockés
- carte refusée connue → FAILED + raison
- carte expirée → CardError
- CVC invalide → CardError
- titulaire vide → CardError
- PAN non stocké (vérifie qu'aucun champ ne contient le PAN complet)
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core import mail
from django.test import TestCase

from apps.citizens.models import Address
from apps.citizens.services import get_or_create_profile, upsert_address
from apps.core.models import Commune
from apps.gis_data.models import GISPolygon, GISSourceVersion
from apps.permits.models import PermitConfig, PermitStatus, PermitType
from apps.permits.services import create_draft, submit_application
from apps.vehicles.services import create_vehicle

from apps.payments import card_gateway
from apps.payments.card_gateway import CardError, CardInput
from apps.payments.models import Payment, PaymentMethod, PaymentStatus

User = get_user_model()


class _Setup(TestCase):
    def setUp(self):
        cfg = PermitConfig.get()
        cfg.resident_price_cents = 1500
        cfg.save()

        self.commune = Commune.objects.get(niscode="21015")
        version = GISSourceVersion.objects.create(
            name="t", source_filename="x", srid=31370,
            polygon_count=1, is_active=True,
        )
        square = Polygon(((1000, 1000), (2000, 1000), (2000, 2000), (1000, 2000), (1000, 1000)))
        GISPolygon.objects.create(
            version=version, geometry=MultiPolygon(square, srid=31370),
            zonecode="ZONE-A", niscode="21015", commune=self.commune,
        )
        self.user = User.objects.create_user(
            username="bob", email="bob@example.com", password="Pw123!Aa",
        )
        profile = get_or_create_profile(self.user)
        upsert_address(
            profile, user=self.user, street="X", number="1", box="",
            postal_code="1030", commune=self.commune, country="BE",
        )
        addr = Address.objects.get(profile=profile)
        addr.location = Point(1500, 1500, srid=31370)
        addr.save()
        car = create_vehicle(owner=self.user, plate="1-AAA-111", brand="R", model="C")
        permit = create_draft(self.user, car, PermitType.RESIDENT)
        permit.price_cents = 1500
        permit.save()
        self.permit = submit_application(permit)
        if self.permit.price_cents == 0:
            self.permit.price_cents = 1500
            self.permit.save()
        self.assertEqual(self.permit.status, PermitStatus.AWAITING_PAYMENT)


class LuhnTests(TestCase):
    def test_valid_visa(self):
        self.assertTrue(card_gateway.luhn_valid("4242424242424242"))
        self.assertTrue(card_gateway.luhn_valid("4000000000000002"))

    def test_valid_mastercard(self):
        self.assertTrue(card_gateway.luhn_valid("5555555555554444"))

    def test_valid_amex(self):
        self.assertTrue(card_gateway.luhn_valid("378282246310005"))

    def test_invalid_short(self):
        self.assertFalse(card_gateway.luhn_valid("123"))

    def test_invalid_typo(self):
        self.assertFalse(card_gateway.luhn_valid("4242424242424241"))

    def test_handles_spaces_and_dashes(self):
        self.assertTrue(card_gateway.luhn_valid("4242 4242 4242 4242"))
        self.assertTrue(card_gateway.luhn_valid("4242-4242-4242-4242"))


class BrandDetectionTests(TestCase):
    def test_visa(self):
        self.assertEqual(card_gateway.detect_brand("4242424242424242"), "visa")

    def test_mastercard(self):
        self.assertEqual(card_gateway.detect_brand("5555555555554444"), "mastercard")
        self.assertEqual(card_gateway.detect_brand("2221000000000009"), "mastercard")

    def test_amex(self):
        self.assertEqual(card_gateway.detect_brand("378282246310005"), "amex")


class ProcessTests(_Setup):
    def _payment(self) -> Payment:
        return card_gateway.initiate_card_payment(
            self.permit, by_user=self.user, ip="127.0.0.1",
        )

    def _good_card(self, **overrides) -> CardInput:
        defaults = dict(
            number="4242 4242 4242 4242", holder="JEAN DUPONT",
            exp_month=12, exp_year=2099, cvc="123",
        )
        defaults.update(overrides)
        return CardInput(**defaults)

    def test_success_activates_permit_and_sends_email(self):
        payment = self._payment()
        mail.outbox = []
        card_gateway.process_card_payment(
            payment, self._good_card(), by_user=self.user, ip="1.1.1.1",
        )
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.SUCCEEDED)
        self.assertEqual(payment.card_brand, "visa")
        self.assertEqual(payment.card_last4, "4242")
        self.assertEqual(payment.card_holder, "JEAN DUPONT")
        # PAN complet jamais stocké
        self.assertNotIn("4242424242424242", str(payment.__dict__))
        self.permit.refresh_from_db()
        self.assertEqual(self.permit.status, PermitStatus.ACTIVE)
        self.assertEqual(len(mail.outbox), 1)

    def test_declined_card_marks_failed(self):
        payment = self._payment()
        with self.assertRaises(CardError) as ctx:
            card_gateway.process_card_payment(
                payment, self._good_card(number="4000000000000002"),
                by_user=self.user,
            )
        self.assertIn("refusée", str(ctx.exception).lower())
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.FAILED)
        self.permit.refresh_from_db()
        self.assertEqual(self.permit.status, PermitStatus.AWAITING_PAYMENT)

    def test_invalid_luhn_rejected(self):
        payment = self._payment()
        with self.assertRaises(CardError):
            card_gateway.process_card_payment(
                payment, self._good_card(number="4242424242424241"),
                by_user=self.user,
            )
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.PENDING)

    def test_expired_card_rejected(self):
        payment = self._payment()
        with self.assertRaises(CardError) as ctx:
            card_gateway.process_card_payment(
                payment, self._good_card(exp_month=1, exp_year=2020),
                by_user=self.user,
            )
        self.assertIn("expir", str(ctx.exception).lower())

    def test_invalid_cvc_rejected(self):
        payment = self._payment()
        with self.assertRaises(CardError):
            card_gateway.process_card_payment(
                payment, self._good_card(cvc="12"), by_user=self.user,
            )

    def test_empty_holder_rejected(self):
        payment = self._payment()
        with self.assertRaises(CardError):
            card_gateway.process_card_payment(
                payment, self._good_card(holder=""), by_user=self.user,
            )
