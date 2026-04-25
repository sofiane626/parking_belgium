"""
Gestion des utilisateurs côté admin / super_admin.

Toute la logique métier (qui peut quoi) est dans ``apps.accounts.services``.
Ces vues ne font que router + afficher des messages d'erreur.
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from apps.accounts.models import Role
from apps.accounts.services import (
    UserManagementError,
    assignable_roles,
    can_manage_users,
    change_role,
    list_users,
    send_password_reset_for,
    update_user_basics,
)

User = get_user_model()


def _ensure_admin(request: HttpRequest) -> None:
    if not can_manage_users(request.user):
        raise PermissionDenied


@login_required
def admin_users_list(request: HttpRequest) -> HttpResponse:
    _ensure_admin(request)
    role_filter = request.GET.get("role", "").strip() or None
    q = request.GET.get("q", "").strip() or None
    include_inactive = request.GET.get("inactive") == "1"

    qs = list_users(request.user, role=role_filter, q=q, include_inactive=include_inactive)
    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page"))

    roles_with_counts = [
        {"value": r.value, "label": r.label,
         "count": User.objects.filter(role=r.value).count()}
        for r in Role
    ]

    return render(request, "dashboard/admin_users_list.html", {
        "page": page,
        "role_filter": role_filter,
        "q": q,
        "include_inactive": include_inactive,
        "roles_with_counts": roles_with_counts,
        "total_count": User.objects.count(),
    })


@login_required
def admin_user_edit(request: HttpRequest, pk: int) -> HttpResponse:
    _ensure_admin(request)
    target = get_object_or_404(User, pk=pk)

    if request.method == "POST":
        new_role = request.POST.get("role", "").strip()
        try:
            update_user_basics(
                target,
                first_name=request.POST.get("first_name", "").strip(),
                last_name=request.POST.get("last_name", "").strip(),
                email=request.POST.get("email", "").strip(),
                is_active=request.POST.get("is_active") == "on",
                actor=request.user,
            )
            if new_role and new_role != target.role:
                change_role(target, new_role=new_role, actor=request.user)
        except UserManagementError as exc:
            messages.error(request, str(exc))
            return redirect("dashboard:admin_user_edit", pk=target.pk)
        except PermissionDenied:
            messages.error(request, _("Vous n'avez pas le droit d'effectuer cette action."))
            return redirect("dashboard:admin_user_edit", pk=target.pk)

        messages.success(request, _("Utilisateur mis à jour."))
        return redirect("dashboard:admin_users")

    return render(request, "dashboard/admin_user_edit.html", {
        "target": target,
        "available_roles": assignable_roles(request.user),
        "is_self": request.user.pk == target.pk,
    })


@login_required
def admin_user_send_reset(request: HttpRequest, pk: int) -> HttpResponse:
    _ensure_admin(request)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    target = get_object_or_404(User, pk=pk)
    try:
        send_password_reset_for(target, request=request, actor=request.user)
    except UserManagementError as exc:
        messages.error(request, str(exc))
    except PermissionDenied:
        messages.error(request, _("Action refusée."))
    else:
        messages.success(request, _(
            "Email de réinitialisation envoyé à %(email)s."
        ) % {"email": target.email})
    return redirect("dashboard:admin_user_edit", pk=target.pk)


@login_required
def admin_user_toggle_active(request: HttpRequest, pk: int) -> HttpResponse:
    _ensure_admin(request)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    target = get_object_or_404(User, pk=pk)
    try:
        update_user_basics(
            target,
            first_name=target.first_name,
            last_name=target.last_name,
            email=target.email,
            is_active=not target.is_active,
            actor=request.user,
        )
    except UserManagementError as exc:
        messages.error(request, str(exc))
    except PermissionDenied:
        messages.error(request, _("Action refusée."))
    else:
        messages.success(
            request,
            _("Utilisateur réactivé.") if target.is_active else _("Utilisateur désactivé."),
        )
    return redirect("dashboard:admin_users")
