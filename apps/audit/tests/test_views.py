"""
Vue dashboard journal d'audit :
- liste accessible aux admins
- refusée aux citoyens
- filtres action/sévérité fonctionnent
- export CSV produit le bon Content-Type et inclut les colonnes attendues
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role
from apps.audit.models import AuditAction, AuditSeverity
from apps.audit.services import log

User = get_user_model()


class AuditViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="adm", password="Pw123!Aa", role=Role.ADMIN,
        )
        self.citizen = User.objects.create_user(
            username="cit", password="Pw123!Aa",
        )
        # Quelques entrées
        for _ in range(3):
            log(AuditAction.PERMIT_ACTIVATED, actor=self.admin)
        log(AuditAction.AUTH_FAILED, actor=None,
            payload={"context": {"username": "intruder"}})

    def test_admin_sees_list(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("dashboard:admin_audit"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "permit_activated")
        self.assertContains(resp, "auth_failed")

    def test_citizen_refused(self):
        self.client.force_login(self.citizen)
        resp = self.client.get(reverse("dashboard:admin_audit"))
        self.assertEqual(resp.status_code, 403)

    def test_filter_by_severity(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("dashboard:admin_audit"), {"severity": "warning"})
        self.assertContains(resp, "auth_failed")
        # PERMIT_ACTIVATED est INFO → ne doit pas apparaître dans le tbody.
        # Vérifie via le compteur total renvoyé en context.
        self.assertEqual(resp.context["total_count"], 1)

    def test_csv_export(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("dashboard:admin_audit_export"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp["Content-Type"])
        body = resp.content.decode("utf-8-sig")
        self.assertIn("permit_activated", body)
        self.assertIn("auth_failed", body)
        # En-tête présente
        self.assertIn("severity", body.splitlines()[0])
