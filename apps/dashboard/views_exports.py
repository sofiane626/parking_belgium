"""
Exports CSV back-office (permits, demandes, paiements, utilisateurs).

Chaque vue :
- vérifie que l'utilisateur a le droit d'exporter (admin/super-admin)
- ré-applique les mêmes filtres GET que la liste correspondante (cohérence
  visuelle : ce que l'admin voit à l'écran = ce qu'il exporte)
- streame le CSV via ``apps.dashboard.csv_export.stream_csv``
- log un événement ``CSV_EXPORTED`` dans l'audit (avec nb de lignes + filtres)
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpRequest

from apps.accounts.services import can_manage_users
from apps.audit.services import AuditAction, log as audit_log
from apps.citizens.models import AddressChangeRequest
from apps.payments.models import Payment
from apps.permits.models import Permit
from apps.vehicles.models import PlateChangeRequest

from .csv_export import stream_csv

User = get_user_model()


def _ensure_admin(request: HttpRequest) -> None:
    if not can_manage_users(request.user):
        raise PermissionDenied


def _audit_export(request: HttpRequest, *, label: str, count: int, filters: dict) -> None:
    audit_log(
        AuditAction.CSV_EXPORTED,
        actor=request.user, request=request,
        payload={"context": {
            "export": label,
            "rows": count,
            "filters": {k: v for k, v in filters.items() if v},
        }},
    )


# ----- permits --------------------------------------------------------------

@login_required
def admin_permits_export(request: HttpRequest):
    _ensure_admin(request)
    status = request.GET.get("status", "")
    permit_type = request.GET.get("permit_type", "")
    q = (request.GET.get("q") or "").strip()

    qs = Permit.objects.select_related("citizen", "vehicle", "company", "target_commune")
    if status and status != "all":
        qs = qs.filter(status=status)
    if permit_type:
        qs = qs.filter(permit_type=permit_type)
    if q:
        qs = qs.filter(
            Q(citizen__username__icontains=q) | Q(citizen__email__icontains=q)
            | Q(vehicle__plate__icontains=q)
        )
    qs = qs.order_by("-created_at")

    header = [
        "id", "type", "statut", "citoyen", "email", "plaque", "entreprise",
        "commune_cible", "valid_from", "valid_until", "price_cents",
        "created_at", "activated_at", "expired_at", "suspended_at",
    ]

    rows_list = list(qs.iterator(chunk_size=500))

    def rows():
        for p in rows_list:
            yield [
                p.pk, p.permit_type, p.status,
                getattr(p.citizen, "username", ""),
                getattr(p.citizen, "email", ""),
                getattr(p.vehicle, "plate", "") if p.vehicle_id else "",
                getattr(p.company, "name", "") if p.company_id else "",
                getattr(p.target_commune, "name_fr", "") if p.target_commune_id else "",
                p.valid_from.isoformat() if p.valid_from else "",
                p.valid_until.isoformat() if p.valid_until else "",
                p.price_cents or 0,
                p.created_at.isoformat(),
                p.activated_at.isoformat() if p.activated_at else "",
                p.expired_at.isoformat() if p.expired_at else "",
                p.suspended_at.isoformat() if p.suspended_at else "",
            ]

    _audit_export(request, label="permits", count=len(rows_list),
                  filters={"status": status, "permit_type": permit_type, "q": q})
    return stream_csv(filename_base="permits", header=header, rows=rows())


# ----- payments -------------------------------------------------------------

@login_required
def admin_payments_export(request: HttpRequest):
    _ensure_admin(request)
    status = request.GET.get("status", "")
    method = request.GET.get("method", "")

    qs = Payment.objects.select_related("citizen", "permit")
    if status:
        qs = qs.filter(status=status)
    if method:
        qs = qs.filter(method=method)
    qs = qs.order_by("-initiated_at")

    header = [
        "id", "permit_id", "citoyen", "email", "amount_cents", "method", "statut",
        "reference", "stripe_payment_intent", "stripe_session_id",
        "card_brand", "card_last4", "initiated_at", "confirmed_at",
    ]
    rows_list = list(qs.iterator(chunk_size=500))

    def rows():
        for p in rows_list:
            yield [
                p.pk, p.permit_id,
                getattr(p.citizen, "username", "") if p.citizen_id else "",
                getattr(p.citizen, "email", "") if p.citizen_id else "",
                p.amount_cents, p.method, p.status,
                getattr(p, "reference", "") or "",
                getattr(p, "stripe_payment_intent", "") or "",
                getattr(p, "stripe_session_id", "") or "",
                p.card_brand or "", p.card_last4 or "",
                p.initiated_at.isoformat() if p.initiated_at else "",
                p.confirmed_at.isoformat() if p.confirmed_at else "",
            ]

    _audit_export(request, label="payments", count=len(rows_list),
                  filters={"status": status, "method": method})
    return stream_csv(filename_base="payments", header=header, rows=rows())


# ----- users ----------------------------------------------------------------

@login_required
def admin_users_export(request: HttpRequest):
    _ensure_admin(request)
    role = request.GET.get("role", "")
    q = (request.GET.get("q") or "").strip()
    include_inactive = request.GET.get("include_inactive", "").lower() in {"1", "true", "on"}

    qs = User.objects.all()
    if role:
        qs = qs.filter(role=role)
    if not include_inactive:
        qs = qs.filter(is_active=True)
    if q:
        qs = qs.filter(
            Q(username__icontains=q) | Q(email__icontains=q)
            | Q(first_name__icontains=q) | Q(last_name__icontains=q)
        )
    qs = qs.order_by("-date_joined")

    header = [
        "id", "username", "email", "first_name", "last_name",
        "role", "is_active", "preferred_language",
        "date_joined", "last_login",
    ]
    rows_list = list(qs.iterator(chunk_size=500))

    def rows():
        for u in rows_list:
            yield [
                u.pk, u.username, u.email, u.first_name, u.last_name,
                u.role, "1" if u.is_active else "0",
                getattr(u, "preferred_language", ""),
                u.date_joined.isoformat(),
                u.last_login.isoformat() if u.last_login else "",
            ]

    _audit_export(request, label="users", count=len(rows_list),
                  filters={"role": role, "q": q, "include_inactive": str(include_inactive)})
    return stream_csv(filename_base="users", header=header, rows=rows())


# ----- demandes (changements d'adresse + plaque) ---------------------------

@login_required
def admin_requests_export(request: HttpRequest):
    """
    Exporte les demandes en cours : changements d'adresse + changements de plaque.
    Format unifié avec colonne ``request_kind`` pour distinguer.
    """
    _ensure_admin(request)
    status = request.GET.get("status", "")

    addr_qs = AddressChangeRequest.objects.select_related("profile__user", "commune")
    plate_qs = PlateChangeRequest.objects.select_related("vehicle__owner")
    if status:
        addr_qs = addr_qs.filter(status=status)
        plate_qs = plate_qs.filter(status=status)

    addr_list = list(addr_qs.order_by("-submitted_at"))
    plate_list = list(plate_qs.order_by("-submitted_at"))

    header = [
        "id", "kind", "citoyen", "submitted_at", "status",
        "decided_at", "decided_by", "details",
    ]

    def rows():
        for r in addr_list:
            user = r.profile.user
            details = f"{r.street} {r.number}, {r.postal_code} {r.commune.name_fr}"
            yield [
                r.pk, "address",
                getattr(user, "username", ""),
                r.submitted_at.isoformat(),
                r.status,
                r.decided_at.isoformat() if r.decided_at else "",
                getattr(r.decided_by, "username", "") if r.decided_by_id else "",
                details,
            ]
        for r in plate_list:
            yield [
                r.pk, "plate",
                getattr(r.vehicle.owner, "username", ""),
                r.submitted_at.isoformat(),
                r.status,
                r.decided_at.isoformat() if r.decided_at else "",
                getattr(r.decided_by, "username", "") if r.decided_by_id else "",
                f"{r.vehicle.plate} -> {r.new_plate}",
            ]

    total = len(addr_list) + len(plate_list)
    _audit_export(request, label="requests", count=total, filters={"status": status})
    return stream_csv(filename_base="requests", header=header, rows=rows())
