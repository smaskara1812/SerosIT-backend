"""Connects the HAZ ID Register mail to its alert through the Notification Triggers table (safe to run again), and creates the scheduler's job row.
The alert is the legacy alert 228 "HAZ ID Register Mail Alert", found by name, or by --alert <id>. The same can be done by hand in Masters >
Notification Triggers (Automation → Send HAZ ID register mail).

NOTE: once this row exists the scheduler considers the report due as soon as the alert's Next Mail date has arrived. Check that date first.

    python manage.py setup_haz_id_register
    python manage.py setup_haz_id_register --alert 228"""

from django.core.management.base import BaseCommand

from core import haz_id_register


class Command(BaseCommand):
    help = "Connect the HAZ ID Register mail to its alert through the Notification Triggers table."

    def add_arguments(self, parser):
        parser.add_argument("--alert", type=int, default=None, help="the alert's id (default: the alert named 'HAZ ID Register Mail Alert')")

    def handle(self, *args, **opts):
        did = haz_id_register.ensure_setup(opts["alert"])
        self.stdout.write("Done: " + (", ".join(did) if did else "nothing to change (already set up, or the alert was not found)"))
        for w in haz_id_register.JOB.get_setup()["warnings"]:
            self.stdout.write(self.style.WARNING("Note: " + w))
