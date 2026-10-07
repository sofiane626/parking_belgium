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
- Un compte anonymisé n'est plus modifiable (pas de ré-identification).

Désinscription et anonymisation (soft delete RGPD) :
- ``anonymise_user`` est la définition unique d'un « compte anonymisé »,
  utilisée par la désinscription volontaire et par la commande
  ``purge_expired_data``.
- ``delete_citizen_account`` orchestre la désinscription d'un citoyen : clôture
  des cartes, annulation des demandes, archivage des véhicules, puis
  anonymisation. La ligne utilisateur n'est jamais supprimée : les paiements
  (``Payment.citizen`` en PROTECT, conservation comptable 7 ans) et
  l'historique des cartes y restent rattachés.

Anti brute-force (``is_login_locked`` / ``register_login_failure``) : verrouillage
d'un identifiant après trop d'échecs de connexion, compteur lu dans le journal
d'audit. Appelé par le formulaire de connexion web, celui de l'admin Django et
l'endpoint ``/api/v1/token/``.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth import SESSION_KEY, get_user_model
from django.contrib.auth.models import update_last_login
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sessions.models import Session
from django.core.exceptions import PermissionDenied
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import Max
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext

from apps.audit.services import AuditAction, log as audit_log

from .models import Role

User = get_user_model()

# Préfixe des usernames attribués aux comptes anonymisés. Réservé : le
# formulaire d'inscription le refuse, ce qui garantit l'unicité de
# « anonyme-<pk> » sans dépendre du hasard.
ANONYMOUS_USERNAME_PREFIX = "anonyme-"


class UserManagementError(Exception):
    """Erreur fonctionnelle de gestion utilisateur (rôle invalide, garde-fou…)."""


class AccountDeletionError(Exception):
    """Désinscription refusée (mot de passe incorrect…)."""


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
    if target.is_anonymised:
        raise UserManagementError(
            gettext("Ce compte a été anonymisé : il n'est plus modifiable ni réactivable.")
        )
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
    # Rend l'email dans la langue préférée du destinataire (pas de l'admin).
    from django.conf import settings as _settings
    from django.utils import translation as _trans
    from django.utils.translation import gettext
    code = getattr(target, "preferred_language", None) or _settings.LANGUAGE_CODE
    valid = {c for c, _name in _settings.LANGUAGES}
    if code not in valid:
        code = _settings.LANGUAGE_CODE
    with _trans.override(code):
        subject = gettext("Parking.Belgium — Réinitialisation de votre mot de passe (initiée par un administrateur)")
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


# ----- anonymisation & désinscription (soft delete RGPD) --------------------

def anonymous_username(pk: int) -> str:
    return f"{ANONYMOUS_USERNAME_PREFIX}{pk}"


def _erase_citizen_data(user, *, now) -> None:
    """
    Efface les données personnelles du profil citoyen, de l'adresse et des
    demandes de changement d'adresse. Les lignes restent : ``Address.commune``
    est en PROTECT et non nullable, on garde donc la commune (granularité
    grossière, utile aux statistiques), tout le reste est vidé.
    """
    from apps.citizens.models import Address, AddressChangeRequest, CitizenProfile

    CitizenProfile.objects.filter(user=user).update(
        national_number="", phone="", date_of_birth=None, updated_at=now,
    )
    Address.objects.filter(profile__user=user).update(
        street="", number="", box="", postal_code="", location=None, updated_at=now,
    )
    AddressChangeRequest.objects.filter(profile__user=user).update(
        street="", number="", box="", postal_code="", reason="",
    )


def _invalidate_sessions(user, *, now) -> int:
    """
    Supprime les sessions ouvertes de ``user`` (backend de session en base).
    Le mot de passe rendu inutilisable invalide déjà le hash de session ; on
    supprime aussi les lignes pour que l'effet soit immédiat et vérifiable.
    """
    deleted = 0
    for session in Session.objects.filter(expire_date__gt=now).iterator():
        if session.get_decoded().get(SESSION_KEY) == str(user.pk):
            session.delete()
            deleted += 1
    return deleted


def anonymise_user(user, *, now=None) -> bool:
    """
    Définition unique d'un compte anonymisé. Idempotent : renvoie ``False``
    sans rien toucher si le compte l'est déjà.

    - username remplacé par ``anonyme-<pk>``, email / prénom / nom vidés ;
    - mot de passe rendu inutilisable, compte désactivé ;
    - profil citoyen, adresse et demandes d'adresse vidés ;
    - jeton API supprimé, sessions invalidées ;
    - ``anonymised_at`` horodaté (le soft delete est visible en base).
    """
    if user.anonymised_at is not None:
        return False
    from rest_framework.authtoken.models import Token

    now = now or timezone.now()
    user.username = anonymous_username(user.pk)
    user.email = ""
    user.first_name = ""
    user.last_name = ""
    user.preferred_language = "fr"
    user.is_active = False
    user.set_unusable_password()
    user.anonymised_at = now
    user.save(update_fields=[
        "username", "email", "first_name", "last_name",
        "preferred_language", "is_active", "password", "anonymised_at",
    ])
    _erase_citizen_data(user, now=now)
    Token.objects.filter(user=user).delete()
    _invalidate_sessions(user, now=now)
    return True


