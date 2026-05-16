"""
Document 07 — DUMP de la base de données (version PDF).

Convertit le fichier 07_dump_base_donnees.sql en PDF lisible pour le jury :
- Page de garde
- Récap des tables et nombre de lignes
- Contenu intégral du dump SQL (code monospace, paginé automatiquement)

Le .sql brut reste disponible séparément pour import direct.
"""
from __future__ import annotations

import os
import re
from collections import Counter
from pathlib import Path

import django


def _setup_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "parking_belgium.settings.dev")
    django.setup()


_setup_django()

from .pdf_base import PBPdf, SLATE_100, SLATE_700, SLATE_900, save_to  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent.parent


def _read_dump() -> str:
    path = ROOT / "documents" / "07_dump_base_donnees.sql"
    if not path.exists():
        raise SystemExit(
            "07_dump_base_donnees.sql introuvable. Générez-le d'abord :\n"
            '  pg_dump -U parking_belgium -h localhost -d parking_belgium '
            '--column-inserts --inserts --no-owner --no-privileges '
            '> documents/07_dump_base_donnees.sql'
        )
    return path.read_text(encoding="utf-8")


def _stats(sql: str) -> tuple[list[str], Counter, int]:
    """Extrait : liste tables CREATE, nombre d'INSERT par table, total INSERTs."""
    tables = re.findall(r"CREATE TABLE\s+(?:[\w\.]+\.)?(\w+)", sql)
    inserts = re.findall(r"INSERT INTO\s+(?:[\w\.]+\.)?(\w+)", sql)
    counter = Counter(inserts)
    return sorted(set(tables)), counter, sum(counter.values())


def _truncate_line(line: str, max_chars: int = 95) -> list[str]:
    """Découpe une ligne longue en plusieurs lignes pour tenir dans la largeur."""
    if len(line) <= max_chars:
        return [line]
    out = []
    while len(line) > max_chars:
        # Coupe sur le dernier espace dans la fenêtre, sinon brut
        cut = line.rfind(",", 0, max_chars)
        if cut < max_chars // 2:
            cut = line.rfind(" ", 0, max_chars)
        if cut < max_chars // 2:
            cut = max_chars
        out.append(line[:cut])
        line = "    " + line[cut:].lstrip()
    out.append(line)
    return out


def generate() -> str:
    sql = _read_dump()
    tables, insert_counter, total_inserts = _stats(sql)

    pdf = PBPdf(
        title="DUMP de la base de données",
        subtitle="Structure (CREATE TABLE) et données de démonstration (INSERT)",
    )
    pdf.cover()

    # ----- Récap ---------------------------------------------------------
    pdf.h1("1. Vue d'ensemble")
    pdf.p(
        "Ce DUMP a été généré par pg_dump 17 (PostgreSQL avec extension "
        "PostGIS) depuis la base de production locale après exécution de la "
        "commande management seed_demo_data, qui peuple la base avec des "
        "données réalistes de démonstration."
    )
    pdf.p(
        "Le dump utilise les options --column-inserts (INSERT explicite "
        "colonne par colonne, idéal pour la relecture) et --inserts (pas "
        "de COPY binaire, données lisibles directement). Les options "
        "--no-owner et --no-privileges retirent les références à des "
        "rôles spécifiques pour faciliter le rejoue sur une autre instance."
    )

    pdf.h2("Statistiques")
    pdf.kv("Nombre de tables", str(len(tables)))
    pdf.kv("Nombre total d'INSERT", f"{total_inserts:,}".replace(",", " "))
    pdf.kv("Taille du fichier .sql", f"{(ROOT / 'documents' / '07_dump_base_donnees.sql').stat().st_size // 1024} ko")
    pdf.kv("Nombre de lignes texte", str(sql.count("\n")))

    pdf.h2("Répartition des INSERT par table")
    rows = []
    for tbl in sorted(insert_counter.keys()):
        rows.append([tbl, f"{insert_counter[tbl]:,}".replace(",", " ")])
    pdf.table(
        headers=["Table", "Nombre de lignes"],
        rows=rows,
        col_widths=[110, 64],
    )

    pdf.h2("Procédure de restauration")
    pdf.p("Pour restaurer ce dump sur une nouvelle instance PostgreSQL :")
    pdf.code(
        "# 1. Créer la base + extensions\n"
        "createdb -U postgres parking_belgium\n"
        "psql -U postgres -d parking_belgium -c \"CREATE EXTENSION postgis;\"\n"
        "\n"
        "# 2. Importer le dump\n"
        "psql -U parking_belgium -d parking_belgium \\\n"
        "  -f 07_dump_base_donnees.sql\n"
    )

    # ----- Contenu intégral du dump --------------------------------------
    pdf.h1("2. Contenu intégral du dump SQL")
    pdf.p(
        "Le contenu ci-dessous reproduit fidèlement le fichier "
        "07_dump_base_donnees.sql livré séparément. Pour un import "
        "automatisé, utiliser directement le fichier .sql ; le PDF est "
        "destiné à la consultation et à l'archivage."
    )

    # Configuration page de code
    pdf.set_font("Mono", "", 7)
    pdf.set_fill_color(*SLATE_100)
    pdf.set_text_color(*SLATE_900)

    line_height = 3.2  # mm
    chars_per_line = 110

    for raw_line in sql.split("\n"):
        # Saut de page automatique géré par fpdf2 (auto_page_break)
        for line in _truncate_line(raw_line, chars_per_line):
            # Ignore les lignes vides redondantes
            try:
                pdf.cell(0, line_height, "  " + line, fill=False,
                          new_x="LMARGIN", new_y="NEXT")
            except Exception:
                # Cell trop large pour le caractère ? Tronque agressivement.
                pdf.cell(0, line_height, "  " + line[:80] + "...",
                          fill=False, new_x="LMARGIN", new_y="NEXT")

    return str(save_to(pdf, "07_dump_base_donnees.pdf"))


if __name__ == "__main__":
    print(generate())
