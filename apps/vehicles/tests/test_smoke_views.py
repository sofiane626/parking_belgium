"""
Smoke tests pour les vues vehicles (list, detail, form, plate change).
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.vehicles.services import create_vehicle

User = get_user_model()


class VehicleViewsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", email="u@x.fr", password="Pw1!Aa")
        self.vehicle = create_vehicle(owner=self.user, plate="1-AAA-111", brand="R", model="C")
        self.client = Client()
        self.client.force_login(self.user)

    def test_list(self):
        self.assertEqual(self.client.get(reverse("vehicles:list")).status_code, 200)

    def test_form_create_get(self):
        self.assertEqual(self.client.get(reverse("vehicles:create")).status_code, 200)

    def test_detail(self):
        url = reverse("vehicles:detail", kwargs={"pk": self.vehicle.pk})
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_plate_change_create_get(self):
        url = reverse("vehicles:plate_change_create", kwargs={"vehicle_pk": self.vehicle.pk})
        self.assertEqual(self.client.get(url).status_code, 200)
