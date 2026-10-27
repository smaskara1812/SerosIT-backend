"""The Holiday Mailer: festival and holiday pictures that go to everyone on the "Holiday Events" alert on the date set for each.

What decides what, so nothing here is hardcoded:
  * Which alert the mail belongs to, and whether it is on: ONE row of the Notification Triggers table, (entity_key "automation.holiday", action
    "send"), pointing at an alert (named "Holiday Events"). Switching that row off stops every holiday mail.
  * Who receives it: the alert's active rows in Alert To Users (To, Cc, Bcc), exactly as for every other alert. One alert for all festivals.
  * When it goes: the dates set on each event here, at the alert's start hour, by the hourly scheduler (core/scheduler.py).
  * The From name: the alert's display name. The subject: the event's own subject (the alert's subject only when the event has none).
  * The sending account: BIRTHDAY_EMAIL_* in the environment (the same account as the birthday mail), then the default account (core/mailer.py).
The picture is finished by the person who uploads it: nothing is drawn on it.
"""

import calendar
import datetime
import io
import logging
import os

from django.conf import settings
from django.utils import timezone

from . import mailer
from .birthday_mailer import MAIL_WIDTH, TemplateError, make_thumb, process_template_upload
from .models import HolidayEvent, MailAlertDtl, NotificationTrigger, SchedItem, SchedJob
from .notification_triggers import resolve_alert_recipients
from .sched_base import JobBase

log = logging.getLogger("seros.scheduler")

JOB_KEY = "holiday"
ENTITY_KEY = "automation.holiday"
ACTION = "send"
TRIGGER_CODE = "auto.holiday"
ALERT_NAME = "Holiday Events"  # only what the setup command looks for when it is not told an alert id
FOLDER = "holiday_images"
MAX_DAYS = 14  # the most days in a row one event can go out
MAX_JPEG_FREE = 600 * 1024  # a picture without see-through parts that is heavier than this is sent as a JPEG


# ── the dates ────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def _on(year, month, day):
    if month == 2 and day == 29 and not calendar.isleap(year):
        day = 28  # a 29 February event that repeats yearly is kept on 28 February in a year that has none
    return datetime.date(year, month, day)


def send_dates(ev, lo, hi):
    """Every day in [lo, hi] on which this event goes out: `send_days` days in a row from its date, and, when it repeats yearly, from the same
    day of every year."""
    days = max(1, min(MAX_DAYS, ev.send_days or 1))
    if ev.repeat_yearly == "Y":
        starts = [_on(y, ev.send_on.month, ev.send_on.day) for y in range(lo.year - 1, hi.year + 1)]
    else:
        starts = [ev.send_on]
    out = []
    for st in starts:
        for i in range(days):
            d = st + datetime.timedelta(days=i)
            if lo <= d <= hi:
                out.append(d)
    return sorted(set(out))


def next_send(ev, today):
    """The first day on or after `today` this event goes out, or None when it has none left (a one-off that is over)."""
    if ev.repeat_yearly == "Y":
        found = send_dates(ev, today, today + datetime.timedelta(days=370))
        return found[0] if found else None
    last = ev.send_on + datetime.timedelta(days=max(1, min(MAX_DAYS, ev.send_days or 1)) - 1)
    return max(today, ev.send_on) if last >= today else None


def day_text(ev, day):
    """'Day 2 of 3' for an event that goes out on several days, else ''."""
    n = max(1, min(MAX_DAYS, ev.send_days or 1))
    if n == 1:
        return ""
    starts = [ev.send_on] if ev.repeat_yearly != "Y" else [_on(y, ev.send_on.month, ev.send_on.day) for y in (day.year - 1, day.year)]
    for st in starts:
        k = (day - st).days
        if 0 <= k < n:
            return f"Day {k + 1} of {n}"
    return ""


# ── the picture ──────────────────────────────────────────────────────────────────────────────────────────────────────────────

