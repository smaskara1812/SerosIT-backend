"""Scheduler health: is the scheduler alive, is mail piling up that should have gone, can the mail server be reached, and the watchdog that tells IT.

Three parts that work together:
  * The scheduler SERVICE (manage.py run_scheduler) writes a heartbeat every minute (`heartbeat`): "I am alive", when it started, on which server, and whether
    it was stopped properly. In SCHEDULER_MODE=task (Windows Task Scheduler runs it once an hour) there is no heartbeat between runs, so the last run is used.
  * `evaluate` reads the heartbeat, the planned mails and the last mail-server check and says: ok, warning or critical, with the problems in words. The
    Scheduled Mails page and the sidebar dot use it. It never sends anything and never connects to the mail server.
  * The WATCHDOG (manage.py check_scheduler_health, a Task Scheduler job every 15 minutes, separate from the service so it can see the service die) checks the
    mail server, records each problem as a row in sched_health_event, and e-mails SCHEDULER_ERROR_MAIL_TO. One problem is one e-mail: a problem that goes on is not
    mailed again (unless SCHEDULER_HEALTH_REMINDER_HOURS is set), and a stopped service or an unreachable mail server gets one "back to normal" mail. Mails
    that failed for good are not a health problem here: each already sends its own error mail (core/error_mail.py). Nothing is e-mailed unless
    SCHEDULER_HEALTH_ALERTS is True, so a development machine never writes to IT; the events are still recorded."""

import datetime
import logging
import os
import smtplib
import socket

from django.conf import settings

from . import error_mail, mailer
from .models import SchedHealthEvent, SchedHeartbeat, SchedItem, SchedJob

log = logging.getLogger("seros.scheduler")

TASK_MODE_LIMIT_MINUTES = 75  # in task mode the scheduler runs once an hour: more than this since its last run means it has stopped
SMTP_FAILS_BEFORE_ALERT = 2  # the mail server must fail this many checks in a row (30 minutes at one check every 15) before it counts
LEVELS = {"ok": 0, "warning": 1, "critical": 2}


def _now():
    return datetime.datetime.now().replace(microsecond=0)


