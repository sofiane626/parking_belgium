"""
Couvre l'intégration Stripe Checkout en mockant le SDK (pas d'appel réseau).

- create_checkout_session : crée Payment(stripe), enregistre session_id, URL retournée
- confirm_from_session_id : succès → ACTIVE + email + idempotent
- confirm_from_session_id : si payment_status != 'paid' → StripeError
- cancel_session : marque CANCELLED
- handle_webhook_event : checkout.session.completed → confirme
- is_enabled : False si clés vides
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core import mail
from django.test import RequestFactory, TestCase, override_settings

from apps.citizens.models import Address
from apps.citizens.services import get_or_create_profile, upsert_address
from apps.core.models import Commune
from apps.gis_data.models import GISPolygon, GISSourceVersion
from apps.permits.models import PermitConfig, PermitStatus, PermitType
from apps.permits.services import create_draft, submit_application
from apps.vehicles.services import create_vehicle

from apps.payments import stripe_gateway
from apps.payments.models import Payment, PaymentMethod, PaymentStatus

User = get_user_model()


@override_settings(
    STRIPE_PUBLIC_KEY="pk_test_xxx",
    STRIPE_SECRET_KEY="sk_test_xxx",
    STRIPE_CURRENCY="eur",
    STRIPE_WEBHOOK_SECRET="whsec_test_xxx",
)
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
        permit.price_cents = 1500
        permit.save()
        self.permit = submit_application(permit)
        if self.permit.price_cents == 0:
            self.permit.price_cents = 1500
            self.permit.save()
        self.assertEqual(self.permit.status, PermitStatus.AWAITING_PAYMENT)
        self.factory = RequestFactory()


class IsEnabledTests(TestCase):
    @override_settings(STRIPE_PUBLIC_KEY="", STRIPE_SECRET_KEY="")
    def test_disabled_when_keys_missing(self):
        self.assertFalse(stripe_gateway.is_enabled())

    @override_settings(STRIPE_PUBLIC_KEY="pk_x", STRIPE_SECRET_KEY="sk_x")
    def test_enabled_when_keys_present(self):
        self.assertTrue(stripe_gateway.is_enabled())


class CreateSessionTests(_Setup):
    @mock.patch("apps.payments.stripe_gateway.stripe.checkout.Session.create")
    def test_create_session_records_id_and_returns_url(self, mock_create):
        mock_create.return_value = SimpleNamespace(
            id="cs_test_123", url="https://checkout.stripe.com/c/pay/cs_test_123",
        )
        request = self.factory.get("/")
        request.user = self.user
        payment, url = stripe_gateway.create_checkout_session(
            self.permit, by_user=self.user, request=request, ip="127.0.0.1",
        )
        self.assertEqual(payment.method, PaymentMethod.STRIPE)
        self.assertEqual(payment.status, PaymentStatus.PENDING)
        self.assertEqual(payment.stripe_session_id, "cs_test_123")
        self.assertIn("checkout.stripe.com", url)
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs["line_items"][0]["price_data"]["unit_amount"], 1500)
        self.assertEqual(kwargs["line_items"][0]["price_data"]["currency"], "eur")
        self.assertEqual(kwargs["client_reference_id"], payment.reference)


class ConfirmTests(_Setup):
    def _make_payment(self, session_id="cs_test_xyz") -> Payment:
        return Payment.objects.create(
            permit=self.permit, citizen=self.user,
            amount_cents=1500, method=PaymentMethod.STRIPE,
            status=PaymentStatus.PENDING, stripe_session_id=session_id,
        )

    @mock.patch("apps.payments.stripe_gateway.stripe.checkout.Session.retrieve")
    def test_confirm_paid_activates_and_emails(self, mock_retrieve):
        payment = self._make_payment()
        mock_retrieve.return_value = SimpleNamespace(
            payment_status="paid",
            payment_intent=SimpleNamespace(id="pi_123", latest_charge="ch_456"),
        )
        mail.outbox = []
        stripe_gateway.confirm_from_session_id(
            payment.stripe_session_id, by_user=self.user, ip="1.1.1.1",
        )
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.SUCCEEDED)
        self.assertEqual(payment.stripe_payment_intent, "pi_123")
        self.assertEqual(payment.external_transaction_id, "ch_456")
        self.permit.refresh_from_db()
        self.assertEqual(self.permit.status, PermitStatus.ACTIVE)
        self.assertEqual(len(mail.outbox), 1)

    @mock.patch("apps.payments.stripe_gateway.stripe.checkout.Session.retrieve")
    def test_confirm_idempotent(self, mock_retrieve):
        payment = self._make_payment()
        mock_retrieve.return_value = SimpleNamespace(
            payment_status="paid",
            payment_intent=SimpleNamespace(id="pi_x", latest_charge="ch_x"),
        )
        stripe_gateway.confirm_from_session_id(payment.stripe_session_id, by_user=self.user)
        mail.outbox = []
        stripe_gateway.confirm_from_session_id(payment.stripe_session_id, by_user=self.user)
        # 2nd retrieve must NOT have run again (early return on SUCCEEDED).
        self.assertEqual(mock_retrieve.call_count, 1)
        self.assertEqual(len(mail.outbox), 0)

    @mock.patch("apps.payments.stripe_gateway.stripe.checkout.Session.retrieve")
    def test_confirm_unpaid_raises(self, mock_retrieve):
        payment = self._make_payment()
        mock_retrieve.return_value = SimpleNamespace(payment_status="unpaid", payment_intent=None)
        with self.assertRaises(stripe_gateway.StripeError):
            stripe_gateway.confirm_from_session_id(payment.stripe_session_id, by_user=self.user)
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.PENDING)


class CancelTests(_Setup):
    def test_cancel_session_marks_cancelled(self):
        payment = Payment.objects.create(
            permit=self.permit, citizen=self.user,
            amount_cents=1500, method=PaymentMethod.STRIPE,
            status=PaymentStatus.PENDING, stripe_session_id="cs_x",
        )
        stripe_gateway.cancel_session(payment.reference, by_user=self.user)
        payment.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.CANCELLED)


class WebhookDispatchTests(_Setup):
    @mock.patch("apps.payments.stripe_gateway.confirm_from_session_id")
    def test_handle_checkout_completed_calls_confirm(self, mock_confirm):
        event = {
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_test_evt"}},
        }
        stripe_gateway.handle_webhook_event(event)
        mock_confirm.assert_called_once_with("cs_test_evt")

    def test_handle_unknown_event_is_noop(self):
        stripe_gateway.handle_webhook_event({"type": "ping", "data": {"object": {}}})
