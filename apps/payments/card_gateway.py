"""
Passerelle "carte bancaire" interne.

Pas de banque réelle derrière — c'est un processeur **mock** mais qui force le
citoyen à saisir un vrai numéro de carte valide :
- Validation **Luhn** sur le PAN (16 chiffres standard)
- Détection de marque (Visa / Mastercard / Amex / autres)
- Date d'expiration > aujourd'hui
- CVC 3 ou 4 chiffres
- Nom porteur non vide

Le PAN complet n'est **jamais** stocké : seuls la marque et les 4 derniers
chiffres sont persistés sur ``Payment``. Le CVC n'est jamais persisté.

Quelques numéros de test reproduisent le comportement Stripe pour rester
réaliste :

| Carte                   | Comportement                  |
|-------------------------|-------------------------------|
| 4242 4242 4242 4242     | Succès                        |
| 5555 5555 5555 4444     | Succès (Mastercard)           |
| 3782 822463 10005       | Succès (Amex)                 |
| 4000 0000 0000 0002     | Échec — carte refusée         |
| 4000 0000 0000 9995     | Échec — solde insuffisant     |

Tout autre numéro Luhn-valide est accepté en succès.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.permits.models import Permit, PermitStatus
from apps.permits.services import PermitError, mark_paid

from .models import LIVE_STATUSES, Payment, PaymentMethod, PaymentStatus


class CardError(Exception):
    """Erreur fonctionnelle (carte invalide, refusée, expirée…)."""


# ----- numero / luhn / brand -------------------------------------------------

_DECLINED_CARDS = {
    "4000000000000002": "Carte refusée par la banque (do_not_honor).",
    "4000000000009995": "Solde insuffisant.",
    "4000000000000069": "Carte expirée.",
    "4000000000000127": "CVC incorrect.",
}


def _digits_only(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def luhn_valid(pan: str) -> bool:
    """Algorithme de Luhn — checksum standard pour numéros de carte."""
    digits = _digits_only(pan)
    if not (12 <= len(digits) <= 19):
        return False
    total = 0
    parity = len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def detect_brand(pan: str) -> str:
    digits = _digits_only(pan)
    if not digits:
        return ""
    first2 = int(digits[:2]) if len(digits) >= 2 else 0
    if digits.startswith("4"):
        return "visa"
    if 51 <= first2 <= 55 or 2221 <= int(digits[:4] or 0) <= 2720:
        return "mastercard"
    if first2 in (34, 37):
        return "amex"
    if digits.startswith("6"):
        return "discover"
    return "unknown"


# ----- inputs ---------------------------------------------------------------

@dataclass
class CardInput:
    number: str
    holder: str
    exp_month: int
    exp_year: int
    cvc: str

    def validate(self) -> None:
        digits = _digits_only(self.number)
        if not digits:
            raise CardError("Numéro de carte requis.")
        if not luhn_valid(digits):
            raise CardError("Numéro de carte invalide.")
        if not self.holder or len(self.holder.strip()) < 2:
            raise CardError("Nom du titulaire requis.")
        if not (1 <= int(self.exp_month) <= 12):
            raise CardError("Mois d'expiration invalide.")
        # Année à 2 ou 4 chiffres
        year = int(self.exp_year)
        if year < 100:
            year += 2000
        today = dt.date.today()
        last_day = (
            dt.date(year + (1 if self.exp_month == 12 else 0),
                    1 if self.exp_month == 12 else self.exp_month + 1, 1)
            - dt.timedelta(days=1)
        )
        if last_day < today:
            raise CardError("Carte expirée.")
        cvc_digits = _digits_only(self.cvc)
        if not (3 <= len(cvc_digits) <= 4):
            raise CardError("Code de sécurité (CVC) invalide.")


# ----- transitions -----------------------------------------------------------

@transaction.atomic
def initiate_card_payment(permit: Permit, *, by_user, ip: str | None = None) -> Payment:
    permit = Permit.objects.select_for_update().get(pk=permit.pk)
    if permit.citizen_id != by_user.pk:
        raise PermissionDenied
    if permit.status != PermitStatus.AWAITING_PAYMENT:
        raise CardError(
            f"La carte n'est pas en attente de paiement (statut : {permit.get_status_display()})."
        )
    if permit.price_cents <= 0:
        raise CardError("Cette carte est gratuite — pas de paiement nécessaire.")

    # Annule toute tentative live précédente.
    Payment.objects.filter(permit=permit, status__in=LIVE_STATUSES).update(
        status=PaymentStatus.CANCELLED,
        cancelled_at=timezone.now(),
        failure_reason="Remplacé par une nouvelle tentative carte.",
    )

    return Payment.objects.create(
        permit=permit,
        citizen=permit.citizen,
        amount_cents=permit.price_cents,
        method=PaymentMethod.CARD,
        status=PaymentStatus.PENDING,
        initiated_from_ip=ip,
    )


def process_card_payment(
    payment: Payment,
    card: CardInput,
    *,
    by_user,
    ip: str | None = None,
) -> Payment:
    """
    Valide la carte, simule l'autorisation, marque le paiement comme réussi,
    active la carte et envoie l'email. Idempotent sur Payment SUCCEEDED.

    Volontairement pas globalement @transaction.atomic : on veut que les
    écritures FAILED (carte refusée) soient persistées même si on raise.
    Le bloc succès reste atomique localement.
    """
    # Pré-checks rapides.
    if payment.citizen_id != by_user.pk:
        raise PermissionDenied
    payment.refresh_from_db()
    if payment.status == PaymentStatus.SUCCEEDED:
        return payment
    if payment.status not in LIVE_STATUSES:
        raise CardError(
            f"Le paiement n'est plus modifiable (statut : {payment.get_status_display()})."
        )

    # Validation des champs (raise → ne touche pas au Payment, reste PENDING).
    card.validate()

    digits = _digits_only(card.number)
    brand = detect_brand(digits)
    last4 = digits[-4:]

    # Cartes de test bloquées : FAILED commit + raise.
    decline_reason = _DECLINED_CARDS.get(digits)
    if decline_reason:
        with transaction.atomic():
            p = Payment.objects.select_for_update().get(pk=payment.pk)
            p.status = PaymentStatus.FAILED
            p.failed_at = timezone.now()
            p.failure_reason = decline_reason
            p.card_brand = brand
            p.card_last4 = last4
            p.card_holder = card.holder.strip()
            p.save(update_fields=[
                "status", "failed_at", "failure_reason",
                "card_brand", "card_last4", "card_holder",
            ])
        raise CardError(decline_reason)

    # Succès : transition + activation atomique.
    with transaction.atomic():
        p = Payment.objects.select_for_update().get(pk=payment.pk)
        if p.status == PaymentStatus.SUCCEEDED:
            return p  # idempotent (race possible)
        p.status = PaymentStatus.SUCCEEDED
        p.confirmed_at = timezone.now()
        p.confirmed_from_ip = ip
        p.card_brand = brand
        p.card_last4 = last4
        p.card_holder = card.holder.strip()
        p.external_transaction_id = f"AUTH-{p.reference[:10]}"
        p.save(update_fields=[
            "status", "confirmed_at", "confirmed_from_ip",
            "card_brand", "card_last4", "card_holder",
            "external_transaction_id",
        ])
        permit = p.permit
        if permit.status == PermitStatus.AWAITING_PAYMENT:
            try:
                mark_paid(permit)
            except PermitError:
                pass

    from .emails import send_permit_activated_email
    send_permit_activated_email(p)
    return p
