"""Visitor permit + visitor codes workflow."""
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings

from apps.citizens.models import Address
from apps.citizens.services import get_or_create_profile, upsert_address
from apps.core.models import Commune
from apps.gis_data.models import GISPolygon, GISSourceVersion
from apps.permits.models import (
    Permit, PermitStatus, PermitType, VisitorCode, VisitorCodeStatus,
)
from apps.permits.services import (
    PermitError, cancel_visitor_code, create_draft, create_visitor_permit,
    generate_visitor_code, mark_paid, remaining_visitor_quota, submit_application,
)
from apps.vehicles.services import create_vehicle

User = get_user_model()


class _Setup(TestCase):
    def setUp(self):
        commune = Commune.objects.get(niscode="21015")
        version = GISSourceVersion.objects.create(
            name="t", source_filename="x", srid=31370,
            polygon_count=1, is_active=True,
        )
        GISPolygon.objects.create(
            version=version,
            geometry=MultiPolygon(
                Polygon(((1000, 1000), (2000, 1000), (2000, 2000), (1000, 2000), (1000, 1000))),
                srid=31370,
            ),
            zonecode="ZONE-A", niscode="21015", commune=commune,
        )
        self.alice = User.objects.create_user(username="alice", password="Pw123!Aa")
        profile = get_or_create_profile(self.alice)
        upsert_address(
            profile, user=self.alice, street="Rue X", number="1", box="",
            postal_code="1030", commune=commune, country="BE",
        )
        addr = Address.objects.get(profile=profile)
        addr.location = Point(1500, 1500, srid=31370)
        addr.save()
        self.car = create_vehicle(owner=self.alice, plate="1-AAA-111", brand="R", model="C")
        # Activate resident permit (prerequisite for visitor)
        self.resident = mark_paid(submit_application(create_draft(self.alice, self.car, PermitType.RESIDENT)))


class VisitorPermitTests(_Setup):
    def test_requires_active_resident(self):
        bob = User.objects.create_user(username="bob", password="Pw123!Aa")
        with self.assertRaises(PermitError):
            create_visitor_permit(bob)

    def test_visitor_is_auto_activated_because_free(self):
        permit = create_visitor_permit(self.alice)
        self.assertEqual(permit.permit_type, PermitType.VISITOR)
        self.assertEqual(permit.status, PermitStatus.ACTIVE)
        self.assertIsNotNone(permit.activated_at)
        self.assertIsNotNone(permit.valid_from)

    def test_idempotent_within_period(self):
        a = create_visitor_permit(self.alice)
        b = create_visitor_permit(self.alice)
        self.assertEqual(a.pk, b.pk)


class VisitorCodeTests(_Setup):
    def test_generate_code_normalises_plate(self):
        permit = create_visitor_permit(self.alice)
        code = generate_visitor_code(permit, plate=" 1-bcd-789 ", duration_hours=2)
        self.assertEqual(code.plate, "1-BCD-789")
        self.assertEqual(code.status, VisitorCodeStatus.ACTIVE)

    def test_quota_decreases_with_each_code(self):
        permit = create_visitor_permit(self.alice)
        self.assertEqual(remaining_visitor_quota(permit), 100)
        generate_visitor_code(permit, plate="1-AAA-001")
        self.assertEqual(remaining_visitor_quota(permit), 99)

    def test_quota_enforced(self):
        from apps.permits.models import PermitConfig
        cfg = PermitConfig.get()
        cfg.visitor_codes_per_year = 2
        cfg.save()
        permit = create_visitor_permit(self.alice)
        generate_visitor_code(permit, plate="1-AAA-001")
        generate_visitor_code(permit, plate="1-AAA-002")
        with self.assertRaises(PermitError):
            generate_visitor_code(permit, plate="1-AAA-003")

    def test_cancelled_code_does_not_free_quota(self):
        # Spec & anti-abuse: cancelling a code keeps the slot consumed —
        # otherwise a citizen could rotate through unlimited codes.
        permit = create_visitor_permit(self.alice)
        c = generate_visitor_code(permit, plate="1-AAA-001")
        cancel_visitor_code(c, by_user=self.alice)
        self.assertEqual(remaining_visitor_quota(permit), 99)

    def test_visitor_inherits_resident_zones(self):
        # The resident permit was created in setUp() and has a zone "ZONE-A".
        from apps.permits.models import PermitZone
        permit = create_visitor_permit(self.alice)
        zone_codes = list(PermitZone.objects.filter(permit=permit).values_list("zone_code", flat=True))
        self.assertIn("ZONE-A", zone_codes)

    def test_other_user_cannot_cancel(self):
        permit = create_visitor_permit(self.alice)
        c = generate_visitor_code(permit, plate="1-AAA-001")
        bob = User.objects.create_user(username="bob", password="Pw123!Aa")
        with self.assertRaises(PermissionDenied):
            cancel_visitor_code(c, by_user=bob)