def picture_path(ev):
    return os.path.join(settings.MEDIA_ROOT, ev.file_path)


def mail_picture(ev):
    """The picture as sent: -> (bytes, 'png' or 'jpeg', width). Shrunk to MAIL_WIDTH; a picture with no see-through parts that is still heavy as a PNG is
    sent as a JPEG instead, so a mail to everyone stays light."""
    from PIL import Image

    img = Image.open(picture_path(ev))
    img.load()
    has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
    if img.size[0] > MAIL_WIDTH:
        k = MAIL_WIDTH / img.size[0]
        img = img.resize((MAIL_WIDTH, max(1, round(img.size[1] * k))), Image.LANCZOS)
    out = io.BytesIO()
    img.convert("RGBA" if has_alpha else "RGB").save(out, "PNG", optimize=True)
    if not has_alpha and out.tell() > MAX_JPEG_FREE:
        out = io.BytesIO()
        img.convert("RGB").save(out, "JPEG", quality=90, optimize=True, progressive=True)
        return out.getvalue(), "jpeg", img.size[0]
    return out.getvalue(), "png", img.size[0]


# ── the setup the page shows, and the mail ───────────────────────────────────────────────────────────────────────────────────

def ensure_setup(alert_id=None, alert_name=ALERT_NAME):
    """Makes sure the scheduler's job row exists and, when the alert can be found (by id, else by name), the trigger row that connects the Holiday
    Mailer to it. Safe to run again. Returns what it did, as a list of words."""
    did = []
    SchedJob.objects.get_or_create(job_key=JOB_KEY, defaults={"name": "Holiday Mailer", "enabled": "Y"})
    if NotificationTrigger.objects.filter(entity_key=ENTITY_KEY, action=ACTION).exists():
        return did
    alert = MailAlertDtl.objects.filter(pk=alert_id).first() if alert_id else MailAlertDtl.objects.filter(alert_name__iexact=alert_name).order_by("alert_id").first()
    if alert is None:
        return did
    NotificationTrigger.objects.create(entity_key=ENTITY_KEY, action=ACTION, alert=alert, notification_trigger_active="Y", cr_user_id=0, cr_dt=timezone.now())
    did.append(f"trigger row created for alert {alert.alert_id} ({alert.alert_name})")
    return did


def get_setup(today=None):
    """Everything the Holiday Mailer page shows about how the mail is set up, read from the trigger, the alert and the environment."""
    today = today or datetime.date.today()
    trig = NotificationTrigger.objects.filter(entity_key=ENTITY_KEY, action=ACTION).select_related("alert").first()
    out = {
        "trigger_found": bool(trig), "trigger_active": bool(trig and trig.notification_trigger_active == "Y"), "alert": None,
        "from_name": "", "subject": "", "send_hour": 7, "recipients": {"to": [], "cc": [], "bcc": []}, "warnings": [],
        "smtp": {"designated": bool(mailer.designated_smtp()), "designated_host": settings.BIRTHDAY_EMAIL_HOST or "", "default_host": settings.EMAIL_HOST, "sender": None},
    }
    if not trig:
        out["warnings"].append("No trigger row connects the Holiday Mailer to an alert. Create the alert “Holiday Events” in Mail Alerts, then add the trigger in Masters > Notification Triggers (Automation → Holiday Mailer).")
        return out
    a = trig.alert
    out["alert"] = {"id": a.alert_id, "name": a.alert_name, "active": a.alert_active == "Y"}
    out["subject"] = a.mail_subject or ""
    out["send_hour"] = a.start_time if a.start_time is not None else 7
    out["recipients"] = resolve_alert_recipients(a.alert_id, as_of=today)
    out["smtp"]["sender"] = mailer.sender_info(a.alert_id)
    out["from_name"] = (out["smtp"]["sender"] or {}).get("display_name", "")  # the sender name is kept with the alert's sender account; none = the From address only
    if out["smtp"]["sender"] and out["smtp"]["sender"]["broken"]:
        out["warnings"].append("The sender set for this alert cannot be used: " + out["smtp"]["sender"]["broken"] + ". The next account is used instead.")
    if not out["trigger_active"]:
        out["warnings"].append("The trigger is switched off, so no holiday mail will be sent.")
    if a.alert_active != "Y":
        out["warnings"].append(f"The alert '{a.alert_name}' is switched off.")
    if not any(out["recipients"].values()):
        out["warnings"].append(f"Alert '{a.alert_name}' has no active recipients today, so a holiday mail would have nobody to go to.")
    if not out["smtp"]["sender"] and not out["smtp"]["designated"]:
        out["warnings"].append("No sender is set for this alert (Masters > Alert Senders) and no separate account in the environment, so the default account is used.")
    return out


