from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from .forms import PlateChangeRequestForm, VehicleCreateForm, VehicleEditForm
from .models import PlateChangeRequest, PlateChangeStatus, Vehicle
from .services import (
    VehicleError,
    archive_vehicle,
    cancel_plate_change,
    create_vehicle,
    restore_vehicle,
    submit_plate_change,
    update_vehicle,
)


def _owned(request: HttpRequest, pk: int) -> Vehicle:
    return get_object_or_404(Vehicle, pk=pk, owner=request.user)


def _owned_plate_request(request: HttpRequest, pk: int) -> PlateChangeRequest:
    return get_object_or_404(PlateChangeRequest, pk=pk, vehicle__owner=request.user)


# ----- vehicle CRUD ---------------------------------------------------------

@login_required
def vehicle_list(request: HttpRequest) -> HttpResponse:
    vehicles = request.user.vehicles.filter(archived_at__isnull=True)
    archived = request.user.vehicles.filter(archived_at__isnull=False)
    return render(
        request, "vehicles/list.html",
        {"vehicles": vehicles, "archived_vehicles": archived},
    )


@login_required
def vehicle_detail(request: HttpRequest, pk: int) -> HttpResponse:
    vehicle = _owned(request, pk)
    pending_plate_change = vehicle.plate_change_requests.filter(
        status=PlateChangeStatus.PENDING
    ).first()
    return render(
        request,
        "vehicles/detail.html",
        {"vehicle": vehicle, "pending_plate_change": pending_plate_change},
    )


@login_required
def vehicle_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = VehicleCreateForm(request.POST, request.FILES)
        if form.is_valid():
            from apps.permits.policies import PolicyError
            try:
                vehicle = create_vehicle(owner=request.user, **form.cleaned_data)
            except PolicyError as exc:
                messages.error(request, str(exc))
                return render(request, "vehicles/form.html", {"form": form, "is_create": True})
            messages.success(request, _("Véhicule ajouté."))
            return redirect("vehicles:detail", pk=vehicle.pk)
    else:
        form = VehicleCreateForm()
    return render(request, "vehicles/form.html", {"form": form, "is_create": True})


@login_required
def vehicle_edit(request: HttpRequest, pk: int) -> HttpResponse:
    vehicle = _owned(request, pk)
    if request.method == "POST":
        form = VehicleEditForm(request.POST, request.FILES, instance=vehicle)
        if form.is_valid():
            update_vehicle(vehicle, **form.cleaned_data)
            messages.success(request, _("Véhicule mis à jour."))
            return redirect("vehicles:detail", pk=vehicle.pk)
    else:
        form = VehicleEditForm(instance=vehicle)
    return render(
        request,
        "vehicles/form.html",
        {"form": form, "is_create": False, "vehicle": vehicle},
    )


@login_required
def vehicle_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Archivage logique. Refuse si une carte non terminale est encore liée.
    L'historique des cartes terminées (active expirée, refusée, annulée…)
    reste accessible via /me/permits/.
    """
    vehicle = _owned(request, pk)
    if request.method == "POST":
        try:
            archive_vehicle(vehicle, by_user=request.user, reason=request.POST.get("reason", ""))
        except VehicleError as exc:
            messages.error(request, str(exc))
            return redirect("vehicles:detail", pk=vehicle.pk)
        messages.success(request, _(
            "Véhicule archivé. L'historique des cartes liées reste consultable."
        ))
        return redirect("vehicles:list")
    if request.method == "GET":
        from apps.permits.models import Permit, PermitStatus
        blocking = {
            PermitStatus.DRAFT, PermitStatus.SUBMITTED,
            PermitStatus.MANUAL_REVIEW, PermitStatus.AWAITING_PAYMENT,
            PermitStatus.ACTIVE, PermitStatus.SUSPENDED,
        }
        open_permits = Permit.objects.filter(vehicle=vehicle, status__in=blocking)
        return render(request, "vehicles/confirm_delete.html", {
            "vehicle": vehicle, "open_permits": open_permits,
        })
    return HttpResponseNotAllowed(["GET", "POST"])


@login_required
def vehicle_restore(request: HttpRequest, pk: int) -> HttpResponse:
    vehicle = _owned(request, pk)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    try:
        restore_vehicle(vehicle, by_user=request.user)
    except VehicleError as exc:
        messages.error(request, str(exc))
        return redirect("vehicles:list")
    messages.success(request, _("Véhicule restauré."))
    return redirect("vehicles:detail", pk=vehicle.pk)


# ----- plate change request workflow ---------------------------------------

@login_required
def plate_change_create(request: HttpRequest, vehicle_pk: int) -> HttpResponse:
    vehicle = _owned(request, vehicle_pk)
    pending = vehicle.plate_change_requests.filter(status=PlateChangeStatus.PENDING).first()
    if pending:
        messages.info(request, _("Une demande de changement de plaque est déjà en cours pour ce véhicule."))
        return redirect("vehicles:plate_change_detail", pk=pending.pk)

    if request.method == "POST":
        form = PlateChangeRequestForm(request.POST, request.FILES, vehicle=vehicle)
        if form.is_valid():
            req = submit_plate_change(
                vehicle,
                user=request.user,
                new_plate=form.cleaned_data["new_plate"],
                new_registration_document=form.cleaned_data.get("new_registration_document"),
                reason=form.cleaned_data.get("reason", ""),
            )
            messages.success(request, _("Demande envoyée. Un agent va l'examiner."))
            return redirect("vehicles:plate_change_detail", pk=req.pk)
    else:
        form = PlateChangeRequestForm(vehicle=vehicle)
    return render(
        request,
        "vehicles/plate_change_create.html",
        {"form": form, "vehicle": vehicle},
    )


@login_required
def plate_change_detail(request: HttpRequest, pk: int) -> HttpResponse:
    req = _owned_plate_request(request, pk)
    return render(request, "vehicles/plate_change_detail.html", {"req": req})


@login_required
def plate_change_cancel(request: HttpRequest, pk: int) -> HttpResponse:
    req = _owned_plate_request(request, pk)
    if request.method != "POST":
        raise PermissionDenied
    cancel_plate_change(req, user=request.user)
    messages.success(request, _("Demande annulée."))
    return redirect("citizens:request_list")
