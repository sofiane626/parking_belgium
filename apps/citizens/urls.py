from django.urls import path

from . import views

urlpatterns = [
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("address-change/", views.address_change_create, name="address_change_create"),
    path("address-change/<int:pk>/", views.address_change_detail, name="address_change_detail"),
    path("address-change/<int:pk>/cancel/", views.address_change_cancel, name="address_change_cancel"),
    path("requests/", views.request_list, name="request_list"),
]