def _minutes(a, b):
    return int((a - b).total_seconds() // 60)


# ── the heartbeat, written by the scheduler service ──────────────────────────────────────────────────────────────────────────────

def heartbeat(now=None, start=False, stop=False):
    """"I am alive". Called once a minute by the service loop; start=True when it starts (records the server and process), stop=True when it is stopped properly."""
    now = now or _now()
    SchedHeartbeat.objects.get_or_create(heartbeat_id=1)
    fields = {"last_alive_at": now}
    if start:
        fields.update(started_at=now, stopped_at=None, service_host=socket.gethostname()[:80], service_pid=os.getpid())
    if stop:
        fields.update(stopped_at=now)
    SchedHeartbeat.objects.filter(pk=1).update(**fields)


def service_state(hb, now):
    """-> (state, minutes since it was last seen). State: running, stale (it stopped without saying so), stopped (stopped properly), never."""
    task = settings.SCHEDULER_MODE == "task"
    last = hb.last_service_tick_at if task else (hb.last_alive_at or hb.last_service_tick_at)
    if not last:
        return "never", None
    age = _minutes(now, last)
    limit = TASK_MODE_LIMIT_MINUTES if task else settings.SCHEDULER_STALE_MINUTES
    if age <= limit:
        return "running", age
    if not task and hb.stopped_at and hb.last_alive_at and hb.stopped_at >= hb.last_alive_at - datetime.timedelta(seconds=5):
        return "stopped", age
    return "stale", age


# ── what is wrong, read from the data ────────────────────────────────────────────────────────────────────────────────────────────

def overdue_items(now):
    """Planned mails that were due more than SCHEDULER_OVERDUE_HOURS ago, for automations that are switched on, oldest first. (A run started by hand is not one.)"""
    cutoff = now - datetime.timedelta(hours=settings.SCHEDULER_OVERDUE_HOURS)
    paused = set(SchedJob.objects.filter(enabled="N").values_list("job_key", flat=True))
    qs = SchedItem.objects.filter(status="planned", due_at__lte=cutoff, send_date__lte=now.date()).exclude(subject_key__contains=":by hand")
    return [i for i in qs.order_by("due_at", "item_id") if i.job_key not in paused]


def counts(now):
    day = now.date() - datetime.timedelta(days=7)
    return {
        "overdue": len(overdue_items(now)),
        "failed": SchedItem.objects.filter(status="failed", send_date__gte=day).exclude(subject_key__contains=":by hand").count(),
        "missed": SchedItem.objects.filter(status="missed", send_date__gte=day).count(),
    }


def evaluate(now=None):
    """The scheduler's health as the page shows it:
    {"level": ok|warning|critical, "title", "state", "age", "heartbeat": {...}, "counts": {...}, "smtp": {...}, "problems": [{"kind","level","title","detail","since"}]}.
    Reads only the database: it does not connect to the mail server (the watchdog does, and records the result)."""
    now = now or _now()
    hb = SchedHeartbeat.objects.filter(pk=1).first() or SchedHeartbeat(heartbeat_id=1)
    state, age = service_state(hb, now)
    problems = []
    down = False
    if state in ("stale", "never"):
        down = True
        problems.append({
            "kind": "service_down", "level": "critical", "title": "The scheduler service is not running",
            "detail": ("It has never run. Nothing goes out by itself until it is started on the server." if state == "never"
                       else f"No sign of life for {age} minutes (last at {(hb.last_alive_at or hb.last_service_tick_at):%d %b %H:%M}). Mails due meanwhile go out when it starts again."),
            "since": hb.last_alive_at or hb.last_service_tick_at,
        })
    elif state == "stopped" and age > settings.SCHEDULER_STOPPED_GRACE_MINUTES:
        down = True
        problems.append({"kind": "service_down", "level": "critical", "title": "The scheduler service was stopped and not started again",
                         "detail": f"It was stopped properly {age} minutes ago (at {hb.stopped_at:%d %b %H:%M}).", "since": hb.stopped_at})
    c = counts(now)
    if not down and c["overdue"]:
        first = overdue_items(now)[0]
        problems.append({"kind": "overdue", "level": "warning", "title": f"{c['overdue']} {'mail is' if c['overdue'] == 1 else 'mails are'} overdue",
                         "detail": f"Due more than {settings.SCHEDULER_OVERDUE_HOURS} hours ago and not sent. The oldest: {first.label}, due {first.due_at:%d %b %H:%M}.", "since": first.due_at})
    if hb.smtp_fail_streak >= SMTP_FAILS_BEFORE_ALERT:
        problems.append({"kind": "smtp_down", "level": "critical", "title": "The mail server cannot be reached",
                         "detail": f"The last {hb.smtp_fail_streak} checks failed: {hb.smtp_error or 'no answer'}.", "since": hb.smtp_checked_at})
    level = max((p["level"] for p in problems), key=LEVELS.get, default="ok")
    title = {"ok": "The scheduler is running normally", "warning": "The scheduler needs attention", "critical": "The scheduler has a problem"}[level]
    if state == "stopped" and not problems:
        title, level = "The scheduler service was stopped on purpose", "warning"
    return {
        "level": level, "title": title, "state": state, "age": age, "mode": settings.SCHEDULER_MODE, "problems": problems, "counts": c,
        "heartbeat": {
            "last_alive_at": hb.last_alive_at, "last_run_at": hb.last_service_tick_at, "last_manual_at": hb.last_manual_tick_at, "last_run_ok": hb.last_tick_ok, "last_run_message": hb.last_message,
            "started_at": hb.started_at, "stopped_at": hb.stopped_at, "host": hb.service_host, "pid": hb.service_pid,
            "uptime_minutes": _minutes(now, hb.started_at) if hb.started_at and state == "running" else None,
        },
        "smtp": {"ok": hb.smtp_ok, "checked_at": hb.smtp_checked_at, "error": hb.smtp_error, "fail_streak": hb.smtp_fail_streak, "host": settings.EMAIL_HOST},
    }


# ── the mail-server check, made by the watchdog (and on demand from the page) ─────────────────────────────────────────────────

def smtp_check(now=None):
    """Connects to the default mail account's server (and says hello; no sign-in, no mail), records the result. Returns {"ok": True|False|None, "error"}.
    None means there was nothing to check (no server set, or the console backend of a development machine)."""
    now = now or _now()
    SchedHeartbeat.objects.get_or_create(heartbeat_id=1)
    cfg = mailer.default_smtp()
    if getattr(settings, "EMAIL_USE_CONSOLE", False) or not cfg["host"]:
        SchedHeartbeat.objects.filter(pk=1).update(smtp_ok=None, smtp_checked_at=now, smtp_error="", smtp_fail_streak=0)
        return {"ok": None, "error": ""}
    error = ""
    try:
        srv = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=10) if cfg["use_ssl"] else smtplib.SMTP(cfg["host"], cfg["port"], timeout=10)
        try:
            srv.ehlo()
            if cfg["use_tls"] and not cfg["use_ssl"]:
                srv.starttls()
                srv.ehlo()
        finally:
            try:
                srv.quit()
            except Exception:
                pass
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"[:300]
    hb = SchedHeartbeat.objects.get(pk=1)
    SchedHeartbeat.objects.filter(pk=1).update(smtp_ok=not error, smtp_checked_at=now, smtp_error=error, smtp_fail_streak=0 if not error else hb.smtp_fail_streak + 1)
    return {"ok": not error, "error": error}


