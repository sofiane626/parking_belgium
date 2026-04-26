"""
Tests d'intégration : vérifie que les services métier loggent bien les
événements attendus.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.test import TestCase

from apps.accounts.models import Role
from apps.accounts.services import change_role, update_user_basics
from apps.api.services import issue_token_for, revoke_token
from apps.audit.models import AuditAction, AuditLog
from apps.citizens.models import Address
from apps.citizens.services import get_or_create_profile, upsert_address
from apps.core.models import Commune
from apps.gis_data.models import GISPolygon, GISSourceVersion
from apps.permits.models import PermitConfig, PermitStatus, PermitType
from apps.permits.services import create_draft, mark_paid, submit_application
from apps.vehicles.services import archive_vehicle, create_vehicle

User = get_user_model()


class _Setup(TestCase):
    def setUp(self):
        cfg = PermitConfig.get()
        cfg.resident_price_cents = 0
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
            username="alice", email="alice@example.com", password="Pw123!Aa",
        )
        profile = get_or_create_profile(self.user)
        upsert_address(
            profile, user=self.user, street="X", number="1", box="",
            postal_code="1030", commune=self.commune, country="BE",
        )
        addr = Address.objects.get(profile=profile)
        addr.location = Point(1500, 1500, srid=31370)
        addr.save()
        self.admin = User.objects.create_user(
            username="adm", password="Pw123!Aa", role=Role.ADMIN,
        )


class PermitFlowAuditTests(_Setup):
    def test_submit_logs_event(self):
        AuditLog.objects.all().delete()
        v = create_vehicle(owner=self.user, plate="1-AAA-111", brand="R", model="C")
        permit = create_draft(self.user, v, PermitType.RESIDENT)
        permit = submit_application(permit)
        # Si une CommunePermitPolicy seedée force un prix > 0, on simule
        # le paiement pour atteindre ACTIVE et déclencher PERMIT_ACTIVATED.
        if permit.status == PermitStatus.AWAITING_PAYMENT:
            mark_paid(permit)
        actions = list(AuditLog.objects.values_list("action", flat=True))
        self.assertIn(AuditAction.PERMIT_SUBMITTED, actions)
        self.assertIn(AuditAction.PERMIT_ACTIVATED, actions)


class UserManagementAuditTests(_Setup):
    def test_role_change_logged_with_diff(self):
        AuditLog.objects.all().delete()
        change_role(self.user, new_role=Role.AGENT, actor=self.admin)
        entry = AuditLog.objects.get(action=AuditAction.USER_ROLE_CHANGED)
        self.assertEqual(entry.actor, self.admin)
        self.assertEqual(entry.target_id, self.user.pk)
        self.assertEqual(entry.payload["diff"]["role"], ["citizen", "agent"])

    def test_basics_update_logs_diff(self):
        AuditLog.objects.all().delete()
        update_user_basics(
            self.user, first_name="Alice", last_name="Test",
            email="alice@x.fr", is_active=True, actor=self.admin,
        )
        entry = AuditLog.objects.get(action=AuditAction.USER_BASICS_UPDATED)
        diff = entry.payload["diff"]
        self.assertIn("first_name", diff)
        self.assertEqual(diff["email"][1], "alice@x.fr")

    def test_deactivation_uses_specific_action(self):
        AuditLog.objects.all().delete()
        update_user_basics(
            self.user, first_name=self.user.first_name,
            last_name=self.user.last_name, email=self.user.email,
            is_active=False, actor=self.admin,
        )
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.USER_DEACTIVATED).exists())
        self.assertFalse(AuditLog.objects.filter(action=AuditAction.USER_BASICS_UPDATED).exists())


class TokenAuditTests(_Setup):
    def test_issue_and_revoke_logged(self):
        agent = User.objects.create_user(username="ag", password="x", role=Role.AGENT)
        AuditLog.objects.all().delete()
        token = issue_token_for(agent, actor=self.admin)
        revoke_token(token, actor=self.admin)
        actions = list(AuditLog.objects.values_list("action", flat=True))
        self.assertIn(AuditAction.API_TOKEN_ISSUED, actions)
        self.assertIn(AuditAction.API_TOKEN_REVOKED, actions)


class VehicleAuditTests(_Setup):
    def test_archive_logged(self):
        v = create_vehicle(owner=self.user, plate="2-BBB-222", brand="R", model="C")
        AuditLog.objects.all().delete()
        archive_vehicle(v, by_user=self.user, reason="vendu")
        entry = AuditLog.objects.get(action=AuditAction.VEHICLE_ARCHIVED)
        self.assertEqual(entry.actor, self.user)
        self.assertEqual(entry.payload["context"]["reason"], "vendu")
