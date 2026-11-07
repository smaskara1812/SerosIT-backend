"""The Daily Mail Summary: once a day, one mail that lists every mail the system sent, so IT can see at a glance what went out and what failed (and notice a day on
which nothing went out at all).

  * What decides what: Admin > Mail Controls (core/mail_summary_views.py, stored in `mail_summary_setting`; the .env MAIL_SUMMARY / MAIL_SUMMARY_TO / MAIL_SUMMARY_TIME are the
    backup, see core/mail_settings.py). It is OFF until switched on. It is its own automation, not an alert: who gets it is the list on that page, or the same people as
    the error mail.
  * When it goes: at the chosen time, on the first scheduler run at or after it (the scheduler runs every SCHEDULER_INTERVAL_MINUTES, 30 by default). One item is planned per day (today and tomorrow), so it shows on Admin > Scheduled Mails and
    can be paused, skipped, sent now or sent again like any other automatic mail.
  * What it covers: everything since the LAST summary that went out, up to the moment it is built (the first one: the last 24 hours; never more than 3 days). So a late run, a
    changed time or a pause neither loses nor repeats mails. It reads the Email Log; the summary mails themselves are left out.
  * What it says: a one-line headline, a red note when mail redirect is on, then a table: mail type, subject, sent from, sent at, status. Failures come first. "Grouped" (the default) gives
    one row per mail type with counts; otherwise one row per mail (at most 200; the rest are counted).
  * A day with no mail still sends a short "no mail was sent" message unless the page says not to (a missing summary then means the scheduler was not running).
  * It goes through the default account. A failure is retried and, after the last try, the error mail goes out (core/error_mail.py).
  * Switching it on (or moving its time) when today's time is already more than one scheduler run (plus 5 minutes) behind does not send straight away: today's is skipped and
    the first one goes tomorrow. Switched on just before the time, with the scheduler not yet having run, it still goes at that run."""

import datetime
import html as _html
import logging
import sys

from . import mail_settings, mailer, sched_clock
from .models import EmailLog, SchedItem, SchedJob
from .sched_base import JobBase

log = logging.getLogger("seros.scheduler")

JOB_KEY = "mail_summary"
TRIGGER_CODE = "auto.mail_summary"
NAME = "Daily Mail Summary"
MAX_ROWS = 200  # in the one-row-per-mail layout
SUBJECTS_SHOWN = 3  # in the grouped layout, a type that sent mails with many different subjects shows this many, then "and N more"
LONGEST_LOOK_BACK = datetime.timedelta(days=3)
FIRST_LOOK_BACK = datetime.timedelta(hours=24)

# Friendly names for the mail types that are not automations (those take the name of their automation).
KNOWN = {
    "auto.error": "Error mail",
    "drilling_report.finalize": "Drilling report: finalised",
    "drilling_report.approve": "Drilling report: approved",
    "drilling_report.reject": "Drilling report: rejected",
    "drilling_report.revise_previous": "Drilling report: previous report revised",
    "qhse.incident_details.create": "QHSE incident report: created",
}


def _automation_names():
    """trigger code -> the automation's name, read from the jobs the scheduler runs."""
    from . import scheduler

    out = {}
    for job in scheduler.JOBS.values():
        code = getattr(sys.modules.get(type(job).__module__), "TRIGGER_CODE", None)
        if code:
            out[code] = job.name
    return out


def mail_type(code, subject, names=None):
    """A person-friendly name for a mail's type, from its Email Log trigger code (the code is a dotted label; '.test' marks a test send)."""
    names = names if names is not None else _automation_names()
    code = (code or "").strip()
    if not code:
        return (subject or "Other mail")[:50]
    test = code.endswith(".test")
    base = code[: -len(".test")] if test else code
    name = KNOWN.get(base) or names.get(base)
    if not name:
        parts = base.replace("_", " ").split(".")
        name = parts[0].capitalize() + (": " + " ".join(parts[1:]) if len(parts) > 1 else "")
    return name + (" (test)" if test else "")


def _fmt_time(dt, with_date):
    return f"{dt:%d %b %H:%M}" if with_date else f"{dt:%H:%M}"


def _status(row):
    if row.success:
        return ("Sent via the fallback account" if row.used_fallback else "Sent"), True
    first = (row.error or "").strip().splitlines()[0][:110] if (row.error or "").strip() else "no reason given"
    return f"Failed: {first}", False


