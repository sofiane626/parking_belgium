"""
Couvre :
- envoi d'email d'activation pour une carte visiteur gratuite (mark_paid via
  _maybe_auto_activate déclenche l'email sans Payment associé)
- management command send_expiry_reminders : ne traite que les cartes
  ACTIVE qui expirent dans <= N jours, idempotent, dry-run ne modifie rien
"""
from __future__ import annotations

import datetime as dt
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.citizens.models import Address
from apps.citizens.services import get_or_create_profile, upsert_address
from apps.core.models import Commune
from apps.gis_data.models import GISPolygon, GISSourceVersion
from apps.permits.models import Permit, PermitConfig, PermitStatus, PermitType
from apps.permits.services import (
    create_draft, create_visitor_permit, mark_paid, submit_application,
)
from apps.vehicles.services import create_vehicle

User = get_user_model()


class _Setup(TestCase):
    def setUp(self):
        cfg = PermitConfig.get()
        cfg.resident_price_cents = 0
        cfg.visitor_price_cents = 0
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
            username="alice", email="alice@x.fr", password="Pw1!Aa",
        )
        profile = get_or_create_profile(self.user)
        upsert_address(
            profile, user=self.user, street="X", number="1", box="",
            postal_code="1030", commune=self.commune, country="BE",
        )
        addr = Address.objects.get(profile=profile)
        addr.location = Point(1500, 1500, srid=31370)
        addr.save()
        v = create_vehicle(owner=self.user, plate="1-AAA-111", brand="R", model="C")
        permit = create_draft(self.user, v, PermitType.RESIDENT)
        permit = submit_application(permit)
        if permit.status == PermitStatus.AWAITING_PAYMENT:
            permit = mark_paid(permit)
        self.resident = permit


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class VisitorPermitEmailTests(_Setup):
    """L'activation d'une carte visiteur (gratuite) doit envoyer un email."""

    def test_visitor_creation_sends_activation_email(self):
        # locmem backend stocke les mails dans mail.outbox
        mail.outbox = []
        permit = create_visitor_permit(self.user)
        self.assertEqual(permit.status, PermitStatus.ACTIVE)
        # Au moins un email envoyé au citoyen
        self.assertGreaterEqual(len(mail.outbox), 1)
        # Le dernier email doit aller au citoyen et mentionner la carte
        msg = mail.outbox[-1]
        self.assertIn(self.user.email, msg.to)
        self.assertIn(f"#{permit.pk}", msg.subject)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ExpiryReminderCommandTests(_Setup):
    """Tests de la management command send_expiry_reminders."""

    def _set_valid_until(self, days_offset: int):
        self.resident.valid_until = timezone.localdate() + dt.timedelta(days=days_offset)
        self.resident.expiry_reminder_sent_at = None
        self.resident.save(update_fields=["valid_until", "expiry_reminder_sent_at"])

    def test_sends_reminder_for_card_expiring_in_15_days(self):
        self._set_valid_until(days_offset=10)
        mail.outbox = []
        call_command("send_expiry_reminders", stdout=StringIO())
        # Email envoyé
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertIn(self.user.email, msg.to)
        self.assertIn("expire", msg.subject.lower())
        # Champ marqué
        self.resident.refresh_from_db()
        self.assertIsNotNone(self.resident.expiry_reminder_sent_at)

    def test_does_not_resend_if_already_reminded(self):
        self._set_valid_until(days_offset=10)
        self.resident.expiry_reminder_sent_at = timezone.now()
        self.resident.save(update_fields=["expiry_reminder_sent_at"])
        mail.outbox = []
        call_command("send_expiry_reminders", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 0)

    def test_ignores_cards_expiring_after_threshold(self):
        # Expire dans 30 jours → trop tôt pour rappeler à J-15
        self._set_valid_until(days_offset=30)
        mail.outbox = []
        call_command("send_expiry_reminders", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 0)

    def test_ignores_already_expired_cards(self):
        # valid_until = hier → la carte est expirée, pas de rappel
        self._set_valid_until(days_offset=-1)
        mail.outbox = []
        call_command("send_expiry_reminders", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 0)

    def test_dry_run_does_not_send(self):
        self._set_valid_until(days_offset=10)
        mail.outbox = []
        call_command("send_expiry_reminders", "--dry-run", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 0)
        self.resident.refresh_from_db()
        self.assertIsNone(self.resident.expiry_reminder_sent_at)

    def test_custom_days_argument(self):
        # Avec --days 30, une carte qui expire dans 25 jours doit recevoir le rappel
        self._set_valid_until(days_offset=25)
        mail.outbox = []
        call_command("send_expiry_reminders", "--days", "30", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)
