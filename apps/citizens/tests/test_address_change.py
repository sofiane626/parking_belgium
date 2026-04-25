from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from apps.citizens.models import Address, AddressChangeRequest, RequestStatus
from apps.citizens.services import (
    approve_address_change,
    cancel_address_change,
    get_or_create_profile,
    reject_address_change,
    submit_address_change,
    upsert_address,
)
from apps.citizens.signals import address_changed
from apps.core.models import Commune

User = get_user_model()


class AddressChangeRequestWorkflowTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="pwd123!Aa")
        self.profile = get_or_create_profile(self.alice)
        self.schaerbeek = Commune.objects.get(niscode="21015")
        self.bxl = Commune.objects.get(niscode="21004")
        upsert_address(
            self.profile, user=self.alice,
            street="Rue 1", number="1", box="", postal_code="1030",
            commune=self.schaerbeek, country="BE",
        )
        self.agent = User.objects.create_user(username="agent_jane", password="pwd123!Aa")

    def _payload(self, **over):
        data = dict(
            street="Grand-Place", number="1", box="",
            postal_code="1000", commune=self.bxl, country="BE",
            reason="Déménagement",
        )
        data.update(over)
        return data

    def test_submit_creates_pending_request(self):
        req = submit_address_change(self.profile, user=self.alice, **self._payload())
        self.assertEqual(req.status, RequestStatus.PENDING)
        self.assertIsNone(req.decided_at)

    def test_submit_rejects_other_user(self):
        bob = User.objects.create_user(username="bob", password="pwd123!Aa")
        with self.assertRaises(PermissionDenied):
            submit_address_change(self.profile, user=bob, **self._payload())

    def test_approve_applies_change_and_fires_signal(self):
        req = submit_address_change(self.profile, user=self.alice, **self._payload())
        signals = []
        address_changed.connect(lambda **kw: signals.append(kw), weak=False, dispatch_uid="t1")
        try:
            approve_address_change(req, agent=self.agent, notes="OK")
        finally:
            address_changed.disconnect(dispatch_uid="t1")

        req.refresh_from_db()
        self.assertEqual(req.status, RequestStatus.APPROVED)
        self.assertEqual(req.decided_by, self.agent)

        addr = Address.objects.get(profile=self.profile)
        self.assertEqual(addr.street, "Grand-Place")
        self.assertEqual(addr.commune, self.bxl)
        self.assertEqual(len(signals), 1)
        self.assertFalse(signals[0]["created"])

    def test_reject_does_not_change_address(self):
        req = submit_address_change(self.profile, user=self.alice, **self._payload())
        reject_address_change(req, agent=self.agent, notes="Adresse hors Bruxelles")
        req.refresh_from_db()
        self.assertEqual(req.status, RequestStatus.REJECTED)
        addr = Address.objects.get(profile=self.profile)
        self.assertEqual(addr.street, "Rue 1")  # unchanged

    def test_cancel_pending_request_by_owner_only(self):
        req = submit_address_change(self.profile, user=self.alice, **self._payload())
        bob = User.objects.create_user(username="bob", password="pwd123!Aa")
        with self.assertRaises(PermissionDenied):
            cancel_address_change(req, user=bob)
        cancel_address_change(req, user=self.alice)
        req.refresh_from_db()
        self.assertEqual(req.status, RequestStatus.CANCELLED)

    def test_cannot_approve_already_decided_request(self):
        req = submit_address_change(self.profile, user=self.alice, **self._payload())
        approve_address_change(req, agent=self.agent)
        with self.assertRaises(ValueError):
            approve_address_change(req, agent=self.agent)
