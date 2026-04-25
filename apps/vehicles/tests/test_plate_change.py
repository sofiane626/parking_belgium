from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.vehicles.models import PlateChangeRequest, PlateChangeStatus, Vehicle
from apps.vehicles.services import (
    approve_plate_change,
    cancel_plate_change,
    create_vehicle,
    reject_plate_change,
    submit_plate_change,
    update_vehicle,
)

User = get_user_model()


@override_settings(MEDIA_ROOT="/tmp/parking-belgium-test-media")
class PlateChangeRequestWorkflowTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="pwd123!Aa")
        self.bob = User.objects.create_user(username="bob", password="pwd123!Aa")
        self.agent = User.objects.create_user(username="agent_jo", password="pwd123!Aa")
        self.car = create_vehicle(
            owner=self.alice, plate="1-AAA-111", brand="Renault", model="Clio",
        )

    def test_update_vehicle_rejects_plate_argument(self):
        with self.assertRaises(ValueError):
            update_vehicle(self.car, plate="1-XXX-999")

    def test_submit_creates_pending(self):
        req = submit_plate_change(self.car, user=self.alice, new_plate="1-bbb-222", reason="achat")
        self.assertEqual(req.status, PlateChangeStatus.PENDING)
        self.assertEqual(req.new_plate, "1-BBB-222")  # normalized on save

    def test_submit_rejects_non_owner(self):
        with self.assertRaises(PermissionDenied):
            submit_plate_change(self.car, user=self.bob, new_plate="1-bbb-222")

    def test_approve_changes_plate_and_doc(self):
        new_doc = SimpleUploadedFile("new_carte.pdf", b"%PDF-1.4 new", content_type="application/pdf")
        req = submit_plate_change(
            self.car, user=self.alice, new_plate="1-CCC-333",
            new_registration_document=new_doc,
        )
        approve_plate_change(req, agent=self.agent, notes="ok")
        self.car.refresh_from_db()
        req.refresh_from_db()
        self.assertEqual(self.car.plate, "1-CCC-333")
        self.assertTrue(self.car.registration_document.name.endswith(".pdf"))
        self.assertEqual(req.status, PlateChangeStatus.APPROVED)

    def test_reject_keeps_plate(self):
        req = submit_plate_change(self.car, user=self.alice, new_plate="1-DDD-444")
        reject_plate_change(req, agent=self.agent, notes="doc illisible")
        self.car.refresh_from_db()
        req.refresh_from_db()
        self.assertEqual(self.car.plate, "1-AAA-111")
        self.assertEqual(req.status, PlateChangeStatus.REJECTED)

    def test_approve_rejects_clashing_plate(self):
        bob_car = create_vehicle(owner=self.bob, plate="1-EEE-555", brand="Toyota", model="Yaris")
        req = submit_plate_change(self.car, user=self.alice, new_plate="1-EEE-555")
        with self.assertRaises(ValueError):
            approve_plate_change(req, agent=self.agent)
        # ensure nothing applied
        self.car.refresh_from_db()
        self.assertEqual(self.car.plate, "1-AAA-111")
        bob_car.refresh_from_db()
        self.assertEqual(bob_car.plate, "1-EEE-555")

    def test_cancel_by_owner_only(self):
        req = submit_plate_change(self.car, user=self.alice, new_plate="1-FFF-666")
        with self.assertRaises(PermissionDenied):
            cancel_plate_change(req, user=self.bob)
        cancel_plate_change(req, user=self.alice)
        req.refresh_from_db()
        self.assertEqual(req.status, PlateChangeStatus.CANCELLED)
