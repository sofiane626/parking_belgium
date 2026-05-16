"""
Couvre :
- accès refusé aux non-admin sur les exports CSV
- réponse Content-Type + Content-Disposition + BOM Excel
- une entrée AuditLog CSV_EXPORTED est créée à chaque téléchargement
- le contenu inclut au moins l'en-tête + les lignes attendues
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import Role
from apps.audit.models import AuditAction, AuditLog

User = get_user_model()


def _join_streaming(response) -> str:
    """Concatène les chunks d'une StreamingHttpResponse en str unique."""
    return b"".join(response.streaming_content).decode("utf-8")


class _Setup(TestCase):
    def setUp(self):
        self.client = Client()
        self.citizen = User.objects.create_user(
            username="citizen", password="Pw1!Aa", role=Role.CITIZEN,
        )
        self.admin = User.objects.create_user(
            username="admin", password="Pw1!Aa", role=Role.ADMIN,
        )


class CsvExportPermissionTests(_Setup):
    """Tous les exports refusent l'accès aux non-admin."""

    URLS = [
        "dashboard:admin_permits_export",
        "dashboard:admin_payments_export",
        "dashboard:admin_users_export",
        "dashboard:admin_requests_export",
    ]

    def test_anonymous_redirected_to_login(self):
        for name in self.URLS:
            response = self.client.get(reverse(name))
            self.assertIn(response.status_code, (302, 301))

    def test_citizen_gets_403(self):
        self.client.force_login(self.citizen)
        for name in self.URLS:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 403, name)

    def test_admin_ok(self):
        self.client.force_login(self.admin)
        for name in self.URLS:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, name)


class CsvExportContentTests(_Setup):
    """Format CSV (UTF-8 BOM, séparateur ;) + audit log."""

    def test_users_export_returns_csv_with_admin_user(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:admin_users_export"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertIn("users_", response["Content-Disposition"])

        body = _join_streaming(response)
        # BOM Excel présent
        self.assertTrue(body.startswith("﻿"))
        # En-tête + au moins la ligne admin
        self.assertIn("username", body)
        self.assertIn("admin", body)
        self.assertIn(";", body)  # séparateur

    def test_export_creates_audit_entry(self):
        self.client.force_login(self.admin)
        before = AuditLog.objects.filter(action=AuditAction.CSV_EXPORTED).count()
        response = self.client.get(reverse("dashboard:admin_users_export"))
        # Forcer la consommation du streaming pour que la vue s'exécute jusqu'au bout
        _join_streaming(response)
        after = AuditLog.objects.filter(action=AuditAction.CSV_EXPORTED).count()
        self.assertEqual(after, before + 1)
        entry = AuditLog.objects.filter(action=AuditAction.CSV_EXPORTED).latest("created_at")
        self.assertEqual(entry.payload.get("context", {}).get("export"), "users")

    def test_permits_export_with_filters_passes(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("dashboard:admin_permits_export") + "?status=active&permit_type=resident"
        )
        self.assertEqual(response.status_code, 200)
        body = _join_streaming(response)
        self.assertIn("plaque", body)  # en-tête présent
