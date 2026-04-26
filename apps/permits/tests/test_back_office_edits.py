"""
Couvre les éditions back-office sur les cartes ACTIVE / SUSPENDED :
- update_validity refuse hors statuts ACTIVE/SUSPENDED, refuse une date
  antérieure à valid_from, log un diff à l'audit
- set_main_zone_code modifie le code, crée une zone si absente, refuse les
  conflits avec une zone secondaire existante
- suspend_permit refuse hors ACTIVE, exige une raison, annule les codes
  visiteurs actifs
- reactivate_permit refuse hors SUSPENDED
- cancel_visitor_code_by_agent refuse les non back-office
"""
from __future__ import annotations

import datetime as dt

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Role
from apps.audit.models import AuditAction, AuditLog
from apps.citizens.models import Address
from apps.citizens.services import get_or_create_profile, upsert_address
from apps.core.models import Commune
from apps.gis_data.models import GISPolygon, GISSourceVersion
from apps.permits.models import (
    Permit, PermitConfig, PermitStatus, PermitType, PermitZone,
    VisitorCode, VisitorCodeStatus, ZoneSource,
)
from apps.permits.services import (
    PermitError,
    cancel_visitor_code_by_agent,
    create_draft, create_visitor_permit, generate_visitor_code,
    mark_paid, reactivate_permit, set_main_zone_code,
    submit_application, suspend_permit, update_validity,
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
        self.permit = submit_application(permit)
        if self.permit.status == PermitStatus.AWAITING_PAYMENT:
            self.permit = mark_paid(self.permit)
        self.assertEqual(self.permit.status, PermitStatus.ACTIVE)
        self.agent = User.objects.create_user(
            username="ag", password="Pw1!Aa", role=Role.AGENT,
        )
        self.citizen = User.objects.create_user(
            username="cit", password="Pw1!Aa", role=Role.CITIZEN,
        )


class UpdateValidityTests(_Setup):
    def test_extends_validity_on_active(self):
        new_until = self.permit.valid_until + dt.timedelta(days=180)
        AuditLog.objects.all().delete()
        update_validity(self.permit, valid_until=new_until, agent=self.agent)
        self.permit.refresh_from_db()
        self.assertEqual(self.permit.valid_until, new_until)
        self.assertTrue(AuditLog.objects.filter(target_id=self.permit.pk).exists())

    def test_refuses_on_draft(self):
        self.permit.status = PermitStatus.DRAFT
        self.permit.save()
        with self.assertRaises(PermitError):
            update_validity(self.permit, valid_until=dt.date(2099, 1, 1), agent=self.agent)

    def test_refuses_date_before_valid_from(self):
        before = self.permit.valid_from - dt.timedelta(days=1)
        with self.assertRaises(PermitError):
            update_validity(self.permit, valid_until=before, agent=self.agent)


class SetMainZoneTests(_Setup):
    def test_changes_existing_main(self):
        # Une zone principale existe (créée par mark_paid)
        main = PermitZone.objects.get(permit=self.permit, is_main=True)
        old_code = main.zone_code
        set_main_zone_code(self.permit, zone_code="ZONE-NEW", agent=self.agent)
        main.refresh_from_db()
        self.assertEqual(main.zone_code, "ZONE-NEW")
        self.assertEqual(main.source, ZoneSource.MANUAL)
        self.assertNotEqual(main.zone_code, old_code)

    def test_creates_main_when_absent(self):
        PermitZone.objects.filter(permit=self.permit, is_main=True).delete()
        set_main_zone_code(self.permit, zone_code="ZZZ", agent=self.agent)
        self.assertTrue(
            PermitZone.objects.filter(permit=self.permit, is_main=True, zone_code="ZZZ").exists()
        )

    def test_refuses_empty_code(self):
        with self.assertRaises(PermitError):
            set_main_zone_code(self.permit, zone_code="   ", agent=self.agent)

    def test_refuses_conflict_with_secondary(self):
        PermitZone.objects.create(
            permit=self.permit, zone_code="EXISTING", is_main=False, source=ZoneSource.MANUAL,
        )
        with self.assertRaises(PermitError):
            set_main_zone_code(self.permit, zone_code="EXISTING", agent=self.agent)


class SuspendReactivateTests(_Setup):
    def test_suspend_active_with_reason(self):
        suspend_permit(self.permit, agent=self.agent, reason="fraude détectée")
        self.permit.refresh_from_db()
        self.assertEqual(self.permit.status, PermitStatus.SUSPENDED)
        self.assertIn("fraude", self.permit.suspension_reason)
        self.assertTrue(AuditLog.objects.filter(action=AuditAction.PERMIT_SUSPENDED).exists())

    def test_suspend_refuses_without_reason(self):
        with self.assertRaises(PermitError):
            suspend_permit(self.permit, agent=self.agent, reason="")

    def test_suspend_refuses_non_active(self):
        self.permit.status = PermitStatus.EXPIRED
        self.permit.save()
        with self.assertRaises(PermitError):
            suspend_permit(self.permit, agent=self.agent, reason="x")

    def test_suspend_cancels_active_visitor_codes(self):
        # Créer une carte visiteur + un code actif
        visitor = create_visitor_permit(self.user)
        if visitor.status == PermitStatus.AWAITING_PAYMENT:
            visitor = mark_paid(visitor)
        code = generate_visitor_code(visitor, plate="9-ZZZ-999", duration_hours=4)
        suspend_permit(visitor, agent=self.agent, reason="signalement")
        code.refresh_from_db()
        self.assertEqual(code.status, VisitorCodeStatus.CANCELLED)

    def test_reactivate_suspended_works(self):
        suspend_permit(self.permit, agent=self.agent, reason="x")
        reactivate_permit(self.permit, agent=self.agent, notes="résolu")
        self.permit.refresh_from_db()
        self.assertEqual(self.permit.status, PermitStatus.ACTIVE)
        self.assertEqual(self.permit.suspension_reason, "")

    def test_reactivate_refuses_non_suspended(self):
        with self.assertRaises(PermitError):
            reactivate_permit(self.permit, agent=self.agent)


class CancelVisitorCodeByAgentTests(_Setup):
    def setUp(self):
        super().setUp()
        visitor = create_visitor_permit(self.user)
        if visitor.status == PermitStatus.AWAITING_PAYMENT:
            visitor = mark_paid(visitor)
        self.visitor = visitor
        self.code = generate_visitor_code(visitor, plate="9-XXX-111", duration_hours=4)

    def test_agent_can_cancel(self):
        cancel_visitor_code_by_agent(self.code, agent=self.agent, reason="signalement")
        self.code.refresh_from_db()
        self.assertEqual(self.code.status, VisitorCodeStatus.CANCELLED)

    def test_citizen_cannot_use_this_path(self):
        with self.assertRaises(PermissionDenied):
            cancel_visitor_code_by_agent(self.code, agent=self.citizen, reason="x")

    def test_already_cancelled_refused(self):
        cancel_visitor_code_by_agent(self.code, agent=self.agent)
        with self.assertRaises(PermitError):
            cancel_visitor_code_by_agent(self.code, agent=self.agent)
