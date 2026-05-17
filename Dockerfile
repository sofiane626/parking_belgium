# syntax=docker/dockerfile:1.7
#
# Image Docker prod pour Parking.Belgium.
#
# Choix : python:3.12-slim-bookworm (Debian 12) + apt comme unique gestionnaire
# de paquets. On évite Nixpacks parce qu'il mélange Nix et apt avec des
# LD_LIBRARY_PATH disjoints, ce qui empêche ctypes (Nix-Python) de résoudre
# libcurl.so.4 (apt) au moment du chargement de libgdal.so.
#
# Le build fait :
#   1. apt : GDAL/GEOS/PROJ + Node 20 LTS
#   2. pip install requirements.txt
#   3. npm ci + npm run build dans theme/static_src (Tailwind) et frontend (Vite)
#
# collectstatic et migrate sont déclenchés via Procfile en phase release —
# le build Docker n'a pas accès aux variables d'environnement Railway
# (DATABASE_URL, DJANGO_SECRET_KEY, etc.).

FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Bibliothèques système : GeoDjango (GDAL/GEOS/PROJ) + Node 20 pour le build front
# Tout via apt → un seul linker dynamique cohérent.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gnupg \
        gdal-bin \
        libgdal-dev \
        libgeos-dev \
        libproj-dev \
        proj-data \
        proj-bin \
        binutils \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Étape pip d'abord (couche cacheable indépendante du reste du code).
COPY requirements.txt /app/
RUN pip install -r requirements.txt

# Code applicatif (incluant theme/static_src et frontend avec leurs package.json).
COPY . /app

# Build Tailwind → static/css/dist/styles.css
RUN cd theme/static_src && npm ci && npm run build

# Build Vite (map + wizard + audit bundles) → static/frontend/
RUN cd frontend && npm ci && npm run build

# Filet de sécurité au cas où Railway n'honorerait pas le Procfile en mode
# Dockerfile : on tente migrate + collectstatic + gunicorn dans le CMD.
# Migrate et collectstatic sont idempotents, donc en cas de double exécution
# (Procfile release + ce CMD) il n'y a pas d'effet de bord.
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && exec gunicorn parking_belgium.wsgi --bind 0.0.0.0:${PORT:-8000} --workers 3 --timeout 60 --access-logfile - --error-logfile -"]
