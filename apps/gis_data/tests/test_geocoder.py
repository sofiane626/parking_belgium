"""Geocoder tests — Nominatim is mocked; no network calls."""
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.test import TestCase

from apps.citizens.models import Address
from apps.citizens.services import get_or_create_profile
from apps.core.models import Commune
from apps.gis_data import services as gis_services
from apps.gis_data.models import GISPolygon, GISSourceVersion

User = get_user_model()


def _make_address():
    u = User.objects.create_user(username="gc", password="Pw123!Aa")
    profile = get_or_create_profile(u)
    return Address.objects.create(
        profile=profile, street="Rue Royale", number="1", postal_code="1000",
        commune=Commune.objects.get(niscode="21004"), country="BE",
    )


class GeocoderTests(TestCase):
    def setUp(self):
        # Reset cache between tests
        gis_services._GEOCODE_CACHE.clear()

    @patch("apps.gis_data.services.requests.get")
    def test_nominatim_success(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: [{"lat": "50.851", "lon": "4.357"}],
        )
        mock_get.return_value.raise_for_status = lambda: None
        addr = _make_address()
        result = gis_services.geocode_address(addr)
        self.assertIsNotNone(result)
        self.assertEqual(result.source, "nominatim")
        self.assertAlmostEqual(result.point.x, 4.357, places=3)
        self.assertAlmostEqual(result.point.y, 50.851, places=3)

    @patch("apps.gis_data.services.requests.get")
    def test_falls_back_to_commune_centroid(self, mock_get):
        # Nominatim returns no result
        mock_get.return_value = MagicMock(status_code=200, json=lambda: [])
        mock_get.return_value.raise_for_status = lambda: None

        # Seed an active GIS polygon for the commune so centroid fallback can compute
        v = GISSourceVersion.objects.create(
            name="t", source_filename="x", srid=31370, polygon_count=1, is_active=True,
        )
        commune = Commune.objects.get(niscode="21004")
        square = Polygon(
            ((148000, 168000), (152000, 168000), (152000, 172000), (148000, 172000), (148000, 168000)),
        )
        GISPolygon.objects.create(
            version=v, geometry=MultiPolygon(square, srid=31370),
            zonecode="C", niscode="21004", commune=commune,
        )

        addr = _make_address()
        result = gis_services.geocode_address(addr)
        self.assertIsNotNone(result)
        self.assertEqual(result.source, "commune_centroid")
        # Centroid in WGS84 of a Brussels-centered square should be near 4.35°E / 50.85°N
        self.assertAlmostEqual(result.point.x, 4.35, places=1)
        self.assertAlmostEqual(result.point.y, 50.85, places=1)

    @patch("apps.gis_data.services.requests.get")
    def test_returns_none_when_both_fail(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, json=lambda: [])
        mock_get.return_value.raise_for_status = lambda: None
        # No GIS polygon for the commune → no centroid available either
        addr = _make_address()
        result = gis_services.geocode_address(addr)
        self.assertIsNone(result)

    @patch("apps.gis_data.services.requests.get")
    def test_cache_avoids_second_call(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: [{"lat": "50.851", "lon": "4.357"}],
        )
        mock_get.return_value.raise_for_status = lambda: None
        addr = _make_address()
        gis_services.geocode_address(addr)
        gis_services.geocode_address(addr)  # should hit cache
        self.assertEqual(mock_get.call_count, 1)
