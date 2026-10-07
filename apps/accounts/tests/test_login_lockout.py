"""
Couvre le verrouillage anti brute-force (5 échecs / 15 min → 15 min de blocage) :
- 4 échecs puis succès : pas de verrouillage, compteur remis à zéro
- 5 échecs : même le bon mot de passe est refusé, avec le message de blocage
- déverrouillage après expiration (horloge avancée)
- les tentatives pendant le blocage ne le prolongent pas
- identifiant inexistant traité exactement comme un vrai
- une seule entrée d'audit AUTH_LOCKED par verrouillage
- même protection sur POST /api/v1/token/ et sur /admin/login/
"""
from __future__ import annotations

import datetime as dt
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.accounts.services import is_login_locked, lockout_message
from apps.audit.models import AuditAction, AuditLog, AuditSeverity

User = get_user_model()

PASSWORD = "Pw123!Aa"


class _Setup(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="bob", email="bob@example.com", password=PASSWORD, role=Role.CITIZEN,
        )
        self.url = reverse("accounts:login")

    def _login(self, username="bob", password=PASSWORD):
        return self.client.post(self.url, {"username": username, "password": password})

    def _fail(self, times, username="bob"):
        response = None
        for _ in range(times):
            response = self._login(username=username, password="mauvais")
        return response

    def _errors(self, response):
        return response.context["form"].non_field_errors()

    def _later(self, minutes):
        """Avance l'horloge de ``minutes`` (lecture du temps par les services et les vues)."""
        return mock.patch(
            "django.utils.timezone.now",
            return_value=timezone.now() + dt.timedelta(minutes=minutes),
        )


class WebLoginLockoutTests(_Setup):
    def test_four_failures_then_success_resets_counter(self):
        self._fail(4)
        self.assertFalse(is_login_locked("bob"))
        self.assertEqual(self._login().status_code, 302)
        self.client.logout()
        # Le compteur repart de zéro : 4 nouveaux échecs ne verrouillent pas
        self._fail(4)
        self.assertFalse(is_login_locked("bob"))
        self.assertEqual(self._login().status_code, 302)

    def test_five_failures_lock_even_with_correct_password(self):
        response = self._fail(5)
        self.assertIn(lockout_message(), self._errors(response))
        response = self._login()
        self.assertEqual(response.status_code, 200)
        self.assertIn(lockout_message(), self._errors(response))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_unlocked_after_expiry(self):
        self._fail(5)
        with self._later(16):
            self.assertFalse(is_login_locked("bob"))
            self.assertEqual(self._login().status_code, 302)

    def test_attempts_during_lock_do_not_extend_it(self):
        self._fail(5)
        with self._later(10):
            response = self._fail(5)
            self.assertIn(lockout_message(), self._errors(response))
        self.assertEqual(
            AuditLog.objects.filter(action=AuditAction.AUTH_FAILED).count(), 5,
        )
        with self._later(16):
            self.assertEqual(self._login().status_code, 302)

    def test_counter_restarts_after_lock_expiry(self):
        self._fail(5)
        with self._later(16):
            response = self._fail(1)
            self.assertNotIn(lockout_message(), self._errors(response))
            self.assertFalse(is_login_locked("bob"))

    def test_unknown_identifier_treated_like_real_one(self):
        real_first = self._errors(self._fail(1, username="bob"))
        ghost_first = self._errors(self._fail(1, username="ghost"))
        self.assertEqual(list(real_first), list(ghost_first))

        ghost_locked = self._errors(self._fail(4, username="ghost"))
        self.assertEqual(list(ghost_locked), [lockout_message()])
        self.assertTrue(is_login_locked("ghost"))
        # Le blocage d'un identifiant n'affecte pas les autres
        self.assertFalse(is_login_locked("bob"))

    def test_identifier_case_does_not_bypass_lock(self):
        self._fail(5, username="Bob")
        self.assertTrue(is_login_locked("bob"))
        self.assertIn(lockout_message(), self._errors(self._login(username="bob")))

    def test_single_lock_audit_entry(self):
        self._fail(5)
        self._fail(3)
        self._login()
        entries = AuditLog.objects.filter(action=AuditAction.AUTH_LOCKED)
        self.assertEqual(entries.count(), 1)
        entry = entries.get()
        self.assertEqual(entry.severity, AuditSeverity.WARNING)
        self.assertEqual(entry.payload["context"]["failures"], 5)
        self.assertEqual(entry.target_id, self.user.pk)


class AdminLoginLockoutTests(_Setup):
    def test_admin_login_shares_the_lock(self):
        self.user.is_staff = True
        self.user.save()
        self._fail(5)
        response = self.client.post(
            reverse("admin:login"), {"username": "bob", "password": PASSWORD},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "temporairement bloqué")


class ApiTokenLockoutTests(_Setup):
    def setUp(self):
        super().setUp()
        self.token_url = reverse("api:token")

    def _token(self, password, username="bob"):
        return self.client.post(self.token_url, {"username": username, "password": password})

    def test_token_endpoint_locks_after_five_failures(self):
        for _ in range(4):
            self.assertEqual(self._token("mauvais").status_code, 400)
        response = self._token("mauvais")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["detail"], lockout_message())
        # Bon mot de passe refusé pendant le blocage
        self.assertEqual(self._token(PASSWORD).status_code, 429)
        with self._later(16):
            response = self._token(PASSWORD)
            self.assertEqual(response.status_code, 200)
            self.assertIn("token", response.json())

    def test_token_success_resets_counter(self):
        for _ in range(4):
            self._token("mauvais")
        self.assertEqual(self._token(PASSWORD).status_code, 200)
        for _ in range(4):
            self.assertEqual(self._token("mauvais").status_code, 400)
        self.assertFalse(is_login_locked("bob"))

    def test_token_unknown_identifier_locked_identically(self):
        for _ in range(4):
            self._token("mauvais", username="ghost")
        response = self._token("mauvais", username="ghost")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["detail"], lockout_message())
