"""
Management command : passe en EXPIRED toutes les cartes ACTIVE ou SUSPENDED
dont la date ``valid_until`` est dépassée.

Idempotent — appelable plusieurs fois par jour sans effet de bord.

Usage :
    python manage.py expire_due           # mode normal
    python manage.py expire_due --dry-run # ne modifie rien, affiche ce qui serait fait
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.permits.models import Permit, PermitStatus
from apps.permits.services import PermitError, expire_permit


class Command(BaseCommand):
    help = "Expire les cartes ACTIVE/SUSPENDED dont valid_until est dépassée."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Affiche les cartes concernées sans les modifier.",
        )

    def handle(self, *args, dry_run: bool = False, **options):
        today = timezone.localdate()
        # ACTIVE et SUSPENDED peuvent expirer (une carte suspendue dépassée n'a
        # plus de sens — on la sort proprement du système).
        due = (
            Permit.objects
            .filter(status__in=[PermitStatus.ACTIVE, PermitStatus.SUSPENDED])
            .filter(valid_until__lt=today)
            .select_related("citizen")
            .order_by("valid_until")
        )
        total = due.count()
        if total == 0:
            self.stdout.write("Aucune carte à expirer.")
            return

        self.stdout.write(f"{total} carte(s) à expirer (valid_until < {today}):")
        ok = 0
        ko = 0
        for permit in due:
            owner = getattr(permit.citizen, "username", f"user#{permit.citizen_id}")
            line = (f"  #{permit.pk:>5} {permit.permit_type:<14} "
                    f"{owner:<20} valid_until={permit.valid_until}")
            if dry_run:
                self.stdout.write("[DRY] " + line)
                continue
            try:
                with transaction.atomic():
                    expire_permit(permit)
                self.stdout.write(self.style.SUCCESS("[OK]  " + line))
                ok += 1
            except PermitError as exc:
                self.stdout.write(self.style.ERROR(f"[KO]  {line} — {exc}"))
                ko += 1

        if dry_run:
            self.stdout.write(self.style.NOTICE(f"Dry-run : {total} carte(s) seraient expirées."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Terminé : {ok} expirée(s), {ko} en erreur."))
