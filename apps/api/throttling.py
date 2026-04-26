"""Throttle scopes spécifiques à l'API publique."""
from rest_framework.throttling import ScopedRateThrottle


class CheckRightThrottle(ScopedRateThrottle):
    """Limite dédiée à ``/check-right/`` (taux plus élevé que le défaut user)."""
    scope = "check_right"
