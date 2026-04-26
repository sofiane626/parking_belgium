from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("after-login/", views.post_login_redirect, name="post_login_redirect"),
    path("commune-lookup/", views.commune_lookup, name="commune_lookup"),
    path("legal/privacy/", views.legal_privacy, name="legal_privacy"),
    path("legal/terms/", views.legal_terms, name="legal_terms"),
]
