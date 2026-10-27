"""Scheduled report mails: a report that is built from the data and mailed on a cycle ("every 15 days"), not on a calendar date like a birthday.

What decides what (nothing is written into the code except what the report itself is):
  * Which alert the report belongs to, and whether it is on: ONE row of Notification Triggers (trigger point "automation", an action such as
    "send_haz_id_register_mail"), pointing at an alert in Alert Details. Switching that row off, or unticking Active on the alert, stops it.
  * WHEN it goes: the alert's Next Mail date and its Start Time (the hour). The hourly scheduler sends the report on the first run at or after that
    date and hour. After it goes out, Next Mail moves forward by the alert's Frequency (days): from the date it was due, not from the day it was
    sent, so a late run does not shift the cycle; and if the service was down for more than one cycle, to the next future date of the same cycle,
    so there is one catch-up mail and not several. Frequency must be at least 1.
  * What the report looks at: the alert's Window (days), in a way each report defines (for the HAZ ID Register: cards open longer than the window).
  * WHO gets it: the alert's active rows in Alert To Users (To, Cc, Bcc), the same as every other alert (core/notification_triggers.py).
  * The subject: the alert's Mail Subject. The sender: the alert's own account in Alert Senders when it has one, else the default account (never the
    birthday account); the name next to the From address is the alert sender's display name, else none (the mail server adds its own).
  * A report that fails is retried at the next hourly runs; after its last try the people in SCHEDULER_ERROR_MAIL_TO are told (core/error_mail.py).
A skipped run moves Next Mail on as well (the cycle is skipped, not repeated the next day). Resend builds a fresh report and does not move the date."""

import datetime
import logging
from dataclasses import dataclass, field

from django.conf import settings

from . import mailer
from .models import MailAlertDtl, SchedItem
from .notification_triggers import resolve_alert_recipients, resolve_alert_recipients_detailed
from .sched_base import JobBase

log = logging.getLogger("seros.scheduler")


RUN_COOLDOWN_SECONDS = 60  # how long after a run by hand another is refused


class RunMode(ValueError):
    """A run by hand was refused because the chosen change to Next Mail cannot be made; the message says why, for the person."""


class RunBusy(Exception):
    """A run by hand was refused because one has just been made or is going on; the message says so, for the person."""


@dataclass
class ReportMail:
    subject: str
    html: str
    text: str
    attachments: list = field(default_factory=list)  # [(file name, bytes, mime type)]
    empty: bool = False  # nothing to report: the mail says so and has no attachment
    summary: str = ""  # one line about what was in it, kept on the Scheduled Mails item


def next_after(base, freq, today, hour):
    """The next Next Mail date: `base` (the date the run was due) plus `freq` days, and again `freq` days until it is after `today` (so a long gap
    gives the next future date of the same cycle). Returns a datetime at `hour`:00."""
    nxt = base + datetime.timedelta(days=freq)
    while nxt <= today:
        nxt += datetime.timedelta(days=freq)
    return datetime.datetime.combine(nxt, datetime.time(hour=hour))


