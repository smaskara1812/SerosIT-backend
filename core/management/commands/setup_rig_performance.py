"""Connects the Rig Performance mail to its alert through the Notification Triggers table (safe to run again), and creates the scheduler's job row. The alert
is the alert you create for the Rig Performance mail, found by name, or by --alert <id>. The same can be done by hand in Masters > Notification Triggers
(Automation → Send Rig Performance mail).

NOTE: once this row exists the scheduler sends the mail when the alert's Next Mail date has arrived, at its Start Time, to the alert's real recipients.
Check that date (and Report Mails > Send a test) first. On a development database, think before running it.

    python manage.py setup_rig_performance
    python manage.py setup_rig_performance --alert <id>"""

from django.core.management.base import BaseCommand

from core import rig_performance_month


class Command(BaseCommand):
    help = "Connect the Rig Performance mail to its alert through the Notification Triggers table."

    def add_arguments(self, parser):
        parser.add_argument("--alert", type=int, default=None, help="the alert's id (default: the alert named 'Rig Performance')")

    def handle(self, *args, **opts):
        did = rig_performance_month.ensure_setup(opts["alert"])
        self.stdout.write("Done: " + (", ".join(did) if did else "nothing to change (already set up, or the alert was not found)"))
        for w in rig_performance_month.JOB.get_setup()["warnings"]:
            self.stdout.write(self.style.WARNING("Note: " + w))
