from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from apps.vehicles.models import PlateChangeRequest

from .forms import AddressChangeRequestForm, ProfileForm
from .models import AddressChangeRequest, RequestStatus
from .services import (
    cancel_address_change,
    get_or_create_profile,
    submit_address_change,
    update_profile,
)


@login_required
def profile_edit(request: HttpRequest) -> HttpResponse:
    profile = get_or_create_profile(request.user)
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            update_profile(profile, **form.cleaned_data)
            messages.success(request, _("Profil mis à jour."))
            return redirect("dashboard:citizen")
    else:
        form = ProfileForm(instance=profile)
    return render(request, "citizens/profile_edit.html", {"form": form})


@login_required
def address_change_create(request: HttpRequest) -> HttpResponse:
    profile = get_or_create_profile(request.user)
    pending = AddressChangeRequest.objects.filter(
        profile=profile, status=RequestStatus.PENDING
    ).first()
    if pending:
        messages.info(request, _("Vous avez déjà une demande en cours."))
        return redirect("citizens:address_change_detail", pk=pending.pk)

    if request.method == "POST":
        form = AddressChangeRequestForm(request.POST)
        if form.is_valid():
            req = submit_address_change(profile, user=request.user, **form.cleaned_data)
            messages.success(request, _("Demande envoyée. Un agent va l'examiner."))
            return redirect("citizens:address_change_detail", pk=req.pk)
    else:
        form = AddressChangeRequestForm()
    return render(request, "citizens/address_change_create.html", {"form": form})


@login_required
def address_change_detail(request: HttpRequest, pk: int) -> HttpResponse:
    req = get_object_or_404(AddressChangeRequest, pk=pk, profile__user=request.user)
    return render(request, "citizens/address_change_detail.html", {"req": req})


@login_required
def address_change_cancel(request: HttpRequest, pk: int) -> HttpResponse:
    req = get_object_or_404(AddressChangeRequest, pk=pk, profile__user=request.user)
    if request.method != "POST":
        raise PermissionDenied
    cancel_address_change(req, user=request.user)
    messages.success(request, _("Demande annulée."))
    return redirect("citizens:request_list")


@login_required
def request_list(request: HttpRequest) -> HttpResponse:
    """Aggregated list of every change request submitted by this citizen."""
    addr_requests = AddressChangeRequest.objects.filter(profile__user=request.user)
    plate_requests = PlateChangeRequest.objects.filter(vehicle__owner=request.user).select_related("vehicle")
    return render(
        request,
        "citizens/request_list.html",
        {"address_requests": addr_requests, "plate_requests": plate_requests},
    )
