import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

VAT_RE = re.compile(r"^BE0\d{9}$")


def validate_belgian_vat(value: str) -> None:
    cleaned = value.replace(".", "").replace(" ", "").upper()
    if not VAT_RE.match(cleaned):
        raise ValidationError(_("Format attendu : BE0XXXXXXXXX (10 chiffres après BE0)."))


class Company(models.Model):
    """
    A company / professional activity owned by a citizen. Used as the
    legal-side anchor of a professional permit.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="companies",
    )
    name = models.CharField(_("dénomination"), max_length=200)
    vat_number = models.CharField(
        _("numéro TVA"),
        max_length=15,
        validators=[validate_belgian_vat],
        help_text=_("Format : BE0XXXXXXXXX."),
    )
    activity = models.CharField(_("activité"), max_length=200, blank=True)

    street = models.CharField(_("rue"), max_length=200)
    number = models.CharField(_("numéro"), max_length=20)
    box = models.CharField(_("boîte"), max_length=20, blank=True)
    postal_code = models.CharField(_("code postal"), max_length=10)
    commune = models.ForeignKey(
        "core.Commune",
        on_delete=models.PROTECT,
        related_name="companies",
        verbose_name=_("commune"),
    )
    country = models.CharField(_("pays"), max_length=2, default="BE")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("entreprise")
        verbose_name_plural = _("entreprises")
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "vat_number"],
                name="unique_vat_per_owner",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.vat_number})"

    def save(self, *args, **kwargs):
        self.vat_number = self.vat_number.replace(".", "").replace(" ", "").upper()
        super().save(*args, **kwargs)
