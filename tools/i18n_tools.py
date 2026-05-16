"""
Outils i18n maison — utilisés en remplacement de ``makemessages`` / ``compilemessages``
parce que gettext n'est pas installé sur la machine Windows de dev.

Commandes :
    python tools/i18n_tools.py extract     -> génère locale/messages.pot
    python tools/i18n_tools.py update      -> crée/met à jour locale/{nl,en}/LC_MESSAGES/django.po
    python tools/i18n_tools.py compile     -> compile les .po en .mo

S'appuie sur Babel (Python pur) pour la lecture/écriture .po + .mo.
L'extraction des chaînes se fait par regex (suffisant pour les patterns Django standards).
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from babel.messages.catalog import Catalog
from babel.messages.pofile import read_po, write_po
from babel.messages.mofile import write_mo

ROOT = Path(__file__).resolve().parent.parent
LOCALE_DIR = ROOT / "locale"
LANGUAGES = ["nl", "en"]

# Dossiers à scanner pour extraire les chaînes
SOURCE_DIRS = ["templates", "apps", "parking_belgium"]
# Dossiers à exclure (build, venv, etc.)
EXCLUDE_DIRS = {"node_modules", "__pycache__", "migrations", ".git", ".venv",
                "frontend", "staticfiles", "static", "dist"}

# --- Regex extracteurs ---------------------------------------------------------

# Templates Django : {% trans "..." %} ou {% trans '...' %} (avec optional `noop`).
RE_TRANS_TAG = re.compile(
    r"""\{%\s*(?:trans|translate)\s+(?P<q>['"])(?P<msg>(?:\\.|(?!\1).)+)(?P=q)""",
    re.UNICODE,
)
# {% blocktrans %}...{% endblocktrans %} (sans variables interpolées pour rester simple)
RE_BLOCKTRANS = re.compile(
    r"""\{%\s*(?:blocktrans|blocktranslate)\s*(?:\s+[^%]*)?%\}(?P<msg>.+?)\{%\s*end(?:blocktrans|blocktranslate)\s*%\}""",
    re.DOTALL,
)
# Python : _("..."), gettext("..."), gettext_lazy("...")
RE_PYTHON_GETTEXT = re.compile(
    r"""(?<![A-Za-z0-9_])(?:_|gettext|gettext_lazy|ugettext|ugettext_lazy)\(\s*(?P<q>['"])(?P<msg>(?:\\.|(?!\1).)+)(?P=q)\s*\)""",
)


def walk_sources():
    """Yield les chemins absolus des .py et .html à scanner."""
    for top in SOURCE_DIRS:
        base = ROOT / top
        if not base.exists():
            continue
        for path, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for name in files:
                if name.endswith((".py", ".html", ".txt")):
                    yield Path(path) / name


def extract_from_file(path: Path) -> list[tuple[str, int]]:
    """Retourne une liste de (msg, line_number) trouvés dans le fichier."""
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    results: list[tuple[str, int]] = []

    def add(match, msg_group="msg"):
        msg = match.group(msg_group)
        # Compte la ligne : nb de '\n' avant le début du match
        line = text.count("\n", 0, match.start()) + 1
        results.append((msg, line))

    suffix = path.suffix
    if suffix in (".html", ".txt"):
        for m in RE_TRANS_TAG.finditer(text):
            add(m)
        for m in RE_BLOCKTRANS.finditer(text):
            # Trim whitespace dans le bloc — comportement makemessages
            msg = m.group("msg").strip()
            line = text.count("\n", 0, m.start()) + 1
            results.append((msg, line))
    if suffix == ".py":
        for m in RE_PYTHON_GETTEXT.finditer(text):
            add(m)

    return results


def cmd_extract() -> None:
    """Extrait toutes les chaînes et génère locale/messages.pot."""
    LOCALE_DIR.mkdir(parents=True, exist_ok=True)
    cat = Catalog(
        project="Parking.Belgium",
        version="1.0",
        msgid_bugs_address="",
        copyright_holder="Parking.Belgium",
        charset="utf-8",
    )

    seen: dict[str, list[tuple[str, int]]] = {}
    n_files = 0
    for path in walk_sources():
        n_files += 1
        for msg, line in extract_from_file(path):
            rel = path.relative_to(ROOT).as_posix()
            seen.setdefault(msg, []).append((rel, line))

    for msg, locations in seen.items():
        # Dédup locations (Babel le ferait mais ça garde le fichier propre)
        unique_locs = list(dict.fromkeys(locations))
        cat.add(msg, locations=unique_locs)

    pot_path = LOCALE_DIR / "messages.pot"
    with pot_path.open("wb") as fh:
        write_po(fh, cat, width=78, omit_header=False, sort_output=True)

    print(f"[extract] {n_files} fichiers scannés -> {len(seen)} chaînes uniques")
    print(f"[extract] écrit : {pot_path.relative_to(ROOT)}")


def cmd_update() -> None:
    """Crée ou met à jour locale/<lang>/LC_MESSAGES/django.po à partir du .pot."""
    pot_path = LOCALE_DIR / "messages.pot"
    if not pot_path.exists():
        sys.exit("Aucun messages.pot trouvé. Lance d'abord : extract")

    with pot_path.open("rb") as fh:
        template = read_po(fh)

    for lang in LANGUAGES:
        lang_dir = LOCALE_DIR / lang / "LC_MESSAGES"
        lang_dir.mkdir(parents=True, exist_ok=True)
        po_path = lang_dir / "django.po"

        if po_path.exists():
            with po_path.open("rb") as fh:
                existing = read_po(fh, locale=lang)
            # Récupère traductions existantes
            existing_translations = {
                msg.id: msg.string for msg in existing if msg.id and msg.string
            }
        else:
            existing_translations = {}

        cat = Catalog(
            locale=lang,
            project="Parking.Belgium",
            version="1.0",
            charset="utf-8",
        )
        for msg in template:
            if not msg.id:
                continue
            translation = existing_translations.get(msg.id, "")
            cat.add(msg.id, string=translation, locations=msg.locations)

        with po_path.open("wb") as fh:
            write_po(fh, cat, width=78, omit_header=False, sort_output=True)
        print(f"[update] {lang} -> {po_path.relative_to(ROOT)} ({len(cat)} chaînes)")


def cmd_compile() -> None:
    """Compile chaque locale/<lang>/LC_MESSAGES/django.po en django.mo."""
    for lang in LANGUAGES:
        po_path = LOCALE_DIR / lang / "LC_MESSAGES" / "django.po"
        if not po_path.exists():
            print(f"[compile] {lang} : pas de .po, skip")
            continue
        with po_path.open("rb") as fh:
            cat = read_po(fh, locale=lang)
        mo_path = po_path.with_suffix(".mo")
        with mo_path.open("wb") as fh:
            write_mo(fh, cat, use_fuzzy=False)
        n_translated = sum(1 for m in cat if m.id and m.string)
        n_total = sum(1 for m in cat if m.id)
        pct = (n_translated / n_total * 100) if n_total else 0
        print(f"[compile] {lang} -> {mo_path.relative_to(ROOT)} "
              f"({n_translated}/{n_total} = {pct:.0f}%)")


def cmd_apply() -> None:
    """
    Applique les dicts FR -> trad depuis tools/translations_<lang>.py
    aux fichiers .po existants. Les traductions déjà non vides dans le .po
    sont conservées si la clé n'est pas dans le dict.
    """
    import importlib.util

    for lang in LANGUAGES:
        mod_path = ROOT / "tools" / f"translations_{lang}.py"
        if not mod_path.exists():
            print(f"[apply] {lang} : aucun translations_{lang}.py, skip")
            continue
        spec = importlib.util.spec_from_file_location(f"translations_{lang}", mod_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        translations = getattr(module, "TRANSLATIONS", {})

        po_path = LOCALE_DIR / lang / "LC_MESSAGES" / "django.po"
        if not po_path.exists():
            print(f"[apply] {lang} : pas de .po, skip")
            continue

        with po_path.open("rb") as fh:
            cat = read_po(fh, locale=lang)

        applied = 0
        for msg in cat:
            if not msg.id:
                continue
            trad = translations.get(msg.id)
            if trad and not msg.string:
                msg.string = trad
                applied += 1
            elif trad and msg.string != trad:
                msg.string = trad
                applied += 1

        with po_path.open("wb") as fh:
            write_po(fh, cat, width=78, omit_header=False, sort_output=True)
        total = sum(1 for m in cat if m.id)
        translated = sum(1 for m in cat if m.id and m.string)
        print(f"[apply] {lang} : {applied} maj appliquées, "
              f"{translated}/{total} traduits ({translated/total*100:.0f}%)")


COMMANDS = {
    "extract": cmd_extract,
    "update": cmd_update,
    "apply": cmd_apply,
    "compile": cmd_compile,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)
    COMMANDS[sys.argv[1]]()


if __name__ == "__main__":
    main()