# ── the watchdog: events and e-mails ─────────────────────────────────────────────────────────────────────────────────────────────

ADVICE = {
    "service_down": "Start the SerosIT scheduler service on the server. Mails due meanwhile go out when it starts; mails for days that have passed are marked Missed on Admin > Scheduled Mails.",
    "overdue": "Open Admin > Scheduled Mails: the mails that are overdue are listed under Today. Check the scheduler service and the automation's trigger, alert and recipients.",
    "smtp_down": "Check the mail server and the network between it and this server. Automatic mails cannot be sent until it can be reached; they are retried at the next hourly runs.",
}


def _mail(subject, rows, note):
    """Sends a health mail to SCHEDULER_ERROR_MAIL_TO. It may use the environment's second account as well as the default one, so a mail-server problem on one
    does not hide the alert. Returns True when it went."""
    return error_mail._send(subject, rows, note, designated=True)


def _duration(a, b):
    m = max(0, _minutes(b, a))
    return f"{m // 60} h {m % 60} min" if m >= 60 else f"{m} min"


def sync_events(now, problems, alerts=None):
    """Opens an event for each problem that has started, closes the ones that are over, and e-mails IT as described in the module's text.
    Returns [(what happened, kind)] for the watchdog's printout."""
    alerts = settings.SCHEDULER_HEALTH_ALERTS if alerts is None else alerts
    current = {p["kind"]: p for p in problems}
    done = []
    open_events = {e.kind: e for e in SchedHealthEvent.objects.filter(ended_at__isnull=True)}
    reminder = datetime.timedelta(hours=settings.SCHEDULER_HEALTH_REMINDER_HOURS)
    for kind, p in current.items():
        ev = open_events.get(kind)
        if ev is None:
            ev = SchedHealthEvent.objects.create(kind=kind, level=p["level"], started_at=p["since"] or now, detail=p["detail"][:500])
            done.append(("opened", kind))
        elif ev.detail != p["detail"][:500]:
            SchedHealthEvent.objects.filter(pk=ev.pk).update(detail=p["detail"][:500])
        if alerts and ev.alerted_at is None:
            rows = [("Problem", p["title"]), ("Since", f"{ev.started_at:%d %b %Y %H:%M}"), ("Details", p["detail"])]
            hb = SchedHeartbeat.objects.filter(pk=1).first()
            if hb and hb.service_host:
                rows.append(("Server", hb.service_host))
            if _mail(f"[SerosIT] Scheduler problem: {p['title']}", rows, ADVICE[kind]):
                SchedHealthEvent.objects.filter(pk=ev.pk).update(alerted_at=now)
                done.append(("alert mailed", kind))
        elif alerts and settings.SCHEDULER_HEALTH_REMINDER_HOURS > 0 and ev.alerted_at and now - (ev.reminder_at or ev.alerted_at) >= reminder:
            rows = [("Still a problem", p["title"]), ("Since", f"{ev.started_at:%d %b %Y %H:%M}"), ("For", _duration(ev.started_at, now)), ("Details", p["detail"])]
            if _mail(f"[SerosIT] Scheduler problem continues: {p['title']}", rows, ADVICE[kind]):
                SchedHealthEvent.objects.filter(pk=ev.pk).update(reminder_at=now)
                done.append(("reminder mailed", kind))
    for kind, ev in open_events.items():
        if kind in current or (kind == "overdue" and "service_down" in current):
            continue
        SchedHealthEvent.objects.filter(pk=ev.pk).update(ended_at=now)
        done.append(("closed", kind))
        if alerts and ev.alerted_at and kind in ("service_down", "smtp_down") and ev.recovery_alerted_at is None:
            what = "The scheduler service is running again" if kind == "service_down" else "The mail server can be reached again"
            if _mail(f"[SerosIT] {what}", [("Was", ev.detail or kind), ("Down for", _duration(ev.started_at, now))], "No action is needed."):
                SchedHealthEvent.objects.filter(pk=ev.pk).update(recovery_alerted_at=now)
                done.append(("recovery mailed", kind))
    return done


def watchdog(now=None, check_smtp=True, alerts=None):
    """One run of the watchdog. Returns {"status": evaluate(...), "smtp", "actions", "alerts"}."""
    now = now or _now()
    smtp = smtp_check(now) if check_smtp else None
    status = evaluate(now)
    actions = sync_events(now, status["problems"], alerts)
    return {"status": status, "smtp": smtp, "actions": actions, "alerts": settings.SCHEDULER_HEALTH_ALERTS if alerts is None else alerts}


def recent_events(limit=8):
    return list(SchedHealthEvent.objects.all()[:limit])
