from django.db import migrations

# 19 communes of the Brussels-Capital Region with their NIS codes (Statbel reference).
# The niscode is the bridge to GIS polygons (which carry the same attribute).
COMMUNES = [
    ("21001", "Anderlecht", "Anderlecht", "Anderlecht"),
    ("21002", "Auderghem", "Oudergem", "Auderghem"),
    ("21003", "Berchem-Sainte-Agathe", "Sint-Agatha-Berchem", "Berchem-Sainte-Agathe"),
    ("21004", "Bruxelles", "Brussel", "City of Brussels"),
    ("21005", "Etterbeek", "Etterbeek", "Etterbeek"),
    ("21006", "Evere", "Evere", "Evere"),
    ("21007", "Forest", "Vorst", "Forest"),
    ("21008", "Ganshoren", "Ganshoren", "Ganshoren"),
    ("21009", "Ixelles", "Elsene", "Ixelles"),
    ("21010", "Jette", "Jette", "Jette"),
    ("21011", "Koekelberg", "Koekelberg", "Koekelberg"),
    ("21012", "Molenbeek-Saint-Jean", "Sint-Jans-Molenbeek", "Molenbeek-Saint-Jean"),
    ("21013", "Saint-Gilles", "Sint-Gillis", "Saint-Gilles"),
    ("21014", "Saint-Josse-ten-Noode", "Sint-Joost-ten-Node", "Saint-Josse-ten-Noode"),
    ("21015", "Schaerbeek", "Schaarbeek", "Schaerbeek"),
    ("21016", "Uccle", "Ukkel", "Uccle"),
    ("21017", "Watermael-Boitsfort", "Watermaal-Bosvoorde", "Watermael-Boitsfort"),
    ("21018", "Woluwe-Saint-Lambert", "Sint-Lambrechts-Woluwe", "Woluwe-Saint-Lambert"),
    ("21019", "Woluwe-Saint-Pierre", "Sint-Pieters-Woluwe", "Woluwe-Saint-Pierre"),
]


def seed(apps, schema_editor):
    Commune = apps.get_model("core", "Commune")
    for niscode, name_fr, name_nl, name_en in COMMUNES:
        Commune.objects.update_or_create(
            niscode=niscode,
            defaults={"name_fr": name_fr, "name_nl": name_nl, "name_en": name_en},
        )


def unseed(apps, schema_editor):
    Commune = apps.get_model("core", "Commune")
    Commune.objects.filter(niscode__in=[c[0] for c in COMMUNES]).delete()


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
