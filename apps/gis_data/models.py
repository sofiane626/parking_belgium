"""
GIS source-of-truth models.

The shapefile shipped with the project (``GIS/map_tfe.shp``) is V1; new versions
can be imported via ``manage.py import_gis``. Only one version is *active* at a
time — the attribution engine queries ``is_active=True`` polygons exclusively.
Older versions stay in DB for audit and rollback.
"""
from django.conf import settings
from django.contrib.gis.db import models as gismodels
from django.db import models
from django.utils.translation import gettext_lazy as _


# Belgian Lambert 1972 — the SRID of the project's GIS source.
DEFAULT_SHAPEFILE_SRID = 31370


class GISSourceVersion(models.Model):
    name = models.CharField(_("nom"), max_length=100, unique=True)
    source_filename = models.CharField(_("fichier source"), max_length=255)
    srid = models.IntegerField(_("SRID"))
    polygon_count = models.IntegerField(_("nombre de polygones"), default=0)
    notes = models.TextField(_("notes"), blank=True)
    is_active = models.BooleanField(_("active"), default=False)

    imported_at = models.DateTimeField(auto_now_add=True)
    imported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ["-imported_at"]
        verbose_name = _("version GIS")
        verbose_name_plural = _("versions GIS")
        constraints = [
            models.UniqueConstraint(
                fields=["is_active"],
                condition=models.Q(is_active=True),
                name="only_one_active_gis_version",
            ),
        ]

    def __str__(self) -> str:
        flag = "actif" if self.is_active else "inactif"
        return f"{self.name} — {self.polygon_count} polygones ({flag})"


class GISPolygon(models.Model):
    """
    A single polygon imported from the shapefile. The original ``attributes_json``
    column preserves every source field so future shapefile additions never get
    silently dropped — the typed mirror columns are just for fast querying.
    """

    version = models.ForeignKey(
        GISSourceVersion,
        on_delete=models.CASCADE,
        related_name="polygons",
    )
    geometry = gismodels.MultiPolygonField(srid=DEFAULT_SHAPEFILE_SRID)

    # Mirrored attributes (fast lookup / display).
    zonecode = models.CharField(_("zonecode"), max_length=100, db_index=True)
    niscode = models.CharField(_("niscode"), max_length=10, db_index=True)
    commune = models.ForeignKey(
        "core.Commune",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gis_polygons",
    )
    type = models.CharField(_("type"), max_length=50, blank=True)
    layer = models.CharField(_("layer"), max_length=100, blank=True)
    name_fr = models.CharField(_("nom (fr)"), max_length=200, blank=True)
    name_nl = models.CharField(_("nom (nl)"), max_length=200, blank=True)
    name_en = models.CharField(_("nom (en)"), max_length=200, blank=True)
    reciprocit = models.CharField(_("reciprocit"), max_length=100, blank=True)
    area = models.FloatField(_("aire (m²)"), null=True, blank=True)
    perimeter = models.FloatField(_("périmètre (m)"), null=True, blank=True)

    # Untouched copy of every field from the source row.
    attributes_json = models.JSONField(_("attributs source"), default=dict)

    class Meta:
        verbose_name = _("polygone GIS")
        verbose_name_plural = _("polygones GIS")
        ordering = ["niscode", "zonecode"]
        indexes = [
            models.Index(fields=["version", "zonecode"]),
            models.Index(fields=["version", "niscode"]),
        ]
        # No unique constraint on (version, zonecode): real shapefiles allow
        # the same zonecode to span multiple non-contiguous polygons.

    def __str__(self) -> str:
        return f"{self.zonecode} ({self.commune or self.niscode})"
