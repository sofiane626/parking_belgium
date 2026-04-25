"""
Business rules layered on top of GIS polygons.

The rule lives next to the polygon it applies to, but is created/edited entirely
in the back-office — never in the source shapefile. This separation lets us
re-import a new GIS version without losing administrative decisions.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class PermitType(models.TextChoices):
    RESIDENT = "resident", _("Riverain")
    VISITOR = "visitor", _("Visiteur")
    PROFESSIONAL = "professional", _("Professionnel")


class RuleAction(models.TextChoices):
    ADD_ZONE = "add_zone", _("Ajouter une zone")
    REPLACE_MAIN_ZONE = "replace_main_zone", _("Remplacer la zone principale")
    MANUAL_REVIEW = "manual_review", _("Forcer revue manuelle")
    DENY = "deny", _("Refuser l'attribution automatique")


class PolygonRule(models.Model):
    polygon = models.ForeignKey(
        "gis_data.GISPolygon",
        on_delete=models.CASCADE,
        related_name="rules",
    )
    commune = models.ForeignKey(
        "core.Commune",
        on_delete=models.PROTECT,
        related_name="polygon_rules",
    )
    permit_type = models.CharField(
        _("type de carte"),
        max_length=20,
        choices=PermitType.choices,
    )
    action_type = models.CharField(
        _("action"),
        max_length=30,
        choices=RuleAction.choices,
    )
    target_zone_code = models.CharField(
        _("zonecode cible"),
        max_length=100,
        blank=True,
        help_text=_("Requis pour ADD_ZONE et REPLACE_MAIN_ZONE."),
    )
    priority = models.IntegerField(
        _("priorité"),
        default=100,
        help_text=_("Plus petit = plus prioritaire (appliqué en premier)."),
    )
    valid_from = models.DateField(_("valide à partir du"), null=True, blank=True)
    valid_until = models.DateField(_("valide jusqu'au"), null=True, blank=True)
    is_active = models.BooleanField(_("active"), default=True)
    description = models.TextField(_("description"), blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "id"]
        verbose_name = _("règle polygone")
        verbose_name_plural = _("règles polygones")

    def __str__(self) -> str:
        return f"{self.polygon.zonecode} · {self.permit_type} · {self.action_type} (p={self.priority})"

    def is_currently_valid(self, on_date=None) -> bool:
        from django.utils import timezone
        d = on_date or timezone.now().date()
        if not self.is_active:
            return False
        if self.valid_from and d < self.valid_from:
            return False
        if self.valid_until and d > self.valid_until:
            return False
        return True
