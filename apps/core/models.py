from django.db import models
from django.utils.translation import gettext_lazy as _


class Commune(models.Model):
    """
    A Brussels-Capital commune. Reference table seeded with the 19 communes.

    The ``niscode`` is the Belgian National Statistical Institute code; it is the
    bridge to GIS polygons (which carry the same niscode attribute).
    """

    niscode = models.CharField(_("code NIS"), max_length=10, unique=True)
    name_fr = models.CharField(_("nom (fr)"), max_length=100)
    name_nl = models.CharField(_("nom (nl)"), max_length=100)
    name_en = models.CharField(_("nom (en)"), max_length=100, blank=True)
    # Liste de codes postaux belges desservis par cette commune, séparés par
    # virgule. Utilisé pour pré-remplir la commune à l'inscription depuis le
    # code postal saisi par le citoyen. Une commune peut couvrir plusieurs CP
    # (Bruxelles-Ville en couvre 8) et un même CP peut chevaucher plusieurs
    # communes (rare à Bruxelles, traité avec une priorité par CP-pivot).
    postal_codes = models.CharField(
        _("codes postaux"), max_length=200, blank=True, default="",
        help_text=_("CSV ex: 1000,1020,1120 — utilisé pour auto-remplir la commune"),
    )

    class Meta:
        ordering = ["name_fr"]
        verbose_name = _("commune")
        verbose_name_plural = _("communes")

    def __str__(self) -> str:
        return self.name_fr

    @classmethod
    def for_postal_code(cls, postal_code: str):
        """
        Lookup the commune that serves a given postal code. Returns None if
        nothing matches. Strips whitespace; tolerates leading zeros being
        absent. Performs a substring search on the CSV ``postal_codes`` field
        anchored on word boundaries.
        """
        from django.db.models import Q
        pc = (postal_code or "").strip()
        if not pc:
            return None
        # Match exact tokens (start, end, or surrounded by commas).
        return cls.objects.filter(
            Q(postal_codes__exact=pc) |
            Q(postal_codes__startswith=f"{pc},") |
            Q(postal_codes__endswith=f",{pc}") |
            Q(postal_codes__contains=f",{pc},")
        ).first()
