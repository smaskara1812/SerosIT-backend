"""Admin > Scheduled Mails: the overview of every automatic mail the scheduler looks after: what is coming in the next 7 days, what went today, what
went before, and what can be done to each (skip, send now, resend), plus a pause switch per automation. The rights are the page's own (menu key
admin.scheduled_mails): View to see, Edit to act. The work itself is done by core/scheduler.py."""

import datetime

from django.conf import settings
from django.db.models import Count, Q
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import audit as _audit
from . import birthday_mailer, holiday_mailer, mail_settings, sched_clock, scheduler
from . import scheduler_health as scheduler_health_module
from .birthday_views import scheduler_health
from .models import BirthdayTemplate, EmailLog, NotificationTrigger, SchedItem, SchedJob
from .notice_board import poster_name
from .permissions import holds_a_right_on

MENU_KEY = "admin.scheduled_mails"
STATUS_LABELS = {"planned": "Planned", "sending": "Sending", "sent": "Sent", "failed": "Failed", "skipped": "Skipped", "missed": "Missed", "cancelled": "Cancelled"}


def _may(request, *flags):
    return holds_a_right_on(request, [MENU_KEY], flags=flags)


def _deny(what="use Scheduled Mails"):
    return Response({"detail": f"You do not have the right to {what}."}, status=403)


def _who(request):
    return poster_name(request.user)


