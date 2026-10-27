"""Connects the Rig Rate Break-Up Sheet mail to its alert through the Notification Triggers table (safe to run again), and creates the scheduler's job
row. The alert is the legacy alert 233 "Rig Rate Break-Up Sheet", found by name, or by --alert <id>. The same can be done by hand in Masters >
Notification Triggers (Automation → Send Rig Rate Break-Up mail).

NOTE: once this row exists the scheduler sends the report when the alert's Next Mail date has arrived, at its Start Time. Check that date first.

    python manage.py setup_rig_rate_breakup
    python manage.py setup_rig_rate_breakup --alert 233"""

from django.core.management.base import BaseCommand

from core import rig_rate_breakup


class Command(BaseCommand):
    help = "Connect the Rig Rate Break-Up Sheet mail to its alert through the Notification Triggers table."

    def add_arguments(self, parser):
        parser.add_argument("--alert", type=int, default=None, help="the alert's id (default: the alert named 'Rig Rate Break-Up Sheet')")

    def handle(self, *args, **opts):
        did = rig_rate_breakup.ensure_setup(opts["alert"])
        self.stdout.write("Done: " + (", ".join(did) if did else "nothing to change (already set up, or the alert was not found)"))
        for w in rig_rate_breakup.JOB.get_setup()["warnings"]:
            self.stdout.write(self.style.WARNING("Note: " + w))
