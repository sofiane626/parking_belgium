from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.vehicles.models import Vehicle

User = get_user_model()


def _fake_doc(name: str = "carte_grise.pdf") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, b"%PDF-1.4 fake", content_type="application/pdf")


@override_settings(MEDIA_ROOT="/tmp/parking-belgium-test-media")
class VehicleViewsTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="pwd123!Aa")
        self.bob = User.objects.create_user(username="bob", password="pwd123!Aa")
        self.alice_car = Vehicle.objects.create(
            owner=self.alice, plate="1-AAA-111", brand="Renault", model="Clio"
        )

    def test_anonymous_redirects_to_login(self):
        resp = self.client.get(reverse("vehicles:list"))
        self.assertEqual(resp.status_code, 302)

    def test_owner_sees_only_own_vehicles(self):
        self.client.login(username="bob", password="pwd123!Aa")
        resp = self.client.get(reverse("vehicles:list"))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "1-AAA-111")

    def test_cannot_access_other_users_vehicle(self):
        self.client.login(username="bob", password="pwd123!Aa")
        resp = self.client.get(reverse("vehicles:detail", args=[self.alice_car.pk]))
        self.assertEqual(resp.status_code, 404)

    def test_create_vehicle_requires_document(self):
        self.client.login(username="alice", password="pwd123!Aa")
        resp = self.client.post(
            reverse("vehicles:create"),
            data={"plate": "1-ccc-333", "brand": "Peugeot", "model": "208", "color": "blue"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Ce champ est obligatoire", status_code=200)
        self.assertFalse(Vehicle.objects.filter(plate="1-CCC-333").exists())

    def test_create_vehicle_with_document(self):
        self.client.login(username="alice", password="pwd123!Aa")
        resp = self.client.post(
            reverse("vehicles:create"),
            data={
                "plate": "1-ccc-333",
                "brand": "Peugeot",
                "model": "208",
                "color": "blue",
                "registration_document": _fake_doc(),
            },
        )
        self.assertEqual(resp.status_code, 302)
        v = Vehicle.objects.get(plate="1-CCC-333")
        self.assertEqual(v.owner, self.alice)
        self.assertTrue(v.registration_document.name.endswith(".pdf"))

    def test_delete_vehicle_soft_archives(self):
        self.client.login(username="alice", password="pwd123!Aa")
        resp = self.client.post(reverse("vehicles:delete", args=[self.alice_car.pk]))
        self.assertEqual(resp.status_code, 302)
        # Soft-delete : le véhicule existe toujours mais est archivé.
        self.alice_car.refresh_from_db()
        self.assertIsNotNone(self.alice_car.archived_at)
