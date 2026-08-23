"""Public-facing GIS views: interactive map and GeoJSON feed."""
import json

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render

from apps.core.models import Commune

from .models import GISPolygon, GISSourceVersion

# Géométries connues comme parasites/invalides dans les shapefiles sources,
# à exclure de l'affichage sans toucher aux données importées (ex : polygone
# résiduel hors zone couvrant toute la carte).
EXCLUDED_POLYGON_IDS = {4000}


def map_page(request: HttpRequest) -> HttpResponse:
    communes = list(
        Commune.objects.all().order_by("name_fr")
        .values("niscode", "name_fr", "name_nl", "name_en")
    )
    return render(
        request,
        "gis/map.html",
        {"communes": communes},
    )


def polygons_geojson(request: HttpRequest) -> JsonResponse:
    """
    Active GIS polygons as a GeoJSON FeatureCollection in WGS84. Optional
    ``?commune=<niscode>`` filter narrows the response.
    """
    version = GISSourceVersion.objects.filter(is_active=True).first()
    if not version:
        return JsonResponse({"type": "FeatureCollection", "features": []})

    qs = (
        GISPolygon.objects.filter(version=version)
        .exclude(pk__in=EXCLUDED_POLYGON_IDS)
        .select_related("commune")
    )
    commune_nis = request.GET.get("commune")
    if commune_nis:
        qs = qs.filter(commune__niscode=commune_nis)

    features = []
    for p in qs:
        # Aire calculée depuis la géométrie source (Lambert 72, SRID 31370 —
        # déjà en mètres) avant reprojection WGS84, qui la fausserait (degrés).
        area_m2 = p.geometry.area
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
                "area": area_m2,
            },
        })
    return JsonResponse({"type": "FeatureCollection", "features": features})
