"""Runs the scheduler: every automatic mail the system has (see core/scheduler.py).

    python manage.py run_scheduler            # stays running; a run at the start, then one at the top of every hour (the Windows service does this)
    python manage.py run_scheduler --once     # one run, then exit (for Windows Task Scheduler every hour, or to try it by hand)
    python manage.py run_scheduler --status   # shows when it last ran and what is planned

Stop it with Ctrl+C (or by stopping the service). Everything it does is written to backend/logs/scheduler-<date>.log, and every error also to
automation_errors-<date>.log."""

import datetime
import logging
import signal
import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from core import scheduler, scheduler_health
from core.models import SchedHeartbeat, SchedItem, SchedJob

log = logging.getLogger("seros.scheduler")
HEARTBEAT_SECONDS = 60


def seconds_to_next_hour(now=None):
    now = now or datetime.datetime.now()
    nxt = now.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(hours=1)
    return max(1.0, (nxt - now).total_seconds() + 5)  # five seconds past the hour, so a mail due at 07:00 is due when the run starts


class Command(BaseCommand):
    help = "Run the scheduler (hourly) for every automatic mail."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="run once and exit")
        parser.add_argument("--status", action="store_true", help="show the last run and what is planned, then exit")

    def handle(self, *args, **opts):
        if opts["status"]:
            return self._status()
        if opts["once"]:
            res = scheduler.tick()
            self.stdout.write(f"ran={res['ran']} jobs={res['jobs']} errors={res['errors']}")
            return
        stop = {"now": False}

        def _stop(signum, frame):
            stop["now"] = True
            log.info("scheduler stopping (signal %s)", signum)

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, _stop)
            except (ValueError, OSError):
                pass
        log.info("scheduler started: one run now, then one at the top of every hour")
        self._beat(start=True)
        first = True
        while not stop["now"]:
            try:
                close_old_connections()
                scheduler.tick()
            except Exception:
                log.exception("the hourly run crashed; it will try again at the next hour")
            if first:
                first = False
            wait = seconds_to_next_hour()
            log.info("next run in %.0f minutes", wait / 60)
            end = time.monotonic() + wait
            next_beat = time.monotonic() + HEARTBEAT_SECONDS
            while not stop["now"] and time.monotonic() < end:
                time.sleep(min(5, max(0.0, end - time.monotonic())))
                if time.monotonic() >= next_beat:  # "still alive", once a minute, so a crash is seen within minutes
                    self._beat()
                    next_beat = time.monotonic() + HEARTBEAT_SECONDS
        self._beat(stop=True)
        log.info("scheduler stopped")

    @staticmethod
    def _beat(start=False, stop=False):
        try:
            close_old_connections()
            scheduler_health.heartbeat(start=start, stop=stop)
        except Exception:
            log.exception("the heartbeat could not be written")  # never stops the scheduler

    def _status(self):
        from django.utils import timezone  # noqa: F401

        st = scheduler_health.evaluate()
        self.stdout.write(f"Health: {st['level'].upper()}: {st['title']}" + "".join(f"\n  - {p['title']}: {p['detail']}" for p in st["problems"]))
        hb = SchedHeartbeat.objects.filter(pk=1).first()
        self.stdout.write("Last run by the service: " + (f"{hb.last_service_tick_at:%Y-%m-%d %H:%M} ({'ok' if hb.last_tick_ok else 'errors'}: {hb.last_message})" if hb and hb.last_service_tick_at else "never"))
        if hb and hb.last_manual_tick_at:
            self.stdout.write(f"Last run started by hand (Run it now): {hb.last_manual_tick_at:%Y-%m-%d %H:%M}")
        for j in SchedJob.objects.all():
            self.stdout.write(f"  {j.name}: {'on' if j.enabled == 'Y' else 'PAUSED'}; last run {j.last_run_at or 'never'} ({j.last_run_note})")
        today = datetime.date.today()
        for st in ("planned", "sent", "failed", "skipped", "missed", "cancelled"):
            self.stdout.write(f"  {st}: {SchedItem.objects.filter(send_date__gte=today - datetime.timedelta(days=7), status=st).count()}")
