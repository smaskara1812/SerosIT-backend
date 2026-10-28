"""The scheduler: one hourly run that looks after every automatic mail the system has.

`tick()` is what runs at the top of each hour (core/management/commands/run_scheduler.py, as a Windows service in production). For each job
that is switched on it plans the next 7 days, sends what is due, retries what failed (once per hourly run, at most SCHEDULER_MAX_RETRIES more
times), and records the result. A job is any object with `key`, `name`, `plan(now)`, `process(now)`, `attempt(item, now)` and `resend(item, now)`;
the birthday mailer is the first (core/birthday_mailer.py), the holiday mailer the second (core/holiday_mailer.py). A job that raises is logged and does not stop the others.

Two copies can never run at once: a tick takes a lock in the heartbeat row (and gives it up when done, or when it expires, in case a copy died).
Everything is logged to the scheduler log, and every error also to automation_errors (see settings.LOGGING)."""

import datetime
import logging
import os
import socket
import time

from django.db.models import Q

from . import birthday_mailer, error_mail, haz_id_register, holiday_mailer, rig_rate_breakup
from .models import SchedHeartbeat, SchedItem, SchedJob

log = logging.getLogger("seros.scheduler")

JOBS = {birthday_mailer.JOB.key: birthday_mailer.JOB, holiday_mailer.JOB.key: holiday_mailer.JOB, haz_id_register.JOB.key: haz_id_register.JOB, rig_rate_breakup.JOB.key: rig_rate_breakup.JOB}
LOCK_MINUTES = 50  # a lock older than this is taken as left behind by a copy that died


def owner_name():
    return f"{socket.gethostname()}:{os.getpid()}"


def acquire_lock(owner, now):
    SchedHeartbeat.objects.get_or_create(heartbeat_id=1)
    n = SchedHeartbeat.objects.filter(pk=1).filter(Q(locked_until__isnull=True) | Q(locked_until__lt=now) | Q(locked_by=owner)).update(
        locked_by=owner, locked_until=now + datetime.timedelta(minutes=LOCK_MINUTES)
    )
    return n == 1


def release_lock(owner):
    SchedHeartbeat.objects.filter(pk=1, locked_by=owner).update(locked_by="", locked_until=None)


def tick(now=None, owner=None, source="service"):
    """One run of the scheduler. `source` is "service" for the scheduler service (run_scheduler) and "manual" for "Run it now" on the page: only a service run
    shows the service as alive. Returns {"ran": bool, "jobs": {key: summary}, "errors": [..]}."""
    now = now or datetime.datetime.now().replace(microsecond=0)
    owner = owner or owner_name()
    if not acquire_lock(owner, now):
        log.warning("tick skipped: another scheduler copy holds the lock")
        return {"ran": False, "jobs": {}, "errors": ["another scheduler copy is running"]}
    started = time.monotonic()
    summary, errors = {}, []
    try:
        birthday_mailer.ensure_setup(fix_subject=False)
        for key, job in JOBS.items():
            row, _ = SchedJob.objects.get_or_create(job_key=key, defaults={"name": job.name})
            if row.enabled != "Y":
                summary[key] = {"paused": True}
                log.info("%s: paused, nothing planned or sent", job.name)
                continue
            try:
                planned = job.plan(now)
                done = job.process(now)
                summary[key] = {**planned, **done}
                note = ", ".join(f"{k} {v}" for k, v in summary[key].items() if v)[:300] or "nothing to do"
                SchedJob.objects.filter(pk=row.pk).update(last_run_at=now, last_run_note=note)
                log.info("%s: %s", job.name, note)
            except Exception as exc:
                log.exception("job %s failed during the hourly run", key)
                errors.append(f"{key}: {type(exc).__name__}: {exc}")
                error_mail.notify_job_failed(key, job.name, f"{type(exc).__name__}: {exc}", now)
                SchedJob.objects.filter(pk=row.pk).update(last_run_at=now, last_run_note=f"Error: {exc}"[:300])
        msg = ("Errors: " + "; ".join(errors)) if errors else "OK"
        SchedHeartbeat.objects.filter(pk=1).update(last_tick_at=now, last_tick_ok=not errors, last_message=msg[:300], **({"last_manual_tick_at": now} if source == "manual" else {"last_service_tick_at": now, "last_alive_at": now}))
        log.info("hourly run finished in %.1fs (%s)", time.monotonic() - started, msg)
    finally:
        release_lock(owner)
    return {"ran": True, "jobs": summary, "errors": errors}


# ── what the Scheduled Mails page can do to one item ───────────────────────────────────────────────────────────────────────

class ActionError(Exception):
    """A refused action, worded for the person."""


def _item(item_id):
    it = SchedItem.objects.filter(pk=item_id).first()
    if it is None:
        raise ActionError("That mail no longer exists.")
    if it.job_key not in JOBS:
        raise ActionError("That kind of mail is no longer handled by the scheduler.")
    return it


def skip_item(item_id, who, now=None):
    now = now or datetime.datetime.now().replace(microsecond=0)
    it = _item(item_id)
    n = SchedItem.objects.filter(pk=it.pk, status__in=("planned", "failed", "missed")).update(status="skipped", skipped_by=who[:60], skipped_at=now, mod_dt=now, note="Skipped")
    if not n:
        raise ActionError(f"A mail that is {it.status} cannot be skipped.")
    JOBS[it.job_key].on_skip(it, now)
    log.info("item %s (%s) skipped by %s", it.pk, it.label, who)


def unskip_item(item_id, who, now=None):
    now = now or datetime.datetime.now().replace(microsecond=0)
    it = _item(item_id)
    status = "planned" if it.send_date >= now.date() else "missed"
    n = SchedItem.objects.filter(pk=it.pk, status="skipped").update(status=status, skipped_by="", skipped_at=None, mod_dt=now, note="Skip undone")
    if not n:
        raise ActionError("Only a skipped mail can be un-skipped.")
    log.info("item %s (%s) un-skipped by %s", it.pk, it.label, who)


def send_now(item_id, who, now=None):
    """Sends a planned, failed, missed or skipped item at once (not waiting for the hour). Returns (ok, error)."""
    now = now or datetime.datetime.now().replace(microsecond=0)
    it = _item(item_id)
    n = SchedItem.objects.filter(pk=it.pk, status__in=("planned", "failed", "missed", "skipped")).update(status="sending", last_attempt_at=now)
    if not n:
        raise ActionError(f"A mail that is {it.status} cannot be sent now.")
    it.refresh_from_db()
    log.info("item %s (%s): send now, asked by %s", it.pk, it.label, who)
    ok = JOBS[it.job_key].attempt(it, now)
    it.refresh_from_db()
    return ok, ("" if ok else it.last_error)


def resend(item_id, who, now=None):
    now = now or datetime.datetime.now().replace(microsecond=0)
    it = _item(item_id)
    if it.status != "sent":
        raise ActionError("Only a mail that was sent can be sent again.")
    log.info("item %s (%s): resend, asked by %s", it.pk, it.label, who)
    return JOBS[it.job_key].resend(it, now)
