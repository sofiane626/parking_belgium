"""
Cartes de stationnement (permits).

Models defined here:
- Permit, PermitZone, VisitorCode (lifecycle of a card + its zones)
- PermitConfig (singleton — global limits + fallback prices)
- CommunePermitPolicy (per-commune × per-type policy with time effectivity
  and pluggable price strategies)
"""
import datetime as dt
from decimal import Decimal

_HEADER_PLACEHOLDER = """\

A single ``Permit`` row covers the whole life of a card — from initial draft
all the way to expiry. The state machine matches the spec exactly:

    draft → submitted → manual_review → refused
                     → manual_review → awaiting_payment → active → suspended
                                                                 → expired
                                                                 → cancelled
                     → awaiting_payment → active → ...
                     → refused

Once active, ``PermitZone`` rows materialise the zones the citizen is allowed to
park in, with full provenance (which polygon and which rule produced each
zonecode).
"""  # noqa: PYL-W0105 — module-level docstring placeholder
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class PermitType(models.TextChoices):
    RESIDENT = "resident", _("Riverain")
    VISITOR = "visitor", _("Visiteur")
    PROFESSIONAL = "professional", _("Professionnel")


class PermitStatus(models.TextChoices):
    DRAFT = "draft", _("Brouillon")
    SUBMITTED = "submitted", _("Soumise")
    MANUAL_REVIEW = "manual_review", _("Revue manuelle")
    REFUSED = "refused", _("Refusée")
    AWAITING_PAYMENT = "awaiting_payment", _("En attente de paiement")
    ACTIVE = "active", _("Active")
    SUSPENDED = "suspended", _("Suspendue")
    EXPIRED = "expired", _("Expirée")
    CANCELLED = "cancelled", _("Annulée")


class ZoneSource(models.TextChoices):
    POLYGON = "polygon", _("Polygone GIS")
    RULE = "rule", _("Règle métier")
    MANUAL = "manual", _("Saisie manuelle")


# Statuses where active cards exist (need to be suspended on address/plate change).
ACTIVE_STATUSES = {PermitStatus.ACTIVE}

# Statuses where the card is "in progress" (citizen is engaged but not yet active).
IN_PROGRESS_STATUSES = {
    PermitStatus.SUBMITTED,
    PermitStatus.MANUAL_REVIEW,
    PermitStatus.AWAITING_PAYMENT,
}


class Permit(models.Model):
    citizen = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="permits",
    )
    vehicle = models.ForeignKey(
        "vehicles.Vehicle",
        on_delete=models.PROTECT,
        related_name="permits",
        null=True, blank=True,  # visitor permits aren't tied to a single plate
    )
    company = models.ForeignKey(
        "companies.Company",
        on_delete=models.PROTECT,
        related_name="permits",
        null=True, blank=True,  # only set on professional permits
    )
    target_commune = models.ForeignKey(
        "core.Commune",
        on_delete=models.PROTECT,
        related_name="+",
        null=True, blank=True,  # used by professional permits — entire commune
    )
    permit_type = models.CharField(
        _("type"),
        max_length=20,
        choices=PermitType.choices,
    )
    status = models.CharField(
        _("statut"),
        max_length=20,
        choices=PermitStatus.choices,
        default=PermitStatus.DRAFT,
    )

    # ---- Submission & evaluation -----------------------------------------
    submitted_at = models.DateTimeField(null=True, blank=True)
    # Snapshot of the attribution engine result at evaluation time. Kept
    # verbatim so the agent screen can replay the engine's reasoning even if
    # rules / GIS version change later.
    attribution_snapshot = models.JSONField(_("snapshot d'attribution"), default=dict, blank=True)
    # The polygon that contained the citizen's address at evaluation time —
    # nullable because GIS versions may rotate.
    source_polygon = models.ForeignKey(
        "gis_data.GISPolygon",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="+",
    )

    # ---- Manual review decision ------------------------------------------
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="+",
    )
    decision_notes = models.TextField(_("notes de décision"), blank=True)

    # ---- Payment ---------------------------------------------------------
    awaiting_payment_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    price_cents = models.IntegerField(_("prix (centimes)"), default=0)

    # ---- Activation & lifecycle ------------------------------------------
    activated_at = models.DateTimeField(null=True, blank=True)
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspension_reason = models.TextField(_("raison de suspension"), blank=True)
    expired_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("carte")
        verbose_name_plural = _("cartes")
        indexes = [
            models.Index(fields=["citizen", "status"]),
            models.Index(fields=["vehicle", "status"]),
        ]

    def __str__(self) -> str:
        plate = self.vehicle.plate if self.vehicle_id else "—"
        return f"#{self.pk} {self.permit_type}/{self.status} ({plate})"

    @property
    def is_active(self) -> bool:
        return self.status == PermitStatus.ACTIVE

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            PermitStatus.REFUSED,
            PermitStatus.EXPIRED,
            PermitStatus.CANCELLED,
        }