def window_for(item, now):
    """(start, end) of what a summary covers. A new one runs from the last summary that went out to now; a sent one (a resend) covers what it covered."""
    prev_q = SchedItem.objects.filter(job_key=JOB_KEY, status="sent", sent_at__isnull=False)
    if item is not None and item.status == "sent" and item.sent_at:
        end = item.sent_at
        prev = prev_q.filter(sent_at__lt=end).order_by("-sent_at").first()
        return (prev.sent_at if prev else end - FIRST_LOOK_BACK), end
    prev = prev_q.order_by("-sent_at").first()
    start = prev.sent_at if prev else now - FIRST_LOOK_BACK
    return max(start, now - LONGEST_LOOK_BACK), now


def build(start, end, grouped, test=False):
    """-> {"subject", "html", "text", "total", "failed"} for the mails sent after `start` up to and including `end`."""
    rows = list(EmailLog.objects.filter(sent_dt__gt=start, sent_dt__lte=end).exclude(trigger_code__in=(TRIGGER_CODE, TRIGGER_CODE + ".test")).order_by("sent_dt"))
    names = _automation_names()
    with_date = start.date() != end.date()
    total = len(rows)
    failed = sum(1 for r in rows if not r.success)
    r_on, r_to, _src = mailer.redirect_state()

    # one line per mail, or one per type
    lines = []
    if grouped:
        groups = {}
        for r in rows:
            groups.setdefault(mail_type(r.trigger_code, r.subject, names), []).append(r)
        for name, rs in groups.items():
            bad = [x for x in rs if not x.success]
            froms = sorted({x.from_address for x in rs if x.from_address})
            a, b = _fmt_time(rs[0].sent_dt, with_date), _fmt_time(rs[-1].sent_dt, with_date)
            span = a if a == b else f"{a} to {b}"
            status = f"{len(rs) - len(bad)} sent" + (f", {len(bad)} failed" if bad else "")
            detail = _status(bad[0])[0] if bad else ""
            subs = list(dict.fromkeys((x.subject or "").strip() for x in rs))
            lines.append({"type": name, "subjects": subs, "from": ", ".join(froms) or "-", "at": span, "status": status, "detail": detail, "ok": not bad, "n": len(rs), "key": (0 if bad else 1, rs[0].sent_dt)})
    else:
        for r in rows[:MAX_ROWS]:
            st, ok = _status(r)
            lines.append({"type": mail_type(r.trigger_code, r.subject, names), "subjects": [(r.subject or "").strip()], "from": r.from_address or "-", "at": _fmt_time(r.sent_dt, with_date), "status": st, "detail": "", "ok": ok, "n": 1, "key": (1 if ok else 0, r.sent_dt)})
    lines.sort(key=lambda x: x["key"])  # failures first, then in time order

    day = end.strftime("%d %b %Y")
    if total:
        headline = f"{total} mail{'s' if total != 1 else ''} sent between {_fmt_time(start, True)} and {_fmt_time(end, True)}: {total - failed} sent" + (f", {failed} failed." if failed else ", none failed.")
    else:
        headline = f"No mail was sent between {_fmt_time(start, True)} and {_fmt_time(end, True)}."
    subject = f"[SerosIT] Daily mail summary, {day}: " + (f"{total} mail{'s' if total != 1 else ''}" + (f", {failed} failed" if failed else "") if total else "no mail sent")
    if test:
        subject = "[Test] " + subject

    esc = _html.escape
    th = "padding:6px 12px;text-align:left;background:#1e2656;color:#fff;font-size:12px;"
    td = "padding:6px 12px;border-bottom:1px solid #e3e6ee;font-size:13px;vertical-align:top;"
    body = []

    def subject_cell(subs):
        shown = "".join(f"<div>{esc(x[:110] + ('…' if len(x) > 110 else ''))}</div>" for x in subs[:SUBJECTS_SHOWN])
        more = f"<div style='color:#777;font-size:12px'>and {len(subs) - SUBJECTS_SHOWN} more subject{'s' if len(subs) - SUBJECTS_SHOWN != 1 else ''}</div>" if len(subs) > SUBJECTS_SHOWN else ""
        return shown + more

    for ln in lines:
        bg = "" if ln["ok"] else "background:#fdecea;"
        colour = "#1b7a3a" if ln["ok"] else "#b3261e"
        extra = f"<div style='color:#b3261e;font-size:12px'>{esc(ln['detail'])}</div>" if ln["detail"] else ""
        body.append(f"<tr style='{bg}'><td style='{td}'>{esc(ln['type'])}</td><td style='{td}'>{subject_cell(ln['subjects'])}</td><td style='{td}'>{esc(ln['from'])}</td><td style='{td}'>{esc(ln['at'])}</td><td style='{td}color:{colour};font-weight:bold'>{esc(ln['status'])}{extra}</td></tr>")
    table = (
        f"<table style='border-collapse:collapse;width:100%;max-width:900px'><tr><th style='{th}'>Mail type</th><th style='{th}'>Subject</th><th style='{th}'>Sent from</th><th style='{th}'>Sent at</th><th style='{th}'>Status</th></tr>{''.join(body)}</table>"
        if lines else ""
    )
    notes = []
    if r_on:
        notes.append(f"<p style='margin:8px 0;padding:8px 12px;border:1px solid #e8900c;background:#fff8e6;color:#7c420d;font-size:12px'><b>Mail redirect is ON</b> on this server, so mails went to {esc(', '.join(r_to) or 'nobody')} and not to the people they were meant for.</p>")
    if not grouped and total > MAX_ROWS:
        notes.append(f"<p style='margin:8px 0;color:#555;font-size:12px'>Showing the first {MAX_ROWS} of {total} mails. See Admin > Email Log for all of them.</p>")
    if test:
        notes.append("<p style='margin:8px 0;color:#555;font-size:12px'>This is a test, built from today so far. The real summary goes out at its set time.</p>")
    page = (
        "<div style='font-family:Arial,sans-serif;color:#222'>"
        f"<p style='margin:0 0 10px;font-size:15px'><b>Seros-IT: daily mail summary</b></p>"
        f"<p style='margin:0 0 12px;font-size:14px;color:{'#b3261e' if failed else '#222'}'>{esc(headline)}</p>"
        f"{''.join(notes)}{table}"
        "<p style='margin-top:14px;color:#777;font-size:11px'>Built from the Email Log. This mail itself is not counted.</p></div>"
    )
    text_lines = [headline, ""] + [f"{ln['type']} | {'; '.join(ln['subjects'][:SUBJECTS_SHOWN])}{' (+' + str(len(ln['subjects']) - SUBJECTS_SHOWN) + ' more)' if len(ln['subjects']) > SUBJECTS_SHOWN else ''} | {ln['from']} | {ln['at']} | {ln['status']}" + (f" ({ln['detail']})" if ln["detail"] else "") for ln in lines]
    if r_on:
        text_lines += ["", f"Mail redirect is ON: mails went to {', '.join(r_to) or 'nobody'}."]
    return {"subject": subject, "html": page, "text": "\n".join(text_lines), "total": total, "failed": failed}


