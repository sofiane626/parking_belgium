"""
Workflow paiement — toutes les transitions d'état passent par ici.

Sécurité (paiement réel "interne gratuit") :
- Initiate : un seul paiement live (PENDING/PROCESSING) par carte à la fois
- Confirm : reference + signature TimestampSigner (max_age=15 min) requise
- Verrou DB ``select_for_update`` à chaque transition pour éviter double-spend
- Idempotence : confirmer un paiement déjà SUCCEEDED retourne sans rien faire
- Hook succès : ``permits.services.mark_paid`` + email d'activation
- Refund : suspend la carte et notifie

Le mode SIMULATION court-circuite la phase confirm pour les tests staff/DEBUG.
"""
from __future__ import annotations

from typing import Optional

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.db import transaction
from django.utils import timezone

from apps.permits.models import Permit, PermitStatus
from apps.permits.services import PermitError, mark_paid, suspend_active_permits_for_citizen

from .models import LIVE_STATUSES, Payment, PaymentMethod, PaymentStatus

SIGNER_SALT = "apps.payments.confirm"
SIGNATURE_MAX_AGE_SECONDS = 15 * 60


class PaymentError(Exception):
    """Raised on illegal payment-state transitions or auth/permission issues."""


# ----- signing helpers ------------------------------------------------------

def _signer() -> TimestampSigner:
    return TimestampSigner(salt=SIGNER_SALT)


def sign_reference(reference: str) -> str:
    """Return a timestamped signature of the reference (one-shot, 15-min TTL)."""
    return _signer().sign(reference)


def verify_signed_reference(signed_value: str) -> str:
    """Return the reference if the signature is valid and unexpired."""
    try:
        return _signer().unsign(signed_value, max_age=SIGNATURE_MAX_AGE_SECONDS)
    except SignatureExpired as exc:
        raise PaymentError("Lien de paiement expiré, recommencez.") from exc
    except BadSignature as exc:
        raise PaymentError("Lien de paiement invalide.") from exc


# ----- permission helpers ---------------------------------------------------

def _ensure_owner(payment: Payment, user) -> None:
    if payment.citizen_id != user.pk:
        raise PermissionDenied


def can_simulate(user) -> bool:
    """Simulate button is reserved to staff/back-office or DEBUG mode."""
    if not user.is_authenticated:
        return False
    if settings.DEBUG:
        return True
    if getattr(user, "is_back_office", False) or user.is_staff or user.is_superuser:
        return True
    return False


# ----- transitions ----------------------------------------------------------

@transaction.atomic
def initiate_payment(permit: Permit, *, by_user, ip: Optional[str] = None) -> Payment:
    """
    Create a PENDING payment for ``permit``. Refuses if the permit isn't
    awaiting payment, if there's already a live payment, or if the price is 0
    (those activate automatically — no payment to make).
    """
    permit = Permit.objects.select_for_update().get(pk=permit.pk)
    if permit.citizen_id != by_user.pk:
        raise PermissionDenied
    if permit.status != PermitStatus.AWAITING_PAYMENT:
        raise PaymentError(
            f"La carte n'est pas en attente de paiement (statut actuel : {permit.get_status_display()})."
        )
    if permit.price_cents <= 0:
        raise PaymentError("Cette carte est gratuite — aucun paiement nécessaire.")

    existing = Payment.objects.filter(permit=permit, status__in=LIVE_STATUSES).first()
    if existing:
        return existing  # idempotent: reuse the live payment instead of stacking

    return Payment.objects.create(
        permit=permit,
        citizen=permit.citizen,
        amount_cents=permit.price_cents,
        method=PaymentMethod.INTERNAL_FREE,
        status=PaymentStatus.PENDING,
        initiated_from_ip=ip,
    )


@transaction.atomic
def confirm_payment(
    *,
    signed_reference: str,
    by_user,
    ip: Optional[str] = None,
) -> Payment:
    """
    Real-flow confirmation. Validates the signed reference, locks the payment
    row, transitions PENDING → PROCESSING → SUCCEEDED atomically, then
    activates the permit and notifies the citizen.

    Idempotent : confirming an already-SUCCEEDED payment is a no-op.
    """
    reference = verify_signed_reference(signed_reference)
    payment = (
        Payment.objects.select_for_update()
        .filter(reference=reference)
        .first()
    )
    if payment is None:
        raise PaymentError("Paiement introuvable.")
    _ensure_owner(payment, by_user)

    if payment.status == PaymentStatus.SUCCEEDED:
        return payment  # idempotent
    if payment.status != PaymentStatus.PENDING:
        raise PaymentError(
            f"Le paiement n'est plus modifiable (statut : {payment.get_status_display()})."
        )

    # Two-step transition kept for clarity even though we're in one TX —
    # makes future async / external-gateway integration trivial.
    payment.status = PaymentStatus.PROCESSING
    payment.save(update_fields=["status"])

    payment.status = PaymentStatus.SUCCEEDED
    payment.confirmed_at = timezone.now()
    payment.confirmed_from_ip = ip
    payment.save(update_fields=["status", "confirmed_at", "confirmed_from_ip"])

    _activate_permit_and_notify(payment)
    return payment


