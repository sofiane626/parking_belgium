"""
Lookup commune par code postal + endpoint AJAX consommé par le formulaire
d'inscription.
"""
from django.test import Client, TestCase
from django.urls import reverse

from apps.core.models import Commune


class CommuneLookupTests(TestCase):
    def test_for_postal_code_known(self):
        c = Commune.for_postal_code("1030")
        self.assertIsNotNone(c)
        self.assertEqual(c.niscode, "21015")  # Schaerbeek

    def test_for_postal_code_brussels_multiple(self):
        # Bruxelles-Ville : plusieurs CP
        for pc in ("1000", "1020", "1120", "1130"):
            c = Commune.for_postal_code(pc)
            self.assertIsNotNone(c, f"CP {pc} doit matcher une commune")
            self.assertEqual(c.niscode, "21004")

    def test_for_postal_code_unknown(self):
        self.assertIsNone(Commune.for_postal_code("9999"))
        self.assertIsNone(Commune.for_postal_code(""))
        self.assertIsNone(Commune.for_postal_code(None))

    def test_for_postal_code_strips_whitespace(self):
        self.assertIsNotNone(Commune.for_postal_code("  1030  "))


class CommuneLookupEndpointTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_endpoint_returns_commune(self):
        url = reverse("core:commune_lookup")
        resp = self.client.get(url, {"postal_code": "1180"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["niscode"], "21016")  # Uccle

    def test_endpoint_returns_null_for_unknown(self):
        url = reverse("core:commune_lookup")
        resp = self.client.get(url, {"postal_code": "9999"})
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()["id"])
