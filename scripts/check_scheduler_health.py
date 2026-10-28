"""Checks the scheduler health feature (core/scheduler_health.py): the heartbeat and what counts as running, stopped on purpose or dead (service mode and task
mode), overdue mail, the mail-server check, the watchdog's events and e-mails (one mail per problem, none while alerts are off, recovery only for a stopped
service or an unreachable mail server, retry when the alert could not be sent), the command's exit codes, and the endpoints with people holding exactly the
rights named. A fake mail server is used and everything in the database is rolled back.

    cd backend
    .venv/bin/python scripts/check_scheduler_health.py
"""
import datetime, io, os, shutil, sys, tempfile, django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TMP = tempfile.mkdtemp(prefix="sched_health_check_")
os.environ["LOG_DIR"] = os.path.join(TMP, "logs")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import transaction
from rest_framework.test import APIClient
from core import mailer, scheduler_health as sh
from core.models import SchedHealthEvent, SchedHeartbeat, SchedItem, SchedJob, UserPermission, UserProfile
from core.permissions import invalidate_user_access

sent, down = [], set()


def fake_deliver(subject, html, text, to, cc, bcc, from_name, smtp, inline_images, attachments=None):
    if smtp["host"] in down:
        raise ConnectionError(f"{smtp['host']} refused the connection")
    sent.append({"subject": subject, "html": html, "to": to, "host": smtp["host"]})


mailer._deliver = fake_deliver
settings.EMAIL_HOST = "smtp.default.test"
settings.EMAIL_USE_CONSOLE = False
settings.BIRTHDAY_EMAIL_HOST = ""
settings.SCHEDULER_ERROR_MAIL_TO = ["it@example.test"]
settings.SCHEDULER_MODE = "service"
settings.SCHEDULER_STALE_MINUTES = 10
settings.SCHEDULER_STOPPED_GRACE_MINUTES = 60
settings.SCHEDULER_OVERDUE_HOURS = 2
settings.SCHEDULER_HEALTH_ALERTS = True
settings.SCHEDULER_HEALTH_REMINDER_HOURS = 0


class Rollback(Exception):
    pass


fails = []


