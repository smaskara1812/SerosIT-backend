"""Admin > Report Mails: the page for the report-style automatic mails (the HAZ ID Register today): how each is set up (alert, window, frequency, next
mail date, sender, who it goes to), a download of the report as it would be sent now, a test send to one address, and its latest runs. The rights are the
page's own (menu key admin.report_mails): View to see, Edit to send a test, Export to download the file. The sending itself is done by the scheduler
(core/report_job.py); runs, skips and resends are on Scheduled Mails."""

import datetime
import re

from django.http import HttpResponse
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import audit as _audit
from . import mailer, scheduler
from .models import SchedItem
from .permissions import holds_a_right_on
from .report_job import RunBusy, RunMode, ScheduledReportJob
from .scheduled_mails_views import recipients_preview

MENU_KEY = "admin.report_mails"


def _may(request, *flags):
    return holds_a_right_on(request, [MENU_KEY], flags=flags)


def _deny(what="use Report Mails"):
    return Response({"detail": f"You do not have the right to {what}."}, status=403)


def _reports():
    return {k: j for k, j in scheduler.JOBS.items() if isinstance(j, ScheduledReportJob)}


def _report(key):
    return _reports().get(key)


def _card(job, today):
    s = job.get_setup(today)
    alert = job.alert()
    effect = job.run_now_effect(alert, today)
    items = SchedItem.objects.filter(job_key=job.key).order_by("-send_date", "-item_id")[:6]
    due = None
    if s["alert"] and s["next_mail_dt"] and s["freq"] >= 1:
        due = s["next_mail_dt"]
    return {
        "key": job.key, "name": job.report_name, "description": job.description, "setup": s, "schedule": job.schedule_text(today),
        "overdue": bool(due and due.date() < today), "run_now": effect,
        "runs": [{"id": i.item_id, "label": i.label, "send_date": i.send_date, "status": i.status, "note": i.note, "last_error": i.last_error, "sent_at": i.sent_at} for i in items],
        "preview": recipients_preview(job, today),
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def reports_api(request):
    if not _may(request, "view"):
        return _deny()
    today = datetime.date.today()
    return Response({"results": [_card(j, today) for j in _reports().values()]})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def download_api(request, key):
    """The report as it would be built right now, as the file (not sent to anyone). Needs Export."""
    job = _report(key)
    if job is None:
        return Response({"detail": "Unknown report."}, status=404)
    if not _may(request, "export"):
        return _deny("download this report")
    alert = job.alert()
    if alert is None:
        return Response({"detail": "This report is not connected to an alert yet."}, status=409)
    mail = job.build(alert, datetime.datetime.now())
    _audit.record_action(request, "export", MENU_KEY, key, f"{job.report_name} downloaded", {"summary": {"old": None, "new": mail.summary}})
    if not mail.attachments:
        return Response({"detail": mail.summary or "There is nothing to report right now.", "empty": True}, status=404)
    name, data, mime = mail.attachments[0]
    r = HttpResponse(data, content_type=mime)
    r["Content-Disposition"] = f'attachment; filename="{name}"'
    r["Cache-Control"] = "no-store"
    return r


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def test_send_api(request, key):
    """Sends the report as it would be sent now to ONE address (not to the alert's recipients), marked [Test]. It goes the way the real one goes
    (the alert's own account, else the default account). Needs Edit."""
    job = _report(key)
    if job is None:
        return Response({"detail": "Unknown report."}, status=404)
    if not _may(request, "edit"):
        return _deny("send a test mail")
    to = (request.data.get("email") or "").strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", to):
        return Response({"detail": "Enter an e-mail address to send the test to."}, status=400)
    alert = job.alert()
    if alert is None:
        return Response({"detail": "This report is not connected to an alert yet."}, status=409)
    setup = job.get_setup()
    mail = job.build(alert, datetime.datetime.now())
    res = mailer.send_scheduled_email(
        "[Test] " + mail.subject, mail.html, mail.text, to=[to], from_name=setup["from_name"], trigger=f"{job.report_name} test to {to}", trigger_code=job.trigger_code + ".test",
        designated=True, alert_id=alert.alert_id, attachments=mail.attachments, env_account=False,
    )
    _audit.record_action(request, "update", MENU_KEY, "test", f"{job.report_name} test mail to {to}", {"result": {"old": None, "new": "sent" if res["ok"] else "failed"}})
    return Response(
        {"ok": res["ok"], "smtp_used": res["smtp_used"], "fell_back": res.get("fell_back", False), "error": res["error"], "summary": mail.summary, "email_log_id": res["email_log_id"]},
        status=200 if res["ok"] else 502,
    )


def _who(request):
    from .notice_board import poster_name

    return poster_name(request.user)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def run_now_api(request, key):
    """Sends the report to the alert's recipients straight away (Edit). It is recorded on Scheduled Mails as "by hand". Body: {"mode": "copy" | "count" |
    "restart"} says what happens to Next Mail (see ScheduledReportJob.run_now_effect); without one, an extra copy when Next Mail is ahead and "count" when due."""
    job = _report(key)
    if job is None:
        return Response({"detail": "Unknown report."}, status=404)
    if not _may(request, "edit"):
        return _deny("send this report now")
    alert = job.alert()
    if alert is None:
        return Response({"detail": "This report is not connected to an alert yet."}, status=409)
    now = datetime.datetime.now().replace(microsecond=0)
    mode = request.data.get("mode") or None
    effect = job.run_now_effect(alert, now.date())
    try:
        ok, error, item = job.run_now(alert, _who(request), now, mode)
    except RunMode as exc:
        return Response({"detail": str(exc)}, status=400)
    except RunBusy as exc:
        return Response({"detail": str(exc), "busy": True}, status=409)
    chosen = mode or effect["default_mode"]
    _audit.record_action(request, "update", MENU_KEY, key, f"{job.report_name} sent by hand", {"result": {"old": None, "new": "sent" if ok else "failed"}, "next_mail": {"old": None, "new": chosen}})
    fresh = type(alert).objects.get(pk=alert.pk)
    body = {"ok": ok, "error": error, "summary": item.note, "recipients": item.recipients, "next_mail_dt": fresh.next_mail_dt, "moved": chosen != "copy" and ok, "mode": chosen, "item_id": item.pk}
    return Response(body, status=200 if ok else 502)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def schedule_api(request, key):
    """Sets the alert's Next Mail date and Start Time (hour) for this report (Edit). Body: {"date": "YYYY-MM-DD", "hour": 0-23}."""
    job = _report(key)
    if job is None:
        return Response({"detail": "Unknown report."}, status=404)
    if not _may(request, "edit"):
        return _deny("change when this report goes out")
    alert = job.alert()
    if alert is None:
        return Response({"detail": "This report is not connected to an alert yet."}, status=409)
    try:
        day = datetime.date.fromisoformat(str(request.data.get("date", ""))[:10])
    except ValueError:
        return Response({"detail": "Choose a date."}, status=400)
    try:
        hour = int(request.data.get("hour"))
    except (TypeError, ValueError):
        return Response({"detail": "The hour must be from 0 to 23."}, status=400)
    try:
        old, new = job.set_schedule(alert, day, hour, datetime.datetime.now().replace(microsecond=0))
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=400)
    _audit.record_action(request, "update", MENU_KEY, key, f"{job.report_name}: Next Mail changed", {"next_mail_dt": {"old": str(old) if old else None, "new": str(new)}, "start_time": {"old": alert.start_time, "new": hour}})
    return Response({"ok": True, "next_mail_dt": new, "start_time": hour})
