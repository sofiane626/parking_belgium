from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render

from .models import Commune


def home(request: HttpRequest) -> HttpResponse:
    return render(request, "core/home.html")


def commune_lookup(request: HttpRequest) -> JsonResponse:
    """
    Endpoint AJAX consommé par le formulaire d'inscription pour auto-remplir
    la commune dès que le citoyen tape son code postal.

    GET /commune-lookup/?postal_code=1030 → {"id": 15, "name_fr": "Schaerbeek"}
    Pas de match → {"id": null}.
    """
    pc = request.GET.get("postal_code", "").strip()
    commune = Commune.for_postal_code(pc)
    if commune is None:
        return JsonResponse({"id": None})
    return JsonResponse({
        "id": commune.pk,
        "niscode": commune.niscode,
        "name_fr": commune.name_fr,
        "name_nl": commune.name_nl,
    })


@login_required
def post_login_redirect(request: HttpRequest) -> HttpResponse:
    """
    Single landing endpoint after login. Routes the user to the dashboard
    matching their role. Keeping this in one place means we never duplicate
    the role→dashboard mapping across views.
    """
    user = request.user
    if user.is_super_admin:
        return redirect("dashboard:super_admin")
    if user.is_admin_role:
        return redirect("dashboard:admin")
    if user.is_agent:
        return redirect("dashboard:agent")
    return redirect("dashboard:citizen")


def error_403(request: HttpRequest, exception=None) -> HttpResponse:
    return render(request, "core/403.html", status=403)


def error_404(request: HttpRequest, exception=None) -> HttpResponse:
    return render(request, "core/404.html", status=404)


def error_500(request: HttpRequest) -> HttpResponse:
    return render(request, "core/500.html", status=500)
