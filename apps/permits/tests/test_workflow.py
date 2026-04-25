"""
End-to-end test of the resident permit workflow.

Address.location is pre-set so the engine doesn't hit the network. The active
GIS version + a single covering polygon are seeded in setUp.
"""
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from apps.citizens.models import Address
from apps.citizens.services import get_or_create_profile, upsert_address
from apps.core.models import Commune
from apps.gis_data.models import GISPolygon, GISSourceVersion
from apps.permits.models import (
    Permit, PermitStatus, PermitType, PermitZone,
)
from apps.permits.services import (
    PermitError, approve_manual_review, cancel, create_draft,
    mark_paid, refuse, submit_application,
    suspend_active_permits_for_citizen, suspend_active_permits_for_vehicle,
)
from apps.rules.models import PermitType as RulePermitType, PolygonRule, RuleAction
from apps.vehicles.services import create_vehicle

User = get_user_model()


class _Setup(TestCase):
    def setUp(self):
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
        self.alice = User.objects.create_user(username="alice", password="Pw123!Aa")
        profile = get_or_create_profile(self.alice)
        upsert_address(
            profile, user=self.alice,
            street="Rue X", number="1", box="", postal_code="1030",
            commune=self.commune, country="BE",
        )
        # Pre-set location so the engine skips geocoding.
        addr = Address.objects.get(profile=profile)
        addr.location = Point(1500, 1500, srid=31370)
        addr.save()
        self.car = create_vehicle(
            owner=self.alice, plate="1-AAA-111", brand="Renault", model="Clio",
        )
        self.agent = User.objects.create_user(username="agent_jo", password="Pw123!Aa")


class HappyPathTests(_Setup):
    def test_full_flow_to_active(self):
        permit = create_draft(self.alice, self.car, PermitType.RESIDENT)
        self.assertEqual(permit.status, PermitStatus.DRAFT)

        permit = submit_application(permit)
        self.assertEqual(permit.status, PermitStatus.AWAITING_PAYMENT)
        self.assertEqual(permit.attribution_snapshot["main_zone"], "ZONE-A")
        self.assertIsNotNone(permit.awaiting_payment_at)

        permit = mark_paid(permit)
        self.assertEqual(permit.status, PermitStatus.ACTIVE)
        self.assertIsNotNone(permit.activated_at)
        self.assertIsNotNone(permit.valid_from)

        zones = list(PermitZone.objects.filter(permit=permit))
        self.assertEqual(len(zones), 1)
        self.assertEqual(zones[0].zone_code, "ZONE-A")
        self.assertTrue(zones[0].is_main)


class ManualReviewTests(_Setup):
    def test_rule_forces_manual_review(self):
        PolygonRule.objects.create(
            polygon=self.polygon, commune=self.commune,
            permit_type=RulePermitType.RESIDENT, action_type=RuleAction.MANUAL_REVIEW,
        )
        permit = submit_application(create_draft(self.alice, self.car, PermitType.RESIDENT))
        self.assertEqual(permit.status, PermitStatus.MANUAL_REVIEW)

        # Agent approves → awaiting_payment.
        permit = approve_manual_review(permit, agent=self.agent, notes="OK")
        self.assertEqual(permit.status, PermitStatus.AWAITING_PAYMENT)
        self.assertEqual(permit.decided_by, self.agent)


