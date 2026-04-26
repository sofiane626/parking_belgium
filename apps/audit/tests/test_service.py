"""
Couvre le service log() et ses helpers :
- log() crée bien une ligne avec snapshot acteur + cible
- log() ne lève jamais (résilience absolue)
- hash_plate est stable et non réversible
- diff_dict détecte les bonnes différences
- mapping severity par défaut respecté + surcharge possible
- extraction IP depuis HttpRequest (avec X-Forwarded-For)
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from apps.accounts.models import Role
from apps.audit.models import AuditAction, AuditLog, AuditSeverity
from apps.audit.services import (
    diff_dict, extract_request_ip, hash_plate, log,
)

User = get_user_model()


class HashPlateTests(TestCase):
    def test_stable(self):
        self.assertEqual(hash_plate("1-AAA-111"), hash_plate("1-AAA-111"))

    def test_different_plates_give_different_hashes(self):
        self.assertNotEqual(hash_plate("1-AAA-111"), hash_plate("2-BBB-222"))

    def test_empty_plate(self):
        self.assertEqual(hash_plate(""), "")

    def test_truncated_to_16_hex(self):
        h = hash_plate("X-YYY-999")
        self.assertEqual(len(h), 16)
        self.assertTrue(all(c in "0123456789abcdef" for c in h))


class DiffDictTests(TestCase):
    def test_simple_change(self):
        out = diff_dict({"a": 1, "b": 2}, {"a": 1, "b": 3})
        self.assertEqual(out, {"b": [2, 3]})

    def test_added_key(self):
        out = diff_dict({"a": 1}, {"a": 1, "b": 2})
        self.assertEqual(out, {"b": [None, 2]})

    def test_removed_key(self):
        out = diff_dict({"a": 1, "b": 2}, {"a": 1})
        self.assertEqual(out, {"b": [2, None]})

    def test_no_diff(self):
        self.assertEqual(diff_dict({"a": 1}, {"a": 1}), {})


class ExtractRequestIPTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def test_remote_addr(self):
        r = self.rf.get("/", REMOTE_ADDR="10.1.2.3")
        self.assertEqual(extract_request_ip(r), "10.1.2.3")

    def test_x_forwarded_for_first_wins(self):
        r = self.rf.get("/", HTTP_X_FORWARDED_FOR="1.1.1.1, 2.2.2.2", REMOTE_ADDR="10.1.2.3")
        self.assertEqual(extract_request_ip(r), "1.1.1.1")

    def test_none_request_returns_none(self):
        self.assertIsNone(extract_request_ip(None))


class LogServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", role=Role.ADMIN, password="x")

    def test_creates_row_with_actor_snapshot(self):
        entry = log(AuditAction.USER_ROLE_CHANGED, actor=self.user, target=self.user)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.actor, self.user)
        self.assertEqual(entry.actor_role, "admin")
        self.assertEqual(entry.target_type, "user")
        self.assertEqual(entry.target_id, self.user.pk)
        self.assertEqual(entry.target_label, str(self.user)[:200])

    def test_default_severity_applied(self):
        entry = log(AuditAction.PERMIT_SUSPENDED, actor=self.user)
        self.assertEqual(entry.severity, AuditSeverity.WARNING)

    def test_severity_override(self):
        entry = log(
            AuditAction.PERMIT_SUSPENDED,
            actor=self.user, severity=AuditSeverity.CRITICAL,
        )
        self.assertEqual(entry.severity, AuditSeverity.CRITICAL)

    def test_does_not_raise_on_failure(self):
        # Action inexistante côté validation Django → save échoue, mais log() doit swallow
        entry = log("__not_a_valid_action__" * 10, actor=self.user)
        self.assertIsNone(entry)
        # Et le test continue normalement → pas de propagation d'exception

    def test_extracts_actor_and_ip_from_request(self):
        rf = RequestFactory()
        request = rf.get("/", REMOTE_ADDR="9.9.9.9")
        request.user = self.user
        entry = log(AuditAction.API_CHECK_RIGHT, request=request)
        self.assertEqual(entry.actor, self.user)
        self.assertEqual(entry.ip, "9.9.9.9")

    def test_explicit_ip_wins_over_request(self):
        rf = RequestFactory()
        request = rf.get("/", REMOTE_ADDR="9.9.9.9")
        request.user = self.user
        entry = log(AuditAction.API_CHECK_RIGHT, request=request, ip="1.2.3.4")
        self.assertEqual(entry.ip, "1.2.3.4")

    def test_system_action_no_actor(self):
        entry = log(AuditAction.PERMIT_EXPIRED)
        self.assertIsNone(entry.actor)
        self.assertEqual(entry.actor_role, "")
