"""Closes approved offer letters nobody has answered or touched for N days (default 30). See hr/offer_letter_autoclose.py.

    python manage.py close_stale_offer_letters --dry-run     # only says how many
    python manage.py close_stale_offer_letters               # closes them
    python manage.py close_stale_offer_letters --days 45
"""

from django.core.management.base import BaseCommand

from hr import offer_letter_autoclose


class Command(BaseCommand):
    help = "Close approved offer letters with no response and no change for a number of days."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=None, help="default: OFFER_LETTER_AUTOCLOSE_DAYS (30)")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        res = offer_letter_autoclose.run(days=opts["days"], dry_run=opts["dry_run"])
        verb = "would close" if opts["dry_run"] else "closed"
        self.stdout.write(f"{verb} {res['closed']} offer letter(s); {res['skipped_joined']} skipped because the applicant has joined")