def _row(i, names, max_attempts):
    s = i.status
    return {
        "id": i.item_id, "job": i.job_key, "job_name": names.get(i.job_key, i.job_key), "label": i.label, "send_date": i.send_date, "due_at": i.due_at,
        "status": s, "status_label": STATUS_LABELS.get(s, s), "attempts": i.attempts, "max_attempts": max_attempts,
        "retry_pending": s == "failed" and i.attempts < max_attempts, "last_error": i.last_error, "smtp_used": i.smtp_used, "email_log_id": i.email_log_id,
        "multi_mail": bool(getattr(scheduler.JOBS.get(i.job_key), "uses_rig_recipients", False)),
        "recipients": i.recipients, "sent_at": i.sent_at, "resend_count": i.resend_count, "skipped_by": i.skipped_by, "note": i.note,
        "template": i.template_id,
        "can": {"skip": s in ("planned", "failed", "missed"), "unskip": s == "skipped", "send_now": s in ("planned", "failed", "missed", "skipped"), "resend": s == "sent"},
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def scheduled_mails_api(request):
    """?section=upcoming|today|earlier  &job=<key>  &status=<status>  &q=<text>  &page=<n>  &page_size=<n>  &part=list|panel
    The page needs two things that change at different speeds: the LIST of mails (changes with every tab, filter and page) and the PANEL above it (the scheduler's health
    and the automations: changes slowly). part=list answers only the list, part=panel only the panel, no part both (as before). Switching tabs asks for the list alone."""
    if not _may(request, "view"):
        return _deny()
    now = datetime.datetime.now()
    today = now.date()
    q = request.query_params
    part = q.get("part", "")
    out = {}
    if part in ("", "list"):
        out.update(_list_part(q, today))
    if part in ("", "panel"):
        out.update(_panel_part(now, today))
    return Response(out)


def _list_part(q, today):
    section = q.get("section", "upcoming")
    qs = SchedItem.objects.all()
    if q.get("job"):
        qs = qs.filter(job_key=q["job"])
    if q.get("status") in STATUS_LABELS:
        qs = qs.filter(status=q["status"])
    if q.get("q"):
        qs = qs.filter(Q(label__icontains=q["q"]) | Q(last_error__icontains=q["q"]))
    in_upcoming = Q(send_date__gte=today, send_date__lte=today + datetime.timedelta(days=7)) & ~Q(status__in=("sent", "cancelled"))
    in_today = Q(send_date=today) & ~Q(status="cancelled")
    in_earlier = Q(send_date__lt=today)
    where = {"upcoming": in_upcoming, "today": in_today, "earlier": in_earlier}
    order = {"upcoming": ("due_at", "item_id"), "today": ("due_at", "item_id"), "earlier": ("-send_date", "-due_at", "-item_id")}
    if section not in where:
        section = "upcoming"
    try:
        size = min(200, max(1, int(q.get("page_size", 50))))
        page = max(1, int(q.get("page", 1)))
    except ValueError:
        size, page = 50, 1
    # three plain counts, not one CASE over the whole table. On SQL Server the CASE form scans every column of every row (the table is clustered on the
    # primary key, and the rows carry the error text and the recipient snapshot). A count that only names send_date and status can use the index.
    counts = {"upcoming": qs.filter(in_upcoming).count(), "today": qs.filter(in_today).count(), "earlier": qs.filter(in_earlier).count()}
    max_attempts = 1 + settings.SCHEDULER_MAX_RETRIES
    names = {k: j.name for k, j in scheduler.JOBS.items()}
    rows = [_row(i, names, max_attempts) for i in qs.filter(where[section]).order_by(*order[section])[(page - 1) * size : page * size]]
    return {
        "section": section, "count": counts[section], "page": page, "page_size": size, "results": rows, "counts": counts,
        "max_attempts": max_attempts, "statuses": [{"key": k, "label": v} for k, v in STATUS_LABELS.items()],
    }


def _light_setup(alert):
    """The few fields an automation tile needs, taken from the alert already loaded with its trigger. The tile does not show recipients or the sender,
    so it must not read those (that was one query per automation, and it ran again on every tab)."""
    if alert is None:
        return {"alert": None, "next_mail_dt": None, "freq": 0, "send_hour": 7}
    return {
        "alert": {"id": alert.alert_id, "name": alert.alert_name}, "next_mail_dt": alert.next_mail_dt, "freq": alert.alert_freq or 0,
        "send_hour": alert.start_time if alert.start_time is not None else 7,
    }


def _panel_part(now, today):
    """The scheduler's health, its recent problems and the automations (switches, schedules, counts). The per-automation counts are one grouped query.
    A report's Next Mail and a mailer's hour come from the trigger's alert, which is read once for every automation; the recipients and the sender are not read here."""
    base = SchedItem.objects.all()
    rows = {r.job_key: r for r in SchedJob.objects.all()}
    stats = {
        r["job_key"]: r for r in base.values("job_key").annotate(
            failed=Count("pk", filter=Q(status="failed")),
            sent_today=Count("pk", filter=Q(send_date=today, status="sent")),
            planned=Count("pk", filter=Q(status="planned", send_date__gte=today)),
            overdue=Count("pk", filter=Q(status="planned", send_date__lt=today)),
        )
    }
    trigs = {(t.entity_key, t.action): t for t in NotificationTrigger.objects.filter(entity_key__in={j.trigger_entity for j in scheduler.JOBS.values() if getattr(j, "trigger_entity", None)}).select_related("alert")}
    next_run = sched_clock.next_run_after(now)
    jobs = []
    for key, job in scheduler.JOBS.items():
        row = rows.get(key)
        st = stats.get(key, {})
        trig = trigs.get((getattr(job, "trigger_entity", None), getattr(job, "trigger_action", None))) if getattr(job, "trigger_entity", None) else None
        light = _light_setup(trig.alert if trig is not None else None)
        jobs.append({"key": key, "name": job.name, "enabled": (row.enabled == "Y") if row else True, "last_run_at": row.last_run_at if row else None,
                     "last_run_note": row.last_run_note if row else "", "next_run": next_run, "schedule": job.schedule_text(today, light),
                     "failed": st.get("failed", 0), "sent_today": st.get("sent_today", 0),
                     # for the pause and resume dialogs: what pausing would leave behind
                     "kind": job.schedule_kind, "planned": st.get("planned", 0), "overdue_planned": st.get("overdue", 0),
                     **({"next_mail_dt": light["next_mail_dt"], "freq": light["freq"]} if job.schedule_kind == "cycle" else {})})
    return {
        "health": scheduler_health(now), "health_events": [
            {"id": e.event_id, "kind": e.kind, "level": e.level, "started_at": e.started_at, "ended_at": e.ended_at, "detail": e.detail, "alerted": e.alerted_at is not None}
            for e in scheduler_health_module.recent_events(6)
        ], "jobs": jobs, "run_every_minutes": sched_clock.interval_minutes(),
    }


def _act(request, item_id, name):
    if not _may(request, "edit"):
        return _deny("change scheduled mails")
    who = _who(request)
    it = SchedItem.objects.filter(pk=item_id).first()
    label = it.label if it else str(item_id)
    try:
        if name == "skip":
            scheduler.skip_item(item_id, who)
            msg = "Skipped."
        elif name == "unskip":
            scheduler.unskip_item(item_id, who)
            msg = "Put back: it will go out at its time."
        elif name == "send-now":
            ok, err = scheduler.send_now(item_id, who)
            if not ok:
                _audit.record_action(request, "update", MENU_KEY, item_id, f"Scheduled mail: {label}", {"send_now": {"old": None, "new": "failed"}})
                return Response({"detail": f"It could not be sent: {err}", "item": _fresh(item_id)}, status=502)
            msg = "Sent."
        else:
            ok, err = scheduler.resend(item_id, who)
            if not ok:
                _audit.record_action(request, "update", MENU_KEY, item_id, f"Scheduled mail: {label}", {"resend": {"old": None, "new": "failed"}})
                return Response({"detail": f"It could not be sent again: {err}", "item": _fresh(item_id)}, status=502)
            msg = "Sent again."
    except scheduler.ActionError as exc:
        return Response({"detail": str(exc)}, status=409)
    _audit.record_action(request, "update", MENU_KEY, item_id, f"Scheduled mail: {label}", {name.replace("-", "_"): {"old": None, "new": "done"}})
    return Response({"detail": msg, "item": _fresh(item_id)})


def _fresh(item_id):
    it = SchedItem.objects.filter(pk=item_id).first()
    return _row(it, {k: j.name for k, j in scheduler.JOBS.items()}, 1 + settings.SCHEDULER_MAX_RETRIES) if it else None


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def skip_api(request, item_id):
    return _act(request, item_id, "skip")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def unskip_api(request, item_id):
    return _act(request, item_id, "unskip")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def send_now_api(request, item_id):
    return _act(request, item_id, "send-now")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def resend_api(request, item_id):
    return _act(request, item_id, "resend")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def job_switch_api(request, job_key, state):
    """Pause or resume one automation. Paused: nothing is planned or sent for it (items already planned stay as they are)."""
    if not _may(request, "edit"):
        return _deny("pause or resume automations")
    if job_key not in scheduler.JOBS or state not in ("pause", "resume"):
        return Response({"detail": "Unknown automation."}, status=404)
    row, _ = SchedJob.objects.get_or_create(job_key=job_key, defaults={"name": scheduler.JOBS[job_key].name})
    SchedJob.objects.filter(pk=row.pk).update(enabled="N" if state == "pause" else "Y")
    _audit.record_action(request, "update", MENU_KEY, row.pk, f"Automation: {row.name}", {"enabled": {"old": row.enabled, "new": "N" if state == "pause" else "Y"}})
    return Response({"detail": "Paused." if state == "pause" else "Resumed.", "enabled": state == "resume"})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def run_now_api(request):
    """Runs the scheduler's check right now, in this request (plan the next 7 days, send what is due). For when the service is not running yet or someone
    wants it done without waiting for the hour."""
    if not _may(request, "edit"):
        return _deny("run the scheduler")
    res = scheduler.tick(source="manual")
    _audit.record_action(request, "update", MENU_KEY, "run", "Scheduler run by hand", {"result": {"old": None, "new": "ran" if res["ran"] else "skipped"}})
    return Response(res, status=200 if res["ran"] else 409)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def item_email_api(request, item_id):
    """The email an item sent (subject, who it went to, what the picture looked like, any error), read from the Email Log. This is here so that people
    who may see Scheduled Mails can see the mail without needing the App-Admin-only Email Log page."""
    if not _may(request, "view"):
        return _deny()
    it = SchedItem.objects.filter(pk=item_id).first()
    log = EmailLog.objects.filter(pk=it.email_log_id).first() if it and it.email_log_id else None
    if not log:
        return Response({"detail": "No email was recorded for this item yet."}, status=404)
    return Response({"id": log.email_log_id, "subject": log.subject, "body": log.body, "recipients": log.recipients, "success": log.success, "error": log.error,
                     "used_fallback": log.used_fallback, "sent_at": log.sent_dt, "trigger": log.trigger})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def item_mails_api(request, item_id):
    """Every mail one run sends. A run of Drilling Info Status / Not Entered is ONE item on the page but sends one mail per company / per rig. Answers
    {"sent": [the mails already logged for that day], "preview": [the mails a run would send now, with who each goes to]}; the preview is given only
    for an item that has not been sent."""
    if not _may(request, "view"):
        return _deny()
    it = SchedItem.objects.filter(pk=item_id).first()
    job = scheduler.JOBS.get(it.job_key) if it else None
    if not it or not job:
        return Response({"detail": "That mail no longer exists."}, status=404)
    sent = []
    code = getattr(job, "trigger_code", "")
    if code:
        for g in EmailLog.objects.filter(trigger_code=code, sent_dt__date=it.send_date).order_by("sent_dt", "email_log_id")[:200]:
            sent.append({"id": g.email_log_id, "label": g.trigger, "subject": g.subject, "body": g.body, "recipients": g.recipients, "success": g.success, "error": g.error, "sent_at": g.sent_dt})
    preview, note = [], ""
    if it.status != "sent" and hasattr(job, "preview_mails"):
        try:
            alert = job.alert()
            now = datetime.datetime.combine(it.send_date, datetime.datetime.now().time()) if it.send_date >= datetime.date.today() else datetime.datetime.now()
            if alert:
                for m in job.preview_mails(alert, now):
                    preview.append({"subject": m.subject, "body": m.html, "summary": m.summary, "to": m.to, "cc": m.cc, "bcc": m.bcc})
        except Exception as exc:  # the preview is a help; never fail the page over it
            note = f"The preview could not be built: {exc}"
    return Response({"item": it.item_id, "label": it.label, "status": it.status, "sent": sent, "preview": preview, "note": note})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def item_recipients_api(request, item_id):
    """Who one item goes (or went) to: every To, Cc and Bcc recipient with where it comes from, resolved the way sending resolves it, for the day the
    item is for. `snapshot` is what was recorded when it was actually sent. Also the sender and the error-mail address. Needs View on this page."""
    if not _may(request, "view"):
        return _deny()
    it = SchedItem.objects.filter(pk=item_id).first()
    job = scheduler.JOBS.get(it.job_key) if it else None
    if not it or not job:
        return Response({"detail": "That mail no longer exists."}, status=404)
    return Response(recipients_preview(job, it.send_date, it.recipients))


def recipients_preview(job, as_of, snapshot="", setup=None, alert_obj=None, base=None):
    """The preview payload for one job on one day (shared with the Report Mails page). A caller that already has the job's setup (and its alert, and the detailed
    recipient list) passes them in, so they are not read again."""
    from .notification_triggers import resolve_alert_recipients_detailed

    setup = (setup if setup is not None else job.setup(as_of)) or {}
    alert = setup.get("alert")
    # a job that also reads Rig Alert Recipients (one mail per rig or per company) lists those people too, each labelled with where it comes from
    if alert and hasattr(job, "recipients_detailed"):
        kw = {}
        if alert_obj is not None:
            kw["alert"] = alert_obj
        if base is not None:
            kw["base"] = base
        entries = job.recipients_detailed(as_of, **kw)
    elif base is not None:
        entries = list(base)
    else:
        entries = resolve_alert_recipients_detailed(alert["id"], as_of) if alert else []
    links = dict(setup.get("links", {}))
    if alert and getattr(job, "uses_rig_recipients", False):
        from urllib.parse import quote

        links["rig_recipients"] = f"/masters/rig-alert-recipients?alert={alert['id']}&alertName={quote(alert.get('name') or '', safe='')}"
    counts = {k: sum(1 for e in entries if e["type"] == k) for k in ("to", "cc", "bcc")}
    return {
        "job": job.key, "job_name": job.name, "as_of": as_of, "alert": alert, "from_name": setup.get("from_name", ""), "from_address": setup.get("from_address", ""), "links": links, "subject": setup.get("subject", ""),
        "sender": (setup.get("smtp") or {}).get("sender"), "recipients": entries, "counts": counts, "snapshot": snapshot or "",
        "error_mail_to": mail_settings.error_recipients(), "warnings": setup.get("warnings", []),
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def scheduler_status_api(request):
    """The light status the sidebar dot polls once a minute: {"level": ok|warning|critical, "title", "problems": [titles]}. Needs View on this page."""
    if not _may(request, "view"):
        return _deny()
    ev = scheduler_health_module.evaluate()
    return Response({"level": ev["level"], "title": ev["title"], "problems": [p["title"] for p in ev["problems"]]})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def smtp_check_api(request):
    """Checks now whether the default mail server can be reached (a connection and a hello; nothing is sent) and records the result. Needs Edit. At most one
    check every 20 seconds, so a clicking person cannot hammer the mail server."""
    if not _may(request, "edit"):
        return _deny("check the mail server")
    hb = scheduler_health_module.SchedHeartbeat.objects.filter(pk=1).first()
    now = datetime.datetime.now().replace(microsecond=0)
    if hb and hb.smtp_checked_at and (now - hb.smtp_checked_at).total_seconds() < 20:
        return Response({"detail": "The mail server was checked a moment ago. Wait a few seconds."}, status=429)
    res = scheduler_health_module.smtp_check(now)
    _audit.record_action(request, "update", MENU_KEY, "smtp-check", "Mail server checked", {"result": {"old": None, "new": "reachable" if res["ok"] else "not reachable" if res["ok"] is False else "not checked"}})
    return Response(res)
