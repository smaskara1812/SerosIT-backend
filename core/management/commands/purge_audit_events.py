"""Deletes routine audit events (exports, logins, logouts, failed logins) older than six months.

Data changes (create, update, delete, revert) are never touched: they are kept for good so a record's
history stays complete.

    python manage.py purge_audit_events              # delete events older than 6 months
    python manage.py purge_audit_events --dry-run    # only say how many
    python manage.py purge_audit_events --months 3
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import SysAuditLog


class Command(BaseCommand):
    help = "Delete audit events (exports, logins, logouts) older than N months. Data changes are kept."

    def add_arguments(self, parser):
        parser.add_argument("--months", type=int, default=6, help="Age in months (default 6)")
        parser.add_argument("--dry-run", action="store_true", help="Count only, delete nothing")

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=30 * options["months"])
        qs = SysAuditLog.objects.filter(kind="event", ts__lt=cutoff)
        n = qs.count()
        if options["dry_run"]:
            self.stdout.write(f"{n} event row(s) older than {options['months']} months would be deleted (dry run).")
            return
        qs.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {n} event row(s) older than {options['months']} months."))
