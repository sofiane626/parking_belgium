"""
Couvre la désinscription d'un citoyen (soft delete RGPD) :
- citoyen avec paiement réussi + carte active + carte visiteur + véhicule :
  tout est clôturé / archivé, le paiement existe toujours, les PII sont vides,
  la connexion échoue, une seule entrée d'audit sans donnée personnelle
- paiement en attente annulé avec la carte non activée
- mauvais mot de passe refusé, rien ne change
- compte back-office refusé
- GET n'efface rien
- idempotence
- sessions ouvertes ailleurs invalidées
- purge_expired_data passe par le même service d'anonymisation
- back-office : liste, fiche, détail de carte et export CSV d'un compte anonymisé
"""
from __future__ import annotations

import datetime as dt
import json
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.accounts.services import (
    AccountDeletionError,
    UserManagementError,
    anonymise_user,
    delete_citizen_account,
    update_user_basics,
)
from apps.audit.models import AuditAction, AuditLog
from apps.citizens.models import (
    Address, AddressChangeRequest, CitizenProfile, RequestStatus,
)
from apps.citizens.services import get_or_create_profile, submit_address_change, upsert_address
from apps.core.models import Commune
from apps.gis_data.models import GISPolygon, GISSourceVersion
from apps.payments.models import Payment, PaymentStatus
from apps.payments.services import initiate_payment, simulate_payment_success
from apps.permits.models import (
    Permit, PermitConfig, PermitStatus, PermitType, VisitorCode, VisitorCodeStatus,
)
from apps.permits.services import (
    create_draft, create_visitor_permit, generate_visitor_code, submit_application,
)
from apps.vehicles.models import Vehicle
from apps.vehicles.services import create_vehicle

User = get_user_model()

PASSWORD = "Pw123!Aa"


class _Setup(TestCase):
    """Citoyen « bob » : carte riverain payée et active, carte visiteur avec un code, demande d'adresse en attente."""

    def setUp(self):
        cfg = PermitConfig.get()
        cfg.resident_price_cents = 1500
        cfg.visitor_price_cents = 0
        cfg.save()

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

        self.user = User.objects.create_user(
            username="bob", email="bob@example.com", password=PASSWORD,
            first_name="Bob", last_name="Martin", role=Role.CITIZEN,
        )
        self.profile = get_or_create_profile(self.user)
        CitizenProfile.objects.filter(pk=self.profile.pk).update(
            national_number="85.07.30-033.61", phone="+32470000000",
            date_of_birth=dt.date(1985, 7, 30),
        )
        upsert_address(
            self.profile, user=self.user, street="Rue Royale", number="12", box="",
            postal_code="1030", commune=self.commune, country="BE",
        )
        addr = Address.objects.get(profile=self.profile)
        addr.location = Point(1500, 1500, srid=31370)
        addr.save()

        self.vehicle = create_vehicle(owner=self.user, plate="1-AAA-111", brand="R", model="C")
        permit = submit_application(create_draft(self.user, self.vehicle, PermitType.RESIDENT))
        self.assertEqual(permit.status, PermitStatus.AWAITING_PAYMENT)
        with self.settings(DEBUG=True):
            self.payment = simulate_payment_success(permit, by_user=self.user)
        self.permit = Permit.objects.get(pk=permit.pk)
        self.assertEqual(self.permit.status, PermitStatus.ACTIVE)

        self.visitor_permit = create_visitor_permit(self.user)
        self.assertEqual(self.visitor_permit.status, PermitStatus.ACTIVE)
        self.code = generate_visitor_code(self.visitor_permit, plate="2-BBB-222", duration_hours=2)

        self.address_request = submit_address_change(
            self.profile, user=self.user, street="Rue Neuve", number="1", box="",
            postal_code="1000", commune=self.commune, country="BE",
        )

    def _delete_via_view(self, client=None, password=PASSWORD):
        client = client or self.client
        client.login(username="bob", password=PASSWORD)
        return client.post(reverse("accounts:account_delete"), {"password": password})


