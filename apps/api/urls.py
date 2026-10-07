"""URLs DRF v1."""
from django.urls import path
from drf_spectacular.views import (
    SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView,
)
from .views import (
    AuditLogListView, CheckRightView, CommuneListView, LockoutObtainAuthToken,
    PermitEligibilityView, PermitSubmitView, ZoneListView,
)

urlpatterns = [
    path("check-right/", CheckRightView.as_view(), name="check-right"),
    path("communes/", CommuneListView.as_view(), name="communes"),
    path("zones/", ZoneListView.as_view(), name="zones"),
    # Endpoint token DRF (POST username + password → token), avec verrouillage
    # anti brute-force.
    path("token/", LockoutObtainAuthToken.as_view(), name="token"),
    # Wizard de création de carte (consommé par le bundle React).
    path("permits/eligibility/<int:vehicle_pk>/",
         PermitEligibilityView.as_view(), name="permit-eligibility"),
    path("permits/submit/<int:vehicle_pk>/",
         PermitSubmitView.as_view(), name="permit-submit"),
    # Datatable d'audit pour la page back-office (admin).
    path("audit/", AuditLogListView.as_view(), name="audit-list"),

    # ----- OpenAPI / Swagger / Redoc ----------------------------------------
    # Schéma brut (JSON ou YAML selon le format demandé).
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    # UI interactive Swagger pour tester les endpoints depuis le navigateur.
    path("docs/", SpectacularSwaggerView.as_view(url_name="api:schema"), name="docs"),
    # UI Redoc, plus lisible pour de la documentation à présenter.
    path("redoc/", SpectacularRedocView.as_view(url_name="api:schema"), name="redoc"),
]
