from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from apps.companies.models import Company, validate_belgian_vat
from apps.core.models import Commune

User = get_user_model()


class VatValidatorTests(TestCase):
    def test_accepts_well_formed(self):
        validate_belgian_vat("BE0123456789")

    def test_strips_dots(self):
        validate_belgian_vat("BE0.123.456.789".replace(".", ""))

    def test_rejects_bad_format(self):
        for bad in ["1234567890", "BE12345", "BE0XYZABC123", "0123456789"]:
            with self.assertRaises(ValidationError):
                validate_belgian_vat(bad)


class CompanyModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="Pw123!Aa")
        self.commune = Commune.objects.get(niscode="21015")

    def test_save_normalises_vat(self):
        c = Company.objects.create(
            owner=self.user, name="Acme", vat_number="be0.123.456.789",
            street="Rue", number="1", postal_code="1030", commune=self.commune,
        )
        self.assertEqual(c.vat_number, "BE0123456789")

    def test_unique_vat_per_owner(self):
        Company.objects.create(
            owner=self.user, name="A", vat_number="BE0123456789",
            street="r", number="1", postal_code="1030", commune=self.commune,
        )
        with self.assertRaises(IntegrityError):
            Company.objects.create(
                owner=self.user, name="B", vat_number="BE0123456789",
                street="r", number="2", postal_code="1030", commune=self.commune,
            )
