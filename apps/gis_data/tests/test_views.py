from django.contrib.gis.geos import MultiPolygon, Polygon
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Commune
from apps.gis_data.models import GISPolygon, GISSourceVersion


class MapEndpointsTests(TestCase):
    def setUp(self):
        self.version = GISSourceVersion.objects.create(
            name="t", source_filename="test.shp", srid=31370,
            polygon_count=1, is_active=True,
        )
        square = Polygon(
            ((140000, 160000), (160000, 160000), (160000, 180000), (140000, 180000), (140000, 160000)),
        )
        self.polygon = GISPolygon.objects.create(
            version=self.version,
            geometry=MultiPolygon(square, srid=31370),
            zonecode="ZONE-T",
            niscode="21015",
            commune=Commune.objects.get(niscode="21015"),
            name_fr="Test zone",
        )

    def test_map_page_renders(self):
        r = self.client.get(reverse("gis_data:map"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "polygons.geojson")

    def test_geojson_returns_active_features(self):
        r = self.client.get(reverse("gis_data:polygons_geojson"))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["type"], "FeatureCollection")
        self.assertEqual(len(data["features"]), 1)
        feat = data["features"][0]
        self.assertEqual(feat["properties"]["zonecode"], "ZONE-T")
        self.assertEqual(feat["properties"]["commune"], "Schaerbeek")

    def test_geojson_filters_by_commune(self):
        r = self.client.get(reverse("gis_data:polygons_geojson") + "?commune=21001")
        self.assertEqual(len(r.json()["features"]), 0)
        r = self.client.get(reverse("gis_data:polygons_geojson") + "?commune=21015")
        self.assertEqual(len(r.json()["features"]), 1)

    def test_inactive_version_excluded(self):
        self.version.is_active = False
        self.version.save()
        r = self.client.get(reverse("gis_data:polygons_geojson"))
        self.assertEqual(len(r.json()["features"]), 0)
