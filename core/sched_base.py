"""What every automatic-mail job (core/scheduler.py) shares: sending what is due, marking what was missed, and retrying what failed.
A job supplies `key`, `name`, `plan(now)`, `attempt(item, now)` and `resend(item, now)`; the rest is here. A job that is switched on by a Notification Triggers
row names it in `trigger_entity` / `trigger_action`, which lets the pages find its alert and the people it goes to."""

import datetime

from django.conf import settings
from django.db.models import Q

from . import error_mail
from .models import MailAlertDtl, NotificationTrigger, SchedItem


class JobBase:
    key = ""
    name = ""
    trigger_entity = None
    trigger_action = None
    schedule_kind = "dates"  # "dates": goes out on calendar days (birthdays, holidays); "cycle": goes out on Next Mail and repeats (report mails). Used by the pause/resume dialogs.

    def alert(self):
        """The alert this job's Notification Triggers row points at, or None."""
        if not self.trigger_entity:
            return None
        t = NotificationTrigger.objects.filter(entity_key=self.trigger_entity, action=self.trigger_action).select_related("alert").first()
        return t.alert if t else None

    def schedule_text(self, today):
        """One line for the Scheduled Mails page: when this automation goes out."""
        return "Hourly"

    def setup(self, today=None):
        """How this automation is set up as the pages show it: {"alert", "from_name", "subject", "recipients", "warnings", ...}; None when a job has none."""
        return None

    def on_skip(self, item, now):
        """Called after an item of this job was skipped by hand. A job whose next date depends on its runs (a report) moves it on here."""

    def process(self, now, max_retries=None):
        """Sends what is due. Returns {"sent", "failed", "missed", "retried"}."""
        max_retries = settings.SCHEDULER_MAX_RETRIES if max_retries is None else max_retries
        out = {"sent": 0, "failed": 0, "missed": 0, "retried": 0}
        today = now.date()
        # a planned mail whose day has passed was never sent (the service was down): shown as Missed, and can be sent by hand
        out["missed"] = SchedItem.objects.filter(job_key=self.key, status="planned", send_date__lt=today).update(status="missed", note="The scheduler was not running on that day.", mod_dt=now)
        # a mail left 'sending' (the service stopped part-way) is treated as failed so it is retried
        SchedItem.objects.filter(job_key=self.key, status="sending", last_attempt_at__lt=now - datetime.timedelta(minutes=30)).update(status="failed", last_error="Interrupted while sending.")
        hour_start = now.replace(minute=0, second=0, microsecond=0)
        due = SchedItem.objects.filter(job_key=self.key, send_date=today, due_at__lte=now).filter(
            Q(status="planned") | Q(status="failed", attempts__lte=max_retries, last_attempt_at__lt=hour_start)
        ).exclude(subject_key__contains=":by hand").order_by("due_at", "item_id")  # a run started by hand is not retried by itself: the person saw the result
        for item in list(due):
            first = item.status == "planned"
            SchedItem.objects.filter(pk=item.pk).update(status="sending", last_attempt_at=now)
            item.refresh_from_db()
            ok = self.attempt(item, now)
            out["sent" if ok else "failed"] += 1
            if not first:
                out["retried"] += 1
        # an item whose tries are all used: tell the people in SCHEDULER_ERROR_MAIL_TO, once. Also tried on later runs (for a day) for an error mail that
        # could not go the first time.
        for item in SchedItem.objects.filter(job_key=self.key, status="failed", attempts__gt=max_retries, error_mailed_at__isnull=True, send_date__gte=today - datetime.timedelta(days=1)):
            error_mail.notify_item_failed(self.name, item, now)
        return out
