"""
Seed demo data: citizens, vehicles, companies, permits in varied states.

Idempotent — every demo account is prefixed with ``demo_`` so re-running the
command upserts safely. Use ``--reset`` to wipe demo data first.

Usage:
    python manage.py seed_demo               # seeds 100 citizens + 3 agents + 2 admins
    python manage.py seed_demo --citizens 50
    python manage.py seed_demo --reset       # delete demo_* accounts first
"""
from __future__ import annotations

import datetime as dt
import random
import string

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role
from apps.citizens.models import Address, CitizenProfile
from apps.companies.models import Company
from apps.core.models import Commune
from apps.gis_data.models import GISPolygon
from apps.permits.models import Permit, PermitStatus, PermitType, PermitZone, ZoneSource
from apps.permits.services import (
    create_draft, create_visitor_permit, generate_visitor_code,
    mark_paid, submit_application,
)
from apps.vehicles.models import Vehicle

User = get_user_model()

FIRST_NAMES = [
    "Alice", "Bruno", "Camille", "Diane", "Emma", "François", "Gabrielle",
    "Hugo", "Inès", "Julien", "Karine", "Louis", "Marine", "Nathan",
    "Olivia", "Pierre", "Quentin", "Romane", "Samuel", "Thomas", "Ulysse",
    "Valentine", "Wassim", "Xavier", "Yasmine", "Zoé", "Antoine", "Béatrice",
    "Charles", "Delphine", "Étienne", "Fatima", "Grégoire", "Hélène",
    "Ismaël", "Joséphine", "Léon", "Manon", "Noah", "Océane",
]
LAST_NAMES = [
    "Dupont", "Martin", "Dubois", "Lambert", "Lefèvre", "Moreau", "Janssens",
    "Peeters", "Maes", "Hermans", "Van Damme", "De Smet", "De Vos",
    "Vermeulen", "Willems", "Mertens", "Claes", "Wouters", "Goossens",
    "Pauwels", "Dumont", "Dubois", "Bernard", "Petit", "Robert", "Richard",
    "Durand", "Leroy", "Moreau", "Simon", "Laurent", "Lefebvre", "Michel",
    "Garcia", "Roux", "Vincent", "Fournier", "Morel", "Girard", "André",
]
STREETS = [
    "Rue de la Loi", "Avenue Louise", "Boulevard Anspach", "Chaussée d'Ixelles",
    "Rue Neuve", "Avenue de Tervueren", "Boulevard du Souverain", "Rue Royale",
    "Avenue de la Toison d'Or", "Chaussée de Wavre", "Rue Haute",
    "Avenue Brugmann", "Boulevard Lambermont", "Rue de Flandre",
    "Avenue de la Couronne", "Chaussée de Mons", "Rue du Marché",
    "Avenue Roosevelt", "Boulevard Léopold II", "Rue de la Madeleine",
    "Place Sainte-Catherine", "Rue Antoine Dansaert",
]
BRANDS_MODELS = [
    ("Renault", "Clio"), ("Renault", "Mégane"), ("Renault", "Captur"),
    ("Peugeot", "208"), ("Peugeot", "308"), ("Peugeot", "3008"),
    ("Citroën", "C3"), ("Citroën", "C4"), ("Citroën", "Berlingo"),
    ("Volkswagen", "Polo"), ("Volkswagen", "Golf"), ("Volkswagen", "Passat"),
    ("BMW", "Série 1"), ("BMW", "Série 3"), ("BMW", "X1"),
    ("Audi", "A3"), ("Audi", "A4"), ("Audi", "Q3"),
    ("Mercedes", "Classe A"), ("Mercedes", "Classe C"),
    ("Toyota", "Yaris"), ("Toyota", "Corolla"), ("Toyota", "RAV4"),
    ("Skoda", "Fabia"), ("Skoda", "Octavia"),
    ("Opel", "Corsa"), ("Opel", "Astra"),
    ("Fiat", "500"), ("Fiat", "Panda"),
    ("Tesla", "Model 3"),
]
COLORS = ["noir", "blanc", "gris", "rouge", "bleu", "vert", "jaune"]

