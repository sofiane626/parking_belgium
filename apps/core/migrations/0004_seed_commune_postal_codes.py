"""
Seed des codes postaux belges des 19 communes de la Région bruxelloise.

Source : bpost / liste officielle des CP par commune. Les codes postaux 1000-1299
correspondent à la Région de Bruxelles-Capitale. Bruxelles-Ville en couvre 8
(le centre + Laeken/Haren/Neder-Over-Heembeek + Pentagone), les 18 autres
communes couvrent typiquement 1-2 codes chacune.
"""
from django.db import migrations

# (niscode, "csv_des_postal_codes")
COMMUNE_POSTAL_CODES = [
    ("21001", "1070"),                                          # Anderlecht
    ("21002", "1160"),                                          # Auderghem
    ("21003", "1082"),                                          # Berchem-Sainte-Agathe
    ("21004", "1000,1020,1120,1130"),                           # Bruxelles-Ville (centre + Laeken + Neder-Over-Heembeek + Haren)
    ("21005", "1040"),                                          # Etterbeek
    ("21006", "1140"),                                          # Evere
    ("21007", "1190"),                                          # Forest
    ("21008", "1083"),                                          # Ganshoren
    ("21009", "1050"),                                          # Ixelles
    ("21010", "1090"),                                          # Jette
    ("21011", "1081"),                                          # Koekelberg
    ("21012", "1080"),                                          # Molenbeek-Saint-Jean
    ("21013", "1060"),                                          # Saint-Gilles
    ("21014", "1210"),                                          # Saint-Josse-ten-Noode
    ("21015", "1030"),                                          # Schaerbeek
    ("21016", "1180"),                                          # Uccle
    ("21017", "1170"),                                          # Watermael-Boitsfort
    ("21018", "1200"),                                          # Woluwe-Saint-Lambert
    ("21019", "1150"),                                          # Woluwe-Saint-Pierre
]


def seed(apps, schema_editor):
    Commune = apps.get_model("core", "Commune")
    for niscode, codes in COMMUNE_POSTAL_CODES:
        Commune.objects.filter(niscode=niscode).update(postal_codes=codes)


def unseed(apps, schema_editor):
    Commune = apps.get_model("core", "Commune")
    Commune.objects.filter(niscode__in=[c[0] for c in COMMUNE_POSTAL_CODES]).update(postal_codes="")


class Migration(migrations.Migration):
    dependencies = [("core", "0003_commune_postal_codes")]
    operations = [migrations.RunPython(seed, unseed)]
