from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from apps.companies.models import Company
from apps.core.models import Commune
from apps.vehicles.models import Vehicle

from .models import Permit, PermitStatus, PermitType, VisitorCode, VisitorCodeStatus
from .services import (
    PermitError,
    cancel,
    cancel_visitor_code,
    create_draft,
    create_professional_permit,
    create_visitor_permit,
    generate_visitor_code,
    mark_paid,
    remaining_visitor_quota,
    submit_application,
)


def _own(request: HttpRequest, pk: int) -> Permit:
    return get_object_or_404(Permit, pk=pk, citizen=request.user)


@login_required
def permit_list(request: HttpRequest) -> HttpResponse:
    permits = request.user.permits.select_related("vehicle", "company").all()
    return render(request, "permits/list.html", {"permits": permits})


@login_required
def permit_detail(request: HttpRequest, pk: int) -> HttpResponse:
    permit = _own(request, pk)
    zones = permit.zones.select_related("source_polygon", "source_rule").all()
    visitor_quota = (
        remaining_visitor_quota(permit) if permit.permit_type == PermitType.VISITOR else None
    )
    return render(
        request,
        "permits/detail.html",
        {"permit": permit, "zones": zones, "visitor_quota": visitor_quota},
    )


@login_required
def permit_wizard(request: HttpRequest, vehicle_pk: int) -> HttpResponse:
    """
    Wizard React multi-étapes pour la création d'une carte riverain.

    Le serveur ne fait QUE servir le shell HTML qui monte le bundle React.
    Toute la logique vit dans :
    - ``apps.api.views.PermitEligibilityView`` (lecture)
    - ``apps.api.views.PermitSubmitView`` (création)
    - ``apps.payments.views`` (paiement Stripe / simulation)

    Si le query-string contient ``?step=success&permit_id=N``, le wizard saute
    direct à l'étape 5 (utilisé pour le retour après Stripe Checkout).
    """
    vehicle = get_object_or_404(Vehicle, pk=vehicle_pk, owner=request.user)
    initial_permit_id = request.GET.get("permit_id")
    initial_step = request.GET.get("step")
    return render(request, "permits/wizard.html", {
        "vehicle": vehicle,
        "initial_permit_id": initial_permit_id,
        "initial_step": initial_step,
    })


@login_required
def permit_create_for_vehicle(request: HttpRequest, vehicle_pk: int) -> HttpResponse:
    """
    One-shot: create a resident draft for this vehicle and immediately submit
    it. The engine evaluates and the citizen lands on the detail page where
    they can pay (or wait for manual review / see refusal).
    """
    vehicle = get_object_or_404(Vehicle, pk=vehicle_pk, owner=request.user)

    # Don't allow stacking active applications for the same (vehicle, type).
    blocking_statuses = {
        PermitStatus.SUBMITTED, PermitStatus.MANUAL_REVIEW,
        PermitStatus.AWAITING_PAYMENT, PermitStatus.ACTIVE,
    }
    existing = Permit.objects.filter(
        vehicle=vehicle, citizen=request.user,
        permit_type=PermitType.RESIDENT, status__in=blocking_statuses,
    ).first()
    if existing:
        messages.info(request, _("Une demande pour ce véhicule est déjà en cours."))
        return redirect("permits:detail", pk=existing.pk)

    if request.method != "POST":
        return render(request, "permits/confirm_create.html", {"vehicle": vehicle})

    from apps.permits.policies import PolicyError
    try:
        permit = create_draft(request.user, vehicle, PermitType.RESIDENT)
        permit = submit_application(permit)
    except (PermitError, PolicyError, PermissionDenied) as exc:
        messages.error(request, str(exc) or _("Demande impossible."))
        return redirect("vehicles:detail", pk=vehicle.pk)

    messages.success(request, _("Demande introduite."))
    return redirect("permits:detail", pk=permit.pk)


@login_required
def permit_pay(request: HttpRequest, pk: int) -> HttpResponse:
    """Backward-compatible redirect — real flow lives in apps.payments now."""
    permit = _own(request, pk)
    return redirect("payments:start", pk=permit.pk)


@login_required
def permit_cancel(request: HttpRequest, pk: int) -> HttpResponse:
    permit = _own(request, pk)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    try:
        cancel(permit, by_user=request.user)
    except PermitError as exc:
        messages.error(request, str(exc))
        return redirect("permits:detail", pk=permit.pk)
    messages.success(request, _("Demande annulée."))
    return redirect("permits:list")


# ----- visitor permits ------------------------------------------------------

@login_required
def visitor_create(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return render(request, "permits/confirm_visitor_create.html")
    from apps.permits.policies import PolicyError
    try:
        permit = create_visitor_permit(request.user)
    except (PermitError, PolicyError) as exc:
        messages.error(request, str(exc))
        return redirect("permits:list")
    messages.success(request, _("Carte visiteur activée."))
    return redirect("permits:detail", pk=permit.pk)


@login_required
def visitor_code_create(request: HttpRequest, pk: int) -> HttpResponse:
    permit = _own(request, pk)
    if permit.permit_type != PermitType.VISITOR:
        raise PermissionDenied
    if request.method == "POST":
        plate = (request.POST.get("plate") or "").strip()
        try:
            duration = int(request.POST.get("duration_hours") or 0) or None
        except ValueError:
            duration = None
        if not plate:
            messages.error(request, _("La plaque est requise."))
        else:
            try:
                generate_visitor_code(permit, plate=plate, duration_hours=duration)
                messages.success(request, _("Code généré."))
                return redirect("permits:detail", pk=permit.pk)
            except PermitError as exc:
                messages.error(request, str(exc))
    return render(request, "permits/visitor_code_form.html", {"permit": permit})


@login_required
def visitor_code_cancel(request: HttpRequest, pk: int, code_pk: int) -> HttpResponse:
    permit = _own(request, pk)
    code = get_object_or_404(VisitorCode, pk=code_pk, permit=permit)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    try:
        cancel_visitor_code(code, by_user=request.user)
        messages.success(request, _("Code annulé."))
    except PermitError as exc:
        messages.error(request, str(exc))
    return redirect("permits:detail", pk=permit.pk)


# ----- professional permits -------------------------------------------------

@login_required
def professional_create(request: HttpRequest, vehicle_pk: int) -> HttpResponse:
    vehicle = get_object_or_404(Vehicle, pk=vehicle_pk, owner=request.user)
    companies = request.user.companies.all()
    if not companies.exists():
        messages.warning(request, _("Vous devez d'abord enregistrer une entreprise."))
        return redirect("companies:create")

    communes = Commune.objects.all()

    if request.method == "POST":
        company_pk = request.POST.get("company")
        commune_pk = request.POST.get("target_commune")
        company = companies.filter(pk=company_pk).first()
        commune = communes.filter(pk=commune_pk).first()
        if not company:
            messages.error(request, _("Entreprise invalide."))
        elif not commune:
            messages.error(request, _("Commune cible requise."))
        else:
            from apps.permits.policies import PolicyError
            try:
                permit = create_professional_permit(request.user, vehicle, company, commune)
                messages.success(request, _(
                    "Demande envoyée — toutes les zones de cette commune sont attribuées en attendant validation."
                ))
                return redirect("permits:detail", pk=permit.pk)
            except (PermitError, PolicyError, PermissionDenied) as exc:
                messages.error(request, str(exc) or _("Création impossible."))

    return render(
        request,
        "permits/confirm_professional_create.html",
        {"vehicle": vehicle, "companies": companies, "communes": communes},
    )
