"""
Pricing strategies + per-citizen / per-commune limit enforcement.
"""
import datetime as dt
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from apps.citizens.models import Address
from apps.citizens.services import get_or_create_profile, upsert_address
from apps.companies.services import create_company
from apps.core.models import Commune
from apps.gis_data.models import GISPolygon, GISSourceVersion
from apps.permits.models import (
    CommunePermitPolicy, Permit, PermitConfig, PermitStatus, PermitType, PriceStrategy,
)
from apps.permits.policies import (
    PolicyError, compute_price, enforce_max_companies_per_citizen,
    enforce_max_vehicles_per_citizen,
)
from apps.permits.services import create_draft, create_visitor_permit, mark_paid, submit_application
from apps.vehicles.services import create_vehicle

User = get_user_model()


def _seed_polygon(commune):
    v = GISSourceVersion.objects.create(name=f"t-{commune.niscode}", source_filename="x", srid=31370, polygon_count=1, is_active=True)
    GISPolygon.objects.create(
        version=v,
        geometry=MultiPolygon(Polygon(((1000, 1000), (2000, 1000), (2000, 2000), (1000, 2000), (1000, 1000))), srid=31370),
        zonecode="Z", niscode=commune.niscode, commune=commune,
    )
    return v


class PriceStrategyTests(TestCase):
    def setUp(self):
        self.commune = Commune.objects.get(niscode="21015")
        self.user = User.objects.create_user(username="u", password="Pw123!Aa")

    def test_fixed_price(self):
        p = CommunePermitPolicy.objects.filter(commune=self.commune, permit_type=PermitType.RESIDENT).first()
        p.price_strategy = PriceStrategy.FIXED
        p.price_fixed_cents = 2500
        p.save()
        self.assertEqual(compute_price(self.user, PermitType.RESIDENT, commune=self.commune), 2500)

    def test_grid_price_picks_largest_threshold_at_or_below_rank(self):
        p = CommunePermitPolicy.objects.filter(commune=self.commune, permit_type=PermitType.RESIDENT).first()
        p.price_strategy = PriceStrategy.GRID
        p.price_grid = [[1, 1000], [2, 2500], [3, 5000]]
        p.save()
        # rank=1 (no existing resident permit)
        self.assertEqual(compute_price(self.user, PermitType.RESIDENT, commune=self.commune), 1000)

    def test_exponential_price(self):
        p = CommunePermitPolicy.objects.filter(commune=self.commune, permit_type=PermitType.RESIDENT).first()
        p.price_strategy = PriceStrategy.EXPONENTIAL
        p.price_exponential_base_cents = 1000
        p.price_exponential_factor = Decimal("2.00")
        p.save()
        # rank=1 → 1000 * 2^0 = 1000
        self.assertEqual(compute_price(self.user, PermitType.RESIDENT, commune=self.commune), 1000)


class GlobalLimitsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="Pw123!Aa")

    def test_max_vehicles_enforced(self):
        cfg = PermitConfig.get()
        cfg.max_vehicles_per_citizen = 2
        cfg.save()
        create_vehicle(owner=self.user, plate="1-AAA-001", brand="A", model="A")
        create_vehicle(owner=self.user, plate="1-AAA-002", brand="A", model="A")
        with self.assertRaises(PolicyError):
            create_vehicle(owner=self.user, plate="1-AAA-003", brand="A", model="A")

    def test_max_companies_enforced(self):
        cfg = PermitConfig.get()
        cfg.max_companies_per_citizen = 1
        cfg.save()
        commune = Commune.objects.get(niscode="21015")
        create_company(
            owner=self.user, name="A", vat_number="BE0123456789", activity="x",
            street="x", number="1", postal_code="1030", commune=commune, country="BE",
        )
        with self.assertRaises(PolicyError):
            create_company(
                owner=self.user, name="B", vat_number="BE0987654321", activity="x",
                street="x", number="1", postal_code="1030", commune=commune, country="BE",
            )


class PolicyEnforcedAtCreationTests(TestCase):
    def setUp(self):
        self.commune = Commune.objects.get(niscode="21015")
        _seed_polygon(self.commune)
        self.user = User.objects.create_user(username="u", password="Pw123!Aa")
        profile = get_or_create_profile(self.user)
        upsert_address(
            profile, user=self.user, street="X", number="1", box="",
            postal_code="1030", commune=self.commune, country="BE",
        )
        addr = Address.objects.get(profile=profile)
        addr.location = Point(1500, 1500, srid=31370)
        addr.save()
        self.car = create_vehicle(owner=self.user, plate="1-AAA-111", brand="R", model="C")

    def test_disabled_card_type_blocks_creation(self):
        p = CommunePermitPolicy.objects.filter(commune=self.commune, permit_type=PermitType.RESIDENT).first()
        p.is_enabled = False
        p.save()
        with self.assertRaises(PolicyError):
            create_draft(self.user, self.car, PermitType.RESIDENT)

    def test_auto_attribution_off_forces_manual_review(self):
        p = CommunePermitPolicy.objects.filter(commune=self.commune, permit_type=PermitType.RESIDENT).first()
        p.auto_attribution = False
        p.save()
        permit = submit_application(create_draft(self.user, self.car, PermitType.RESIDENT))
        self.assertEqual(permit.status, PermitStatus.MANUAL_REVIEW)

    def test_validity_days_used_at_activation(self):
        p = CommunePermitPolicy.objects.filter(commune=self.commune, permit_type=PermitType.RESIDENT).first()
        p.validity_days = 90
        p.save()
        permit = mark_paid(submit_application(create_draft(self.user, self.car, PermitType.RESIDENT)))
        self.assertEqual((permit.valid_until - permit.valid_from).days, 90)
