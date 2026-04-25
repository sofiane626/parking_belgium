from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.citizens.models import Address, CitizenProfile
from apps.citizens.services import get_or_create_profile, upsert_address
from apps.citizens.signals import address_changed
from apps.core.models import Commune

User = get_user_model()


class GetOrCreateProfileTests(TestCase):
    def test_idempotent(self):
        user = User.objects.create_user(username="alice", password="pwd123!Aa")
        p1 = get_or_create_profile(user)
        p2 = get_or_create_profile(user)
        self.assertEqual(p1.pk, p2.pk)
        self.assertEqual(CitizenProfile.objects.filter(user=user).count(), 1)


class UpsertAddressTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="pwd123!Aa")
        self.profile = get_or_create_profile(self.user)
        self.commune = Commune.objects.get(niscode="21015")  # Schaerbeek
        self.signals = []

        def on_change(**kwargs):
            self.signals.append(kwargs)

        address_changed.connect(on_change, weak=False)
        self.addCleanup(address_changed.disconnect, on_change)

    def test_create_emits_signal_with_created_true(self):
        addr = upsert_address(
            self.profile,
            user=self.user,
            street="Rue de la Loi",
            number="16",
            box="",
            postal_code="1040",
            commune=self.commune,
            country="BE",
        )
        self.assertIsInstance(addr, Address)
        self.assertEqual(len(self.signals), 1)
        self.assertTrue(self.signals[0]["created"])
        self.assertIsNone(self.signals[0]["previous"])

    def test_update_emits_signal_with_previous_snapshot(self):
        upsert_address(
            self.profile,
            user=self.user,
            street="Rue de la Loi",
            number="16",
            box="",
            postal_code="1040",
            commune=self.commune,
            country="BE",
        )
        new_commune = Commune.objects.get(niscode="21004")  # Bruxelles
        upsert_address(
            self.profile,
            user=self.user,
            street="Grand-Place",
            number="1",
            box="",
            postal_code="1000",
            commune=new_commune,
            country="BE",
        )
        self.assertEqual(len(self.signals), 2)
        update = self.signals[1]
        self.assertFalse(update["created"])
        self.assertEqual(update["previous"]["street"], "Rue de la Loi")
        self.assertEqual(update["previous"]["postal_code"], "1040")


class CommuneSeedTests(TestCase):
    def test_19_communes_present(self):
        self.assertEqual(Commune.objects.count(), 19)
        self.assertTrue(Commune.objects.filter(niscode="21001", name_fr="Anderlecht").exists())
