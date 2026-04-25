from django.conf import settings
from django.contrib.gis.db import models as gismodels
from django.db import models
from django.utils.translation import gettext_lazy as _


class CitizenProfile(models.Model):
    """
    Civic profile attached to a User. Lazily created on first dashboard access
    so back-office accounts don't get one until they actually need it.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="citizen_profile",
    )
    national_number = models.CharField(_("numéro national"), max_length=15, blank=True)
    phone = models.CharField(_("téléphone"), max_length=30, blank=True)
    date_of_birth = models.DateField(_("date de naissance"), null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("profil citoyen")
        verbose_name_plural = _("profils citoyens")

    def __str__(self) -> str:
        return f"Profil de {self.user.username}"


class Address(models.Model):
    """
    A citizen has exactly one principal address. The geocoded ``location`` is
    populated by the GIS step (services geocode the textual address into a Point
    in WGS84). Until then it stays ``NULL``.

    Citizens cannot edit this directly — they submit an
    :class:`AddressChangeRequest` that an agent must approve. On approval the
    service updates this row and emits ``address_changed``, which the permits
    app subscribes to in order to suspend active resident cards.
    """

    profile = models.OneToOneField(
        CitizenProfile,
        on_delete=models.CASCADE,
        related_name="address",
    )
    street = models.CharField(_("rue"), max_length=200)
    number = models.CharField(_("numéro"), max_length=20)
    box = models.CharField(_("boîte"), max_length=20, blank=True)
    postal_code = models.CharField(_("code postal"), max_length=10)
    commune = models.ForeignKey(
        "core.Commune",
        on_delete=models.PROTECT,
        related_name="addresses",
        verbose_name=_("commune"),
    )
    country = models.CharField(_("pays"), max_length=2, default="BE")
    location = gismodels.PointField(_("point géocodé"), srid=4326, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("adresse")
        verbose_name_plural = _("adresses")

    def __str__(self) -> str:
        box = f" bte {self.box}" if self.box else ""
        return f"{self.street} {self.number}{box}, {self.postal_code} {self.commune}"


class RequestStatus(models.TextChoices):
    """
    Generic four-state status for citizen-submitted change requests. Reused as-is
    by :class:`AddressChangeRequest` and (separately, on its own model) by
    ``vehicles.PlateChangeRequest``.
    """

    PENDING = "pending", _("En attente")
    APPROVED = "approved", _("Approuvée")
    REJECTED = "rejected", _("Refusée")
    CANCELLED = "cancelled", _("Annulée")


class AddressChangeRequest(models.Model):
    """
    Self-service request to change the principal address. An agent must approve;
    on approval the new fields are applied to :class:`Address` via
    :func:`apps.citizens.services.approve_address_change`, which in turn fires
    ``address_changed`` so card suspension kicks in.
    """

    profile = models.ForeignKey(
        CitizenProfile,
        on_delete=models.CASCADE,
        related_name="address_change_requests",
    )

    # Proposed new address — same shape as Address (minus geocoding).
    street = models.CharField(_("rue"), max_length=200)
    number = models.CharField(_("numéro"), max_length=20)
    box = models.CharField(_("boîte"), max_length=20, blank=True)
    postal_code = models.CharField(_("code postal"), max_length=10)
    commune = models.ForeignKey(
        "core.Commune",
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("commune"),
    )
    country = models.CharField(_("pays"), max_length=2, default="BE")
    reason = models.TextField(_("motif"), blank=True)

    status = models.CharField(
        _("statut"),
        max_length=20,
        choices=RequestStatus.choices,
        default=RequestStatus.PENDING,
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
        verbose_name = _("demande de changement d'adresse")
        verbose_name_plural = _("demandes de changement d'adresse")

    def __str__(self) -> str:
        return f"Changement d'adresse #{self.pk} — {self.profile.user.username} ({self.status})"
