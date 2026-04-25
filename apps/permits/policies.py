"""
Policy resolution service.

The single entry-point for "what's the price / can this card be issued / how
long is it valid" — all conditions live in :class:`CommunePermitPolicy`
(per-commune × per-type × time-versioned) with :class:`PermitConfig` as the
global fallback. Views and other services should never read prices directly
from settings — always go through here.
"""
from __future__ import annotations

from typing import Optional

from apps.citizens.models import Address
from apps.core.models import Commune

from .models import (
    ACTIVE_STATUSES,
    IN_PROGRESS_STATUSES,
    Permit,
    PermitConfig,
    PermitStatus,
    PermitType,
    CommunePermitPolicy,
)


class PolicyError(Exception):
    """
    Raised when a business policy (limit, disabled type, cumul, …) blocks an
    action. Views catch this and surface ``str(exc)`` to the user — never let
    it bubble up as a 403/500.
    """


# ----- commune lookup helpers ----------------------------------------------

def _resident_commune(citizen) -> Optional[Commune]:
    addr = Address.objects.filter(profile__user=citizen).select_related("commune").first()
    return addr.commune if addr else None


def commune_for(citizen, permit_type: str, *, target_commune: Commune | None = None) -> Optional[Commune]:
    """
    Pick the commune that owns the policy decision for this permit:
    professional uses the explicit target, everything else uses the citizen's
    home address commune.
    """
    if permit_type == PermitType.PROFESSIONAL:
        return target_commune
    return _resident_commune(citizen)


def get_policy(commune: Commune, permit_type: str) -> Optional[CommunePermitPolicy]:
    if commune is None:
        return None
    return CommunePermitPolicy.active_for(commune, permit_type)


# ----- pricing --------------------------------------------------------------

def _resident_rank(citizen) -> int:
    """Position (1-indexed) of the next resident permit among existing ones."""
    existing = Permit.objects.filter(
        citizen=citizen,
        permit_type=PermitType.RESIDENT,
        status__in=ACTIVE_STATUSES | IN_PROGRESS_STATUSES,
    ).count()
    return existing + 1


def compute_price(citizen, permit_type: str, *, commune: Commune | None = None) -> int:
    """
    Resolve the effective policy and compute the price. Falls back to the
    global :class:`PermitConfig` defaults when no policy exists for this
    commune (e.g. communes not in the seeded set).
    """
    policy = get_policy(commune, permit_type) if commune else None
    rank = _resident_rank(citizen) if permit_type == PermitType.RESIDENT else 1
    if policy:
        return policy.compute_price(rank=rank)
    return PermitConfig.get().price_for(permit_type)


def compute_validity_days(commune: Commune | None, permit_type: str) -> int:
    policy = get_policy(commune, permit_type) if commune else None
    if policy:
        return policy.validity_days
    return PermitConfig.get().permit_default_validity_days


def auto_attribution_allowed(commune: Commune | None, permit_type: str) -> bool:
    """If False, requests must always go to manual review."""
    policy = get_policy(commune, permit_type) if commune else None
    return policy.auto_attribution if policy else True


# ----- enforcement ----------------------------------------------------------

def enforce_card_type_enabled(commune: Commune | None, permit_type: str) -> None:
    if commune is None:
        # No commune resolved → can't validate type availability.
        # We accept (fall back to global defaults) but mark notes upstream.
        return
    policy = get_policy(commune, permit_type)
    if policy is None:
        raise PolicyError(
            f"Le type de carte « {permit_type} » n'est pas configuré pour {commune.name_fr}."
        )
    if not policy.is_enabled:
        raise PolicyError(
            f"Le type de carte « {permit_type} » n'est plus proposé à {commune.name_fr}."
        )


def enforce_max_active_per_citizen(citizen, commune: Commune | None, permit_type: str) -> None:
    """Per-policy cap on how many ACTIVE permits a citizen may hold for this (commune, type)."""
    policy = get_policy(commune, permit_type) if commune else None
    if not policy or policy.max_active_per_citizen is None:
        return
    qs = Permit.objects.filter(citizen=citizen, permit_type=permit_type, status=PermitStatus.ACTIVE)
    if commune:
        if permit_type == PermitType.PROFESSIONAL:
            qs = qs.filter(target_commune=commune)
        else:
            # Resident: same commune via citizen address (best-effort).
            home = _resident_commune(citizen)
            qs = qs.filter()  # don't add stricter filter here
    if qs.count() >= policy.max_active_per_citizen:
        raise PolicyError(
            f"Limite atteinte : {policy.max_active_per_citizen} carte(s) {permit_type} actives à {commune.name_fr}."
        )


def enforce_max_vehicles_per_citizen(citizen) -> None:
    """
    Global cap on the number of *active* vehicles a citizen may register —
    archived vehicles don't count (the citizen archived them precisely to free
    a slot).
    """
    cfg = PermitConfig.get()
    cap = cfg.max_vehicles_per_citizen
    active_count = citizen.vehicles.filter(archived_at__isnull=True).count()
    if cap and active_count >= cap:
        raise PolicyError(
            f"Limite atteinte : {cap} véhicule(s) maximum par citoyen."
        )


def enforce_max_companies_per_citizen(citizen) -> None:
    cfg = PermitConfig.get()
    cap = cfg.max_companies_per_citizen
    if cap and citizen.companies.count() >= cap:
        raise PolicyError(
            f"Limite atteinte : {cap} entreprise(s) maximum par citoyen."
        )


def enforce_max_active_pro_per_citizen(citizen) -> None:
    cfg = PermitConfig.get()
    cap = cfg.max_active_pro_per_citizen
    if cap is None:
        return
    n = Permit.objects.filter(
        citizen=citizen, permit_type=PermitType.PROFESSIONAL,
        status__in=ACTIVE_STATUSES | IN_PROGRESS_STATUSES,
    ).count()
    if n >= cap:
        raise PolicyError(
            f"Limite atteinte : {cap} carte(s) professionnelle(s) actives ou en cours."
        )


def enforce_cumul_resident_pro(citizen, permit_type: str) -> None:
    cfg = PermitConfig.get()
    if cfg.allow_cumul_resident_pro:
        return
    other = PermitType.PROFESSIONAL if permit_type == PermitType.RESIDENT else PermitType.RESIDENT
    has_other = Permit.objects.filter(
        citizen=citizen, permit_type=other, status=PermitStatus.ACTIVE,
    ).exists()
    if has_other:
        raise PolicyError(
            "Le cumul carte riverain + professionnelle est désactivé."
        )
