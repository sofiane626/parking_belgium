"""
Tests d'intégration sur les actions agent (approve / refuse / add zone /
remove zone / edit validity / suspend / reactivate). On test le happy path
via le client Django pour couvrir les vues dashboard côté agent.
"""
from __future__ import annotations

import datetime as dt

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.citizens.models import Address
from apps.citizens.services import get_or_create_profile, upsert_address
from apps.core.models import Commune
from apps.gis_data.models import GISPolygon, GISSourceVersion
from apps.permits.models import (
    Permit, PermitConfig, PermitStatus, PermitType, PermitZone,
)
from apps.permits.services import (
    create_draft, mark_paid, submit_application,
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
        self.polygon = GISPolygon.objects.create(
            version=version, geometry=MultiPolygon(square, srid=31370),
            zonecode="ZONE-A", niscode="21015", commune=self.commune,
        )
        GISPolygon.objects.create(
            version=version,
            geometry=MultiPolygon(
                Polygon(((3000, 3000), (4000, 3000), (4000, 4000), (3000, 4000), (3000, 3000))),
                srid=31370,
            ),
            zonecode="ZONE-B", niscode="21015", commune=self.commune,
        )

        self.citizen = User.objects.create_user(username="c", email="c@x.fr", password="Pw1!Aa")
        profile = get_or_create_profile(self.citizen)
        upsert_address(
            profile, user=self.citizen, street="X", number="1", box="",
            postal_code="1030", commune=self.commune, country="BE",
        )
        addr = Address.objects.get(profile=profile)
        addr.location = Point(1500, 1500, srid=31370)
        addr.save()
        v = create_vehicle(owner=self.citizen, plate="1-AAA-111", brand="R", model="C")
        permit = create_draft(self.citizen, v, PermitType.RESIDENT)
        self.permit = submit_application(permit)
        if self.permit.status == PermitStatus.AWAITING_PAYMENT:
            self.permit = mark_paid(self.permit)

        self.agent = User.objects.create_user(username="a", password="Pw1!Aa", role=Role.AGENT)
        self.admin = User.objects.create_user(username="ad", password="Pw1!Aa", role=Role.ADMIN)
        self.client = Client()


class AgentEditPermitTests(_Setup):
    """Édition validité + suspension/réactivation côté agent."""

    def test_edit_validity_extends_until_date(self):
        self.client.force_login(self.agent)
        new_date = (timezone.localdate() + dt.timedelta(days=400)).isoformat()
        url = reverse("dashboard:agent_permit_edit_validity", kwargs={"pk": self.permit.pk})
        response = self.client.post(url, {"valid_until": new_date})
        self.assertEqual(response.status_code, 302)
        self.permit.refresh_from_db()
        self.assertEqual(self.permit.valid_until.isoformat(), new_date)

    def test_set_main_zone(self):
        self.client.force_login(self.agent)
        url = reverse("dashboard:agent_permit_edit_main_zone", kwargs={"pk": self.permit.pk})
        response = self.client.post(url, {"zone_code": "ZONE-B"})
        self.assertEqual(response.status_code, 302)
        self.permit.refresh_from_db()
        main = PermitZone.objects.get(permit=self.permit, is_main=True)
        self.assertEqual(main.zone_code, "ZONE-B")

    def test_suspend_then_reactivate(self):
        self.client.force_login(self.agent)
        suspend_url = reverse("dashboard:agent_permit_suspend", kwargs={"pk": self.permit.pk})
        response = self.client.post(suspend_url, {"reason": "test"})
        self.assertEqual(response.status_code, 302)
        self.permit.refresh_from_db()
        self.assertEqual(self.permit.status, PermitStatus.SUSPENDED)

        reactivate_url = reverse("dashboard:agent_permit_reactivate", kwargs={"pk": self.permit.pk})
        response = self.client.post(reactivate_url)
        self.assertEqual(response.status_code, 302)
        self.permit.refresh_from_db()
        self.assertEqual(self.permit.status, PermitStatus.ACTIVE)


class AdminUserToggleTests(_Setup):
    """Désactivation/réactivation d'un user par un admin."""

    def test_toggle_active(self):
        self.client.force_login(self.admin)
        url = reverse("dashboard:admin_user_toggle_active", kwargs={"pk": self.citizen.pk})
        # Désactiver
        response = self.client.post(url, {"active": "off"})
        self.assertEqual(response.status_code, 302)
        self.citizen.refresh_from_db()
        self.assertFalse(self.citizen.is_active)
        # Réactiver
        response = self.client.post(url, {"active": "on"})
        self.assertEqual(response.status_code, 302)
        self.citizen.refresh_from_db()
        self.assertTrue(self.citizen.is_active)
