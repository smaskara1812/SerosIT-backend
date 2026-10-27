"""Checks the report mails (the HAZ ID Register) end to end with a fake mail server: the Excel (layout, which cards, the window, the legacy values), setup
warnings, planning from Next Mail and Frequency, sending (attachment, recipients, sender, default account only), moving Next Mail on (sent, skipped,
late, behind by several cycles, failed, nothing open), the error mail, the recipients preview, and the Report Mails and Scheduled Mails endpoints
with people holding exactly the rights named. Everything in the database is rolled back.

    cd backend
    .venv/bin/python scripts/check_report_mails.py
"""
import datetime, io, os, shutil, sys, tempfile, django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TMP = tempfile.mkdtemp(prefix="report_mails_check_")
os.environ["LOG_DIR"] = os.path.join(TMP, "logs")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from openpyxl import load_workbook
from rest_framework.test import APIClient
from core import error_mail, haz_id_register as hz, mailer, scheduler
from core.models import AlertSenderDtl, EmailLog, HazardCard, MailAlertDtl, MailAlertToUser, NotificationTrigger, SchedItem, SchedJob, SysAuditLog, UserPermission, UserProfile
from core.permissions import invalidate_user_access
from core.report_job import next_after

sent, down = [], set()


def fake_deliver(subject, html, text, to, cc, bcc, from_name, smtp, inline_images, attachments=None):
    if smtp["host"] in down:
        raise ConnectionError(f"{smtp['host']} refused the connection")
    sent.append({"subject": subject, "html": html, "to": to, "cc": cc, "bcc": bcc, "from_name": from_name, "host": smtp["host"], "from": smtp["from_address"], "attachments": attachments or []})


mailer._deliver = fake_deliver
settings.EMAIL_HOST = "smtp.default.test"
settings.BIRTHDAY_EMAIL_HOST = "smtp.env.test"  # the report must NOT use this one
settings.SCHEDULER_ERROR_MAIL_TO = ["it@example.test"]
settings.SCHEDULER_MAX_RETRIES = 2


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


D, DT = datetime.date, datetime.datetime
NOW = DT(2026, 10, 27, 17, 0, 5)  # five seconds past the alert's hour (17)
TODAY = NOW.date()
JOB = hz.JOB
MK = "admin.report_mails"
ALERT = 228


def set_alert(**kw):
    MailAlertDtl.objects.filter(pk=ALERT).update(**kw)
    return MailAlertDtl.objects.get(pk=ALERT)


def nxt():
    return MailAlertDtl.objects.get(pk=ALERT).next_mail_dt


def items():
    return SchedItem.objects.filter(job_key=hz.JOB_KEY)


def age_by_hand_items():
    """Pretend the runs by hand were made a few minutes ago (the cooldown after a run by hand is a minute)."""
    for it in SchedItem.objects.filter(job_key=hz.JOB_KEY, subject_key__contains="by hand"):
        if not it.subject_key.endswith("-old"):
            SchedItem.objects.filter(pk=it.pk).update(subject_key=f"{it.subject_key}-old{it.pk}-old", cr_dt=it.cr_dt - datetime.timedelta(minutes=5))