class AccountDeletionTests(_Setup):
    def test_full_deletion_keeps_payment_and_erases_personal_data(self):
        response = self._delete_via_view()
        self.assertRedirects(response, reverse("core:home"), fetch_redirect_response=False)

        # Cartes clôturées, code visiteur annulé
        self.permit.refresh_from_db()
        self.visitor_permit.refresh_from_db()
        self.assertEqual(self.permit.status, PermitStatus.CANCELLED)
        self.assertIsNotNone(self.permit.cancelled_at)
        self.assertEqual(self.visitor_permit.status, PermitStatus.CANCELLED)
        self.code.refresh_from_db()
        self.assertEqual(self.code.status, VisitorCodeStatus.CANCELLED)

        # Véhicule archivé (soft delete), plaque conservée pour l'historique
        self.vehicle.refresh_from_db()
        self.assertIsNotNone(self.vehicle.archived_at)
        self.assertIn("Désinscription", self.vehicle.archive_reason)
        self.assertEqual(self.vehicle.plate, "1-AAA-111")

        # Paiement intact, toujours rattaché à la même ligne utilisateur
        payment = Payment.objects.get(pk=self.payment.pk)
        self.assertEqual(payment.status, PaymentStatus.SUCCEEDED)
        self.assertEqual(payment.citizen_id, self.user.pk)

        # Compte anonymisé, ligne conservée
        user = User.objects.get(pk=self.user.pk)
        self.assertEqual(user.username, f"anonyme-{user.pk}")
        self.assertEqual((user.email, user.first_name, user.last_name), ("", "", ""))
        self.assertFalse(user.is_active)
        self.assertFalse(user.has_usable_password())
        self.assertIsNotNone(user.anonymised_at)

        # Profil, adresse et demande d'adresse vidés
        profile = CitizenProfile.objects.get(pk=self.profile.pk)
        self.assertEqual((profile.national_number, profile.phone), ("", ""))
        self.assertIsNone(profile.date_of_birth)
        address = Address.objects.get(profile=profile)
        self.assertEqual((address.street, address.number, address.postal_code), ("", "", ""))
        self.assertIsNone(address.location)
        req = AddressChangeRequest.objects.get(pk=self.address_request.pk)
        self.assertEqual(req.status, RequestStatus.CANCELLED)
        self.assertEqual(req.street, "")

        # Plus aucune connexion possible, ni avec l'ancien ni avec le nouveau username
        self.assertFalse(Client().login(username="bob", password=PASSWORD))
        self.assertFalse(Client().login(username=user.username, password=PASSWORD))
        # La session courante est fermée
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_single_audit_entry_without_personal_data(self):
        self._delete_via_view()
        entries = AuditLog.objects.filter(action=AuditAction.ACCOUNT_DELETED)
        self.assertEqual(entries.count(), 1)
        entry = entries.get()
        self.assertEqual(entry.target_id, self.user.pk)
        context = entry.payload["context"]
        self.assertEqual(context["permits_closed"], 2)
        self.assertEqual(context["vehicles_archived"], 1)
        self.assertEqual(context["payments_kept"], 1)
        self.assertEqual(context["requests_cancelled"], 1)
        self.assertEqual(entry.payload["diff"]["is_active"], [True, False])
        dumped = json.dumps(entry.payload) + entry.target_label
        for pii in ("bob", "Martin", "example.com", "Rue Royale", "85.07.30"):
            self.assertNotIn(pii, dumped)

    def test_pending_payment_cancelled_with_unpaid_permit(self):
        car = create_vehicle(owner=self.user, plate="3-CCC-333", brand="R", model="C")
        unpaid = submit_application(create_draft(self.user, car, PermitType.RESIDENT))
        self.assertEqual(unpaid.status, PermitStatus.AWAITING_PAYMENT)
        pending = initiate_payment(unpaid, by_user=self.user)

        delete_citizen_account(self.user, password=PASSWORD)

        unpaid.refresh_from_db()
        pending.refresh_from_db()
        self.assertEqual(unpaid.status, PermitStatus.CANCELLED)
        self.assertEqual(pending.status, PaymentStatus.CANCELLED)
        self.assertFalse(Vehicle.objects.filter(owner=self.user, archived_at__isnull=True).exists())

    def test_wrong_password_refused(self):
        response = self._delete_via_view(password="mauvais")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        user = User.objects.get(pk=self.user.pk)
        self.assertEqual(user.username, "bob")
        self.assertTrue(user.is_active)
        self.permit.refresh_from_db()
        self.assertEqual(self.permit.status, PermitStatus.ACTIVE)
        self.assertFalse(AuditLog.objects.filter(action=AuditAction.ACCOUNT_DELETED).exists())
        with self.assertRaises(AccountDeletionError):
            delete_citizen_account(self.user, password="mauvais")

    def test_back_office_account_refused(self):
        agent = User.objects.create_user(
            username="agent1", email="a@x.fr", password=PASSWORD, role=Role.AGENT,
        )
        self.client.login(username="agent1", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("accounts:account_delete")).status_code, 403)
        response = self.client.post(reverse("accounts:account_delete"), {"password": PASSWORD})
        self.assertEqual(response.status_code, 403)
        agent.refresh_from_db()
        self.assertTrue(agent.is_active)
        self.assertIsNone(agent.anonymised_at)
        with self.assertRaises(PermissionDenied):
            delete_citizen_account(agent, password=PASSWORD)

    def test_get_shows_confirmation_and_deletes_nothing(self):
        self.client.login(username="bob", password=PASSWORD)
        response = self.client.get(reverse("accounts:account_delete"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["preview"].permits_closed, 2)
        self.assertEqual(response.context["preview"].payments_kept, 1)
        self.assertContains(response, 'name="password"')
        user = User.objects.get(pk=self.user.pk)
        self.assertTrue(user.is_active)
        self.assertIsNone(user.anonymised_at)
        self.permit.refresh_from_db()
        self.assertEqual(self.permit.status, PermitStatus.ACTIVE)

    def test_idempotent(self):
        delete_citizen_account(self.user, password=PASSWORD)
        user = User.objects.get(pk=self.user.pk)
        stamp = user.anonymised_at
        result = delete_citizen_account(user, password=PASSWORD)
        self.assertTrue(result.already_anonymised)
        self.assertFalse(anonymise_user(user))
        user.refresh_from_db()
        self.assertEqual(user.anonymised_at, stamp)
        self.assertEqual(AuditLog.objects.filter(action=AuditAction.ACCOUNT_DELETED).count(), 1)

    def test_other_sessions_invalidated(self):
        other = Client()
        other.login(username="bob", password=PASSWORD)
        self.assertEqual(other.get(reverse("dashboard:citizen")).status_code, 200)
        self._delete_via_view()
        response = other.get(reverse("dashboard:citizen"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])


class PurgeUsesSharedServiceTests(TestCase):
    def test_purge_anonymises_through_shared_service(self):
        u = User.objects.create_user(username="oldie", email="o@x.fr", password=PASSWORD)
        old = timezone.now() - dt.timedelta(days=365 * 5)
        User.objects.filter(pk=u.pk).update(last_login=old, date_joined=old)
        target = "apps.accounts.management.commands.purge_expired_data.anonymise_user"
        with mock.patch(target, wraps=anonymise_user) as spy:
            call_command("purge_expired_data", "--apply", stdout=StringIO())
        self.assertEqual(spy.call_count, 1)
        u.refresh_from_db()
        self.assertEqual(u.username, f"anonyme-{u.pk}")
        self.assertIsNotNone(u.anonymised_at)
        self.assertFalse(u.has_usable_password())
        # Déjà anonymisé : n'est plus candidat au passage suivant
        call_command("purge_expired_data", "--apply", stdout=StringIO())
        u.refresh_from_db()
        self.assertEqual(u.username, f"anonyme-{u.pk}")


class ReservedUsernameTests(TestCase):
    def test_registration_refuses_anonymous_prefix(self):
        response = self.client.post(reverse("accounts:register"), {"username": "anonyme-12"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("username", response.context["form"].errors)


class BackOfficeDisplayTests(_Setup):
    def setUp(self):
        super().setUp()
        delete_citizen_account(self.user, password=PASSWORD)
        self.anonymised = User.objects.get(pk=self.user.pk)
        self.admin = User.objects.create_user(
            username="admin1", email="adm@x.fr", password=PASSWORD, role=Role.ADMIN,
        )
        self.client.login(username="admin1", password=PASSWORD)

    def test_user_list_and_detail(self):
        response = self.client.get(reverse("dashboard:admin_users"), {"inactive": "1"})
        self.assertContains(response, self.anonymised.username)
        self.assertContains(response, "Anonymisé le")
        response = self.client.get(reverse("dashboard:admin_user_edit", args=[self.anonymised.pk]))
        self.assertContains(response, "Compte anonymisé")
        self.assertNotContains(response, 'name="email"')

    def test_permit_detail_shows_anonymised_holder(self):
        response = self.client.get(reverse("dashboard:agent_permit_detail", args=[self.permit.pk]))
        self.assertContains(response, "Compte anonymisé")
        self.assertNotContains(response, f"{self.anonymised.username} ()")

    def test_users_csv_export(self):
        response = self.client.get(reverse("dashboard:admin_users_export"), {"include_inactive": "1"})
        self.assertEqual(response.status_code, 200)
        body = b"".join(response.streaming_content).decode("utf-8-sig")
        self.assertIn("anonymised_at", body.splitlines()[0])
        self.assertIn(self.anonymised.username, body)

    def test_back_office_cannot_edit_anonymised_account(self):
        with self.assertRaises(UserManagementError):
            update_user_basics(
                self.anonymised, first_name="Bob", last_name="", email="bob@example.com",
                is_active=True, actor=self.admin,
            )
