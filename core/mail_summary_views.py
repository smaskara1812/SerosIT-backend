"""Admin > Mail Controls (App Admin only, like Mail Redirect; no rights can be given for it). Two cards live on this one page:

  * the Daily Mail Summary: on or off, when it goes, who gets it, and how it is laid out;
  * "if a mail fails for good, tell": the people the error mail goes to (core/error_mail.py), chosen here instead of in the .env.

GET gives both as they are now. PUT {section: "summary", ...} or {section: "error", to: [..] | null, confirm: "CONFIRM ERROR MAIL UPDATE"}. Changing the error mail's
people needs the typed phrase (like the mail redirect) because it decides who hears about a failure. `to: null` puts the .env value back. POST test/ sends the
summary of the day so far to the chosen people, marked as a test. A saved row wins over the .env (core/mail_settings.py)."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from . import audit as _audit
from . import mail_settings, mailer, sched_clock
from .models import MailSummarySetting
from .notice_board import poster_name
from .permissions import IsAppAdmin

ERROR_MAIL_PHRASE = "CONFIRM ERROR MAIL UPDATE"
ENTITY = "mail_summary"


def _addresses(raw):
    """A list or a text of addresses -> a clean list; raises ValueError naming the first one that is not an address."""
    if isinstance(raw, str):
        raw = raw.replace("\n", ",").replace(";", ",").split(",")
    out = list(dict.fromkeys(a.strip() for a in (raw or []) if a and str(a).strip()))
    for a in out:
        try:
            validate_email(a)
        except ValidationError:
            raise ValueError(f"'{a}' is not a valid e-mail address.") from None
    return out


def payload():
    from . import mail_summary

    st = mail_settings.summary_state()
    err, err_src = mail_settings.error_state()
    r_on, r_to, _r_src = mailer.redirect_state()
    return {
        "summary": {
            **{k: st[k] for k in ("on", "time", "to", "same_as_error", "send_when_quiet", "grouped", "source", "changed_by", "changed_at")},
            "recipients": mail_settings.summary_recipients(st),
            "env": {"on": bool(settings.MAIL_SUMMARY), "to": list(settings.MAIL_SUMMARY_TO), "time": settings.MAIL_SUMMARY_TIME},
        },
        "error": {"to": err, "source": err_src, "env_to": list(settings.SCHEDULER_ERROR_MAIL_TO), "phrase": ERROR_MAIL_PHRASE},
        "redirect": {"on": r_on, "to": r_to},
        "status": mail_summary.status(),
        "run_every": sched_clock.interval_minutes(),
    }


def _row():
    row, _ = MailSummarySetting.objects.get_or_create(pk=1)
    return row


@api_view(["GET", "PUT"])
@permission_classes([IsAppAdmin])
def admin_mail_summary_api(request):
    if request.method == "GET":
        return Response(payload())
    d = request.data or {}
    section = d.get("section")
    if section == "summary":
        return _save_summary(request, d)
    if section == "error":
        return _save_error(request, d)
    return Response({"detail": "Say which part is being saved: summary or error."}, status=400)


def _save_summary(request, d):
    t = mail_settings.normal_time(str(d.get("time", "")))
    if not t:
        return Response({"detail": "The time must be hours and minutes, like 22:00."}, status=400)
    try:
        to = _addresses(d.get("to"))
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=400)
    new = {"on": bool(d.get("on")), "time": t, "to": to, "same_as_error": bool(d.get("same_as_error")), "send_when_quiet": bool(d.get("send_when_quiet", True)), "grouped": bool(d.get("grouped", True))}
    people = mail_settings.error_recipients() if new["same_as_error"] else to
    if new["on"] and not people:
        why = "Nobody is set to receive the error mails yet, so add someone in the other card first, or give the summary its own addresses." if new["same_as_error"] else "Add at least one address before switching the summary on."
        return Response({"detail": why}, status=400)
    old = mail_settings.summary_state()
    row = _row()
    row.summary_saved = True
    row.summary_on = new["on"]
    row.send_time = t
    row.summary_to = ", ".join(to)
    row.same_as_error = new["same_as_error"]
    row.send_when_quiet = new["send_when_quiet"]
    row.grouped = new["grouped"]
    row.changed_by = poster_name(request.user)[:100]
    row.changed_at = timezone.now()
    row.save()
    mail_settings.clear_cache()
    changes = {k: {"old": old[k] if not isinstance(old[k], list) else ", ".join(old[k]), "new": new[k] if not isinstance(new[k], list) else ", ".join(new[k])} for k in new if old[k] != new[k]}
    _audit.record_action(request, "update", ENTITY, 1, "Mail summary", changes or {"saved": {"old": None, "new": "no change"}})
    return Response(payload())


def _save_error(request, d):
    if (d.get("confirm") or "").strip() != ERROR_MAIL_PHRASE:
        return Response({"detail": f"Type {ERROR_MAIL_PHRASE} exactly to confirm."}, status=400)
    raw = d.get("to")
    use_env = raw is None
    try:
        to = [] if use_env else _addresses(raw)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=400)
    now = mail_settings.summary_state()
    new_people = list(settings.SCHEDULER_ERROR_MAIL_TO) if use_env else to
    if now["on"] and now["same_as_error"] and not new_people:
        return Response({"detail": "The daily summary is switched on and goes to these same people, so at least one address is needed. Give the summary its own addresses first, or switch it off."}, status=400)
    old_to, _src = mail_settings.error_state()
    row = _row()
    row.error_to = None if use_env else ", ".join(to)
    row.changed_by = poster_name(request.user)[:100]
    row.changed_at = timezone.now()
    row.save()
    mail_settings.clear_cache()
    new_to, new_src = mail_settings.error_state()
    _audit.record_action(request, "update", ENTITY, 1, "Mail summary: error mail recipients", {"error_to": {"old": ", ".join(old_to), "new": ", ".join(new_to) + (" (.env)" if new_src == "env" else "")}})
    return Response(payload())


@api_view(["POST"])
@permission_classes([IsAppAdmin])
def admin_mail_summary_test_api(request):
    """Sends the summary of the day so far to the chosen people, marked as a test. Uses what is saved on the page (or the .env)."""
    from . import mail_summary

    res = mail_summary.send_test(poster_name(request.user))
    if not res["ok"]:
        return Response({"detail": res["error"]}, status=502 if res.get("sent_attempted") else 400)
    _audit.record_action(request, "update", ENTITY, 1, "Mail summary: test sent", {"test": {"old": None, "new": ", ".join(res["to"])}})
    return Response({"ok": True, "to": res["to"], "status": mail_summary.status()})
