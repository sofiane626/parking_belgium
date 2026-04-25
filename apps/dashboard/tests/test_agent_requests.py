from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role
from apps.citizens.models import AddressChangeRequest, RequestStatus
from apps.citizens.services import get_or_create_profile, submit_address_change, upsert_address
from apps.core.models import Commune

User = get_user_model()


class AgentRequestsAccessTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="pwd123!Aa")
        self.alice.role = Role.CITIZEN
        self.alice.save()
        profile = get_or_create_profile(self.alice)
        commune = Commune.objects.get(niscode="21015")
        upsert_address(
            profile, user=self.alice,
            street="Rue 1", number="1", box="", postal_code="1030",
            commune=commune, country="BE",
        )
        self.req = submit_address_change(
            profile, user=self.alice,
            street="Grand-Place", number="1", box="",
            postal_code="1000", commune=Commune.objects.get(niscode="21004"),
            country="BE", reason="d",
        )
        self.agent = User.objects.create_user(username="agent_jo", password="pwd123!Aa")
        self.agent.role = Role.AGENT
        self.agent.save()

    def test_citizen_blocked_from_agent_list(self):
        self.client.login(username="alice", password="pwd123!Aa")
        resp = self.client.get(reverse("dashboard:agent_requests"))
        self.assertEqual(resp.status_code, 403)

    def test_agent_can_access_list(self):
        self.client.login(username="agent_jo", password="pwd123!Aa")
        resp = self.client.get(reverse("dashboard:agent_requests"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Grand-Place")

    def test_agent_can_approve_address_change(self):
        self.client.login(username="agent_jo", password="pwd123!Aa")
        resp = self.client.post(
            reverse("dashboard:agent_request_address_approve", args=[self.req.pk]),
            data={"notes": "OK"},
        )
        self.assertEqual(resp.status_code, 302)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, RequestStatus.APPROVED)
        self.assertEqual(self.req.decided_by, self.agent)
