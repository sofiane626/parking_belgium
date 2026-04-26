"""
Permit lifecycle services. Every state transition goes through here so the
state machine is enforced in one place — never tweak ``permit.status`` directly
from a view.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import asdict
from typing import Optional

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.citizens.models import Address
from apps.citizens.services import get_or_create_profile
from apps.rules.models import PolygonRule, RuleAction
from apps.rules.services import resolve_zones

from .models import (
    ACTIVE_STATUSES,
    IN_PROGRESS_STATUSES,
    Permit,
    PermitConfig,
    PermitStatus,
    PermitType,
    PermitZone,
    ZoneSource,
)


class PermitError(Exception):
    """Raised on illegal state transitions or missing prerequisites."""


# ----- snapshot helpers -----------------------------------------------------

def _snapshot_attribution(result) -> dict:
    """Serialise an :class:`AttributionResult` for storage in JSONField."""
    return {
        "main_zone": result.main_zone,
        "additional_zones": list(result.additional_zones),
        "requires_manual_review": result.requires_manual_review,
        "denied": result.denied,
        "polygon_pk": result.polygon.pk if result.polygon else None,
        "polygon_zonecode": result.polygon.zonecode if result.polygon else None,
        "applied_rules": [
            {
                "pk": r.pk,
                "action_type": r.action_type,
                "target_zone_code": r.target_zone_code,
                "priority": r.priority,
            }
            for r in result.applied_rules
        ],
        "notes": list(result.notes),
    }


def _price_for(permit_type: str, *, citizen=None, commune=None) -> int:
    """Resolve commune-specific price; fallback to global default."""
    from . import policies
    if citizen is not None:
        return policies.compute_price(citizen, permit_type, commune=commune)
    return PermitConfig.get().price_for(permit_type)


# ----- creation & submission ------------------------------------------------

def create_draft(citizen, vehicle, permit_type: str = PermitType.RESIDENT) -> Permit:
    if permit_type == PermitType.RESIDENT and vehicle is None:
        raise PermitError("Une carte riverain exige un véhicule.")
    if vehicle and vehicle.owner_id != citizen.pk:
        raise PermissionDenied("Le véhicule n'appartient pas à ce citoyen.")

    from . import policies
    commune = policies.commune_for(citizen, permit_type)
    policies.enforce_card_type_enabled(commune, permit_type)
    policies.enforce_cumul_resident_pro(citizen, permit_type)
    policies.enforce_max_active_per_citizen(citizen, commune, permit_type)

    return Permit.objects.create(
        citizen=citizen,
        vehicle=vehicle,
        permit_type=permit_type,
        status=PermitStatus.DRAFT,
        price_cents=_price_for(permit_type, citizen=citizen, commune=commune),
    )


@transaction.atomic
def submit_application(permit: Permit) -> Permit:
    """
    Move from DRAFT to SUBMITTED, then immediately run the engine to land on
    one of: AWAITING_PAYMENT, MANUAL_REVIEW, or REFUSED.
    """
    if permit.status != PermitStatus.DRAFT:
        raise PermitError(f"Cannot submit a permit in status {permit.status}.")

    permit.status = PermitStatus.SUBMITTED
    permit.submitted_at = timezone.now()
    permit.save(update_fields=["status", "submitted_at", "updated_at"])

    return _evaluate(permit)


@transaction.atomic
def _evaluate(permit: Permit) -> Permit:
    """
    Run the attribution engine against the citizen's current address and route
    the permit to the right next state. Snapshot is always saved.
    """
    profile = get_or_create_profile(permit.citizen)
    address = Address.objects.filter(profile=profile).first()
    if not address:
        permit.status = PermitStatus.MANUAL_REVIEW
        permit.attribution_snapshot = {"notes": ["Pas d'adresse principale."]}
        permit.save()
        return permit

    result = resolve_zones(address, permit.permit_type)
    permit.attribution_snapshot = _snapshot_attribution(result)
    permit.source_polygon = result.polygon

    if result.denied:
        permit.status = PermitStatus.REFUSED
        permit.decided_at = timezone.now()
        permit.decision_notes = "Attribution automatique refusée par règle."
        permit.save()
        return permit
    from . import policies as _pol
    commune = address.commune
    if result.requires_manual_review or not _pol.auto_attribution_allowed(commune, permit.permit_type):
        permit.status = PermitStatus.MANUAL_REVIEW
        permit.save()
        return permit

    permit.status = PermitStatus.AWAITING_PAYMENT
    permit.awaiting_payment_at = timezone.now()
    permit.save()
    return _maybe_auto_activate(permit)


# ----- manual review --------------------------------------------------------

@transaction.atomic
def approve_manual_review(permit: Permit, *, agent, notes: str = "") -> Permit:
    if permit.status != PermitStatus.MANUAL_REVIEW:
        raise PermitError(f"Cannot approve a permit in status {permit.status}.")
    permit.status = PermitStatus.AWAITING_PAYMENT
    permit.awaiting_payment_at = timezone.now()
    permit.decided_at = timezone.now()
    permit.decided_by = agent
    permit.decision_notes = notes
    permit.save()
    return _maybe_auto_activate(permit)


def _maybe_auto_activate(permit: Permit) -> Permit:
    """Skip the payment step entirely when the price is zero (e.g. visitor)."""
    if permit.status == PermitStatus.AWAITING_PAYMENT and permit.price_cents == 0:
        return mark_paid(permit)
    return permit


@transaction.atomic
def refuse(permit: Permit, *, agent, notes: str) -> Permit:
    if permit.status not in {PermitStatus.MANUAL_REVIEW, PermitStatus.SUBMITTED}:
        raise PermitError(f"Cannot refuse a permit in status {permit.status}.")
    if not notes:
        raise PermitError("Une note est requise pour refuser.")
    permit.status = PermitStatus.REFUSED
    permit.decided_at = timezone.now()
    permit.decided_by = agent
    permit.decision_notes = notes
    permit.save()
    return permit


# ----- payment & activation -------------------------------------------------

@transaction.atomic
def mark_paid(permit: Permit, *, validity_days: Optional[int] = None) -> Permit:
    """
    Called by the payment app once payment is confirmed (placeholder until
    step 7 — for now triggered by a button). Activates the card and
    materialises ``PermitZone`` rows from the saved attribution snapshot.
    """
    if permit.status != PermitStatus.AWAITING_PAYMENT:
        raise PermitError(f"Cannot mark paid a permit in status {permit.status}.")

    now = timezone.now()
    permit.status = PermitStatus.ACTIVE
    permit.paid_at = now
    permit.activated_at = now
    # Preserve dates already set by the caller (e.g. visitor: Jan 1 → Dec 1).
    if not permit.valid_from:
        from . import policies as _pol
        commune = permit.target_commune or _pol.commune_for(permit.citizen, permit.permit_type)
        days = validity_days or _pol.compute_validity_days(commune, permit.permit_type)
        permit.valid_from = now.date()
        permit.valid_until = permit.valid_from + dt.timedelta(days=days)
    permit.save()

    _materialize_zones(permit)
    return permit


def _materialize_zones(permit: Permit) -> None:
    """
    Create PermitZone rows from the saved attribution snapshot. If zones
    already exist (e.g. agent added them manually for a professional permit),
    this is a no-op — manual choices win.
    """
    snap = permit.attribution_snapshot or {}
    if PermitZone.objects.filter(permit=permit).exists():
        return  # preserve manual zones

    if snap.get("main_zone"):
        PermitZone.objects.create(
            permit=permit,
            zone_code=snap["main_zone"],
            is_main=True,
            source=ZoneSource.POLYGON,
            source_polygon=permit.source_polygon,
        )

    # Map applied_rules by target_zone_code for source_rule attribution.
    rule_by_zone = {
        ar["target_zone_code"]: ar
        for ar in (snap.get("applied_rules") or [])
        if ar.get("action_type") in {RuleAction.ADD_ZONE, RuleAction.REPLACE_MAIN_ZONE}
        and ar.get("target_zone_code")
    }

    for zone_code in snap.get("additional_zones") or []:
        rule_info = rule_by_zone.get(zone_code)
        rule = PolygonRule.objects.filter(pk=rule_info["pk"]).first() if rule_info else None
        PermitZone.objects.create(
            permit=permit,
            zone_code=zone_code,
            is_main=False,
            source=ZoneSource.RULE if rule else ZoneSource.POLYGON,
            source_polygon=permit.source_polygon if not rule else None,
            source_rule=rule,
        )


# ----- citizen-side actions -------------------------------------------------

@transaction.atomic
def cancel(permit: Permit, *, by_user) -> Permit:
    if permit.citizen_id != by_user.pk and not getattr(by_user, "is_back_office", False):
        raise PermissionDenied
    if permit.status not in {PermitStatus.DRAFT, PermitStatus.SUBMITTED,
                             PermitStatus.MANUAL_REVIEW, PermitStatus.AWAITING_PAYMENT}:
        raise PermitError(f"Cannot cancel a permit in status {permit.status}.")
    permit.status = PermitStatus.CANCELLED
    permit.cancelled_at = timezone.now()
    permit.save()
    return permit


# ----- admin / signal-driven transitions -----------------------------------

@transaction.atomic
def suspend_active_permits_for_citizen(citizen, *, reason: str) -> int:
    """
    Bulk-suspend every ACTIVE permit owned by this citizen and cancel any
    in-flight visitor codes attached to them — the spec requires that an
    address change cascades down to every dependent right.
    """
    from .models import VisitorCode, VisitorCodeStatus
    permit_ids = list(
        Permit.objects.filter(
            citizen=citizen, status__in=ACTIVE_STATUSES,
        ).values_list("pk", flat=True)
    )
    if not permit_ids:
        return 0

    now = timezone.now()
    Permit.objects.filter(pk__in=permit_ids).update(
        status=PermitStatus.SUSPENDED,
        suspended_at=now,
        suspension_reason=reason,
        updated_at=now,
    )
    VisitorCode.objects.filter(
        permit__in=permit_ids, status=VisitorCodeStatus.ACTIVE,
    ).update(status=VisitorCodeStatus.CANCELLED, cancelled_at=now)
    return len(permit_ids)


@transaction.atomic
def suspend_active_permits_for_vehicle(vehicle, *, reason: str) -> int:
    qs = Permit.objects.filter(vehicle=vehicle, status__in=ACTIVE_STATUSES)
    now = timezone.now()
    return qs.update(
        status=PermitStatus.SUSPENDED,
        suspended_at=now,
        suspension_reason=reason,
        updated_at=now,
    )


@transaction.atomic
def expire_due(today: Optional[dt.date] = None) -> int:
    today = today or timezone.now().date()
    qs = Permit.objects.filter(
        status=PermitStatus.ACTIVE,
        valid_until__lt=today,
    )
    return qs.update(
        status=PermitStatus.EXPIRED,
        expired_at=timezone.now(),
        updated_at=timezone.now(),
    )


# ----- visitor permits & codes ---------------------------------------------

import secrets
import string

from .models import VisitorCode, VisitorCodeStatus


def _visitor_period(today: Optional[dt.date] = None) -> tuple[dt.date, dt.date]:
    """Return (valid_from, valid_until) for the upcoming/current visitor year."""
    today = today or timezone.now().date()
    sm, sd, em, ed = settings.VISITOR_PERMIT_PERIOD
    end_this_year = dt.date(today.year, em, ed)
    if today > end_this_year:
        start = dt.date(today.year + 1, sm, sd)
        end = dt.date(today.year + 1, em, ed)
    else:
        start = dt.date(today.year, sm, sd)
        end = dt.date(today.year, em, ed)
    return start, end


def _generate_unique_code() -> str:
    """8 char alphanum, dash-separated for readability (XXXX-XXXX)."""
    alphabet = string.ascii_uppercase + string.digits
    for _attempt in range(10):
        raw = "".join(secrets.choice(alphabet) for _ in range(8))
        code = f"{raw[:4]}-{raw[4:]}"
        if not VisitorCode.objects.filter(code=code).exists():
            return code
    raise PermitError("Impossible de générer un code unique.")


@transaction.atomic
def create_visitor_permit(citizen) -> Permit:
    """
    Create + auto-submit + auto-activate the citizen's visitor permit for the
    current period. Requires an active resident permit (per spec). The visitor
    permit inherits the resident permit's zones — so visitors park in the same
    zones as the resident.
    """
    resident = Permit.objects.filter(
        citizen=citizen,
        permit_type=PermitType.RESIDENT,
        status=PermitStatus.ACTIVE,
    ).order_by("-activated_at").first()
    if resident is None:
        raise PermitError("Une carte riverain active est requise pour créer une carte visiteur.")

    from . import policies as _pol
    commune = _pol.commune_for(citizen, PermitType.VISITOR)
    _pol.enforce_card_type_enabled(commune, PermitType.VISITOR)

    valid_from, valid_until = _visitor_period()
    existing = Permit.objects.filter(
        citizen=citizen,
        permit_type=PermitType.VISITOR,
        valid_from=valid_from,
    ).exclude(status__in=[PermitStatus.CANCELLED, PermitStatus.REFUSED]).first()
    if existing:
        return existing

    permit = Permit.objects.create(
        citizen=citizen,
        permit_type=PermitType.VISITOR,
        status=PermitStatus.AWAITING_PAYMENT,
        price_cents=_price_for(PermitType.VISITOR, citizen=citizen, commune=commune),
        submitted_at=timezone.now(),
        awaiting_payment_at=timezone.now(),
        valid_from=valid_from,
        valid_until=valid_until,
        source_polygon=resident.source_polygon,
        attribution_snapshot={"notes": [f"Carte visiteur — zones héritées de la carte riverain #{resident.pk}."]},
    )
    # Copy zones from the resident permit (preserved by mark_paid since they
    # already exist when _materialize_zones runs).
    for rz in resident.zones.all():
        PermitZone.objects.create(
            permit=permit,
            zone_code=rz.zone_code,
            is_main=rz.is_main,
            source=rz.source,
            source_polygon=rz.source_polygon,
            source_rule=rz.source_rule,
        )
    return _maybe_auto_activate(permit)


def _quota_used(permit: Permit) -> int:
    """
    Count *every* code ever generated under this visitor permit, including
    cancelled ones. Cancelling a code does NOT free a slot — that prevents a
    citizen from rotating codes infinitely past the annual cap.
    """
    return VisitorCode.objects.filter(permit=permit).count()


def remaining_visitor_quota(permit: Permit) -> int:
    cfg = PermitConfig.get()
    return max(0, cfg.visitor_codes_per_year - _quota_used(permit))


@transaction.atomic
def generate_visitor_code(
    permit: Permit,
    *,
    plate: str,
    duration_hours: Optional[int] = None,
    valid_from: Optional[dt.datetime] = None,
) -> VisitorCode:
    if permit.permit_type != PermitType.VISITOR:
        raise PermitError("Cette carte n'est pas une carte visiteur.")
    if permit.status != PermitStatus.ACTIVE:
        raise PermitError("La carte visiteur n'est pas active.")
    cfg = PermitConfig.get()
    if remaining_visitor_quota(permit) <= 0:
        raise PermitError(f"Quota annuel atteint ({cfg.visitor_codes_per_year} codes).")

    from apps.vehicles.models import normalize_plate
    plate = normalize_plate(plate)
    duration = duration_hours or cfg.visitor_code_default_hours
    if duration > cfg.visitor_code_max_hours:
        raise PermitError(f"Durée maximale {cfg.visitor_code_max_hours} h.")
    if duration < 1:
        raise PermitError("Durée minimale 1 h.")
    start = valid_from or timezone.now()
    end = start + dt.timedelta(hours=duration)

    return VisitorCode.objects.create(
        permit=permit,
        code=_generate_unique_code(),
        plate=plate,
        valid_from=start,
        valid_until=end,
    )


@transaction.atomic
def cancel_visitor_code(code: VisitorCode, *, by_user) -> VisitorCode:
    if code.permit.citizen_id != by_user.pk:
        raise PermissionDenied
    if code.status != VisitorCodeStatus.ACTIVE:
        raise PermitError("Code déjà annulé.")
    code.status = VisitorCodeStatus.CANCELLED
    code.cancelled_at = timezone.now()
    code.save()
    return code


# ----- professional permits -------------------------------------------------

@transaction.atomic
def create_professional_permit(citizen, vehicle, company, target_commune) -> Permit:
    """
    Professional permit grants access to ALL polygons of one chosen commune.
    Citizen picks the commune at creation; an agent reviews + approves. The
    PermitZone rows are pre-materialised at creation so the agent (and the
    citizen) sees the exact granted scope.
    """
    if vehicle is None or vehicle.owner_id != citizen.pk:
        raise PermissionDenied("Véhicule invalide.")
    if company is None or company.owner_id != citizen.pk:
        raise PermissionDenied("Entreprise invalide.")
    if target_commune is None:
        raise PermitError("Commune cible requise.")

    from . import policies as _pol
    _pol.enforce_card_type_enabled(target_commune, PermitType.PROFESSIONAL)
    _pol.enforce_cumul_resident_pro(citizen, PermitType.PROFESSIONAL)
    _pol.enforce_max_active_pro_per_citizen(citizen)
    _pol.enforce_max_active_per_citizen(citizen, target_commune, PermitType.PROFESSIONAL)

    polygons = list(target_commune.gis_polygons.filter(version__is_active=True))
    if not polygons:
        raise PermitError(
            f"Aucune zone GIS active pour {target_commune.name_fr} — "
            "import requis avant de créer une carte professionnelle."
        )

    permit = Permit.objects.create(
        citizen=citizen,
        vehicle=vehicle,
        company=company,
        target_commune=target_commune,
        permit_type=PermitType.PROFESSIONAL,
        status=PermitStatus.MANUAL_REVIEW,  # agent reviews legitimacy
        price_cents=_price_for(PermitType.PROFESSIONAL, citizen=citizen, commune=target_commune),
        submitted_at=timezone.now(),
        attribution_snapshot={
            "notes": [
                f"Carte professionnelle — {len(polygons)} zone(s) de {target_commune.name_fr} "
                "attribuées automatiquement (l'agent peut affiner)."
            ],
        },
    )
    # Materialise zones immediately so the scope is visible from both sides.
    for poly in polygons:
        PermitZone.objects.create(
            permit=permit,
            zone_code=poly.zonecode,
            is_main=False,
            source=ZoneSource.POLYGON,
            source_polygon=poly,
        )
    return permit


@transaction.atomic
def add_manual_zone(permit: Permit, *, zone_code: str, is_main: bool = False) -> PermitZone:
    """Agent-only: add an explicit zone to a permit (used during pro review)."""
    zone_code = zone_code.strip()
    if not zone_code:
        raise PermitError("Zonecode requis.")
    if PermitZone.objects.filter(permit=permit, zone_code=zone_code).exists():
        raise PermitError("Zone déjà attribuée.")
    if is_main and PermitZone.objects.filter(permit=permit, is_main=True).exists():
        raise PermitError("Une zone principale existe déjà.")
    return PermitZone.objects.create(
        permit=permit, zone_code=zone_code, is_main=is_main, source=ZoneSource.MANUAL,
    )


@transaction.atomic
def remove_zone(zone: PermitZone) -> None:
    """Agent-only zone removal — works on any source (the agent owns the final scope)."""
    zone.delete()


# Kept as alias for backwards-compat in older callers/tests.
remove_manual_zone = remove_zone


@transaction.atomic
def approve_professional(permit: Permit, *, agent, notes: str = "") -> Permit:
    """Approve a professional permit after the agent has added zones."""
    if permit.status != PermitStatus.MANUAL_REVIEW:
        raise PermitError(f"Cannot approve in status {permit.status}.")
    if not PermitZone.objects.filter(permit=permit).exists():
        raise PermitError("Au moins une zone doit être attribuée avant approbation.")
    permit.status = PermitStatus.AWAITING_PAYMENT
    permit.awaiting_payment_at = timezone.now()
    permit.decided_at = timezone.now()
    permit.decided_by = agent
    permit.decision_notes = notes
    permit.save()
    return _maybe_auto_activate(permit)


# ----- public lookups (consumed by the REST API) ---------------------------

def is_plate_authorized(
    plate: str,
    *,
    zone: Optional[str] = None,
    at: Optional[dt.datetime] = None,
) -> Optional[Permit]:
    """
    Vérifie si la plaque ``plate`` est autorisée à se garer.

    Renvoie le ``Permit`` couvrant la plaque (le plus récemment activé en cas
    d'overlap) si une carte ACTIVE valide à ``at`` existe, sinon ``None``.

    Trois pistes d'autorisation sont testées :

    1. Une carte ``RESIDENT`` ou ``PROFESSIONAL`` ACTIVE attachée à un véhicule
       non archivé portant exactement cette plaque.
    2. Un ``VisitorCode`` actif émis sous une carte ``VISITOR`` ACTIVE — ces
       codes ne sont pas liés au véhicule du citoyen mais à une plaque tierce
       saisie au moment de la génération.

    Si ``zone`` est fournie, la zone doit faire partie des zones autorisées
    par le permit (PermitZone.zone_code).
    """
    from apps.vehicles.models import Vehicle, normalize_plate
    from .models import VisitorCode, VisitorCodeStatus

    plate = normalize_plate(plate or "")
    if not plate:
        return None

    moment = at or timezone.now()
    today = timezone.localdate(moment) if timezone.is_aware(moment) else moment.date()

    # --- 1. Carte directement liée à un véhicule (RESIDENT / PROFESSIONAL) ---
    direct_qs = (
        Permit.objects
        .filter(
            status=PermitStatus.ACTIVE,
            vehicle__plate=plate,
            vehicle__archived_at__isnull=True,
            valid_from__lte=today,
            valid_until__gte=today,
        )
        .select_related("vehicle", "citizen", "target_commune")
        .prefetch_related("zones")
        .order_by("-activated_at")
    )
    if zone:
        direct_qs = direct_qs.filter(zones__zone_code=zone)
    direct = direct_qs.first()
    if direct:
        return direct

    # --- 2. Code visiteur actif émis sous une carte VISITOR active -----------
    code_qs = (
        VisitorCode.objects
        .filter(
            plate=plate,
            status=VisitorCodeStatus.ACTIVE,
            valid_from__lte=moment,
            valid_until__gte=moment,
            permit__status=PermitStatus.ACTIVE,
        )
        .select_related("permit", "permit__citizen")
        .prefetch_related("permit__zones")
        .order_by("-valid_from")
    )
    if zone:
        code_qs = code_qs.filter(permit__zones__zone_code=zone)
    code = code_qs.first()
    if code:
        return code.permit

    return None
