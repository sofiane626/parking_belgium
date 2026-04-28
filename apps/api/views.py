"""
Vues DRF de l'API publique ``/api/v1/``.

Trois endpoints en lecture, authentifiés par Token (les agents/scan-cars
reçoivent leur token via le back-office). La logique métier vit dans les
``services`` : les vues se contentent de parser la requête et de sérialiser.
"""
from __future__ import annotations

import datetime as dt

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework.permissions import IsAuthenticated

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


class PermitEligibilityView(APIView):
    """
    ``GET /api/v1/permits/eligibility/<vehicle_pk>/`` — pré-calcul des
    informations qui seront utilisées si le citoyen demande une carte
    riverain pour ce véhicule. Lecture seule, **pas** de side-effect — sert
    à alimenter le wizard React avant de créer la carte.

    Réponse :
    ```json
    {
      "vehicle": {"plate": "...", "brand": "...", "model": "..."},
      "address": {"street": "...", "commune": "Schaerbeek"},
      "main_zone": "ZONE-A",
      "additional_zones": ["ZONE-B"],
      "polygon_id": 42,
      "requires_manual_review": false,
      "denied": false,
      "price_cents": 1500,
      "validity_days": 365,
      "notes": [...]
    }
    ```
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, vehicle_pk: int):
        from apps.citizens.models import Address
        from apps.citizens.services import get_or_create_profile
        from apps.permits.models import PermitType
        from apps.permits.policies import (
            commune_for, compute_price, compute_validity_days,
        )
        from apps.rules.services import resolve_zones
        from apps.vehicles.models import Vehicle

        vehicle = get_object_or_404(Vehicle, pk=vehicle_pk, owner=request.user)
        if vehicle.is_archived:
            raise ValidationError({"vehicle": "Véhicule archivé."})

        profile = get_or_create_profile(request.user)
        address = Address.objects.filter(profile=profile).first()
        if address is None:
            raise ValidationError({"address": "Aucune adresse principale enregistrée."})

        commune = commune_for(request.user, PermitType.RESIDENT)
        result = resolve_zones(address, PermitType.RESIDENT)
        price = compute_price(request.user, PermitType.RESIDENT, commune=commune)
        days = compute_validity_days(commune, PermitType.RESIDENT)

        return Response({
            "vehicle": {
                "id": vehicle.pk,
                "plate": vehicle.plate,
                "brand": vehicle.brand,
                "model": vehicle.model,
                "color": vehicle.color,
            },
            "address": {
                "street": address.street,
                "number": address.number,
                "box": address.box,
                "postal_code": address.postal_code,
                "commune": address.commune.name_fr if address.commune else None,
                "commune_niscode": address.commune.niscode if address.commune else None,
            },
            "main_zone": result.main_zone,
            "additional_zones": list(result.additional_zones),
            "polygon_id": result.polygon.pk if result.polygon else None,
            "polygon_zonecode": result.polygon.zonecode if result.polygon else None,
            "requires_manual_review": result.requires_manual_review,
            "denied": result.denied,
            "price_cents": price,
            "validity_days": days,
            "notes": list(result.notes),
        })


class PermitSubmitView(APIView):
    """
    ``POST /api/v1/permits/submit/<vehicle_pk>/`` — crée le draft puis le
    soumet. Renvoie le ``permit_id`` et le statut résultant pour que le
    wizard React puisse rediriger vers le bon écran (paiement / revue
    manuelle / refus).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, vehicle_pk: int):
        from apps.permits.models import PermitType
        from apps.permits.policies import PolicyError
        from apps.permits.services import (
            PermitError, create_draft, submit_application,
        )
        from apps.vehicles.models import Vehicle

        vehicle = get_object_or_404(Vehicle, pk=vehicle_pk, owner=request.user)

        try:
            draft = create_draft(request.user, vehicle, PermitType.RESIDENT)
            permit = submit_application(draft)
        except (PermitError, PolicyError) as exc:
            raise ValidationError({"detail": str(exc)})

        return Response({
            "permit_id": permit.pk,
            "status": permit.status,
            "price_cents": permit.price_cents,
            "next_step": _next_step_for(permit.status),
        }, status=status.HTTP_201_CREATED)


def _next_step_for(permit_status: str) -> str:
    """Mappe le statut du permit vers la prochaine action côté wizard."""
    return {
        "awaiting_payment": "payment",
        "active": "success",       # auto-activé (gratuit)
        "manual_review": "review", # bloqué côté agent
        "refused": "refused",
    }.get(permit_status, "review")


