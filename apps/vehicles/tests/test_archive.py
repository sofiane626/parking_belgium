"""
Soft-delete (archivage) des véhicules :
- archive_vehicle marque archived_at, idempotent
- restore_vehicle remet à None
- bloque l'archivage si carte non terminale liée
- véhicule archivé ne compte plus dans la limite max_vehicles
- restore refusé si la plaque a été reprise par un autre véhicule actif
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.test import TestCase

from apps.citizens.models import Address
from apps.citizens.services import get_or_create_profile, upsert_address
from apps.core.models import Commune
from apps.gis_data.models import GISPolygon, GISSourceVersion
from apps.permits.models import PermitConfig, PermitStatus, PermitType
from apps.permits.services import create_draft, mark_paid, submit_application
from apps.vehicles.services import (
    VehicleError, archive_vehicle, create_vehicle, restore_vehicle,
)

User = get_user_model()


class _Setup(TestCase):
    def setUp(self):
        self.commune = Commune.objects.get(niscode="21015")
        version = GISSourceVersion.objects.create(
            name="t", source_filename="x", srid=31370,
            polygon_count=1, is_active=True,
        )
        square = Polygon(((1000, 1000), (2000, 1000), (2000, 2000), (1000, 2000), (1000, 1000)))
        GISPolygon.objects.create(
            version=version, geometry=MultiPolygon(square, srid=31370),
            zonecode="ZONE-A", niscode="21015", commune=self.commune,
        )
        self.user = User.objects.create_user(username="bob", password="Pw123!Aa")
        profile = get_or_create_profile(self.user)
        upsert_address(
            profile, user=self.user, street="X", number="1", box="",
            postal_code="1030", commune=self.commune, country="BE",
        )
        addr = Address.objects.get(profile=profile)
        addr.location = Point(1500, 1500, srid=31370)
        addr.save()
        self.car = create_vehicle(owner=self.user, plate="1-AAA-111", brand="R", model="C")


class ArchiveTests(_Setup):
    def test_archive_marks_archived_at(self):
        archive_vehicle(self.car, by_user=self.user, reason="vendu")
        self.car.refresh_from_db()
        self.assertIsNotNone(self.car.archived_at)
        self.assertEqual(self.car.archive_reason, "vendu")

    def test_archive_idempotent(self):
        archive_vehicle(self.car, by_user=self.user)
        first_ts = self.car.archived_at
        archive_vehicle(self.car, by_user=self.user, reason="X")
        self.car.refresh_from_db()
        # Pas écrasé
        self.assertEqual(self.car.archived_at, first_ts)

    def test_archive_blocked_if_active_permit(self):
        permit = create_draft(self.user, self.car, PermitType.RESIDENT)
        permit = submit_application(permit)
        # Permit lands on AWAITING_PAYMENT or auto-active selon prix.
        self.assertNotEqual(permit.status, PermitStatus.REFUSED)
        with self.assertRaises(VehicleError):
            archive_vehicle(self.car, by_user=self.user)
        self.car.refresh_from_db()
        self.assertIsNone(self.car.archived_at)

    def test_archive_allowed_after_permit_terminal(self):
        permit = create_draft(self.user, self.car, PermitType.RESIDENT)
        permit = submit_application(permit)
        if permit.status == PermitStatus.AWAITING_PAYMENT and permit.price_cents > 0:
            mark_paid(permit)
        # Force terminal pour le test (ex: cancelled).
        permit.status = PermitStatus.CANCELLED
        permit.save()
        archive_vehicle(self.car, by_user=self.user)
        self.car.refresh_from_db()
        self.assertIsNotNone(self.car.archived_at)

    def test_archived_does_not_count_in_max_vehicles(self):
        cfg = PermitConfig.get()
        cfg.max_vehicles_per_citizen = 2
        cfg.save()
        create_vehicle(owner=self.user, plate="2-BBB-222", brand="X", model="Y")
        # Capacity reached (2/2).
        archive_vehicle(self.car, by_user=self.user)  # libère un slot
        # Ne doit plus lever malgré les 2 véhicules existants.
        new = create_vehicle(owner=self.user, plate="3-CCC-333", brand="X", model="Y")
        self.assertEqual(new.plate, "3-CCC-333")


class RestoreTests(_Setup):
    def test_restore_clears_archived_at(self):
        archive_vehicle(self.car, by_user=self.user)
        restore_vehicle(self.car, by_user=self.user)
        self.car.refresh_from_db()
        self.assertIsNone(self.car.archived_at)

    def test_restore_idempotent(self):
        # Restaurer un véhicule non archivé est un no-op.
        restored = restore_vehicle(self.car, by_user=self.user)
        self.assertIsNone(restored.archived_at)
