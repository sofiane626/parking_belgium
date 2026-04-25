from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from apps.vehicles.models import Vehicle, normalize_plate

User = get_user_model()


class NormalizePlateTests(TestCase):
    def test_uppercases_and_strips_whitespace(self):
        self.assertEqual(normalize_plate("  1-abc-123 "), "1-ABC-123")
        self.assertEqual(normalize_plate("ab\t12\n34"), "AB1234")


class VehicleModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="pwd123!Aa")

    def test_save_normalizes_plate(self):
        v = Vehicle.objects.create(owner=self.user, plate="1-aaa-111", brand="Renault", model="Clio")
        self.assertEqual(v.plate, "1-AAA-111")

    def test_plate_unique(self):
        Vehicle.objects.create(owner=self.user, plate="1-bbb-222", brand="Toyota", model="Yaris")
        other = User.objects.create_user(username="bob", password="pwd123!Aa")
        with self.assertRaises(IntegrityError):
            Vehicle.objects.create(owner=other, plate="1-bbb-222", brand="Honda", model="Jazz")