# ----- audit log datatable (consumed by the React audit page) --------------

class AuditLogListView(APIView):
    """
    ``GET /api/v1/audit/`` — liste paginée et filtrée des entrées d'audit.

    Réservé aux admins/super-admins (mêmes garde-fous que la page back-office
    actuelle). Filtres :
    - ``action`` : code d'action exact
    - ``severity`` : info / notice / warning / critical
    - ``target_type`` : permit / payment / user / vehicle / etc.
    - ``actor`` : recherche partielle sur le username
    - ``date_from`` / ``date_to`` : ISO date (YYYY-MM-DD)
    - ``q`` : recherche libre dans target_label + ip
    - ``page_size`` : 1-200, défaut 50
    - ``cursor`` : id de la dernière ligne reçue, pour scroll infini

    Réponse :
    ```json
    {
      "items": [...],
      "next_cursor": 12345,
      "total_filtered": 8421,
      "counts_by_severity": {"info": 7800, "notice": 500, ...}
    }
    ```
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.accounts.services import can_manage_users
        from apps.audit.models import AuditAction, AuditLog, AuditSeverity
        from django.core.exceptions import PermissionDenied

        if not can_manage_users(request.user):
            raise PermissionDenied

        qs = AuditLog.objects.select_related("actor")

        action = request.query_params.get("action")
        if action:
            qs = qs.filter(action=action)

        severity = request.query_params.get("severity")
        if severity:
            qs = qs.filter(severity=severity)

        target_type = request.query_params.get("target_type")
        if target_type:
            qs = qs.filter(target_type=target_type)

        actor = request.query_params.get("actor", "").strip()
        if actor:
            qs = qs.filter(actor__username__icontains=actor)

        date_from = request.query_params.get("date_from")
        if date_from:
            try:
                qs = qs.filter(created_at__date__gte=dt.date.fromisoformat(date_from))
            except ValueError:
                raise ValidationError({"date_from": "Format AAAA-MM-JJ requis."})

        date_to = request.query_params.get("date_to")
        if date_to:
            try:
                qs = qs.filter(created_at__date__lte=dt.date.fromisoformat(date_to))
            except ValueError:
                raise ValidationError({"date_to": "Format AAAA-MM-JJ requis."})

        q = request.query_params.get("q", "").strip()
        if q:
            from django.db.models import Q
            qs = qs.filter(Q(target_label__icontains=q) | Q(ip__icontains=q))

        # Comptage par sévérité (sur le QS filtré, sans pagination) — utile pour
        # afficher des chips "X infos / Y warnings" dans la barre de filtres.
        from django.db.models import Count
        sev_rows = qs.values("severity").annotate(n=Count("id"))
        counts_by_severity = {row["severity"]: row["n"] for row in sev_rows}
        total_filtered = sum(counts_by_severity.values())

        # Cursor pagination — strictement décroissant sur l'id (qui suit l'ordre
        # de création). Plus simple que offset, pas de saut quand on insère.
        cursor = request.query_params.get("cursor")
        if cursor:
            try:
                qs = qs.filter(pk__lt=int(cursor))
            except ValueError:
                raise ValidationError({"cursor": "Entier requis."})

        try:
            page_size = max(1, min(200, int(request.query_params.get("page_size", 50))))
        except ValueError:
            page_size = 50

        page = list(qs.order_by("-id")[:page_size])
        next_cursor = page[-1].pk if len(page) == page_size else None

        items = [{
            "id": e.id,
            "created_at": e.created_at.isoformat(),
            "action": e.action,
            "severity": e.severity,
            "actor": e.actor.username if e.actor_id else None,
            "actor_role": e.actor_role,
            "target_type": e.target_type,
            "target_id": e.target_id,
            "target_label": e.target_label,
            "ip": e.ip,
            "payload": e.payload,
        } for e in page]

        # Liste des choix possibles renvoyée pour alimenter les selects côté UI.
        meta = {
            "actions": [{"value": v, "label": l} for v, l in AuditAction.choices],
            "severities": [{"value": v, "label": l} for v, l in AuditSeverity.choices],
            "target_types": list(
                AuditLog.objects.exclude(target_type="")
                .order_by("target_type").values_list("target_type", flat=True).distinct()
            ),
        }

        return Response({
            "items": items,
            "next_cursor": next_cursor,
            "total_filtered": total_filtered,
            "counts_by_severity": counts_by_severity,
            "meta": meta,
        })
