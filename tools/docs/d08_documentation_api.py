"""
Document 08 — Documentation de l'API et Open Data.

Présente l'architecture REST, les endpoints disponibles, l'authentification,
le versioning, le throttling et la stratégie Open Data.
"""
from __future__ import annotations

from .pdf_base import PBPdf, save_to


def generate() -> str:
    pdf = PBPdf(
        title="Documentation API & Open Data",
        subtitle="REST API publique /api/v1/ — endpoints, sécurité, ouverture des données",
    )
    pdf.cover()

    # ----- Architecture --------------------------------------------------
    pdf.h1("1. Architecture")

    pdf.h2("Style architectural")
    pdf.p(
        "L'API expose une interface REST conforme aux conventions standards : "
        "verbes HTTP (GET, POST), codes de statut explicites, ressources "
        "nommées au pluriel, format JSON pour les corps de requêtes et de "
        "réponses. Elle est construite sur Django REST Framework (DRF) 3.15 "
        "avec drf-spectacular pour la documentation auto-générée."
    )

    pdf.h2("Principes retenus")
    pdf.bullet("URLs versionnées dans le chemin : /api/v1/ (immutable jusqu'à la prochaine version majeure).")
    pdf.bullet("Authentification par Token DRF (header Authorization: Token <token>) — pas de sessions.")
    pdf.bullet("Format JSON uniquement (pas d'XML, pas de form-encoded en réponse).")
    pdf.bullet("Throttling configurable par scope (60/min user, 120/min check_right, 10/min anon).")
    pdf.bullet("Documentation auto-générée OpenAPI 3.1 (Swagger + Redoc).")
    pdf.bullet("Audit systématique des appels sensibles (check-right hashe la plaque avant log).")

    pdf.h2("Versioning")
    pdf.p(
        "L'API utilise un versioning par préfixe d'URL. La version actuelle "
        "est v1 (stable). Les changements rétro-compatibles (ajout de champs "
        "optionnels, nouveaux endpoints) sont ajoutés à v1 sans incrément. "
        "Les changements cassants (renommage de champ, suppression, "
        "changement de structure) déclenchent une v2 ; v1 reste accessible "
        "pendant au moins 12 mois après la sortie de v2 (politique de "
        "dépréciation). Aucune version n'est en cours de dépréciation à ce "
        "jour."
    )

    pdf.h2("Documentation auto-générée")
    pdf.bullet("Schéma OpenAPI brut : /api/v1/schema/ (YAML).")
    pdf.bullet("Swagger UI (interactif, Try it out) : /api/v1/docs/.")
    pdf.bullet("Redoc (présentation à plat, lecture confort) : /api/v1/redoc/.")
    pdf.p(
        "Les vues DRF utilisent les décorateurs @extend_schema de "
        "drf-spectacular pour enrichir la doc avec descriptions, exemples et "
        "tags."
    )

    # ----- Authentification ---------------------------------------------
    pdf.h1("2. Authentification")

    pdf.h2("Mécanisme : Token DRF")
    pdf.p(
        "L'API utilise le système Token de Django REST Framework "
        "(rest_framework.authtoken). Chaque utilisateur back-office se voit "
        "attribuer un token unique non-expirant, à inclure dans le header "
        "Authorization de chaque requête."
    )
    pdf.code(
        "Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b\n"
        "Accept: application/json"
    )

    pdf.h2("Émission et révocation des tokens")
    pdf.bullet("Émission : back-office admin /dashboard/admin/api-tokens/ → bouton 'Émettre un nouveau token'.")
    pdf.bullet("Affichage en clair une seule fois (au moment de l'émission). À copier immédiatement.")
    pdf.bullet("Révocation : depuis le même back-office ; révoque immédiatement les requêtes en cours.")
    pdf.bullet("Limitation : un seul token actif par compte (la réémission supprime l'ancien).")
    pdf.bullet("Audit : chaque émission/révocation est journalisée (API_TOKEN_ISSUED, API_TOKEN_REVOKED).")

    pdf.h2("Rôles éligibles")
    pdf.p(
        "Les tokens sont émis uniquement pour les comptes back-office "
        "(agents, admins, super-admins). Les comptes citoyens n'ont pas "
        "accès à l'API : ils utilisent l'interface web."
    )

    pdf.h2("Endpoint d'échange username/password → token")
    pdf.code(
        "POST /api/v1/token/\n"
        "Content-Type: application/json\n"
        "\n"
        '{"username": "agent_demo", "password": "DemoPw1!"}\n'
        "\n"
        "→ 200 OK\n"
        '{"token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b"}'
    )

    # ----- Throttling ---------------------------------------------------
    pdf.h1("3. Throttling (limitation de débit)")

    pdf.p(
        "Le throttling protège l'API contre les abus (scraping massif, "
        "tentatives de brute-force) et garantit l'équité d'accès entre les "
        "consommateurs. La librairie DRF gère le compteur avec un cache "
        "(en production, Redis ; en dev, mémoire locale)."
    )

    pdf.table(
        headers=["Scope", "Limite", "Période", "S'applique à"],
        rows=[
            ["anon",        "10",  "minute", "Requêtes non authentifiées"],
            ["user",        "60",  "minute", "Toute requête authentifiée par défaut"],
            ["check_right", "120", "minute", "Endpoint /check-right/ uniquement (scan-cars)"],
        ],
        col_widths=[40, 25, 30, 79],
    )

    pdf.h2("Comportement en cas de dépassement")
    pdf.p(
        "L'API renvoie un statut HTTP 429 Too Many Requests avec un header "
        "Retry-After indiquant le délai en secondes avant nouvelle tentative."
    )
    pdf.code(
        "HTTP/1.1 429 Too Many Requests\n"
        "Retry-After: 47\n"
        "Content-Type: application/json\n"
        "\n"
        '{"detail": "Request was throttled. Expected available in 47 seconds."}'
    )

    # ----- Endpoints ----------------------------------------------------
    pdf.h1("4. Endpoints")

    pdf.h2("Vue d'ensemble")
    pdf.table(
        headers=["Méthode", "URL", "Tag", "Auth"],
        rows=[
            ["POST", "/api/v1/token/",                       "Auth",      "user+pw"],
            ["GET",  "/api/v1/check-right/",                 "Permits",   "Token"],
            ["GET",  "/api/v1/communes/",                    "Reference", "Token"],
            ["GET",  "/api/v1/zones/",                       "Reference", "Token"],
            ["GET",  "/api/v1/permits/eligibility/{pk}/",    "Permits",   "Token"],
            ["POST", "/api/v1/permits/submit/{pk}/",         "Permits",   "Token"],
            ["GET",  "/api/v1/audit/",                       "Audit",     "Token (admin)"],
            ["GET",  "/api/v1/schema/",                      "Docs",      "Public"],
            ["GET",  "/api/v1/docs/",                        "Docs",      "Public"],
            ["GET",  "/api/v1/redoc/",                       "Docs",      "Public"],
        ],
        col_widths=[20, 80, 30, 44],
    )

    # ----- check-right (endpoint phare) ----------------------------------
    pdf.h2("4.1 — GET /api/v1/check-right/")
    pdf.p(
        "Endpoint principal de l'API publique, destiné aux véhicules "
        "scan-cars communaux. Vérifie le droit de stationnement d'une plaque "
        "à un instant donné, optionnellement filtré sur une zone GIS."
    )

    pdf.h3("Paramètres de requête (query string)")
    pdf.table(
        headers=["Paramètre", "Type", "Requis", "Description"],
        rows=[
            ["plate", "string", "Oui", "Plaque normalisée (ex: 1-AAA-111). Normalisation auto côté serveur."],
            ["zone",  "string", "Non", "zonecode GIS. Si fourni, vérifie que la carte couvre cette zone."],
            ["at",    "string", "Non", "ISO 8601 (2026-04-26T14:30:00+02:00) ou date. Défaut : maintenant."],
        ],
        col_widths=[30, 25, 20, 99],
    )

    pdf.h3("Exemple de requête")
    pdf.code(
        "GET /api/v1/check-right/?plate=1-AAA-111&zone=21015-A&at=2026-04-26T14:30:00%2B02:00\n"
        "Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b"
    )

    pdf.h3("Réponse 200 OK")
    pdf.code(
        "{\n"
        '  "authorized": true,\n'
        '  "plate": "1-AAA-111",\n'
        '  "zone": "21015-A",\n'
        '  "checked_at": "2026-04-26T14:30:00+02:00",\n'
        '  "permit": {\n'
        '    "id": 42,\n'
        '    "type": "resident",\n'
        '    "valid_from": "2026-01-15",\n'
        '    "valid_until": "2027-01-15",\n'
        '    "zones": ["21015-A", "21015-B"]\n'
        "  }\n"
        "}"
    )

    pdf.h3("Réponse 200 OK (non autorisé)")
    pdf.code(
        "{\n"
        '  "authorized": false,\n'
        '  "plate": "9-XYZ-999",\n'
        '  "zone": "21015-A",\n'
        '  "checked_at": "2026-04-26T14:30:00+02:00",\n'
        '  "permit": null\n'
        "}"
    )

    pdf.h3("Audit RGPD")
    pdf.p(
        "Chaque appel à /check-right/ est journalisé dans AuditLog avec la "
        "plaque hashée (HMAC-SHA256 tronqué à 16 hex), jamais en clair. "
        "Préserve la traçabilité (qui a interrogé quoi quand) sans exposer "
        "les plaques aux journaux."
    )

    # ----- communes -----------------------------------------------------
    pdf.h2("4.2 — GET /api/v1/communes/")
    pdf.p("Liste des 19 communes de la Région bruxelloise.")
    pdf.h3("Réponse")
    pdf.code(
        "[\n"
        "  {\n"
        '    "id": 1, "niscode": "21001", "name_fr": "Anderlecht",\n'
        '    "name_nl": "Anderlecht", "postal_codes": "1070"\n'
        "  },\n"
        "  ...\n"
        "]"
    )

    # ----- zones --------------------------------------------------------
    pdf.h2("4.3 — GET /api/v1/zones/")
    pdf.p("Liste des zones GIS de la version active. Filtrable par commune (niscode).")
    pdf.h3("Paramètres")
    pdf.bullet("commune — niscode 5 chiffres (ex: 21015 = Schaerbeek).")
    pdf.h3("Réponse")
    pdf.code(
        '[{"zonecode": "21015-A", "niscode": "21015"}, ...]'
    )

    # ----- permit eligibility ------------------------------------------
    pdf.h2("4.4 — GET /api/v1/permits/eligibility/{vehicle_pk}/")
    pdf.p(
        "Pré-calcul d'éligibilité pour une carte riverain. Lecture seule. "
        "Alimente le wizard React avant la soumission de la demande."
    )
    pdf.h3("Réponse")
    pdf.code(
        "{\n"
        '  "vehicle": {"plate": "1-AAA-111", "brand": "Renault", "model": "Clio"},\n'
        '  "address": {"street": "Rue de Flandre", "commune": "Bruxelles"},\n'
        '  "main_zone": "21004-C",\n'
        '  "additional_zones": ["21004-D"],\n'
        '  "polygon_id": 42,\n'
        '  "requires_manual_review": false,\n'
        '  "denied": false,\n'
        '  "price_cents": 1000,\n'
        '  "validity_days": 365\n'
        "}"
    )

    pdf.h2("4.5 — POST /api/v1/permits/submit/{vehicle_pk}/")
    pdf.p("Crée le draft puis le soumet en une opération atomique.")
    pdf.h3("Réponse")
    pdf.code(
        "{\n"
        '  "permit_id": 87,\n'
        '  "status": "awaiting_payment",\n'
        '  "next_step": "pay"\n'
        "}"
    )

    # ----- audit --------------------------------------------------------
    pdf.h2("4.6 — GET /api/v1/audit/")
    pdf.p(
        "Liste paginée du journal d'audit (réservée aux admin/super-admin). "
        "Pagination par cursor (cursor opaque dans next/previous). Filtres "
        "via query params : action, severity, target_type, actor, q, "
        "date_from, date_to."
    )

    # ----- Codes d'erreur ----------------------------------------------
    pdf.h1("5. Codes d'erreur")

    pdf.table(
        headers=["Code", "Signification", "Action recommandée"],
        rows=[
            ["200 OK",                    "Requête réussie",                    "Traiter la réponse"],
            ["201 Created",               "Ressource créée (POST submit)",      "Récupérer l'ID dans le payload"],
            ["400 Bad Request",           "Paramètre invalide ou manquant",     "Vérifier les paramètres requis"],
            ["401 Unauthorized",          "Token absent ou invalide",           "Vérifier le header Authorization"],
            ["403 Forbidden",             "Token valide mais permissions KO",   "Demander un token avec les bons droits"],
            ["404 Not Found",             "Ressource inexistante",              "Vérifier l'ID ou le chemin"],
            ["429 Too Many Requests",     "Throttling dépassé",                 "Attendre Retry-After secondes"],
            ["500 Internal Server Error", "Erreur serveur",                     "Réessayer plus tard, contacter support"],
        ],
        col_widths=[35, 60, 79],
    )

    # ----- Open Data ---------------------------------------------------
    pdf.h1("6. Open Data")

    pdf.h2("Données ouvertes par défaut")
    pdf.p(
        "Conformément à la directive européenne 2019/1024 sur les données "
        "publiques ouvertes, certaines données non-personnelles sont mises "
        "à disposition sous licence ouverte (Etalab 2.0 ou équivalent) :"
    )
    pdf.bullet("Liste des 19 communes (niscode + noms FR/NL).")
    pdf.bullet("Liste des zones GIS actives (zonecode + niscode).")
    pdf.bullet("Polygones GIS (GeoJSON via /map/) — projection WGS84.")
    pdf.bullet("Statistiques agrégées (à venir) : nombre de cartes actives par commune, taux d'approbation automatique, temps moyen de traitement.")

    pdf.h2("Données restreintes (non-Open Data)")
    pdf.bullet("Plaques, identités, adresses, paiements — strictement réservés aux acteurs autorisés (RGPD).")
    pdf.bullet("Journal d'audit — réservé aux admins (contient des plaques hashées, des IPs).")
    pdf.bullet("Tokens API — émis nominativement, jamais publiés.")

    pdf.h2("Format et téléchargement")
    pdf.bullet("Format JSON (API REST) — toujours disponible.")
    pdf.bullet("Format GeoJSON pour les zones — récupérable depuis /map/ (frontend) ou directement via /api/v1/zones/.")
    pdf.bullet("Future : export CSV bulk des données publiques pour usages analytiques (jupyter, R, QGIS).")
    pdf.bullet("Future : flux Atom/RSS des modifications de zones GIS.")

    pdf.h2("Licence")
    pdf.p(
        "Sauf indication contraire, les données ouvertes sont publiées sous "
        "licence Etalab Open License 2.0 — autorisation de réutilisation "
        "commerciale et non-commerciale, avec mention de la source "
        "(« Source : Parking.Belgium / Région de Bruxelles-Capitale »)."
    )

    # ----- Bonnes pratiques pour consommateurs --------------------------
    pdf.h1("7. Bonnes pratiques pour les consommateurs")

    pdf.h2("Pour les scan-cars communaux")
    pdf.bullet("Mettre en cache localement les résultats positifs pendant 10 minutes (réduit la charge sur l'API et la latence).")
    pdf.bullet("En cas d'erreur 429, attendre Retry-After avant de réessayer (pas de retry immédiat).")
    pdf.bullet("Toujours envoyer le paramètre 'zone' pour optimiser le check (filtre côté serveur).")
    pdf.bullet("Loguer localement les requêtes effectuées (contre-audit avec le journal côté serveur).")

    pdf.h2("Pour les intégrations applicatives")
    pdf.bullet("Stocker le token de manière sécurisée (variable d'environnement, vault) — jamais en clair dans le code.")
    pdf.bullet("Renouveler le token périodiquement (rotation manuelle via le back-office, recommandée tous les 6 mois).")
    pdf.bullet("Suivre les changements de version sur le changelog (publication des deprecations 6 mois à l'avance).")
    pdf.bullet("Tester d'abord en environnement staging (token de test gratuit sur demande).")

    pdf.h2("Pour les chercheurs / data scientists")
    pdf.bullet("Endpoint /api/v1/communes/ et /zones/ accessibles sans rate-limit étendu, idéaux pour de l'analyse géo.")
    pdf.bullet("Le format GeoJSON est consommable directement par QGIS, ArcGIS, Mapshaper.")
    pdf.bullet("Pour l'historique des modifications GIS : nous écrire à privacy@parking.belgium.local — accès au journal d'audit anonymisé sur demande motivée.")

    return str(save_to(pdf, "08_documentation_api.pdf"))


if __name__ == "__main__":
    print(generate())
