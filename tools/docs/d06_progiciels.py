"""
Document 06 — Recherche de progiciels et solutions techniques.

Liste les outils utilisés, justifie chaque choix (RAD : Rapid Application
Development), inclut le plan de maintenance préventive.
"""
from __future__ import annotations

from .pdf_base import PBPdf, save_to


def generate() -> str:
    pdf = PBPdf(
        title="Recherche de progiciels et solutions techniques",
        subtitle="Sélection RAD, justifications et plan de maintenance",
    )
    pdf.cover()

    # ----- Philosophie ---------------------------------------------------
    pdf.h1("1. Philosophie : Rapid Application Development (RAD)")
    pdf.p(
        "Plutôt que de réinventer la roue, le projet privilégie la "
        "programmation par intégration : chaque besoin technique est d'abord "
        "satisfait par un framework, une librairie ou un composant tiers "
        "éprouvé. Le code original se concentre sur la logique métier "
        "spécifique au domaine (cartes de stationnement, attribution par "
        "polygone, politiques communales)."
    )
    pdf.h2("Critères de sélection appliqués")
    pdf.bullet("Maturité — librairie en production depuis ≥ 3 ans, ≥ 1000 GitHub stars.")
    pdf.bullet("Maintenance active — derniers commits < 6 mois, releases régulières.")
    pdf.bullet("Communauté — documentation officielle complète, écosystème de plugins, Stack Overflow actif.")
    pdf.bullet("Licence permissive — MIT, BSD, Apache 2.0 (compatibles usage public).")
    pdf.bullet("Performance — benchmarks publics ou retours d'expérience industriels.")
    pdf.bullet("Sécurité — historique d'audits, CVE rares et patchées rapidement.")

    # ----- Backend ------------------------------------------------------
    pdf.h1("2. Backend (Python)")

    pdf.h2("Django 5.1 — Framework web")
    pdf.p(
        "Choix structurant. Django est le framework web mature de l'écosystème "
        "Python, particulièrement adapté aux projets administratifs avec "
        "back-office (l'ORM, l'admin auto, les forms et le templating couvrent "
        "60-70 % d'un projet CRUD classique sans une ligne de code custom)."
    )
    pdf.bullet("Maturité : v1.0 en 2008, 5.1 en 2024 — extrêmement éprouvé.")
    pdf.bullet("Built-ins critiques : ORM, migrations, authentification, sessions, CSRF, ModelForm, admin auto, i18n, gestion de fichiers.")
    pdf.bullet("Sécurité : XSS, CSRF, SQL injection, clickjacking traités par défaut.")
    pdf.bullet("Plus de 80 % des fonctionnalités du projet utilisent Django sans surcouche.")

    pdf.h2("Django REST Framework 3.15 — API")
    pdf.p(
        "Surcouche Django pour exposer des endpoints REST. DRF est le "
        "standard de facto (utilisé par Instagram, Mozilla, Eventbrite). "
        "Couvre serializers, permissions, throttling, pagination, "
        "authentification token."
    )
    pdf.bullet("APIView + ListAPIView — vues prêtes à l'emploi.")
    pdf.bullet("TokenAuthentication intégré — authtoken app.")
    pdf.bullet("Throttling configurable par scope (check_right : 120/min/user).")

    pdf.h2("drf-spectacular 0.29 — OpenAPI / Swagger")
    pdf.p(
        "Génération automatique d'un schéma OpenAPI 3.1 + UI interactive "
        "(Swagger UI + Redoc). Décorateurs @extend_schema pour enrichir la "
        "documentation par endpoint."
    )

    pdf.h2("psycopg 3.2 — Pilote PostgreSQL")
    pdf.bullet("v3 (2021) — succession de psycopg2, async natif.")
    pdf.bullet("Binary version (sans compilation) : pip install psycopg[binary].")

    pdf.h2("Pillow 11 — Manipulation d'images")
    pdf.bullet("Traitement des photos de certificats d'immatriculation uploadés (vérification taille, format, conversion JPEG → WebP).")

    pdf.h2("Stripe 11.5 — SDK paiement")
    pdf.p(
        "SDK officiel pour Stripe Checkout (paiement hosted) et "
        "Payment Intents (webhook). Stripe a une réputation solide en "
        "matière de sécurité (PCI-DSS niveau 1) et son intégration en mode "
        "test est extrêmement fluide."
    )
    pdf.bullet("Stripe Checkout — page hostée Stripe, aucune donnée carte ne transite par notre serveur.")
    pdf.bullet("Webhook signature verification — STRIPE_WEBHOOK_SECRET vérifiée à chaque réception.")
    pdf.bullet("Mode test gratuit avec cartes de test fournies (4242 4242 4242 4242).")

    pdf.h2("django-environ — Configuration via .env")
    pdf.bullet("Chargement des variables d'environnement depuis un fichier .env (12-factor app).")

    pdf.h2("WhiteNoise 6 — Service de fichiers statiques")
    pdf.p(
        "Permet de servir les fichiers statiques (CSS, JS, images) "
        "directement depuis Django/Gunicorn sans serveur web séparé (Nginx). "
        "Compression gzip + brotli, headers cache appropriés, "
        "hashing pour cache-busting."
    )

    pdf.h2("django-cors-headers — CORS")
    pdf.bullet("Gestion des en-têtes CORS pour l'API publique (futur usage cross-domain).")

    pdf.h2("django-extensions — Outils dev")
    pdf.bullet("shell_plus, runserver_plus, graph_models — outils de productivité.")

    pdf.h2("Babel 2.18 — i18n alternatif")
    pdf.p(
        "Substitut à gettext (non installé sur Windows) pour l'extraction "
        "et la compilation des chaînes de traduction. Outil interne "
        "tools/i18n_tools.py orchestre extract / update / apply / compile."
    )

    pdf.h2("coverage 7.14 — Mesure de couverture de tests")
    pdf.bullet("Configuration via .coveragerc (omit migrations, tests, init).")
    pdf.bullet("Coverage actuelle : 70.8 % global, 85-100 % sur les services critiques.")

    # ----- Frontend -----------------------------------------------------
    pdf.h1("3. Frontend")

    pdf.h2("Tailwind CSS 3 — Utility-first CSS")
    pdf.p(
        "Framework CSS qui privilégie les classes utilitaires (p-4, text-lg, "
        "bg-brand-500) plutôt que des composants pré-stylés. Avantages : "
        "personnalisation extrême, bundle CSS minimal (purge automatique), "
        "cohérence visuelle (design tokens centralisés)."
    )
    pdf.bullet("Plugins utilisés : @tailwindcss/forms (reset cohérent des inputs), @tailwindcss/typography, @tailwindcss/aspect-ratio.")
    pdf.bullet("Configuration centralisée : theme.extend.colors avec palettes brand/accent/signal.")
    pdf.bullet("Bundle final ~68 ko (minifié, gzippé) — léger même avec animation custom.")

    pdf.h2("React 18 + Vite 5 — Îlots interactifs")
    pdf.p(
        "Choix d'architecture : server-rendered Django par défaut, React "
        "uniquement pour les zones à fortes interactions (carte, wizard, "
        "datatable). Évite la complexité d'une SPA monolithique tout en "
        "permettant des UI riches là où c'est utile."
    )
    pdf.bullet("3 bundles Vite distincts (map-bundle.js, wizard-bundle.js, audit-bundle.js).")
    pdf.bullet("Chacun monté sur un <div id='react-*-root'> placé dans le template Django.")
    pdf.bullet("Vite : dev server hot-reload < 100 ms, build production avec tree-shaking.")

    pdf.h2("react-leaflet 4 — Cartographie React")
    pdf.bullet("Wrapper React de Leaflet.js (carte open-source, alternative à Google Maps).")
    pdf.bullet("Tuiles : CartoDB Voyager (style sobre, lisible) + OpenStreetMap en fallback.")
    pdf.bullet("Couches GeoJSON pour les polygones de zones, popups customisés.")

    # ----- Base de données ----------------------------------------------
    pdf.h1("4. Base de données")

    pdf.h2("PostgreSQL 17 — SGBD relationnel")
    pdf.bullet("Standard ouvert, performances excellentes, transactions ACID, support JSON natif (JSONB).")
    pdf.bullet("Choix par défaut de Django, ORM optimisé pour PG.")
    pdf.bullet("Recommandé par les autorités belges pour les applications publiques (Smals, BOSA).")

    pdf.h2("PostGIS 3.6 — Extension géospatiale")
    pdf.bullet("Extension SQL/OGC pour stocker, indexer et requêter des objets géographiques.")
    pdf.bullet("Index GIST pour les opérations point-in-polygon (cœur de l'engine d'attribution).")
    pdf.bullet("Reprojection EPSG (Lambert 72 belge → WGS84 web) en SQL natif.")

    # ----- Hébergement et infrastructure --------------------------------
    pdf.h1("5. Hébergement et infrastructure (production prévue)")

    pdf.h2("Cloud souverain européen")
    pdf.p(
        "Pour un service public bruxellois traitant des données personnelles "
        "RGPD, l'hébergement est contraint à un cloud européen. Choix retenu :"
    )
    pdf.bullet("Scaleway (FR) — alternative française à AWS, datacenter à Amsterdam (NL) — proximité géographique idéale.")
    pdf.bullet("OVHcloud (FR/BE) — alternative crédible, datacenter à Bruxelles-Boortmeerbeek.")
    pdf.p(
        "Exclus : AWS, Google Cloud, Azure (CLOUD Act américain incompatible "
        "avec le service public européen sensible)."
    )

    pdf.h2("Stack d'exécution")
    pdf.bullet("Gunicorn 23 — Serveur WSGI Python (4-8 workers selon CPU).")
    pdf.bullet("Nginx en reverse proxy — terminaison TLS, compression, rate limiting layer 7.")
    pdf.bullet("PostgreSQL managed (Scaleway Database) — backups automatiques quotidiens, point-in-time recovery 7 jours.")
    pdf.bullet("Stockage objet S3-compatible (Scaleway Object Storage) — backups longue durée, certificats d'immatriculation uploadés.")

    pdf.h2("CI/CD")
    pdf.bullet("GitHub Actions — pipeline tests à chaque push (django.test, coverage report).")
    pdf.bullet("Déploiement manuel à terme — `git pull` + migrate + collectstatic + restart Gunicorn (script automatisable via Ansible).")

    pdf.h2("Monitoring et observabilité")
    pdf.bullet("Sentry — capture des exceptions Python + JS, alertes par email.")
    pdf.bullet("UptimeRobot — vérification HTTP toutes les 5 min sur les endpoints critiques.")
    pdf.bullet("Logs structurés JSON → Loki/Grafana en production.")

    # ----- Outils dev ---------------------------------------------------
    pdf.h1("6. Outils de développement")

    pdf.h2("Environnement local")
    pdf.bullet("Python 3.13 + venv — isolation des dépendances.")
    pdf.bullet("Node.js 20 LTS + npm — pipeline Tailwind et Vite.")
    pdf.bullet("PostgreSQL 17 + PostGIS 3.6 — installés localement (winget sur Windows, apt sur Linux).")
    pdf.bullet("Git + GitHub — versioning + collaboration.")
    pdf.bullet("VS Code — éditeur principal (extensions Python, Pylance, Tailwind IntelliSense).")

    pdf.h2("Outils maison (tools/)")
    pdf.bullet("tools/i18n_tools.py — orchestration extract/update/apply/compile pour la i18n (sans gettext).")
    pdf.bullet("tools/docs/ — générateur de PDF pour les livrables TFE (10 documents).")

    pdf.h2("Tests")
    pdf.bullet("django.test — TestCase, Client, factory de données.")
    pdf.bullet("314 tests automatisés.")
    pdf.bullet("Coverage 7.14 — mesure et rapport.")

    # ----- Plan de maintenance ------------------------------------------
    pdf.h1("7. Plan de maintenance préventive")

    pdf.h2("Mises à jour de sécurité")
    pdf.bullet("Vérification hebdomadaire automatisée (Dependabot GitHub) des CVE sur Django, DRF, Pillow, Stripe SDK.")
    pdf.bullet("Application des patches critiques (CVSS ≥ 7) dans les 72 h, autres patches dans les 30 jours.")
    pdf.bullet("Audit annuel externe (pentest) avant chaque mise à jour majeure de Django.")

    pdf.h2("Sauvegardes")
    pdf.bullet("Backup PostgreSQL quotidien — automatique via Scaleway Database, rétention 30 jours.")
    pdf.bullet("Backup objet (uploads) quotidien vers bucket secondaire, rétention 90 jours.")
    pdf.bullet("Test de restauration mensuel — restore complet sur environnement staging pour valider l'intégrité.")
    pdf.bullet("Backup off-site annuel — archive chiffrée externalisée chez un second fournisseur (ex: Hetzner DE).")

    pdf.h2("Évolution des dépendances")
    pdf.table(
        headers=["Composant", "Cadence", "Action"],
        rows=[
            ["Python",            "Annuelle",      "Migration vers la dernière 3.x stable (3.13 → 3.14 fin 2025)"],
            ["Django",            "Tous les 2 ans", "Migration vers la prochaine LTS (5.1 → 5.2 LTS en 2026)"],
            ["DRF",               "Annuelle",      "Suivi des releases mineures"],
            ["Tailwind",          "Semestrielle",  "Suivi des releases mineures (rebuild requis)"],
            ["React",             "Annuelle",      "Suivi des releases majeures (test régression)"],
            ["PostgreSQL/PostGIS", "Tous les 3 ans", "Migration vers la dernière version supportée"],
            ["Node.js",           "Annuelle",      "Suivi des LTS pairs (20 → 22 en 2024, 24 en 2026)"],
        ],
        col_widths=[40, 35, 99],
    )

    pdf.h2("Données GIS")
    pdf.bullet("Mise à jour annuelle des shapefiles communaux (suivi des modifications de zonage).")
    pdf.bullet("Procédure : `import_gis_polygons --commune <NIS> --activate` — gestion versionnée GISSourceVersion.")
    pdf.bullet("Tests automatiques post-import : vérification que tous les permits ACTIVE référencent toujours des polygones valides.")

    pdf.h2("Tâches planifiées (cron)")
    pdf.bullet("expire_due — quotidien (03:00) : passe les cartes dépassées en EXPIRED.")
    pdf.bullet("purge_expired_data — mensuel (1er dimanche) : anonymisation RGPD + suppression données expirées.")
    pdf.bullet("backup verification — hebdomadaire (dimanche 04:00) : tente une restauration sur env. staging.")
    pdf.bullet("Vérification SSL — mensuel : alerte 30 jours avant expiration du certificat Let's Encrypt.")

    pdf.h2("Documentation vivante")
    pdf.bullet("README.md mis à jour à chaque release majeure.")
    pdf.bullet("CHANGELOG.md (à créer) — versionnement sémantique des releases.")
    pdf.bullet("Tests servent de spécification vivante (314 tests documentent le comportement attendu).")
    pdf.bullet("Documentation API auto-générée (/api/v1/docs/) — toujours synchronisée avec le code.")

    pdf.h2("Indicateurs de santé technique")
    pdf.bullet("Couverture de tests ≥ 70 % (cible 80 %).")
    pdf.bullet("Build CI vert sur main (Github Actions).")
    pdf.bullet("Zéro CVE critique en cours sur la stack.")
    pdf.bullet("Temps de réponse médian API < 100 ms (mesure Sentry).")
    pdf.bullet("Disponibilité ≥ 99,5 % (SLA cible).")

    return str(save_to(pdf, "06_progiciels_solutions_techniques.pdf"))


if __name__ == "__main__":
    print(generate())
