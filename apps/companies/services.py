"""Thin service layer over Company. Keeps a single hook for future audit."""
from django.core.exceptions import PermissionDenied

from .models import Company


def create_company(*, owner, **fields) -> Company:
    from apps.permits.policies import enforce_max_companies_per_citizen
    enforce_max_companies_per_citizen(owner)
    return Company.objects.create(owner=owner, **fields)


def update_company(company: Company, *, by_user, **fields) -> Company:
    if company.owner_id != by_user.pk:
        raise PermissionDenied
    for k, v in fields.items():
        setattr(company, k, v)
    company.save()
    return company


def delete_company(company: Company, *, by_user) -> None:
    if company.owner_id != by_user.pk:
        raise PermissionDenied
    company.delete()
