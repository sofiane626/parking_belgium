"""
Role-gated dashboards and back-office actions.

The citizen dashboard is the user's hub: it pulls profile, address and vehicles
through ``apps.citizens.services`` so we never duplicate the lazy-create logic.
The agent area handles request triage (address change, plate change).
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from django.core.paginator import Paginator

from apps.citizens.forms import AgentDecisionForm
from apps.citizens.models import Address, AddressChangeRequest, RequestStatus
from apps.citizens.services import (
    approve_address_change,
    get_or_create_profile,
    reject_address_change,
)
from apps.core.models import Commune
from apps.gis_data.models import GISPolygon, GISSourceVersion
from apps.rules.forms import PolygonRuleForm
from apps.rules.models import PolygonRule
from apps.permits.forms import CommunePermitPolicyForm, PermitConfigForm
from apps.permits.models import (
    CommunePermitPolicy, Permit, PermitConfig, PermitStatus, PermitType, PermitZone, PriceStrategy,
)
from apps.permits.services import (
    PermitError,
    add_manual_zone,
    approve_manual_review,
    approve_professional,
    refuse as refuse_permit,
    remove_zone,
)
from apps.vehicles.models import PlateChangeRequest, PlateChangeStatus
from apps.vehicles.services import approve_plate_change, reject_plate_change

BACK_OFFICE_ROLES = {"agent", "admin", "super_admin"}
ADMIN_ROLES = {"admin", "super_admin"}


def _require_role(request: HttpRequest, *allowed: str) -> None:
    if not request.user.is_authenticated or request.user.role not in allowed:
        raise PermissionDenied


# ----- citizen dashboard ----------------------------------------------------

@login_required
def citizen_dashboard(request: HttpRequest) -> HttpResponse:
    _require_role(request, "citizen")
    profile = get_or_create_profile(request.user)
    address = Address.objects.filter(profile=profile).first()
    vehicles = list(request.user.vehicles.all())
    pending_address_request = AddressChangeRequest.objects.filter(
        profile=profile, status=RequestStatus.PENDING
    ).first()
    permits = list(
        Permit.objects.filter(citizen=request.user)
        .exclude(status__in=[PermitStatus.CANCELLED, PermitStatus.EXPIRED, PermitStatus.REFUSED])
        .select_related("vehicle")
    )
    from apps.citizens.journey import compute_journey
    from apps.permits.models import PermitType
    journey = compute_journey(
        request.user,
        profile=profile, address=address,
        vehicles_qs=vehicles, permits_qs=permits,
        pending_address_request=pending_address_request,
    )
    # Pour chaque véhicule actif : a-t-il déjà une carte en cours ? Sinon on
    # affiche le bouton "Demander une carte" directement sur sa ligne.
    busy_vehicle_ids = {p.vehicle_id for p in permits if p.vehicle_id}

    # ---- Section "Carte visiteur" : prérequis = carte riverain ACTIVE.
    has_active_resident = any(
        p.permit_type == PermitType.RESIDENT and p.status == PermitStatus.ACTIVE
        for p in permits
    )
    visitor_permit = next(
        (p for p in permits
         if p.permit_type == PermitType.VISITOR and p.status == PermitStatus.ACTIVE),
        None,
    )
    visitor_quota_left = None
    if visitor_permit:
        from apps.permits.services import remaining_visitor_quota
        visitor_quota_left = remaining_visitor_quota(visitor_permit)

    return render(
        request,
        "dashboard/citizen.html",
        {
            "profile": profile,
            "address": address,
            "vehicles": vehicles,
            "pending_address_request": pending_address_request,
            "permits": permits,
            "journey": journey,
            "busy_vehicle_ids": busy_vehicle_ids,
            "has_active_resident": has_active_resident,
            "visitor_permit": visitor_permit,
            "visitor_quota_left": visitor_quota_left,
        },
    )


# ----- agent / admin --------------------------------------------------------

@login_required
def agent_dashboard(request: HttpRequest) -> HttpResponse:
    _require_role(request, *BACK_OFFICE_ROLES)
    pending_permits = Permit.objects.filter(status=PermitStatus.MANUAL_REVIEW).count()
    pending_count = (
        AddressChangeRequest.objects.filter(status=RequestStatus.PENDING).count()
        + PlateChangeRequest.objects.filter(status=PlateChangeStatus.PENDING).count()
    )
    return render(request, "dashboard/agent.html", {
        "pending_count": pending_count,
        "pending_permits": pending_permits,
    })


@login_required
def admin_dashboard(request: HttpRequest) -> HttpResponse:
    _require_role(request, "admin", "super_admin")
    return render(request, "dashboard/admin.html")


@login_required
def super_admin_dashboard(request: HttpRequest) -> HttpResponse:
    _require_role(request, "super_admin")
    return render(request, "dashboard/super_admin.html")


# ----- agent: request triage ------------------------------------------------

@login_required
def agent_requests_list(request: HttpRequest) -> HttpResponse:
    _require_role(request, *BACK_OFFICE_ROLES)
    show_all = request.GET.get("all") == "1"
    address_qs = AddressChangeRequest.objects.select_related("profile__user", "commune")
    plate_qs = PlateChangeRequest.objects.select_related("vehicle__owner")
    if not show_all:
        address_qs = address_qs.filter(status=RequestStatus.PENDING)
        plate_qs = plate_qs.filter(status=PlateChangeStatus.PENDING)
    return render(
        request,
        "dashboard/agent_requests_list.html",
        {
            "address_requests": address_qs,
            "plate_requests": plate_qs,
            "show_all": show_all,
        },
    )


def _decide_address(request, pk, *, approve: bool):
    _require_role(request, *BACK_OFFICE_ROLES)
    req = get_object_or_404(AddressChangeRequest, pk=pk)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    form = AgentDecisionForm(request.POST)
    if not form.is_valid():
        messages.error(request, _("Notes invalides."))
        return redirect("dashboard:agent_request_address", pk=pk)
    notes = form.cleaned_data["notes"]
    if approve:
        approve_address_change(req, agent=request.user, notes=notes)
        messages.success(request, _("Demande d'adresse approuvée."))
    else:
        if not notes:
            messages.error(request, _("Une note est requise pour refuser."))
            return redirect("dashboard:agent_request_address", pk=pk)
        reject_address_change(req, agent=request.user, notes=notes)
        messages.success(request, _("Demande d'adresse refusée."))
    return redirect("dashboard:agent_requests")


@login_required
def agent_request_address(request: HttpRequest, pk: int) -> HttpResponse:
    _require_role(request, *BACK_OFFICE_ROLES)
    req = get_object_or_404(
        AddressChangeRequest.objects.select_related("profile__user", "commune"), pk=pk
    )
    current_address = Address.objects.filter(profile=req.profile).first()
    return render(
        request,
        "dashboard/agent_request_address.html",
        {
            "req": req,
            "current_address": current_address,
            "form": AgentDecisionForm(),
        },
    )


@login_required
def agent_request_address_approve(request: HttpRequest, pk: int) -> HttpResponse:
    return _decide_address(request, pk, approve=True)


@login_required
def agent_request_address_reject(request: HttpRequest, pk: int) -> HttpResponse:
    return _decide_address(request, pk, approve=False)


def _decide_plate(request, pk, *, approve: bool):
    _require_role(request, *BACK_OFFICE_ROLES)
    req = get_object_or_404(PlateChangeRequest, pk=pk)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    form = AgentDecisionForm(request.POST)
    if not form.is_valid():
        messages.error(request, _("Notes invalides."))
        return redirect("dashboard:agent_request_plate", pk=pk)
    notes = form.cleaned_data["notes"]
    if approve:
        try:
            approve_plate_change(req, agent=request.user, notes=notes)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("dashboard:agent_request_plate", pk=pk)
        messages.success(request, _("Changement de plaque appliqué."))
    else:
        if not notes:
            messages.error(request, _("Une note est requise pour refuser."))
            return redirect("dashboard:agent_request_plate", pk=pk)
        reject_plate_change(req, agent=request.user, notes=notes)
        messages.success(request, _("Demande de plaque refusée."))
    return redirect("dashboard:agent_requests")


@login_required
def agent_request_plate(request: HttpRequest, pk: int) -> HttpResponse:
    _require_role(request, *BACK_OFFICE_ROLES)
    req = get_object_or_404(
        PlateChangeRequest.objects.select_related("vehicle__owner"), pk=pk
    )
    return render(
        request,
        "dashboard/agent_request_plate.html",
        {"req": req, "form": AgentDecisionForm()},
    )


@login_required
def agent_request_plate_approve(request: HttpRequest, pk: int) -> HttpResponse:
    return _decide_plate(request, pk, approve=True)


@login_required
def agent_request_plate_reject(request: HttpRequest, pk: int) -> HttpResponse:
    return _decide_plate(request, pk, approve=False)


# ----- admin: GIS data + rules ---------------------------------------------

@login_required
def gis_versions_list(request: HttpRequest) -> HttpResponse:
    _require_role(request, *ADMIN_ROLES)
    versions = GISSourceVersion.objects.all()
    return render(request, "dashboard/gis_versions.html", {"versions": versions})


@login_required
def gis_polygons_list(request: HttpRequest) -> HttpResponse:
    _require_role(request, *ADMIN_ROLES)
    version = GISSourceVersion.objects.filter(is_active=True).first()
    qs = (
        GISPolygon.objects.filter(version=version).select_related("commune")
        if version else GISPolygon.objects.none()
    )
    selected_commune = request.GET.get("commune") or ""
    if selected_commune:
        qs = qs.filter(commune__niscode=selected_commune)
    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "dashboard/gis_polygons_list.html",
        {
            "page": page,
            "version": version,
            "communes": Commune.objects.all(),
            "selected_commune": selected_commune,
        },
    )


@login_required
def gis_polygon_detail(request: HttpRequest, pk: int) -> HttpResponse:
    _require_role(request, *ADMIN_ROLES)
    polygon = get_object_or_404(
        GISPolygon.objects.select_related("commune", "version"), pk=pk
    )
    rules = polygon.rules.select_related("commune", "created_by").order_by("priority", "id")

    if request.method == "POST":
        form = PolygonRuleForm(request.POST)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.polygon = polygon
            rule.commune = polygon.commune
            rule.created_by = request.user
            rule.save()
            messages.success(request, _("Règle créée."))
            return redirect("dashboard:gis_polygon_detail", pk=polygon.pk)
    else:
        form = PolygonRuleForm()

    return render(
        request,
        "dashboard/gis_polygon_detail.html",
        {"polygon": polygon, "rules": rules, "form": form},
    )


@login_required
def gis_rule_toggle(request: HttpRequest, pk: int) -> HttpResponse:
    _require_role(request, *ADMIN_ROLES)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    rule = get_object_or_404(PolygonRule, pk=pk)
    rule.is_active = not rule.is_active
    rule.save(update_fields=["is_active", "updated_at"])
    messages.success(request, _("Règle mise à jour."))
    return redirect("dashboard:gis_polygon_detail", pk=rule.polygon_id)


@login_required
def gis_rule_delete(request: HttpRequest, pk: int) -> HttpResponse:
    _require_role(request, *ADMIN_ROLES)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    rule = get_object_or_404(PolygonRule, pk=pk)
    polygon_pk = rule.polygon_id
    rule.delete()
    messages.success(request, _("Règle supprimée."))
    return redirect("dashboard:gis_polygon_detail", pk=polygon_pk)


# ----- agent: permits review (manual_review queue) -------------------------

@login_required
def agent_permits_list(request: HttpRequest) -> HttpResponse:
    _require_role(request, *BACK_OFFICE_ROLES)
    base = Permit.objects.select_related("citizen", "vehicle", "source_polygon", "company")

    status = request.GET.get("status") or "manual_review"
    permit_type = request.GET.get("permit_type") or ""
    q = (request.GET.get("q") or "").strip()

    from django.db.models import Count, Q

    def _apply_text_filters(queryset):
        if permit_type:
            queryset = queryset.filter(permit_type=permit_type)
        if q:
            queryset = queryset.filter(
                Q(citizen__username__icontains=q) |
                Q(citizen__email__icontains=q) |
                Q(citizen__first_name__icontains=q) |
                Q(citizen__last_name__icontains=q) |
                Q(vehicle__plate__icontains=q)
            )
        return queryset

    qs = _apply_text_filters(base)
    if status and status != "all":
        qs = qs.filter(status=status)

    # Counters per status — respect text filters but ignore the active status
    # so the chips always show the full breakdown for the current scope.
    counts_rows = _apply_text_filters(base).values("status").annotate(n=Count("id"))
    counts = {row["status"]: row["n"] for row in counts_rows}
    counts["all"] = sum(counts.values())

    chip_definitions = [
        ("manual_review", "Revue manuelle"),
        ("awaiting_payment", "À payer"),
        ("active", "Actives"),
        ("suspended", "Suspendues"),
        ("submitted", "Soumises"),
        ("draft", "Brouillon"),
        ("refused", "Refusées"),
        ("expired", "Expirées"),
        ("cancelled", "Annulées"),
        ("all", "Toutes"),
    ]
    chips = [(value, label, counts.get(value, 0)) for value, label in chip_definitions]

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "dashboard/agent_permits_list.html",
        {
            "page": page,
            "selected_status": status,
            "selected_type": permit_type,
            "q": q,
            "permit_types": PermitType.choices,
            "chips": chips,
            "total_count": counts["all"],
        },
    )


@login_required
def agent_permit_detail(request: HttpRequest, pk: int) -> HttpResponse:
    _require_role(request, *BACK_OFFICE_ROLES)
    permit = get_object_or_404(
        Permit.objects.select_related("citizen", "vehicle", "company", "source_polygon", "decided_by"),
        pk=pk,
    )
    zones = permit.zones.all()
    return render(
        request,
        "dashboard/agent_permit_detail.html",
        {"permit": permit, "zones": zones, "form": AgentDecisionForm()},
    )


def _decide_permit(request, pk, *, approve: bool):
    _require_role(request, *BACK_OFFICE_ROLES)
    permit = get_object_or_404(Permit, pk=pk)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    form = AgentDecisionForm(request.POST)
    if not form.is_valid():
        messages.error(request, _("Notes invalides."))
        return redirect("dashboard:agent_permit_detail", pk=pk)
    notes = form.cleaned_data["notes"]
    try:
        if approve:
            if permit.permit_type == PermitType.PROFESSIONAL:
                approve_professional(permit, agent=request.user, notes=notes)
            else:
                approve_manual_review(permit, agent=request.user, notes=notes)
            messages.success(request, _("Demande approuvée."))
        else:
            refuse_permit(permit, agent=request.user, notes=notes)
            messages.success(request, _("Demande refusée."))
    except PermitError as exc:
        messages.error(request, str(exc))
        return redirect("dashboard:agent_permit_detail", pk=pk)
    return redirect("dashboard:agent_permits")


@login_required
def agent_permit_add_zone(request: HttpRequest, pk: int) -> HttpResponse:
    _require_role(request, *BACK_OFFICE_ROLES)
    permit = get_object_or_404(Permit, pk=pk)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    zone_code = (request.POST.get("zone_code") or "").strip()
    is_main = request.POST.get("is_main") == "1"
    try:
        add_manual_zone(permit, zone_code=zone_code, is_main=is_main)
        messages.success(request, _("Zone ajoutée."))
    except PermitError as exc:
        messages.error(request, str(exc))
    return redirect("dashboard:agent_permit_detail", pk=pk)


@login_required
def agent_permit_remove_zone(request: HttpRequest, pk: int, zone_pk: int) -> HttpResponse:
    _require_role(request, *BACK_OFFICE_ROLES)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    zone = get_object_or_404(PermitZone, pk=zone_pk, permit_id=pk)
    try:
        remove_manual_zone(zone)
        messages.success(request, _("Zone retirée."))
    except PermitError as exc:
        messages.error(request, str(exc))
    return redirect("dashboard:agent_permit_detail", pk=pk)


@login_required
def agent_permit_approve(request: HttpRequest, pk: int) -> HttpResponse:
    return _decide_permit(request, pk, approve=True)


@login_required
def agent_permit_refuse(request: HttpRequest, pk: int) -> HttpResponse:
    return _decide_permit(request, pk, approve=False)


# ----- admin: configuration ------------------------------------------------

@login_required
def admin_permit_config(request: HttpRequest) -> HttpResponse:
    _require_role(request, *ADMIN_ROLES)
    config = PermitConfig.get()
    if request.method == "POST":
        form = PermitConfigForm(request.POST, instance=config)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.updated_by = request.user
            obj.save()
            messages.success(request, _("Configuration mise à jour."))
            return redirect("dashboard:admin_permit_config")
    else:
        form = PermitConfigForm(instance=config)
    return render(request, "dashboard/admin_permit_config.html", {"form": form, "config": config})


# ----- admin: per-commune policies -----------------------------------------

@login_required
def admin_policies_list(request: HttpRequest) -> HttpResponse:
    _require_role(request, *ADMIN_ROLES)
    qs = CommunePermitPolicy.objects.select_related("commune", "updated_by").all()

    commune = request.GET.get("commune") or ""
    permit_type = request.GET.get("permit_type") or ""
    enabled = request.GET.get("enabled") or ""
    q = (request.GET.get("q") or "").strip()

    if commune:
        qs = qs.filter(commune__niscode=commune)
    if permit_type:
        qs = qs.filter(permit_type=permit_type)
    if enabled == "1":
        qs = qs.filter(is_enabled=True)
    elif enabled == "0":
        qs = qs.filter(is_enabled=False)
    if q:
        from django.db.models import Q
        qs = qs.filter(
            Q(commune__name_fr__icontains=q) |
            Q(commune__niscode__icontains=q) |
            Q(notes__icontains=q)
        )

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "dashboard/admin_policies_list.html",
        {
            "page": page,
            "communes": Commune.objects.all(),
            "permit_types": PermitType.choices,
            "selected_commune": commune,
            "selected_type": permit_type,
            "selected_enabled": enabled,
            "q": q,
        },
    )


@login_required
def admin_policy_edit(request: HttpRequest, pk: int) -> HttpResponse:
    _require_role(request, *ADMIN_ROLES)
    policy = get_object_or_404(CommunePermitPolicy, pk=pk)
    if request.method == "POST":
        form = CommunePermitPolicyForm(request.POST, instance=policy)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.updated_by = request.user
            obj.save()
            messages.success(request, _("Politique mise à jour."))
            return redirect("dashboard:admin_policies")
    else:
        form = CommunePermitPolicyForm(instance=policy)
    return render(
        request,
        "dashboard/admin_policy_form.html",
        {"form": form, "policy": policy, "is_create": False},
    )


@login_required
def admin_policy_create(request: HttpRequest) -> HttpResponse:
    """Add a new time-versioned policy (e.g. schedule a future price change)."""
    _require_role(request, *ADMIN_ROLES)
    if request.method == "POST":
        form = CommunePermitPolicyForm(request.POST)
        commune_pk = request.POST.get("commune")
        permit_type = request.POST.get("permit_type")
        commune = Commune.objects.filter(pk=commune_pk).first()
        if form.is_valid() and commune and permit_type in dict(PermitType.choices):
            obj = form.save(commit=False)
            obj.commune = commune
            obj.permit_type = permit_type
            obj.updated_by = request.user
            obj.save()
            messages.success(request, _("Politique créée."))
            return redirect("dashboard:admin_policies")
        if not commune:
            messages.error(request, _("Commune requise."))
    else:
        form = CommunePermitPolicyForm()
    return render(
        request,
        "dashboard/admin_policy_form.html",
        {
            "form": form,
            "is_create": True,
            "communes": Commune.objects.all(),
            "permit_types": PermitType.choices,
        },
    )


@login_required
def admin_policy_delete(request: HttpRequest, pk: int) -> HttpResponse:
    _require_role(request, *ADMIN_ROLES)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    policy = get_object_or_404(CommunePermitPolicy, pk=pk)
    policy.delete()
    messages.success(request, _("Politique supprimée."))
    return redirect("dashboard:admin_policies")