class PermitZone(models.Model):
    permit = models.ForeignKey(
        Permit,
        on_delete=models.CASCADE,
        related_name="zones",
    )
    zone_code = models.CharField(_("zonecode"), max_length=100)
    is_main = models.BooleanField(_("zone principale"), default=False)
    source = models.CharField(
        _("provenance"),
        max_length=20,
        choices=ZoneSource.choices,
    )
    source_polygon = models.ForeignKey(
        "gis_data.GISPolygon",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="+",
    )
    source_rule = models.ForeignKey(
        "rules.PolygonRule",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("zone de carte")
        verbose_name_plural = _("zones de cartes")
        constraints = [
            models.UniqueConstraint(
                fields=["permit", "zone_code"],
                name="unique_zone_per_permit",
            ),
            # At most one main zone per permit.
            models.UniqueConstraint(
                fields=["permit"],
                condition=models.Q(is_main=True),
                name="one_main_zone_per_permit",
            ),
        ]

    def __str__(self) -> str:
        flag = " (principale)" if self.is_main else ""
        return f"{self.zone_code}{flag}"


class VisitorCodeStatus(models.TextChoices):
    ACTIVE = "active", _("Actif")
    CANCELLED = "cancelled", _("Annulé")


class VisitorCode(models.Model):
    """
    A visitor parking code generated by a citizen with an active visitor permit.
    Each code grants temporary parking for a single visitor's plate within the
    citizen's resident zone(s) for a configurable duration.
    """

    permit = models.ForeignKey(
        Permit,
        on_delete=models.CASCADE,
        related_name="visitor_codes",
    )
    code = models.CharField(_("code"), max_length=20, unique=True, db_index=True)
    plate = models.CharField(_("plaque visiteur"), max_length=20)
    valid_from = models.DateTimeField(_("valide à partir de"))
    valid_until = models.DateTimeField(_("valide jusqu'au"))
    status = models.CharField(
        _("statut"),
        max_length=20,
        choices=VisitorCodeStatus.choices,
        default=VisitorCodeStatus.ACTIVE,
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("code visiteur")
        verbose_name_plural = _("codes visiteurs")
        indexes = [
            models.Index(fields=["permit", "status"]),
            models.Index(fields=["plate", "valid_from", "valid_until"]),
        ]

    def __str__(self) -> str:
        return f"{self.code} → {self.plate}"


class PermitConfig(models.Model):
    """
    Singleton with **global** business parameters that don't depend on a
    commune. Per-commune-and-type rules live in :class:`CommunePermitPolicy`
    and override the prices / validity defaults below for that specific
    (commune, permit_type) pair.
    """

    # Default fallback prices (used when no CommunePermitPolicy exists).
    resident_price_cents = models.IntegerField(_("prix riverain défaut (centimes)"), default=1000)
    visitor_price_cents = models.IntegerField(_("prix visiteur défaut (centimes)"), default=0)
    professional_price_cents = models.IntegerField(_("prix professionnel défaut (centimes)"), default=5000)

    # Visitor codes are global — same rule applies everywhere in the Region.
    visitor_codes_per_year = models.IntegerField(_("codes visiteurs / an"), default=100)
    visitor_code_default_hours = models.IntegerField(_("durée code visiteur — défaut (h)"), default=4)
    visitor_code_max_hours = models.IntegerField(_("durée code visiteur — max (h)"), default=72)

    permit_default_validity_days = models.IntegerField(_("validité par défaut (jours)"), default=365)

    # Cross-cutting limits that apply to every citizen everywhere.
    max_vehicles_per_citizen = models.IntegerField(_("nb max véhicules / citoyen"), default=5)
    max_companies_per_citizen = models.IntegerField(_("nb max entreprises / citoyen"), default=5)
    max_active_pro_per_citizen = models.IntegerField(_("nb max cartes pro actives / citoyen"), default=3)
    allow_cumul_resident_pro = models.BooleanField(_("autoriser cumul riverain + pro"), default=True)

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = _("configuration globale")
        verbose_name_plural = _("configurations globales")

    def __str__(self) -> str:
        return f"PermitConfig (updated {self.updated_at:%Y-%m-%d %H:%M})"

    @classmethod
    def get(cls) -> "PermitConfig":
        instance = cls.objects.first()
        if instance is None:
            instance = cls.objects.create()
        return instance

    def price_for(self, permit_type: str) -> int:
        return {
            "resident": self.resident_price_cents,
            "visitor": self.visitor_price_cents,
            "professional": self.professional_price_cents,
        }.get(permit_type, 0)


class PriceStrategy(models.TextChoices):
    FIXED = "fixed", _("Prix fixe")
    GRID = "grid", _("Grille (selon rang)")
    EXPONENTIAL = "exponential", _("Exponentielle (base × facteur^(rang-1))")


class CommunePermitPolicy(models.Model):
    """
    Per-commune-and-permit-type policy. The pair (commune, permit_type) can
    have several rows that succeed each other in time via ``effective_from``
    and ``effective_until`` — admins schedule a price change by adding a new
    row instead of editing the existing one (the engine picks whichever row
    is currently effective).
    """

    commune = models.ForeignKey(
        "core.Commune",
        on_delete=models.CASCADE,
        related_name="permit_policies",
    )
    permit_type = models.CharField(
        _("type de carte"),
        max_length=20,
        choices=PermitType.choices,
    )

    # Availability ----------------------------------------------------------
    is_enabled = models.BooleanField(_("type proposé dans cette commune"), default=True)
    auto_attribution = models.BooleanField(
        _("attribution automatique"),
        default=True,
        help_text=_("Si décoché, toute demande passe en revue manuelle même si l'engine ne le requiert pas."),
    )

    # Validity --------------------------------------------------------------
    validity_days = models.IntegerField(_("validité (jours)"), default=365)

    # Pricing ---------------------------------------------------------------
    price_strategy = models.CharField(
        _("stratégie de prix"),
        max_length=20,
        choices=PriceStrategy.choices,
        default=PriceStrategy.FIXED,
    )
    price_fixed_cents = models.IntegerField(
        _("prix fixe (centimes)"),
        default=0,
        help_text=_("Utilisé si stratégie = fixed."),
    )
    price_grid = models.JSONField(
        _("grille tarifaire"),
        default=list,
        blank=True,
        help_text=_("Liste de [rang_seuil, prix_centimes] — ex: [[1,1000],[2,2500],[3,5000]]."),
    )
    price_exponential_base_cents = models.IntegerField(
        _("base exponentielle (centimes)"), default=1000,
    )
    price_exponential_factor = models.DecimalField(
        _("facteur exponentiel"),
        max_digits=6, decimal_places=2, default=Decimal("1.50"),
    )

    # Per-card limits -------------------------------------------------------
    max_active_per_citizen = models.IntegerField(
        _("nb max cartes actives / citoyen (vide = illimité)"),
        null=True, blank=True,
    )
    max_vehicles_per_card = models.IntegerField(
        _("nb max véhicules / carte (vide = illimité)"),
        null=True, blank=True,
        help_text=_("Pertinent surtout pour la carte professionnelle."),
    )

    # Time validity of the policy itself -----------------------------------
    effective_from = models.DateField(_("effective à partir du"), default=dt.date.today)
    effective_until = models.DateField(_("effective jusqu'au"), null=True, blank=True)

    notes = models.TextField(_("notes"), blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ["commune__name_fr", "permit_type", "-effective_from"]
        verbose_name = _("politique commune × type")
        verbose_name_plural = _("politiques commune × type")
        indexes = [
            models.Index(fields=["commune", "permit_type", "effective_from"]),
        ]

    def __str__(self) -> str:
        return f"{self.commune.name_fr} · {self.get_permit_type_display()} (depuis {self.effective_from})"

    def is_currently_effective(self, on_date=None) -> bool:
        from django.utils import timezone as _tz
        # Use local date (TIME_ZONE) — sinon on a un trou la nuit entre minuit
        # local et minuit UTC où aucune policy n'est considérée effective.
        d = on_date or _tz.localdate()
        if not self.is_enabled:
            return False
        if self.effective_from and d < self.effective_from:
            return False
        if self.effective_until and d > self.effective_until:
            return False
        return True

    @classmethod
    def active_for(cls, commune, permit_type, on_date=None):
        from django.db.models import Q
        from django.utils import timezone as _tz
        d = on_date or _tz.localdate()
        return (
            cls.objects.filter(
                commune=commune, permit_type=permit_type,
                is_enabled=True, effective_from__lte=d,
            )
            .filter(Q(effective_until__isnull=True) | Q(effective_until__gte=d))
            .order_by("-effective_from").first()
        )

    def compute_price(self, *, rank: int = 1) -> int:
        if self.price_strategy == PriceStrategy.FIXED:
            return self.price_fixed_cents
        if self.price_strategy == PriceStrategy.GRID:
            grid = sorted([(int(r), int(c)) for r, c in (self.price_grid or [])], key=lambda x: x[0])
            if not grid:
                return 0
            chosen = grid[0][1]
            for thresh, cents in grid:
                if rank >= thresh:
                    chosen = cents
            return chosen
        if self.price_strategy == PriceStrategy.EXPONENTIAL:
            return int(self.price_exponential_base_cents * float(self.price_exponential_factor) ** (rank - 1))
        return 0
