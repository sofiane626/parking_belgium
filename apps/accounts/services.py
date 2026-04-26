"""
Gestion des utilisateurs côté back-office.

Garde-fous de hiérarchie (jamais bypassable depuis les vues) :
- Seul un ``super_admin`` peut promouvoir/rétrograder vers ou depuis ``admin``
  ou ``super_admin``.
- Un ``admin`` peut seulement promouvoir un ``citizen`` en ``agent`` (et
  l'inverse).
- Personne ne peut modifier son propre rôle (anti-coup d'État).
- Personne ne peut désactiver ou modifier un ``super_admin`` autre que
  soi-même (et un super_admin ne peut pas se désactiver).
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import PermissionDenied
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.audit.services import AuditAction, log as audit_log

from .models import Role

User = get_user_model()


class UserManagementError(Exception):
    """Erreur fonctionnelle de gestion utilisateur (rôle invalide, garde-fou…)."""


# ----- permission helpers ---------------------------------------------------

# Rôles que chaque rôle « manager » est autorisé à attribuer.
_ROLES_MANAGEABLE_BY = {
    Role.SUPER_ADMIN: {Role.CITIZEN, Role.AGENT, Role.ADMIN, Role.SUPER_ADMIN},
    Role.ADMIN:       {Role.CITIZEN, Role.AGENT},
}


def can_manage_users(user) -> bool:
    return user.is_authenticated and user.role in _ROLES_MANAGEABLE_BY


def assignable_roles(actor) -> list[tuple[str, str]]:
    """Liste de (value, label) que ``actor`` a le droit d'assigner."""
    allowed = _ROLES_MANAGEABLE_BY.get(actor.role, set())
    return [(r.value, r.label) for r in Role if r.value in allowed]


def _ensure_can_act_on(actor, target) -> None:
    if not can_manage_users(actor):
        raise PermissionDenied
    if actor.pk == target.pk:
        raise UserManagementError("Vous ne pouvez pas modifier votre propre compte ici.")
    # Un admin ne peut jamais toucher à un super_admin ou un admin.
    if actor.role == Role.ADMIN and target.role in {Role.ADMIN, Role.SUPER_ADMIN}:
        raise PermissionDenied
    # Un super_admin ne peut pas toucher à un autre super_admin (à l'exception
    # du seed initial qui passe par la DB / shell).
    if actor.role == Role.SUPER_ADMIN and target.role == Role.SUPER_ADMIN and actor.pk != target.pk:
        raise UserManagementError(
            "Un super-admin ne peut pas modifier un autre super-admin via l'interface "
            "(passez par la base ou un shell Django)."
        )


# ----- queries --------------------------------------------------------------

def list_users(actor, *, role: str | None = None, q: str | None = None,
               include_inactive: bool = True):
    if not can_manage_users(actor):
        raise PermissionDenied
    qs = User.objects.all().order_by("-date_joined")
    if role:
        qs = qs.filter(role=role)
    if q:
        qs = qs.filter(
            username__icontains=q,
        ) | qs.filter(email__icontains=q) | qs.filter(
            first_name__icontains=q,
        ) | qs.filter(last_name__icontains=q)
    if not include_inactive:
        qs = qs.filter(is_active=True)
    return qs.distinct()


# ----- mutations ------------------------------------------------------------

def change_role(target: "User", *, new_role: str, actor) -> "User":
    _ensure_can_act_on(actor, target)
    if new_role not in {r.value for r in Role}:
        raise UserManagementError(f"Rôle inconnu : {new_role}")
    allowed = _ROLES_MANAGEABLE_BY.get(actor.role, set())
    if new_role not in allowed:
        raise PermissionDenied("Vous n'avez pas le droit d'attribuer ce rôle.")
    if target.role == new_role:
        return target
    old_role = target.role
    target.role = new_role
    target.save(update_fields=["role"])
    audit_log(
        AuditAction.USER_ROLE_CHANGED,
        actor=actor, target=target,
        payload={"diff": {"role": [old_role, new_role]}},
    )
    return target


def update_user_basics(target: "User", *, first_name: str, last_name: str,
                       email: str, is_active: bool, actor) -> "User":
    _ensure_can_act_on(actor, target)
    before = {
        "first_name": target.first_name, "last_name": target.last_name,
        "email": target.email, "is_active": target.is_active,
    }
    target.first_name = first_name
    target.last_name = last_name
    target.email = email
    was_active = target.is_active
    target.is_active = is_active
    target.save(update_fields=["first_name", "last_name", "email", "is_active"])
    after = {
        "first_name": target.first_name, "last_name": target.last_name,
        "email": target.email, "is_active": target.is_active,
    }
    from apps.audit.services import diff_dict
    diff = diff_dict(before, after)
    # Si seul le flag is_active a changé → log spécifique deactivated/reactivated
    if diff and set(diff.keys()) == {"is_active"}:
        audit_log(
            AuditAction.USER_REACTIVATED if is_active else AuditAction.USER_DEACTIVATED,
            actor=actor, target=target,
        )
    elif diff:
        audit_log(
            AuditAction.USER_BASICS_UPDATED,
            actor=actor, target=target,
            payload={"diff": diff},
        )
    return target


def send_password_reset_for(target: "User", *, request, actor) -> bool:
    """
    Déclenche manuellement l'envoi d'un email de reset au compte cible — utile
    quand un admin doit réinitialiser un mot de passe sans connaître l'email
    courant. Retourne True si un email a pu être envoyé.
    """
    _ensure_can_act_on(actor, target)
    if not target.email:
        raise UserManagementError("Cet utilisateur n'a pas d'adresse email enregistrée.")

    uid = urlsafe_base64_encode(force_bytes(target.pk))
    token = default_token_generator.make_token(target)
    path = reverse("accounts:password_reset_confirm",
                   kwargs={"uidb64": uid, "token": token})
    url = f"{request.scheme}://{request.get_host()}{path}"

    ctx = {
        "user": target,
        "actor": actor,
        "reset_url": url,
    }
    subject = "Parking.Belgium — Réinitialisation de votre mot de passe (initiée par un administrateur)"
    text_body = render_to_string("registration/password_reset_admin_email.txt", ctx)
    html_body = render_to_string("registration/password_reset_admin_email.html", ctx)

    msg = EmailMultiAlternatives(subject, text_body, None, [target.email])
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)
    audit_log(
        AuditAction.PASSWORD_RESET_SENT,
        actor=actor, target=target, request=request,
        payload={"context": {"trigger": "admin_initiated"}},
    )
    return True
