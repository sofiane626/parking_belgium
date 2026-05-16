"""
Smoke tests pour les vues permits côté citoyen (list, detail, wizard, visitor code form).
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.test import Client, TestCase
from django.urls import reverse

from apps.citizens.models import Address
from apps.citizens.services import get_or_create_profile, upsert_address
from apps.core.models import Commune
from apps.gis_data.models import GISPolygon, GISSourceVersion
from apps.permits.models import PermitConfig, PermitStatus, PermitType
from apps.permits.services import (
    create_draft, mark_paid, submit_application,
)
from apps.vehicles.services import create_vehicle

User = get_user_model()


class PermitsViewsTests(TestCase):
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
        self.user = User.objects.create_user(username="u", email="u@x.fr", password="Pw1!Aa")
        profile = get_or_create_profile(self.user)
        upsert_address(
            profile, user=self.user, street="X", number="1", box="",
            postal_code="1030", commune=self.commune, country="BE",
        )
        addr = Address.objects.get(profile=profile)
        addr.location = Point(1500, 1500, srid=31370)
        addr.save()
        self.vehicle = create_vehicle(owner=self.user, plate="1-AAA-111", brand="R", model="C")
        permit = create_draft(self.user, self.vehicle, PermitType.RESIDENT)
        permit = submit_application(permit)
        if permit.status == PermitStatus.AWAITING_PAYMENT:
            permit = mark_paid(permit)
        self.permit = permit
        self.client = Client()
        self.client.force_login(self.user)

    def test_list_permits(self):
        self.assertEqual(self.client.get(reverse("permits:list")).status_code, 200)

    def test_permit_detail(self):
        url = reverse("permits:detail", kwargs={"pk": self.permit.pk})
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_wizard_get(self):
        url = reverse("permits:wizard", kwargs={"vehicle_pk": self.vehicle.pk})
        self.assertEqual(self.client.get(url).status_code, 200)