@transaction.atomic
def simulate_payment_success(permit: Permit, *, by_user, ip: Optional[str] = None) -> Payment:
    """
    Test-only one-shot success. Restricted by ``can_simulate`` — view enforces.
    Creates (or reuses) a SIMULATION-method payment marked SUCCEEDED, then
    activates the permit + notifies.
    """
    if not can_simulate(by_user):
        raise PermissionDenied
    permit = Permit.objects.select_for_update().get(pk=permit.pk)
    if permit.citizen_id != by_user.pk and not getattr(by_user, "is_back_office", False):
        raise PermissionDenied
    if permit.status != PermitStatus.AWAITING_PAYMENT:
        raise PaymentError(
            f"La carte n'est pas en attente de paiement (statut : {permit.get_status_display()})."
        )

    # Cancel any live "real" payment to avoid leaving a dangling PENDING row.
    Payment.objects.filter(permit=permit, status__in=LIVE_STATUSES).update(
        status=PaymentStatus.CANCELLED,
        cancelled_at=timezone.now(),
        failure_reason="Annulé : remplacé par un paiement simulé.",
    )

    payment = Payment.objects.create(
        permit=permit,
        citizen=permit.citizen,
        amount_cents=permit.price_cents,
        method=PaymentMethod.SIMULATION,
        status=PaymentStatus.SUCCEEDED,
        confirmed_at=timezone.now(),
        initiated_from_ip=ip,
        confirmed_from_ip=ip,
        failure_reason="",
    )
    _activate_permit_and_notify(payment)
    return payment


@transaction.atomic
def cancel_payment(payment: Payment, *, by_user, reason: str = "") -> Payment:
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    _ensure_owner(payment, by_user)
    if payment.status not in LIVE_STATUSES:
        raise PaymentError("Le paiement n'est plus actif.")
    payment.status = PaymentStatus.CANCELLED
    payment.cancelled_at = timezone.now()
    payment.failure_reason = reason or "Annulé par le citoyen."
    payment.save(update_fields=["status", "cancelled_at", "failure_reason"])
    return payment


@transaction.atomic
def fail_payment(payment: Payment, *, reason: str) -> Payment:
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.status not in LIVE_STATUSES:
        raise PaymentError("Le paiement n'est plus actif.")
    payment.status = PaymentStatus.FAILED
    payment.failed_at = timezone.now()
    payment.failure_reason = reason
    payment.save(update_fields=["status", "failed_at", "failure_reason"])
    return payment


@transaction.atomic
def refund_payment(payment: Payment, *, by_user, reason: str) -> Payment:
    """
    Refund a SUCCEEDED payment. Suspends the permit (cascades to visitor codes
    via ``suspend_active_permits_for_citizen``) and emails the citizen.
    """
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if not getattr(by_user, "is_back_office", False) and not by_user.is_superuser:
        raise PermissionDenied
    if payment.status != PaymentStatus.SUCCEEDED:
        raise PaymentError("Seul un paiement validé peut être remboursé.")

    payment.status = PaymentStatus.REFUNDED
    payment.refunded_at = timezone.now()
    payment.failure_reason = reason
    payment.save(update_fields=["status", "refunded_at", "failure_reason"])

    permit = payment.permit
    if permit.status == PermitStatus.ACTIVE:
        suspend_active_permits_for_citizen(
            permit.citizen,
            reason=f"Paiement #{payment.pk} remboursé : {reason}",
        )

    _send_refund_email(payment)
    return payment


# ----- internal hooks -------------------------------------------------------

def _activate_permit_and_notify(payment: Payment) -> None:
    """Activate the permit via permits.mark_paid then send activation email."""
    permit = payment.permit
    if permit.status == PermitStatus.AWAITING_PAYMENT:
        try:
            mark_paid(permit)
        except PermitError:
            # Permit moved out of awaiting_payment between our locks — the
            # payment row stays SUCCEEDED but no double-activation happens.
            return
    _send_activation_email(payment)


def _send_activation_email(payment: Payment) -> None:
    from .emails import send_permit_activated_email
    send_permit_activated_email(payment)


def _send_refund_email(payment: Payment) -> None:
    from .emails import send_payment_refunded_email
    send_payment_refunded_email(payment)
