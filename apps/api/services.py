"""
Gestion des tokens d'accès à l'API publique.

Les tokens sont émis depuis le back-office par un admin/super_admin pour des
comptes ``staff`` (typiquement : intégration scan-car d'une commune, app
mobile d'un agent). Un compte citoyen ne peut pas obtenir de token via cette
voie — c'est volontaire, l'API est destinée aux acteurs métiers.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from rest_framework.authtoken.models import Token

from apps.accounts.services import can_manage_users

User = get_user_model()


class TokenError(Exception):
    """Erreur fonctionnelle de gestion de token (cible invalide…)."""


def _ensure_actor_can_manage_tokens(actor) -> None:
    if not can_manage_users(actor):
        raise PermissionDenied


def list_tokens(actor):
    """Renvoie tous les tokens existants — l'admin voit tout."""
    _ensure_actor_can_manage_tokens(actor)
    return (
        Token.objects.select_related("user").order_by("-created")
    )


def issue_token_for(target_user, *, actor) -> Token:
    """
    Crée un token pour ``target_user``. Si un token existe déjà, le
    révoque (DRF n'autorise qu'un token par user via ce flow simple).

    Refus :
    - actor non autorisé à gérer les utilisateurs
    - target sans rôle back-office (un citoyen ne doit pas avoir de token API)
    - target inactif
    """
    _ensure_actor_can_manage_tokens(actor)
    if not target_user.is_active:
        raise TokenError("Cet utilisateur est désactivé.")
    if not getattr(target_user, "is_back_office", False):
        raise TokenError(
            "Seuls les comptes back-office (agent, admin, super-admin) "
            "peuvent recevoir un token API."
        )
    Token.objects.filter(user=target_user).delete()
    return Token.objects.create(user=target_user)


def revoke_token(token: "Token", *, actor) -> None:
    _ensure_actor_can_manage_tokens(actor)
    token.delete()


def back_office_users_eligible_for_token():
    """Comptes back-office actifs sans token actuellement."""
    from apps.accounts.models import Role
    return (
        User.objects
        .filter(is_active=True, role__in=[Role.AGENT, Role.ADMIN, Role.SUPER_ADMIN])
        .exclude(auth_token__isnull=False)
        .order_by("username")
    )