def _send(start, end, test=False):
    """Builds and sends one summary. Returns (error, result, built); error is '' when it went."""
    st = mail_settings.summary_state()
    to = mail_settings.summary_recipients(st)
    if not to:
        return "Nobody is set to receive the summary. Add addresses on Admin > Mail Controls.", None, None
    built = build(start, end, st["grouped"], test=test)
    res = mailer.send_scheduled_email(built["subject"], built["html"], built["text"], to=to, trigger=built["subject"][:200], trigger_code=TRIGGER_CODE + (".test" if test else ""), designated=False)
    res["recipients"] = ", ".join(to)
    return ("" if res["ok"] else (res["error"] or "The mail could not be sent.")), res, built


class MailSummaryJob(JobBase):
    key = JOB_KEY
    name = NAME
    schedule_kind = "dates"

    def schedule_text(self, today, setup=None):
        st = mail_settings.summary_state()
        if not st["on"]:
            return "Switched off (Admin > Mail Controls)"
        return f"Every day at {st['time']} (checked {sched_clock.interval_text()})"

    def plan(self, now, days=1):
        """One item for today and one for tomorrow while the summary is on; planned ones are cancelled when it is switched off. Returns {"planned", "cancelled"}."""
        st = mail_settings.summary_state()
        today = now.date()
        planned = cancelled = 0
        wanted = set()
        late = datetime.timedelta(minutes=sched_clock.interval_minutes() + 5)  # the scheduler may not have run since the time came, so a little late is still on time
        if st["on"]:
            hh, mm = (int(x) for x in st["time"].split(":"))
            for n in range(days + 1):
                day = today + datetime.timedelta(days=n)
                wanted.add(day.isoformat())
                due = datetime.datetime.combine(day, datetime.time(hour=hh, minute=mm))
                item, created = SchedItem.objects.get_or_create(
                    job_key=JOB_KEY, subject_key=day.isoformat(), send_date=day,
                    defaults={"label": f"Mail summary, {day:%d %b}", "due_at": due, "status": "planned", "cr_dt": now},
                )
                if created:
                    if due < now - late:  # switched on (or the time changed) long after the time had passed: the first one goes tomorrow
                        SchedItem.objects.filter(pk=item.pk).update(status="cancelled", note="Switched on after today's time had passed; the first summary goes tomorrow.", mod_dt=now)
                    else:
                        planned += 1
                elif item.status in ("planned", "failed") and item.due_at != due:
                    SchedItem.objects.filter(pk=item.pk).update(due_at=due, mod_dt=now)
        for item in SchedItem.objects.filter(job_key=JOB_KEY, status="planned", send_date__gte=today):
            if item.subject_key not in wanted:
                SchedItem.objects.filter(pk=item.pk).update(status="cancelled", note="The daily summary was switched off or its time changed.", mod_dt=now)
                cancelled += 1
        return {"planned": planned, "cancelled": cancelled}

    def attempt(self, item, now, designated=True):
        """One try at sending one item. Updates the item and returns True when it went (or was rightly not needed)."""
        item.attempts += 1
        start, end = window_for(item, now)
        st = mail_settings.summary_state()
        fields = {"attempts": item.attempts, "last_attempt_at": now, "mod_dt": now}
        quiet = not EmailLog.objects.filter(sent_dt__gt=start, sent_dt__lte=end).exclude(trigger_code__in=(TRIGGER_CODE, TRIGGER_CODE + ".test")).exists()
        if quiet and not st["send_when_quiet"]:
            SchedItem.objects.filter(pk=item.pk).update(**fields, status="cancelled", note="No mail was sent in that period, and the page says not to send a summary then.")
            return True
        try:
            error, res, _built = _send(start, end)
        except Exception as exc:
            log.exception("the daily mail summary (item %s) failed while it was being built", item.pk)
            error, res = f"{type(exc).__name__}: {exc}", None
        if res:
            fields.update(smtp_used=res["smtp_used"], email_log_id=res["email_log_id"], recipients=res["recipients"][:2000])
        if error:
            SchedItem.objects.filter(pk=item.pk).update(**fields, status="failed", last_error=error[:4000])
            log.error("daily mail summary (item %s, attempt %s) failed: %s", item.pk, item.attempts, error)
            return False
        SchedItem.objects.filter(pk=item.pk).update(**fields, status="sent", sent_at=now, last_error="")
        log.info("daily mail summary sent (item %s, %s account)", item.pk, res["smtp_used"])
        return True

    def resend(self, item, now):
        """Sends a summary again, for the period it covered (a new mail, a new Email Log row). Returns (ok, error)."""
        start, end = window_for(item, now)
        try:
            error, res, _built = _send(start, end)
        except Exception as exc:
            log.exception("resend of the daily mail summary (item %s) failed while it was being built", item.pk)
            error, res = f"{type(exc).__name__}: {exc}", None
        fields = {"mod_dt": now}
        if res:
            fields.update(email_log_id=res["email_log_id"], smtp_used=res["smtp_used"], recipients=res["recipients"][:2000])
        if error:
            SchedItem.objects.filter(pk=item.pk).update(**fields, last_error=f"Resend failed: {error}"[:4000])
            return False, error
        SchedItem.objects.filter(pk=item.pk).update(**fields, resend_count=item.resend_count + 1, last_error="")
        return True, ""


