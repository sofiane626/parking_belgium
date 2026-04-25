"""
Attribution engine matrix tests. The geocoder is bypassed by pre-setting
``Address.location`` directly, so these tests run offline and don't hit
Nominatim.
"""
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.test import TestCase

from apps.citizens.models import Address
from apps.citizens.services import get_or_create_profile
from apps.core.models import Commune
from apps.gis_data.models import GISPolygon, GISSourceVersion
from apps.rules.models import PermitType, PolygonRule, RuleAction
from apps.rules.services import resolve_zones

User = get_user_model()


class AttributionEngineTests(TestCase):
    def setUp(self):
        self.commune = Commune.objects.get(niscode="21015")
        self.version = GISSourceVersion.objects.create(
            name="t", source_filename="test.shp", srid=31370,
            polygon_count=1, is_active=True,
        )
        # Square polygon in Lambert 72 covering [1000..2000, 1000..2000].
        square = Polygon(
            ((1000, 1000), (2000, 1000), (2000, 2000), (1000, 2000), (1000, 1000)),
        )
        self.polygon = GISPolygon.objects.create(
            version=self.version,
            geometry=MultiPolygon(square, srid=31370),
            zonecode="ZONE-A",
            niscode="21015",
            commune=self.commune,
        )
        u = User.objects.create_user(username="u", password="Pw123!Aa")
        profile = get_or_create_profile(u)
        self.address = Address.objects.create(
            profile=profile, street="Rue X", number="1", postal_code="1030",
            commune=self.commune, country="BE",
            location=Point(1500, 1500, srid=31370),  # inside the square
        )

    def _rule(self, **kw):
        defaults = dict(
            polygon=self.polygon, commune=self.commune,
            permit_type=PermitType.RESIDENT, priority=100, is_active=True,
        )
        defaults.update(kw)
        return PolygonRule.objects.create(**defaults)

    def test_no_rules_returns_polygon_zonecode(self):
        r = resolve_zones(self.address, PermitType.RESIDENT)
        self.assertEqual(r.main_zone, "ZONE-A")
        self.assertEqual(r.additional_zones, [])
        self.assertFalse(r.requires_manual_review)
        self.assertFalse(r.denied)
        self.assertEqual(r.polygon, self.polygon)

    def test_add_zone_appends(self):
        self._rule(action_type=RuleAction.ADD_ZONE, target_zone_code="EXTRA-1")
        self._rule(action_type=RuleAction.ADD_ZONE, target_zone_code="EXTRA-2", priority=200)
        r = resolve_zones(self.address, PermitType.RESIDENT)
        self.assertEqual(r.main_zone, "ZONE-A")
        self.assertEqual(r.additional_zones, ["EXTRA-1", "EXTRA-2"])
        self.assertEqual(r.all_zones, ["ZONE-A", "EXTRA-1", "EXTRA-2"])

    def test_replace_main_zone_first_wins(self):
        self._rule(action_type=RuleAction.REPLACE_MAIN_ZONE, target_zone_code="HIGH", priority=10)
        self._rule(action_type=RuleAction.REPLACE_MAIN_ZONE, target_zone_code="LOW", priority=100)
        r = resolve_zones(self.address, PermitType.RESIDENT)
        self.assertEqual(r.main_zone, "HIGH")

    def test_manual_review_flag(self):
        self._rule(action_type=RuleAction.MANUAL_REVIEW)
        r = resolve_zones(self.address, PermitType.RESIDENT)
        self.assertTrue(r.requires_manual_review)
        self.assertEqual(r.main_zone, "ZONE-A")  # other rules still apply

    def test_deny_short_circuits(self):
        self._rule(action_type=RuleAction.ADD_ZONE, target_zone_code="X", priority=10)
        self._rule(action_type=RuleAction.DENY, priority=20)
        self._rule(action_type=RuleAction.ADD_ZONE, target_zone_code="Y", priority=30)
        r = resolve_zones(self.address, PermitType.RESIDENT)
        self.assertTrue(r.denied)
        self.assertIsNone(r.main_zone)
        self.assertEqual(r.additional_zones, [])
        # Y should never have been processed
        self.assertNotIn("Y", [r.target_zone_code for r in r.applied_rules])

    def test_permit_type_isolation(self):
        self._rule(permit_type=PermitType.VISITOR, action_type=RuleAction.DENY)
        r = resolve_zones(self.address, PermitType.RESIDENT)
        self.assertFalse(r.denied)
        self.assertEqual(r.main_zone, "ZONE-A")

    def test_inactive_rule_ignored(self):
        self._rule(action_type=RuleAction.DENY, is_active=False)
        r = resolve_zones(self.address, PermitType.RESIDENT)
        self.assertFalse(r.denied)

    def test_point_outside_any_polygon_triggers_manual_review(self):
        self.address.location = Point(5000, 5000, srid=31370)
        self.address.save()
        r = resolve_zones(self.address, PermitType.RESIDENT)
        self.assertIsNone(r.main_zone)
        self.assertTrue(r.requires_manual_review)
        self.assertIsNone(r.polygon)
