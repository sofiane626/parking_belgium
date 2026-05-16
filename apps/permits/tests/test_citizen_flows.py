"""
Tests d'intégration citoyen : permit_cancel, visitor flow (create + code + cancel code),
professional flow.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.test import Client, TestCase
from django.urls import reverse

from apps.citizens.models import Address
from apps.citizens.services import get_or_create_profile, upsert_address
from apps.companies.models import Company
from apps.core.models import Commune
from apps.gis_data.models import GISPolygon, GISSourceVersion
from apps.permits.models import (
    Permit, PermitConfig, PermitStatus, PermitType, VisitorCode, VisitorCodeStatus,
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
        cfg.professional_price_cents = 0
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
        # Riverain ACTIVE (prérequis pour visitor)
        rp = create_draft(self.user, self.vehicle, PermitType.RESIDENT)
        rp = submit_application(rp)
        if rp.status == PermitStatus.AWAITING_PAYMENT:
            rp = mark_paid(rp)
        self.resident_permit = rp
        self.client = Client()
        self.client.force_login(self.user)


class VisitorFlowTests(_Setup):
    """Création d'une carte visiteur + génération + annulation d'un code."""

    def test_visitor_create_get_shows_confirmation(self):
        response = self.client.get(reverse("permits:visitor_create"))
        self.assertEqual(response.status_code, 200)

    def test_visitor_create_post_activates_permit(self):
        response = self.client.post(reverse("permits:visitor_create"))
        self.assertEqual(response.status_code, 302)
        visitor = Permit.objects.filter(
            citizen=self.user, permit_type=PermitType.VISITOR,
        ).latest("created_at")
        self.assertIn(visitor.status, [PermitStatus.ACTIVE, PermitStatus.AWAITING_PAYMENT])

    def test_visitor_code_generation(self):
        self.client.post(reverse("permits:visitor_create"))
        visitor = Permit.objects.filter(
            citizen=self.user, permit_type=PermitType.VISITOR,
        ).latest("created_at")
        if visitor.status == PermitStatus.AWAITING_PAYMENT:
            mark_paid(visitor)
        url = reverse("permits:visitor_code_create", kwargs={"pk": visitor.pk})
        response = self.client.post(url, {"plate": "9-XYZ-999", "duration_hours": "2"})
        self.assertEqual(response.status_code, 302)
        code = VisitorCode.objects.get(permit=visitor)
        self.assertEqual(code.plate, "9-XYZ-999")
        self.assertEqual(code.status, VisitorCodeStatus.ACTIVE)


class PermitCancelTests(_Setup):
    """Annulation d'un permit en cours (par le citoyen)."""

    def test_cancel_active_not_allowed(self):
        # Une carte ACTIVE ne peut pas être annulée via cette vue
        url = reverse("permits:cancel", kwargs={"pk": self.resident_permit.pk})
        response = self.client.post(url)
        # Redirige vers detail avec un message d'erreur (PermitError attrapé)
        self.assertEqual(response.status_code, 302)
        self.resident_permit.refresh_from_db()
        self.assertEqual(self.resident_permit.status, PermitStatus.ACTIVE)


class PermitPayRedirectTests(_Setup):
    """La vue permit_pay redirige vers le flow payments."""

    def test_pay_redirects_to_payments_start(self):
        url = reverse("permits:pay", kwargs={"pk": self.resident_permit.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("payments:start", kwargs={"pk": self.resident_permit.pk}), response["Location"])
