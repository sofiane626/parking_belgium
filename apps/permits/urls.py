from django.urls import path

from . import views

urlpatterns = [
    path("", views.permit_list, name="list"),
    path("<int:pk>/", views.permit_detail, name="detail"),
    path("vehicle/<int:vehicle_pk>/new/", views.permit_create_for_vehicle, name="create_for_vehicle"),
    path("<int:pk>/pay/", views.permit_pay, name="pay"),
    path("<int:pk>/cancel/", views.permit_cancel, name="cancel"),

    # Visitor
    path("visitor/new/", views.visitor_create, name="visitor_create"),
    path("<int:pk>/codes/new/", views.visitor_code_create, name="visitor_code_create"),
    path("<int:pk>/codes/<int:code_pk>/cancel/", views.visitor_code_cancel, name="visitor_code_cancel"),

    # Professional
    path("professional/<int:vehicle_pk>/new/", views.professional_create, name="professional_create"),
]