@dataclass
class AccountDeletionResult:
    permits_closed: int = 0
    requests_cancelled: int = 0
    vehicles_archived: int = 0
    payments_kept: int = 0
    already_anonymised: bool = False


ACCOUNT_DELETION_REASON = "Désinscription du titulaire (suppression du compte)"


def account_deletion_preview(user) -> AccountDeletionResult:
    """Ce que ``delete_citizen_account`` clôturerait et conserverait, sans rien modifier."""
    from apps.citizens.models import AddressChangeRequest, RequestStatus
    from apps.payments.models import Payment
    from apps.permits.models import Permit, PermitStatus
    from apps.vehicles.models import PlateChangeRequest, PlateChangeStatus

    return AccountDeletionResult(
        permits_closed=Permit.objects.filter(citizen=user).exclude(
            status__in=[PermitStatus.REFUSED, PermitStatus.EXPIRED, PermitStatus.CANCELLED],
        ).count(),
        requests_cancelled=(
            AddressChangeRequest.objects.filter(
                profile__user=user, status=RequestStatus.PENDING).count()
            + PlateChangeRequest.objects.filter(
                vehicle__owner=user, status=PlateChangeStatus.PENDING).count()
        ),
        vehicles_archived=user.vehicles.filter(archived_at__isnull=True).count(),
        payments_kept=Payment.objects.filter(citizen=user).count(),
        already_anonymised=user.is_anonymised,
    )


def delete_citizen_account(user, *, password: str, request=None) -> AccountDeletionResult:
    """
    Désinscription d'un citoyen par lui-même. Tout se passe dans une seule
    transaction : soit le compte est entièrement clôturé et anonymisé, soit
    rien ne change.

    Refusé pour les comptes back-office (gérés via la gestion des
    utilisateurs). Idempotent : sur un compte déjà anonymisé, ne fait rien.
    """
    from apps.payments.models import Payment

    if user.role != Role.CITIZEN:
        raise PermissionDenied
    if user.is_anonymised:
        return AccountDeletionResult(
            payments_kept=Payment.objects.filter(citizen=user).count(),
            already_anonymised=True,
        )
    if not user.check_password(password):
        raise AccountDeletionError(gettext("Mot de passe incorrect."))

    with transaction.atomic():
        result = AccountDeletionResult()
        result.permits_closed = _close_permits(user)
        result.requests_cancelled = _cancel_pending_requests(user)
        result.vehicles_archived = _archive_vehicles(user)
        result.payments_kept = Payment.objects.filter(citizen=user).count()
        anonymise_user(user)
        audit_log(
            AuditAction.ACCOUNT_DELETED,
            actor=user, target=user, request=request,
            payload={
                "diff": {
                    "is_active": [True, False],
                    "anonymised_at": [None, user.anonymised_at.isoformat()],
                },
                "context": {
                    "trigger": "self_service",
                    "permits_closed": result.permits_closed,
                    "requests_cancelled": result.requests_cancelled,
                    "vehicles_archived": result.vehicles_archived,
                    "payments_kept": result.payments_kept,
                },
            },
        )
    return result


def _close_permits(user) -> int:
    """
    Clôture toutes les cartes non terminales. Les cartes d'avant activation
    passent par ``cancel()`` (paiement en cours annulé au préalable), les
    cartes ACTIVE / SUSPENDED par ``close_permit_for_holder()``.
    """
    from apps.payments.models import LIVE_STATUSES, Payment
    from apps.payments.services import cancel_payment
    from apps.permits.models import Permit, PermitStatus
    from apps.permits.services import cancel, close_permit_for_holder

    pre_activation = {
        PermitStatus.DRAFT, PermitStatus.SUBMITTED,
        PermitStatus.MANUAL_REVIEW, PermitStatus.AWAITING_PAYMENT,
    }
    closed = 0
    for permit in Permit.objects.filter(citizen=user).exclude(
        status__in=[PermitStatus.REFUSED, PermitStatus.EXPIRED, PermitStatus.CANCELLED],
    ):
        if permit.status in pre_activation:
            for payment in Payment.objects.filter(permit=permit, status__in=LIVE_STATUSES):
                cancel_payment(payment, by_user=user, reason=ACCOUNT_DELETION_REASON)
            cancel(permit, by_user=user)
        else:
            close_permit_for_holder(permit, by_user=user, reason=ACCOUNT_DELETION_REASON)
        closed += 1
    return closed


