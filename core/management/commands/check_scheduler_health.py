"""The scheduler watchdog: run it every 15 minutes from Windows Task Scheduler (a job of its own, NOT part of the scheduler service, so it can notice the
service dying). It checks the scheduler's heartbeat, the mails that should have gone, and whether the mail server can be reached; it records each problem
(Admin > Scheduled Mails shows the last ones) and, when SCHEDULER_HEALTH_ALERTS=True, e-mails SCHEDULER_ERROR_MAIL_TO: one mail when a problem starts, one
when a stopped service or an unreachable mail server is back. Nothing is mailed for a problem that is already known (see core/scheduler_health.py).

    python manage.py check_scheduler_health               # the normal run
    python manage.py check_scheduler_health --no-smtp     # leave out the mail-server check
    python manage.py check_scheduler_health --no-mail     # print and record, never e-mail (even if alerts are on)

The exit code is 0 for ok, 1 for a warning and 2 for critical, so a monitoring tool can use it too."""

import sys

from django.core.management.base import BaseCommand

from core import scheduler_health


class Command(BaseCommand):
    help = "Check the scheduler's health and tell IT about a new problem (exit code 0 ok, 1 warning, 2 critical)."

    def add_arguments(self, parser):
        parser.add_argument("--no-smtp", action="store_true", help="do not check the mail server")
        parser.add_argument("--no-mail", action="store_true", help="never send an e-mail")

    def handle(self, *args, **opts):
        res = scheduler_health.watchdog(check_smtp=not opts["no_smtp"], alerts=False if opts["no_mail"] else None)
        st = res["status"]
        self.stdout.write(f"{st['level'].upper()}: {st['title']}")
        for p in st["problems"]:
            self.stdout.write(f"  - {p['title']}: {p['detail']}")
        smtp = res["smtp"]
        if smtp is not None:
            self.stdout.write("  mail server: " + ("not checked here (no server, or the development console)" if smtp["ok"] is None else "reachable" if smtp["ok"] else f"NOT reachable ({smtp['error']})"))
        self.stdout.write(f"  mails overdue {st['counts']['overdue']}, failed {st['counts']['failed']}, missed {st['counts']['missed']} (last 7 days)")
        for what, kind in res["actions"]:
            self.stdout.write(f"  {what}: {kind}")
        if not res["alerts"]:
            self.stdout.write("  (alert e-mails are off: SCHEDULER_HEALTH_ALERTS is not True, or --no-mail)")
        sys.exit({"ok": 0, "warning": 1, "critical": 2}[st["level"]])
