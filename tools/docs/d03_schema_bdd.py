"""
Document 03 — Schéma de base de données.

Liste les tables avec leurs relations exprimées en phrases naturelles
selon la convention demandée (« Un X appartient à plusieurs Y - Un Y possède
plusieurs X [cardinalité] »).
"""
from __future__ import annotations

from .pdf_base import PBPdf, save_to


def generate() -> str:
    pdf = PBPdf(
        title="Schéma de base de données",
        subtitle="Relations entre les tables — modèle relationnel PostgreSQL/PostGIS",
    )
    pdf.cover()

    # ----- Vue d'ensemble -----------------------------------------------
    pdf.h1("1. Vue d'ensemble")
    pdf.p(
        "Le modèle de données s'articule autour de 17 tables groupées en 7 "
        "domaines fonctionnels : référentiel géographique (communes + données "
        "GIS), comptes utilisateurs, identité civile (profil + adresse), parc "
        "véhicules, entreprises, cycle de vie des cartes (permits + zones + "
        "codes visiteurs + politiques), paiements et journalisation d'audit."
    )
    pdf.p(
        "Le SGBD est PostgreSQL 17 avec l'extension PostGIS 3.6 pour les "
        "objets géographiques (points géocodés EPSG:31370, polygones de zones). "
        "Tous les modèles sont gérés via Django ORM (CODE FIRST) : migrations "
        "incrémentales, fixtures de seed, contraintes d'intégrité référentielle "
        "déclarées via ForeignKey."
    )

    pdf.h2("Liste des tables")
    pdf.table(
        headers=["Domaine", "Tables"],
        rows=[
            ["Référentiel", "core_commune"],
            ["GIS", "gis_data_gissourceversion, gis_data_gispolygon, rules_polygonrule"],
            ["Comptes", "accounts_user (custom)"],
            ["Identité civile", "citizens_citizenprofile, citizens_address, citizens_addresschangerequest"],
            ["Véhicules", "vehicles_vehicle, vehicles_platechangerequest"],
            ["Entreprises", "companies_company"],
            ["Cartes", "permits_permit, permits_permitzone, permits_visitorcode, permits_permitconfig, permits_communepermitpolicy"],
            ["Paiements", "payments_payment"],
            ["Audit", "audit_auditlog"],
            ["Auth (Django)", "auth_group, auth_permission, authtoken_token, django_session"],
        ],
        col_widths=[40, 134],
    )

    # ----- Diagramme ASCII -----------------------------------------------
    pdf.h1("2. Diagramme relationnel")
    pdf.p(
        "Vue simplifiée des principales associations métier (les relations "
        "Django technique vers auth_user sont implicites pour la lisibilité) :"
    )
    pdf.code(
        "Commune ────* Address                              \n"
        "   │            │                                   \n"
        "   │            │  (1 user → 1 profile → 1 address) \n"
        "   │            │                                   \n"
        "   │       CitizenProfile ─── 1 ─── User           \n"
        "   │            │                    │             \n"
        "   │            │                    └─* Vehicle   \n"
        "   │            └─* AddressChangeReq    │           \n"
        "   │                                    └─* Permit \n"
        "   │                                         │     \n"
        "   *────* CommunePermitPolicy                │     \n"
        "                                             │     \n"
        "                                             ├─* PermitZone   \n"
        "                                             ├─* VisitorCode  \n"
        "                                             └─1 Payment      \n"
        "                                                              \n"
        "GISSourceVersion ─* GISPolygon ─* PolygonRule                 \n"
        "                       │                                      \n"
        "                       └─ source_polygon de Permit            \n"
        "                                                              \n"
        "User ─* AuditLog (actor)                                      \n"
        "Permit/Payment/Vehicle… ─ target_id de AuditLog (générique)   \n"
    )

    # ----- Relations détaillées -------------------------------------------
    pdf.h1("3. Énoncé des relations")
    pdf.p("Chaque relation est exprimée en phrase naturelle avec la cardinalité.")

    pdf.h2("Référentiel géographique")
    pdf.bullet("Une commune dessert plusieurs adresses — Une adresse appartient à une seule commune [1-*]")
    pdf.bullet("Une commune comporte plusieurs polygones GIS — Un polygone GIS appartient à une seule commune [1-*]")
    pdf.bullet("Une commune possède plusieurs politiques — Une politique cible une seule commune [1-*]")
    pdf.bullet("Une commune peut être ciblée par plusieurs cartes pro — Une carte pro cible 0 ou 1 commune [0-1 - *]")

    pdf.h2("Comptes et identité civile")
    pdf.bullet("Un utilisateur possède un seul profil citoyen — Un profil appartient à un seul utilisateur [1-1]")
    pdf.bullet("Un profil possède une seule adresse principale — Une adresse appartient à un seul profil [1-1]")
    pdf.bullet("Un profil émet plusieurs demandes de changement d'adresse — Une demande appartient à un seul profil [1-*]")
    pdf.bullet("Un utilisateur est l'acteur de plusieurs entrées d'audit — Une entrée d'audit a 0 ou 1 acteur [0-1 - *] (null = action système)")

    pdf.h2("Véhicules et entreprises")
    pdf.bullet("Un utilisateur possède plusieurs véhicules — Un véhicule appartient à un seul utilisateur [1-*]")
    pdf.bullet("Un véhicule peut faire l'objet de plusieurs demandes de changement de plaque — Une demande de plaque vise un seul véhicule [1-*]")
    pdf.bullet("Un utilisateur possède plusieurs entreprises — Une entreprise appartient à un seul utilisateur [1-*]")

    pdf.h2("Cartes de stationnement")
    pdf.bullet("Un utilisateur possède plusieurs cartes — Une carte appartient à un seul utilisateur (le citoyen) [1-*]")
    pdf.bullet("Un véhicule peut être lié à plusieurs cartes successives — Une carte est liée à 0 ou 1 véhicule (les cartes visiteurs n'ont pas de véhicule fixe) [0-1 - *]")
    pdf.bullet("Une entreprise peut être liée à plusieurs cartes pro — Une carte pro est liée à 0 ou 1 entreprise [0-1 - *]")
    pdf.bullet("Une carte possède plusieurs zones — Une zone permit appartient à une seule carte [1-*]")
    pdf.bullet("Une carte (visiteur) génère plusieurs codes visiteurs — Un code visiteur appartient à une seule carte [1-*]")
    pdf.bullet("Une carte (resident) peut générer un changement d'adresse par un événement — Une carte est suspendue par un changement validé [*-*]")
    pdf.bullet("Un polygone GIS sert de source d'attribution pour plusieurs cartes — Une carte référence 0 ou 1 polygone source [0-1 - *]")

    pdf.h2("Politiques et règles")
    pdf.bullet("Une commune × type de carte est régie par plusieurs politiques (avec périodes successives) — Une politique cible une seule (commune, type) [1-*]")
    pdf.bullet("Un polygone GIS porte plusieurs règles d'attribution — Une règle s'applique à un seul polygone [1-*]")

    pdf.h2("Paiements")
    pdf.bullet("Une carte est payée par exactement un paiement réussi — Un paiement référence une seule carte [1-1] (contrainte unique partielle sur status=succeeded)")
    pdf.bullet("Un utilisateur a effectué plusieurs paiements — Un paiement est effectué par un seul utilisateur (citoyen) [1-*]")

    pdf.h2("Versions GIS")
    pdf.bullet("Une version GIS contient plusieurs polygones — Un polygone appartient à une seule version [1-*]")
    pdf.bullet("Plusieurs versions GIS peuvent coexister — Une seule est active à la fois (contrainte applicative + index conditionnel)")

    pdf.h2("Audit")
    pdf.bullet("Une entrée d'audit cible un objet quelconque via (target_type, target_id) — Un objet métier peut être référencé par plusieurs entrées d'audit [*-*] (relation polymorphique technique, pas de FK stricte)")

    # ----- Contraintes d'intégrité ---------------------------------------
    pdf.h1("4. Contraintes d'intégrité référentielle")

    pdf.h2("Contraintes ON DELETE")
    pdf.table(
        headers=["Relation", "Action ON DELETE", "Justification"],
        rows=[
            ["User → CitizenProfile", "CASCADE", "Le profil n'a pas de sens sans user"],
            ["User → Vehicle.owner", "CASCADE", "Idem — les véhicules sont liés à un user actif"],
            ["User → Permit.citizen", "PROTECT", "Refus si l'user a des cartes : préserve l'historique comptable"],
            ["User → Payment.citizen", "PROTECT", "Idem (obligation TVA 7 ans)"],
            ["User → AuditLog.actor", "SET_NULL", "Préserve l'audit même si l'user est supprimé"],
            ["Commune → Address", "PROTECT", "Refus si des adresses pointent encore dessus"],
            ["Commune → CommunePermitPolicy", "CASCADE", "Pas de politique orpheline"],
            ["GISSourceVersion → GISPolygon", "CASCADE", "Versions atomiques (purge complète)"],
            ["GISPolygon → PolygonRule", "CASCADE", "Pas de règle orpheline"],
            ["GISPolygon → Permit.source_polygon", "SET_NULL", "Préserve la carte si on supprime un polygone"],
            ["Vehicle → Permit.vehicle", "PROTECT", "Pas de suppression d'un véhicule lié à une carte active"],
            ["Permit → PermitZone", "CASCADE", "Les zones suivent le cycle de la carte"],
            ["Permit → VisitorCode", "CASCADE", "Idem pour les codes visiteurs"],
            ["Permit → Payment.permit", "PROTECT", "Préserve la trace comptable"],
        ],
        col_widths=[55, 30, 89],
    )

    pdf.h2("Contraintes UNIQUE")
    pdf.bullet("User.username — unique (auth Django).")
    pdf.bullet("CitizenProfile.user — OneToOne (1-1 strict).")
    pdf.bullet("CitizenProfile.national_number — unique (un seul citoyen par n° RN).")
    pdf.bullet("Vehicle (owner, plate) — unique partiel where archived_at IS NULL (une plaque active par citoyen).")
    pdf.bullet("Payment (permit, status=succeeded) — unique partiel (un seul paiement réussi par carte).")
    pdf.bullet("CommunePermitPolicy (commune, permit_type, effective_from) — unique (versionnement temporel).")
    pdf.bullet("GISPolygon (version, zonecode, niscode) — unique partiel (déduplication intra-version).")
    pdf.bullet("Token.user — unique (un seul token actif par user back-office).")

    pdf.h2("Index de performance")
    pdf.bullet("Permit (status) — filtrage rapide par état (back-office queues).")
    pdf.bullet("Permit (citizen, status) — dashboard citoyen.")
    pdf.bullet("Permit (vehicle, status) — recherche par véhicule.")
    pdf.bullet("VisitorCode (plate, valid_from, valid_until) — endpoint check-right (lookup par plaque).")
    pdf.bullet("VisitorCode (permit, status) — liste des codes actifs.")
    pdf.bullet("GISPolygon.geometry — index GIST (PostGIS) pour les opérations point-in-polygon.")
    pdf.bullet("Address.location — index GIST pour la géolocalisation inversée.")
    pdf.bullet("AuditLog (created_at) — pagination par cursor + recherche temporelle.")
    pdf.bullet("AuditLog (target_type, target_id) — recherche par cible.")

    # ----- Stratégie de versionning -------------------------------------
    pdf.h1("5. Stratégie de versionning et migrations")

    pdf.h2("Migrations Django")
    pdf.p(
        "Toute évolution du schéma passe par une migration Django (commande "
        "makemigrations) avec un nom métier descriptif. Les migrations sont "
        "versionnées dans git (apps/<x>/migrations/), nommées de manière "
        "séquentielle (0001_initial, 0002_<verbe>, ...) et peuvent être "
        "rejouées sur n'importe quel environnement (dev, staging, production)."
    )

    pdf.h2("Données seedées")
    pdf.p(
        "Certaines tables sont peuplées par des migrations de données :"
    )
    pdf.bullet("core.0002_seed_communes — peuple les 19 communes (niscode, name_fr, name_nl).")
    pdf.bullet("core.0004_seed_commune_postal_codes — ajoute les codes postaux 1000-1299.")
    pdf.bullet("permits.0005_seed_default_commune_policies — politique par défaut pour chaque commune × type de carte.")

    pdf.h2("Versions GIS")
    pdf.p(
        "Les données GIS (polygones de zones) sont versionnées explicitement "
        "via la table GISSourceVersion : chaque import crée une nouvelle "
        "version, et un seul flag is_active=True à la fois. Cela permet une "
        "cohabitation des versions pendant les transitions et un rollback "
        "immédiat en cas de problème d'import."
    )

    return str(save_to(pdf, "03_schema_base_de_donnees.pdf"))


if __name__ == "__main__":
    print(generate())
