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
    msg = EmailMultiAlternatives(subject, text_body, _from(), to)
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)


def send_permit_activated_email(payment) -> None:
    user = payment.citizen
    if not user.email:
        return
    permit = payment.permit
    ctx = {
        "user": user,
        "permit": permit,
        "payment": payment,
        "amount_eur": payment.amount_cents / 100,
    }
    _send(
        subject=f"Parking.Belgium — Carte #{permit.pk} activée",
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
