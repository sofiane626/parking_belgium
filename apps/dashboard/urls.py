from django.urls import path

from . import views, views_users

urlpatterns = [
    path("citizen/", views.citizen_dashboard, name="citizen"),
    path("agent/", views.agent_dashboard, name="agent"),
    path("admin/", views.admin_dashboard, name="admin"),
    path("super-admin/", views.super_admin_dashboard, name="super_admin"),

    # Agent — request triage
    path("agent/requests/", views.agent_requests_list, name="agent_requests"),
    path("agent/requests/address/<int:pk>/", views.agent_request_address, name="agent_request_address"),
    path("agent/requests/address/<int:pk>/approve/", views.agent_request_address_approve, name="agent_request_address_approve"),
    path("agent/requests/address/<int:pk>/reject/", views.agent_request_address_reject, name="agent_request_address_reject"),
    path("agent/requests/plate/<int:pk>/", views.agent_request_plate, name="agent_request_plate"),
    path("agent/requests/plate/<int:pk>/approve/", views.agent_request_plate_approve, name="agent_request_plate_approve"),
    path("agent/requests/plate/<int:pk>/reject/", views.agent_request_plate_reject, name="agent_request_plate_reject"),

    # Agent — permits manual review queue
    path("agent/permits/", views.agent_permits_list, name="agent_permits"),
    path("agent/permits/<int:pk>/", views.agent_permit_detail, name="agent_permit_detail"),
    path("agent/permits/<int:pk>/approve/", views.agent_permit_approve, name="agent_permit_approve"),
    path("agent/permits/<int:pk>/refuse/", views.agent_permit_refuse, name="agent_permit_refuse"),
    path("agent/permits/<int:pk>/zones/add/", views.agent_permit_add_zone, name="agent_permit_add_zone"),
    path("agent/permits/<int:pk>/zones/<int:zone_pk>/remove/", views.agent_permit_remove_zone, name="agent_permit_remove_zone"),

    # Admin — GIS data + polygon rules
    path("admin/gis/", views.gis_versions_list, name="gis_versions"),
    path("admin/gis/polygons/", views.gis_polygons_list, name="gis_polygons"),
    path("admin/gis/polygons/<int:pk>/", views.gis_polygon_detail, name="gis_polygon_detail"),
    path("admin/gis/rules/<int:pk>/toggle/", views.gis_rule_toggle, name="gis_rule_toggle"),
    path("admin/gis/rules/<int:pk>/delete/", views.gis_rule_delete, name="gis_rule_delete"),

    # Admin — configuration métier
    path("admin/config/", views.admin_permit_config, name="admin_permit_config"),
    path("admin/policies/", views.admin_policies_list, name="admin_policies"),
    path("admin/policies/new/", views.admin_policy_create, name="admin_policy_create"),
    path("admin/policies/<int:pk>/", views.admin_policy_edit, name="admin_policy_edit"),
    path("admin/policies/<int:pk>/delete/", views.admin_policy_delete, name="admin_policy_delete"),

    # Admin — gestion des utilisateurs
    path("admin/users/", views_users.admin_users_list, name="admin_users"),
    path("admin/users/<int:pk>/", views_users.admin_user_edit, name="admin_user_edit"),
    path("admin/users/<int:pk>/send-reset/", views_users.admin_user_send_reset, name="admin_user_send_reset"),
    path("admin/users/<int:pk>/toggle-active/", views_users.admin_user_toggle_active, name="admin_user_toggle_active"),
]
