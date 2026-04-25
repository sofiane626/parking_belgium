from django.urls import path

from . import views

urlpatterns = [
    path("", views.vehicle_list, name="list"),
    path("add/", views.vehicle_create, name="create"),
    path("<int:pk>/", views.vehicle_detail, name="detail"),
    path("<int:pk>/edit/", views.vehicle_edit, name="edit"),
    path("<int:pk>/delete/", views.vehicle_delete, name="delete"),
    path("<int:pk>/restore/", views.vehicle_restore, name="restore"),
    path("<int:vehicle_pk>/plate-change/", views.plate_change_create, name="plate_change_create"),
    path("plate-change/<int:pk>/", views.plate_change_detail, name="plate_change_detail"),
    path("plate-change/<int:pk>/cancel/", views.plate_change_cancel, name="plate_change_cancel"),
]
