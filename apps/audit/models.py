"""
Journal d'audit applicatif.

Une ligne ``AuditLog`` = un événement métier signifiant. La table est volontaire-
ment écrite uniquement (jamais d'``update``) — elle reflète ce qui s'est passé
dans le temps, pas l'état courant du système.

Pourquoi pas de ``GenericForeignKey`` :
les paires ``target_type`` / ``target_id`` plates suffisent et restent lisibles
même si l'objet ciblé est supprimé plus tard. Ça évite aussi un index sur
``content_type`` peu sélectif.

Convention de payload (pour permettre des affichages structurés côté UI) :

- ``payload.diff`` : ``{"role": ["citizen", "agent"]}`` quand une valeur change
  — toujours ``[avant, après]``.
- ``payload.context`` : reste libre (raison, montant, paramètres d'appel API…).
"""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class AuditAction(models.TextChoices):
    # ---- permits ----------------------------------------------------------
    PERMIT_SUBMITTED   = "permit_submitted",   _("Carte soumise")
    PERMIT_APPROVED    = "permit_approved",    _("Carte approuvée (revue manuelle)")
    PERMIT_REFUSED     = "permit_refused",     _("Carte refusée")
    PERMIT_ACTIVATED   = "permit_activated",   _("Carte activée")
    PERMIT_SUSPENDED   = "permit_suspended",   _("Carte suspendue")
    PERMIT_EXPIRED     = "permit_expired",     _("Carte expirée")
    PERMIT_CANCELLED   = "permit_cancelled",   _("Carte annulée")

    # ---- payments ---------------------------------------------------------
    PAYMENT_SUCCEEDED  = "payment_succeeded",  _("Paiement validé")
    PAYMENT_REFUNDED   = "payment_refunded",   _("Paiement remboursé")
    PAYMENT_CANCELLED  = "payment_cancelled",  _("Paiement annulé")
    PAYMENT_SIMULATED  = "payment_simulated",  _("Paiement simulé (debug/staff)")

    # ---- users / auth -----------------------------------------------------
    USER_ROLE_CHANGED   = "user_role_changed",   _("Rôle utilisateur modifié")
    USER_BASICS_UPDATED = "user_basics_updated", _("Profil utilisateur modifié")
    USER_DEACTIVATED    = "user_deactivated",    _("Utilisateur désactivé")
    USER_REACTIVATED    = "user_reactivated",    _("Utilisateur réactivé")
    PASSWORD_RESET_SENT = "password_reset_sent", _("Email de reset envoyé")
    AUTH_FAILED         = "auth_failed",         _("Échec d'authentification")

    # ---- API tokens -------------------------------------------------------
    API_TOKEN_ISSUED   = "api_token_issued",   _("Token API émis")
    API_TOKEN_REVOKED  = "api_token_revoked",  _("Token API révoqué")
    API_CHECK_RIGHT    = "api_check_right",    _("Appel API check-right")

    # ---- vehicles ---------------------------------------------------------
    VEHICLE_ARCHIVED   = "vehicle_archived",   _("Véhicule archivé")
    VEHICLE_RESTORED   = "vehicle_restored",   _("Véhicule restauré")

    # ---- back-office config ----------------------------------------------
    POLICY_CHANGED         = "policy_changed",         _("Politique commune modifiée")
    PERMIT_CONFIG_CHANGED  = "permit_config_changed",  _("Configuration globale modifiée")
    POLYGON_RULE_CHANGED   = "polygon_rule_changed",   _("Règle de polygone modifiée")

    # ---- GIS --------------------------------------------------------------
    GIS_IMPORTED               = "gis_imported",               _("Import GIS effectué")
    GIS_ACTIVE_VERSION_CHANGED = "gis_active_version_changed", _("Version GIS active changée")


class AuditSeverity(models.TextChoices):
    INFO     = "info",     _("Information")
    NOTICE   = "notice",   _("Notable")
    WARNING  = "warning",  _("Avertissement")
    CRITICAL = "critical", _("Critique")


