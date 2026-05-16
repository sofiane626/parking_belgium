"""Top-level URL configuration for parking_belgium."""
from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from django.contrib.sitemaps.views import sitemap

from apps.accounts.views import set_language_persistent
from apps.core.sitemaps import StaticViewSitemap
from apps.core.views import robots_txt
from apps.payments import views as payment_views

SITEMAPS = {"static": StaticViewSitemap}

handler403 = "apps.core.views.error_403"
handler404 = "apps.core.views.error_404"
handler500 = "apps.core.views.error_500"

# Routes hors-i18n : back-office Django, API publique, webhook Stripe et
# endpoint set_language. Ne pas préfixer ces URLs par la langue (elles sont
# appelées par des systèmes extérieurs ou doivent rester stables).
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(("apps.api.urls", "api"), namespace="api")),
    # Vue wrapper qui persiste aussi le choix dans User.preferred_language
    # (au lieu de juste le cookie). Garde la même URL que Django (i18n/setlang/).
    path("i18n/setlang/", set_language_persistent, name="set_language"),
    path("stripe/webhook/", payment_views.stripe_webhook, name="stripe_webhook_root"),
    # SEO — sitemap + robots.txt à la racine, hors préfixe de langue.
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
    path("robots.txt", robots_txt, name="robots_txt"),
]

# Routes UI : préfixées par /fr/ /nl/ /en/ (toutes les langues, pas de défaut sans préfixe).
urlpatterns += i18n_patterns(
    path("accounts/", include(("apps.accounts.urls", "accounts"), namespace="accounts")),
    path("dashboard/", include(("apps.dashboard.urls", "dashboard"), namespace="dashboard")),
    path("me/", include(("apps.citizens.urls", "citizens"), namespace="citizens")),
    path("me/vehicles/", include(("apps.vehicles.urls", "vehicles"), namespace="vehicles")),
    path("me/permits/", include(("apps.permits.urls", "permits"), namespace="permits")),
    path("me/payments/", include(("apps.payments.urls", "payments"), namespace="payments")),
    path("me/companies/", include(("apps.companies.urls", "companies"), namespace="companies")),
    path("map/", include(("apps.gis_data.urls", "gis_data"), namespace="gis_data")),
    path("", include(("apps.core.urls", "core"), namespace="core")),
    prefix_default_language=True,
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
