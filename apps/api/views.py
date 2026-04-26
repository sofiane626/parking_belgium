"""
Vues DRF de l'API publique ``/api/v1/``.

Trois endpoints en lecture, authentifiés par Token (les agents/scan-cars
reçoivent leur token via le back-office). La logique métier vit dans les
``services`` : les vues se contentent de parser la requête et de sérialiser.
"""
from __future__ import annotations

import datetime as dt

from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.services import AuditAction, hash_plate, log as audit_log
from apps.core.models import Commune
from apps.gis_data.models import GISPolygon
from apps.permits.services import is_plate_authorized

from .serializers import CheckRightSerializer, CommuneSerializer, ZoneSerializer
from .throttling import CheckRightThrottle


def _parse_at(raw: str | None) -> dt.datetime | None:
    """
    Accepte ISO 8601 (``2026-04-26T14:30:00+02:00``) ou date simple
    (``2026-04-26``). Renvoie un datetime aware (UTC pour les dates nues).
    """
    if not raw:
        return None
    parsed = timezone.datetime.fromisoformat(raw) if "T" in raw else None
    if parsed is None:
        try:
            d = dt.date.fromisoformat(raw)
        except ValueError as exc:
            raise ValidationError({"at": "Format invalide (ISO 8601 attendu)."}) from exc
        return timezone.make_aware(dt.datetime.combine(d, dt.time(12, 0)))
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


class CheckRightView(APIView):
    """
    ``GET /api/v1/check-right/?plate=1-AAA-111&zone=ZONE-A&at=2026-04-26T14:30``

    - ``plate`` (requis) : plaque normalisée (la normalisation est faite côté
      service, l'appelant peut envoyer espaces / minuscules sans souci).
    - ``zone`` (optionnel) : ``zonecode`` GIS — si fourni, la carte doit couvrir
      explicitement cette zone.
    - ``at`` (optionnel) : moment de vérification, défaut = maintenant.

    Réponse :
    ```json
    {
      "authorized": true,
      "plate": "1-AAA-111",
      "zone": "ZONE-A",
      "checked_at": "2026-04-26T14:30:00+02:00",
      "permit": {
        "id": 42, "type": "resident",
        "valid_from": "2026-01-15", "valid_until": "2027-01-15",
        "zones": ["ZONE-A", "ZONE-B"]
      }
    }
    ```
    """

    throttle_classes = [CheckRightThrottle]

    def get(self, request):
        plate = request.query_params.get("plate", "").strip()
        if not plate:
            raise ValidationError({"plate": "Paramètre requis."})

        zone = request.query_params.get("zone") or None
        at = _parse_at(request.query_params.get("at"))

        permit = is_plate_authorized(plate, zone=zone, at=at)
        payload = {
            "authorized": permit is not None,
            "plate": plate.upper(),
            "zone": zone,
            "checked_at": at or timezone.now(),
            "permit": permit,
        }
        audit_log(
            AuditAction.API_CHECK_RIGHT,
            request=request,
            payload={"context": {
                "plate_hash": hash_plate(plate.upper()),
                "zone": zone,
                "authorized": permit is not None,
                "permit_id": permit.pk if permit else None,
            }},
        )
        return Response(CheckRightSerializer(payload).data)


class CommuneListView(ListAPIView):
    """``GET /api/v1/communes/`` — liste des 19 communes."""
    queryset = Commune.objects.all().order_by("name_fr")
    serializer_class = CommuneSerializer
    pagination_class = None


class ZoneListView(ListAPIView):
    """
    ``GET /api/v1/zones/?commune=21015`` — liste des zones (zonecode +
    niscode) de la version GIS active. Filtrable par ``commune`` (niscode).

    Le même ``zonecode`` peut couvrir plusieurs polygones non-contigus dans
    le shapefile : la réponse les déduplique sur (zonecode, niscode).
    """
    serializer_class = ZoneSerializer
    pagination_class = None

    def get_queryset(self):
        qs = (
            GISPolygon.objects
            .filter(version__is_active=True)
            .values("zonecode", "niscode")
            .distinct()
            .order_by("niscode", "zonecode")
        )
        commune = self.request.query_params.get("commune")
        if commune:
            qs = qs.filter(niscode=commune)
        return qs
