"""
Vérifie l'émission/révocation des tokens API depuis le back-office :
- un admin peut émettre un token pour un agent
- un agent ne peut pas émettre un token (escalade refusée)
- on refuse d'émettre un token pour un citoyen
- la révocation supprime bien la ligne Token
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.authtoken.models import Token

from apps.accounts.models import Role
from apps.api.services import TokenError, issue_token_for, revoke_token

User = get_user_model()


class TokenServiceTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="adm", password="Pw123!Aa", role=Role.ADMIN,
        )
        self.agent = User.objects.create_user(
            username="ag", password="Pw123!Aa", role=Role.AGENT,
        )
        self.citizen = User.objects.create_user(
            username="cit", password="Pw123!Aa", role=Role.CITIZEN,
        )

    def test_admin_can_issue_for_agent(self):
        token = issue_token_for(self.agent, actor=self.admin)
        self.assertEqual(token.user, self.agent)
        self.assertTrue(Token.objects.filter(user=self.agent).exists())

    def test_issue_for_citizen_refused(self):
        with self.assertRaises(TokenError):
            issue_token_for(self.citizen, actor=self.admin)

    def test_agent_cannot_issue_tokens(self):
        from django.core.exceptions import PermissionDenied
        with self.assertRaises(PermissionDenied):
            issue_token_for(self.agent, actor=self.agent)

    def test_reissue_replaces_old_token(self):
        first = issue_token_for(self.agent, actor=self.admin)
        second = issue_token_for(self.agent, actor=self.admin)
        self.assertNotEqual(first.key, second.key)
        self.assertEqual(Token.objects.filter(user=self.agent).count(), 1)

    def test_revoke_deletes_token(self):
        token = issue_token_for(self.agent, actor=self.admin)
        revoke_token(token, actor=self.admin)
        self.assertFalse(Token.objects.filter(user=self.agent).exists())

    def test_inactive_user_refused(self):
        self.agent.is_active = False
        self.agent.save()
        with self.assertRaises(TokenError):
            issue_token_for(self.agent, actor=self.admin)
