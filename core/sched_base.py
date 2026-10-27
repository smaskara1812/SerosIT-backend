"""What every automatic-mail job (core/scheduler.py) shares: sending what is due, marking what was missed, and retrying what failed.
A job supplies `key`, `name`, `plan(now)`, `attempt(item, now)` and `resend(item, now)`; the rest is here."""

import datetime

from django.conf import settings
from django.db.models import Q

from .models import SchedItem


class JobBase:
    key = ""
    name = ""

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
        ).order_by("due_at", "item_id")
        for item in list(due):
            first = item.status == "planned"
            SchedItem.objects.filter(pk=item.pk).update(status="sending", last_attempt_at=now)
            item.refresh_from_db()
            ok = self.attempt(item, now)
            out["sent" if ok else "failed"] += 1
            if not first:
                out["retried"] += 1
        return out
