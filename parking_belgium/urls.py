"""Top-level URL configuration for parking_belgium."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

handler403 = "apps.core.views.error_403"
handler404 = "apps.core.views.error_404"
handler500 = "apps.core.views.error_500"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(("apps.api.urls", "api"), namespace="api")),
    path("accounts/", include(("apps.accounts.urls", "accounts"), namespace="accounts")),
    path("dashboard/", include(("apps.dashboard.urls", "dashboard"), namespace="dashboard")),
    path("me/", include(("apps.citizens.urls", "citizens"), namespace="citizens")),
    path("me/vehicles/", include(("apps.vehicles.urls", "vehicles"), namespace="vehicles")),
    path("me/permits/", include(("apps.permits.urls", "permits"), namespace="permits")),
    path("me/payments/", include(("apps.payments.urls", "payments"), namespace="payments")),
    path("me/companies/", include(("apps.companies.urls", "companies"), namespace="companies")),
    path("map/", include(("apps.gis_data.urls", "gis_data"), namespace="gis_data")),
    path("", include(("apps.core.urls", "core"), namespace="core")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
