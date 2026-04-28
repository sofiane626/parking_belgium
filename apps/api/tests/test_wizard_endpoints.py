"""
Couvre les endpoints API consommés par le wizard React :
- /permits/eligibility/<vehicle_pk>/ (lecture seule)
- /permits/submit/<vehicle_pk>/ (création + soumission)
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.citizens.models import Address
from apps.citizens.services import get_or_create_profile, upsert_address
from apps.core.models import Commune
from apps.gis_data.models import GISPolygon, GISSourceVersion
from apps.permits.models import PermitConfig
from apps.vehicles.services import create_vehicle

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
        self.vehicle = create_vehicle(owner=self.user, plate="1-AAA-111", brand="R", model="C")

        self.client = APIClient()
        self.client.force_authenticate(self.user)


class EligibilityTests(_Setup):
    def test_returns_full_payload(self):
        url = reverse("api:permit-eligibility", args=[self.vehicle.pk])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        self.assertEqual(data["vehicle"]["plate"], "1-AAA-111")
        self.assertEqual(data["address"]["commune"], "Schaerbeek")
        self.assertEqual(data["main_zone"], "ZONE-A")
        self.assertFalse(data["denied"])
        self.assertIn("price_cents", data)
        self.assertIn("validity_days", data)

    def test_unauthenticated_refused(self):
        anon = APIClient()
        r = anon.get(reverse("api:permit-eligibility", args=[self.vehicle.pk]))
        self.assertIn(r.status_code, (401, 403))

    def test_other_user_vehicle_refused(self):
        intruder = User.objects.create_user(username="eve", password="Pw1!Aa")
        self.client.force_authenticate(intruder)
        r = self.client.get(reverse("api:permit-eligibility", args=[self.vehicle.pk]))
        self.assertEqual(r.status_code, 404)

    def test_archived_vehicle_refused(self):
        from django.utils import timezone
        self.vehicle.archived_at = timezone.now()
        self.vehicle.save()
        r = self.client.get(reverse("api:permit-eligibility", args=[self.vehicle.pk]))
        self.assertEqual(r.status_code, 400)

    def test_no_address_returns_400(self):
        bare = User.objects.create_user(username="bare", password="x")
        get_or_create_profile(bare)
        v = create_vehicle(owner=bare, plate="9-XXX-999", brand="R", model="C")
        self.client.force_authenticate(bare)
        r = self.client.get(reverse("api:permit-eligibility", args=[v.pk]))
        self.assertEqual(r.status_code, 400)


class SubmitTests(_Setup):
    def test_submit_creates_permit_and_returns_next_step(self):
        url = reverse("api:permit-submit", args=[self.vehicle.pk])
        r = self.client.post(url)
        self.assertEqual(r.status_code, 201, r.content)
        data = r.json()
        self.assertIn(data["status"], ("active", "awaiting_payment", "manual_review"))
        self.assertIn("permit_id", data)
        self.assertIn(data["next_step"], ("payment", "success", "review", "refused"))

    def test_submit_unauthenticated(self):
        anon = APIClient()
        r = anon.post(reverse("api:permit-submit", args=[self.vehicle.pk]))
        self.assertIn(r.status_code, (401, 403))

    def test_submit_other_user_vehicle(self):
        intruder = User.objects.create_user(username="eve", password="Pw1!Aa")
        self.client.force_authenticate(intruder)
        r = self.client.post(reverse("api:permit-submit", args=[self.vehicle.pk]))
        self.assertEqual(r.status_code, 404)
