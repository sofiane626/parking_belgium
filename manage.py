#!/usr/bin/env python
"""
Django's command-line utility for administrative tasks.

Bootstrap quirk: PROJ (the projection library used by GeoDjango) reads
``PROJ_DATA`` from the OS environment block at DLL-load time. Setting it via
``os.environ`` inside the Python process is too late — PROJ is already
initialised. We work around this by re-spawning ourselves with the right
environment if PROJ_DATA is missing.
"""
import os
import sys
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent


def _bootstrap_proj_env() -> None:
    """If PROJ_DATA is missing, read it from .env and re-execute ourselves."""
    if os.environ.get("PROJ_DATA") or os.environ.get("_PARKING_PROJ_BOOTSTRAPPED"):
        return
    env_path = _BASE_DIR / ".env"
    if not env_path.exists():
        return
    needed = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if k in {"PROJ_LIB", "PROJ_DATA", "GDAL_DATA"}:
            needed[k] = v
    if "PROJ_LIB" in needed and "PROJ_DATA" not in needed:
        needed["PROJ_DATA"] = needed["PROJ_LIB"]
    if not needed:
        return
    import subprocess
    new_env = {**os.environ, **needed, "_PARKING_PROJ_BOOTSTRAPPED": "1"}
    completed = subprocess.run([sys.executable, *sys.argv], env=new_env)
    sys.exit(completed.returncode)


_bootstrap_proj_env()


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "parking_belgium.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH? Did you forget to activate a venv?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
