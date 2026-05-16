# Parking.Belgium

Plateforme web unique pour la gestion des cartes de stationnement des **19 communes
de la Région de Bruxelles-Capitale**. Demande, paiement, attribution automatique
des zones selon l'adresse, codes visiteurs, carte professionnelle — le tout en
français, néerlandais et anglais.

Projet de fin d'études — Sofiane Ezzahti.

## Sommaire

- [Aperçu](#aperçu)
- [Stack technique](#stack-technique)
- [Architecture](#architecture)
- [Installation locale (Windows)](#installation-locale-windows)
- [Workflows opérationnels](#workflows-opérationnels)
- [Tests](#tests)
- [Conventions](#conventions)

## Aperçu

| Acteur | Ce qu'il peut faire |
|---|---|
| **Citoyen** | inscription self-service, carte riverain (auto-attribuée selon son adresse), carte visiteur (100 codes/an, gratuite), carte professionnelle (revue manuelle), paiement Stripe, changement d'adresse/plaque (avec validation agent) |
| **Agent** | revue manuelle des demandes ambiguës, attribution de zones, validation des changements d'adresse et de plaque |
| **Admin** | configuration globale + politiques par commune × type, gestion des utilisateurs, tokens API, données GIS, journal d'audit, exports CSV |
| **Super-admin** | + promotion / révocation des admins |

Endpoints publics :
- Site web multilingue : `/fr/`, `/nl/`, `/en/`
- API REST : `/api/v1/` (token DRF, throttlé) — endpoint phare `check-right/?plate=…&zone=…` pour les scan-cars communaux
- Doc API interactive : `/api/v1/docs/` (Swagger UI) + `/api/v1/redoc/` (Redoc)

## Stack technique

| Couche | Outil |
|---|---|
| Backend | Django 5.1 · Django REST Framework · drf-spectacular (OpenAPI) |
| Base de données | PostgreSQL 17 + PostGIS 3.6 (GeoDjango) |
| Front server-rendered | Tailwind CSS (`django-tailwind`) · templates Django avec partials |
| Front îlots React | React 18 + Vite 5 + react-leaflet 4 (carte interactive, wizard demande, datatable audit) |
| Auth | Django auth + DRF Token |
| Paiement | Stripe Checkout (test mode) + formulaire carte interne (validation Luhn) + simulation staff/DEBUG |
| GIS | Lambert 72 (EPSG:31370) → WGS84, point-in-polygon, moteur d'attribution + règles |
| Audit | journalisation applicative résiliente (modèle `AuditLog` + signaux passifs) |
| i18n | 950 chaînes FR/NL/EN à 100% via outil Babel maison (`tools/i18n_tools.py`) |
| Email | SMTP Gmail (App Password) + workaround SSL antivirus + templates `.txt` + `.html` |

## Architecture

```
parking_belgium/                # config Django (settings éclatés base/dev/prod)
frontend/                       # bundle React-Leaflet + Vite (3 entries : map, wizard, audit)
locale/                         # fichiers .po + .mo NL et EN
tools/                          # outils i18n maison (extract / update / apply / compile)
apps/
├── core/                       # home, legal, post_login_redirect, error handlers
├── accounts/                   # custom User (role + preferred_language), auth, register
├── citizens/                   # profil citoyen, adresse géocodée, demandes de changement
├── vehicles/                   # véhicules (soft-delete), demandes de changement de plaque
├── companies/                  # entités professionnelles (BE0XXXXXXXXX)
├── permits/                    # cartes (riverain/visiteur/pro), state machine 9 statuts,
│                                 codes visiteurs, services métier, expire_due
├── gis_data/                   # GISSourceVersion, GISPolygon, import OSM/shapefile
├── rules/                      # PolygonRule + moteur d'attribution adresse→zones
├── payments/                   # Stripe Checkout + carte interne + simulation + emails
├── audit/                      # AuditLog applicatif (28 actions × 4 sévérités)
├── api/                        # DRF v1 : check-right + référence + audit + OpenAPI
└── dashboard/                  # back-office (agent + admin + super_admin) + exports CSV
templates/                      # templates partagés
static/                         # assets source
GIS/                            # shapefile source (map_tfe.*)
```

### Flux clés

1. **Demande de carte riverain** : citoyen → wizard React (`/me/permits/vehicle/<pk>/wizard/`) → API DRF `permits/eligibility` (calcule la zone via point-in-polygon) → `permits/submit` (crée le draft + soumet) → moteur d'attribution + politiques par commune → `ACTIVE` (auto) ou `MANUAL_REVIEW` (agent) → Stripe Checkout → carte active + email de confirmation
2. **Vérification scan-car** : `GET /api/v1/check-right/?plate=…&zone=…` → service `is_plate_authorized` (résident/pro ACTIVE puis fallback codes visiteurs) → 200 avec `authorized: bool` + détail de la carte (plaque hashée HMAC-SHA256 côté audit, jamais exposée en clair dans les logs)
3. **Expiration** : cron `python manage.py expire_due` → permits `ACTIVE` avec `valid_until < today()` passent en `EXPIRED` + codes visiteurs annulés + log d'audit

## Installation locale (Windows)

### 1. Prérequis

| Outil | Version | Installation |
|---|---|---|
| Python | 3.13+ | https://www.python.org/downloads/ |
| PostgreSQL + PostGIS | 17 + 3.6 | `winget install PostgreSQL.PostgreSQL.17` puis bundle PostGIS [stackbuilder](https://download.osgeo.org/postgis/windows/pg17/) |
| Node.js | 20+ LTS | `winget install OpenJS.NodeJS.LTS` |
| Git | n.a. | `winget install Git.Git` |

### 2. Cloner et créer le venv

```powershell
git clone https://github.com/sofiane626/parking_belgium.git
cd parking_belgium
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Base de données

```powershell
$env:PGPASSWORD = "postgres"
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -h localhost -c "CREATE ROLE parking_belgium WITH LOGIN PASSWORD 'parking_belgium' CREATEDB;"
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -h localhost -c "CREATE DATABASE parking_belgium OWNER parking_belgium ENCODING 'UTF8';"
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -h localhost -d parking_belgium -c "CREATE EXTENSION IF NOT EXISTS postgis; ALTER SCHEMA public OWNER TO parking_belgium;"
```

### 4. Configuration `.env`

```powershell
Copy-Item .env.example .env
# Éditer si besoin :
#   - DJANGO_SECRET_KEY (générer une clé)
#   - GDAL_LIBRARY_PATH / GEOS_LIBRARY_PATH / PROJ_LIB (paths PostgreSQL\17\bin)
#   - STRIPE_PUBLIC_KEY / STRIPE_SECRET_KEY (compte test gratuit sur dashboard.stripe.com)
#   - EMAIL_HOST_USER / EMAIL_HOST_PASSWORD (App Password Gmail si on veut tester les emails)
```

### 5. Migrer + compiler les assets

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py shell -c "from apps.accounts.models import User, Role; u = User.objects.get(username='<ton_user>'); u.role = Role.SUPER_ADMIN; u.save()"

# Tailwind
$env:PATH = "C:\Program Files\nodejs;$env:PATH"
python manage.py tailwind install
python manage.py tailwind build

# Bundles React (3 entries : map, wizard, audit)
cd frontend
npm install
npm run build
cd ..

# Traductions NL + EN
pip install babel
python tools/i18n_tools.py compile
```

### 6. Lancer

```powershell
python manage.py runserver
# Le projet est servi sur http://127.0.0.1:8000/
# Tu seras redirigé automatiquement vers /fr/, /nl/ ou /en/ selon ta langue préférée.
```

## Workflows opérationnels

### Cron `expire_due`

Passe en `EXPIRED` toutes les cartes `ACTIVE`/`SUSPENDED` dont `valid_until < today`.

```powershell
python manage.py expire_due            # exécution normale
python manage.py expire_due --dry-run  # n'expire rien, affiche ce qui serait fait
```

À planifier dans le **Planificateur de tâches Windows** (ou cron Linux) pour un lancement
quotidien à 03:00 par exemple.

### Exports CSV

Le dashboard admin propose des exports CSV (UTF-8 BOM, séparateur `;`, compatible
Excel FR/NL) pour : cartes, paiements, utilisateurs, demandes de changement,
journal d'audit. Chaque export est journalisé dans l'audit (action `CSV_EXPORTED`)
avec le compte d'auteur + les filtres appliqués.

### i18n — workflow Babel maison

Sans `gettext` (non installé sur Windows par défaut), on utilise Babel + des
outils maison pour extraire / appliquer / compiler les traductions.

```powershell
python tools/i18n_tools.py extract  # scanne templates + .py -> locale/messages.pot
python tools/i18n_tools.py update   # propage -> locale/{nl,en}/LC_MESSAGES/django.po
python tools/i18n_tools.py apply    # remplit depuis tools/translations_{nl,en}.py
python tools/i18n_tools.py compile  # produit les .mo
# Important : redémarrer Django pour recharger les .mo (pas hot-reloadés)
```

### Webhook Stripe (test local)

```powershell
stripe listen --forward-to localhost:8000/stripe/webhook/
# Copie le whsec_… affiché dans .env (STRIPE_WEBHOOK_SECRET)
```

## Tests

```powershell
python manage.py test                    # suite complète
python manage.py test apps.payments      # un module
python manage.py test apps.permits.tests.test_expire_due -v 2
```

Une violation d'audit volontaire (action factice trop longue pour tester la
résilience du logger) affiche une trace `DataError` dans la sortie — c'est
intentionnel, les tests passent.

## Conventions

- **Service layer** : toute logique métier vit dans `apps/<x>/services.py`, jamais
  dans les vues. Les transitions du state machine `Permit.status` passent toutes
  par un service dédié.
- **Audit** : chaque action sensible (création/modification/suppression de carte,
  paiement, changement de rôle, appel API check-right…) est journalisée via
  `apps.audit.services.log()`. Le service est résilient : **ne lève jamais**.
- **i18n** : toutes les chaînes utilisateur passent par `{% trans %}` /
  `gettext_lazy()`. URL préfixées `/fr/`, `/nl/`, `/en/` ; routes machines
  (`admin/`, `api/v1/`, `stripe/webhook/`, `i18n/setlang/`) hors préfixe.
- **Front** : server-rendered Django + 3 îlots React (carte, wizard, audit) pour
  les interactions riches. Pas de SPA monolithique.
- **Commits** : messages en français, style classique (verbe à l'infinitif ou
  nom). Pas de marqueurs IA dans le code ni les commits.

## Documentation API

- **OpenAPI brut** : `/api/v1/schema/`
- **Swagger UI** (interactif, "Try it out") : `/api/v1/docs/`
- **Redoc** (lecture, présentation TFE) : `/api/v1/redoc/`

## Licence

Académique — TFE. Les données géographiques (zones de stationnement) sont la
propriété de la Région de Bruxelles-Capitale.
