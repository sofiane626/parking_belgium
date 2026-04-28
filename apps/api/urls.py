"""URLs DRF v1."""
from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token

from .views import (
    AuditLogListView, CheckRightView, CommuneListView,
    PermitEligibilityView, PermitSubmitView, ZoneListView,
)

urlpatterns = [
    path("check-right/", CheckRightView.as_view(), name="check-right"),
    path("communes/", CommuneListView.as_view(), name="communes"),
    path("zones/", ZoneListView.as_view(), name="zones"),
    # Standard DRF token endpoint (POST username + password → token).
    path("token/", obtain_auth_token, name="token"),
    # Wizard de création de carte (consommé par le bundle React).
    path("permits/eligibility/<int:vehicle_pk>/",
         PermitEligibilityView.as_view(), name="permit-eligibility"),
    path("permits/submit/<int:vehicle_pk>/",
         PermitSubmitView.as_view(), name="permit-submit"),
    # Datatable d'audit pour la page back-office (admin).
    path("audit/", AuditLogListView.as_view(), name="audit-list"),
]
