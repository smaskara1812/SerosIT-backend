"""Connects the Holiday Mailer to its alert through the Notification Triggers table (safe to run again), and creates the scheduler's job row.
The alert ("Holiday Events") is made in Mail Alerts first; this finds it by name, or by --alert <id>. The same can be done by hand in
Masters > Notification Triggers (Automation → Holiday Mailer).

    python manage.py setup_holiday_mailer
    python manage.py setup_holiday_mailer --alert 312"""

from django.core.management.base import BaseCommand

from core import holiday_mailer


class Command(BaseCommand):
    help = "Connect the Holiday Mailer to its alert through the Notification Triggers table."

    def add_arguments(self, parser):
        parser.add_argument("--alert", type=int, default=None, help="the alert's id (default: the alert named 'Holiday Events')")

    def handle(self, *args, **opts):
        did = holiday_mailer.ensure_setup(opts["alert"])
        self.stdout.write("Done: " + (", ".join(did) if did else "nothing to change (already set up, or no alert named 'Holiday Events' was found)"))
        for w in holiday_mailer.get_setup()["warnings"]:
            self.stdout.write(self.style.WARNING("Note: " + w))
