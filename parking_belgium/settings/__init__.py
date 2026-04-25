"""
Bootstrap that runs before any settings module.

Some env vars (notably ``PROJ_DATA`` for GDAL) must be set before GDAL is
loaded. Reading them here means they're in ``os.environ`` for the very first
GDAL call, no matter which settings file (dev/prod) is active.
"""
import os
from pathlib import Path

import environ

_BASE_DIR = Path(__file__).resolve().parent.parent.parent
environ.Env.read_env(_BASE_DIR / ".env")

# PROJ 8+ uses PROJ_DATA; older versions used PROJ_LIB. We set both.
_proj_path = os.environ.get("PROJ_LIB")
if _proj_path:
    os.environ.setdefault("PROJ_DATA", _proj_path)