def ok(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {detail}" if not cond else ""))
    if not cond:
        fails.append(name)


def mk(n, grants):
    U = get_user_model(); u = U.objects.create_user(username=n, password="x")
    uid = (UserProfile.objects.order_by("-user_id").first().user_id or 0) + 1
    UserProfile.objects.create(user_id=uid, user_login_id=n, is_app_admin=False)
    for key, flags in grants.items():
        UserPermission.objects.create(user_id=uid, menu_key=key, can_view="view" in flags, can_add="add" in flags, can_edit="edit" in flags, can_delete="delete" in flags, can_export="export" in flags)
    invalidate_user_access(n)
    c = APIClient(HTTP_HOST="localhost"); c.force_authenticate(u); return c


NOW = datetime.datetime(2026, 11, 10, 12, 0, 0)
M = lambda m: datetime.timedelta(minutes=m)


def hb(**kw):
    base = dict(last_tick_at=None, last_service_tick_at=None, last_manual_tick_at=None, last_alive_at=None, started_at=None, stopped_at=None, service_host="", service_pid=None,
                smtp_ok=None, smtp_checked_at=None, smtp_error="", smtp_fail_streak=0)
    base.update(kw)
    SchedHeartbeat.objects.update_or_create(heartbeat_id=1, defaults=base)


def alive(t):
    SchedHeartbeat.objects.filter(pk=1).update(last_alive_at=t - M(1))


def item(label, due_hours_ago, job="birthday", status="planned", day_offset=0, key=None):
    due = NOW - datetime.timedelta(hours=due_hours_ago)
    return SchedItem.objects.create(job_key=job, subject_key=key or label, label=label, send_date=NOW.date() + datetime.timedelta(days=day_offset), due_at=due, status=status, cr_dt=NOW)


def kinds(ev):
    return [p["kind"] for p in ev["problems"]]


class FakeSMTP:
    mode = "ok"

    def __init__(self, host, port, timeout=0):
        if FakeSMTP.mode == "fail":
            raise ConnectionRefusedError("[Errno 61] Connection refused")

    def ehlo(self): pass
    def starttls(self): pass
    def quit(self): pass


import smtplib
smtplib.SMTP = FakeSMTP
smtplib.SMTP_SSL = FakeSMTP

try:
    with transaction.atomic():
        SchedItem.objects.all().delete(); SchedHealthEvent.objects.all().delete(); SchedJob.objects.all().delete()

        print("A. is the service alive?")
        hb()
        e = sh.evaluate(NOW)
        ok("it has never run: critical, the service is not running", e["level"] == "critical" and e["state"] == "never" and kinds(e) == ["service_down"])
        hb(last_alive_at=NOW - M(3), started_at=NOW - M(180))
        e = sh.evaluate(NOW)
        ok("a heartbeat 3 minutes ago: running, ok, with its uptime", e["level"] == "ok" and e["state"] == "running" and e["heartbeat"]["uptime_minutes"] == 180 and not e["problems"])
        hb(last_alive_at=NOW - M(11))
        e = sh.evaluate(NOW)
        ok("no heartbeat for 11 minutes (the limit is 10): stopped without saying so, critical", e["state"] == "stale" and e["level"] == "critical" and "11 minutes" in e["problems"][0]["detail"])
        hb(last_alive_at=NOW - M(9))
        ok("9 minutes is still fine", sh.evaluate(NOW)["state"] == "running")
        hb(last_alive_at=NOW - M(30), stopped_at=NOW - M(30))
        e = sh.evaluate(NOW)
        ok("stopped properly 30 minutes ago: a planned stop, not a problem yet (a warning on the page only)", e["state"] == "stopped" and not e["problems"] and e["level"] == "warning" and "on purpose" in e["title"])
        hb(last_alive_at=NOW - M(90), stopped_at=NOW - M(90))
        e = sh.evaluate(NOW)
        ok("stopped properly and never started again after 60 minutes: now a problem", e["level"] == "critical" and kinds(e) == ["service_down"] and "not started again" in e["problems"][0]["title"])
        hb(last_alive_at=NOW - M(90), stopped_at=NOW - M(200))
        ok("a stop followed by a later heartbeat (it was started again, then died) is a crash, not a planned stop", sh.evaluate(NOW)["state"] == "stale")
        sh.heartbeat(NOW, start=True)
        b = SchedHeartbeat.objects.get(pk=1)
        ok("starting records the time, the server and the process, and clears the stop", b.started_at == NOW and b.last_alive_at == NOW and b.stopped_at is None and b.service_host and b.service_pid == os.getpid())
        sh.heartbeat(NOW + M(5), stop=True)
        ok("stopping properly records it", SchedHeartbeat.objects.get(pk=1).stopped_at == NOW + M(5))
        settings.SCHEDULER_MODE = "task"
        hb(last_service_tick_at=NOW - M(70))
        ok("task mode (an hourly task): the last run 70 minutes ago is fine", sh.evaluate(NOW)["state"] == "running")
        hb(last_service_tick_at=NOW - M(80))
        ok("and 80 minutes is not", sh.evaluate(NOW)["state"] == "stale")
        settings.SCHEDULER_MODE = "service"

        print("B. mail that should have gone")
        hb(last_alive_at=NOW - M(1), started_at=NOW - M(600))
        item("due 3 h ago", 3)
        e = sh.evaluate(NOW)
        ok("a planned mail due 3 hours ago (limit 2) is a warning", e["level"] == "warning" and kinds(e) == ["overdue"] and "due 3 h ago" in e["problems"][0]["detail"], str(e["problems"]))
        SchedItem.objects.all().delete()
        item("due 1 h ago", 1)
        ok("1 hour ago is fine", sh.evaluate(NOW)["level"] == "ok")
        item("tomorrow", 5, day_offset=1)
        ok("a mail for a future day is not overdue, whatever its time", sh.evaluate(NOW)["level"] == "ok")
        SchedItem.objects.all().delete()
        item("by hand", 5, key="233:by hand 1")
        ok("a run started by hand is not overdue", sh.evaluate(NOW)["level"] == "ok")
        SchedItem.objects.all().delete()
        item("paused one", 5, job="holiday")
        SchedJob.objects.create(job_key="holiday", name="Holiday", enabled="N")
        ok("an automation that is paused is not overdue (it was asked not to run)", sh.evaluate(NOW)["level"] == "ok")
        SchedJob.objects.filter(job_key="holiday").update(enabled="Y")
        item("sent late", 5, status="sent")
        item("failed", 5, status="failed")
        item("missed", 30, status="missed", day_offset=-1)
        e = sh.evaluate(NOW)
        ok("only planned mail counts as overdue; failed and missed are counted for the page", e["counts"]["overdue"] == 1 and e["counts"]["failed"] == 1 and e["counts"]["missed"] == 1, str(e["counts"]))
        hb(last_alive_at=NOW - M(30))
        ok("when the service is down the overdue mail is not reported separately (the stopped service is the problem)", kinds(sh.evaluate(NOW)) == ["service_down"])
        SchedItem.objects.all().delete()

        print("C. the mail-server check")
        hb(last_alive_at=NOW - M(1))
        FakeSMTP.mode = "ok"
        r = sh.smtp_check(NOW)
        ok("a reachable server is recorded as ok", r["ok"] is True and SchedHeartbeat.objects.get(pk=1).smtp_ok is True)
        FakeSMTP.mode = "fail"
        r = sh.smtp_check(NOW)
        ok("one failed check is recorded but is not yet a problem (it may be a blip)", r["ok"] is False and "refused" in r["error"].lower() and not sh.evaluate(NOW)["problems"] and SchedHeartbeat.objects.get(pk=1).smtp_fail_streak == 1)
        alive(NOW + M(15)); sh.smtp_check(NOW + M(15))
        e = sh.evaluate(NOW + M(15))
        ok("the second failure in a row is a critical problem", e["level"] == "critical" and kinds(e) == ["smtp_down"] and "2 checks" in e["problems"][0]["detail"])
        FakeSMTP.mode = "ok"
        alive(NOW + M(30)); sh.smtp_check(NOW + M(30))
        ok("one good check clears it", SchedHeartbeat.objects.get(pk=1).smtp_fail_streak == 0 and not sh.evaluate(NOW + M(30))["problems"])
        settings.EMAIL_USE_CONSOLE = True
        ok("on a development machine (the console backend) there is nothing to check", sh.smtp_check(NOW)["ok"] is None)
        settings.EMAIL_USE_CONSOLE = False

        print("D. the watchdog: one problem, one e-mail")
        hb(last_alive_at=NOW - M(30), service_host="SERVER01")
        sent.clear()
        res = sh.watchdog(NOW, check_smtp=False)
        ev = SchedHealthEvent.objects.get()
        ok("a stopped service opens an event and e-mails IT once", ev.kind == "service_down" and ev.level == "critical" and ev.alerted_at == NOW and len(sent) == 1 and sent[0]["to"] == ["it@example.test"], str(res["actions"]))
        ok("the mail names the problem, when it began, the server and what to do", "Scheduler problem: The scheduler service is not running" in sent[0]["subject"] and "SERVER01" in sent[0]["html"] and "Start the SerosIT scheduler service" in sent[0]["html"] and "S.I.S." not in sent[0]["html"])
        ok("the event began when the service was last seen", ev.started_at == NOW - M(30))
        sent.clear(); sh.watchdog(NOW + M(15), check_smtp=False); sh.watchdog(NOW + M(30), check_smtp=False); sh.watchdog(NOW + M(600), check_smtp=False)
        ok("the same problem a quarter of an hour later, and ten hours later: no second mail, no second event", not sent and SchedHealthEvent.objects.count() == 1)
        settings.SCHEDULER_HEALTH_REMINDER_HOURS = 6
        sh.watchdog(NOW + M(300), check_smtp=False)
        ok("with a reminder interval of 6 hours a reminder is not sent before 6 hours", not sent)
        sh.watchdog(NOW + M(400), check_smtp=False)
        ok("and is sent after them, once", len(sent) == 1 and "continues" in sent[0]["subject"] and "For" in sent[0]["html"])
        sh.watchdog(NOW + M(410), check_smtp=False)
        ok("not again straight after", len(sent) == 1)
        settings.SCHEDULER_HEALTH_REMINDER_HOURS = 0
        sent.clear()
        hb(last_alive_at=NOW + M(700) - M(1), service_host="SERVER01")
        sh.watchdog(NOW + M(700), check_smtp=False)
        ev = SchedHealthEvent.objects.get()
        ok("when the service is back the event is closed and IT gets one 'back to normal' mail with how long it was down", ev.ended_at == NOW + M(700) and ev.recovery_alerted_at is not None and len(sent) == 1 and "running again" in sent[0]["subject"] and "h" in sent[0]["html"], str(sent))
        sent.clear(); alive(NOW + M(715)); sh.watchdog(NOW + M(715), check_smtp=False)
        ok("and nothing more", not sent)
        hb(last_alive_at=NOW + M(900) - M(40))
        sh.watchdog(NOW + M(900), check_smtp=False)
        ok("a new outage later is a new event and a new mail", SchedHealthEvent.objects.count() == 2 and len(sent) == 1)

        print("E. overdue mail and the mail server")
        SchedHealthEvent.objects.all().delete(); sent.clear()
        hb(last_alive_at=NOW - M(1), started_at=NOW - M(900))
        item("due 4 h ago", 4)
        sh.watchdog(NOW, check_smtp=False)
        ok("overdue mail opens an event and e-mails once", SchedHealthEvent.objects.get().kind == "overdue" and len(sent) == 1 and "overdue" in sent[0]["subject"])
        SchedItem.objects.all().delete(); sent.clear()
        alive(NOW + M(15)); sh.watchdog(NOW + M(15), check_smtp=False)
        ok("when it is sent the event closes quietly (no 'back to normal' mail for this kind)", SchedHealthEvent.objects.get().ended_at is not None and not sent)
        SchedHealthEvent.objects.all().delete(); sent.clear()
        FakeSMTP.mode = "fail"; hb(last_alive_at=NOW - M(1))
        sh.watchdog(NOW, check_smtp=True)
        ok("the first failed mail-server check does not alert", not sent and not SchedHealthEvent.objects.exists())
        down.add("smtp.default.test")
        alive(NOW + M(15)); sh.watchdog(NOW + M(15), check_smtp=True)
        ok("the second opens the event; the alert cannot be sent through the broken account, so it is not marked as sent", SchedHealthEvent.objects.get().kind == "smtp_down" and SchedHealthEvent.objects.get().alerted_at is None and not sent)
        down.discard("smtp.default.test")
        alive(NOW + M(30)); sh.watchdog(NOW + M(30), check_smtp=True)
        ok("and it is tried again at the next run, once the mail goes", SchedHealthEvent.objects.get().alerted_at is not None and len(sent) == 1)
        FakeSMTP.mode = "ok"; sent.clear()
        alive(NOW + M(45)); sh.watchdog(NOW + M(45), check_smtp=True)
        ok("when the mail server is back: the event closes and IT gets one 'can be reached again' mail", SchedHealthEvent.objects.get().ended_at is not None and len(sent) == 1 and "reached again" in sent[0]["subject"])

        print("F. alerts off, and nobody to tell")
        SchedHealthEvent.objects.all().delete(); sent.clear()
        settings.SCHEDULER_HEALTH_ALERTS = False
        hb(last_alive_at=NOW - M(60))
        sh.watchdog(NOW, check_smtp=False)
        ev = SchedHealthEvent.objects.get()
        ok("with alerts off (a development machine) the event is recorded and nobody is e-mailed", ev.alerted_at is None and not sent)
        settings.SCHEDULER_HEALTH_ALERTS = True
        sh.watchdog(NOW + M(15), check_smtp=False)
        ok("when alerts are switched on the open problem is mailed once", SchedHealthEvent.objects.get().alerted_at is not None and len(sent) == 1)
        SchedHealthEvent.objects.all().delete(); sent.clear()
        settings.SCHEDULER_ERROR_MAIL_TO = []
        sh.watchdog(NOW, check_smtp=False)
        ok("with no SCHEDULER_ERROR_MAIL_TO nothing can be sent and nothing breaks", not sent and SchedHealthEvent.objects.count() == 1)
        settings.SCHEDULER_ERROR_MAIL_TO = ["it@example.test"]

        print("G. the command")
        SchedHealthEvent.objects.all().delete(); sent.clear()
        def run(*args):
            out = io.StringIO()
            try:
                call_command("check_scheduler_health", *args, stdout=out)
                code = 0
            except SystemExit as exc:
                code = exc.code
            return code, out.getvalue()
        REAL = datetime.datetime.now().replace(microsecond=0)
        hb(last_alive_at=REAL)
        code, text = run("--no-smtp", "--no-mail")
        ok("healthy: exit code 0", code == 0 and text.startswith("OK"), text[:100])
        SchedItem.objects.create(job_key="birthday", subject_key="old", label="old", send_date=REAL.date(), due_at=REAL - datetime.timedelta(hours=4), status="planned", cr_dt=REAL)
        code, text = run("--no-smtp", "--no-mail")
        ok("a warning: exit code 1", code == 1 and "overdue" in text)
        SchedItem.objects.all().delete()
        # the command uses the real clock: make the heartbeat old for it
        hb(last_alive_at=datetime.datetime.now() - M(30))
        code, text = run("--no-smtp", "--no-mail")
        ok("critical: exit code 2, and --no-mail sends nothing even with alerts on", code == 2 and "not running" in text and not sent and "alert e-mails are off" in text, text[:200])

        print("H. the pages")
        SchedHealthEvent.objects.all().delete()
        full = mk("zzsh1", {"admin.scheduled_mails": ("view", "edit")})
        viewer = mk("zzsh2", {"admin.scheduled_mails": ("view",)})
        nobody = mk("zzsh3", {})
        hb(last_alive_at=datetime.datetime.now() - M(2), started_at=datetime.datetime.now() - M(90))
        r = full.get("/api/admin/scheduler-status/")
        ok("the sidebar status: level and title", r.status_code == 200 and r.json()["level"] == "ok" and "normally" in r.json()["title"], str(r.content[:150]))
        ok("it needs the View right", nobody.get("/api/admin/scheduler-status/").status_code == 403 and viewer.get("/api/admin/scheduler-status/").status_code == 200)
        sm = full.get("/api/admin/scheduled-mails/").json()
        ok("Scheduled Mails carries the health: level, problems, heartbeat, mail-server result and the last outages", sm["health"]["level"] == "ok" and sm["health"]["heartbeat"]["uptime_minutes"] >= 89 and "smtp" in sm["health"] and "problems" in sm["health"] and "health_events" in sm)
        ok("and the older keys the pages already use", sm["health"]["state"] == "running" and "minutes_ago" in sm["health"] and "manual_at" in sm["health"])
        hb(last_alive_at=datetime.datetime.now() - M(30))
        sh.watchdog(check_smtp=False, alerts=False)
        sm = full.get("/api/admin/scheduled-mails/").json()
        ok("an outage shows in the list of the last outages, open", sm["health"]["level"] == "critical" and sm["health_events"] and sm["health_events"][0]["kind"] == "service_down" and sm["health_events"][0]["ended_at"] is None)
        FakeSMTP.mode = "ok"
        SchedHeartbeat.objects.filter(pk=1).update(smtp_checked_at=None)
        r = full.post("/api/admin/scheduler-health/smtp-check/")
        ok("the mail server can be checked from the page (Edit), and the answer is recorded", r.status_code == 200 and r.json()["ok"] is True and SchedHeartbeat.objects.get(pk=1).smtp_ok is True, str(r.content[:150]))
        ok("a second check straight away is refused (429), so the mail server is not hammered", full.post("/api/admin/scheduler-health/smtp-check/").status_code == 429)
        ok("a viewer cannot run the check", viewer.post("/api/admin/scheduler-health/smtp-check/").status_code == 403)
        raise Rollback()
except Rollback:
    pass
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print()
print("FAILED: " + ", ".join(fails) if fails else "all checks passed")
sys.exit(1 if fails else 0)
