"""
Wrapper Stripe Checkout (mode TEST par défaut).

Flux :
1. ``create_checkout_session(payment, success_url, cancel_url)`` →
   crée une session Stripe pour le montant du Payment, stocke le session_id
   sur le Payment et retourne l'URL hostée Stripe.
2. Citoyen est redirigé vers Stripe → entre la carte test (4242…).
3. Stripe redirige vers success_url avec ?session_id=cs_test_xxx
4. ``confirm_from_session_id(session_id, by_user, ip)`` interroge l'API,
   vérifie payment_status='paid', puis active la carte + envoie l'email
   via le service ``confirm_payment_via_stripe``.
5. Webhook ``checkout.session.completed`` (signé) appelle le même service
   en idempotent (filet de sécurité au cas où le citoyen ferme l'onglet
   avant la redirection).

Aucune clé Stripe = mode désactivé (l'UI cache le bouton et bascule sur la
simulation).
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

import stripe

from apps.permits.models import Permit, PermitStatus
from apps.permits.services import PermitError, mark_paid

from .models import LIVE_STATUSES, Payment, PaymentMethod, PaymentStatus

logger = logging.getLogger(__name__)


class StripeNotConfigured(Exception):
    """Raised when Stripe keys are missing — caller should fall back."""


class StripeError(Exception):
    """Generic Stripe wrapper error (network, signature, business)."""


def is_enabled() -> bool:
    return bool(getattr(settings, "STRIPE_SECRET_KEY", "") and
                getattr(settings, "STRIPE_PUBLIC_KEY", ""))


def _client() -> "stripe":
    if not is_enabled():
        raise StripeNotConfigured(
            "Stripe désactivé : STRIPE_SECRET_KEY et STRIPE_PUBLIC_KEY non configurées."
        )
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


@transaction.atomic
def create_checkout_session(
    permit: Permit,
    *,
    by_user,
    request,
    ip: str | None = None,
) -> tuple[Payment, str]:
    """
    Initialise un Payment(method=stripe, status=pending), crée la session
    Stripe, enregistre le session_id, retourne (payment, redirect_url).
    """
    permit = Permit.objects.select_for_update().get(pk=permit.pk)
    if permit.citizen_id != by_user.pk:
        raise PermissionDenied
    if permit.status != PermitStatus.AWAITING_PAYMENT:
        raise StripeError(
            f"La carte n'est pas en attente de paiement (statut : {permit.get_status_display()})."
        )
    if permit.price_cents <= 0:
        raise StripeError("Cette carte est gratuite — pas de paiement nécessaire.")

    # Annule toute tentative live précédente pour éviter les doublons.
    Payment.objects.filter(permit=permit, status__in=LIVE_STATUSES).update(
        status=PaymentStatus.CANCELLED,
        cancelled_at=timezone.now(),
        failure_reason="Remplacé par une nouvelle tentative Stripe.",
    )

    payment = Payment.objects.create(
        permit=permit,
        citizen=permit.citizen,
        amount_cents=permit.price_cents,
        method=PaymentMethod.STRIPE,
        status=PaymentStatus.PENDING,
        initiated_from_ip=ip,
    )

    api = _client()
    success_path = reverse("payments:stripe_success") + f"?reference={payment.reference}"
    cancel_path = reverse("payments:stripe_cancel") + f"?reference={payment.reference}"
    base = f"{request.scheme}://{request.get_host()}"

    session = api.checkout.Session.create(
        mode="payment",
        payment_method_types=["card", "bancontact"],
        client_reference_id=payment.reference,
        customer_email=permit.citizen.email or None,
        line_items=[{
            "price_data": {
                "currency": settings.STRIPE_CURRENCY,
                "product_data": {
                    "name": f"Carte de stationnement #{permit.pk} ({permit.get_permit_type_display()})",
                    "description": (
                        f"Citoyen : {permit.citizen.username} · "
                        + (f"Véhicule {permit.vehicle.plate} · " if permit.vehicle_id else "")
                        + (f"Commune : {permit.target_commune.name_fr}" if permit.target_commune_id else "")
                    ).strip(" ·"),
                },
                "unit_amount": permit.price_cents,
            },
            "quantity": 1,
        }],
        metadata={
            "permit_id": str(permit.pk),
            "payment_reference": payment.reference,
            "citizen_id": str(permit.citizen_id),
        },
        success_url=base + success_path + "&stripe_session={CHECKOUT_SESSION_ID}",
        cancel_url=base + cancel_path,
        locale="fr",
    )
    payment.stripe_session_id = session.id
    payment.save(update_fields=["stripe_session_id"])
    return payment, session.url


@transaction.atomic
def confirm_from_session_id(
    session_id: str,
    *,
    by_user=None,
    ip: str | None = None,
) -> Payment:
    """
    Récupère la session côté Stripe, vérifie payment_status='paid', active
    la carte. Idempotent : un Payment SUCCEEDED reste SUCCEEDED sans
    relancer mark_paid ni email.
    """
    if not session_id:
        raise StripeError("session_id manquant.")
    payment = (
        Payment.objects.select_for_update()
        .filter(stripe_session_id=session_id)
        .first()
    )
    if payment is None:
        raise StripeError("Paiement Stripe introuvable.")
    if by_user is not None and payment.citizen_id != by_user.pk:
        raise PermissionDenied

    if payment.status == PaymentStatus.SUCCEEDED:
        return payment  # idempotent

    api = _client()
    try:
        session = api.checkout.Session.retrieve(session_id, expand=["payment_intent"])
    except stripe.StripeError as exc:
        raise StripeError(f"Erreur Stripe : {exc}") from exc

    if session.payment_status != "paid":
        raise StripeError(
            f"Le paiement n'est pas encore validé côté Stripe (statut : {session.payment_status})."
        )

    pi = session.payment_intent
    if isinstance(pi, str):
        payment.stripe_payment_intent = pi
    elif pi is not None:
        payment.stripe_payment_intent = pi.id
        payment.external_transaction_id = (
            getattr(pi, "latest_charge", "") or ""
        )
    payment.status = PaymentStatus.SUCCEEDED
    payment.confirmed_at = timezone.now()
    payment.confirmed_from_ip = ip
    payment.save(update_fields=[
        "status", "confirmed_at", "confirmed_from_ip",
        "stripe_payment_intent", "external_transaction_id",
    ])

    permit = payment.permit
    if permit.status == PermitStatus.AWAITING_PAYMENT:
        try:
            mark_paid(permit)
        except PermitError:
            pass

    from .emails import send_permit_activated_email
    send_permit_activated_email(payment)
    return payment


def cancel_session(reference: str, *, by_user) -> Payment | None:
    """Mark the Payment as cancelled when Stripe redirected to cancel URL."""
    payment = Payment.objects.filter(reference=reference).first()
    if payment is None:
        return None
    if payment.citizen_id != by_user.pk:
        raise PermissionDenied
    if payment.status not in LIVE_STATUSES:
        return payment
    payment.status = PaymentStatus.CANCELLED
    payment.cancelled_at = timezone.now()
    payment.failure_reason = "Annulé sur la page de paiement Stripe."
    payment.save(update_fields=["status", "cancelled_at", "failure_reason"])
    return payment


def verify_webhook(payload: bytes, signature_header: str) -> dict:
    """
    Vérifie la signature du webhook Stripe et retourne l'event décodé.
    Le secret vient de ``stripe listen`` en local, ou du dashboard en prod.
    """
    secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
    if not secret:
        raise StripeNotConfigured("STRIPE_WEBHOOK_SECRET non configuré.")
    api = _client()
    try:
        return api.Webhook.construct_event(payload, signature_header, secret)
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise StripeError(f"Signature webhook invalide : {exc}") from exc


def handle_webhook_event(event: dict) -> None:
    """Dispatch des events qui nous intéressent."""
    event_type = event.get("type", "")
    obj = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        session_id = obj.get("id")
        if session_id:
            try:
                confirm_from_session_id(session_id)
            except StripeError as exc:
                logger.warning("Webhook confirm_from_session_id échec : %s", exc)
    # Future : "charge.refunded", "checkout.session.async_payment_failed"…
