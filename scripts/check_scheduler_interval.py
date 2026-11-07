"""Checks how often the scheduler runs (core/sched_clock.py, SCHEDULER_INTERVAL_MINUTES): the run times stay on the clock (:00 and :30 by default), a value that does not divide
an hour is read as 30, the service sleeps to five seconds past the next run, every automation's schedule line says the real interval, Scheduled Mails shows the next run on the
interval, the Mail Controls page is told the interval, and a mail due on the half hour goes out on the run at that time.

    cd backend
    .venv/bin/python scripts/check_scheduler_interval.py
"""
import datetime
import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.test import APIClient

from core import mail_settings, mail_summary, mailer, sched_clock, scheduler
from core.management.commands import run_scheduler
from core.models import MailSummarySetting, SchedItem, UserProfile
from core.permissions import invalidate_user_access

fails = []


def ok(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {detail}" if not cond else ""))
    if not cond:
        fails.append(name)


class Rollback(Exception):
    pass


DT = datetime.datetime
real_default = settings.SCHEDULER_INTERVAL_MINUTES
ok("with nothing in the .env the default is 30 minutes", real_default == 30 or os.getenv("SCHEDULER_INTERVAL_MINUTES") is not None, str(real_default))

# ── the clock ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────
settings.SCHEDULER_INTERVAL_MINUTES = 30
n = sched_clock.next_run_after
ok("every 30 minutes: 10:00:00 -> 10:30, 10:29:59 -> 10:30, 10:30:00 -> 11:00", n(DT(2030, 1, 1, 10, 0, 0)) == DT(2030, 1, 1, 10, 30) and n(DT(2030, 1, 1, 10, 29, 59)) == DT(2030, 1, 1, 10, 30) and n(DT(2030, 1, 1, 10, 30, 0)) == DT(2030, 1, 1, 11, 0))
ok("it crosses midnight", n(DT(2030, 1, 1, 23, 45, 0)) == DT(2030, 1, 2, 0, 0))
settings.SCHEDULER_INTERVAL_MINUTES = 15
ok("every 15 minutes: 10:44 -> 10:45, 10:45 -> 11:00", n(DT(2030, 1, 1, 10, 44)) == DT(2030, 1, 1, 10, 45) and n(DT(2030, 1, 1, 10, 45)) == DT(2030, 1, 1, 11, 0))
settings.SCHEDULER_INTERVAL_MINUTES = 60
ok("every hour is what it was: 10:15 -> 11:00", n(DT(2030, 1, 1, 10, 15)) == DT(2030, 1, 1, 11, 0))
for bad in (45, 0, -5, 7, 90, "abc", None):
    settings.SCHEDULER_INTERVAL_MINUTES = bad
    if sched_clock.interval_minutes() != 30:
        ok(f"a value that is not an allowed interval ({bad!r}) is read as 30", False, str(sched_clock.interval_minutes()))
        break
else:
    ok("a value that does not divide an hour (45, 0, -5, 7, 90, text, nothing) is read as 30", True)
settings.SCHEDULER_INTERVAL_MINUTES = 30
ok("the interval is described in words", sched_clock.interval_text() == "every 30 minutes" and sched_clock.interval_text(60) == "every hour" and sched_clock.interval_text(15) == "every 15 minutes")

# ── the service's sleep ──────────────────────────────────────────────────────────────────────────────────────────────────────────
ok("the service sleeps to five seconds past the next run", abs(run_scheduler.seconds_to_next_run(DT(2030, 1, 1, 10, 0, 8)) - (1800 - 8 + 5)) < 0.01 and abs(run_scheduler.seconds_to_next_run(DT(2030, 1, 1, 10, 29, 59)) - 6) < 0.01)
ok("never less than a second", run_scheduler.seconds_to_next_run(DT(2030, 1, 1, 10, 29, 59, 999999)) >= 1)

# ── what people read ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
today = datetime.date(2030, 1, 1)
lines = [j.schedule_text(today) for j in scheduler.JOBS.values() if j.key != "mail_summary"] + [mail_summary.JOB.schedule_text(today)]
ok("no automation says it is checked every hour while it is every 30 minutes", all("every hour" not in x and "Hourly" not in x for x in lines), str([x for x in lines if "hour" in x.lower()]))
by_key = {j.key: j.schedule_text(today) for j in scheduler.JOBS.values()}
ok("the birthday and holiday schedule lines say every 30 minutes", "every 30 minutes" in by_key["birthday"] and "every 30 minutes" in by_key["holiday"], str(by_key))

try:
    with transaction.atomic():
        MailSummarySetting.objects.all().delete()
        mail_settings.clear_cache()
        u = get_user_model().objects.create_user(username="zz_interval_admin", password="x", is_superuser=False)
        uid = (UserProfile.objects.order_by("-user_id").first().user_id or 0) + 1
        UserProfile.objects.create(user_id=uid, user_login_id="zz_interval_admin", is_app_admin=True)
        invalidate_user_access("zz_interval_admin")
        c = APIClient(HTTP_HOST="localhost")
        c.force_authenticate(u)
        ok("the Mail Controls page is told the interval", c.get("/api/admin/mail-summary/").json().get("run_every") == 30)
        settings.SCHEDULER_INTERVAL_MINUTES = 15
        ok("and it changes with the setting", c.get("/api/admin/mail-summary/").json().get("run_every") == 15)
        settings.SCHEDULER_INTERVAL_MINUTES = 30
        st = c.get("/api/admin/scheduled-mails/").json()
        nxt = DT.fromisoformat(st["jobs"][0]["next_run"]) if st.get("jobs") else None
        ok("Scheduled Mails shows the next run on the interval and says how often it runs", st.get("run_every_minutes") == 30 and nxt is not None and nxt.minute in (0, 30) and nxt.second == 0, str((st.get("run_every_minutes"), nxt)))
        # a mail due on the half hour goes out on the run at that time (the summary, set for 21:30)
        sent = []
        mailer._deliver = lambda subject, html, text, to, cc, bcc, from_name, smtp, inline_images, attachments=None: sent.append(subject)
        settings.EMAIL_HOST = "smtp.default.test"
        mail_settings.clear_cache()
        c.put("/api/admin/mail-summary/", {"section": "summary", "on": True, "time": "21:30", "to": ["own@example.test"], "same_as_error": False, "send_when_quiet": True, "grouped": True}, format="json")
        SchedItem.objects.filter(job_key="mail_summary").delete()
        job = mail_summary.JOB
        ok("the summary's schedule line says every 30 minutes once it is on", "every 30 minutes" in job.schedule_text(today))
        job.plan(DT(2030, 1, 1, 17, 0, 5))
        job.process(DT(2030, 1, 1, 21, 0, 5))
        ok("a mail due at 21:30 is not sent by the 21:00 run", not sent)
        job.process(DT(2030, 1, 1, 21, 30, 5))
        ok("and goes out on the 21:30 run", len(sent) == 1)
        raise Rollback
except Rollback:
    pass
settings.SCHEDULER_INTERVAL_MINUTES = real_default
mail_settings.clear_cache()
print("\nFAILED: " + ", ".join(fails) if fails else "\nall checks passed")
sys.exit(1 if fails else 0)
