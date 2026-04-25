"""
Couvre les URLs Django auth wired pour password change/reset.
"""
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class PasswordChangeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="bob", email="bob@x.fr", password="OldPw123!Aa",
        )
        self.client.login(username="bob", password="OldPw123!Aa")

    def test_password_change_view_renders(self):
        resp = self.client.get(reverse("accounts:password_change"))
        self.assertEqual(resp.status_code, 200)

    def test_password_change_updates_password(self):
        resp = self.client.post(reverse("accounts:password_change"), {
            "old_password": "OldPw123!Aa",
            "new_password1": "BrandNew2026!Aa",
            "new_password2": "BrandNew2026!Aa",
        })
        self.assertEqual(resp.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("BrandNew2026!Aa"))


class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", email="alice@x.fr", password="OldPw123!Aa",
        )

    def test_reset_form_renders(self):
        resp = self.client.get(reverse("accounts:password_reset"))
        self.assertEqual(resp.status_code, 200)

    def test_reset_sends_email(self):
        mail.outbox = []
        resp = self.client.post(reverse("accounts:password_reset"), {"email": "alice@x.fr"})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("alice@x.fr", mail.outbox[0].to)
        # Lien de reset
        self.assertIn("password/reset/", mail.outbox[0].body)

    def test_reset_silent_for_unknown_email(self):
        # Django renvoie toujours success même si email inconnu (anti enumeration).
        mail.outbox = []
        resp = self.client.post(reverse("accounts:password_reset"), {"email": "ghost@x.fr"})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)

    def test_login_page_has_reset_link(self):
        resp = self.client.get(reverse("accounts:login"))
        self.assertContains(resp, reverse("accounts:password_reset"))
