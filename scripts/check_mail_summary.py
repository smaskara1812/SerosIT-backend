"""Checks Admin > Mail Controls and the Daily Mail Summary mail: the page's API (App Admin only; the typed phrase for the error recipients; the saved row wins over .env and
"Reset" puts .env back), the error mail using the page's people, the job's planning (today and tomorrow, time changes, switching off, switching on late), the mail's contents
(window since the last summary, mail-type names, failures first, grouped and one-per-mail layouts, the 200-row cap, the redirect note, the summary leaving itself out, a quiet
day), sending through a stubbed mail server (failure, retry, resend, the test button), and the status the page shows. Everything runs in a transaction that is rolled back.

    cd backend
    .venv/bin/python scripts/check_mail_summary.py
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

from core import error_mail, mail_settings, mail_summary, mailer, scheduler
from core.models import EmailLog, MailRedirectSetting, MailSummarySetting, SchedItem, SchedJob, UserProfile
from core.permissions import invalidate_user_access

sent = []
down = set()


def fake_deliver(subject, html, text, to, cc, bcc, from_name, smtp, inline_images, attachments=None):
    if smtp["host"] in down:
        raise ConnectionError(f"{smtp['host']} refused the connection")
    sent.append({"subject": subject, "html": html, "text": text, "to": to, "host": smtp["host"], "from": smtp["from_address"]})


mailer._deliver = fake_deliver
settings.EMAIL_HOST = "smtp.default.test"
settings.SCHEDULER_ERROR_MAIL_TO = ["it@example.test"]
settings.SCHEDULER_MAX_RETRIES = 2
settings.MAIL_SUMMARY, settings.MAIL_SUMMARY_TO, settings.MAIL_SUMMARY_TIME = False, [], "22:00"
settings.MAIL_REDIRECT, settings.MAIL_REDIRECT_TO = False, []

fails = []


def ok(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {detail}" if not cond else ""))
    if not cond:
        fails.append(name)


class Rollback(Exception):
    pass


def mk(n, admin):
    u = get_user_model().objects.create_user(username=n, password="x", is_superuser=False)
    uid = (UserProfile.objects.order_by("-user_id").first().user_id or 0) + 1
    UserProfile.objects.create(user_id=uid, user_login_id=n, is_app_admin=admin)
    invalidate_user_access(n)
    c = APIClient(HTTP_HOST="localhost")
    c.force_authenticate(u)
    return c


DT = datetime.datetime
URL = "/api/admin/mail-summary/"
PH = "CONFIRM ERROR MAIL UPDATE"
DAY = datetime.date(2030, 1, 10)  # far from any real data in the Email Log
NOW = DT(2030, 1, 10, 22, 0, 5)
JOB = mail_summary.JOB


def log_row(code, subject, success=True, when=None, frm="alerts@seros.test", err="", fallback=False):
    row = EmailLog.objects.create(subject=subject, body="", recipients="x@example.test", from_address=frm, trigger_code=code, success=success, error=err, used_fallback=fallback)
    EmailLog.objects.filter(pk=row.pk).update(sent_dt=when or DT(2030, 1, 10, 9, 0, 0))
    return row


def items():
    return list(SchedItem.objects.filter(job_key=mail_summary.JOB_KEY).order_by("send_date"))


try:
    with transaction.atomic():
        MailSummarySetting.objects.all().delete()
        MailRedirectSetting.objects.all().delete()
        mail_settings.clear_cache()
        mailer.clear_redirect_cache()
        adm, usr = mk("zz_sum_admin", True), mk("zz_sum_user", False)

        # ── who may use the page ─────────────────────────────────────────────────────────────────────────────────────────────
        ok("a non-admin is refused (read, save and test)", usr.get(URL).status_code == 403 and usr.put(URL, {"section": "summary"}, format="json").status_code == 403 and usr.post(URL + "test/").status_code == 403)

        # ── .env decides until the page is saved ───────────────────────────────────────────────────────────────────────────
        g = adm.get(URL).json()
        ok("with nothing saved, .env decides: off, 22:00, the error people", g["summary"]["source"] == "env" and not g["summary"]["on"] and g["summary"]["time"] == "22:00" and g["summary"]["recipients"] == ["it@example.test"])
        ok("the error people come from .env with no saved choice", g["error"]["source"] == "env" and g["error"]["to"] == ["it@example.test"] and error_mail.recipients() == ["it@example.test"])

        # ── the error recipients card ──────────────────────────────────────────────────────────────────────────────────────
        ok("changing the error people needs the typed phrase", adm.put(URL, {"section": "error", "to": ["a@example.test"], "confirm": "yes"}, format="json").status_code == 400)
        ok("a bad address is refused", adm.put(URL, {"section": "error", "to": ["nope"], "confirm": PH}, format="json").status_code == 400)
        r = adm.put(URL, {"section": "error", "to": "a@example.test\nb@example.test, a@example.test", "confirm": PH}, format="json")
        ok("saved: duplicates dropped, source is the page, and the error mail uses them", r.status_code == 200 and r.json()["error"]["to"] == ["a@example.test", "b@example.test"] and r.json()["error"]["source"] == "page" and error_mail.recipients() == ["a@example.test", "b@example.test"])
        r = adm.put(URL, {"section": "error", "to": [], "confirm": PH}, format="json")
        ok("an empty list is a choice: nobody is told (not the .env)", r.status_code == 200 and r.json()["error"]["to"] == [] and r.json()["error"]["source"] == "page" and error_mail.recipients() == [])
        r = adm.put(URL, {"section": "error", "to": None, "confirm": PH}, format="json")
        ok("reset puts the .env people back", r.status_code == 200 and r.json()["error"]["source"] == "env" and error_mail.recipients() == ["it@example.test"])
        ok("a part must be named", adm.put(URL, {"to": []}, format="json").status_code == 400)

        # ── the summary card ───────────────────────────────────────────────────────────────────────────────────────────────
        body = {"section": "summary", "on": True, "time": "22:00", "to": [], "same_as_error": True, "send_when_quiet": True, "grouped": True}
        ok("a bad time is refused", adm.put(URL, {**body, "time": "25:00"}, format="json").status_code == 400 and adm.put(URL, {**body, "time": "soon"}, format="json").status_code == 400)
        ok("a bad address is refused", adm.put(URL, {**body, "same_as_error": False, "to": ["nope"]}, format="json").status_code == 400)
        ok("on with no address of its own is refused", adm.put(URL, {**body, "same_as_error": False, "to": []}, format="json").status_code == 400)
        adm.put(URL, {"section": "error", "to": [], "confirm": PH}, format="json")
        ok("on, sent to the error people, with nobody chosen there is refused", adm.put(URL, body, format="json").status_code == 400)
        adm.put(URL, {"section": "error", "to": None, "confirm": PH}, format="json")
        r = adm.put(URL, body, format="json")
        j = r.json()
        ok("saved on: the page now decides and the people are the error people", r.status_code == 200 and j["summary"]["on"] and j["summary"]["source"] == "page" and j["summary"]["recipients"] == ["it@example.test"] and j["summary"]["changed_by"])
        ok("the error people cannot be emptied while the summary goes to them", adm.put(URL, {"section": "error", "to": [], "confirm": PH}, format="json").status_code == 400)
        r = adm.put(URL, {**body, "same_as_error": False, "to": "own@example.test", "time": "21:30", "grouped": False, "send_when_quiet": False}, format="json")
        j = r.json()["summary"]
        ok("its own list, time, layout and quiet-day choice are saved", j["recipients"] == ["own@example.test"] and j["time"] == "21:30" and not j["grouped"] and not j["send_when_quiet"])
        settings.MAIL_SUMMARY = False
        ok("a saved page beats .env", mail_settings.summary_state()["on"])
        adm.put(URL, {**body, "same_as_error": False, "to": "own@example.test", "time": "22:00"}, format="json")

        # ── the job: planning ───────────────────────────────────────────────────────────────────────────────────────────────
        ok("the job is one the scheduler runs, and its schedule says when", mail_summary.JOB_KEY in scheduler.JOBS and "22:00" in JOB.schedule_text(DAY))
        SchedItem.objects.filter(job_key=mail_summary.JOB_KEY).delete()
        p = JOB.plan(DT(2030, 1, 10, 17, 0, 5))
        its = items()
        ok("it plans today and tomorrow at the time", p["planned"] == 2 and [i.send_date for i in its] == [DAY, DAY + datetime.timedelta(days=1)] and all(i.due_at.time() == datetime.time(22, 0) for i in its) and all(i.status == "planned" for i in its))
        adm.put(URL, {**body, "same_as_error": False, "to": "own@example.test", "time": "21:15"}, format="json")
        JOB.plan(DT(2030, 1, 10, 17, 0, 5))
        ok("a changed time moves the planned items", all(i.due_at.time() == datetime.time(21, 15) for i in items()))
        adm.put(URL, {**body, "on": False, "same_as_error": False, "to": "own@example.test"}, format="json")
        c = JOB.plan(DT(2030, 1, 10, 17, 0, 5))
        ok("switching off cancels what was planned", c["cancelled"] == 2 and all(i.status == "cancelled" for i in items()))
        SchedItem.objects.filter(job_key=mail_summary.JOB_KEY).delete()
        adm.put(URL, {**body, "same_as_error": False, "to": "own@example.test", "time": "22:00"}, format="json")
        JOB.plan(DT(2030, 1, 10, 23, 30, 0))
        its = items()
        ok("switched on after today's time: today's is cancelled, the first goes tomorrow", its[0].status == "cancelled" and "tomorrow" in its[0].note and its[1].status == "planned")
        for label, when, expect in (("5 seconds after its time (the scheduler had not run before)", DT(2030, 1, 10, 22, 0, 5), "planned"), ("10 minutes after its time", DT(2030, 1, 10, 22, 10, 0), "planned"), ("40 minutes after its time", DT(2030, 1, 10, 22, 40, 0), "cancelled")):
            SchedItem.objects.filter(job_key=mail_summary.JOB_KEY).delete()
            JOB.plan(when)
            ok(f"first planned {label}: today's item is {expect}", items()[0].status == expect, str(items()[0].status))
        SchedItem.objects.filter(job_key=mail_summary.JOB_KEY).delete()
        JOB.plan(DT(2030, 1, 10, 17, 0, 5))

        # ── the mail's contents ─────────────────────────────────────────────────────────────────────────────────────────────
        old = DT(2030, 1, 9, 21, 0, 0)
        log_row("auto.holiday", "Diwali greetings", when=old)  # before the window: must not appear
        log_row("auto.holiday", "Diwali greetings", when=DT(2030, 1, 10, 8, 0, 0))
        log_row("auto.holiday", "Diwali greetings", when=DT(2030, 1, 10, 8, 0, 1))
        log_row("drilling_report.finalize", "Report 12", when=DT(2030, 1, 10, 10, 30, 0), frm="reports@seros.test")
        log_row("drilling_report.approve", "Report 12 approved", success=False, err="Connection refused\nsecond line", when=DT(2030, 1, 10, 11, 0, 0))
        log_row("auto.birthday.test", "Test birthday", when=DT(2030, 1, 10, 12, 0, 0), fallback=True)
        log_row("", "A mail with no type", when=DT(2030, 1, 10, 13, 0, 0))
        log_row("auto.mail_summary", "[SerosIT] Daily mail summary, 9 Jan", when=DT(2030, 1, 10, 14, 0, 0))  # the summary itself: left out
        for who in ("SOSIL", "SEPL", "SK Drilling", "Axom Rhino"):
            log_row("auto.drilling_info_status", f"Drilling Info Status - {who}", when=DT(2030, 1, 10, 15, 0, 0), frm="alerts@seros.test")
        built = mail_summary.build(DT(2030, 1, 9, 22, 0, 5), NOW, True)
        h = built["html"]
        ok("the headline counts what went out and what failed, leaving the summary itself out", built["total"] == 10 and built["failed"] == 1 and "10 mails" in built["subject"] and "1 failed" in built["subject"])
        ok("mail types have friendly names (automation names, known codes, tests, no code)", all(x in h for x in ("Holiday Mailer", "Drilling report: finalised", "Drilling report: approved", "Birthday Mailer (test)", "A mail with no type")))
        ok("grouped: the holiday mails are one row with a count and a time span", "2 sent" in h and "10 Jan 08:00" in h and "08:00 to" not in h)
        ok("the subject of the mails shows next to the type (the same subject once)", h.count("Diwali greetings") == 1 and "A mail with no type" in h and "Report 12 approved" in h)
        ok("a type with many different subjects shows three and says how many more", h.count("Drilling Info Status - ") == 3 and "and 1 more subject<" in h, str(h.count("Drilling Info Status - ")))
        ok("the sender's address and the fallback account show", "reports@seros.test" in h and "alerts@seros.test" in h)
        ok("a failure comes first, with its first line of reason only", h.index("Drilling report: approved") < h.index("Holiday Mailer") and "Failed: Connection refused" in h and "second line" not in h)
        flat = mail_summary.build(DT(2030, 1, 9, 22, 0, 5), NOW, False)["html"]
        ok("one row per mail: the two holiday mails are two rows, a fallback send says so", flat.count("Holiday Mailer") == 2 and "Sent via the fallback account" in flat)
        ok("one row per mail: each mail shows its own subject, all four company mails", all(f"Drilling Info Status - {w}" in flat for w in ("SOSIL", "SEPL", "SK Drilling", "Axom Rhino")))
        ok("the table has the columns asked for, with the subject next to the type", all(x in h for x in (">Mail type<", ">Subject<", ">Sent from<", ">Sent at<", ">Status<")) and h.index(">Mail type<") < h.index(">Subject<") < h.index(">Sent from<"))
        mailer.clear_redirect_cache()
        settings.MAIL_REDIRECT, settings.MAIL_REDIRECT_TO = True, ["redir@example.test"]
        ok("with mail redirect on, the mail says so", "Mail redirect is ON" in mail_summary.build(DT(2030, 1, 9, 22, 0, 5), NOW, True)["html"])
        settings.MAIL_REDIRECT, settings.MAIL_REDIRECT_TO = False, []
        mailer.clear_redirect_cache()
        quiet = mail_summary.build(DT(2031, 1, 1, 0, 0, 0), DT(2031, 1, 2, 0, 0, 0), True)
        ok("a day with nothing says so", quiet["total"] == 0 and "no mail sent" in quiet["subject"] and "No mail was sent" in quiet["html"])
        ok("the type names work on their own", mail_summary.mail_type("auto.holiday.test", "") == "Holiday Mailer (test)" and mail_summary.mail_type("foo.bar_baz", "") == "Foo: bar baz" and mail_summary.mail_type("", "A long subject line") == "A long subject line")

        ok("a first summary looks back 24 hours", mail_summary.window_for(None, NOW) == (NOW - datetime.timedelta(hours=24), NOW))

        # ── sending it ───────────────────────────────────────────────────────────────────────────────────────────────────────
        sent.clear()
        JOB.plan(DT(2030, 1, 10, 17, 0, 5))
        res = JOB.process(NOW)
        it = items()[0]
        ok("at the time, the hourly run sends it to the chosen person through the default account", res["sent"] == 1 and len(sent) == 1 and sent[0]["to"] == ["own@example.test"] and sent[0]["host"] == "smtp.default.test" and it.status == "sent" and it.sent_at)
        ok("its subject has the date and counts, and the summary mail is logged as its own type", "10 Jan 2030" in sent[0]["subject"] and EmailLog.objects.filter(trigger_code=mail_summary.TRIGGER_CODE).count() >= 1)
        sent.clear()
        log_row("auto.holiday", "Later one", when=DT(2030, 1, 10, 22, 30, 0))
        start, end = mail_summary.window_for(None, DT(2030, 1, 11, 22, 0, 5))
        ok("the next summary starts where the last one stopped", start == it.sent_at and end == DT(2030, 1, 11, 22, 0, 5))
        rs = JOB.resend(it, NOW)
        ok("sent again covers the same period and counts the resend", rs == (True, "") and len(sent) == 1 and SchedItem.objects.get(pk=it.pk).resend_count == 1 and "10 mails" in sent[0]["subject"])

        # a failure, then a retry at the next run, then the error mail after the last try
        sent.clear()
        SchedItem.objects.filter(job_key=mail_summary.JOB_KEY).delete()
        down.add("smtp.default.test")
        JOB.plan(DT(2030, 1, 12, 17, 0, 5))
        n12 = DT(2030, 1, 12, 22, 0, 5)
        JOB.process(n12)
        it = items()[0]
        ok("a failed send is recorded with its reason", it.status == "failed" and "refused" in it.last_error and it.attempts == 1)
        down.clear()
        JOB.process(DT(2030, 1, 12, 23, 0, 5))
        it = items()[0]
        ok("the next hourly run retries it and it goes", it.status == "sent" and it.attempts == 2 and any("Daily mail summary" in m["subject"] for m in sent))

        # a quiet day
        sent.clear()
        SchedItem.objects.filter(job_key=mail_summary.JOB_KEY).delete()
        adm.put(URL, {**body, "same_as_error": False, "to": "own@example.test", "send_when_quiet": False}, format="json")
        JOB.plan(DT(2036, 3, 1, 17, 0, 5))
        JOB.process(DT(2036, 3, 1, 22, 0, 5))
        it = items()[0]
        ok("a quiet day with 'send when quiet' off sends nothing and the item says why", not sent and it.status == "cancelled" and "No mail was sent" in it.note)
        adm.put(URL, {**body, "same_as_error": False, "to": "own@example.test", "send_when_quiet": True}, format="json")
        SchedItem.objects.filter(job_key=mail_summary.JOB_KEY).delete()
        JOB.plan(DT(2036, 3, 1, 17, 0, 5))
        JOB.process(DT(2036, 3, 1, 22, 0, 5))
        ok("with it on, a quiet day still sends a short message", len(sent) == 1 and "no mail sent" in sent[0]["subject"])

        # one row per mail is capped at 200
        for i in range(205):
            log_row("auto.holiday", f"Mass {i}", when=DT(2037, 5, 1, 8, 0, 0) + datetime.timedelta(seconds=i))
        big = mail_summary.build(DT(2037, 5, 1, 0, 0, 0), DT(2037, 5, 2, 0, 0, 0), False)
        ok("the one-per-mail layout stops at 200 rows and says how many there were", big["total"] == 205 and big["html"].count("Holiday Mailer") == 200 and "first 200 of 205" in big["html"])

        # ── the test button and the page's status ─────────────────────────────────────────────────────────────────────────────
        sent.clear()
        n_items = SchedItem.objects.filter(job_key=mail_summary.JOB_KEY).count()
        r = adm.post(URL + "test/")
        ok("the test button sends to the chosen person, marked [Test], and adds no item", r.status_code == 200 and sent and sent[0]["subject"].startswith("[Test]") and sent[0]["to"] == ["own@example.test"] and SchedItem.objects.filter(job_key=mail_summary.JOB_KEY).count() == n_items)
        ok("the test mail is logged as a test type, so the real summary leaves it out", EmailLog.objects.filter(trigger_code="auto.mail_summary.test").exists())
        down.add("smtp.default.test")
        ok("a test that cannot be sent says so", adm.post(URL + "test/").status_code == 502)
        down.clear()
        adm.put(URL, {**body, "same_as_error": False, "to": "own@example.test"}, format="json")
        st = adm.get(URL).json()["status"]
        ok("the page's status has the last summary and the next one", st["last"] and st["last"]["status"] in ("sent", "failed") and "paused" in st and "next_at" in st)
        SchedJob.objects.update_or_create(job_key=mail_summary.JOB_KEY, defaults={"name": "Daily Mail Summary", "enabled": "N"})
        ok("a paused automation shows as paused", adm.get(URL).json()["status"]["paused"])
        raise Rollback
except Rollback:
    pass
mail_settings.clear_cache()
mailer.clear_redirect_cache()
print("\nFAILED: " + ", ".join(fails) if fails else "\nall checks passed")
sys.exit(1 if fails else 0)
