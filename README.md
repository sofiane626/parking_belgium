# Parking.Belgium

Plateforme centralisée Django/PostGIS pour la gestion des droits de stationnement
sur les 19 communes de Bruxelles. Une seule application multi-communes, avec
règles métier configurables, cartographie GIS, back-office et API REST.

> Statut : étape **1** du plan de développement (setup local) — terminée.
> Étape **2** (auth + rôles + dashboards) : structure en place, à étoffer.

## Stack

- Python 3.13, Django 5.1, Django REST Framework 3.15
- PostgreSQL 17 + PostGIS 3.6 (GeoDjango)
- Tailwind CSS (pipeline `django-tailwind` — à brancher étape suivante)
- Leaflet (carto front, ajouté à l'étape GIS)

## Prérequis

- **Python 3.13+** (`python --version`)
- **PostgreSQL 17 + PostGIS 3.6** installés localement
- **Node.js 20+** (pour Tailwind, étape suivante)

### Installation des prérequis (Windows)

```powershell
winget install --id PostgreSQL.PostgreSQL.17 --silent --custom "--mode unattended --unattendedmodeui none --superpassword postgres --servicename postgresql-x64-17 --serverport 5432 --locale C"
# Puis le bundle PostGIS depuis https://download.osgeo.org/postgis/windows/pg17/
winget install --id OpenJS.NodeJS.LTS --silent
```

## Installation locale

```powershell
# 1. Cloner et entrer dans le projet
cd Parking.Belgium

# 2. Créer le venv et installer les deps
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 3. Préparer la DB (en tant que superuser postgres)
$env:PGPASSWORD = "postgres"
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -h localhost -c "CREATE ROLE parking_belgium WITH LOGIN PASSWORD 'parking_belgium' CREATEDB;"
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -h localhost -c "CREATE DATABASE parking_belgium OWNER parking_belgium ENCODING 'UTF8';"
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -h localhost -d parking_belgium -c "CREATE EXTENSION IF NOT EXISTS postgis; ALTER SCHEMA public OWNER TO parking_belgium;"

# 4. Configurer .env
Copy-Item .env.example .env
# (édite si besoin — paths GDAL/GEOS, secret key, DB URL)

# 5. Migrer + créer un super_admin
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py createsuperuser
# puis dans un shell :
.venv\Scripts\python.exe manage.py shell -c "from apps.accounts.models import User, Role; u = User.objects.get(username='<ton_user>'); u.role = Role.SUPER_ADMIN; u.save()"

# 6. Lancer le serveur
.venv\Scripts\python.exe manage.py runserver
```

Le projet est servi sur <http://127.0.0.1:8000/>.

## Structure

```
parking_belgium/         # config Django (settings éclatés base/dev/prod, urls, wsgi, asgi)
apps/
├── core/                # home, post-login redirect, error handlers, base templates
├── accounts/            # Custom User + rôle (citizen/agent/admin/super_admin)
├── citizens/            # profil citoyen, adresse principale
├── vehicles/            # véhicules (plusieurs par citoyen)
├── companies/           # entités professionnelles
├── permits/             # demandes & cartes (resident/visitor/professional)
├── gis_data/            # GISSourceVersion, GISPolygon, import shapefile
├── rules/               # PolygonRule + moteur d'attribution
├── payments/            # paiement simulé
├── audit/               # AuditLog applicatif
├── api/                 # DRF /api/v1/ — check-right endpoints
└── dashboard/           # back-office par rôle
templates/               # templates partagés
static/                  # assets statiques source
GIS/                     # source shapefile (map_tfe.*)
```

## Configuration GeoDjango sous Windows

Le projet pointe `GDAL_LIBRARY_PATH` et `GEOS_LIBRARY_PATH` (via `.env`) vers les
DLLs shippées par le bundle PostGIS dans `C:\Program Files\PostgreSQL\17\bin\`.
Pas besoin d'OSGeo4W ni de wheels GDAL séparées.

## Rôles & accès

| Rôle | Inscription | Dashboard | Capacités principales |
|---|---|---|---|
| `citizen` | self-service | `/dashboard/citizen/` | gère ses véhicules, demandes, cartes |
| `agent` | par admin | `/dashboard/agent/` | consulte profils, gère dossiers manuels |
| `admin` | par super_admin | `/dashboard/admin/` | + règles métier, GIS, audits |
| `super_admin` | par DB ou autre super_admin | `/dashboard/super-admin/` | tous droits |

## Commandes utiles

```powershell
.venv\Scripts\python.exe manage.py check         # checks système
.venv\Scripts\python.exe manage.py makemigrations
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py shell
.venv\Scripts\python.exe manage.py runserver
```

## Sécurité — credentials par défaut

Les credentials locales (`postgres/postgres`, `parking_belgium/parking_belgium`,
`admin/admin`) sont **dev only**. À durcir avant tout déploiement.
