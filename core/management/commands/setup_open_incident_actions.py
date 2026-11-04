"""Connects the Open Incident Actions mail to its alert through the Notification Triggers table (safe to run again), and creates the scheduler's job row. The alert
is the legacy alert 141 "Open Incident Actions", found by name, or by --alert <id>. The same can be done by hand in Masters > Notification Triggers
(Automation → Send Open Incident Actions mail).

NOTE: once this row exists the scheduler sends the mail when the alert's Next Mail date has arrived, at its Start Time, to the alert's real recipients.
Check that date (and Report Mails > Send a test) first. On a development database, think before running it.

    python manage.py setup_open_incident_actions
    python manage.py setup_open_incident_actions --alert 141"""

from django.core.management.base import BaseCommand

from core import open_incident_actions


class Command(BaseCommand):
    help = "Connect the Open Incident Actions mail to its alert through the Notification Triggers table."

    def add_arguments(self, parser):
        parser.add_argument("--alert", type=int, default=None, help="the alert's id (default: the alert named 'Open Incident Actions')")

    def handle(self, *args, **opts):
        did = open_incident_actions.ensure_setup(opts["alert"])
        self.stdout.write("Done: " + (", ".join(did) if did else "nothing to change (already set up, or the alert was not found)"))
        for w in open_incident_actions.JOB.get_setup()["warnings"]:
            self.stdout.write(self.style.WARNING("Note: " + w))
