"""
Smoke tests : pour chaque vue GET du dashboard, vérifie qu'un user avec le
bon rôle reçoit un 200 (ou redirection légitime). Ne teste pas le contenu —
le but est juste d'attraper les régressions (import cassé, NameError, query
qui plante au rendu).

Couvre :
- dashboards par rôle (citizen / agent / admin / super_admin)
- back-office admin : config, policies, GIS, users, audit, API tokens, exports
- pages détail (avec data minimale)
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import Role
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


class _Setup(TestCase):
    """Setup minimal partagé : 4 users (un par rôle) + une carte ACTIVE."""

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

        self.citizen = User.objects.create_user(
            username="c", email="c@x.fr", password="Pw1!Aa",
        )
        profile = get_or_create_profile(self.citizen)
        upsert_address(
            profile, user=self.citizen, street="X", number="1", box="",
            postal_code="1030", commune=self.commune, country="BE",
        )
        addr = Address.objects.get(profile=profile)
        addr.location = Point(1500, 1500, srid=31370)
        addr.save()
        vehicle = create_vehicle(owner=self.citizen, plate="1-AAA-111", brand="R", model="C")
        permit = create_draft(self.citizen, vehicle, PermitType.RESIDENT)
        permit = submit_application(permit)
        if permit.status == PermitStatus.AWAITING_PAYMENT:
            permit = mark_paid(permit)
        self.permit = permit
        self.vehicle = vehicle

        self.agent = User.objects.create_user(username="a", password="Pw1!Aa", role=Role.AGENT)
        self.admin = User.objects.create_user(username="ad", password="Pw1!Aa", role=Role.ADMIN)
        self.super_admin = User.objects.create_user(username="sa", password="Pw1!Aa", role=Role.SUPER_ADMIN)
        self.client = Client()


class DashboardRoleViewsTests(_Setup):
    """Chaque rôle peut accéder à son dashboard."""

    def test_citizen_dashboard(self):
        self.client.force_login(self.citizen)
        self.assertEqual(self.client.get(reverse("dashboard:citizen")).status_code, 200)

    def test_agent_dashboard(self):
        self.client.force_login(self.agent)
        self.assertEqual(self.client.get(reverse("dashboard:agent")).status_code, 200)

    def test_admin_dashboard(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("dashboard:admin")).status_code, 200)

    def test_super_admin_dashboard(self):
        self.client.force_login(self.super_admin)
        self.assertEqual(self.client.get(reverse("dashboard:super_admin")).status_code, 200)


class AgentReviewQueueTests(_Setup):
    """Listes côté agent : requests + permits."""

    def test_agent_requests_list(self):
        self.client.force_login(self.agent)
        self.assertEqual(self.client.get(reverse("dashboard:agent_requests")).status_code, 200)

    def test_agent_permits_list(self):
        self.client.force_login(self.agent)
        self.assertEqual(self.client.get(reverse("dashboard:agent_permits")).status_code, 200)

    def test_agent_permit_detail(self):
        self.client.force_login(self.agent)
        url = reverse("dashboard:agent_permit_detail", kwargs={"pk": self.permit.pk})
        self.assertEqual(self.client.get(url).status_code, 200)


class AdminBackOfficeTests(_Setup):
    """Pages back-office admin (config, policies, GIS, users, audit, tokens)."""

    URLS = [
        "dashboard:admin_permit_config",
        "dashboard:admin_policies",
        "dashboard:gis_versions",
        "dashboard:gis_polygons",
        "dashboard:admin_users",
        "dashboard:admin_api_tokens",
        "dashboard:admin_audit",
    ]

    def test_each_admin_page_returns_200(self):
        self.client.force_login(self.admin)
        for name in self.URLS:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, name)

    def test_admin_pages_forbid_citizen(self):
        self.client.force_login(self.citizen)
        for name in self.URLS:
            response = self.client.get(reverse(name))
            self.assertIn(response.status_code, (302, 403), name)

    def test_gis_polygon_detail(self):
        self.client.force_login(self.admin)
        url = reverse("dashboard:gis_polygon_detail", kwargs={"pk": self.polygon.pk})
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_admin_user_edit(self):
        self.client.force_login(self.admin)
        url = reverse("dashboard:admin_user_edit", kwargs={"pk": self.citizen.pk})
        self.assertEqual(self.client.get(url).status_code, 200)


class CsvExportSmokeTests(_Setup):
    """Tous les exports CSV répondent 200 et téléchargent un fichier."""

    URLS = [
        "dashboard:admin_permits_export",
        "dashboard:admin_payments_export",
        "dashboard:admin_users_export",
        "dashboard:admin_requests_export",
        "dashboard:admin_audit_export",
    ]

    def test_each_export_returns_csv(self):
        self.client.force_login(self.admin)
        for name in self.URLS:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, name)
            self.assertIn("text/csv", response["Content-Type"], name)
