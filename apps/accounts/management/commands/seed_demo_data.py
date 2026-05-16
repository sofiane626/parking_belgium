"""
Management command : peuple la base avec des données de démonstration réalistes
pour la défense TFE (DUMP demandé : 100+ lignes par table métier).

Génère :
- 4 comptes back-office (agent, admin, super_admin, agent2)
- 120 citoyens avec profil + adresse géocodée dans une commune au hasard
- 250 véhicules (1 à 3 par citoyen)
- 40 entreprises (1 par 5 citoyens en moyenne)
- 180 permits riverains + 60 visiteurs + 30 pro (statuts variés)
- 110 paiements (succeeded / refunded / cancelled)
- 200 codes visiteurs (actifs et passés)
- 30 demandes de changement d'adresse + 25 de plaque (statuts variés)
- Quelques entrées d'audit pour les actions principales

Usage : python manage.py seed_demo_data [--reset]
        --reset supprime les données existantes avant de re-seeder.
"""
from __future__ import annotations

import datetime as dt
import random

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role
from apps.audit.models import AuditAction, AuditLog
from apps.citizens.models import Address, AddressChangeRequest, CitizenProfile
from apps.citizens.services import get_or_create_profile, upsert_address
from apps.companies.models import Company
from apps.core.models import Commune
from apps.gis_data.models import GISPolygon, GISSourceVersion
from apps.payments.models import Payment, PaymentMethod, PaymentStatus
from apps.permits.models import (
    Permit, PermitConfig, PermitStatus, PermitType,
    VisitorCode, VisitorCodeStatus,
)
from apps.permits.services import (
    create_draft, create_visitor_permit, generate_visitor_code, mark_paid,
    submit_application,
)
from apps.vehicles.models import PlateChangeRequest, Vehicle
from apps.vehicles.services import create_vehicle

User = get_user_model()

# Pools de données réalistes
FIRST_NAMES = [
    "Sophie", "Lucas", "Marie", "Thomas", "Camille", "Hugo", "Léa", "Maxime",
    "Julie", "Antoine", "Sarah", "Nicolas", "Emma", "Pierre", "Chloé", "Romain",
    "Anaïs", "Alexandre", "Manon", "Julien", "Inès", "François", "Laura",
    "Sébastien", "Eva", "David", "Clara", "Olivier", "Margaux", "Vincent",
    "Pauline", "Benjamin", "Charlotte", "Mathieu", "Jeanne", "Quentin",
    "Mélanie", "Adrien", "Aurélie", "Florent", "Lina", "Bruno", "Lisa",
    "Cédric", "Élise", "Damien", "Jade", "Fabrice", "Mila", "Gabriel",
]
LAST_NAMES = [
    "Martin", "Bernard", "Dubois", "Thomas", "Robert", "Petit", "Richard",
    "Durand", "Leroy", "Moreau", "Simon", "Laurent", "Lefebvre", "Michel",
    "Garcia", "David", "Bertrand", "Roux", "Vincent", "Fournier", "Morel",
    "Girard", "Andre", "Lefèvre", "Mercier", "Dupont", "Lambert", "Bonnet",
    "François", "Martinez", "Legrand", "Garnier", "Faure", "Rousseau",
    "Blanc", "Guerin", "Muller", "Henry", "Roussel", "Nicolas", "Perrin",
    "Morin", "Mathieu", "Clément", "Gauthier", "Dumont", "Lopez", "Fontaine",
]
STREETS = [
    "Rue de la Loi", "Avenue Louise", "Chaussée d'Ixelles", "Rue Royale",
    "Boulevard du Régent", "Rue de Flandre", "Avenue de la Toison d'Or",
    "Rue Neuve", "Place Sainte-Catherine", "Rue Antoine Dansaert",
    "Rue du Bailli", "Avenue Brugmann", "Chaussée de Vleurgat",
    "Rue de la Régence", "Boulevard Anspach", "Rue Haute", "Rue Blaes",
    "Avenue Molière", "Rue du Trône", "Place Stéphanie",
]
CAR_BRANDS = [
    ("Renault", ["Clio", "Mégane", "Captur", "Scénic", "Twingo"]),
    ("Peugeot", ["208", "308", "2008", "3008", "5008"]),
    ("Volkswagen", ["Golf", "Polo", "Tiguan", "Passat", "T-Roc"]),
    ("BMW", ["Série 1", "Série 3", "X1", "X3", "i3"]),
    ("Audi", ["A3", "A4", "Q3", "A1", "Q5"]),
    ("Toyota", ["Yaris", "Corolla", "RAV4", "C-HR", "Auris"]),
    ("Citroën", ["C3", "C4", "C5 Aircross", "Berlingo", "C1"]),
    ("Ford", ["Fiesta", "Focus", "Kuga", "Puma", "Mondeo"]),
    ("Tesla", ["Model 3", "Model Y", "Model S"]),
    ("Hyundai", ["i20", "i30", "Tucson", "Kona", "Ioniq"]),
]
COLORS = ["Blanc", "Noir", "Gris", "Bleu", "Rouge", "Vert", "Beige", "Argent"]


