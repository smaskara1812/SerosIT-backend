"""Closes Rig Performance months by hand (retrospectively): every rig that reported in the month gets its Rig Month Plan row (ILM days 0 when none were entered)
marked closed, so the month's ILM day count is final. Use it for past months once their ILM days have been entered (or confirmed as 0), for example
Aug-Oct 2026. Months are closed automatically by the daily report after this; a rig that had ILM/IPM activity with no ILM days entered is left open
(shown by --dry-run) unless --force is given.

    python manage.py close_rig_months --month 2026-08 --dry-run
    python manage.py close_rig_months --month 2026-08 --month 2026-09 --month 2026-10
    python manage.py close_rig_months --month 2026-10 --force --note "ILM days confirmed 0"
"""

import datetime

from django.core.management.base import BaseCommand, CommandError

from core import rig_performance_month as m


class Command(BaseCommand):
    help = "Close Rig Performance months (the ILM day count of each rig becomes final)."

    def add_arguments(self, parser):
        parser.add_argument("--month", action="append", required=True, help="YYYY-MM (repeat for several months)")
        parser.add_argument("--note", default="closed retrospectively")
        parser.add_argument("--force", action="store_true", help="close rigs with ILM/IPM activity and no ILM days too (the days are taken as 0)")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        today = datetime.date.today()
        for raw in opts["month"]:
            try:
                first = datetime.datetime.strptime(raw + "-01", "%Y-%m-%d").date()
            except ValueError:
                raise CommandError(f"{raw}: use YYYY-MM")
            last = first.replace(day=28) + datetime.timedelta(days=4)
            last = last - datetime.timedelta(days=last.day)
            if last >= today:
                self.stdout.write(self.style.WARNING(f"{first:%B %Y}: has not ended, skipped"))
                continue
            pending = m.unconfirmed_ilm(first)
            if opts["dry_run"]:
                self.stdout.write(f"{first:%B %Y}: would close; ILM days still to enter or confirm: {', '.join(pending) or 'none'}")
                continue
            closed, left = m.close_month(first, note=opts["note"], auto=not opts["force"])
            self.stdout.write(f"{first:%B %Y}: {closed} closed" + (f"; left open (ILM/IPM recorded, no ILM days entered): {', '.join(left)}" if left else ""))