def subject_for(ev, setup, day):
    """The event's own subject, else the alert's, else 'Happy <name>'. {name} is the event's name and {year} the year of the day it goes out."""
    pattern = (ev.subject or "").strip() or (setup.get("subject") or "").strip() or f"Happy {ev.name}"
    return pattern.replace("{name}", ev.name).replace("{year}", str(day.year))[:200]


def build_mail(ev, setup, day=None):
    """-> (subject, html, text, inline_images) for one event."""
    day = day or datetime.date.today()
    data, sub, width = mail_picture(ev)
    subject = subject_for(ev, setup, day)
    alt = ev.name.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
    html = (
        '<div style="margin:0;padding:0;background:#ffffff;text-align:center">'
        f'<img src="cid:holiday" alt="{alt}" width="{width}" style="display:block;margin:0 auto;max-width:100%;height:auto;border:0">'
        "</div>"
    )
    return subject, html, ev.name, [("holiday", data, sub)]


def send_event(ev, setup, day, designated=True):
    """Sends one event's mail to the alert's recipients. Returns the mailer's result plus the recipient snapshot."""
    subject, html, text, images = build_mail(ev, setup, day)
    r = setup["recipients"]
    result = mailer.send_scheduled_email(
        subject, html, text, to=r["to"], cc=r["cc"], bcc=r["bcc"], from_name=setup["from_name"], inline_images=images,
        trigger=f"Holiday: {ev.name}"[:200], trigger_code=TRIGGER_CODE, designated=designated,
        alert_id=(setup.get("alert") or {}).get("id"),
    )
    result["recipients"] = ", ".join([*r["to"], *(f"cc:{a}" for a in r["cc"]), *(f"bcc:{a}" for a in r["bcc"])])
    return result


# ── the job the scheduler runs ──────────────────────────────────────────────────────────────────────────────────────────────