class ScheduledReportJob(JobBase):
    schedule_kind = "cycle"
    report_name = ""  # "HAZ ID Register": the label on Scheduled Mails
    description = ""  # one sentence on the Report Mails page: what the report contains
    trigger_code = ""  # the Email Log's trigger code, e.g. "auto.haz_id_register"

    # ── what a report supplies ──
    def build(self, alert, now):
        """-> ReportMail for this alert as of `now`. Raises on any problem (the item then fails with the message)."""
        raise NotImplementedError

    # ── setup, as the pages show it ──
    def from_name(self, alert):
        from . import mailer as _m

        sender = _m.sender_info(alert.alert_id) if alert else None
        return ((sender or {}).get("display_name") or "").strip()  # blank: the From address only, the mail server adds whatever name it uses

    def get_setup(self, today=None):
        today = today or datetime.date.today()
        from .models import NotificationTrigger

        trig = NotificationTrigger.objects.filter(entity_key=self.trigger_entity, action=self.trigger_action).select_related("alert").first()
        out = {
            "trigger_found": bool(trig), "trigger_active": bool(trig and trig.notification_trigger_active == "Y"), "alert": None, "from_name": "", "from_address": mailer.sender_identity(None, False)["address"], "links": mailer.alert_links(None, ""), "subject": "",
            "send_hour": 7, "window": 0, "freq": 0, "next_mail_dt": None, "recipients": {"to": [], "cc": [], "bcc": []}, "warnings": [],
            "smtp": {"designated": False, "designated_host": "", "default_host": settings.EMAIL_HOST, "sender": None},
            "error_mail_to": list(settings.SCHEDULER_ERROR_MAIL_TO),
        }
        if not trig:
            out["warnings"].append(f"No trigger row connects the {self.report_name} to an alert. Add one in Masters > Notification Triggers (Automation → the {self.report_name} action).")
            return out
        a = trig.alert
        out["alert"] = {"id": a.alert_id, "name": a.alert_name, "active": a.alert_active == "Y"}
        out["subject"] = a.mail_subject or ""
        out["send_hour"] = a.start_time if a.start_time is not None else 7
        out["window"], out["freq"], out["next_mail_dt"] = a.alert_window, a.alert_freq, a.next_mail_dt
        out["recipients"] = resolve_alert_recipients(a.alert_id, as_of=today)
        out["smtp"]["sender"] = mailer.sender_info(a.alert_id)
        out["from_address"] = mailer.sender_identity(a.alert_id, False)["address"]
        out["links"] = mailer.alert_links(a.alert_id, a.alert_name)
        out["from_name"] = self.from_name(a)
        if out["smtp"]["sender"] and out["smtp"]["sender"]["broken"]:
            out["warnings"].append("The sender set for this alert cannot be used: " + out["smtp"]["sender"]["broken"] + ". The default account is used instead.")
        if not out["trigger_active"]:
            out["warnings"].append(f"The trigger is switched off, so the {self.report_name} will not be sent.")
        if a.alert_active != "Y":
            out["warnings"].append(f"The alert '{a.alert_name}' is switched off. Tick Active on it in Masters > Alert Details.")
        if not any(out["recipients"].values()):
            out["warnings"].append(f"Alert '{a.alert_name}' has no active recipients today, so the {self.report_name} would have nobody to go to.")
        if (a.alert_freq or 0) < 1:
            out["warnings"].append("The alert's Frequency must be at least 1 day, or the report is never scheduled.")
        if a.next_mail_dt is None:
            out["warnings"].append("The alert has no Next Mail date, so the report is never scheduled.")
        if not settings.SCHEDULER_ERROR_MAIL_TO:
            out["warnings"].append("SCHEDULER_ERROR_MAIL_TO is not set in the server's .env, so nobody is e-mailed when this report fails (it still shows on Scheduled Mails).")
        return out

    def setup(self, today=None):
        return self.get_setup(today)

    def recipients_detailed(self, as_of=None):
        a = self.alert()
        return resolve_alert_recipients_detailed(a.alert_id, as_of) if a else []

    def schedule_text(self, today):
        s = self.get_setup(today)
        if not s["alert"]:
            return "Not connected to an alert yet"
        nxt = f"{s['next_mail_dt']:%d %b %Y} at {s['send_hour']:02d}:00" if s["next_mail_dt"] else "no date set"
        return f"Every {s['freq']} days; next {nxt} (checked every hour)"

    # ── planning ──
    def plan(self, now, days=7):
        """Plans the one run that is due (or due within `days` days). Returns {"planned": n, "cancelled": n}."""
        today = now.date()
        trig_alert = self.alert()
        planned = cancelled = 0
        wanted = None
        if trig_alert and (trig_alert.alert_freq or 0) >= 1 and trig_alert.next_mail_dt is not None:
            due_date = trig_alert.next_mail_dt.date()
            run_date = max(due_date, today)  # behind schedule: one catch-up run today, never several
            if run_date <= today + datetime.timedelta(days=days):
                wanted = (str(trig_alert.alert_id), run_date, due_date)
        if wanted:
            key, run_date, due_date = wanted
            due = datetime.datetime.combine(run_date, datetime.time(hour=trig_alert.start_time if trig_alert.start_time is not None else 7))
            label = f"{self.report_name} · {run_date:%d %b %Y}"
            item, created = SchedItem.objects.get_or_create(
                job_key=self.key, subject_key=key, send_date=run_date,
                defaults={"label": label, "due_at": due, "status": "planned", "note": f"Due {due_date:%d %b %Y}", "cr_dt": now},
            )
            if created:
                planned += 1
            elif item.status == "cancelled":  # it was cancelled while the date was elsewhere, and is due again
                SchedItem.objects.filter(pk=item.pk).update(status="planned", label=label, due_at=due, note=f"Due {due_date:%d %b %Y}", mod_dt=now)
                planned += 1
            elif item.status in ("planned", "failed") and (item.due_at != due or item.label != label):
                SchedItem.objects.filter(pk=item.pk).update(label=label, due_at=due, mod_dt=now)
        for item in SchedItem.objects.filter(job_key=self.key, status="planned", send_date__gte=today):
            if not wanted or (item.subject_key, item.send_date) != (wanted[0], wanted[1]):
                SchedItem.objects.filter(pk=item.pk).update(status="cancelled", note="The alert's Next Mail date or Frequency changed, or it was switched off.", mod_dt=now)
                cancelled += 1
        return {"planned": planned, "cancelled": cancelled}

    # ── the next date ──
    def advance(self, alert_id, item_date, now):
        """Moves the alert's Next Mail on by its Frequency after a run (sent or skipped). Only when the date has not already moved past this run."""
        alert = MailAlertDtl.objects.filter(pk=alert_id).first()
        if alert is None or alert.next_mail_dt is None or (alert.alert_freq or 0) < 1:
            return None
        base = alert.next_mail_dt.date()
        if base > item_date:  # already moved on (for example an un-skipped item sent after its cycle was skipped)
            return None
        new = next_after(base, alert.alert_freq, now.date(), alert.start_time if alert.start_time is not None else 7)
        MailAlertDtl.objects.filter(pk=alert.pk).update(next_mail_dt=new, mod_dt=now)
        log.info("%s: Next Mail of alert %s moved from %s to %s", self.report_name, alert.alert_id, alert.next_mail_dt, new)
        return new

    def on_skip(self, item, now):
        alert_id = self._alert_id(item)
        if alert_id:
            self.advance(alert_id, item.send_date, now)

    # ── sending ──
    def _blockers(self, setup, now):
        if not setup["trigger_found"] or not setup["trigger_active"]:
            return f"The trigger for the {self.report_name} is missing or switched off."
        if not setup["alert"]["active"]:
            return f"The alert '{setup['alert']['name']}' is switched off. Tick Active on it in Masters > Alert Details."
        if not any(setup["recipients"].values()):
            return f"The alert has no active recipients on {now.date()}."
        return ""

    def send_report(self, alert, setup, now, designated=True):
        """Builds and sends the report to the alert's recipients. Returns (error, result, mail); error is "" when it went."""
        error, result, mail = self._blockers(setup, now), None, None
        if not error:
            try:
                mail = self.build(alert, now)
                r = setup["recipients"]
                result = mailer.send_scheduled_email(
                    mail.subject, mail.html, mail.text, to=r["to"], cc=r["cc"], bcc=r["bcc"], from_name=setup["from_name"], trigger=f"{self.report_name}: {alert.alert_name}"[:200],
                    trigger_code=self.trigger_code, designated=designated, alert_id=alert.alert_id, attachments=mail.attachments, env_account=False,
                )
                result["recipients"] = ", ".join([*r["to"], *(f"cc:{a}" for a in r["cc"]), *(f"bcc:{a}" for a in r["bcc"])])
                if not result["ok"]:
                    error = result["error"] or "The mail could not be sent."
            except Exception as exc:
                log.exception("%s failed while it was being built or sent", self.report_name)
                error = f"{type(exc).__name__}: {exc}"
        return error, result, mail

    @staticmethod
    def _alert_id(item):
        """The alert an item belongs to: its subject key is the alert's id, or "<id>:by hand <time>" for a run started by hand."""
        head = (item.subject_key or "").split(":")[0]
        return int(head) if head.isdigit() else None

    def _alert_of(self, item):
        alert_id = self._alert_id(item)
        return MailAlertDtl.objects.filter(pk=alert_id).first() if alert_id else None

    def attempt(self, item, now, designated=True):
        alert = self._alert_of(item)
        if alert is None:
            SchedItem.objects.filter(pk=item.pk).update(status="cancelled", note="The alert no longer exists.", mod_dt=now)
            return False
        item.attempts += 1
        error, result, mail = self.send_report(alert, self.get_setup(now.date()), now, designated)
        fields = {"attempts": item.attempts, "last_attempt_at": now, "mod_dt": now}
        if result:
            fields.update(smtp_used=result["smtp_used"], email_log_id=result["email_log_id"], recipients=result["recipients"][:2000])
        if error:
            fields.update(status="failed", last_error=error[:4000])
            log.error("%s (item %s, attempt %s) failed: %s", self.report_name, item.pk, item.attempts, error)
            SchedItem.objects.filter(pk=item.pk).update(**fields)
            return False
        fields.update(status="sent", sent_at=now, last_error="", note=f"{(item.note or '').split(' · ')[0]} · {mail.summary}".strip(" ·")[:300])
        SchedItem.objects.filter(pk=item.pk).update(**fields)
        log.info("%s sent (item %s, %s account): %s", self.report_name, item.pk, result["smtp_used"], mail.summary)
        if ":by hand" not in (item.subject_key or ""):  # a run by hand moves Next Mail as the person chose (run_now), not by the cycle's rule
            self.advance(alert.alert_id, item.send_date, now)
        return True

    def resend(self, item, now):
        alert = self._alert_of(item)
        if alert is None:
            return False, "The alert no longer exists."
        error, result, mail = self.send_report(alert, self.get_setup(now.date()), now, True)
        fields = {"mod_dt": now}
        if result:
            fields.update(email_log_id=result["email_log_id"], smtp_used=result["smtp_used"], recipients=result["recipients"][:2000])
        if error:
            fields.update(last_error=f"Resend failed: {error}"[:4000])
            log.error("resend of %s (item %s) failed: %s", self.report_name, item.pk, error)
            SchedItem.objects.filter(pk=item.pk).update(**fields)
            return False, error
        fields.update(resend_count=item.resend_count + 1, last_error="", note=f"Resent {now:%d %b %Y %H:%M} · {mail.summary}"[:300])
        SchedItem.objects.filter(pk=item.pk).update(**fields)
        return True, ""

    # ── started by hand from the Report Mails page ──
    MODES = ("copy", "count", "restart")

    def run_now_effect(self, alert, today):
        """What "send now" would do to Next Mail, for each choice the dialog offers (see run_now). Returns
        {"due", "default_mode", "modes": {"copy"|"count"|"restart": {"allowed", "next"}}, "moves", "from", "to"}; "moves"/"to" describe the default choice.
          copy    an extra copy: Next Mail stays. Only while Next Mail is still ahead (if it is due, the scheduler sends it at its next run anyway).
          count   it counts as the next send: Next Mail moves on by the frequency from the date it was due, so the cycle keeps its rhythm
                  (6 Nov -> 21 Nov, or a due 22 Oct -> 6 Nov).
          restart a new cycle from today: Next Mail becomes today plus the frequency (27 Oct -> 11 Nov)."""
        none = {"allowed": False, "next": None}
        if alert is None:
            return {"due": False, "default_mode": "copy", "modes": {m: dict(none) for m in self.MODES}, "moves": False, "from": None, "to": None}
        nm, freq = alert.next_mail_dt, (alert.alert_freq or 0)
        hour = alert.start_time if alert.start_time is not None else 7
        has_cycle = nm is not None and freq >= 1
        due = bool(has_cycle and nm.date() <= today)
        modes = {
            "copy": {"allowed": not due, "next": nm},
            "count": {"allowed": has_cycle, "next": next_after(nm.date(), freq, today, hour) if has_cycle else None},
            "restart": {"allowed": has_cycle, "next": datetime.datetime.combine(today + datetime.timedelta(days=freq), datetime.time(hour=hour)) if has_cycle else None},
        }
        default = "count" if due else "copy"
        moves = default != "copy"
        return {"due": due, "default_mode": default, "modes": modes, "moves": moves, "from": nm, "to": modes[default]["next"] if moves else None}

    def run_now(self, alert, who, now, mode=None):
        """Builds and sends the report to the alert's recipients straight away. It is recorded on Scheduled Mails like any run (labelled "by hand"). `mode`
        (see run_now_effect) says what happens to Next Mail once it has gone; without one, an extra copy when Next Mail is ahead and "count" when it is due.
        Returns (ok, error, item). A failed run changes nothing, and is not retried by itself: the person sees the reason and can send again. A second run
        while one is going, or within a minute of the last one, is refused (RunBusy): a double click, or two people at once, must not send the mail twice.
        Raises RunMode for a choice that cannot be made."""
        from django.db import IntegrityError, transaction

        eff = self.run_now_effect(alert, now.date())
        mode = mode or eff["default_mode"]
        if mode not in self.MODES:
            raise RunMode("Choose what happens to Next Mail.")
        if not eff["modes"][mode]["allowed"]:
            raise RunMode("Next Mail is due, so the scheduler sends it at its next run: choose to count this as that send, or to start a new cycle from today." if mode == "copy" else "This alert has no Frequency or Next Mail date, so it cannot be moved on.")
        mine = SchedItem.objects.filter(job_key=self.key, subject_key__startswith=f"{alert.alert_id}:by hand")
        recent = mine.filter(cr_dt__gte=now - datetime.timedelta(seconds=RUN_COOLDOWN_SECONDS)).order_by("-item_id").first() or mine.filter(
            status="sending", last_attempt_at__gte=now - datetime.timedelta(minutes=5)
        ).order_by("-item_id").first()
        if recent is not None:
            raise RunBusy(f"It was already sent by hand at {recent.cr_dt:%H:%M:%S}. Wait a minute before sending it again.")
        try:
            with transaction.atomic():  # the key holds the minute, so two requests in the same minute cannot both create it (the database refuses the second)
                item = SchedItem.objects.create(
                    job_key=self.key, subject_key=f"{alert.alert_id}:by hand {now:%Y%m%d%H%M}", label=f"{self.report_name} · {now:%d %b %Y %H:%M} (by hand)", send_date=now.date(),
                    due_at=now, status="sending", attempts=0, last_attempt_at=now, note=f"Started by {who}"[:300], cr_dt=now,
                )
        except IntegrityError:
            raise RunBusy("It is being sent right now. Wait a minute before sending it again.")
        ok = self.attempt(item, now)
        item.refresh_from_db()
        if ok and mode != "copy":
            MailAlertDtl.objects.filter(pk=alert.pk).update(next_mail_dt=eff["modes"][mode]["next"], mod_dt=now)
            self.plan(now)  # the plan follows the new date at once
            note = {"count": "counted as the next send", "restart": "a new cycle from today"}[mode]
            SchedItem.objects.filter(pk=item.pk).update(note=f"{item.note} · {note}"[:300])
            item.refresh_from_db()
        return ok, ("" if ok else item.last_error), item

    def set_schedule(self, alert, day, hour, now):
        """Sets the alert's Next Mail date and Start Time (the hour) from the Report Mails page. The date cannot be in the past (use send now for that).
        Returns (old Next Mail, new Next Mail); raises ValueError with the reason."""
        if not isinstance(day, datetime.date) or isinstance(day, datetime.datetime):
            raise ValueError("Choose a date.")
        if day < now.date():
            raise ValueError("The date cannot be in the past. To send it now, use Send now.")
        if not isinstance(hour, int) or not 0 <= hour <= 23:
            raise ValueError("The hour must be from 0 to 23.")
        old = alert.next_mail_dt
        new = datetime.datetime.combine(day, datetime.time(hour=hour))
        MailAlertDtl.objects.filter(pk=alert.pk).update(next_mail_dt=new, start_time=hour, mod_dt=now)
        self.plan(now)  # the plan follows the new date at once: an old plan is cancelled, a new one made when the date is near
        return old, new
