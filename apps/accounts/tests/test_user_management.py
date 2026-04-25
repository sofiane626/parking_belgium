"""
Couvre :
- Hiérarchie des rôles : qui peut promouvoir qui
- Garde-fou : impossible de modifier son propre rôle
- Garde-fou : un admin ne peut pas toucher à un admin/super_admin
- Reset password admin-initiated : envoie un email valide
- Toggle is_active
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase

from apps.accounts.models import Role
from apps.accounts.services import (
    UserManagementError,
    assignable_roles,
    can_manage_users,
    change_role,
    list_users,
    send_password_reset_for,
    update_user_basics,
)

User = get_user_model()


class _Setup(TestCase):
    def setUp(self):
        self.citizen = User.objects.create_user(
            username="citizen1", email="c@x.fr", password="Pw123!Aa", role=Role.CITIZEN,
        )
        self.agent = User.objects.create_user(
            username="agent1", email="a@x.fr", password="Pw123!Aa", role=Role.AGENT,
        )
        self.admin = User.objects.create_user(
            username="admin1", email="adm@x.fr", password="Pw123!Aa", role=Role.ADMIN,
        )
        self.super = User.objects.create_user(
            username="super1", email="sup@x.fr", password="Pw123!Aa", role=Role.SUPER_ADMIN,
        )


class CanManageTests(_Setup):
    def test_citizen_cannot_manage(self):
        self.assertFalse(can_manage_users(self.citizen))

    def test_agent_cannot_manage(self):
        self.assertFalse(can_manage_users(self.agent))

    def test_admin_can_manage(self):
        self.assertTrue(can_manage_users(self.admin))

    def test_super_can_manage(self):
        self.assertTrue(can_manage_users(self.super))


class AssignableRolesTests(_Setup):
    def test_admin_can_only_assign_citizen_and_agent(self):
        roles = {v for v, _ in assignable_roles(self.admin)}
        self.assertEqual(roles, {Role.CITIZEN.value, Role.AGENT.value})

    def test_super_can_assign_all(self):
        roles = {v for v, _ in assignable_roles(self.super)}
        self.assertEqual(roles, {r.value for r in Role})


class ChangeRoleTests(_Setup):
    def test_admin_can_promote_citizen_to_agent(self):
        change_role(self.citizen, new_role=Role.AGENT.value, actor=self.admin)
        self.citizen.refresh_from_db()
        self.assertEqual(self.citizen.role, Role.AGENT.value)

    def test_admin_cannot_promote_to_admin(self):
        with self.assertRaises(PermissionDenied):
            change_role(self.citizen, new_role=Role.ADMIN.value, actor=self.admin)

    def test_admin_cannot_modify_admin(self):
        other_admin = User.objects.create_user(
            username="admin2", email="adm2@x.fr", password="Pw123!Aa", role=Role.ADMIN,
        )
        with self.assertRaises(PermissionDenied):
            change_role(other_admin, new_role=Role.AGENT.value, actor=self.admin)

    def test_super_can_promote_to_admin(self):
        change_role(self.citizen, new_role=Role.ADMIN.value, actor=self.super)
        self.citizen.refresh_from_db()
        self.assertEqual(self.citizen.role, Role.ADMIN.value)

    def test_cannot_modify_self(self):
        with self.assertRaises(UserManagementError):
            change_role(self.admin, new_role=Role.SUPER_ADMIN.value, actor=self.admin)

    def test_super_cannot_modify_other_super(self):
        other_super = User.objects.create_user(
            username="super2", email="sup2@x.fr", password="Pw123!Aa", role=Role.SUPER_ADMIN,
        )
        with self.assertRaises(UserManagementError):
            change_role(other_super, new_role=Role.ADMIN.value, actor=self.super)

    def test_unknown_role_rejected(self):
        with self.assertRaises(UserManagementError):
            change_role(self.citizen, new_role="hacker", actor=self.super)

    def test_citizen_cannot_act(self):
        with self.assertRaises(PermissionDenied):
            change_role(self.agent, new_role=Role.CITIZEN.value, actor=self.citizen)


class UpdateBasicsTests(_Setup):
    def test_update_basics(self):
        update_user_basics(
            self.citizen, first_name="X", last_name="Y", email="new@x.fr",
            is_active=True, actor=self.admin,
        )
        self.citizen.refresh_from_db()
        self.assertEqual(self.citizen.first_name, "X")
        self.assertEqual(self.citizen.email, "new@x.fr")

    def test_deactivate_user(self):
        update_user_basics(
            self.citizen, first_name=self.citizen.first_name,
            last_name=self.citizen.last_name, email=self.citizen.email,
            is_active=False, actor=self.admin,
        )
        self.citizen.refresh_from_db()
        self.assertFalse(self.citizen.is_active)


class SendResetTests(_Setup):
    def test_admin_sends_reset_email(self):
        rf = RequestFactory()
        req = rf.get("/")
        mail.outbox = []
        send_password_reset_for(self.citizen, request=req, actor=self.admin)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("réinitialisation", mail.outbox[0].subject.lower())
        self.assertIn(self.citizen.email, mail.outbox[0].to)
        # Lien de reset présent dans le corps
        self.assertIn("password/reset/", mail.outbox[0].body)

    def test_send_reset_refused_on_self(self):
        # On ne peut pas se déclencher un reset à soi-même via cette interface.
        rf = RequestFactory()
        with self.assertRaises(UserManagementError):
            send_password_reset_for(self.admin, request=rf.get("/"), actor=self.admin)

    def test_send_reset_refused_admin_targets_other_admin(self):
        rf = RequestFactory()
        other_admin = User.objects.create_user(
            username="admin2", email="adm2@x.fr", password="Pw123!Aa", role=Role.ADMIN,
        )
        with self.assertRaises(PermissionDenied):
            send_password_reset_for(other_admin, request=rf.get("/"), actor=self.admin)

    def test_send_reset_refused_no_email(self):
        self.citizen.email = ""
        self.citizen.save()
        rf = RequestFactory()
        with self.assertRaises(UserManagementError):
            send_password_reset_for(self.citizen, request=rf.get("/"), actor=self.admin)


class ListUsersTests(_Setup):
    def test_list_filter_by_role(self):
        qs = list_users(self.admin, role=Role.AGENT.value)
        self.assertEqual(list(qs.values_list("username", flat=True)), ["agent1"])

    def test_list_search(self):
        qs = list_users(self.admin, q="citizen")
        self.assertIn("citizen1", qs.values_list("username", flat=True))

    def test_list_refused_for_citizen(self):
        with self.assertRaises(PermissionDenied):
            list_users(self.citizen)
