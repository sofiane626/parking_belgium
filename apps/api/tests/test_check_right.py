"""
Couvre l'API publique :
- check-right refuse sans token
- check-right autorise une plaque liée à un permit ACTIVE
- check-right refuse si la zone demandée n'est pas couverte
- check-right refuse si la carte est expirée
- check-right refuse si le véhicule est archivé
- check-right autorise via VisitorCode
- communes / zones renvoient les listes attendues
- token endpoint échange username+password contre un token
"""
from __future__ import annotations

import datetime as dt

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.citizens.models import Address
from apps.citizens.services import get_or_create_profile, upsert_address
from apps.core.models import Commune
from apps.gis_data.models import GISPolygon, GISSourceVersion
from apps.permits.models import Permit, PermitConfig, PermitStatus, PermitType
from apps.permits.services import create_draft, generate_visitor_code, mark_paid, submit_application
from apps.vehicles.services import create_vehicle

User = get_user_model()


class _BaseAPI(TestCase):
    def setUp(self):
        # Carte gratuite → activation automatique sans passer par le paiement.
        cfg = PermitConfig.get()
        cfg.resident_price_cents = 0
        cfg.save()

        self.commune = Commune.objects.get(niscode="21015")
        self.version = GISSourceVersion.objects.create(
            name="t", source_filename="x", srid=31370,
            polygon_count=1, is_active=True,
        )
        square = Polygon(((1000, 1000), (2000, 1000), (2000, 2000), (1000, 2000), (1000, 1000)))
        self.polygon = GISPolygon.objects.create(
            version=self.version,
            geometry=MultiPolygon(square, srid=31370),
            zonecode="ZONE-A", niscode="21015", commune=self.commune,
        )

        self.user = User.objects.create_user(
            username="alice", email="alice@example.com", password="Pw123!Aa",
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
        permit = create_draft(self.user, self.vehicle, PermitType.RESIDENT)
        self.permit = submit_application(permit)
        # Si une CommunePermitPolicy seedée force un prix > 0, on simule le
        # paiement pour atteindre ACTIVE — l'API teste l'autorisation, pas le
        # workflow de paiement (déjà couvert par apps.payments.tests).
        if self.permit.status == PermitStatus.AWAITING_PAYMENT:
            self.permit = mark_paid(self.permit)
        self.assertEqual(self.permit.status, PermitStatus.ACTIVE)

        # Compte agent → autorisé à recevoir un token et à appeler l'API.
        self.agent = User.objects.create_user(
            username="agent", password="Pw123!Aa", role="agent",
        )
        self.token = Token.objects.create(user=self.agent)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")


class CheckRightAuthTests(_BaseAPI):
    def test_unauthenticated_refused(self):
        anon = APIClient()
        resp = anon.get(reverse("api:check-right"), {"plate": "1-AAA-111"})
        self.assertIn(resp.status_code, (401, 403))

    def test_token_required(self):
        wrong = APIClient()
        wrong.credentials(HTTP_AUTHORIZATION="Token notavalidkey")
        resp = wrong.get(reverse("api:check-right"), {"plate": "1-AAA-111"})
        self.assertEqual(resp.status_code, 401)


class CheckRightLogicTests(_BaseAPI):
    def test_authorized_for_active_resident_permit(self):
        resp = self.client.get(reverse("api:check-right"), {"plate": "1-AAA-111"})
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertTrue(data["authorized"])
        self.assertEqual(data["plate"], "1-AAA-111")
        self.assertEqual(data["permit"]["id"], self.permit.pk)
        self.assertIn("ZONE-A", data["permit"]["zones"])

    def test_authorized_in_correct_zone(self):
        resp = self.client.get(
            reverse("api:check-right"),
            {"plate": "1-AAA-111", "zone": "ZONE-A"},
        )
        self.assertTrue(resp.json()["authorized"])

    def test_refused_in_wrong_zone(self):
        resp = self.client.get(
            reverse("api:check-right"),
            {"plate": "1-AAA-111", "zone": "ZONE-Z"},
        )
        data = resp.json()
        self.assertFalse(data["authorized"])
        self.assertIsNone(data["permit"])

    def test_unknown_plate_refused(self):
        resp = self.client.get(reverse("api:check-right"), {"plate": "9-ZZZ-999"})
        self.assertFalse(resp.json()["authorized"])

    def test_normalizes_plate_input(self):
        resp = self.client.get(reverse("api:check-right"), {"plate": "1-aaa-111  "})
        self.assertTrue(resp.json()["authorized"])

    def test_expired_permit_refused(self):
        self.permit.valid_until = timezone.localdate() - dt.timedelta(days=1)
        self.permit.save(update_fields=["valid_until"])
        resp = self.client.get(reverse("api:check-right"), {"plate": "1-AAA-111"})
        self.assertFalse(resp.json()["authorized"])

    def test_archived_vehicle_refused(self):
        self.vehicle.archived_at = timezone.now()
        self.vehicle.save(update_fields=["archived_at"])
        resp = self.client.get(reverse("api:check-right"), {"plate": "1-AAA-111"})
        self.assertFalse(resp.json()["authorized"])

    def test_visitor_code_authorizes_third_party_plate(self):
        # Active une carte visiteur dérivée de la carte riverain
        cfg = PermitConfig.get()
        cfg.visitor_price_cents = 0
        cfg.save()
        from apps.permits.services import create_visitor_permit
        visitor = create_visitor_permit(self.user)
        self.assertEqual(visitor.status, PermitStatus.ACTIVE)
        code = generate_visitor_code(visitor, plate="2-BBB-222", duration_hours=4)

        resp = self.client.get(reverse("api:check-right"), {"plate": "2-BBB-222"})
        data = resp.json()
        self.assertTrue(data["authorized"])
        self.assertEqual(data["permit"]["id"], visitor.pk)

    def test_missing_plate_param_returns_400(self):
        resp = self.client.get(reverse("api:check-right"))
        self.assertEqual(resp.status_code, 400)

    def test_invalid_at_format_returns_400(self):
        resp = self.client.get(
            reverse("api:check-right"),
            {"plate": "1-AAA-111", "at": "not-a-date"},
        )
        self.assertEqual(resp.status_code, 400)


class CommuneZoneListingTests(_BaseAPI):
    def test_communes_listed(self):
        resp = self.client.get(reverse("api:communes"))
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        # Les 19 communes sont seedées par migration
        self.assertEqual(len(body), 19)
        nis = {c["niscode"] for c in body}
        self.assertIn("21015", nis)

    def test_zones_filtered_by_commune(self):
        resp = self.client.get(reverse("api:zones"), {"commune": "21015"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["zonecode"], "ZONE-A")
        self.assertEqual(body[0]["commune_niscode"], "21015")

    def test_zones_unknown_commune_returns_empty(self):
        resp = self.client.get(reverse("api:zones"), {"commune": "00000"})
        self.assertEqual(resp.json(), [])


class TokenEndpointTests(_BaseAPI):
    def test_obtain_token_with_credentials(self):
        anon = APIClient()
        resp = anon.post(reverse("api:token"), {
            "username": "agent", "password": "Pw123!Aa",
        })
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIn("token", resp.json())

    def test_obtain_token_wrong_password(self):
        anon = APIClient()
        resp = anon.post(reverse("api:token"), {
            "username": "agent", "password": "WRONG",
        })
        self.assertEqual(resp.status_code, 400)
