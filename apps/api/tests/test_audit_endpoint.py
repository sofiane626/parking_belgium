"""
Couvre l'endpoint datatable d'audit /api/v1/audit/ :
- Permissions admin/super_admin only
- Filtres action / severity / target_type / actor / dates / q
- Pagination par cursor
- Réponse contient counts_by_severity et meta
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.audit.models import AuditAction, AuditSeverity
from apps.audit.services import log

User = get_user_model()


class AuditEndpointTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="adm", password="x", role=Role.ADMIN,
        )
        self.citizen = User.objects.create_user(
            username="cit", password="x", role=Role.CITIZEN,
        )
        # Quelques entrées d'audit avec diverses sévérités
        for _ in range(5):
            log(AuditAction.PERMIT_ACTIVATED, actor=self.admin)        # info
        for _ in range(3):
            log(AuditAction.PERMIT_SUSPENDED, actor=self.admin)        # warning
        log(AuditAction.GIS_ACTIVE_VERSION_CHANGED, actor=None)        # critical
        log(AuditAction.AUTH_FAILED, actor=None,
            payload={"context": {"username": "intruder"}}, ip="1.2.3.4")
        self.url = reverse("api:audit-list")
        self.client = APIClient()

    def test_admin_can_list(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("items", data)
        self.assertIn("counts_by_severity", data)
        self.assertIn("meta", data)
        self.assertGreaterEqual(data["total_filtered"], 10)

    def test_citizen_refused(self):
        self.client.force_authenticate(self.citizen)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 403)

    def test_unauthenticated_refused(self):
        r = self.client.get(self.url)
        self.assertIn(r.status_code, (401, 403))

    def test_filter_by_severity(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get(self.url, {"severity": "warning"})
        items = r.json()["items"]
        self.assertTrue(all(i["severity"] == "warning" for i in items))
        # 3 PERMIT_SUSPENDED + 1 AUTH_FAILED (les deux sont severity=warning)
        self.assertEqual(r.json()["total_filtered"], 4)

    def test_filter_by_action(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get(self.url, {"action": AuditAction.PERMIT_ACTIVATED.value})
        self.assertEqual(r.json()["total_filtered"], 5)

    def test_filter_by_actor(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get(self.url, {"actor": "adm"})
        items = r.json()["items"]
        for it in items:
            self.assertEqual(it["actor"], "adm")

    def test_search_q_matches_ip(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get(self.url, {"q": "1.2.3"})
        self.assertEqual(r.json()["total_filtered"], 1)

    def test_invalid_date_returns_400(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get(self.url, {"date_from": "not-a-date"})
        self.assertEqual(r.status_code, 400)

    def test_cursor_pagination(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get(self.url, {"page_size": 3})
        data = r.json()
        self.assertEqual(len(data["items"]), 3)
        self.assertIsNotNone(data["next_cursor"])
        # Page 2
        r2 = self.client.get(self.url, {"page_size": 3, "cursor": data["next_cursor"]})
        items_page2 = r2.json()["items"]
        # Pas d'overlap entre les deux pages
        ids1 = {i["id"] for i in data["items"]}
        ids2 = {i["id"] for i in items_page2}
        self.assertEqual(ids1 & ids2, set())

    def test_meta_includes_choices(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get(self.url)
        meta = r.json()["meta"]
        self.assertGreater(len(meta["actions"]), 10)
        self.assertEqual(len(meta["severities"]), 4)
