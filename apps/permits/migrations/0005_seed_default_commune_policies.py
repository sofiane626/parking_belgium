"""
Seed a default CommunePermitPolicy for every (commune, permit_type) combination
so that admins can immediately tweak per-commune rules without having to create
each row by hand.
"""
import datetime as dt

from django.db import migrations


PERMIT_TYPES = [
    ("resident", 1000),
    ("visitor", 0),
    ("professional", 5000),
]


def seed(apps, schema_editor):
    Commune = apps.get_model("core", "Commune")
    Policy = apps.get_model("permits", "CommunePermitPolicy")
    today = dt.date.today()
    for commune in Commune.objects.all():
        for permit_type, default_price in PERMIT_TYPES:
            Policy.objects.get_or_create(
                commune=commune,
                permit_type=permit_type,
                effective_from=today,
                defaults={
                    "is_enabled": True,
                    "auto_attribution": True,
                    "validity_days": 365,
                    "price_strategy": "fixed",
                    "price_fixed_cents": default_price,
                    "max_active_per_citizen": None,  # unlimited by default
                    "max_vehicles_per_card": 1 if permit_type != "professional" else None,
                    "notes": "Politique par défaut générée automatiquement.",
                },
            )


def unseed(apps, schema_editor):
    Policy = apps.get_model("permits", "CommunePermitPolicy")
    Policy.objects.filter(notes__startswith="Politique par défaut").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("permits", "0004_alter_permitconfig_options_and_more"),
        ("core", "0002_seed_communes"),
    ]
    operations = [migrations.RunPython(seed, unseed)]