class RefusedTests(_Setup):
    def test_deny_rule_refuses_immediately(self):
        PolygonRule.objects.create(
            polygon=self.polygon, commune=self.commune,
            permit_type=RulePermitType.RESIDENT, action_type=RuleAction.DENY,
        )
        permit = submit_application(create_draft(self.alice, self.car, PermitType.RESIDENT))
        self.assertEqual(permit.status, PermitStatus.REFUSED)

    def test_agent_can_refuse_manual_review(self):
        PolygonRule.objects.create(
            polygon=self.polygon, commune=self.commune,
            permit_type=RulePermitType.RESIDENT, action_type=RuleAction.MANUAL_REVIEW,
        )
        permit = submit_application(create_draft(self.alice, self.car, PermitType.RESIDENT))
        permit = refuse(permit, agent=self.agent, notes="hors-périmètre")
        self.assertEqual(permit.status, PermitStatus.REFUSED)
        self.assertEqual(permit.decision_notes, "hors-périmètre")

    def test_refuse_requires_notes(self):
        PolygonRule.objects.create(
            polygon=self.polygon, commune=self.commune,
            permit_type=RulePermitType.RESIDENT, action_type=RuleAction.MANUAL_REVIEW,
        )
        permit = submit_application(create_draft(self.alice, self.car, PermitType.RESIDENT))
        with self.assertRaises(PermitError):
            refuse(permit, agent=self.agent, notes="")


class CancellationTests(_Setup):
    def test_citizen_can_cancel_in_progress(self):
        permit = submit_application(create_draft(self.alice, self.car, PermitType.RESIDENT))
        self.assertEqual(permit.status, PermitStatus.AWAITING_PAYMENT)
        permit = cancel(permit, by_user=self.alice)
        self.assertEqual(permit.status, PermitStatus.CANCELLED)

    def test_other_user_cannot_cancel(self):
        permit = submit_application(create_draft(self.alice, self.car, PermitType.RESIDENT))
        bob = User.objects.create_user(username="bob", password="Pw123!Aa")
        with self.assertRaises(PermissionDenied):
            cancel(permit, by_user=bob)


class SignalSubscriberTests(_Setup):
    def test_address_change_suspends_active_permits(self):
        # Activate a permit
        p = mark_paid(submit_application(create_draft(self.alice, self.car, PermitType.RESIDENT)))
        self.assertEqual(p.status, PermitStatus.ACTIVE)

        # Citizen's address changes → handler should suspend
        upsert_address(
            self.alice.citizen_profile, user=self.alice,
            street="Nouvelle", number="9", box="", postal_code="1000",
            commune=Commune.objects.get(niscode="21004"), country="BE",
        )
        p.refresh_from_db()
        self.assertEqual(p.status, PermitStatus.SUSPENDED)
        self.assertIn("Adresse modifiée", p.suspension_reason)

    def test_plate_change_suspends_card_for_that_vehicle(self):
        p = mark_paid(submit_application(create_draft(self.alice, self.car, PermitType.RESIDENT)))
        # Use the public service that also fires the signal
        from apps.vehicles.services import approve_plate_change, submit_plate_change
        req = submit_plate_change(self.car, user=self.alice, new_plate="1-NEW-999")
        approve_plate_change(req, agent=self.agent)
        p.refresh_from_db()
        self.assertEqual(p.status, PermitStatus.SUSPENDED)
        self.assertIn("Plaque changée", p.suspension_reason)


class SuspensionHelperTests(_Setup):
    def test_bulk_suspend_for_citizen(self):
        p = mark_paid(submit_application(create_draft(self.alice, self.car, PermitType.RESIDENT)))
        n = suspend_active_permits_for_citizen(self.alice, reason="test")
        self.assertEqual(n, 1)
        p.refresh_from_db()
        self.assertEqual(p.status, PermitStatus.SUSPENDED)


class GuardrailTests(_Setup):
    def test_cannot_submit_a_paid_permit(self):
        p = mark_paid(submit_application(create_draft(self.alice, self.car, PermitType.RESIDENT)))
        with self.assertRaises(PermitError):
            submit_application(p)

    def test_cannot_pay_a_draft(self):
        permit = create_draft(self.alice, self.car, PermitType.RESIDENT)
        with self.assertRaises(PermitError):
            mark_paid(permit)

    def test_resident_requires_vehicle(self):
        with self.assertRaises(PermitError):
            create_draft(self.alice, None, PermitType.RESIDENT)

    def test_cannot_create_for_someone_elses_vehicle(self):
        bob = User.objects.create_user(username="bob", password="Pw123!Aa")
        with self.assertRaises(PermissionDenied):
            create_draft(bob, self.car, PermitType.RESIDENT)
