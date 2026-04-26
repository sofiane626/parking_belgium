"""
Point d'entrée unique du journal d'audit : ``log(action, …)``.

Règle d'or : **un échec d'audit ne doit jamais casser le métier**. Toutes les
exceptions sont attrapées et envoyées au logger Python ; l'appelant n'a pas à
gérer les erreurs.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any

from django.conf import settings

from .models import DEFAULT_SEVERITY, AuditAction, AuditLog, AuditSeverity

logger = logging.getLogger("apps.audit")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_request_ip(request) -> str | None:
    """
    Renvoie l'IP source d'une ``HttpRequest`` Django.

    Tient compte de ``X-Forwarded-For`` si la plateforme est derrière un proxy
    (ex: nginx, Cloudflare). On prend la première IP de la chaîne, c'est-à-dire
    celle du client originel.
    """
    if request is None:
        return None
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def hash_plate(plate: str) -> str:
    """
    Hash HMAC-SHA256 stable d'une plaque, tronqué à 16 caractères hex.

    Stable : la même plaque produira toujours le même hash (utile pour
    corréler les appels API à une plaque donnée).
    Non réversible : RGPD-friendly, on ne stocke pas la plaque en clair pour
    les événements à fort volume comme ``api_check_right``.
    """
    if not plate:
        return ""
    key = settings.SECRET_KEY.encode("utf-8")
    digest = hmac.new(key, plate.encode("utf-8"), hashlib.sha256).hexdigest()
    return digest[:16]


def diff_dict(before: dict[str, Any], after: dict[str, Any]) -> dict[str, list]:
    """
    Renvoie ``{champ: [avant, après]}`` pour les clés où la valeur a changé.
    Utile pour les changements de rôle, de policy, etc.
    """
    out: dict[str, list] = {}
    for k in set(before) | set(after):
        b, a = before.get(k), after.get(k)
        if b != a:
            out[k] = [b, a]
    return out


# ---------------------------------------------------------------------------
# Service principal
# ---------------------------------------------------------------------------

def log(
    action: str,
    *,
    actor=None,
    target=None,
    payload: dict | None = None,
    ip: str | None = None,
    request=None,
    severity: str | None = None,
) -> AuditLog | None:
    """
    Crée une entrée d'audit. Ne lève **jamais** d'exception côté appelant.

    Paramètres :
    - ``action`` : valeur d'``AuditAction``.
    - ``actor`` : User déclencheur — si fourni, on snapshot son ``role``.
    - ``target`` : instance Django Model ciblée — on déduit ``target_type``,
      ``target_id`` et ``target_label = str(target)``.
    - ``payload`` : dict JSON-sérialisable. Convention : ``{"diff": {...},
      "context": {...}}`` mais reste libre.
    - ``ip`` : IP source explicite. Si ``request`` est fourni à la place, on
      l'extrait automatiquement (X-Forwarded-For inclus).
    - ``request`` : raccourci — extrait actor + ip s'ils ne sont pas fournis.
    - ``severity`` : surcharge le mapping par défaut.

    Renvoie l'``AuditLog`` créé, ou ``None`` si une erreur est survenue
    (loggée mais swallowée).
    """
    try:
        # Auto-extraction depuis la request si fournie
        if request is not None:
            if actor is None and getattr(request, "user", None) and request.user.is_authenticated:
                actor = request.user
            if ip is None:
                ip = extract_request_ip(request)

        target_type = ""
        target_id = None
        target_label = ""
        if target is not None:
            target_type = type(target).__name__.lower()
            target_id = getattr(target, "pk", None)
            try:
                target_label = str(target)[:200]
            except Exception:  # noqa: BLE001 — on ne fait pas confiance à __str__
                target_label = ""

        return AuditLog.objects.create(
            actor=actor if actor is not None and getattr(actor, "pk", None) else None,
            actor_role=getattr(actor, "role", "") or "",
            action=action,
            severity=severity or DEFAULT_SEVERITY.get(action, AuditSeverity.INFO),
            target_type=target_type,
            target_id=target_id,
            target_label=target_label,
            payload=payload or {},
            ip=ip,
        )
    except Exception:  # noqa: BLE001 — résilience absolue
        logger.exception("Audit log failed for action=%s", action)
        return None


__all__ = [
    "log",
    "extract_request_ip",
    "hash_plate",
    "diff_dict",
    "AuditAction",
    "AuditSeverity",
]
