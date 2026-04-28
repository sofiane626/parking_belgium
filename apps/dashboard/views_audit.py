"""
Consultation et export du journal d'audit côté back-office.

Accessible aux admin/super_admin (mêmes garde-fous que la gestion users).
"""
from __future__ import annotations

import csv
import datetime as dt

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from apps.accounts.services import can_manage_users
from apps.audit.models import AuditAction, AuditLog, AuditSeverity


def _ensure_admin(request: HttpRequest) -> None:
    if not can_manage_users(request.user):
        raise PermissionDenied


def _parse_date(raw: str | None) -> dt.date | None:
    if not raw:
        return None
    try:
        return dt.date.fromisoformat(raw)
    except ValueError:
        return None


def _filtered_qs(request: HttpRequest):
    qs = AuditLog.objects.select_related("actor")

    action = request.GET.get("action", "").strip()
    if action:
        qs = qs.filter(action=action)

    severity = request.GET.get("severity", "").strip()
    if severity:
        qs = qs.filter(severity=severity)

    target_type = request.GET.get("target_type", "").strip()
    if target_type:
        qs = qs.filter(target_type=target_type)

    actor_q = request.GET.get("actor", "").strip()
    if actor_q:
        qs = qs.filter(actor__username__icontains=actor_q)

    date_from = _parse_date(request.GET.get("date_from"))
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)

    date_to = _parse_date(request.GET.get("date_to"))
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    return qs


@login_required
def admin_audit_list(request: HttpRequest) -> HttpResponse:
    """
    Sert le shell HTML qui monte la datatable React. Toutes les données
    (filtres + lignes + pagination + counts) sont fournies par
    ``apps.api.views.AuditLogListView`` et consommées côté JS.

    L'export CSV (vue séparée ci-dessous) garde la logique de filtrage côté
    serveur — le React lui passe ses query params en l'état.
    """
    _ensure_admin(request)
    return render(request, "dashboard/admin_audit_list.html")


@login_required
def admin_audit_export(request: HttpRequest) -> HttpResponse:
    """
    Export CSV du journal filtré (UTF-8 BOM pour Excel). Pas de pagination —
    streaming serait préférable pour de très gros volumes (>100k lignes), mais
    pour l'usage prévu (audit hebdo / mémoire) la version simple suffit.
    """
    _ensure_admin(request)
    qs = _filtered_qs(request).order_by("-created_at")

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    fname = f"audit_{timezone.localdate().isoformat()}.csv"
    response["Content-Disposition"] = f'attachment; filename="{fname}"'
    response.write("﻿")  # BOM UTF-8 pour Excel

    writer = csv.writer(response, delimiter=";")
    writer.writerow([
        "id", "created_at", "severity", "action",
        "actor", "actor_role",
        "target_type", "target_id", "target_label",
        "ip", "payload",
    ])
    for log in qs.iterator(chunk_size=500):
        writer.writerow([
            log.id,
            log.created_at.isoformat(),
            log.severity,
            log.action,
            log.actor.username if log.actor_id else "",
            log.actor_role,
            log.target_type,
            log.target_id or "",
            log.target_label,
            log.ip or "",
            log.payload,
        ])
    return response
