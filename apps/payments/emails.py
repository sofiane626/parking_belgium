"""Notifications transactionnelles liées au paiement."""
from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def _from() -> str:
    return getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@parking.belgium.local")


def _send(*, subject: str, to: list[str], text_body: str, html_body: str) -> None:
    if not to:
        return
    # Reply-To = adresse SMTP réelle pour que le destinataire puisse répondre
    # (et pour aider Gmail à classer comme transactionnel plutôt que marketing).
    reply_to = [getattr(settings, "EMAIL_HOST_USER", None) or _from()]
    msg = EmailMultiAlternatives(
        subject, text_body, _from(), to, reply_to=reply_to,
        headers={
            "Auto-Submitted": "auto-generated",
            "X-Auto-Response-Suppress": "All",
        },
    )
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)


def send_permit_activated_email(payment) -> None:
    user = payment.citizen
    if not user.email:
        return
    permit = payment.permit

    # Charge zones + adresse principale + société pour étoffer la confirmation.
    zones = list(permit.zones.all().order_by("-is_main", "zone_code"))
    main_zone = next((z for z in zones if z.is_main), None)
    additional_zones = [z for z in zones if not z.is_main]

    address = None
    try:
        from apps.citizens.models import Address
        address = (
            Address.objects.filter(profile__user=user)
            .select_related("commune").first()
        )
    except Exception:  # noqa: BLE001 — never let email rendering break the payment flow
        address = None

    # Méthode de paiement lisible + masque carte si applicable.
    method_label = payment.get_method_display()
    card_mask = ""
    if payment.card_brand and payment.card_last4:
        card_mask = f"{payment.card_brand.upper()} •••• {payment.card_last4}"

    ctx = {
        "user": user,
        "permit": permit,
        "payment": payment,
        "amount_eur": payment.amount_cents / 100,
        "zones": zones,
        "main_zone": main_zone,
        "additional_zones": additional_zones,
        "address": address,
        "company": permit.company,
        "target_commune": permit.target_commune,
        "method_label": method_label,
        "card_mask": card_mask,
    }
    _send(
        # Sujet sobre, pas d'emoji, pas de mots déclencheurs marketing.
        subject=f"Confirmation de paiement — Carte de stationnement #{permit.pk}",
        to=[user.email],
        text_body=render_to_string("emails/permit_activated.txt", ctx),
        html_body=render_to_string("emails/permit_activated.html", ctx),
    )


def send_payment_refunded_email(payment) -> None:
    user = payment.citizen
    if not user.email:
        return
    ctx = {
        "user": user,
        "permit": payment.permit,
        "payment": payment,
        "amount_eur": payment.amount_cents / 100,
        "reason": payment.failure_reason,
    }
    _send(
        subject=f"Parking.Belgium — Remboursement paiement #{payment.pk}",
        to=[user.email],
        text_body=render_to_string("emails/payment_refunded.txt", ctx),
        html_body=render_to_string("emails/payment_refunded.html", ctx),
    )