def _cancel_pending_requests(user) -> int:
    from apps.citizens.models import AddressChangeRequest, RequestStatus
    from apps.citizens.services import cancel_address_change
    from apps.vehicles.models import PlateChangeRequest, PlateChangeStatus
    from apps.vehicles.services import cancel_plate_change

    count = 0
    for req in AddressChangeRequest.objects.filter(
        profile__user=user, status=RequestStatus.PENDING,
    ):
        cancel_address_change(req, user=user)
        count += 1
    for req in PlateChangeRequest.objects.filter(
        vehicle__owner=user, status=PlateChangeStatus.PENDING,
    ):
        cancel_plate_change(req, user=user)
        count += 1
    return count


def _archive_vehicles(user) -> int:
    from apps.vehicles.services import archive_vehicle

    count = 0
    for vehicle in user.vehicles.filter(archived_at__isnull=True):
        archive_vehicle(vehicle, by_user=user, reason=ACCOUNT_DELETION_REASON)
        count += 1
    return count


# ----- verrouillage anti brute-force ----------------------------------------
#
# Pas de compteur en cache mémoire (faux avec plusieurs workers gunicorn) ni de
# dépendance externe : le compteur est lu dans le journal d'audit, qui reçoit
# déjà une ligne AUTH_FAILED par échec (signal user_login_failed). Le
# verrouillage lui-même est matérialisé par une ligne AUTH_LOCKED, écrite une
# seule fois au déclenchement.
#
# Les tentatives faites pendant le verrouillage sont refusées sans appeler
# authenticate() : elles ne produisent pas d'AUTH_FAILED et ne prolongent donc
# pas le blocage. Le compteur ne prend en compte que les échecs postérieurs à
# la dernière connexion réussie (last_login) et à la fin du dernier verrouillage.

def _lockout_delta() -> dt.timedelta:
    return dt.timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)


def _identifier_logs(action: str, identifier: str):
    from apps.audit.models import AuditLog
    return AuditLog.objects.filter(
        action=action, payload__context__username__iexact=identifier,
    )


def lockout_message() -> str:
    """Message unique, que l'identifiant existe ou non (pas d'énumération de comptes)."""
    return gettext(
        "Trop de tentatives de connexion échouées : cet identifiant est temporairement bloqué. Réessayez dans %(minutes)s minutes ou, si vous avez oublié votre mot de passe, utilisez « Mot de passe oublié »."
    ) % {"minutes": settings.LOGIN_LOCKOUT_MINUTES}


def is_login_locked(identifier: str) -> bool:
    identifier = (identifier or "").strip()
    if not identifier:
        return False
    return _identifier_logs(AuditAction.AUTH_LOCKED, identifier).filter(
        created_at__gt=timezone.now() - _lockout_delta(),
    ).exists()


def register_login_failure(identifier: str, *, request=None) -> bool:
    """
    À appeler après un échec d'authentification (la ligne AUTH_FAILED est déjà
    écrite par le signal). Verrouille l'identifiant si le seuil est atteint.
    Renvoie ``True`` si l'identifiant est désormais verrouillé.
    """
    identifier = (identifier or "").strip()
    if not identifier:
        return False
    if is_login_locked(identifier):
        return True

    now = timezone.now()
    since = now - _lockout_delta()
    last_success = User.objects.filter(username__iexact=identifier).aggregate(
        last=Max("last_login"),
    )["last"]
    if last_success and last_success > since:
        since = last_success
    last_lock = _identifier_logs(AuditAction.AUTH_LOCKED, identifier).aggregate(
        last=Max("created_at"),
    )["last"]
    if last_lock and last_lock + _lockout_delta() > since:
        since = last_lock + _lockout_delta()

    failures = _identifier_logs(AuditAction.AUTH_FAILED, identifier).filter(
        created_at__gt=since,
    ).count()
    if failures < settings.LOGIN_LOCKOUT_MAX_FAILURES:
        return False

    audit_log(
        AuditAction.AUTH_LOCKED,
        actor=None,
        target=User.objects.filter(username__iexact=identifier).first(),
        request=request,
        payload={"context": {
            "username": identifier,
            "failures": failures,
            "window_minutes": settings.LOGIN_LOCKOUT_MINUTES,
            "lock_minutes": settings.LOGIN_LOCKOUT_MINUTES,
        }},
    )
    return True


def register_login_success(user) -> None:
    """
    Remet le compteur à zéro : seuls les échecs postérieurs à ``last_login``
    sont comptés. Le login web met déjà ``last_login`` à jour (signal
    user_logged_in) ; l'API token, qui n'ouvre pas de session, passe par ici.
    """
    update_last_login(None, user)
