"""Notifications transactionnelles liées au paiement."""
from __future__ import annotations

from contextlib import contextmanager

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import translation


def _from() -> str:
    return getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@parking.belgium.local")


@contextmanager
def _user_locale(user):
    """
    Active la langue préférée du compte le temps du rendu de l'email,
    puis restaure la langue courante. Fallback gracieux si le code est inconnu.
    """
    code = getattr(user, "preferred_language", None) or settings.LANGUAGE_CODE
    valid = {c for c, _name in settings.LANGUAGES}
    if code not in valid:
        code = settings.LANGUAGE_CODE
    with translation.override(code):
        yield


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


def send_permit_activated_email(payment=None, *, permit=None) -> None:
    """
    Envoie l'email d'activation. Deux modes :
    - avec ``payment`` : confirme aussi le paiement (cas standard).
    - avec ``permit`` seul : carte activée sans paiement (visiteur gratuit).
    """
    if payment is None and permit is None:
        return
    if permit is None:
        permit = payment.permit
    user = permit.citizen
    if not user.email:
        return

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
    with _user_locale(user):
        method_label = payment.get_method_display() if payment else ""
        card_mask = ""
        if payment and payment.card_brand and payment.card_last4:
            card_mask = f"{payment.card_brand.upper()} •••• {payment.card_last4}"

        ctx = {
            "user": user,
            "permit": permit,
            "payment": payment,
            "amount_eur": (payment.amount_cents / 100) if payment else 0,
            "zones": zones,
            "main_zone": main_zone,
            "additional_zones": additional_zones,
            "address": address,
            "company": permit.company,
            "target_commune": permit.target_commune,
            "method_label": method_label,
            "card_mask": card_mask,
        }
        from django.utils.translation import gettext
        if payment:
            subject = gettext("Confirmation de paiement — Carte de stationnement #%(pk)s") % {"pk": permit.pk}
        else:
            subject = gettext("Carte de stationnement #%(pk)s activée") % {"pk": permit.pk}
        _send(
            subject=subject,
            to=[user.email],
            text_body=render_to_string("emails/permit_activated.txt", ctx),
            html_body=render_to_string("emails/permit_activated.html", ctx),
        )


def send_expiry_reminder_email(permit) -> None:
    """
    Envoie un email de rappel d'expiration pour une carte qui arrive à
    échéance dans 15 jours. Le citoyen peut anticiper le renouvellement.
    """
    user = permit.citizen
    if not user.email:
        return
    zones = list(permit.zones.all().order_by("-is_main", "zone_code"))
    main_zone = next((z for z in zones if z.is_main), None)
    additional_zones = [z for z in zones if not z.is_main]
    with _user_locale(user):
        ctx = {
            "user": user,
            "permit": permit,
            "zones": zones,
            "main_zone": main_zone,
            "additional_zones": additional_zones,
        }
        from django.utils.translation import gettext
        _send(
            subject=gettext("Parking.Belgium — Votre carte #%(pk)s expire bientôt") % {"pk": permit.pk},
            to=[user.email],
            text_body=render_to_string("emails/permit_expiry_reminder.txt", ctx),
            html_body=render_to_string("emails/permit_expiry_reminder.html", ctx),
        )


def send_payment_refunded_email(payment) -> None:
    user = payment.citizen
    if not user.email:
        return
    with _user_locale(user):
        ctx = {
            "user": user,
            "permit": payment.permit,
            "payment": payment,
            "amount_eur": payment.amount_cents / 100,
            "reason": payment.failure_reason,
        }
        from django.utils.translation import gettext
        _send(
            subject=gettext("Parking.Belgium — Remboursement paiement #%(pk)s") % {"pk": payment.pk},
            to=[user.email],
            text_body=render_to_string("emails/payment_refunded.txt", ctx),
            html_body=render_to_string("emails/payment_refunded.html", ctx),
        )
