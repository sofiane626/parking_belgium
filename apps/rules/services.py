"""
Attribution engine.

Pure function from ``(address, permit_type)`` to an :class:`AttributionResult`.
Steps:

1. Geocode the address (or use its cached ``location``).
2. Find the active GIS polygon containing the resulting point.
3. Read the polygon's ``zonecode`` as the *main* zone.
4. Apply matching :class:`PolygonRule` rows in priority order:
   - ``ADD_ZONE`` appends to ``additional_zones``
   - ``REPLACE_MAIN_ZONE`` swaps ``main_zone``
   - ``MANUAL_REVIEW`` flags the result
   - ``DENY`` short-circuits the whole attribution

The result is consumed by the permits app to materialise ``PermitZone`` rows
with full provenance (polygon vs rule).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from django.utils import timezone

from apps.citizens.models import Address
from apps.gis_data.models import GISPolygon
from apps.gis_data.services import find_polygon_for_point, geocode_address

from .models import PolygonRule, RuleAction


@dataclass
class AttributionResult:
    main_zone: Optional[str] = None
    additional_zones: list[str] = field(default_factory=list)
    requires_manual_review: bool = False
    denied: bool = False
    polygon: Optional[GISPolygon] = None
    applied_rules: list[PolygonRule] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def all_zones(self) -> list[str]:
        seen = []
        if self.main_zone and not self.denied:
            seen.append(self.main_zone)
        for z in self.additional_zones:
            if z not in seen:
                seen.append(z)
        return seen


def _active_rules(polygon: GISPolygon, permit_type: str) -> list[PolygonRule]:
    today = timezone.now().date()
    qs = (
        PolygonRule.objects
        .filter(polygon=polygon, permit_type=permit_type, is_active=True)
        .order_by("priority", "id")
    )
    return [r for r in qs if r.is_currently_valid(today)]


def resolve_zones(address: Address, permit_type: str) -> AttributionResult:
    result = AttributionResult()

    if not address.location:
        geo = geocode_address(address)
        if geo is None:
            result.notes.append("Géocodage impossible.")
            result.requires_manual_review = True
            return result
        # Persist the geocoded point so we don't re-call the API every time.
        address.location = geo.point
        address.save(update_fields=["location", "updated_at"])
        result.notes.append(f"Géocodage via {geo.source}.")

    polygon = find_polygon_for_point(address.location)
    if polygon is None:
        result.notes.append("Aucun polygone GIS ne contient cette adresse.")
        result.requires_manual_review = True
        return result

    result.polygon = polygon
    result.main_zone = polygon.zonecode
    main_zone_overridden = False  # first REPLACE_MAIN_ZONE wins (priority order)

    for rule in _active_rules(polygon, permit_type):
        result.applied_rules.append(rule)
        if rule.action_type == RuleAction.DENY:
            result.denied = True
            result.main_zone = None
            result.additional_zones = []
            return result
        if rule.action_type == RuleAction.MANUAL_REVIEW:
            result.requires_manual_review = True
            continue
        if rule.action_type == RuleAction.REPLACE_MAIN_ZONE:
            if rule.target_zone_code and not main_zone_overridden:
                result.main_zone = rule.target_zone_code
                main_zone_overridden = True
            continue
        if rule.action_type == RuleAction.ADD_ZONE:
            if rule.target_zone_code and rule.target_zone_code not in result.additional_zones:
                result.additional_zones.append(rule.target_zone_code)
            continue

    return result
