"""Checks the Activity Monitor mail (alert 58): which activities are listed (open, due within the Window or overdue, oldest first), the status text, the
mail (table, red overdue rows, escaping, the empty-state line said once, no attachment), the cycle (Next Mail and Start Time), and the Report Mails
endpoints. A fake mail server is used and everything in the database is rolled back.

    cd backend
    .venv/bin/python scripts/check_activity_monitor_alert.py
"""
import datetime, io, os, shutil, sys, tempfile, django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TMP = tempfile.mkdtemp(prefix="activity_monitor_check_")
os.environ["LOG_DIR"] = os.path.join(TMP, "logs")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from openpyxl import load_workbook
from rest_framework.test import APIClient
from core import activity_monitor_alert as am, mailer
from core.models import ActivityMonitor, MailAlertDtl, MstActivity, MstRig, NotificationTrigger, SchedItem, UserPermission, UserProfile
from core.permissions import invalidate_user_access

sent = []


def fake_deliver(subject, html, text, to, cc, bcc, from_name, smtp, inline_images, attachments=None):
    sent.append({"subject": subject, "html": html, "to": to, "cc": cc, "bcc": bcc, "from_name": from_name, "host": smtp["host"], "attachments": attachments or []})


mailer._deliver = fake_deliver
settings.EMAIL_HOST = "smtp.default.test"
settings.BIRTHDAY_EMAIL_HOST = "smtp.env.test"
settings.SCHEDULER_ERROR_MAIL_TO = ["it@example.test"]


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
ALERT = 58
JOB = am.JOB
NOW = DT(2026, 11, 4, 15, 0, 5)
TODAY = NOW.date()
NO_RIG = am.NO_RIG


def alert(**kw):
    MailAlertDtl.objects.filter(pk=ALERT).update(**kw)
    return MailAlertDtl.objects.get(pk=ALERT)


def act(name, nature="M"):
    return MstActivity.objects.create(activity_name=name, activity_type="I", activity_nature=nature, activity_location="R", intimate_vessel="N", activity_validity_days=30, cr_user_id=0, cr_dt=NOW)


def html_escape(t):
    import html as _h
    return _h.escape(t)


def mon(activity, days, rig=None, remark="", done=False):
    return ActivityMonitor.objects.create(activity=activity, rig=rig, scheduled_dt=TODAY + datetime.timedelta(days=days), planning_remark=remark, completion_dt=TODAY if done else None, cr_user_id=0, cr_dt=NOW)


