"""
Génère l'ensemble des 10 livrables TFE dans le dossier documents/.

Usage :
    python -m tools.docs.generate_all

Le DUMP SQL (07) est généré séparément via pg_dump — voir README.
"""
from __future__ import annotations

from .d01_cahier_charges import generate as gen_01
from .d02_business_plan import generate as gen_02
from .d03_schema_bdd import generate as gen_03
from .d04_dictionnaire import generate as gen_04
from .d05_conception_graphique import generate as gen_05
from .d06_progiciels import generate as gen_06
from .d07_dump_pdf import generate as gen_07
from .d08_documentation_api import generate as gen_08
from .d09_securite import generate as gen_09
from .d10_seo import generate as gen_10


GENERATORS = [
    ("01 Cahier de charges fonctionnel", gen_01),
    ("02 Business Plan",                  gen_02),
    ("03 Schéma de base de données",      gen_03),
    ("04 Dictionnaire de données",        gen_04),
    ("05 Rapport de conception graphique", gen_05),
    ("06 Progiciels et solutions techniques", gen_06),
    ("07 DUMP base de données (PDF)",     gen_07),
    ("08 Documentation API & Open Data",  gen_08),
    ("09 Stratégie de sécurité",          gen_09),
    ("10 Stratégie SEO",                  gen_10),
]


def main():
    print("Generation des livrables TFE...\n")
    for name, fn in GENERATORS:
        try:
            path = fn()
            print(f"  [OK] {name} -> {path}")
        except Exception as exc:  # noqa: BLE001
            print(f"  [KO] {name} : {exc}")
    print("\nNe pas oublier le DUMP SQL :")
    print('  PGPASSWORD=parking_belgium "C:/Program Files/PostgreSQL/17/bin/pg_dump.exe" \\')
    print('    -U parking_belgium -h localhost -d parking_belgium \\')
    print('    --column-inserts --inserts --no-owner --no-privileges \\')
    print('    > documents/07_dump_base_donnees.sql')


if __name__ == "__main__":
    main()
