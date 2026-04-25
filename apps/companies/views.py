from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from .forms import CompanyForm
from .models import Company
from .services import create_company, delete_company, update_company


def _own(request: HttpRequest, pk: int) -> Company:
    return get_object_or_404(Company, pk=pk, owner=request.user)


@login_required
def company_list(request: HttpRequest) -> HttpResponse:
    companies = request.user.companies.select_related("commune").all()
    return render(request, "companies/list.html", {"companies": companies})


@login_required
def company_detail(request: HttpRequest, pk: int) -> HttpResponse:
    company = _own(request, pk)
    return render(request, "companies/detail.html", {"company": company})


@login_required
def company_create(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = CompanyForm(request.POST)
        if form.is_valid():
            from apps.permits.policies import PolicyError
            try:
                company = create_company(owner=request.user, **form.cleaned_data)
            except PolicyError as exc:
                messages.error(request, str(exc))
                return render(request, "companies/form.html", {"form": form, "is_create": True})
            messages.success(request, _("Entreprise ajoutée."))
            return redirect("companies:detail", pk=company.pk)
    else:
        form = CompanyForm()
    return render(request, "companies/form.html", {"form": form, "is_create": True})


@login_required
def company_edit(request: HttpRequest, pk: int) -> HttpResponse:
    company = _own(request, pk)
    if request.method == "POST":
        form = CompanyForm(request.POST, instance=company)
        if form.is_valid():
            update_company(company, by_user=request.user, **form.cleaned_data)
            messages.success(request, _("Entreprise mise à jour."))
            return redirect("companies:detail", pk=company.pk)
    else:
        form = CompanyForm(instance=company)
    return render(request, "companies/form.html", {"form": form, "is_create": False, "company": company})


@login_required
def company_delete(request: HttpRequest, pk: int) -> HttpResponse:
    company = _own(request, pk)
    if request.method == "POST":
        delete_company(company, by_user=request.user)
        messages.success(request, _("Entreprise supprimée."))
        return redirect("companies:list")
    if request.method == "GET":
        return render(request, "companies/confirm_delete.html", {"company": company})
    return HttpResponseNotAllowed(["GET", "POST"])
