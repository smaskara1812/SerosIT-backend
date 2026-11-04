"""Connects the Activity Monitor mail to its alert through the Notification Triggers table (safe to run again), and creates the scheduler's job row. The alert
is the legacy alert 58 "Activity Monitor - EOSL", found by name, or by --alert <id>. The same can be done by hand in Masters > Notification Triggers
(Automation → Send Activity Monitor mail).

NOTE: once this row exists the scheduler sends the mail when the alert's Next Mail date has arrived, at its Start Time, to the alert's real recipients.
Check that date (and Report Mails > Send a test) first. On a development database, think before running it.

    python manage.py setup_activity_monitor_alert
    python manage.py setup_activity_monitor_alert --alert 58"""

from django.core.management.base import BaseCommand

from core import activity_monitor_alert


class Command(BaseCommand):
    help = "Connect the Activity Monitor mail to its alert through the Notification Triggers table."

    def add_arguments(self, parser):
        parser.add_argument("--alert", type=int, default=None, help="the alert's id (default: the alert named 'Activity Monitor - EOSL')")

    def handle(self, *args, **opts):
        did = activity_monitor_alert.ensure_setup(opts["alert"])
        self.stdout.write("Done: " + (", ".join(did) if did else "nothing to change (already set up, or the alert was not found)"))
        for w in activity_monitor_alert.JOB.get_setup()["warnings"]:
            self.stdout.write(self.style.WARNING("Note: " + w))