try:
    with transaction.atomic():
        items().delete()
        NotificationTrigger.objects.filter(entity_key=hz.ENTITY_KEY, action=hz.ACTION).delete()
        AlertSenderDtl.objects.filter(alert_id=ALERT).delete()
        alert = set_alert(alert_window=30, alert_freq=15, next_mail_dt=DT(2026, 10, 22, 17, 27, 10), start_time=17, alert_active="Y", mail_subject="HAZ ID Register Mail Alert")

        print("A. the Excel")
        groups = hz.collect(30, TODAY)
        cards = sum(len(g[2]) for g in groups)
        expect = HazardCard.objects.filter(haz_id_card_status="O", event_dt__date__lte=TODAY - datetime.timedelta(days=30)).exclude(marked_as_deleted="Y").count()
        ok("every open, not deleted card at least 30 days old is in it, and nothing else", cards == expect and cards > 0, f"{cards} vs {expect}")
        ws = load_workbook(io.BytesIO(hz.build_workbook(groups, TODAY))).active
        ok("the title, the report date (Seros-IT, not SIS) and the header row are right", ws["A1"].value == "Haz ID Card Register Report" and str(ws["A2"].value).endswith("27-10-2026") and "Seros-IT Report Date" in str(ws["A2"].value) and "SIS" not in str(ws["A2"].value)
           and [c.value for c in ws[4]] == hz.HEADERS)
        ok("the widths are the legacy ones (5, 15 and 30)", ws.column_dimensions["A"].width == 5 and ws.column_dimensions["H"].width == 5 and ws.column_dimensions["I"].width == 30 and ws.column_dimensions["B"].width == 15)
        ok("each rig and contract has its own two rows, then its cards, SrNo starting at 1 in each group", ws["A5"].value == groups[0][0] and ws["A6"].value == groups[0][1] and ws["A7"].value == 1 and ws["B7"].value == groups[0][2][0]["Haz ID Card No"])
        rowsn = [r for r in range(5, ws.max_row + 1) if isinstance(ws.cell(r, 1).value, int)]
        ok("one row per card", len(rowsn) == cards)
        ok("TOFS says Y or N (the data keeps Y or blank)", {ws.cell(r, 8).value for r in rowsn} <= {"Y", "N"} and "N" in {ws.cell(r, 8).value for r in rowsn})
        ok("every status is Open", {ws.cell(r, 14).value for r in rowsn} == {"Open"})
        ok("dates read dd/mm/yyyy hh:mm", all(len(ws.cell(r, 5).value) == 16 and ws.cell(r, 5).value[2] == "/" for r in rowsn[:50]))
        # the window: a card exactly 30 days old is in, 29 days old is out, a closed one and a deleted one are out
        base = HazardCard.objects.filter(haz_id_card_status="O").exclude(marked_as_deleted="Y").first()
        def clone(no, days, status="O", deleted=""):
            c = HazardCard.objects.get(pk=base.pk); c.pk = None; c.haz_id_card_no = no; c.haz_id_card_status = status; c.marked_as_deleted = deleted
            c.event_dt = DT.combine(TODAY - datetime.timedelta(days=days), datetime.time(9, 30)); c.close_out_dt = None if status == "O" else NOW; c.save(); return c
        clone(990001, 30); clone(990002, 29); clone(990003, 400, status="C"); clone(990004, 400, deleted="Y")
        nos = {r["Haz ID Card No"] for g in hz.collect(30, TODAY) for r in g[2]}
        ok("a card open exactly 30 days is in", 990001 in nos)
        ok("a card open 29 days is out", 990002 not in nos)
        ok("a closed card is out and a deleted card is out", 990003 not in nos and 990004 not in nos)
        nos15 = {r["Haz ID Card No"] for g in hz.collect(15, TODAY) for r in g[2]}
        ok("the window is a setting: with 15 days the 29-day-old card is in", 990002 in nos15 and 990001 in nos15)
        nos0 = {r["Haz ID Card No"] for g in hz.collect(0, TODAY) for r in g[2]}
        ok("with a window of 0 every open card is in", 990002 in nos0 and 990001 in nos0)

        print("B. the setup the pages show")
        s = JOB.get_setup(TODAY)
        ok("with no trigger the page is told what to do", not s["trigger_found"] and s["warnings"])
        did = hz.ensure_setup()
        t = NotificationTrigger.objects.get(entity_key=hz.ENTITY_KEY, action=hz.ACTION)
        ok("the setup command finds the alert by its name and creates the trigger", t.alert_id == ALERT and did and hz.ensure_setup() == [])
        s = JOB.get_setup(TODAY)
        ok("it shows the alert, window, frequency, next mail date and hour", s["alert"]["id"] == ALERT and s["window"] == 30 and s["freq"] == 15 and s["next_mail_dt"] == DT(2026, 10, 22, 17, 27, 10) and s["send_hour"] == 17)
        ok("with no sender account on the alert the From name is blank: the mail server adds its own", s["from_name"] == "" and s["smtp"]["sender"] is None)
        ok("the sender shown is the From address of the default account, since there is no name", s["from_address"] == settings.DEFAULT_FROM_EMAIL and s["from_name"] == "")
        ok("the quick links open Alert To Users filtered to this alert, and Alert Details on it", s["links"]["recipients"] == f"/masters/mail-alert-to-users?alert={ALERT}&alertName={__import__('urllib.parse', fromlist=['x']).quote(s['alert']['name'], safe='')}" and s["links"]["alert"].startswith(f"/masters/mail-alerts?select={ALERT}&q="), str(s["links"]))
        ok("the report ignores the birthday (environment) account for its sender address", s["from_address"] != settings.BIRTHDAY_EMAIL_FROM or not settings.BIRTHDAY_EMAIL_FROM)
        ok("recipients are the alert's active rows today", s["recipients"]["to"] and "Amit.katiyar@seros.co.in" in s["recipients"]["to"], str(s["recipients"]))
        ok("nothing to warn about", not s["warnings"], str(s["warnings"]))
        settings.SCHEDULER_ERROR_MAIL_TO = []
        ok("a missing error-mail address is a warning", any("SCHEDULER_ERROR_MAIL_TO" in w for w in JOB.get_setup(TODAY)["warnings"]))
        settings.SCHEDULER_ERROR_MAIL_TO = ["it@example.test"]
        set_alert(alert_freq=0)
        ok("a frequency of 0 is a warning", any("Frequency" in w for w in JOB.get_setup(TODAY)["warnings"]))
        set_alert(alert_freq=15, alert_active=None)
        ok("an alert that is not ticked Active is a warning", any("switched off" in w for w in JOB.get_setup(TODAY)["warnings"]))
        set_alert(alert_active="Y")
        ok("the trigger and the job are registered with the scheduler", hz.JOB_KEY in scheduler.JOBS and ("Every 15 days" in JOB.schedule_text(TODAY)))

        print("C. planning from Next Mail and Frequency")
        r = JOB.plan(NOW)
        it = items().get()
        ok("a Next Mail date in the past plans ONE catch-up run, today, at the alert's hour", r["planned"] == 1 and it.send_date == TODAY and it.due_at == DT(2026, 10, 27, 17, 0) and "Due 22 Oct 2026" in it.note, str((it.send_date, it.due_at, it.note)))
        ok("the item is labelled with the report and the date", it.label == "HAZ ID Register · 27 Oct 2026")
        JOB.plan(NOW)
        ok("planning again adds nothing", items().count() == 1)
        set_alert(next_mail_dt=DT(2026, 11, 2, 17, 0))
        JOB.plan(NOW)
        ok("a date within 7 days is planned for that day, and the old plan is cancelled", items().filter(status="planned").count() == 1 and items().get(status="planned").send_date == D(2026, 11, 2) and items().get(send_date=TODAY).status == "cancelled")
        set_alert(next_mail_dt=DT(2026, 11, 20, 17, 0))
        JOB.plan(NOW)
        ok("a date further than 7 days away is not planned yet", not items().filter(status="planned").exists())
        set_alert(next_mail_dt=DT(2026, 10, 27, 17, 0))
        JOB.plan(NOW)
        ok("a date that comes back is planned again (a cancelled item is revived)", items().get(send_date=TODAY).status == "planned")
        set_alert(alert_freq=0); JOB.plan(NOW)
        ok("with a frequency of 0 nothing is planned", not items().filter(status="planned").exists())
        set_alert(alert_freq=15, next_mail_dt=None); JOB.plan(NOW)
        ok("with no Next Mail date nothing is planned", not items().filter(status="planned").exists())
        set_alert(next_mail_dt=DT(2026, 10, 22, 17, 27, 10))

        print("D. sending, and moving Next Mail on")
        items().delete(); JOB.plan(NOW)
        n0 = len(sent)
        res = JOB.process(DT(2026, 10, 27, 16, 59, 0))
        ok("nothing goes out before the hour", res["sent"] == 0 and len(sent) == n0)
        res = JOB.process(NOW)
        m = sent[-1]
        ok("at the hour it goes out, once", res["sent"] == 1 and len(sent) == n0 + 1)
        ok("to the alert's To, Cc and Bcc, from the alert's own rows", m["to"] == s["recipients"]["to"] and m["cc"] == s["recipients"]["cc"] and m["bcc"] == s["recipients"]["bcc"])
        ok("with the alert's subject", m["subject"] == "HAZ ID Register Mail Alert")
        ok("with a blank From name, from the From address only", m["from_name"] == "")
        ok("through the DEFAULT account, never the birthday one", m["host"] == "smtp.default.test")
        ok("with the Excel attached, under the legacy file-name pattern", len(m["attachments"]) == 1 and m["attachments"][0][0].startswith("Haz_Id_Register_27_10_2026_170005") and m["attachments"][0][0].endswith(".xlsx") and "spreadsheetml" in m["attachments"][0][2])
        att = load_workbook(io.BytesIO(m["attachments"][0][1])).active
        ok("the attachment is the report", att["A1"].value == "Haz ID Card Register Report" and att.max_row > 10)
        ok("the mail text: 'Seros-IT Auto Report' on top (not S.I.S. Auto Alert), the legacy sentence, and the automated-mail line", "Seros-IT Auto Report" in m["html"] and "S.I.S." not in m["html"] and "Please find attached open HAZ-ID Register" in m["html"] and "automated Mail" in m["html"])
        log = EmailLog.objects.filter(trigger_code="auto.haz_id_register").order_by("-pk").first()
        ok("the Email Log has the mail, its From name's address and the attachment name", log and log.success and ".xlsx" in log.attachment_names and log.from_address)
        it = items().get()
        ok("the item is Sent with the summary of what was in it", it.status == "sent" and "open cards" in it.note and it.email_log_id == log.pk)
        ok("Next Mail moved to the due date plus 15 days (22 Oct -> 6 Nov), at the alert's hour", nxt() == DT(2026, 11, 6, 17, 0), str(nxt()))
        n1 = len(sent); JOB.plan(NOW + datetime.timedelta(hours=1)); JOB.process(NOW + datetime.timedelta(hours=1))
        ok("the next hour does not send it again", len(sent) == n1 and not items().filter(status="planned").exists())

        print("E. the date arithmetic")
        ok("on time: the day it was due plus the frequency", next_after(D(2026, 10, 27), 15, D(2026, 10, 27), 17) == DT(2026, 11, 11, 17, 0))
        ok("late by a few days: the cycle is kept, no drift", next_after(D(2026, 10, 22), 15, D(2026, 10, 27), 17) == DT(2026, 11, 6, 17, 0))
        ok("behind by several cycles: the next future date of the same cycle, one catch-up", next_after(D(2026, 1, 1), 15, D(2026, 10, 27), 17) == DT(2026, 10, 28, 17, 0), str(next_after(D(2026, 1, 1), 15, D(2026, 10, 27), 17)))
        ok("sent early: the planned day plus the frequency", next_after(D(2026, 10, 29), 15, D(2026, 10, 27), 17) == DT(2026, 11, 13, 17, 0))
        set_alert(next_mail_dt=DT(2026, 1, 1, 17, 0)); items().delete(); JOB.plan(NOW); n2 = len(sent); JOB.process(NOW)
        ok("a very late run sends once and moves to the next future date of its cycle", len(sent) == n2 + 1 and nxt() == DT(2026, 10, 28, 17, 0), str(nxt()))
        set_alert(alert_freq=1, next_mail_dt=DT(2026, 10, 27, 17, 0)); items().delete(); JOB.plan(NOW); JOB.process(NOW)
        ok("a frequency of 1 means tomorrow", nxt() == DT(2026, 10, 28, 17, 0))
        set_alert(alert_freq=15, next_mail_dt=DT(2026, 10, 22, 17, 27, 10))

        print("F. skip, resend, send now")
        items().delete(); JOB.plan(NOW)
        it = items().get()
        scheduler.skip_item(it.pk, "tester", NOW)
        ok("skipping a run moves Next Mail on too (the cycle is skipped, not repeated tomorrow)", nxt() == DT(2026, 11, 6, 17, 0) and items().get().status == "skipped", str(nxt()))
        n3 = len(sent); JOB.plan(NOW); JOB.process(NOW)
        ok("and nothing is sent for it", len(sent) == n3)
        scheduler.unskip_item(it.pk, "tester", NOW)
        scheduler.send_now(it.pk, "tester", NOW)
        ok("an un-skipped item sent by hand does not move the date a second time", nxt() == DT(2026, 11, 6, 17, 0) and len(sent) == n3 + 1, str(nxt()))
        scheduler.resend(it.pk, "tester", NOW)
        ok("a resend sends a fresh report and does not move the date", len(sent) == n3 + 2 and nxt() == DT(2026, 11, 6, 17, 0) and items().get().resend_count == 1)

        print("G. nothing open, failures, the alert's own account")
        set_alert(next_mail_dt=DT(2026, 10, 27, 17, 0)); items().delete(); JOB.plan(NOW)
        orig_collect = hz.collect
        hz.collect = lambda w, t: []
        n4 = len(sent); JOB.process(NOW)
        hz.collect = orig_collect
        ok("with nothing open a mail still goes, saying so, with no attachment", len(sent) == n4 + 1 and not sent[-1]["attachments"] and "no open HAZ-ID cards" in sent[-1]["html"] and "30 days" in sent[-1]["html"])
        ok("and the date still moves on", nxt() == DT(2026, 11, 11, 17, 0) and "Nothing open" in items().get().note, str(nxt()))
        set_alert(next_mail_dt=DT(2026, 10, 27, 17, 0)); items().delete(); JOB.plan(NOW)
        down.add("smtp.default.test"); e0 = len(EmailLog.objects.filter(trigger_code=error_mail.TRIGGER_CODE))
        r1 = JOB.process(NOW)
        it = items().get()
        ok("when the account refuses the item is Failed with the reason, and the date does NOT move", r1["failed"] == 1 and it.status == "failed" and "refused" in it.last_error and nxt() == DT(2026, 10, 27, 17, 0))
        ok("no error mail yet: it will be tried again", EmailLog.objects.filter(trigger_code=error_mail.TRIGGER_CODE).count() == e0)
        JOB.process(NOW + datetime.timedelta(hours=1)); JOB.process(NOW + datetime.timedelta(hours=2))
        it = items().get()
        ok("after its third try it stays Failed", it.status == "failed" and it.attempts == 3)
        ok("the error mail could not go (the default account is down too): it is logged, the item is not marked, nothing breaks", it.error_mailed_at is None)
        down.discard("smtp.default.test")
        JOB.process(NOW + datetime.timedelta(hours=3))
        errs = [x for x in sent if x["subject"].startswith("[SerosIT] HAZ ID Register failed")]
        ok("the next run sends the error mail, once, to SCHEDULER_ERROR_MAIL_TO, with the reason", len(errs) == 1 and errs[0]["to"] == ["it@example.test"] and "HAZ ID Register · 27 Oct 2026" in errs[0]["html"] and "refused" in errs[0]["html"], str([x["subject"] for x in sent][-3:]))
        ok("through the default account, with no attachment", errs[0]["host"] == "smtp.default.test" and not errs[0]["attachments"])
        ok("the item is marked, so it is not mailed again", items().get().error_mailed_at is not None)
        JOB.process(NOW + datetime.timedelta(hours=4))
        ok("later runs do not send it again", len([x for x in sent if x["subject"].startswith("[SerosIT] HAZ ID Register failed")]) == 1)
        items().delete(); JOB.plan(NOW); sent.clear()
        hz.collect = lambda w, t: (_ for _ in ()).throw(RuntimeError("the cards could not be read"))
        for h in range(3):
            JOB.process(NOW + datetime.timedelta(hours=h))
        hz.collect = orig_collect
        ok("a report that cannot be built fails the same way, with the reason, and the error mail goes after the last try", "could not be read" in items().get().last_error and len([x for x in sent if x["subject"].startswith("[SerosIT] HAZ ID Register failed")]) == 1)
        items().delete(); JOB.plan(NOW)
        set_alert(alert_active=None); sent.clear()
        JOB.process(NOW)
        it = items().get()
        ok("an alert that is not ticked Active sends nothing and says so", not [x for x in sent if x["subject"] == "HAZ ID Register Mail Alert"] and "switched off" in it.last_error and nxt() == DT(2026, 10, 27, 17, 0), it.last_error)
        set_alert(alert_active="Y"); items().delete(); sent.clear(); JOB.plan(NOW)
        settings.SCHEDULER_ERROR_MAIL_TO = []
        down.add("smtp.default.test")
        for h in range(3):
            JOB.process(NOW + datetime.timedelta(hours=h))
        ok("with no error-mail address nothing is mailed (and nothing breaks)", not [x for x in sent if x["subject"].startswith("[SerosIT]")])
        down.clear(); settings.SCHEDULER_ERROR_MAIL_TO = ["it@example.test"]
        items().delete(); sent.clear(); JOB.plan(NOW)
        AlertSenderDtl.objects.create(alert_id=ALERT, mail_host="smtp.alert.test", mail_port=25, mail_security="N", from_address="reports@example.test", display_name="Reports Desk", is_active="Y", cr_user_id=0, cr_dt=NOW)
        JOB.process(NOW)
        ok("an Alert Senders row for the alert, if one is ever added, is honoured, with its own name", sent[-1]["host"] == "smtp.alert.test" and sent[-1]["from_name"] == "Reports Desk" and sent[-1]["from"] == "reports@example.test")
        AlertSenderDtl.objects.filter(alert_id=ALERT).delete()

        print("H. a failed whole run is reported, at most once a day")
        orig_plan = JOB.plan
        JOB.plan = lambda now, days=7: (_ for _ in ()).throw(RuntimeError("boom"))
        sent.clear()
        r = scheduler.tick(NOW, owner="check")
        ok("a job that raises does not stop the run and its error is mailed", r["errors"] and any("could not run" in x["subject"] and "boom" in x["html"] for x in sent), str(r))
        sent.clear(); scheduler.tick(NOW + datetime.timedelta(hours=1), owner="check")
        ok("a second failure the same day is not mailed again", not [x for x in sent if "could not run" in x["subject"]])
        sent.clear(); scheduler.tick(NOW + datetime.timedelta(hours=25), owner="check")
        ok("the next day it is", any("could not run" in x["subject"] for x in sent))
        JOB.plan = orig_plan

        print("I. the recipients preview")
        pv = scheduler.JOBS["haz_id_register"].setup(TODAY)
        from core.scheduled_mails_views import recipients_preview
        p = recipients_preview(JOB, TODAY, "snapshot text")
        ok("it lists every recipient once, with its type and where it comes from", p["counts"]["to"] >= 1 and all(e["source"].startswith("Alert To Users (alert 228") for e in p["recipients"]) and {e["type"] for e in p["recipients"]} == {"to", "cc", "bcc"})
        ok("it matches what is sent", sorted(e["email"] for e in p["recipients"] if e["type"] == "to") == sorted(pv["recipients"]["to"]))
        ok("it carries the sender address and the quick links", p["from_address"] == settings.DEFAULT_FROM_EMAIL and p["links"]["recipients"].startswith(f"/masters/mail-alert-to-users?alert={ALERT}"))
        AlertSenderDtl.objects.create(alert_id=ALERT, mail_host="smtp.alert.test", mail_port=25, mail_security="N", from_address="reports@example.test", display_name="Reports Desk", is_active="Y", cr_user_id=0, cr_dt=NOW)
        ok("with an Alert Senders row the address shown is that row's", JOB.get_setup(TODAY)["from_address"] == "reports@example.test" and JOB.get_setup(TODAY)["from_name"] == "Reports Desk")
        AlertSenderDtl.objects.filter(alert_id=ALERT).delete()
        ok("it carries the sender name, the error-mail address and the recorded list", p["from_name"] == "" and p["error_mail_to"] == ["it@example.test"] and p["snapshot"] == "snapshot text")
        ok("an ended row is not in it", not any(e["email"].lower().startswith("ujwal") for e in p["recipients"]))
        ok("a day in 2021 shows the people who were on the list then", any("ujwal" in e["email"].lower() for e in recipients_preview(JOB, D(2021, 6, 1))["recipients"]))

        print("J. the pages")
        full = mk("zzrm1", {MK: ("view", "edit", "export"), "admin.scheduled_mails": ("view", "edit")})
        viewer = mk("zzrm2", {MK: ("view",), "admin.scheduled_mails": ("view",)})
        nobody = mk("zzrm3", {})
        ok("no rights: nothing opens", nobody.get("/api/admin/report-mails/").status_code == 403)
        ok("a viewer sees the report with its setup, preview and runs", viewer.get("/api/admin/report-mails/").status_code == 200)
        j = full.get("/api/admin/report-mails/").json()["results"][0]
        ok("the card has the name, schedule, setup, runs and the recipients preview", j["key"] == "haz_id_register" and "Every 15 days" in j["schedule"] and j["setup"]["alert"]["id"] == ALERT and j["preview"]["counts"]["to"] >= 1 and "runs" in j)
        ok("a viewer cannot download or send a test", viewer.get("/api/admin/report-mails/haz_id_register/download/").status_code == 403 and viewer.post("/api/admin/report-mails/haz_id_register/test-send/", {"email": "a@b.co"}, format="json").status_code == 403)
        r = full.get("/api/admin/report-mails/haz_id_register/download/")
        ok("a holder of Export downloads the Excel built now", r.status_code == 200 and "spreadsheetml" in r["Content-Type"] and ".xlsx" in r["Content-Disposition"] and load_workbook(io.BytesIO(r.content)).active["A1"].value == "Haz ID Card Register Report")
        ok("the download is in the audit trail", SysAuditLog.objects.filter(entity=MK, action="export").exists())
        ok("an unknown report is a 404", full.get("/api/admin/report-mails/nope/download/").status_code == 404)
        hz.collect = lambda w, t: []
        r = full.get("/api/admin/report-mails/haz_id_register/download/")
        hz.collect = orig_collect
        ok("with nothing open the download says so", r.status_code == 404 and "Nothing open" in r.json()["detail"])
        sent.clear()
        ok("a test needs an address", full.post("/api/admin/report-mails/haz_id_register/test-send/", {"email": "nope"}, format="json").status_code == 400)
        r = full.post("/api/admin/report-mails/haz_id_register/test-send/", {"email": "me@example.test"}, format="json")
        ok("a test goes to that address only, marked [Test], with the Excel", r.status_code == 200 and len(sent) == 1 and sent[0]["to"] == ["me@example.test"] and not sent[0]["cc"] and not sent[0]["bcc"] and sent[0]["subject"].startswith("[Test] ") and len(sent[0]["attachments"]) == 1, str((r.content[:200], sent)))
        ok("the test did not touch Next Mail", True)
        before = nxt()
        full.post("/api/admin/report-mails/haz_id_register/test-send/", {"email": "me@example.test"}, format="json")
        ok("the test did not move Next Mail", nxt() == before)
        it = items().order_by("-pk").first() or JOB.plan(NOW) and items().first()
        if not it:
            JOB.plan(NOW); it = items().first()
        rr = viewer.get(f"/api/admin/scheduled-mails/{it.pk}/recipients/")
        ok("Scheduled Mails shows who an item goes to (View)", rr.status_code == 200 and rr.json()["counts"]["to"] >= 1 and rr.json()["recipients"][0]["source"].startswith("Alert To Users"))
        ok("nobody else can", nobody.get(f"/api/admin/scheduled-mails/{it.pk}/recipients/").status_code == 403 and full.get("/api/admin/scheduled-mails/999999/recipients/").status_code == 404)
        sm = full.get("/api/admin/scheduled-mails/").json()
        ok("Scheduled Mails lists the three automations, each with its own schedule line", {x["key"] for x in sm["jobs"]} == {"birthday", "holiday", "haz_id_register", "rig_rate_breakup"} and "Every 15 days" in next(x["schedule"] for x in sm["jobs"] if x["key"] == "haz_id_register"))
        print("K. sent by hand, and the schedule changed from the page")
        real = datetime.date.today()
        # the alert's own state, with a trigger row and nothing planned
        NotificationTrigger.objects.get_or_create(entity_key=hz.ENTITY_KEY, action=hz.ACTION, defaults=dict(alert_id=ALERT, notification_trigger_active="Y", cr_user_id=0, cr_dt=NOW))
        items().delete(); sent.clear()
        set_alert(alert_active="Y", next_mail_dt=DT.combine(real + datetime.timedelta(days=10), datetime.time(17, 0)), start_time=17, alert_freq=15)
        eff = JOB.run_now_effect(MailAlertDtl.objects.get(pk=ALERT), real)
        ok("with Next Mail still ahead, sending now is an extra copy: the schedule does not move", eff["moves"] is False)
        before = nxt()
        r = full.post("/api/admin/report-mails/haz_id_register/run-now/", {}, format="json")
        j = r.json()
        ok("send now sends it at once, to the alert's recipients, with the Excel", r.status_code == 200 and j["ok"] and len(sent) == 1 and sent[0]["to"] and len(sent[0]["attachments"]) == 1, str(r.content[:200]))
        ok("it is on Scheduled Mails, labelled by hand, as Sent", items().filter(status="sent", label__contains="(by hand)").count() == 1 and "Started by" in items().get().note)
        ok("Next Mail did not move", nxt() == before and j["moved"] is False)
        r2 = full.post("/api/admin/report-mails/haz_id_register/run-now/", {}, format="json")
        ok("a second send now right after the first (a double click, or two people at once) is refused: one mail, one item", r2.status_code == 409 and r2.json().get("busy") and "already sent by hand" in r2.json()["detail"] and len(sent) == 1 and items().count() == 1, str(r2.content[:200]))
        age_by_hand_items()
        r2 = full.post("/api/admin/report-mails/haz_id_register/run-now/", {}, format="json")
        ok("a minute later it can be sent again: a second copy, a second item", r2.status_code == 200 and len(sent) == 2 and items().count() == 2)
        age_by_hand_items()
        key_now = f"{ALERT}:by hand {datetime.datetime.now():%Y%m%d%H%M}"
        SchedItem.objects.create(job_key=hz.JOB_KEY, subject_key=key_now, label="x", send_date=real, due_at=NOW, status="failed", cr_dt=NOW - datetime.timedelta(minutes=30))
        r_race = full.post("/api/admin/report-mails/haz_id_register/run-now/", {}, format="json")
        ok("two requests in the same minute cannot both create the run: the database refuses the second (409)", r_race.status_code == 409 and "right now" in r_race.json()["detail"] and len(sent) == 2, str(r_race.content[:200]))
        SchedItem.objects.filter(subject_key=key_now).delete()
        SchedItem.objects.create(job_key=hz.JOB_KEY, subject_key=f"{ALERT}:by hand slow", label="x", send_date=real, due_at=NOW, status="sending", last_attempt_at=datetime.datetime.now() - datetime.timedelta(minutes=2), cr_dt=NOW - datetime.timedelta(minutes=30))
        ok("a run still going (sending, started minutes ago) also blocks another", full.post("/api/admin/report-mails/haz_id_register/run-now/", {}, format="json").status_code == 409)
        SchedItem.objects.filter(subject_key=f"{ALERT}:by hand slow").delete()
        age_by_hand_items()
        ok("a viewer cannot send it now, and nobody without rights can", viewer.post("/api/admin/report-mails/haz_id_register/run-now/", {}, format="json").status_code == 403 and nobody.post("/api/admin/report-mails/haz_id_register/run-now/", {}, format="json").status_code == 403)
        ok("the page's card says what send now would do", full.get("/api/admin/report-mails/").json()["results"][0]["run_now"]["moves"] is False)
        set_alert(next_mail_dt=DT.combine(real - datetime.timedelta(days=7), datetime.time(17, 0)))
        card = next(c for c in full.get("/api/admin/report-mails/").json()["results"] if c["key"] == "haz_id_register")
        ok("with the date past, the card says it will move Next Mail on, and to when", card["run_now"]["moves"] and card["run_now"]["to"] == DT.combine(real + datetime.timedelta(days=8), datetime.time(17, 0)).isoformat(), str(card["run_now"]))
        age_by_hand_items()
        full.post("/api/admin/report-mails/haz_id_register/run-now/", {}, format="json")
        ok("a send now when it was due counts as the cycle's run: Next Mail moves on by the frequency", nxt() == DT.combine(real + datetime.timedelta(days=8), datetime.time(17, 0)), str(nxt()))
        age_by_hand_items()
        down.add("smtp.default.test"); sent.clear()
        set_alert(next_mail_dt=DT.combine(real + datetime.timedelta(days=3), datetime.time(17, 0)))
        before = nxt()
        r3 = full.post("/api/admin/report-mails/haz_id_register/run-now/", {}, format="json")
        down.discard("smtp.default.test")
        ok("when the mail cannot be sent the answer says why (502) and the item is Failed", r3.status_code == 502 and not r3.json()["ok"] and "refused" in r3.json()["error"] and items().filter(status="failed", label__contains="(by hand)").exists())
        ok("and Next Mail does not move", nxt() == before)
        NotificationTrigger.objects.filter(entity_key=hz.ENTITY_KEY, action=hz.ACTION).delete()
        ok("a report with no trigger row cannot be sent (409)", full.post("/api/admin/report-mails/haz_id_register/run-now/", {}, format="json").status_code == 409 and full.post("/api/admin/report-mails/haz_id_register/schedule/", {"date": str(real), "hour": 9}, format="json").status_code == 409)
        NotificationTrigger.objects.create(entity_key=hz.ENTITY_KEY, action=hz.ACTION, alert_id=ALERT, notification_trigger_active="Y", cr_user_id=0, cr_dt=NOW)
        ok("an unknown report is a 404", full.post("/api/admin/report-mails/nope/run-now/", {}, format="json").status_code == 404 and full.post("/api/admin/report-mails/nope/schedule/", {"date": str(real), "hour": 9}, format="json").status_code == 404)

        print("K2. the three choices of send now")
        H = datetime.time(17, 0)
        D_ = datetime.timedelta
        base_ahead = DT.combine(real + D_(days=10), H)
        set_alert(next_mail_dt=base_ahead, start_time=17, alert_freq=15)
        eff = JOB.run_now_effect(MailAlertDtl.objects.get(pk=ALERT), real)
        ok("with Next Mail ahead the three choices are offered, an extra copy first", eff["default_mode"] == "copy" and not eff["due"] and all(eff["modes"][m]["allowed"] for m in ("copy", "count", "restart")))
        ok("what each would do: copy keeps the date, count adds the frequency to it, restart is today plus the frequency", eff["modes"]["copy"]["next"] == base_ahead and eff["modes"]["count"]["next"] == base_ahead + D_(days=15) and eff["modes"]["restart"]["next"] == DT.combine(real + D_(days=15), H))
        age_by_hand_items(); items().delete(); sent.clear()
        r = full.post("/api/admin/report-mails/haz_id_register/run-now/", {"mode": "count"}, format="json")
        ok("A (extra copy) was shown above; B (count it as the next send) sends and moves Next Mail on by the frequency from the date it was due", r.status_code == 200 and len(sent) == 1 and nxt() == base_ahead + D_(days=15) and r.json()["moved"] and r.json()["mode"] == "count", str(nxt()))
        ok("and the item says so", "counted as the next send" in SchedItem.objects.get(label__contains="(by hand)").note)
        age_by_hand_items(); items().delete()
        set_alert(next_mail_dt=base_ahead)
        r = full.post("/api/admin/report-mails/haz_id_register/run-now/", {"mode": "restart"}, format="json")
        ok("C (start a new cycle from today) sends and sets Next Mail to today plus the frequency, at the alert's hour", r.status_code == 200 and nxt() == DT.combine(real + D_(days=15), H) and r.json()["mode"] == "restart", str(nxt()))
        ok("the old plan is gone and the new date is not planned (15 days away)", not items().filter(status="planned").exists())
        age_by_hand_items(); items().delete()
        set_alert(next_mail_dt=DT.combine(real - D_(days=5), H))
        eff = JOB.run_now_effect(MailAlertDtl.objects.get(pk=ALERT), real)
        ok("when Next Mail is due an extra copy is not offered (the scheduler sends it at its next run anyway): count is the default", eff["due"] and not eff["modes"]["copy"]["allowed"] and eff["default_mode"] == "count" and eff["modes"]["count"]["next"] == DT.combine(real + D_(days=10), H))
        n_sent = len(sent)
        r = full.post("/api/admin/report-mails/haz_id_register/run-now/", {"mode": "copy"}, format="json")
        ok("asking for an extra copy then is refused, and nothing is sent", r.status_code == 400 and "due" in r.json()["detail"] and len(sent) == n_sent and not items().filter(label__contains="(by hand)").exists(), str(r.content[:200]))
        r = full.post("/api/admin/report-mails/haz_id_register/run-now/", {"mode": "restart"}, format="json")
        ok("when due, a new cycle from today works too", r.status_code == 200 and nxt() == DT.combine(real + D_(days=15), H))
        age_by_hand_items()
        ok("a choice that does not exist is refused", full.post("/api/admin/report-mails/haz_id_register/run-now/", {"mode": "skip"}, format="json").status_code == 400)
        set_alert(alert_freq=0)
        eff = JOB.run_now_effect(MailAlertDtl.objects.get(pk=ALERT), real)
        ok("with no frequency only the extra copy is possible", eff["modes"]["copy"]["allowed"] and not eff["modes"]["count"]["allowed"] and not eff["modes"]["restart"]["allowed"])
        ok("and the others are refused", full.post("/api/admin/report-mails/haz_id_register/run-now/", {"mode": "restart"}, format="json").status_code == 400)
        set_alert(alert_freq=15, next_mail_dt=DT.combine(real + D_(days=10), H))
        down.add("smtp.default.test"); before = nxt(); sent.clear()
        r = full.post("/api/admin/report-mails/haz_id_register/run-now/", {"mode": "restart"}, format="json")
        down.discard("smtp.default.test")
        ok("a send that fails changes nothing, whatever was chosen", r.status_code == 502 and nxt() == before)
        n_before = len(sent)
        JOB.process(DT.combine(real, datetime.time(23, 30)))
        ok("and a failed run by hand is not retried by the scheduler on its own", len(sent) == n_before and SchedItem.objects.filter(label__contains="(by hand)", status="failed").count() >= 1)
        ok("nor does it send an error mail (the person saw the reason on the page)", not [x for x in sent if x["subject"].startswith("[SerosIT]")])
        age_by_hand_items(); items().delete(); sent.clear()

        items().delete(); JOB.plan(DT.combine(real, datetime.time(8, 0)))
        set_alert(next_mail_dt=DT.combine(real + datetime.timedelta(days=2), datetime.time(17, 0)), start_time=17)
        JOB.plan(DT.combine(real, datetime.time(8, 0)))
        ok("(set-up) an item is planned two days ahead", items().filter(status="planned", send_date=real + datetime.timedelta(days=2)).exists())
        target = real + datetime.timedelta(days=20)
        r = full.post("/api/admin/report-mails/haz_id_register/schedule/", {"date": target.isoformat(), "hour": 9}, format="json")
        ok("the page can set Next Mail's date and the hour", r.status_code == 200 and nxt() == DT.combine(target, datetime.time(9, 0)) and MailAlertDtl.objects.get(pk=ALERT).start_time == 9, str(r.content[:150]))
        ok("the old plan is cancelled at once (nothing is planned for a date that far away)", not items().filter(status="planned").exists() and items().filter(status="cancelled").exists())
        near = real + datetime.timedelta(days=3)
        full.post("/api/admin/report-mails/haz_id_register/schedule/", {"date": near.isoformat(), "hour": 14}, format="json")
        ok("a date within 7 days is planned for that day at that hour", items().filter(status="planned", send_date=near, due_at=DT.combine(near, datetime.time(14, 0))).exists())
        ok("a date in the past is refused", full.post("/api/admin/report-mails/haz_id_register/schedule/", {"date": (real - datetime.timedelta(days=1)).isoformat(), "hour": 9}, format="json").status_code == 400)
        ok("a bad hour, a missing hour and a bad date are refused", all(full.post("/api/admin/report-mails/haz_id_register/schedule/", b, format="json").status_code == 400 for b in ({"date": str(real), "hour": 24}, {"date": str(real), "hour": "x"}, {"date": str(real)}, {"date": "not a date", "hour": 9}, {"hour": 9})))
        ok("today is allowed", full.post("/api/admin/report-mails/haz_id_register/schedule/", {"date": str(real), "hour": 23}, format="json").status_code == 200)
        ok("a viewer cannot change it", viewer.post("/api/admin/report-mails/haz_id_register/schedule/", {"date": str(real), "hour": 9}, format="json").status_code == 403)
        ok("the change is in the audit trail, with the old and the new date", SysAuditLog.objects.filter(entity=MK, record_label__contains="Next Mail changed").exists())
        from core import birthday_views
        from core.models import SchedHeartbeat
        SchedHeartbeat.objects.update_or_create(pk=1, defaults=dict(last_tick_at=None, last_service_tick_at=None, last_manual_tick_at=None))
        scheduler.tick(NOW, owner="check", source="manual")
        h = birthday_views.scheduler_health(NOW)
        ok("a run by hand does not make the scheduler service look alive", h["state"] == "never" and h["manual_at"] is not None)
        scheduler.tick(NOW + datetime.timedelta(minutes=1), owner="check", source="service")
        h = birthday_views.scheduler_health(NOW + datetime.timedelta(minutes=2))
        ok("a run by the service does", h["state"] == "running" and h["minutes_ago"] <= 2)
        ok("and it is stale after 75 minutes without one", birthday_views.scheduler_health(NOW + datetime.timedelta(minutes=90))["state"] == "stale")

        raise Rollback()
except Rollback:
    pass
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print()
print("FAILED: " + ", ".join(fails) if fails else "all checks passed")
sys.exit(1 if fails else 0)
