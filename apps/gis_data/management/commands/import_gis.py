"""
Import a versioned GIS shapefile.

Each invocation creates a new ``GISSourceVersion`` row and inserts every feature
as a ``GISPolygon`` linked to that version. Use ``--activate`` to flip the new
version live (the previous active version is automatically deactivated, so the
attribution engine starts using the new data immediately).

Usage::

    python manage.py import_gis GIS/map_tfe.shp --name v1 --activate
    python manage.py import_gis path/to/new.shp --name v2026.06 --activate \
        --notes "MAJ Schaerbeek + Etterbeek"
"""
from pathlib import Path

from django.contrib.gis.gdal import DataSource
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.models import Commune
from apps.gis_data.models import DEFAULT_SHAPEFILE_SRID, GISPolygon, GISSourceVersion


class Command(BaseCommand):
    help = "Import a versioned GIS shapefile (Brussels parking zones)."

    def add_arguments(self, parser):
        parser.add_argument("path", type=str, help="Path to the .shp file")
        parser.add_argument(
            "--name",
            required=True,
            help="Unique version name (e.g. 'v1', 'v2026.06').",
        )
        parser.add_argument(
            "--encoding",
            default="latin1",
            help="DBF encoding (default: latin1, matching the project's .cpg).",
        )
        parser.add_argument(
            "--srid",
            type=int,
            default=DEFAULT_SHAPEFILE_SRID,
            help=f"SRID of the source geometries (default: {DEFAULT_SHAPEFILE_SRID} — Belgian Lambert 1972).",
        )
        parser.add_argument(
            "--activate",
            action="store_true",
            help="Mark this version as active and deactivate the previous one.",
        )
        parser.add_argument("--notes", default="")

    def handle(self, *args, **options):
        path = Path(options["path"]).resolve()
        if not path.exists():
            raise CommandError(f"File not found: {path}")
        if GISSourceVersion.objects.filter(name=options["name"]).exists():
            raise CommandError(f"Version name '{options['name']}' already exists.")

        ds = DataSource(str(path), encoding=options["encoding"])
        layer = ds[0]
        srid = options["srid"]

        self.stdout.write(
            f"Reading {path.name}: {len(layer)} features, geom={layer.geom_type.name}, srid={srid}."
        )

        with transaction.atomic():
            version = GISSourceVersion.objects.create(
                name=options["name"],
                source_filename=path.name,
                srid=srid,
                notes=options["notes"],
            )

            communes_by_nis = {c.niscode: c for c in Commune.objects.all()}
            count = 0

            for feat in layer:
                geom = GEOSGeometry(feat.geom.wkt, srid=srid)
                # Polygon → wrap into MultiPolygon for a uniform column type.
                if geom.geom_type == "Polygon":
                    geom = MultiPolygon(geom, srid=srid)

                nis_raw = feat.get("niscode")
                niscode = str(int(nis_raw)) if nis_raw is not None else ""
                commune = communes_by_nis.get(niscode)

                # Preserve the full original row (forward-compat).
                attrs = {f: feat.get(f) for f in layer.fields}

                GISPolygon.objects.create(
                    version=version,
                    geometry=geom,
                    zonecode=feat.get("zonecode") or "",
                    niscode=niscode,
                    commune=commune,
                    type=str(feat.get("type") or ""),
                    layer=feat.get("layer") or "",
                    name_fr=feat.get("namefre") or "",
                    name_nl=feat.get("namedut") or "",
                    name_en=feat.get("nameeng") or "",
                    reciprocit=feat.get("reciprocit") or "",
                    area=feat.get("area"),
                    perimeter=feat.get("perimeter"),
                    attributes_json=attrs,
                )
                count += 1

            version.polygon_count = count
            activated = False
            if options["activate"]:
                GISSourceVersion.objects.exclude(pk=version.pk).update(is_active=False)
                version.is_active = True
                activated = True
            version.save()

        from apps.audit.services import AuditAction, log as audit_log
        audit_log(
            AuditAction.GIS_IMPORTED,
            actor=None, target=version,
            payload={"context": {
                "name": version.name,
                "source_filename": version.source_filename,
                "polygon_count": count,
                "srid": version.srid,
            }},
        )
        if activated:
            audit_log(
                AuditAction.GIS_ACTIVE_VERSION_CHANGED,
                actor=None, target=version,
                payload={"context": {"name": version.name}},
            )

        flag = "active" if version.is_active else "inactive"
        self.stdout.write(
            self.style.SUCCESS(f"Imported {count} polygons as '{version.name}' ({flag}).")
        )
