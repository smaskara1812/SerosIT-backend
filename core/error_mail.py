"""The error mail: when an automatic mail has finally failed (all its tries used), or a whole hourly run of a job failed, the people in
SCHEDULER_ERROR_MAIL_TO (.env) are told, by e-mail through the default account. It is sent once per failed item, and at most once a day per job for
a failed run, so a broken job does not fill a mailbox. Nothing is sent when SCHEDULER_ERROR_MAIL_TO is empty. A failure to send the error mail is
only logged: it must never stop the scheduler."""

import datetime
import html
import logging

from django.conf import settings

from . import mailer
from .models import SchedItem, SchedJob

log = logging.getLogger("seros.scheduler")
TRIGGER_CODE = "auto.error"


def recipients():
    return list(settings.SCHEDULER_ERROR_MAIL_TO)


def _send(subject, rows, note):
    to = recipients()
    if not to:
        log.warning("error mail not sent: SCHEDULER_ERROR_MAIL_TO is empty (%s)", subject)
        return False
    body = "".join(f"<tr><td style='padding:4px 12px 4px 0;color:#555'><b>{html.escape(k)}</b></td><td style='padding:4px 0'>{html.escape(str(v))}</td></tr>" for k, v in rows)
    page = (
        "<div style='font-family:Arial,sans-serif;font-size:14px'>"
        "<p style='color:#c0392b;margin:0 0 8px'><b>Seros-IT Auto Report: an automatic mail failed</b></p>"
        f"<table style='border-collapse:collapse'>{body}</table>"
        f"<p style='color:#555;margin-top:12px'>{html.escape(note)}</p></div>"
    )
    text = "\n".join(f"{k}: {v}" for k, v in rows) + "\n" + note
    try:
        res = mailer.send_scheduled_email(subject, page, text, to=to, trigger=subject[:200], trigger_code=TRIGGER_CODE, designated=False)
    except Exception:
        log.exception("the error mail itself could not be sent (%s)", subject)
        return False
    if not res["ok"]:
        log.error("the error mail itself could not be sent (%s): %s", subject, res["error"])
    return res["ok"]


def notify_item_failed(job_name, item, now):
    """The error mail for an item that has used all its tries. Marks the item once the mail has gone (or when there is nobody to send it to), so it is
    sent once; if it could not go (the default account is down too), the next hourly run tries again, for a day."""
    if item.error_mailed_at:
        return False
    if not recipients():
        log.warning("error mail for %s (item %s) not sent: SCHEDULER_ERROR_MAIL_TO is empty", job_name, item.pk)
        SchedItem.objects.filter(pk=item.pk).update(error_mailed_at=now)
        return False
    sent = _send(
        f"[SerosIT] {job_name} failed: {item.label}",
        [("Automation", job_name), ("Mail", item.label), ("Date", item.send_date), ("Tries", item.attempts), ("Reason", item.last_error or "unknown")],
        "It will not be tried again by itself. Open Admin > Scheduled Mails to see it, fix the cause, and use Send now.",
    )
    if sent:
        SchedItem.objects.filter(pk=item.pk).update(error_mailed_at=now)
    return sent


def notify_job_failed(job_key, job_name, error, now):
    """The error mail for a job whose whole hourly run raised. At most once a day per job."""
    row = SchedJob.objects.filter(job_key=job_key).first()
    if row and row.last_error_mail_at and now - row.last_error_mail_at < datetime.timedelta(hours=24):
        return False
    sent = _send(
        f"[SerosIT] {job_name} could not run",
        [("Automation", job_name), ("Time", f"{now:%d %b %Y %H:%M}"), ("Reason", error)],
        "The hourly run of this automation raised an error. Nothing was sent for it in this run. See the scheduler logs (automation_errors) for the details.",
    )
    SchedJob.objects.filter(job_key=job_key).update(last_error_mail_at=now)
    return sent
