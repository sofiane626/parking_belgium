"""
Console email backend forçant l'encodage UTF-8 — corrige l'UnicodeEncodeError
sur Windows où ``sys.stdout`` est en cp1252 et casse sur les caractères
non-latin1 (→, ², caractères accentués…).
"""
from __future__ import annotations

import sys

from django.core.mail.backends.console import EmailBackend as ConsoleEmailBackend


class EmailBackend(ConsoleEmailBackend):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # On Windows the default stream is wrapped in a cp1252 TextIOWrapper.
        # Reconfigure (Python 3.7+) to force UTF-8.
        try:
            self.stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            # Buffered/non-TextIO stream (e.g. pytest capture) — fall back to
            # writing through stdout.buffer which is bytes-safe.
            self.stream = sys.stdout
