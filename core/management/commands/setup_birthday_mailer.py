"""Sets up the Birthday Mailer's connections (safe to run again): the Notification Triggers row that points it at alert 247, the scheduler's job row,
and the {name} in the alert's subject (so the mail reads "Happy Birthday <name>").

    python manage.py setup_birthday_mailer
    python manage.py setup_birthday_mailer --alert 247 --keep-subject"""

from django.core.management.base import BaseCommand

from core import birthday_mailer


class Command(BaseCommand):
    help = "Connect the Birthday Mailer to its alert through the Notification Triggers table."

    def add_arguments(self, parser):
        parser.add_argument("--alert", type=int, default=birthday_mailer.DEFAULT_ALERT_ID)
        parser.add_argument("--keep-subject", action="store_true", help="do not touch the alert's subject")

    def handle(self, *args, **opts):
        did = birthday_mailer.ensure_setup(opts["alert"], fix_subject=not opts["keep_subject"])
        self.stdout.write("Done: " + (", ".join(did) if did else "nothing to change (already set up)"))
        setup = birthday_mailer.get_setup()
        for w in setup["warnings"]:
            self.stdout.write(self.style.WARNING("Note: " + w))
