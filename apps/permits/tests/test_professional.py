"""Professional permit workflow: commune-based scope + agent review."""
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from apps.companies.services import create_company
from apps.core.models import Commune
from apps.gis_data.models import GISPolygon, GISSourceVersion
from apps.permits.models import Permit, PermitStatus, PermitType, PermitZone, ZoneSource
from apps.permits.services import (
    PermitError, add_manual_zone, approve_professional, create_professional_permit,
    refuse, remove_zone,
)
from apps.vehicles.services import create_vehicle

User = get_user_model()


def _seed_polygons(commune, count=3):
    version = GISSourceVersion.objects.create(
        name=f"t-{commune.niscode}", source_filename="x", srid=31370,
        polygon_count=count, is_active=True,
    )
    for i in range(count):
        x = 1000 + i * 1000
        GISPolygon.objects.create(
            version=version,
            geometry=MultiPolygon(
                Polygon(((x, 1000), (x + 500, 1000), (x + 500, 1500), (x, 1500), (x, 1000))),
                srid=31370,
            ),
            zonecode=f"{commune.niscode}-Z{i+1}",
            niscode=commune.niscode,
            commune=commune,
        )
    return version


class _Setup(TestCase):
    def setUp(self):
        self.commune = Commune.objects.get(niscode="21015")  # Schaerbeek
        _seed_polygons(self.commune, count=3)
        self.alice = User.objects.create_user(username="alice", password="Pw123!Aa")
        self.car = create_vehicle(owner=self.alice, plate="1-AAA-111", brand="R", model="C")
        self.company = create_company(
            owner=self.alice, name="Acme", vat_number="BE0123456789",
            activity="Plombier", street="Av Y", number="10", box="",
            postal_code="1030", commune=self.commune, country="BE",
        )
        self.agent = User.objects.create_user(username="agent_jo", password="Pw123!Aa")


class ProfessionalCreateTests(_Setup):
    def test_create_lands_in_manual_review_with_commune_zones(self):
        permit = create_professional_permit(self.alice, self.car, self.company, self.commune)
        self.assertEqual(permit.status, PermitStatus.MANUAL_REVIEW)
        self.assertEqual(permit.target_commune, self.commune)
        # All 3 commune polygons attached at creation.
        zones = list(PermitZone.objects.filter(permit=permit).values_list("zone_code", flat=True))
        self.assertEqual(len(zones), 3)

    def test_other_users_company_rejected(self):
        bob = User.objects.create_user(username="bob", password="Pw123!Aa")
        with self.assertRaises(PermissionDenied):
            create_professional_permit(bob, self.car, self.company, self.commune)

    def test_commune_required(self):
        with self.assertRaises(PermitError):
            create_professional_permit(self.alice, self.car, self.company, None)

    def test_commune_with_no_polygons_rejected(self):
        empty_commune = Commune.objects.get(niscode="21001")  # Anderlecht — no polygons seeded
        with self.assertRaises(PermitError):
            create_professional_permit(self.alice, self.car, self.company, empty_commune)


class AgentReviewTests(_Setup):
    def test_agent_can_remove_a_zone_then_approve(self):
        permit = create_professional_permit(self.alice, self.car, self.company, self.commune)
        z = PermitZone.objects.filter(permit=permit).first()
        remove_zone(z)
        permit = approve_professional(permit, agent=self.agent, notes="OK")
        self.assertEqual(permit.status, PermitStatus.AWAITING_PAYMENT)
        self.assertEqual(PermitZone.objects.filter(permit=permit).count(), 2)

    def test_agent_can_add_extra_manual_zone(self):
        permit = create_professional_permit(self.alice, self.car, self.company, self.commune)
        add_manual_zone(permit, zone_code="EXTRA", is_main=False)
        self.assertEqual(PermitZone.objects.filter(permit=permit).count(), 4)

    def test_approve_refused_when_all_zones_removed(self):
        permit = create_professional_permit(self.alice, self.car, self.company, self.commune)
        PermitZone.objects.filter(permit=permit).delete()
        with self.assertRaises(PermitError):
            approve_professional(permit, agent=self.agent)
