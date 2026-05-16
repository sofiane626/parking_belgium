"""
Smoke tests pour les vues citoyen (profil, adresse, demandes).
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.citizens.services import get_or_create_profile, upsert_address
from apps.core.models import Commune

User = get_user_model()


class CitizenViewsTests(TestCase):
    def setUp(self):
        self.commune = Commune.objects.get(niscode="21015")
        self.user = User.objects.create_user(username="c", email="c@x.fr", password="Pw1!Aa")
        profile = get_or_create_profile(self.user)
        upsert_address(
            profile, user=self.user, street="X", number="1", box="",
            postal_code="1030", commune=self.commune, country="BE",
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_profile_edit_get(self):
        self.assertEqual(self.client.get(reverse("citizens:profile_edit")).status_code, 200)

    def test_request_list(self):
        self.assertEqual(self.client.get(reverse("citizens:request_list")).status_code, 200)

    def test_address_change_create_get(self):
        self.assertEqual(self.client.get(reverse("citizens:address_change_create")).status_code, 200)
