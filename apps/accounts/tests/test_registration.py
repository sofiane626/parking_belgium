from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import Role
from apps.citizens.models import Address, CitizenProfile
from apps.core.models import Commune

User = get_user_model()


class RegistrationFlowTests(TestCase):
    def _payload(self) -> dict:
        commune = Commune.objects.get(niscode="21015")  # Schaerbeek
        return {
            "username": "newcitizen",
            "first_name": "Jean",
            "last_name": "Dupont",
            "email": "jean@example.be",
            "password1": "Pw0rdSecure!Aa",
            "password2": "Pw0rdSecure!Aa",
            "phone": "+32499000000",
            "date_of_birth": "1990-05-12",
            "national_number": "90.05.12-000.00",
            "street": "Avenue Louise",
            "number": "100",
            "box": "",
            "postal_code": "1030",  # Schaerbeek — la commune est déduite côté serveur
            "country": "BE",
            # RGPD — case à cocher obligatoire (« on » = checkbox cochée)
            "accept_privacy": "on",
        }

    def test_full_registration_creates_user_profile_and_address_atomically(self):
        resp = self.client.post(reverse("accounts:register"), data=self._payload())
        self.assertEqual(resp.status_code, 302)

        user = User.objects.get(username="newcitizen")
        self.assertEqual(user.role, Role.CITIZEN)
        self.assertEqual(user.email, "jean@example.be")
        # Le timestamp d'acceptation est snapshoté à l'inscription
        self.assertIsNotNone(user.accepted_privacy_at)
        self.assertIsNotNone(user.accepted_terms_at)

        profile = CitizenProfile.objects.get(user=user)
        self.assertEqual(profile.phone, "+32499000000")
        self.assertEqual(profile.national_number, "90.05.12-000.00")

        address = Address.objects.get(profile=profile)
        self.assertEqual(address.street, "Avenue Louise")
        self.assertEqual(address.commune.niscode, "21015")

    def test_registration_rejects_back_office_role_injection(self):
        payload = self._payload()
        payload["role"] = Role.SUPER_ADMIN  # client should never be able to escalate
        self.client.post(reverse("accounts:register"), data=payload)
        user = User.objects.get(username="newcitizen")
        self.assertEqual(user.role, Role.CITIZEN)

    def test_registration_rejects_missing_address(self):
        payload = self._payload()
        del payload["street"]
        resp = self.client.post(reverse("accounts:register"), data=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username="newcitizen").exists())

    def test_registration_refused_without_privacy_acceptance(self):
        """RGPD : pas d'inscription possible sans coche d'acceptation."""
        payload = self._payload()
        del payload["accept_privacy"]
        resp = self.client.post(reverse("accounts:register"), data=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username="newcitizen").exists())
