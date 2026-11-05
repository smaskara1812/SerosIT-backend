"""Connects the Drilling Info Status mail to its alert through the Notification Triggers table (safe to run again), and creates the scheduler's job
row. The alert is the legacy alert 244 "Drilling Info Status", found by name, or by --alert <id>. The same can be done by hand in Masters >
Notification Triggers (Automation → Send Drilling Info Status mail).

NOTE: once this row exists the scheduler sends the mail when the alert's Next Mail date has arrived (set it on Report Mails, normally every day: Frequency 1), at
its Start Time, to the rig's recipients and the alert's real recipients. Check Report Mails > Send a test first.

    python manage.py setup_drilling_info_status
    python manage.py setup_drilling_info_status --alert 244"""

from django.core.management.base import BaseCommand

from core import drilling_info_status


class Command(BaseCommand):
    help = "Connect the Drilling Info Status mail to its alert through the Notification Triggers table."

    def add_arguments(self, parser):
        parser.add_argument("--alert", type=int, default=None, help="the alert's id (default: the alert named 'Drilling Info Status')")

    def handle(self, *args, **opts):
        did = drilling_info_status.ensure_setup(opts["alert"])
        self.stdout.write("Done: " + (", ".join(did) if did else "nothing to change (already set up, or the alert was not found)"))
        for w in drilling_info_status.JOB.get_setup()["warnings"]:
            self.stdout.write(self.style.WARNING("Note: " + w))
