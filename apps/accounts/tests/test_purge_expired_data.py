"""
Couvre :
- mode dry-run : rien n'est modifié
- comptes inactifs > 3 ans anonymisés
- comptes inactifs récents : intacts
- comptes avec permit ACTIVE : intacts (même si inactifs)
- codes visiteurs expirés > 1 an supprimés
- audit log > 3 ans supprimés
- entrée RGPD_PURGED écrite à la fin
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
    create_draft, create_visitor_permit, generate_visitor_code, mark_paid,
    submit_application,
)
from apps.vehicles.services import create_vehicle

User = get_user_model()


class PurgeExpiredDataTests(TestCase):
    def setUp(self):
        cfg = PermitConfig.get()
        cfg.resident_price_cents = 0
        cfg.visitor_price_cents = 0
        cfg.save()
        self.commune = Commune.objects.get(niscode="21015")

    def _make_user(self, username: str, *, years_inactive: int = 0, email: str = "x@x.fr"):
        """Crée un user avec last_login forcé à today - years_inactive."""
        u = User.objects.create_user(username=username, email=email, password="Pw1!Aa")
        if years_inactive > 0:
            old = timezone.now() - dt.timedelta(days=365 * years_inactive + 1)
            User.objects.filter(pk=u.pk).update(last_login=old, date_joined=old)
            u.refresh_from_db()
        return u

    def test_dry_run_does_not_modify(self):
        u = self._make_user("oldie", years_inactive=5)
        out = StringIO()
        call_command("purge_expired_data", stdout=out)
        u.refresh_from_db()
        self.assertEqual(u.email, "x@x.fr")  # non modifié
        self.assertTrue(u.is_active)
        self.assertIn("DRY-RUN", out.getvalue())

    def test_anonymises_inactive_user(self):
        u = self._make_user("oldie", years_inactive=5, email="bob@x.fr")
        out = StringIO()
        call_command("purge_expired_data", "--apply", stdout=out)
        u.refresh_from_db()
        self.assertEqual(u.email, "")
        self.assertEqual(u.first_name, "")
        self.assertFalse(u.is_active)

    def test_recent_user_kept(self):
        u = self._make_user("freshy", years_inactive=1)
        call_command("purge_expired_data", "--apply", stdout=StringIO())
        u.refresh_from_db()
        self.assertEqual(u.email, "x@x.fr")  # intact
        self.assertTrue(u.is_active)

    def test_user_with_active_permit_kept(self):
        """Un user inactif depuis 5 ans MAIS avec un permit ACTIVE n'est pas purgé."""
        # Setup polygon + adresse minimaux pour pouvoir créer un permit
        version = GISSourceVersion.objects.create(
            name="t", source_filename="x", srid=31370,
            polygon_count=1, is_active=True,
        )
        square = Polygon(((1000, 1000), (2000, 1000), (2000, 2000), (1000, 2000), (1000, 1000)))
        GISPolygon.objects.create(
            version=version, geometry=MultiPolygon(square, srid=31370),
            zonecode="ZONE-A", niscode="21015", commune=self.commune,
        )
        u = self._make_user("dormant_holder", years_inactive=5, email="alice@x.fr")
        profile = get_or_create_profile(u)
        upsert_address(
            profile, user=u, street="X", number="1", box="",
            postal_code="1030", commune=self.commune, country="BE",
        )
        addr = Address.objects.get(profile=profile)
        addr.location = Point(1500, 1500, srid=31370)
        addr.save()
        v = create_vehicle(owner=u, plate="1-AAA-111", brand="R", model="C")
        permit = create_draft(u, v, PermitType.RESIDENT)
        permit = submit_application(permit)
        if permit.status == PermitStatus.AWAITING_PAYMENT:
            permit = mark_paid(permit)
        self.assertEqual(permit.status, PermitStatus.ACTIVE)

        call_command("purge_expired_data", "--apply", stdout=StringIO())
        u.refresh_from_db()
        # Email préservé car compte avec permit ACTIVE
        self.assertEqual(u.email, "alice@x.fr")

    def test_old_visitor_codes_deleted(self):
        """Code visiteur expiré il y a > 1 an doit être supprimé."""
        # Setup minimal pour avoir un visitor permit
        version = GISSourceVersion.objects.create(
            name="t", source_filename="x", srid=31370,
            polygon_count=1, is_active=True,
        )
        square = Polygon(((1000, 1000), (2000, 1000), (2000, 2000), (1000, 2000), (1000, 1000)))
        GISPolygon.objects.create(
            version=version, geometry=MultiPolygon(square, srid=31370),
            zonecode="ZONE-A", niscode="21015", commune=self.commune,
        )
        u = self._make_user("v", years_inactive=0, email="v@x.fr")
        profile = get_or_create_profile(u)
        upsert_address(
            profile, user=u, street="X", number="1", box="",
            postal_code="1030", commune=self.commune, country="BE",
        )
        addr = Address.objects.get(profile=profile)
        addr.location = Point(1500, 1500, srid=31370)
        addr.save()
        v = create_vehicle(owner=u, plate="9-ZZZ-999", brand="R", model="C")
        # Prérequis : un permit riverain ACTIVE avant de pouvoir créer un visitor
        rp = create_draft(u, v, PermitType.RESIDENT)
        rp = submit_application(rp)
        if rp.status == PermitStatus.AWAITING_PAYMENT:
            rp = mark_paid(rp)
        permit = create_visitor_permit(u)
        if permit.status == PermitStatus.AWAITING_PAYMENT:
            permit = mark_paid(permit)
        code = generate_visitor_code(permit, plate="2-BBB-222", duration_hours=2)
        # Force valid_until à 2 ans dans le passé
        VisitorCode.objects.filter(pk=code.pk).update(
            valid_until=timezone.now() - dt.timedelta(days=365 * 2),
        )

        call_command("purge_expired_data", "--apply", stdout=StringIO())
        self.assertFalse(VisitorCode.objects.filter(pk=code.pk).exists())

    def test_old_audit_logs_deleted(self):
        # Créer un log forcé à 5 ans dans le passé
        log = AuditLog.objects.create(
            action=AuditAction.PERMIT_ACTIVATED,
            severity="info",
            target_type="permit",
            target_id=42,
            target_label="Test",
            payload={},
        )
        AuditLog.objects.filter(pk=log.pk).update(
            created_at=timezone.now() - dt.timedelta(days=365 * 5),
        )
        call_command("purge_expired_data", "--apply", stdout=StringIO())
        self.assertFalse(AuditLog.objects.filter(pk=log.pk).exists())

    def test_rgpd_purged_audit_entry_written(self):
        before = AuditLog.objects.filter(action=AuditAction.RGPD_PURGED).count()
        call_command("purge_expired_data", "--apply", stdout=StringIO())
        after = AuditLog.objects.filter(action=AuditAction.RGPD_PURGED).count()
        self.assertEqual(after, before + 1)
