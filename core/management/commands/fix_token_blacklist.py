"""Removes duplicate rows from the JWT token blacklist.

    python manage.py fix_token_blacklist            # shows what it would delete
    python manage.py fix_token_blacklist --apply    # deletes the extra rows

A token may be blacklisted only once (the table has a unique constraint on the
token). If a database ends up with the same token blacklisted twice, refreshing
that token fails with "get() returned more than one BlacklistedToken" (HTTP 500).
This keeps the oldest row for each token and deletes the rest. Only blacklist rows
are touched, so nobody is signed out beyond what was already blacklisted.

It also reports whether the unique constraint on the token is present in this
database; if it is missing, duplicates can come back.
"""

from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.db.models import Count, Min
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken


class Command(BaseCommand):
    help = "Delete duplicate rows from the JWT token blacklist (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Delete the extra rows")

    def handle(self, *args, **opts):
        table = BlacklistedToken._meta.db_table
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, table)
        has_unique = any(c.get("unique") and c.get("columns") == ["token_id"] for c in constraints.values())
        self.stdout.write(f"Unique constraint on {table}.token_id: {'present' if has_unique else 'MISSING'}")

        dups = list(BlacklistedToken.objects.values("token_id").annotate(n=Count("id"), keep=Min("id")).filter(n__gt=1))
        extra = sum(d["n"] - 1 for d in dups)
        self.stdout.write(f"{len(dups)} token(s) blacklisted more than once; {extra} extra row(s).")
        if not dups:
            return
        if not opts["apply"]:
            self.stdout.write("Dry run: nothing deleted. Run again with --apply to delete the extra rows.")
            return
        with transaction.atomic():
            deleted = 0
            for d in dups:
                deleted += BlacklistedToken.objects.filter(token_id=d["token_id"]).exclude(id=d["keep"]).delete()[0]
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} duplicate row(s)."))
        if not has_unique:
            self.stdout.write(self.style.WARNING("The unique constraint is missing in this database, so duplicates can come back; tell the developer."))
