"""
Paiement attaché à une carte (Permit).

Une carte peut générer plusieurs ``Payment`` (échec puis nouvelle tentative),
mais un seul peut atteindre l'état SUCCEEDED — protégé par contrainte unique
partielle. La transition d'état est centralisée dans services.py et utilise
``select_for_update`` pour empêcher tout double-spend / double-activation.
"""
from __future__ import annotations

import secrets

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


def _generate_reference() -> str:
    """URL-safe random token used as both idempotency key and signed reference."""
    return secrets.token_urlsafe(24)


class PaymentStatus(models.TextChoices):
    PENDING = "pending", _("En attente")
    PROCESSING = "processing", _("Traitement")
    SUCCEEDED = "succeeded", _("Validé")
    FAILED = "failed", _("Échoué")
    CANCELLED = "cancelled", _("Annulé")
    REFUNDED = "refunded", _("Remboursé")


class PaymentMethod(models.TextChoices):
    CARD = "card", _("Carte bancaire")
    STRIPE = "stripe", _("Carte bancaire (Stripe)")
    INTERNAL_FREE = "internal_free", _("Paiement interne gratuit")
    SIMULATION = "simulation", _("Simulation (test)")


# Statuses where a payment is still "live" and blocks further attempts on the permit.
LIVE_STATUSES = {PaymentStatus.PENDING, PaymentStatus.PROCESSING}
TERMINAL_STATUSES = {
    PaymentStatus.SUCCEEDED,
    PaymentStatus.FAILED,
    PaymentStatus.CANCELLED,
    PaymentStatus.REFUNDED,
}


class Payment(models.Model):
    permit = models.ForeignKey(
        "permits.Permit",
        on_delete=models.CASCADE,
        related_name="payments",
    )
    citizen = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    amount_cents = models.IntegerField(_("montant (centimes)"))
    method = models.CharField(
        _("méthode"),
        max_length=30,
        choices=PaymentMethod.choices,
        default=PaymentMethod.INTERNAL_FREE,
    )
    status = models.CharField(
        _("statut"),
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )

    # Random URL-safe token. Used both as opaque external reference and as the
    # body of the signed token the user POSTs back to confirm.
    reference = models.CharField(
        _("référence"),
        max_length=64,
        unique=True,
        default=_generate_reference,
        db_index=True,
    )

    # Stripe Checkout session id (cs_test_...) — set when redirecting the user
    # to Stripe and used to look up the session on success / via webhook.
    stripe_session_id = models.CharField(
        _("Stripe session id"),
        max_length=255, blank=True, default="", db_index=True,
    )
    stripe_payment_intent = models.CharField(
        _("Stripe PaymentIntent"),
        max_length=255, blank=True, default="",
    )
    # Pour le formulaire carte interne : on garde la marque + 4 derniers
    # chiffres (jamais le PAN complet). Le CVC n'est jamais persisté.
    card_brand = models.CharField(_("marque carte"), max_length=20, blank=True, default="")
    card_last4 = models.CharField(_("4 derniers chiffres"), max_length=4, blank=True, default="")
    card_holder = models.CharField(_("titulaire"), max_length=120, blank=True, default="")

    # Captured later (charge id, paypal txn id…)
    external_transaction_id = models.CharField(
        _("ID transaction externe"),
        max_length=120,
        blank=True,
        default="",
    )

    failure_reason = models.TextField(_("raison d'échec"), blank=True)

    initiated_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)

    initiated_from_ip = models.GenericIPAddressField(null=True, blank=True)
    confirmed_from_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-initiated_at"]
        verbose_name = _("paiement")
        verbose_name_plural = _("paiements")
        constraints = [
            # Au plus un paiement réussi par carte — protège contre toute
            # double activation, même si une race condition contournait
            # la state machine.
            models.UniqueConstraint(
                fields=["permit"],
                condition=models.Q(status="succeeded"),
                name="one_succeeded_payment_per_permit",
            ),
        ]
        indexes = [
            models.Index(fields=["permit", "status"]),
            models.Index(fields=["citizen", "status"]),
        ]

    def __str__(self) -> str:
        return f"Payment#{self.pk} permit={self.permit_id} {self.status} {self.amount_cents}c"

    @property
    def is_live(self) -> bool:
        return self.status in LIVE_STATUSES

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES
