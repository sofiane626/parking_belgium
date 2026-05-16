"""
Document 04 — Dictionnaire de données.

Liste exhaustive des tables avec leurs champs, types, contraintes et règles
métier. Introspection auto depuis les models Django.
"""
from __future__ import annotations

import os

import django


def _setup_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "parking_belgium.settings.dev")
    django.setup()


_setup_django()

from django.db import models  # noqa: E402

from .pdf_base import PBPdf, save_to  # noqa: E402


# Modèles à documenter, dans l'ordre logique de présentation
MODELS_ORDER = [
    ("core", "Commune"),
    ("accounts", "User"),
    ("citizens", "CitizenProfile"),
    ("citizens", "Address"),
    ("citizens", "AddressChangeRequest"),
    ("vehicles", "Vehicle"),
    ("vehicles", "PlateChangeRequest"),
    ("companies", "Company"),
    ("permits", "Permit"),
    ("permits", "PermitZone"),
    ("permits", "VisitorCode"),
    ("permits", "PermitConfig"),
    ("permits", "CommunePermitPolicy"),
    ("gis_data", "GISSourceVersion"),
    ("gis_data", "GISPolygon"),
    ("rules", "PolygonRule"),
    ("payments", "Payment"),
    ("audit", "AuditLog"),
]


def _field_type(f) -> str:
    """Type SQL approximatif pour affichage."""
    name = f.__class__.__name__
    related_label = ""
    if hasattr(f, "related_model") and f.related_model is not None:
        try:
            related_label = f.related_model._meta.label
        except AttributeError:
            related_label = str(f.related_model)
    mapping = {
        "AutoField": "BIGINT (PK auto)",
        "BigAutoField": "BIGINT (PK auto)",
        "CharField": f"VARCHAR({getattr(f, 'max_length', '?')})",
        "TextField": "TEXT",
        "IntegerField": "INTEGER",
        "BigIntegerField": "BIGINT",
        "PositiveIntegerField": "INTEGER ≥ 0",
        "FloatField": "FLOAT",
        "DecimalField": f"DECIMAL({f.max_digits},{f.decimal_places})" if hasattr(f, "max_digits") else "DECIMAL",
        "BooleanField": "BOOLEAN",
        "DateField": "DATE",
        "DateTimeField": "TIMESTAMPTZ",
        "EmailField": "VARCHAR(254)",
        "URLField": "VARCHAR(200)",
        "JSONField": "JSONB",
        "ForeignKey": f"FK → {related_label}" if related_label else "FK",
        "OneToOneField": f"FK 1-1 → {related_label}" if related_label else "FK 1-1",
        "ManyToManyField": f"M2M → {related_label}" if related_label else "M2M",
        "FileField": f"VARCHAR({getattr(f, 'max_length', 100)}) (chemin)",
        "ImageField": f"VARCHAR({getattr(f, 'max_length', 100)}) (chemin)",
        "GenericIPAddressField": "INET",
        "PointField": "GEOMETRY(Point, SRID)",
        "MultiPolygonField": "GEOMETRY(MultiPolygon, SRID)",
    }
    return mapping.get(name, name)


def _constraints(f) -> str:
    """Construit la liste des contraintes lisible."""
    parts = []
    if getattr(f, "primary_key", False):
        parts.append("PK")
    if not getattr(f, "null", True):
        parts.append("NOT NULL")
    if getattr(f, "unique", False):
        parts.append("UNIQUE")
    if getattr(f, "db_index", False) and not getattr(f, "unique", False):
        parts.append("INDEX")
    if hasattr(f, "default") and f.default is not models.NOT_PROVIDED:
        default = f.default
        if callable(default):
            parts.append("default=<callable>")
        else:
            parts.append(f"default={default!r}")
    if hasattr(f, "choices") and f.choices:
        choices_str = ",".join(str(c[0])[:8] for c in f.choices[:4])
        if len(f.choices) > 4:
            choices_str += "…"
        parts.append(f"choices=[{choices_str}]")
    return " · ".join(parts) or "—"


def _verbose_name(f) -> str:
    v = getattr(f, "verbose_name", "") or f.name
    return str(v)[:40]


def _model_fields(model):
    """Retourne [(name, verbose, type, constraints)] pour les champs concrets."""
    rows = []
    for f in model._meta.get_fields():
        # Skip inverse relations (auto)
        if not getattr(f, "concrete", False) and not getattr(f, "primary_key", False):
            continue
        if f.auto_created and not getattr(f, "primary_key", False):
            continue
        rows.append([
            f.name,
            _verbose_name(f),
            _field_type(f),
            _constraints(f),
        ])
    return rows


# Règles métier complémentaires (par modèle) — manuelles, non auto-générables
BUSINESS_RULES = {
    "accounts.User": [
        "role ∈ {citizen, agent, admin, super_admin} — assigné par hiérarchie (admin ne peut pas créer un autre admin).",
        "preferred_language ∈ {fr, nl, en} — applique la langue aux emails et au login.",
        "accepted_privacy_at / accepted_terms_at — snapshot RGPD à l'inscription (consentement éclairé).",
    ],
    "core.Commune": [
        "niscode — code INS national à 5 chiffres, immutable.",
        "postal_codes — CSV (ex: '1030,1031') utilisé pour déduire la commune depuis un CP saisi.",
    ],
    "citizens.Address": [
        "postal_code doit appartenir à la commune référencée (validation form).",
        "location (PointField SRID=31370) — calculé par géocodage côté service.",
    ],
    "vehicles.Vehicle": [
        "plate — normalisée en majuscules (espaces remplacés par '-') avant sauvegarde.",
        "archived_at — soft-delete : un véhicule archivé est masqué mais préserve l'historique.",
        "Refuse l'archivage si des cartes ACTIVE/SUSPENDED/AWAITING_PAYMENT sont liées.",
    ],
    "permits.Permit": [
        "status ∈ 9 valeurs — state machine stricte gérée par apps.permits.services.",
        "Transitions autorisées : draft → submitted → (manual_review|awaiting_payment|refused) → active → (suspended|expired|cancelled).",
        "valid_from + valid_until — dates UTC ; expired_at = horodatage de transition vers EXPIRED.",
        "attribution_snapshot (JSONB) — copie des zones au moment de l'attribution (audit trail).",
        "Une carte visiteur a une période fixe (1 jan → 1 déc) imposée par la politique.",
    ],
    "permits.VisitorCode": [
        "Plate doit être différente du propriétaire de la carte visiteur (pas d'auto-utilisation).",
        "Limite annuelle : 100 codes par carte visiteur par citoyen.",
        "Durée max : VISITOR_CODE_DEFAULT_HOURS × 18 = 72 h.",
    ],
    "payments.Payment": [
        "Contrainte unique partielle : one_succeeded_payment_per_permit — une seule réussite par carte.",
        "amount_cents — entier positif ; le montant 0 est autorisé pour les cartes visiteurs gratuites.",
        "card_brand / card_last4 — seules infos de carte stockées (PAN jamais conservé).",
    ],
    "audit.AuditLog": [
        "action ∈ 30 valeurs (PermitSubmitted, PaymentSucceeded, RgpdPurged, …).",
        "target_type / target_id — relation polymorphique (pas de FK ; survit à la suppression).",
        "payload (JSONB) — convention : {'context': {...}, 'diff': {field: [before, after]}}.",
        "Service log() est résilient : ne lève jamais, capture l'erreur dans le logger.",
    ],
    "gis_data.GISSourceVersion": [
        "is_active — un seul True à la fois (contrainte applicative dans services).",
        "polygon_count — comptage matérialisé au moment de l'import (perf).",
    ],
    "rules.PolygonRule": [
        "action ∈ {OVERRIDE_ZONECODE, RESTRICT_TYPE, DENY, ADD_ZONE, REPLACE_MAIN_ZONE}.",
        "priority — entier ; plus petit = appliqué en premier.",
        "is_active — désactivation sans suppression (préserve l'historique).",
    ],
    "permits.CommunePermitPolicy": [
        "strategy ∈ {fixed, grid, exponential} — détermine le calcul du prix.",
        "exponential_factor — utilisé si strategy=exponential (price = base × factor^(rank-1)).",
        "grid (JSONB) — utilisé si strategy=grid : liste [(rank_threshold, price_cents)].",
        "effective_from / effective_until — versionnement temporel (plusieurs politiques en file).",
    ],
}


def generate() -> str:
    pdf = PBPdf(
        title="Dictionnaire de données",
        subtitle="Tables, champs, types, contraintes et règles métier",
    )
    pdf.cover()

    # ----- Introduction --------------------------------------------------
    pdf.h1("1. Conventions")
    pdf.p(
        "Le projet adopte une approche CODE FIRST : les modèles Python "
        "Django définissent le schéma, traduits en SQL via les migrations. "
        "Chaque table préfixe son nom par celui de l'app Django (ex : "
        "permits_permit, audit_auditlog)."
    )
    pdf.bullet("Tous les noms de tables et colonnes sont en snake_case.")
    pdf.bullet("Chaque table possède une PK auto-incrémentée 'id' (BIGINT).")
    pdf.bullet("Les timestamps sont stockés en TIMESTAMPTZ (UTC) — les conversions vers Europe/Brussels sont faites à l'affichage.")
    pdf.bullet("Les contraintes uniques composites sont déclarées via Meta.constraints ou unique_together.")
    pdf.bullet("Les index composés sont déclarés via Meta.indexes pour les lookups fréquents.")
    pdf.bullet("Les choix sont stockés en VARCHAR (pas d'ENUM SQL) pour faciliter les évolutions.")

    pdf.h2("Légende des contraintes")
    pdf.table(
        headers=["Symbole", "Signification"],
        rows=[
            ["PK", "Clé primaire"],
            ["NOT NULL", "Champ obligatoire"],
            ["UNIQUE", "Valeur unique sur la table"],
            ["INDEX", "Index B-tree pour accélérer les recherches"],
            ["FK → X", "Clé étrangère vers le modèle X"],
            ["1-1 → X", "Relation OneToOne (cardinalité 1-1)"],
            ["choices=[…]", "Valeurs autorisées (énumération applicative)"],
        ],
        col_widths=[40, 134],
    )

    # ----- Tables -------------------------------------------------------
    for label_idx, (app_label, model_name) in enumerate(MODELS_ORDER):
        from django.apps import apps
        try:
            model = apps.get_model(app_label, model_name)
        except LookupError:
            continue
        meta = model._meta
        full_label = f"{label_idx + 2}. {meta.label}"
        verbose = getattr(meta, "verbose_name", model_name)
        pdf.h1(full_label)
        pdf.p(f"Table SQL : {meta.db_table} — désignation : {verbose}.")
        if model.__doc__:
            doc = " ".join(line.strip() for line in model.__doc__.strip().split("\n") if line.strip())
            if doc:
                pdf.p(f"Description : {doc[:400]}")

        pdf.h2("Champs")
        rows = _model_fields(model)
        pdf.table(
            headers=["Champ", "Libellé", "Type", "Contraintes"],
            rows=rows,
            col_widths=[35, 50, 40, 49],
        )

        # Règles métier manuelles
        key = f"{app_label}.{model_name}"
        if key in BUSINESS_RULES:
            pdf.h2("Règles métier")
            for rule in BUSINESS_RULES[key]:
                pdf.bullet(rule)

    return str(save_to(pdf, "04_dictionnaire_de_donnees.pdf"))


if __name__ == "__main__":
    print(generate())
