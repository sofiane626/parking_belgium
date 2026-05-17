from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import translation

from .models import Commune


def healthz(request: HttpRequest) -> JsonResponse:
    """
    Endpoint de healthcheck pour les plateformes type Railway / Heroku.
    Volontairement sans hit DB pour rester rapide et ne pas être affecté
    par une éventuelle latence Postgres pendant un redémarrage.
    """
    return JsonResponse({"ok": True}, status=200)


def robots_txt(request: HttpRequest) -> HttpResponse:
    """
    Sert /robots.txt avec les règles d'indexation. Pages admin et back-office
    bloquées, sitemap référencé.
    """
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /dashboard/",
        "Disallow: /me/",
        "Disallow: /accounts/password/",
        "Disallow: /api/v1/audit/",
        "Allow: /",
        "",
        f"Sitemap: {request.scheme}://{request.get_host()}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def home(request: HttpRequest) -> HttpResponse:
    return render(request, "core/home.html")


def legal_privacy(request: HttpRequest) -> HttpResponse:
    return render(request, "core/legal_privacy.html")


def legal_terms(request: HttpRequest) -> HttpResponse:
    return render(request, "core/legal_terms.html")


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
    matching their role, in the user's preferred language (FR/NL/EN).

    Activates the preferred language *before* reverse() so the redirect URL
    carries the right ``/fr/`` / ``/nl/`` / ``/en/`` prefix, then sets the
    language cookie so all subsequent requests use the same locale.
    """
    user = request.user

    # Active la langue préférée pour que reverse() produise une URL avec
    # le bon préfixe (sinon on retombe sur la langue de la requête courante,
    # qui peut être différente de celle du compte).
    valid_codes = {c for c, _name in settings.LANGUAGES}
    preferred = getattr(user, "preferred_language", None)
    if preferred in valid_codes:
        translation.activate(preferred)

    if user.is_super_admin:
        target = "dashboard:super_admin"
    elif user.is_admin_role:
        target = "dashboard:admin"
    elif user.is_agent:
        target = "dashboard:agent"
    else:
        target = "dashboard:citizen"

    response = redirect(target)
    if preferred in valid_codes:
        response.set_cookie(
            settings.LANGUAGE_COOKIE_NAME,
            preferred,
            max_age=settings.LANGUAGE_COOKIE_AGE,
            path=settings.LANGUAGE_COOKIE_PATH,
            domain=settings.LANGUAGE_COOKIE_DOMAIN,
            secure=settings.LANGUAGE_COOKIE_SECURE,
            httponly=settings.LANGUAGE_COOKIE_HTTPONLY,
            samesite=settings.LANGUAGE_COOKIE_SAMESITE,
        )
    return response


def error_403(request: HttpRequest, exception=None) -> HttpResponse:
    return render(request, "core/403.html", status=403)


def error_404(request: HttpRequest, exception=None) -> HttpResponse:
    return render(request, "core/404.html", status=404)


def error_500(request: HttpRequest) -> HttpResponse:
    return render(request, "core/500.html", status=500)
