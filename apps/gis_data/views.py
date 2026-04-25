"""Public-facing GIS views: interactive map and GeoJSON feed."""
import json

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render

from apps.core.models import Commune

from .models import GISPolygon, GISSourceVersion


def map_page(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "gis/map.html",
        {"communes": Commune.objects.all()},
    )


def polygons_geojson(request: HttpRequest) -> JsonResponse:
    """
    Active GIS polygons as a GeoJSON FeatureCollection in WGS84. Optional
    ``?commune=<niscode>`` filter narrows the response.
    """
    version = GISSourceVersion.objects.filter(is_active=True).first()
    if not version:
        return JsonResponse({"type": "FeatureCollection", "features": []})

    qs = GISPolygon.objects.filter(version=version).select_related("commune")
    commune_nis = request.GET.get("commune")
    if commune_nis:
        qs = qs.filter(commune__niscode=commune_nis)

    features = []
    for p in qs:
        geom = p.geometry.clone()
        geom.transform(4326)
        features.append({
            "type": "Feature",
            "id": p.pk,
            "geometry": json.loads(geom.geojson),
            "properties": {
                "zonecode": p.zonecode,
                "niscode": p.niscode,
                "commune": p.commune.name_fr if p.commune_id else None,
                "type": p.type,
                "name_fr": p.name_fr,
                "name_nl": p.name_nl,
                "name_en": p.name_en,
                "layer": p.layer,
            },
        })
    return JsonResponse({"type": "FeatureCollection", "features": features})