try:
    with transaction.atomic():
        a58 = MailAlertDtl.objects.get(pk=ALERT)
        ok("alert 58 is Activity Monitor - EOSL", a58.alert_name == "Activity Monitor - EOSL")
        ActivityMonitor.objects.all().delete()
        SchedItem.objects.filter(job_key=am.JOB_KEY).delete()  # the dev database may already have runs of its own
        NotificationTrigger.objects.filter(entity_key="automation", action="send_activity_monitor_mail").delete()
        rig = MstRig.objects.order_by("rig_id").first()
        A, B = act("ZZ Survey <b>one</b>", "M"), act("ZZ Drill", "N")

        print("A. which activities are listed")
        mon(A, -10, rig, "late one"); mon(B, 0, rig); mon(A, 30, rig, "soon"); mon(B, 60, None, "edge"); mon(A, 61, rig, "too far"); mon(A, -5, rig, "done", done=True); mon(B, -1, rig)
        rows = am.collect(60, TODAY)
        ok("open ones due within the window or overdue are listed: 5 of 7", len(rows) == 5, str([(r["activity"], r["due"]) for r in rows]))
        ok("the last day of the window is included, one day past it is not", any(r["remark"] == "edge" for r in rows) and not any(r["remark"] == "too far" for r in rows))
        ok("a completed activity is not listed, however overdue", not any(r["remark"] == "done" for r in rows))
        ok("by rig (the rig-less ones last), then oldest first", [r["rig"] for r in rows].count(NO_RIG) == 1 and rows[-1]["rig"] == NO_RIG and [r["due"] for r in rows[:-1]] == sorted(r["due"] for r in rows[:-1]) and rows[0]["remark"] == "late one")
        st = {r["remark"] or r["activity"]: r["status"] for r in rows}
        ok("status says how late or how soon: overdue by 10 days / 1 day, due today, due in 30 days", st["late one"] == "Overdue by 10 days" and any(r["status"] == "Overdue by 1 day" for r in rows) and any(r["status"] == "Due today" for r in rows) and st["soon"] == "Due in 30 days", str(st))
        ok("overdue rows are flagged, the others are not", [r["overdue"] for r in rows] == [True, True, False, False, False], str([r["overdue"] for r in rows]))
        ok("an activity with no rig (office or port) says so", next(r for r in rows if r["remark"] == "edge")["rig"] == "Office / Port")
        ok("nature is spelled out", rows[0]["nature"] == "Mandatory" and next(r for r in rows if r["activity"] == "ZZ Drill")["nature"] == "Non Mandatory")
        ok("a window of 0 lists only today and what is overdue", len(am.collect(0, TODAY)) == 3)

        print("B. the mail")
        rig2 = MstRig.objects.exclude(pk=rig.pk).order_by("rig_id").first()
        mon(B, -2, rig2, "second rig"); mon(B, 10, rig2, "second rig soon")
        m = am.build_mail(a58, NOW)
        ok("the subject is the alert's own, else a default", m.subject == (a58.mail_subject or "Seros-IT Auto Report - Activity Monitor").strip())
        ok("an Excel is attached and the body is a counts table, not a list of activities", len(m.attachments) == 1 and m.attachments[0][0].startswith("Activity_Monitor_") and "spreadsheetml" in m.attachments[0][2] and not m.empty and "<table" in m.html and "ZZ Drill" not in m.html and "ZZ Survey" not in m.html)
        ok("the wording says Seros-IT, never S.I.S.", "Seros-IT Auto Alert" in m.html and "S.I.S." not in m.html and "automated Mail" in m.html)
        ok("the columns are Rig, Overdue, Due in next 60 days, Total, and there is a Total row", all(h in m.html for h in (">Rig<", ">Overdue<", ">Due in next 60 days<", ">Total<")) and m.html.count(">Total<") == 2)
        groups = am.by_rig(am.collect(60, TODAY))
        g = {r: (o, u) for r, o, u in groups}
        ok("a row for each rig, with its own counts: the first rig 2 overdue and 3 due, the second 1 and 1, office/port 0 and 1", g[rig.rig_name] == (2, 2) and g[rig2.rig_name] == (1, 1) and g[NO_RIG] == (0, 1), str(g))
        ok("the mail's rows carry those counts and the totals (3 overdue, 4 due, 7)", f">{html_escape(rig.rig_name)}<" in m.html and ">3<" in m.html and ">4<" in m.html and ">7<" in m.html)
        ok("rigs with a count overdue are marked red, the others are not", m.html.count("background:#fde8e8") == 2)
        ok("the summary line says what it holds", m.summary.startswith("7 activities in 3 rigs") and "3 overdue" in m.summary, m.summary)
        wb = load_workbook(io.BytesIO(m.attachments[0][1]))
        ok("the Excel has a Summary sheet and a Details sheet", wb.sheetnames == ["Summary", "Details"])
        sm_ws, d = wb["Summary"], wb["Details"]
        ok("Summary has the same counts: header, a row per rig, a Total row", [c.value for c in sm_ws[5]] == ["Rig", "Overdue", "Due in next 60 days", "Total"] and sm_ws.max_row == 5 + 3 + 1 and [c.value for c in sm_ws[sm_ws.max_row]] == ["Total", 3, 4, 7], str([[c.value for c in r] for r in sm_ws.iter_rows()]))
        ok("Details has one row per activity, by rig then due date, with the status and overdue rows shaded", d.max_row == 1 + 7 and [c.value for c in d[1]] == am.HEADERS and d["B2"].value == min(rig.rig_name, rig2.rig_name) and d["G2"].value in ("Overdue by 10 days", "Overdue by 2 days") and d["G4"].value == "Overdue by 10 days" and d["B4"].value == "Essar Wildcat" and d["A2"].fill.fgColor.rgb.endswith("FDE8E8") and d["B8"].value == NO_RIG, str([[c.value for c in r] for r in d.iter_rows()]))
        ok("the due dates are real dates, shown as dd/mm/yyyy", isinstance(d["F2"].value, (datetime.date, datetime.datetime)) and d["F2"].number_format == "DD/MM/YYYY")
        ActivityMonitor.objects.all().delete()
        e = am.build_mail(a58, NOW)
        ok("with nothing due the mail says so, once, with no table, no 'Nil' and no attachment", e.empty and not e.attachments and e.html.count("There are no rig activities due") == 1 and "Nil" not in e.html and "<table" not in e.html, e.html[:300])
        ok("an empty Activity Monitor gives the same nothing-due mail, not a mail without a body", "next 60 days" in e.html and e.summary == "Nothing due")
        mon(A, -3, rig); mon(B, 5, rig)

        print("C. the cycle")
        s = JOB.get_setup(TODAY)
        ok("with no trigger the page is told what to do", not s["trigger_found"] and s["warnings"])
        did = am.ensure_setup()
        ok("the setup command finds alert 58 by its name and creates the trigger, once", NotificationTrigger.objects.filter(entity_key="automation", action="send_activity_monitor_mail", alert_id=ALERT).exists() and did and am.ensure_setup() == [])
        s = JOB.get_setup(TODAY)
        ok("the setup shows the alert's own cycle: every 7 days, window 60, start hour 15", s["freq"] == 7 and s["window"] == 60 and s["send_hour"] == 15 and "Every 7 days" in JOB.schedule_text(TODAY), str((s["freq"], s["window"], s["send_hour"])))
        ok("the From name is blank and the default account is used", s["from_name"] == "" and s["smtp"]["sender"] is None)
        ok("the alert has recipients", sum(len(v) for v in s["recipients"].values()) >= 1, str(s["recipients"]))
        alert(next_mail_dt=DT(2026, 10, 20, 15, 37, 52), start_time=15, alert_freq=7, alert_active="Y")
        JOB.plan(NOW)
        it = SchedItem.objects.get(job_key=am.JOB_KEY)
        ok("a Next Mail date that has passed is planned for today at the Start Time (15:00)", it.send_date == TODAY and it.due_at == DT(2026, 11, 4, 15, 0) and "Due 20 Oct 2026" in it.note, str((it.send_date, it.due_at, it.note)))
        n0 = len(sent); JOB.process(DT(2026, 11, 4, 14, 59, 0))
        ok("nothing goes before the hour", len(sent) == n0)
        JOB.process(NOW)
        mm = sent[-1]
        ok("at 15:00 it goes to the alert's recipients through the default account, with the Excel", len(sent) == n0 + 1 and mm["host"] == "smtp.default.test" and mm["to"] and len(mm["attachments"]) == 1 and mm["from_name"] == "", str(mm["host"]))
        ok("the mail that went has the counts table", "Overdue" in mm["html"] and "<table" in mm["html"])
        ok("Next Mail moves on by the frequency from the day it was due: 20 Oct -> 10 Nov at 15:00 (one catch-up, not several)", MailAlertDtl.objects.get(pk=ALERT).next_mail_dt == DT(2026, 11, 10, 15, 0), str(MailAlertDtl.objects.get(pk=ALERT).next_mail_dt))
        ok("the item says what was sent", "activities" in SchedItem.objects.get(job_key=am.JOB_KEY).note)
        alert(alert_active="N")
        ok("an alert that is switched off is not sent", "switched off" in JOB.send_report(MailAlertDtl.objects.get(pk=ALERT), JOB.get_setup(TODAY), NOW)[0])
        alert(alert_active="Y", next_mail_dt=DT(2026, 10, 20, 15, 37, 52))

        print("D. the pages")
        full = mk("zzam1", {"admin.report_mails": ("view", "edit", "export"), "admin.scheduled_mails": ("view",)})
        cards = full.get("/api/admin/report-mails/").json()["results"]
        ok("Report Mails lists the Activity Monitor", "activity_monitor" in {c["key"] for c in cards})
        c = next(x for x in cards if x["key"] == "activity_monitor")
        ok("the card has the setup, the schedule and the recipients", c["name"] == "Activity Monitor - EOSL" and c["setup"]["alert"]["id"] == ALERT and "Every 7 days" in c["schedule"] and c["overdue"])
        r = full.get("/api/admin/report-mails/activity_monitor/download/")
        ok("the Excel can be downloaded (Export)", r.status_code == 200 and "spreadsheetml" in r["Content-Type"] and r["Content-Disposition"].startswith('attachment; filename="Activity_Monitor_') and load_workbook(io.BytesIO(r.content)).sheetnames == ["Summary", "Details"], str(r.status_code))
        sent.clear()
        r = full.post("/api/admin/report-mails/activity_monitor/test-send/", {"email": "me@example.test"}, format="json")
        ok("a test goes to one address, marked [Test], with the Excel, and does not move Next Mail", r.status_code == 200 and len(sent) == 1 and sent[0]["to"] == ["me@example.test"] and sent[0]["subject"].startswith("[Test] ") and sent[0]["attachments"] and MailAlertDtl.objects.get(pk=ALERT).next_mail_dt == DT(2026, 10, 20, 15, 37, 52), str(r.content[:150]))
        sm = full.get("/api/admin/scheduled-mails/").json()
        ok("Scheduled Mails lists the eight automations", {j["key"] for j in sm["jobs"]} == {"birthday", "holiday", "haz_id_register", "rig_rate_breakup", "activity_monitor", "incident_actions", "daily_operations_update", "rig_performance"}, str({j["key"] for j in sm["jobs"]}))
        raise Rollback()
except Rollback:
    pass
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print()
print("FAILED: " + ", ".join(fails) if fails else "all checks passed")
sys.exit(1 if fails else 0)
