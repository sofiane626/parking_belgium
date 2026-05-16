"""
Helper d'export CSV pour le back-office.

Streaming via ``StreamingHttpResponse`` pour ne pas charger toute la liste
en mémoire — utile dès qu'on dépasse quelques milliers de lignes (paiements,
audit, utilisateurs).

UTF-8 + BOM (``﻿``) pour qu'Excel reconnaisse l'encodage automatiquement.
Séparateur ``;`` (convention francophone, Excel FR/NL le détecte sans dialogue).
"""
from __future__ import annotations

import csv
from typing import Iterable, Sequence

from django.http import StreamingHttpResponse
from django.utils import timezone


class _Echo:
    """File-like object dont write() retourne la valeur écrite. Permet à
    ``csv.writer`` de produire des lignes consommables par un générateur."""

    def write(self, value):
        return value


def stream_csv(
    *,
    filename_base: str,
    header: Sequence[str],
    rows: Iterable[Sequence],
) -> StreamingHttpResponse:
    """
    Construit une réponse CSV streamée.

    :param filename_base: nom de fichier sans extension ni date. Une date ISO
        sera suffixée automatiquement : ``permits_2026-05-07.csv``.
    :param header: ligne d'en-têtes.
    :param rows: itérable (idéalement un générateur) de lignes, chacune étant
        un tuple/liste de valeurs convertibles en str.
    """
    pseudo_buffer = _Echo()
    writer = csv.writer(pseudo_buffer, delimiter=";")

    def generate():
        # BOM Excel sur la première ligne uniquement.
        yield "﻿" + writer.writerow(header)
        for row in rows:
            yield writer.writerow(row)

    today = timezone.localdate().isoformat()
    fname = f"{filename_base}_{today}.csv"
    response = StreamingHttpResponse(generate(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{fname}"'
    return response