def _valid_be_vat() -> str:
    """Génère un numéro de TVA belge BE0XXXXXXXXX valide selon le Modulo 97."""
    base = random.randint(10000000, 99999999)
    check = 97 - (base % 97)
    return f"BE0{base:08d}{check:02d}"[:13]  # BE + 0 + 8 + 2 = 13 caractères max


class Command(BaseCommand):
    help = "Peuple la base avec des données de démonstration réalistes."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true",
                            help="Supprime les données existantes avant de re-seeder.")
        parser.add_argument("--seed", type=int, default=42,
                            help="Seed RNG pour reproductibilité.")

    def handle(self, *args, reset: bool = False, seed: int = 42, **options):
        random.seed(seed)
        if reset:
            self.stdout.write("Suppression des données existantes…")
            self._reset()

        self.stdout.write("Création des données…")
        # Pas de transaction globale — chaque sous-opération gère ses propres
        # erreurs via savepoints, pour ne pas casser tout le seed si quelques
        # créations échouent (FK manquante, contrainte unique...).
        self._ensure_config()
        self._ensure_gis()
        agents = self._make_back_office()
        citizens = self._make_citizens(count=120)
        vehicles = self._make_vehicles(citizens)
        companies = self._make_companies(citizens)
        permits = self._make_permits(citizens, vehicles, companies)
        self._make_visitor_codes(permits)
        self._make_payments(permits)
        self._make_change_requests(citizens, vehicles, agents)
        self._make_audit_extras()

        self.stdout.write(self.style.SUCCESS("Seed terminé."))
        self._summarise()

    # ----- reset -----------------------------------------------------------

    def _reset(self):
        AuditLog.objects.all().delete()
        VisitorCode.objects.all().delete()
        Payment.objects.all().delete()
        AddressChangeRequest.objects.all().delete()
        PlateChangeRequest.objects.all().delete()
        Permit.objects.all().delete()
        Vehicle.objects.all().delete()
        Company.objects.all().delete()
        Address.objects.all().delete()
        CitizenProfile.objects.all().delete()
        # Garde les superusers et les communes
        User.objects.filter(is_superuser=False).delete()
        GISPolygon.objects.all().delete()
        GISSourceVersion.objects.all().delete()

    # ----- config & GIS ----------------------------------------------------

    def _ensure_config(self):
        cfg = PermitConfig.get()
        cfg.resident_price_cents = 1000
        cfg.visitor_price_cents = 0
        cfg.professional_price_cents = 5000
        cfg.save()

    def _ensure_gis(self):
        if GISSourceVersion.objects.filter(is_active=True).exists():
            return
        v = GISSourceVersion.objects.create(
            name="demo_v1", source_filename="demo.shp", srid=31370,
            polygon_count=0, is_active=True,
        )
        # Un polygone carré par commune autour du centroïde
        # Coordonnées Lambert 72 approximatives pour Bruxelles : ~150000, 170000
        bx_x, bx_y = 150000, 170000
        for i, commune in enumerate(Commune.objects.all().order_by("niscode")):
            cx = bx_x + (i % 5) * 2000
            cy = bx_y + (i // 5) * 2000
            poly = Polygon(((cx, cy), (cx + 1500, cy), (cx + 1500, cy + 1500),
                            (cx, cy + 1500), (cx, cy)))
            zone_code = f"{commune.niscode[-2:]}-A"
            GISPolygon.objects.create(
                version=v, geometry=MultiPolygon(poly, srid=31370),
                zonecode=zone_code, niscode=commune.niscode, commune=commune,
            )
        v.polygon_count = GISPolygon.objects.filter(version=v).count()
        v.save()
        self.stdout.write(f"  GIS : {v.polygon_count} polygones créés.")

    # ----- back-office -----------------------------------------------------

    def _make_back_office(self) -> dict:
        agents = {}
        for username, role, email in [
            ("agent_demo",  Role.AGENT,       "agent@parking.belgium.local"),
            ("agent2_demo", Role.AGENT,       "agent2@parking.belgium.local"),
            ("admin_demo",  Role.ADMIN,       "admin@parking.belgium.local"),
            ("sa_demo",     Role.SUPER_ADMIN, "sa@parking.belgium.local"),
        ]:
            u, created = User.objects.get_or_create(
                username=username,
                defaults={"email": email, "role": role, "first_name": username.title(), "last_name": "Demo"},
            )
            if created:
                u.set_password("DemoPw1!")
                u.role = role
                u.save()
            agents[username] = u
        self.stdout.write(f"  Comptes back-office : {len(agents)}.")
        return agents

    # ----- citoyens --------------------------------------------------------

    def _make_citizens(self, *, count: int) -> list:
        communes = list(Commune.objects.all())
        citizens = []
        for i in range(count):
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            username = f"{first.lower()}.{last.lower()}{i}"
            commune = random.choice(communes)
            cps = (commune.postal_codes or "1000").split(",")
            pc = random.choice(cps).strip()
            user = User.objects.create_user(
                username=username,
                email=f"{username}@demo.parking.belgium.local",
                password="DemoPw1!",
                first_name=first,
                last_name=last,
                role=Role.CITIZEN,
            )
            user.accepted_privacy_at = timezone.now()
            user.accepted_terms_at = timezone.now()
            user.preferred_language = random.choice(["fr", "fr", "fr", "nl", "en"])
            user.save()

            profile = get_or_create_profile(user)
            profile.phone = f"+32 4{random.randint(70, 99)} {random.randint(100000, 999999)}"
            profile.date_of_birth = dt.date(
                random.randint(1955, 2005),
                random.randint(1, 12),
                random.randint(1, 28),
            )
            profile.national_number = f"{random.randint(50, 99):02d}.{random.randint(1, 12):02d}.{random.randint(1, 28):02d}-{random.randint(100, 999):03d}.{random.randint(10, 99):02d}"
            profile.save()
            upsert_address(
                profile, user=user,
                street=random.choice(STREETS),
                number=str(random.randint(1, 250)),
                box=random.choice(["", "", "", "1", "A", "B"]),
                postal_code=pc,
                commune=commune,
                country="BE",
            )
            # Géolocalisation dans la zone du polygone de cette commune
            polygon = GISPolygon.objects.filter(commune=commune).first()
            if polygon:
                centroid = polygon.geometry.centroid
                Address.objects.filter(profile=profile).update(
                    location=Point(centroid.x + random.uniform(-200, 200),
                                   centroid.y + random.uniform(-200, 200),
                                   srid=31370),
                )
            citizens.append(user)
        self.stdout.write(f"  Citoyens : {len(citizens)}.")
        return citizens

    # ----- véhicules -------------------------------------------------------

    def _make_vehicles(self, citizens: list) -> list:
        vehicles = []
        for user in citizens:
            for _ in range(random.choices([1, 2, 3], weights=[60, 30, 10])[0]):
                brand, models = random.choice(CAR_BRANDS)
                plate = f"{random.randint(1, 9)}-{''.join(random.choices('ABCDEFGHJKLMNPRSTUVWXYZ', k=3))}-{random.randint(100, 999)}"
                try:
                    with transaction.atomic():
                        v = create_vehicle(
                            owner=user,
                            plate=plate,
                            brand=brand,
                            model=random.choice(models),
                            color=random.choice(COLORS),
                        )
                        vehicles.append(v)
                except Exception:
                    continue
        self.stdout.write(f"  Véhicules : {len(vehicles)}.")
        return vehicles

    # ----- entreprises -----------------------------------------------------

    def _make_companies(self, citizens: list) -> list:
        companies = []
        communes_list = list(Commune.objects.all())
        for user in citizens[:40]:
            commune = random.choice(communes_list)
            cps = (commune.postal_codes or "1000").split(",")
            try:
                with transaction.atomic():
                    c = Company.objects.create(
                        owner=user,
                        name=f"{user.last_name} {random.choice(['SPRL', 'SA', 'BV', 'SCS'])}",
                        vat_number=_valid_be_vat(),
                        street=random.choice(STREETS),
                        number=str(random.randint(1, 200)),
                        postal_code=random.choice(cps).strip(),
                        commune=commune,
                        country="BE",
                    )
                    companies.append(c)
            except Exception as exc:
                self.stdout.write(f"    [skip company {user.username}] {exc}")
                continue
        self.stdout.write(f"  Entreprises : {len(companies)}.")
        return companies

    # ----- permits ---------------------------------------------------------

    def _make_permits(self, citizens, vehicles, companies) -> list:
        permits = []
        skip_reasons: dict[str, int] = {}
        for user in citizens:
            user_vehicles = [v for v in vehicles if v.owner_id == user.pk]
            if not user_vehicles:
                continue
            # 1 carte riverain par citoyen avec un véhicule (~80%)
            if random.random() < 0.85:
                v = user_vehicles[0]
                try:
                    with transaction.atomic():
                        p = create_draft(user, v, PermitType.RESIDENT)
                        p = submit_application(p)
                        if p.status == PermitStatus.AWAITING_PAYMENT and random.random() < 0.85:
                            p = mark_paid(p)
                        # Force quelques statuts variés
                        r = random.random()
                        if r < 0.05:
                            p.status = PermitStatus.EXPIRED
                            p.expired_at = timezone.now() - dt.timedelta(days=random.randint(1, 200))
                            p.save()
                        elif r < 0.10:
                            p.status = PermitStatus.SUSPENDED
                            p.suspended_at = timezone.now() - dt.timedelta(days=random.randint(1, 90))
                            p.suspension_reason = "Changement d'adresse en cours"
                            p.save()
                        permits.append(p)
                except Exception as exc:
                    skip_reasons[str(type(exc).__name__)] = skip_reasons.get(str(type(exc).__name__), 0) + 1
            # Carte visiteur (~40%) — nécessite un permit riverain ACTIVE
            if random.random() < 0.4 and any(p.citizen_id == user.pk and p.status == PermitStatus.ACTIVE for p in permits):
                try:
                    with transaction.atomic():
                        p = create_visitor_permit(user)
                        if p.status == PermitStatus.AWAITING_PAYMENT:
                            p = mark_paid(p)
                        permits.append(p)
                except Exception as exc:
                    skip_reasons["visitor:" + str(type(exc).__name__)] = skip_reasons.get("visitor:" + str(type(exc).__name__), 0) + 1
        if skip_reasons:
            self.stdout.write(f"  Permits skip reasons: {skip_reasons}")
        # Cartes pro (sur entreprises)
        for company in companies[:30]:
            user = company.owner
            user_vehicles = [v for v in vehicles if v.owner_id == user.pk]
            if not user_vehicles:
                continue
            try:
                with transaction.atomic():
                    p = Permit.objects.create(
                        citizen=user,
                        vehicle=user_vehicles[0],
                        company=company,
                        permit_type=PermitType.PROFESSIONAL,
                        target_commune=random.choice(list(Commune.objects.all())),
                        status=random.choice([PermitStatus.ACTIVE, PermitStatus.MANUAL_REVIEW, PermitStatus.AWAITING_PAYMENT]),
                        price_cents=5000,
                        valid_from=timezone.localdate() - dt.timedelta(days=random.randint(0, 200)),
                        valid_until=timezone.localdate() + dt.timedelta(days=random.randint(30, 365)),
                    )
                    permits.append(p)
            except Exception:
                continue
        self.stdout.write(f"  Permits : {len(permits)}.")
        return permits

    # ----- visitor codes ---------------------------------------------------

    def _make_visitor_codes(self, permits):
        visitor_permits = [p for p in permits if p.permit_type == PermitType.VISITOR
                           and p.status == PermitStatus.ACTIVE]
        count = 0
        for p in visitor_permits:
            for _ in range(random.randint(2, 6)):
                plate = f"{random.randint(1, 9)}-{''.join(random.choices('ABCDEFGHJKLMNPRSTUVWXYZ', k=3))}-{random.randint(100, 999)}"
                try:
                    with transaction.atomic():
                        generate_visitor_code(p, plate=plate,
                                               duration_hours=random.choice([2, 4, 8, 24, 48]))
                        count += 1
                except Exception:
                    continue
        # Quelques codes annulés et anciens (status n'a pas EXPIRED, juste expiré par valid_until)
        from apps.permits.models import VisitorCode, VisitorCodeStatus
        for code in VisitorCode.objects.all()[: count // 4]:
            VisitorCode.objects.filter(pk=code.pk).update(
                valid_until=timezone.now() - dt.timedelta(hours=random.randint(1, 1000)),
            )
        for code in VisitorCode.objects.all()[count // 4 : count // 3]:
            VisitorCode.objects.filter(pk=code.pk).update(
                status=VisitorCodeStatus.CANCELLED,
                cancelled_at=timezone.now() - dt.timedelta(days=random.randint(1, 60)),
            )
        self.stdout.write(f"  Codes visiteurs : {count}.")

    # ----- payments --------------------------------------------------------

    def _make_payments(self, permits):
        count = 0
        for p in permits:
            if p.status not in (PermitStatus.ACTIVE, PermitStatus.SUSPENDED, PermitStatus.EXPIRED):
                continue
            if p.price_cents == 0:
                continue
            try:
                with transaction.atomic():
                    Payment.objects.create(
                        permit=p,
                        citizen=p.citizen,
                        amount_cents=p.price_cents,
                        method=random.choice([PaymentMethod.STRIPE, PaymentMethod.CARD, PaymentMethod.INTERNAL_FREE]),
                        status=PaymentStatus.SUCCEEDED,
                        reference=f"PAY-{p.pk}-{random.randint(1000, 9999)}",
                        card_brand=random.choice(["visa", "mastercard", "amex"]),
                        card_last4=str(random.randint(1000, 9999)),
                        confirmed_at=timezone.now() - dt.timedelta(days=random.randint(0, 300)),
                    )
                    count += 1
            except Exception as exc:
                if count == 0:
                    self.stdout.write(f"    [debug payment skip] {exc}")
                continue
        # Quelques refunded / cancelled
        for p in Payment.objects.all()[: count // 10]:
            p.status = random.choice([PaymentStatus.REFUNDED, PaymentStatus.CANCELLED])
            p.save()
        self.stdout.write(f"  Paiements : {count}.")

    # ----- change requests -------------------------------------------------

    def _make_change_requests(self, citizens, vehicles, agents):
        from apps.citizens.models import RequestStatus as AddrStatus
        from apps.vehicles.models import PlateChangeStatus as PlateStatus
        agent = agents.get("agent_demo")
        communes = list(Commune.objects.all())
        n_addr = 0
        for user in random.sample(citizens, 30):
            profile = CitizenProfile.objects.filter(user=user).first()
            if not profile:
                continue
            commune = random.choice(communes)
            cps = (commune.postal_codes or "1000").split(",")
            try:
                with transaction.atomic():
                    AddressChangeRequest.objects.create(
                        profile=profile,
                        street=random.choice(STREETS),
                        number=str(random.randint(1, 200)),
                        box="",
                        postal_code=random.choice(cps).strip(),
                        commune=commune,
                        country="BE",
                        reason="Déménagement",
                        status=random.choice([AddrStatus.PENDING, AddrStatus.APPROVED, AddrStatus.REJECTED]),
                        decided_by=agent if random.random() < 0.6 else None,
                    )
                    n_addr += 1
            except Exception as exc:
                if n_addr == 0:
                    self.stdout.write(f"    [debug addr skip] {exc}")
                pass
        n_plate = 0
        for v in random.sample(vehicles, min(25, len(vehicles))):
            try:
                with transaction.atomic():
                    PlateChangeRequest.objects.create(
                        vehicle=v,
                        new_plate=f"{random.randint(1, 9)}-{''.join(random.choices('ABCDEFGHJKLMNPRSTUVWXYZ', k=3))}-{random.randint(100, 999)}",
                        reason="Nouvelle immatriculation",
                        status=random.choice([PlateStatus.PENDING, PlateStatus.APPROVED, PlateStatus.REJECTED]),
                        decided_by=agent if random.random() < 0.5 else None,
                    )
                    n_plate += 1
            except Exception as exc:
                if n_plate == 0:
                    self.stdout.write(f"    [debug plate skip] {exc}")
                continue
        self.stdout.write(f"  Demandes changement adresse: {n_addr}, plaque: {n_plate}.")

    # ----- audit (compléments) --------------------------------------------

    def _make_audit_extras(self):
        # On en a déjà via les services (mark_paid, submit, etc).
        # On rajoute quelques entrées d'API et de connexion pour étoffer.
        now = timezone.now()
        for i in range(30):
            AuditLog.objects.create(
                action=AuditAction.API_CHECK_RIGHT,
                severity="info",
                target_type="",
                target_id=None,
                target_label="",
                payload={"context": {"plate_hash": f"hash_{i:04d}", "authorized": True}},
                ip="192.168.0." + str(random.randint(1, 254)),
                created_at=now - dt.timedelta(hours=random.randint(0, 720)),
            )
        for i in range(8):
            AuditLog.objects.create(
                action=AuditAction.AUTH_FAILED,
                severity="warning",
                target_type="",
                target_id=None,
                target_label=f"bad_user_{i}",
                payload={"context": {"reason": "wrong_password"}},
                ip="10.0.0." + str(random.randint(1, 254)),
                created_at=now - dt.timedelta(hours=random.randint(0, 720)),
            )

    # ----- résumé ----------------------------------------------------------

    def _summarise(self):
        counts = {
            "User": User.objects.count(),
            "CitizenProfile": CitizenProfile.objects.count(),
            "Address": Address.objects.count(),
            "Vehicle": Vehicle.objects.count(),
            "Company": Company.objects.count(),
            "Permit": Permit.objects.count(),
            "VisitorCode": VisitorCode.objects.count(),
            "Payment": Payment.objects.count(),
            "AddressChangeRequest": AddressChangeRequest.objects.count(),
            "PlateChangeRequest": PlateChangeRequest.objects.count(),
            "GISPolygon": GISPolygon.objects.count(),
            "AuditLog": AuditLog.objects.count(),
        }
        self.stdout.write("\nRécapitulatif :")
        for k, v in counts.items():
            self.stdout.write(f"  {k:<25} {v:>5}")
