"""Quick sanity check on the active GIS version."""
from django.core.management.base import BaseCommand
from django.db.models import Count

from apps.gis_data.models import GISPolygon, GISSourceVersion


class Command(BaseCommand):
    help = "Print active GIS version statistics."

    def handle(self, *args, **options):
        v = GISSourceVersion.objects.filter(is_active=True).first()
        if not v:
            self.stdout.write(self.style.WARNING("No active GIS version."))
            return
        self.stdout.write(f"Active version: {v.name} ({v.polygon_count} polygons)")
        rows = (
            GISPolygon.objects.filter(version=v)
            .values("commune__name_fr")
            .annotate(n=Count("id"))
            .order_by("commune__name_fr")
        )
        for r in rows:
            name = r["commune__name_fr"] or "<unlinked>"
            self.stdout.write(f"  {name:30s} {r['n']:4d}")
