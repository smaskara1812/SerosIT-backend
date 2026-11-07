"""When the scheduler runs. One setting decides it: SCHEDULER_INTERVAL_MINUTES in the .env (default 30). The scheduler wakes at the top of every hour and then every
that-many minutes after it, so with 30 it runs at :00 and :30, with 15 at :00 :15 :30 :45. The number has to divide an hour (5, 10, 15, 20, 30 or 60), or the runs would drift
off the clock; any other value is read as 30. A mail due at a set time goes out on the first run at or after it, so a shorter interval only makes it later by less.
A failed mail is still tried again at most once an hour (core/sched_base.py), whatever the interval."""

import datetime
import logging

from django.conf import settings

log = logging.getLogger("seros.scheduler")
ALLOWED = (5, 10, 15, 20, 30, 60)
DEFAULT = 30
_warned = set()


def interval_minutes():
    try:
        n = int(settings.SCHEDULER_INTERVAL_MINUTES)
    except (TypeError, ValueError, AttributeError):
        n = DEFAULT
    if n not in ALLOWED:
        if n not in _warned:
            _warned.add(n)
            log.warning("SCHEDULER_INTERVAL_MINUTES=%s is not one of %s, so %s is used", n, ALLOWED, DEFAULT)
        return DEFAULT
    return n


def interval_text(n=None):
    """'every 30 minutes', 'every hour'."""
    n = n or interval_minutes()
    return "every hour" if n == 60 else f"every {n} minutes"


def next_run_after(now, n=None):
    """The next scheduled run after `now` (a datetime): the next slot of the day's hour, counted from the top of the hour."""
    n = n or interval_minutes()
    start = now.replace(minute=0, second=0, microsecond=0)
    slots = int(((now - start).total_seconds() // 60) // n) + 1
    return start + datetime.timedelta(minutes=n * slots)


def seconds_to_next_run(now=None, n=None):
    """How long the service sleeps: to five seconds past the next slot, so a mail due at 07:00 is due when the run starts."""
    now = now or datetime.datetime.now()
    return max(1.0, (next_run_after(now, n) - now).total_seconds() + 5)
