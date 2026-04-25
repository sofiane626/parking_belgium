import re

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


class VehicleType(models.TextChoices):
    """
    Kept on the model for forward-compat. Today the citizen self-service flow
    only registers passenger cars — the field defaults to ``PASSENGER_CAR`` and
    is intentionally hidden from the public form.
    """

    PASSENGER_CAR = "passenger_car", _("Voiture particulière")
    LCV = "lcv", _("Véhicule utilitaire léger")
    MOTORCYCLE = "motorcycle", _("Moto")
    ELECTRIC_SCOOTER = "electric_scooter", _("Trottinette électrique")
    OTHER = "other", _("Autre")


REGISTRATION_DOC_EXTENSIONS = ["pdf", "jpg", "jpeg", "png", "webp"]
REGISTRATION_DOC_MAX_BYTES = 5 * 1024 * 1024  # 5 MB


def normalize_plate(value: str) -> str:
    """Uppercase and strip whitespace. Hyphens are kept (real Belgian plates use them)."""
    return re.sub(r"\s+", "", value).upper()


class Vehicle(models.Model):
    """
    A vehicle owned by a User. Plate is unique across the platform; the
    registration document (Belgian ``carte grise``) is mandatory at form level.

    The plate cannot be changed via self-service edit — it would invalidate the
    resident card linked to this vehicle. Citizens submit a
    :class:`PlateChangeRequest` that an agent must approve.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vehicles",
    )
    plate = models.CharField(_("plaque"), max_length=20, unique=True, db_index=True)
    vehicle_type = models.CharField(
        _("type"),
        max_length=30,
        choices=VehicleType.choices,
        default=VehicleType.PASSENGER_CAR,
    )
    brand = models.CharField(_("marque"), max_length=50)
    model = models.CharField(_("modèle"), max_length=50)
    color = models.CharField(_("couleur"), max_length=30, blank=True)
    registration_document = models.FileField(
        _("certificat d'immatriculation"),
        upload_to="vehicles/registration_documents/%Y/%m/",
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=REGISTRATION_DOC_EXTENSIONS)],
        help_text=_("PDF, JPG, PNG ou WebP — max 5 Mo."),
    )

    # Soft-delete : un véhicule lié à une carte (Permit.vehicle = PROTECT) ne
    # peut pas être supprimé. L'archivage cache le véhicule de l'UI active du
    # citoyen tout en préservant l'historique des cartes émises.
    archived_at = models.DateTimeField(_("archivé le"), null=True, blank=True, db_index=True)
    archive_reason = models.CharField(_("motif d'archivage"), max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["plate"]
        verbose_name = _("véhicule")
        verbose_name_plural = _("véhicules")

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None

    def save(self, *args, **kwargs):
        self.plate = normalize_plate(self.plate)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.plate} ({self.brand} {self.model})"


class PlateChangeStatus(models.TextChoices):
    PENDING = "pending", _("En attente")
    APPROVED = "approved", _("Approuvée")
    REJECTED = "rejected", _("Refusée")
    CANCELLED = "cancelled", _("Annulée")


class PlateChangeRequest(models.Model):
    """
    Self-service request to change a vehicle's plate. The new plate is checked
    for uniqueness at submission time, but the actual swap happens only when an
    agent approves — the agent's service applies the change atomically and
    notifies the permits app so the resident card can be revoked / reissued.
    """

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="plate_change_requests",
    )
    new_plate = models.CharField(_("nouvelle plaque"), max_length=20)
    new_registration_document = models.FileField(
        _("nouveau certificat d'immatriculation"),
        upload_to="vehicles/plate_change_documents/%Y/%m/",
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=REGISTRATION_DOC_EXTENSIONS)],
        help_text=_("PDF, JPG, PNG ou WebP — max 5 Mo."),
    )
    reason = models.TextField(_("motif"), blank=True)

    status = models.CharField(
        _("statut"),
        max_length=20,
        choices=PlateChangeStatus.choices,
        default=PlateChangeStatus.PENDING,
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    decision_notes = models.TextField(_("notes"), blank=True)

    class Meta:
        ordering = ["-submitted_at"]
        verbose_name = _("demande de changement de plaque")
        verbose_name_plural = _("demandes de changement de plaque")

    def save(self, *args, **kwargs):
        self.new_plate = normalize_plate(self.new_plate)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Plaque {self.vehicle.plate} → {self.new_plate} ({self.status})"
