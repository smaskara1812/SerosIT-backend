"""Admin > Scheduled Mails: the overview of every automatic mail the scheduler looks after: what is coming in the next 7 days, what went today, what
went before, and what can be done to each (skip, send now, resend), plus a pause switch per automation. The rights are the page's own (menu key
admin.scheduled_mails): View to see, Edit to act. The work itself is done by core/scheduler.py."""

import datetime

from django.conf import settings
from django.db.models import Q
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import audit as _audit
from . import birthday_mailer, holiday_mailer, scheduler
from .birthday_views import scheduler_health
from .models import BirthdayTemplate, EmailLog, SchedItem, SchedJob
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
        "recipients": i.recipients, "sent_at": i.sent_at, "resend_count": i.resend_count, "skipped_by": i.skipped_by, "note": i.note,
        "template": i.template_id,
        "can": {"skip": s in ("planned", "failed", "missed"), "unskip": s == "skipped", "send_now": s in ("planned", "failed", "missed", "skipped"), "resend": s == "sent"},
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def scheduled_mails_api(request):
    """?section=upcoming|today|earlier  &job=<key>  &status=<status>  &q=<text>  &page=<n>  &page_size=<n>"""
    if not _may(request, "view"):
        return _deny()
    now = datetime.datetime.now()
    today = now.date()
    q = request.query_params
    section = q.get("section", "upcoming")
    qs = SchedItem.objects.all()
    if q.get("job"):
        qs = qs.filter(job_key=q["job"])
    if q.get("status") in STATUS_LABELS:
        qs = qs.filter(status=q["status"])
    if q.get("q"):
        qs = qs.filter(Q(label__icontains=q["q"]) | Q(last_error__icontains=q["q"]))
    sections = {
        "upcoming": qs.filter(send_date__gte=today, send_date__lte=today + datetime.timedelta(days=7)).exclude(status__in=("sent", "cancelled")).order_by("due_at", "item_id"),
        "today": qs.filter(send_date=today).exclude(status="cancelled").order_by("due_at", "item_id"),
        "earlier": qs.filter(send_date__lt=today).order_by("-send_date", "-due_at", "-item_id"),
    }
    chosen = sections.get(section, sections["upcoming"])
    try:
        size = min(200, max(1, int(q.get("page_size", 50))))
        page = max(1, int(q.get("page", 1)))
    except ValueError:
        size, page = 50, 1
    total = chosen.count()
    max_attempts = 1 + settings.SCHEDULER_MAX_RETRIES
    names = {k: j.name for k, j in scheduler.JOBS.items()}
    rows = [_row(i, names, max_attempts) for i in chosen[(page - 1) * size : page * size]]
    base = SchedItem.objects.all()
    next_hour = now.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(hours=1)
    jobs = []
    for key, job in scheduler.JOBS.items():
        row = SchedJob.objects.filter(job_key=key).first()
        jobs.append({"key": key, "name": job.name, "enabled": (row.enabled == "Y") if row else True, "last_run_at": row.last_run_at if row else None,
                     "last_run_note": row.last_run_note if row else "", "next_run": next_hour, "schedule": job.schedule_text(today),
                     "failed": base.filter(job_key=key, status="failed").count(), "sent_today": base.filter(job_key=key, send_date=today, status="sent").count(),
                     # for the pause and resume dialogs: what pausing would leave behind
                     "kind": job.schedule_kind, "planned": base.filter(job_key=key, status="planned", send_date__gte=today).count(),
                     "overdue_planned": base.filter(job_key=key, status="planned", send_date__lt=today).count(), **_cycle(job, today)})
    return Response({
        "health": scheduler_health(now), "jobs": jobs, "section": section, "count": total, "page": page, "page_size": size, "results": rows,
        "counts": {"upcoming": sections["upcoming"].count() if section != "upcoming" else total, "today": sections["today"].count() if section != "today" else total,
                   "earlier": sections["earlier"].count() if section != "earlier" else total},
        "max_attempts": max_attempts, "statuses": [{"key": k, "label": v} for k, v in STATUS_LABELS.items()],
    })


def _cycle(job, today):
    """For a cycle automation (a report mail): its Next Mail and frequency, so the dialogs can say what resuming will do."""
    if job.schedule_kind != "cycle":
        return {}
    st = job.get_setup(today)
    return {"next_mail_dt": st["next_mail_dt"], "freq": st["freq"]}


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
    """Runs the hourly check right now, in this request (plan the next 7 days, send what is due). For when the service is not running yet or someone
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


def recipients_preview(job, as_of, snapshot=""):
    """The preview payload for one job on one day (shared with the Report Mails page)."""
    from .notification_triggers import resolve_alert_recipients_detailed

    setup = job.setup(as_of) or {}
    alert = setup.get("alert")
    entries = resolve_alert_recipients_detailed(alert["id"], as_of) if alert else []
    counts = {k: sum(1 for e in entries if e["type"] == k) for k in ("to", "cc", "bcc")}
    return {
        "job": job.key, "job_name": job.name, "as_of": as_of, "alert": alert, "from_name": setup.get("from_name", ""), "from_address": setup.get("from_address", ""), "links": setup.get("links", {}), "subject": setup.get("subject", ""),
        "sender": (setup.get("smtp") or {}).get("sender"), "recipients": entries, "counts": counts, "snapshot": snapshot or "",
        "error_mail_to": list(settings.SCHEDULER_ERROR_MAIL_TO), "warnings": setup.get("warnings", []),
    }
