"""
GIS-side services: geocoding and polygon resolution.

Geocoding hits Nominatim (OpenStreetMap) by default — public, free, rate-limited
to ~1 req/s, requires a real User-Agent. We cache results in-process for the
lifetime of the worker; for production, swap for Brussels' UrbIS or a local
BeST extract by replacing :data:`GEOCODER`.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import requests
from django.conf import settings
from django.contrib.gis.geos import Point

from apps.citizens.models import Address
from apps.gis_data.models import GISPolygon, GISSourceVersion

log = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_TIMEOUT = 10  # seconds
NOMINATIM_USER_AGENT = (
    "Parking.Belgium/0.1 (academic project; contact: sofianeezzahti@gmail.com)"
)

# Process-local cache keyed by the (street, number, postal_code, commune) tuple.
_GEOCODE_CACHE: dict[tuple, Optional[Point]] = {}


@dataclass(frozen=True)
class GeocodeResult:
    point: Point
    source: str  # "nominatim" | "commune_centroid"


def _format_query(address: Address) -> str:
    parts = [
        f"{address.street} {address.number}",
        address.postal_code,
        address.commune.name_fr if address.commune_id else "",
        address.country or "BE",
    ]
    return ", ".join(p for p in parts if p)


def _nominatim_search(q: str) -> Optional[Point]:
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": q, "format": "json", "limit": 1, "countrycodes": "be"},
            headers={"User-Agent": NOMINATIM_USER_AGENT},
            timeout=NOMINATIM_TIMEOUT,
        )
        resp.raise_for_status()
        results = resp.json()
        if not results:
            return None
        return Point(float(results[0]["lon"]), float(results[0]["lat"]), srid=4326)
    except (requests.RequestException, ValueError, KeyError) as exc:
        log.warning("Nominatim lookup failed for %r: %s", q, exc)
        return None


def _commune_centroid_fallback(address: Address) -> Optional[Point]:
    """If geocoding fails, fall back to the centroid of the commune's polygons."""
    if not address.commune_id:
        return None
    qs = GISPolygon.objects.filter(version__is_active=True, commune=address.commune)
    if not qs.exists():
        return None
    # Aggregate centroid: union geometries, then take centroid in WGS84.
    union = qs.first().geometry
    for p in qs[1:]:
        union = union.union(p.geometry)
    centroid = union.centroid
    centroid.transform(4326)
    return centroid


def geocode_address(address: Address, *, use_cache: bool = True) -> Optional[GeocodeResult]:
    """
    Resolve an Address to a WGS84 Point. Tries Nominatim, falls back to the
    commune centroid. Returns ``None`` only if both fail (e.g. address has no
    commune linked).
    """
    key = (address.street, address.number, address.postal_code, address.commune_id)
    if use_cache and key in _GEOCODE_CACHE:
        cached = _GEOCODE_CACHE[key]
        return GeocodeResult(point=cached, source="cache") if cached else None

    point = _nominatim_search(_format_query(address))
    if point is not None:
        if use_cache:
            _GEOCODE_CACHE[key] = point
        return GeocodeResult(point=point, source="nominatim")

    fallback = _commune_centroid_fallback(address)
    if fallback is not None:
        if use_cache:
            _GEOCODE_CACHE[key] = fallback
        return GeocodeResult(point=fallback, source="commune_centroid")

    return None


def find_polygon_for_point(point: Point, *, version: GISSourceVersion | None = None) -> Optional[GISPolygon]:
    """
    Spatial query: which active GIS polygon contains this point. The point is
    automatically reprojected to the GIS SRID before the lookup.
    """
    if version is None:
        version = GISSourceVersion.objects.filter(is_active=True).first()
    if not version:
        return None
    if point.srid != version.srid:
        point = point.clone()
        point.transform(version.srid)
    return (
        GISPolygon.objects
        .filter(version=version, geometry__contains=point)
        .select_related("commune", "version")
        .first()
    )
