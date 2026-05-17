"""
Management command : envoie un email de rappel aux citoyens dont la carte
de stationnement expire dans 15 jours (par défaut).

Idempotent — chaque carte ne reçoit qu'un seul rappel (champ
``Permit.expiry_reminder_sent_at`` protège contre les re-envois).

Usage :
    python manage.py send_expiry_reminders            # mode normal
    python manage.py send_expiry_reminders --dry-run  # affiche sans envoyer
    python manage.py send_expiry_reminders --days 30  # rappel à J-30 au lieu de J-15
"""
from __future__ import annotations

import datetime as dt

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.permits.models import Permit, PermitStatus


class Command(BaseCommand):
    help = "Envoie un rappel d'expiration aux cartes ACTIVE qui expirent bientôt."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Affiche les cartes concernées sans envoyer.",
        )
        parser.add_argument(
            "--days", type=int, default=15,
            help="Combien de jours avant expiration on envoie le rappel (défaut: 15).",
        )

    def handle(self, *args, dry_run: bool = False, days: int = 15, **options):
        today = timezone.localdate()
        target_date = today + dt.timedelta(days=days)

        # Cartes ACTIVE dont valid_until tombe entre aujourd'hui et target_date,
        # et qui n'ont pas encore reçu de rappel.
        due = (
            Permit.objects
            .filter(status=PermitStatus.ACTIVE)
            .filter(valid_until__gte=today, valid_until__lte=target_date)
            .filter(expiry_reminder_sent_at__isnull=True)
            .select_related("citizen", "vehicle")
            .order_by("valid_until")
        )
        total = due.count()
        if total == 0:
            self.stdout.write("Aucun rappel à envoyer.")
            return

        self.stdout.write(
            f"{total} carte(s) à notifier "
            f"(expirent entre {today} et {target_date}):"
        )

        ok = 0
        ko = 0
        for permit in due:
            owner = getattr(permit.citizen, "username", f"user#{permit.citizen_id}")
            line = (f"  #{permit.pk:>5} {permit.permit_type:<14} {owner:<20} "
                    f"expire le {permit.valid_until}")
            if dry_run:
                self.stdout.write("[DRY] " + line)
                continue
            try:
                from apps.payments.emails import send_expiry_reminder_email
                send_expiry_reminder_email(permit)
                with transaction.atomic():
                    Permit.objects.filter(pk=permit.pk).update(
                        expiry_reminder_sent_at=timezone.now(),
                    )
                self.stdout.write(self.style.SUCCESS("[OK]  " + line))
                ok += 1
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"[KO]  {line} — {exc}"))
                ko += 1

        if dry_run:
            self.stdout.write(self.style.NOTICE(
                f"Dry-run : {total} rappel(s) seraient envoyé(s)."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Terminé : {ok} envoyé(s), {ko} en erreur."
            ))