ACTIVITIES = [
    "Plomberie", "Électricité", "Avocat", "Notaire", "Médecin généraliste",
    "Dentiste", "Kinésithérapeute", "Restauration", "Boulangerie",
    "Coiffure", "Architecte", "Graphiste indépendant", "Consultant IT",
    "Photographe", "Traducteur", "Soins à domicile", "Plomberie chauffage",
    "Décoration intérieure", "Coursier", "Livraison",
]

# Approximate commune-level postal codes (1 per niscode for the seed; the real
# territory has multiple postal codes per commune but this is enough for demo).
COMMUNE_POSTAL = {
    "21001": "1070", "21002": "1160", "21003": "1082", "21004": "1000",
    "21005": "1040", "21006": "1140", "21007": "1190", "21008": "1083",
    "21009": "1050", "21010": "1090", "21011": "1081", "21012": "1080",
    "21013": "1060", "21014": "1210", "21015": "1030", "21016": "1180",
    "21017": "1170", "21018": "1200", "21019": "1150",
}


class Command(BaseCommand):
    help = "Seed demo data: citizens, vehicles, companies, permits in varied states."

    def add_arguments(self, parser):
        parser.add_argument("--citizens", type=int, default=100)
        parser.add_argument("--reset", action="store_true",
                            help="Delete existing demo_* accounts first.")
        parser.add_argument("--seed", type=int, default=42, help="Random seed.")

    def handle(self, *args, **options):
        random.seed(options["seed"])
        n = options["citizens"]
        if options["reset"]:
            deleted = User.objects.filter(username__startswith="demo_").delete()
            self.stdout.write(self.style.WARNING(f"Reset: deleted {deleted[0]} rows."))

        # Communes that have at least one active polygon (avoids permit creation
        # failures for empty communes).
        communes_with_polygons = list(
            Commune.objects.filter(
                gis_polygons__version__is_active=True,
            ).distinct()
        )
        if not communes_with_polygons:
            self.stdout.write(self.style.ERROR(
                "No GIS polygons imported — run import_gis first."
            ))
            return

        # Pre-compute one centroid per commune (in EPSG:31370).
        centroids = {}
        for commune in communes_with_polygons:
            poly = GISPolygon.objects.filter(
                version__is_active=True, commune=commune,
            ).first()
            if poly:
                c = poly.geometry.centroid
                centroids[commune.pk] = (c.x, c.y)

        created_users = 0
        created_vehicles = 0
        created_permits = 0
        created_codes = 0

        for i in range(n):
            username = f"demo_{i:03d}"
            if User.objects.filter(username=username).exists():
                continue

            user = self._create_citizen(username)
            commune = random.choice(communes_with_polygons)
            self._create_address(user, commune, centroids.get(commune.pk))
            created_users += 1

            # 0–3 vehicles, weighted distribution
            n_vehicles = random.choices([0, 1, 2, 3], weights=[20, 50, 25, 5])[0]
            for _ in range(n_vehicles):
                v = self._create_vehicle(user)
                if v:
                    created_vehicles += 1

            # 30% have a company
            if random.random() < 0.30:
                self._create_company(user, commune)

            # If they have vehicles, 60% submit a resident permit
            vehicles = list(user.vehicles.all())
            if vehicles and random.random() < 0.60:
                permit = self._submit_resident_permit(user, vehicles[0])
                if permit:
                    created_permits += 1
                    # 50% pay it (becomes ACTIVE)
                    if permit.status == PermitStatus.AWAITING_PAYMENT and random.random() < 0.5:
                        try:
                            mark_paid(permit)
                            # Of those, 40% activate the visitor card too
                            if random.random() < 0.40:
                                v_permit = create_visitor_permit(user)
                                created_permits += 1
                                # generate a few visitor codes
                                for _ in range(random.randint(0, 5)):
                                    try:
                                        generate_visitor_code(
                                            v_permit,
                                            plate=self._random_plate(),
                                            duration_hours=random.choice([1, 2, 4, 8, 12, 24]),
                                        )
                                        created_codes += 1
                                    except Exception:
                                        pass
                        except Exception:
                            pass

        # Back-office accounts
        self._create_back_office("demo_agent_alice", Role.AGENT, "Alice", "Agent")
        self._create_back_office("demo_agent_bob", Role.AGENT, "Bob", "Agent")
        self._create_back_office("demo_agent_carla", Role.AGENT, "Carla", "Agent")
        self._create_back_office("demo_admin", Role.ADMIN, "Diana", "Admin")
        self._create_back_office("demo_super", Role.SUPER_ADMIN, "Erik", "Super")

        self.stdout.write(self.style.SUCCESS(
            f"Seed terminé : {created_users} citoyens, {created_vehicles} véhicules, "
            f"{created_permits} cartes, {created_codes} codes visiteurs. "
            f"Mot de passe démo : Demo!2026"
        ))

    # ----- helpers -----

    def _create_citizen(self, username: str) -> User:
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        user = User.objects.create_user(
            username=username,
            email=f"{username}@demo.parking.belgium",
            password="Demo!2026",
            first_name=first,
            last_name=last,
        )
        user.role = Role.CITIZEN
        user.save()
        return user

    def _create_address(self, user, commune: Commune, centroid: tuple | None) -> None:
        profile, _ = CitizenProfile.objects.get_or_create(user=user)
        dob_year = random.randint(1955, 2003)
        profile.date_of_birth = dt.date(
            dob_year, random.randint(1, 12), random.randint(1, 28),
        )
        profile.phone = f"+324{random.randint(70000000, 99999999)}"
        profile.national_number = (
            f"{profile.date_of_birth.strftime('%y.%m.%d')}-"
            f"{random.randint(100, 999)}.{random.randint(10, 99)}"
        )
        profile.save()

        location = None
        if centroid:
            x, y = centroid
            location = Point(x, y, srid=31370)

        Address.objects.update_or_create(
            profile=profile,
            defaults=dict(
                street=random.choice(STREETS),
                number=str(random.randint(1, 250)),
                box="" if random.random() < 0.7 else str(random.randint(1, 25)),
                postal_code=COMMUNE_POSTAL.get(commune.niscode, "1000"),
                commune=commune,
                country="BE",
                location=location,
            ),
        )

    def _random_plate(self) -> str:
        letters = "".join(random.choices(string.ascii_uppercase, k=3))
        digits = "".join(random.choices(string.digits, k=3))
        return f"1-{letters}-{digits}"

    def _create_vehicle(self, user) -> Vehicle | None:
        for _ in range(5):  # up to 5 attempts to avoid plate collisions
            plate = self._random_plate()
            if Vehicle.objects.filter(plate=plate).exists():
                continue
            brand, model = random.choice(BRANDS_MODELS)
            return Vehicle.objects.create(
                owner=user,
                plate=plate,
                brand=brand,
                model=model,
                color=random.choice(COLORS),
            )
        return None

    def _create_company(self, user, commune: Commune) -> Company | None:
        # VAT must be unique per (owner, vat). Use a random valid-shaped one.
        for _ in range(5):
            vat = f"BE0{random.randint(100000000, 999999999)}"
            if Company.objects.filter(vat_number=vat).exists():
                continue
            return Company.objects.create(
                owner=user,
                name=f"{user.last_name} {random.choice(['Sàrl', '& Co', 'SPRL', 'Indep.'])}",
                vat_number=vat,
                activity=random.choice(ACTIVITIES),
                street=random.choice(STREETS),
                number=str(random.randint(1, 250)),
                box="",
                postal_code=COMMUNE_POSTAL.get(commune.niscode, "1000"),
                commune=commune,
                country="BE",
            )
        return None

    def _submit_resident_permit(self, user, vehicle) -> Permit | None:
        try:
            permit = create_draft(user, vehicle, PermitType.RESIDENT)
            return submit_application(permit)
        except Exception as exc:
            self.stdout.write(self.style.WARNING(
                f"  ↳ resident skipped for {user.username}: {exc}"
            ))
            return None

    def _create_back_office(self, username: str, role: str, first: str, last: str) -> None:
        user, _ = User.objects.update_or_create(
            username=username,
            defaults=dict(
                email=f"{username}@demo.parking.belgium",
                first_name=first,
                last_name=last,
                role=role,
            ),
        )
        user.set_password("Demo!2026")
        user.save()