# Mapping action → severity par défaut. Surchargeable au cas par cas via
# ``log(..., severity=...)``.
DEFAULT_SEVERITY: dict[str, str] = {
    # info
    AuditAction.PERMIT_SUBMITTED:    AuditSeverity.INFO,
    AuditAction.PERMIT_APPROVED:     AuditSeverity.INFO,
    AuditAction.PERMIT_ACTIVATED:    AuditSeverity.INFO,
    AuditAction.PERMIT_EXPIRED:      AuditSeverity.INFO,
    AuditAction.PAYMENT_SUCCEEDED:   AuditSeverity.INFO,
    AuditAction.API_CHECK_RIGHT:     AuditSeverity.INFO,
    AuditAction.USER_BASICS_UPDATED: AuditSeverity.INFO,
    AuditAction.PASSWORD_RESET_SENT: AuditSeverity.INFO,
    AuditAction.VEHICLE_ARCHIVED:    AuditSeverity.INFO,
    AuditAction.VEHICLE_RESTORED:    AuditSeverity.INFO,
    # notice
    AuditAction.USER_ROLE_CHANGED:     AuditSeverity.NOTICE,
    AuditAction.API_TOKEN_ISSUED:      AuditSeverity.NOTICE,
    AuditAction.POLICY_CHANGED:        AuditSeverity.NOTICE,
    AuditAction.PERMIT_CONFIG_CHANGED: AuditSeverity.NOTICE,
    AuditAction.POLYGON_RULE_CHANGED:  AuditSeverity.NOTICE,
    AuditAction.PERMIT_REFUSED:        AuditSeverity.NOTICE,
    AuditAction.PERMIT_CANCELLED:      AuditSeverity.NOTICE,
    AuditAction.PAYMENT_CANCELLED:     AuditSeverity.NOTICE,
    AuditAction.PAYMENT_SIMULATED:     AuditSeverity.NOTICE,
    AuditAction.USER_DEACTIVATED:      AuditSeverity.NOTICE,
    AuditAction.USER_REACTIVATED:      AuditSeverity.NOTICE,
    # warning
    AuditAction.PERMIT_SUSPENDED:    AuditSeverity.WARNING,
    AuditAction.PAYMENT_REFUNDED:    AuditSeverity.WARNING,
    AuditAction.AUTH_FAILED:         AuditSeverity.WARNING,
    AuditAction.API_TOKEN_REVOKED:   AuditSeverity.WARNING,
    AuditAction.GIS_IMPORTED:        AuditSeverity.WARNING,
    # critical
    AuditAction.GIS_ACTIVE_VERSION_CHANGED: AuditSeverity.CRITICAL,
}


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="+",
        help_text=_("Null = action déclenchée par le système (cron, signal)."),
    )
    actor_role = models.CharField(
        _("rôle au moment de l'action"),
        max_length=20, blank=True,
        help_text=_("Snapshot — préservé même si l'utilisateur change de rôle ensuite."),
    )

    action = models.CharField(
        _("action"),
        max_length=50,
        choices=AuditAction.choices,
        db_index=True,
    )
    severity = models.CharField(
        _("sévérité"),
        max_length=10,
        choices=AuditSeverity.choices,
        default=AuditSeverity.INFO,
        db_index=True,
    )

    target_type = models.CharField(
        _("type de cible"),
        max_length=50, blank=True, db_index=True,
        help_text=_("Ex: permit, payment, user, vehicle, gis_polygon, api_token."),
    )
    target_id = models.BigIntegerField(
        _("id de la cible"),
        null=True, blank=True, db_index=True,
    )
    target_label = models.CharField(
        _("libellé de la cible"),
        max_length=200, blank=True,
        help_text=_("Snapshot textuel (str(target)) — survit à la suppression de l'objet."),
    )

    payload = models.JSONField(_("contenu"), default=dict, blank=True)
    ip = models.GenericIPAddressField(_("IP source"), null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = _("entrée d'audit")
        verbose_name_plural = _("journal d'audit")
        indexes = [
            models.Index(fields=["action", "-created_at"]),
            models.Index(fields=["actor", "-created_at"]),
            models.Index(fields=["target_type", "target_id"]),
        ]

    def __str__(self) -> str:
        who = self.actor.username if self.actor_id else "system"
        return f"[{self.severity}] {self.action} by {who} @ {self.created_at:%Y-%m-%d %H:%M:%S}"
