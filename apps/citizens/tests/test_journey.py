"""
Couvre la machine d'état du parcours citoyen :
- profil incomplet → CTA "compléter profil"
- profil OK / pas de véhicule → CTA "ajouter véhicule"
- véhicule sans carte → CTA "demander carte"
- carte AWAITING_PAYMENT → CTA "payer" (jaune signal)
- carte ACTIVE → CTA "voir" (outline) + badge emerald
- carte SUSPENDED → CTA "voir" (outline) + badge rouge
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.citizens.journey import (
    compute_journey, STATE_CURRENT, STATE_DONE,
)
from apps.citizens.models import CitizenProfile
from apps.permits.models import Permit, PermitStatus, PermitType

User = get_user_model()


class JourneyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="x")
        self.profile = CitizenProfile.objects.create(user=self.user)

    def _journey(self, **overrides):
        defaults = dict(
            profile=self.profile,
            address=None,
            vehicles_qs=[],
            permits_qs=[],
        )
        defaults.update(overrides)
        return compute_journey(self.user, **defaults)

    def test_no_profile_phone_routes_to_profile_completion(self):
        # profile.phone est vide → première étape = profil
        j = self._journey()
        self.assertIn("profil", j.headline.lower())
        self.assertIn("profile", j.cta_url)

    def test_profile_done_no_vehicle_routes_to_add_vehicle(self):
        self.profile.phone = "+32499000000"
        self.profile.save()
        # adresse présente (mock minimal — on passe juste un objet truthy)
        addr = type("A", (), {})()
        j = self._journey(address=addr)
        self.assertIn("véhicule", j.headline.lower())
        self.assertIn("/vehicles/", j.cta_url)
        self.assertEqual(j.cta_style, "primary")

    def test_active_permit_shows_emerald_badge(self):
        self.profile.phone = "+32499000000"
        self.profile.save()
        v = type("V", (), {"is_archived": False, "pk": 1, "plate": "X"})()
        permit = type("P", (), {
            "status": PermitStatus.ACTIVE, "pk": 42,
        })()
        addr = type("A", (), {})()
        j = self._journey(address=addr, vehicles_qs=[v], permits_qs=[permit])
        self.assertEqual(j.badge, "Active")
        self.assertEqual(j.badge_color, "emerald")
        self.assertEqual(j.cta_style, "outline")

    def test_awaiting_payment_uses_signal_cta(self):
        self.profile.phone = "+32499000000"
        self.profile.save()
        v = type("V", (), {"is_archived": False, "pk": 1, "plate": "X"})()
        permit = type("P", (), {
            "status": PermitStatus.AWAITING_PAYMENT, "pk": 99,
        })()
        addr = type("A", (), {})()
        j = self._journey(address=addr, vehicles_qs=[v], permits_qs=[permit])
        self.assertEqual(j.badge, "À payer")
        self.assertEqual(j.cta_style, "signal")
        self.assertIn("/payments/", j.cta_url)

    def test_suspended_permit_overrides_with_red_badge(self):
        self.profile.phone = "+32499000000"
        self.profile.save()
        v = type("V", (), {"is_archived": False, "pk": 1, "plate": "X"})()
        permit = type("P", (), {
            "status": PermitStatus.SUSPENDED, "pk": 7,
        })()
        addr = type("A", (), {})()
        j = self._journey(address=addr, vehicles_qs=[v], permits_qs=[permit])
        self.assertEqual(j.badge_color, "red")
        self.assertIn("suspendue", j.headline.lower())

    def test_steps_progress_correctly(self):
        # Profil incomplet → seule étape 1 est current, autres pending
        j = self._journey()
        self.assertEqual(j.steps[0].state, STATE_CURRENT)
        # Profil + véhicule → étapes 1 et 2 done, 3 current
        self.profile.phone = "+32499000000"
        self.profile.save()
        v = type("V", (), {"is_archived": False, "pk": 1, "plate": "X"})()
        addr = type("A", (), {})()
        j = self._journey(address=addr, vehicles_qs=[v])
        self.assertEqual(j.steps[0].state, STATE_DONE)
        self.assertEqual(j.steps[1].state, STATE_DONE)
        self.assertEqual(j.steps[2].state, STATE_CURRENT)
