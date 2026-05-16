"""
Management command : purge ou anonymise les données expirées (RGPD art. 17 + 5).

Trois opérations :
  1. **Comptes inactifs > 3 ans** sans permits actifs ni paiements dans la
     fenêtre comptable (7 ans) sont **anonymisés** : email vidé, prénom/nom
     vidés, ``preferred_language`` reset. Ils restent en base pour la
     traçabilité comptable mais ne contiennent plus de PII.
  2. **Codes visiteurs expirés depuis > 1 an** sont supprimés.
  3. **Entrées d'audit > 3 ans** sont supprimées (recommandation APD).

Par défaut **dry-run** : affiche ce qui serait fait sans rien modifier. Pour
appliquer, passer ``--apply``.

Usage :
    python manage.py purge_expired_data            # dry-run
    python manage.py purge_expired_data --apply    # exécution réelle
"""
from __future__ import annotations

import datetime as dt

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.audit.services import AuditAction, log as audit_log
from apps.permits.models import Permit, PermitStatus, VisitorCode

User = get_user_model()

INACTIVE_USER_THRESHOLD_YEARS = 3
VISITOR_CODE_RETENTION_YEARS = 1
AUDIT_LOG_RETENTION_YEARS = 3
ACCOUNTING_RETENTION_YEARS = 7  # garde les comptes liés à un paiement récent


class Command(BaseCommand):
    help = (
        "Purge/anonymise les données expirées (comptes inactifs > 3 ans, "
        "codes visiteurs > 1 an après expiration, journaux d'audit > 3 ans)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true",
            help="Applique réellement les opérations (sans ce flag : dry-run).",
        )

    def handle(self, *args, apply: bool = False, **options):
        now = timezone.now()
        today = timezone.localdate()
        dry = not apply

        users_to_anon = self._find_inactive_users(now)
        codes_to_purge = self._find_old_visitor_codes(today)
        logs_to_purge = self._find_old_audit_logs(now)

        self.stdout.write(self.style.NOTICE(
            f"=== Purge RGPD ({'DRY-RUN' if dry else 'APPLY'}) ==="
        ))
        self.stdout.write(f"Comptes inactifs > {INACTIVE_USER_THRESHOLD_YEARS} ans à anonymiser : {len(users_to_anon)}")
        self.stdout.write(f"Codes visiteurs expirés > {VISITOR_CODE_RETENTION_YEARS} an à supprimer : {codes_to_purge.count()}")
        self.stdout.write(f"Entrées d'audit > {AUDIT_LOG_RETENTION_YEARS} ans à supprimer : {logs_to_purge.count()}")

        if dry:
            self.stdout.write(self.style.WARNING(
                "Aucune modification appliquée. Relance avec --apply pour exécuter."
            ))
            return

        with transaction.atomic():
            users_done = self._anonymise_users(users_to_anon)
            codes_done = codes_to_purge.delete()[0]
            logs_done = logs_to_purge.delete()[0]

        audit_log(
            AuditAction.RGPD_PURGED,
            actor=None,
            payload={"context": {
                "users_anonymised": users_done,
                "visitor_codes_deleted": codes_done,
                "audit_logs_deleted": logs_done,
            }},
        )
        self.stdout.write(self.style.SUCCESS(
            f"Terminé : {users_done} compte(s) anonymisé(s), "
            f"{codes_done} code(s) supprimé(s), {logs_done} log(s) supprimé(s)."
        ))

    # ----- detection helpers -----------------------------------------------

    def _find_inactive_users(self, now):
        """
        Comptes citoyens :
        - last_login < today - 3 ans (ou jamais connecté + inscription > 3 ans)
        - sans permit ACTIVE / SUSPENDED / AWAITING_PAYMENT
        - sans paiement dans les 7 dernières années (rétention TVA)
        - email non vide (sinon déjà anonymisé)
        """
        cutoff = now - dt.timedelta(days=365 * INACTIVE_USER_THRESHOLD_YEARS)
        accounting_cutoff = now - dt.timedelta(days=365 * ACCOUNTING_RETENTION_YEARS)

        from apps.payments.models import Payment
        live_permit_statuses = [
            PermitStatus.ACTIVE, PermitStatus.SUSPENDED,
            PermitStatus.AWAITING_PAYMENT, PermitStatus.MANUAL_REVIEW,
        ]
        active_owner_ids = set(
            Permit.objects.filter(status__in=live_permit_statuses)
            .values_list("citizen_id", flat=True)
        )
        recent_payer_ids = set(
            Payment.objects.filter(initiated_at__gt=accounting_cutoff)
            .values_list("citizen_id", flat=True)
        )
        excluded = active_owner_ids | recent_payer_ids

        candidates = []
        for u in User.objects.exclude(email="").exclude(pk__in=excluded):
            stamp = u.last_login or u.date_joined
            if stamp and stamp < cutoff:
                candidates.append(u)
        return candidates

    def _find_old_visitor_codes(self, today):
        cutoff = today - dt.timedelta(days=365 * VISITOR_CODE_RETENTION_YEARS)
        return VisitorCode.objects.filter(valid_until__date__lt=cutoff)

    def _find_old_audit_logs(self, now):
        cutoff = now - dt.timedelta(days=365 * AUDIT_LOG_RETENTION_YEARS)
        return AuditLog.objects.filter(created_at__lt=cutoff)

    # ----- mutations -------------------------------------------------------

    def _anonymise_users(self, users) -> int:
        """Vide les PII mais garde la ligne pour la traçabilité comptable."""
        count = 0
        for u in users:
            u.email = ""
            u.first_name = ""
            u.last_name = ""
            u.preferred_language = "fr"
            u.is_active = False
            u.save(update_fields=[
                "email", "first_name", "last_name",
                "preferred_language", "is_active",
            ])
            count += 1
        return count
