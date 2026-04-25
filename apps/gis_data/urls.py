from django.urls import path

from . import views

urlpatterns = [
    path("", views.map_page, name="map"),
    path("polygons.geojson", views.polygons_geojson, name="polygons_geojson"),
]
