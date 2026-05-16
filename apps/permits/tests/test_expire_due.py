"""
Couvre :
- service expire_permit : transitions correctes, idempotence, annulation des
  codes visiteurs en cours, log d'audit
- management command expire_due : ne traite que valid_until < today, mode
  dry-run ne modifie rien
"""
from __future__ import annotations

import datetime as dt
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.audit.models import AuditAction, AuditLog
from apps.citizens.models import Address
from apps.citizens.services import get_or_create_profile, upsert_address
from apps.core.models import Commune
from apps.gis_data.models import GISPolygon, GISSourceVersion
from apps.permits.models import (
    Permit, PermitConfig, PermitStatus, PermitType, VisitorCode, VisitorCodeStatus,
)
from apps.permits.services import (
    PermitError, create_draft, create_visitor_permit, expire_permit,
    generate_visitor_code, mark_paid, submit_application,
)
from apps.vehicles.services import create_vehicle

User = get_user_model()


class _Setup(TestCase):
    """Setup minimal réutilisable : une commune, un polygone, un user avec adresse."""

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
        self.permit = permit
        self.assertEqual(self.permit.status, PermitStatus.ACTIVE)


class ExpirePermitServiceTests(_Setup):
    """Comportements du service expire_permit pris isolément."""

    def test_active_permit_becomes_expired(self):
        expire_permit(self.permit)
        self.permit.refresh_from_db()
        self.assertEqual(self.permit.status, PermitStatus.EXPIRED)
        self.assertIsNotNone(self.permit.expired_at)

    def test_writes_audit_entry(self):
        before = AuditLog.objects.filter(action=AuditAction.PERMIT_EXPIRED).count()
        expire_permit(self.permit)
        after = AuditLog.objects.filter(action=AuditAction.PERMIT_EXPIRED).count()
        self.assertEqual(after, before + 1)

    def test_idempotent_on_already_expired(self):
        expire_permit(self.permit)
        # Deuxième appel : ne raise pas, ne re-log pas.
        expire_permit(self.permit)
        n = AuditLog.objects.filter(
            action=AuditAction.PERMIT_EXPIRED, target_id=self.permit.pk,
        ).count()
        self.assertEqual(n, 1)

    def test_refuses_other_statuses(self):
        # Force le statut DRAFT pour tester le refus
        self.permit.status = PermitStatus.DRAFT
        self.permit.save()
        with self.assertRaises(PermitError):
            expire_permit(self.permit)

    def test_cancels_active_visitor_codes(self):
        # Crée un visitor permit + un code actif
        visitor = create_visitor_permit(self.user)
        if visitor.status == PermitStatus.AWAITING_PAYMENT:
            visitor = mark_paid(visitor)
        code = generate_visitor_code(visitor, plate="2-BBB-222", duration_hours=2)
        self.assertEqual(code.status, VisitorCodeStatus.ACTIVE)

        expire_permit(visitor)
        code.refresh_from_db()
        self.assertEqual(code.status, VisitorCodeStatus.CANCELLED)
        self.assertIsNotNone(code.cancelled_at)


class ExpireDueCommandTests(_Setup):
    """Command line behaviour."""

    def _set_valid_until(self, permit, *, days_offset: int):
        """Force valid_until à today + offset."""
        permit.valid_until = timezone.localdate() + dt.timedelta(days=days_offset)
        permit.save(update_fields=["valid_until"])

    def test_only_expires_past_due(self):
        # Crée 3 permits : un en retard, un à demain, un déjà expiré
        self._set_valid_until(self.permit, days_offset=-1)

        # Un permit déjà EXPIRED doit être ignoré
        v = create_vehicle(owner=self.user, plate="3-CCC-333", brand="R", model="C")
        p2 = create_draft(self.user, v, PermitType.RESIDENT)
        p2 = submit_application(p2)
        if p2.status == PermitStatus.AWAITING_PAYMENT:
            p2 = mark_paid(p2)
        p2.status = PermitStatus.EXPIRED
        p2.expired_at = timezone.now()
        p2.save()

        out = StringIO()
        call_command("expire_due", stdout=out)

        self.permit.refresh_from_db()
        self.assertEqual(self.permit.status, PermitStatus.EXPIRED)
        # Le compteur d'audit pour PERMIT_EXPIRED doit avoir augmenté de 1
        # (le permit déjà EXPIRED ne re-logge pas).
        n = AuditLog.objects.filter(
            action=AuditAction.PERMIT_EXPIRED, target_id=self.permit.pk,
        ).count()
        self.assertEqual(n, 1)

    def test_dry_run_does_not_modify(self):
        self._set_valid_until(self.permit, days_offset=-5)
        out = StringIO()
        call_command("expire_due", "--dry-run", stdout=out)
        self.permit.refresh_from_db()
        self.assertEqual(self.permit.status, PermitStatus.ACTIVE)
        self.assertIn("DRY", out.getvalue())

    def test_no_due_permits_clean_output(self):
        # valid_until à demain -> rien à expirer
        self._set_valid_until(self.permit, days_offset=1)
        out = StringIO()
        call_command("expire_due", stdout=out)
        self.assertIn("Aucune carte", out.getvalue())
        self.permit.refresh_from_db()
        self.assertEqual(self.permit.status, PermitStatus.ACTIVE)