class HolidayJob(JobBase):
    key = JOB_KEY
    name = "Holiday Mailer"

    def plan(self, now, days=7):
        """Makes sure there is an item for every day an active event goes out, from today to `days` days ahead, and cancels planned ones that no longer
        apply (the event was removed, switched off, or its dates changed). Returns {"planned": n, "cancelled": n}."""
        today = now.date()
        hi = today + datetime.timedelta(days=days)
        hour = get_setup(today)["send_hour"]
        planned = cancelled = 0
        wanted = {}
        for ev in HolidayEvent.objects.filter(is_active="Y"):
            for d in send_dates(ev, today, hi):
                wanted[(str(ev.event_id), d)] = ev
        for (subject_key, day), ev in wanted.items():
            due = datetime.datetime.combine(day, datetime.time(hour=hour))
            label = f"{ev.name} · {day_text(ev, day).lower()}" if day_text(ev, day) else ev.name  # "Diwali · day 2 of 3"
            item, created = SchedItem.objects.get_or_create(
                job_key=JOB_KEY, subject_key=subject_key, send_date=day,
                defaults={"label": label, "due_at": due, "status": "planned", "cr_dt": now},
            )
            if created:
                planned += 1
            elif item.status in ("planned", "failed") and (item.label != label or item.due_at != due):
                SchedItem.objects.filter(pk=item.pk).update(label=label, due_at=due, mod_dt=now)
        for item in SchedItem.objects.filter(job_key=JOB_KEY, status="planned", send_date__gte=today, send_date__lte=hi):
            if (item.subject_key, item.send_date) not in wanted:
                SchedItem.objects.filter(pk=item.pk).update(status="cancelled", note="The event was removed, switched off, or its dates changed.", mod_dt=now)
                cancelled += 1
        return {"planned": planned, "cancelled": cancelled}

    def _compose_and_send(self, ev, day, now, designated=True):
        """Builds and sends the mail for one event on one day. Returns (error, result); error is "" when the mail went."""
        setup = get_setup(now.date())
        result = None
        error = ""
        if not setup["trigger_found"] or not setup["trigger_active"]:
            error = "The trigger for the holiday mail is missing or switched off."
        elif not setup["alert"]["active"]:
            error = f"The alert '{setup['alert']['name']}' is switched off. Tick Active on it in Masters > Alert Details."
        elif not any(setup["recipients"].values()):
            error = f"The alert has no active recipients on {now.date()}."
        elif not os.path.isfile(picture_path(ev)):
            error = f"The picture for '{ev.name}' is missing from the media folder. Upload it again."
        if not error:
            try:
                result = send_event(ev, setup, day, designated=designated)
                if not result["ok"]:
                    error = result["error"] or "The mail could not be sent."
            except Exception as exc:
                log.exception("holiday mail for %s failed while it was being built", ev.name)
                error = f"{type(exc).__name__}: {exc}"
        return error, result

    def _event(self, item):
        return HolidayEvent.objects.filter(pk=int(item.subject_key)).first() if item.subject_key.isdigit() else None

    def attempt(self, item, now, designated=True):
        """One try at sending one item. Updates the item and returns True when the mail went."""
        ev = self._event(item)
        if ev is None:
            SchedItem.objects.filter(pk=item.pk).update(status="cancelled", note="The event is no longer on the list.", mod_dt=now)
            return False
        item.attempts += 1
        error, result = self._compose_and_send(ev, item.send_date, now, designated)
        fields = {"attempts": item.attempts, "last_attempt_at": now, "mod_dt": now}
        if result:
            fields.update(smtp_used=result["smtp_used"], email_log_id=result["email_log_id"], recipients=result["recipients"][:2000])
        if error:
            fields.update(status="failed", last_error=error[:4000])
            log.error("holiday mail for %s (item %s, attempt %s) failed: %s", ev.name, item.pk, item.attempts, error)
            SchedItem.objects.filter(pk=item.pk).update(**fields)
            return False
        fields.update(status="sent", sent_at=now, last_error="")
        SchedItem.objects.filter(pk=item.pk).update(**fields)
        log.info("holiday mail for %s sent (item %s, %s account)", ev.name, item.pk, result["smtp_used"])
        return True

    def resend(self, item, now):
        """Sends an already-sent item again (a new mail, a new Email Log row). The item stays 'sent'. Returns (ok, error)."""
        ev = self._event(item)
        if ev is None:
            return False, "The event is no longer on the list."
        error, result = self._compose_and_send(ev, item.send_date, now, True)
        fields = {"mod_dt": now}
        if result:
            fields.update(email_log_id=result["email_log_id"], smtp_used=result["smtp_used"], recipients=result["recipients"][:2000])
        if error:
            fields.update(last_error=f"Resend failed: {error}"[:4000])
            log.error("resend of the holiday mail for %s (item %s) failed: %s", ev.name, item.pk, error)
            SchedItem.objects.filter(pk=item.pk).update(**fields)
            return False, error
        fields.update(resend_count=item.resend_count + 1, last_error="", note=f"Resent {now:%d %b %Y %H:%M}")
        SchedItem.objects.filter(pk=item.pk).update(**fields)
        log.info("holiday mail for %s resent (item %s)", ev.name, item.pk)
        return True, ""


JOB = HolidayJob()