JOB = MailSummaryJob()


def send_test(who, now=None):
    """The summary of today so far, sent to the chosen people with [Test] in front. Not an item: it does not change what the real one covers.
    Returns {"ok", "error", "to", "sent_attempted"}."""
    now = now or datetime.datetime.now().replace(microsecond=0)
    st = mail_settings.summary_state()
    to = mail_settings.summary_recipients(st)
    if not to:
        return {"ok": False, "error": "Nobody is set to receive the summary. Add addresses first.", "to": [], "sent_attempted": False}
    start = datetime.datetime.combine(now.date(), datetime.time())
    error, res, _built = _send(start, now, test=True)
    if error:
        log.error("the test mail summary, asked by %s, failed: %s", who, error)
        return {"ok": False, "error": error, "to": to, "sent_attempted": True}
    log.info("a test mail summary was sent to %s, asked by %s", ", ".join(to), who)
    return {"ok": True, "error": "", "to": to, "sent_attempted": True}


def status():
    """What the Mail Controls page shows about the schedule: the last item that went out (or failed), the next planned, and whether the automation is paused."""
    row = SchedJob.objects.filter(job_key=JOB_KEY).first()
    last = SchedItem.objects.filter(job_key=JOB_KEY, status__in=("sent", "failed")).order_by("-last_attempt_at", "-item_id").first()
    nxt = SchedItem.objects.filter(job_key=JOB_KEY, status="planned").order_by("due_at").first()
    return {
        "paused": bool(row and row.enabled != "Y"),
        "last": ({"status": last.status, "at": last.sent_at or last.last_attempt_at, "to": last.recipients, "error": last.last_error} if last else None),
        "next_at": nxt.due_at if nxt else None,
    }
