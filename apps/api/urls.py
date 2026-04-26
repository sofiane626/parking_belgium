"""URLs DRF v1."""
from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token

from .views import CheckRightView, CommuneListView, ZoneListView

urlpatterns = [
    path("check-right/", CheckRightView.as_view(), name="check-right"),
    path("communes/", CommuneListView.as_view(), name="communes"),
    path("zones/", ZoneListView.as_view(), name="zones"),
    # Standard DRF token endpoint (POST username + password → token).
    path("token/", obtain_auth_token, name="token"),
]
