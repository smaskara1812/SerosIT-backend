"""Clears the sign-in wait of an account (after too many wrong passwords).

    python manage.py unlock_login <login id>
"""

from django.core.management.base import BaseCommand

from core import login_guard


class Command(BaseCommand):
    help = "Clear the sign-in throttle for one account."

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, **opts):
        n = login_guard.unlock(opts["username"])
        self.stdout.write(f"Cleared {n} recorded attempts for {opts['username']!r}.")
