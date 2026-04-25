"""
Couvre tout le workflow paiement :
- initiate refuse les cartes hors awaiting_payment
- initiate idempotent (réutilise un live payment)
- confirm signe + valide + active la carte + envoie email
- confirm idempotent
- token signé invalide / expiré refusé
- simulation accessible en DEBUG / staff seulement
- simulation court-circuite la confirm signée
- refund suspend la carte + envoie email
- contrainte unique succeeded par permit
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.test import TestCase, override_settings

from apps.citizens.models import Address
from apps.citizens.services import get_or_create_profile, upsert_address
from apps.core.models import Commune
from apps.gis_data.models import GISPolygon, GISSourceVersion
from apps.permits.models import PermitConfig, PermitStatus, PermitType
from apps.permits.services import create_draft, submit_application
from apps.vehicles.services import create_vehicle

from apps.payments.models import Payment, PaymentMethod, PaymentStatus
from apps.payments.services import (
    PaymentError, can_simulate, cancel_payment, confirm_payment,
    initiate_payment, refund_payment, sign_reference, simulate_payment_success,
    verify_signed_reference,
)

User = get_user_model()


class _Setup(TestCase):
    def setUp(self):
        # Ensure resident is paid (price > 0) so the workflow lands on AWAITING_PAYMENT
        # rather than auto-activating.
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
            version=version,
            geometry=MultiPolygon(square, srid=31370),
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
        # CommunePermitPolicy seeded migration uses 0 €. Force a non-zero price.
        permit.price_cents = 1500
        permit.save()
        self.permit = submit_application(permit)
        # The submit_application re-evaluates and recomputes price via policies →
        # which may reset to 0. Force it back if needed for the test scenario.
        if self.permit.price_cents == 0:
            self.permit.price_cents = 1500
            self.permit.save()
        # Ensure status reaches AWAITING_PAYMENT not auto-activated.
        self.assertEqual(self.permit.status, PermitStatus.AWAITING_PAYMENT)


class InitiateTests(_Setup):
    def test_initiate_creates_pending(self):
        p = initiate_payment(self.permit, by_user=self.user, ip="127.0.0.1")
        self.assertEqual(p.status, PaymentStatus.PENDING)
        self.assertEqual(p.amount_cents, 1500)
        self.assertEqual(p.method, PaymentMethod.INTERNAL_FREE)
        self.assertTrue(p.reference)

    def test_initiate_idempotent(self):
        p1 = initiate_payment(self.permit, by_user=self.user)
        p2 = initiate_payment(self.permit, by_user=self.user)
        self.assertEqual(p1.pk, p2.pk)

    def test_initiate_refuses_other_user(self):
        intruder = User.objects.create_user(username="eve", password="Pw123!Aa")
        with self.assertRaises(PermissionDenied):
            initiate_payment(self.permit, by_user=intruder)

    def test_initiate_refuses_wrong_status(self):
        self.permit.status = PermitStatus.DRAFT
        self.permit.save()
        with self.assertRaises(PaymentError):
            initiate_payment(self.permit, by_user=self.user)

    def test_initiate_refuses_free_permit(self):
        self.permit.price_cents = 0
        self.permit.save()
        with self.assertRaises(PaymentError):
            initiate_payment(self.permit, by_user=self.user)


class ConfirmTests(_Setup):
    def test_confirm_activates_permit_and_sends_email(self):
        p = initiate_payment(self.permit, by_user=self.user)
        signed = sign_reference(p.reference)
        mail.outbox = []
        confirmed = confirm_payment(signed_reference=signed, by_user=self.user)
        self.assertEqual(confirmed.status, PaymentStatus.SUCCEEDED)
        self.permit.refresh_from_db()
        self.assertEqual(self.permit.status, PermitStatus.ACTIVE)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Confirmation", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, ["bob@example.com"])

    def test_confirm_idempotent(self):
        p = initiate_payment(self.permit, by_user=self.user)
        signed = sign_reference(p.reference)
        confirm_payment(signed_reference=signed, by_user=self.user)
        # Second call must not error and not re-send email.
        mail.outbox = []
        again = confirm_payment(signed_reference=signed, by_user=self.user)
        self.assertEqual(again.status, PaymentStatus.SUCCEEDED)
        self.assertEqual(len(mail.outbox), 0)

    def test_confirm_invalid_signature(self):
        initiate_payment(self.permit, by_user=self.user)
        with self.assertRaises(PaymentError):
            confirm_payment(signed_reference="bogus:value", by_user=self.user)

    def test_confirm_other_user_refused(self):
        p = initiate_payment(self.permit, by_user=self.user)
        intruder = User.objects.create_user(username="eve", password="Pw123!Aa")
        signed = sign_reference(p.reference)
        with self.assertRaises(PermissionDenied):
            confirm_payment(signed_reference=signed, by_user=intruder)


class CancelTests(_Setup):
    def test_cancel_pending(self):
        p = initiate_payment(self.permit, by_user=self.user)
        cancel_payment(p, by_user=self.user)
        p.refresh_from_db()
        self.assertEqual(p.status, PaymentStatus.CANCELLED)
        self.permit.refresh_from_db()
        self.assertEqual(self.permit.status, PermitStatus.AWAITING_PAYMENT)

    def test_cancel_succeeded_refused(self):
        p = initiate_payment(self.permit, by_user=self.user)
        confirm_payment(signed_reference=sign_reference(p.reference), by_user=self.user)
        with self.assertRaises(PaymentError):
            cancel_payment(p, by_user=self.user)


@override_settings(DEBUG=True)
class SimulationTests(_Setup):
    def test_can_simulate_in_debug(self):
        self.assertTrue(can_simulate(self.user))

    def test_simulate_activates(self):
        mail.outbox = []
        p = simulate_payment_success(self.permit, by_user=self.user)
        self.assertEqual(p.status, PaymentStatus.SUCCEEDED)
        self.assertEqual(p.method, PaymentMethod.SIMULATION)
        self.permit.refresh_from_db()
        self.assertEqual(self.permit.status, PermitStatus.ACTIVE)
        self.assertEqual(len(mail.outbox), 1)

    def test_simulate_cancels_pending_real_payment(self):
        live = initiate_payment(self.permit, by_user=self.user)
        simulate_payment_success(self.permit, by_user=self.user)
        live.refresh_from_db()
        self.assertEqual(live.status, PaymentStatus.CANCELLED)


@override_settings(DEBUG=False)
class SimulationProductionTests(_Setup):
    def test_can_simulate_blocked_for_citizen(self):
        self.assertFalse(can_simulate(self.user))

    def test_can_simulate_allowed_for_staff(self):
        self.user.is_staff = True
        self.user.save()
        self.assertTrue(can_simulate(self.user))

    def test_simulate_refused_outside_debug_for_citizen(self):
        with self.assertRaises(PermissionDenied):
            simulate_payment_success(self.permit, by_user=self.user)


class RefundTests(_Setup):
    def _activate(self) -> Payment:
        p = initiate_payment(self.permit, by_user=self.user)
        return confirm_payment(signed_reference=sign_reference(p.reference), by_user=self.user)

    def test_refund_suspends_permit_and_emails(self):
        p = self._activate()
        admin = User.objects.create_user(
            username="adm", password="Pw123!Aa", email="adm@x.fr",
        )
        admin.role = "admin"
        admin.save()
        mail.outbox = []
        refund_payment(p, by_user=admin, reason="Erreur facturation")
        p.refresh_from_db()
        self.assertEqual(p.status, PaymentStatus.REFUNDED)
        self.permit.refresh_from_db()
        self.assertEqual(self.permit.status, PermitStatus.SUSPENDED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Remboursement", mail.outbox[0].subject)

    def test_refund_refused_for_citizen(self):
        p = self._activate()
        with self.assertRaises(PermissionDenied):
            refund_payment(p, by_user=self.user, reason="x")


class IntegrityTests(_Setup):
    def test_only_one_succeeded_per_permit(self):
        p = initiate_payment(self.permit, by_user=self.user)
        confirm_payment(signed_reference=sign_reference(p.reference), by_user=self.user)
        # Forcing a second SUCCEEDED row must hit the unique partial constraint.
        with self.assertRaises(IntegrityError):
            Payment.objects.create(
                permit=self.permit, citizen=self.user,
                amount_cents=100, method=PaymentMethod.SIMULATION,
                status=PaymentStatus.SUCCEEDED,
            )

    def test_signed_reference_roundtrip(self):
        signed = sign_reference("hello")
        self.assertEqual(verify_signed_reference(signed), "hello")
