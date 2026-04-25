from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("after-login/", views.post_login_redirect, name="post_login_redirect"),
    path("commune-lookup/", views.commune_lookup, name="commune_lookup"),
]
