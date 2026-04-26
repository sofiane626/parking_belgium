"""
Gestion des tokens API depuis le back-office (admin / super_admin).

La logique métier (qui peut quoi) est dans ``apps.api.services``.
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework.authtoken.models import Token

from apps.accounts.services import can_manage_users
from apps.api.services import (
    TokenError,
    back_office_users_eligible_for_token,
    issue_token_for,
    list_tokens,
    revoke_token,
)

User = get_user_model()


def _ensure_admin(request: HttpRequest) -> None:
    if not can_manage_users(request.user):
        raise PermissionDenied


@login_required
def admin_api_tokens_list(request: HttpRequest) -> HttpResponse:
    _ensure_admin(request)
    return render(request, "dashboard/admin_api_tokens.html", {
        "tokens": list_tokens(request.user),
        "eligible_users": back_office_users_eligible_for_token(),
        # Token fraîchement émis (affiché une seule fois en clair)
        "issued_token": request.session.pop("issued_api_token", None),
        "issued_for": request.session.pop("issued_api_token_user", None),
    })


@login_required
def admin_api_token_issue(request: HttpRequest) -> HttpResponse:
    _ensure_admin(request)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    user_id = request.POST.get("user_id")
    target = get_object_or_404(User, pk=user_id)
    try:
        token = issue_token_for(target, actor=request.user)
    except TokenError as exc:
        messages.error(request, str(exc))
        return redirect("dashboard:admin_api_tokens")
    except PermissionDenied:
        messages.error(request, "Action refusée.")
        return redirect("dashboard:admin_api_tokens")

    # On stocke en session pour l'afficher une fois (pattern "show secret once").
    request.session["issued_api_token"] = token.key
    request.session["issued_api_token_user"] = target.username
    messages.success(request, f"Token créé pour {target.username}.")
    return redirect("dashboard:admin_api_tokens")


@login_required
def admin_api_token_revoke(request: HttpRequest, user_id: int) -> HttpResponse:
    _ensure_admin(request)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    token = get_object_or_404(Token, user_id=user_id)
    username = token.user.username
    try:
        revoke_token(token, actor=request.user)
    except PermissionDenied:
        messages.error(request, "Action refusée.")
    else:
        messages.success(request, f"Token de {username} révoqué.")
    return redirect("dashboard:admin_api_tokens")
