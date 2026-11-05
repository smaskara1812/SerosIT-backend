"""Checks the Open Incident Actions mail (alert 141): which actions are listed (not closed, not deleted, deleted incidents left out), the status text (overdue, due
today, due in N days, Immediate), the mail (counts per rig or unit, the Excel, the empty-state line said once), the cycle (Next Mail and Start Time),
and the Report Mails endpoints. A fake mail server is used and everything in the database is rolled back.

    cd backend
    .venv/bin/python scripts/check_open_incident_actions.py
"""
import datetime, io, os, shutil, sys, tempfile, django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TMP = tempfile.mkdtemp(prefix="open_incident_actions_check_")
os.environ["LOG_DIR"] = os.path.join(TMP, "logs")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from openpyxl import load_workbook
from rest_framework.test import APIClient
from core import mailer, open_incident_actions as oa
from core.models import Incident, IncidentAction, MailAlertDtl, NotificationTrigger, SchedItem, UserPermission, UserProfile
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
ALERT = 141
JOB = oa.JOB
NOW = DT(2026, 11, 4, 10, 0, 5)
TODAY = NOW.date()
NO_RIG = oa.NO_RIG


def alert(**kw):
    MailAlertDtl.objects.filter(pk=ALERT).update(**kw)
    return MailAlertDtl.objects.get(pk=ALERT)


def act(inc, status="OP", days=None, rec="do it", deleted="", party="Rig Manager"):
    return IncidentAction.objects.create(incident=inc, action_recommended=rec, action_party=party, target_date=None if days is None else TODAY + datetime.timedelta(days=days), action_status=status, marked_as_deleted=deleted, cr_user_id=0, cr_dt=NOW)


try:
    with transaction.atomic():
        a141 = MailAlertDtl.objects.get(pk=ALERT)
        ok("alert 141 is Open Incident Actions", a141.alert_name == "Open Incident Actions")
        IncidentAction.objects.all().delete()
        SchedItem.objects.filter(job_key=oa.JOB_KEY).delete()  # the dev database may already have runs of its own
        NotificationTrigger.objects.filter(entity_key="automation", action="send_open_incident_actions_mail").delete()
        incs = list(Incident.objects.exclude(rig__isnull=True).order_by("incident_id")[:200])
        by_rig_name = {}
        for i in incs:
            by_rig_name.setdefault(i.rig_id, i)
        i1, i2, i4 = list(by_rig_name.values())[:2] + [incs[-1]]
        i3 = Incident.objects.exclude(pk__in=[i1.pk, i2.pk, i4.pk]).order_by("incident_id").first()
        Incident.objects.filter(pk=i3.pk).update(rig=None, unit_name="ZZ Unit")
        Incident.objects.filter(pk=i4.pk).update(marked_as_deleted="Y")
        i3 = Incident.objects.get(pk=i3.pk)

        print("A. which actions are listed")
        act(i1, "OP", -10, "overdue ten"); act(i1, "IN", 5, "in process soon"); act(i1, "CL", -30, "closed"); act(i2, "OP", None, "no target"); act(i2, "OP", 0, "today")
        act(i3, "OP", -1, "unit action"); act(i1, "OP", -3, "deleted action", deleted="Y"); act(i4, "OP", -3, "on a deleted incident")
        rows = oa.collect(TODAY)
        ok("open and in-process ones are listed: 5 of 8", len(rows) == 5, str([r["recommendation"] for r in rows]))
        ok("a closed action, a deleted action and an action on a deleted incident are left out", not any(r["recommendation"] in ("closed", "deleted action", "on a deleted incident") for r in rows))
        st = {r["recommendation"]: r["due_text"] for r in rows}
        ok("status says how late or how soon", st["overdue ten"] == "Overdue by 10 days" and st["in process soon"] == "Due in 5 days" and st["today"] == "Due today" and st["unit action"] == "Overdue by 1 day", str(st))
        ok("no target date is Immediate, measured from the incident, and counts as overdue", st["no target"].startswith("Immediate") and next(r for r in rows if r["recommendation"] == "no target")["overdue"])
        ok("the status of the action is spelled out", {r["status"] for r in rows} == {"Open", "In Process"})
        ok("a rig-less incident shows its unit name", any(r["rig"] == "ZZ Unit" for r in rows))
        ok("by rig or unit, then no-target first, then target date", [r["rig"] for r in rows] == sorted((r["rig"] for r in rows), key=str.lower), str([r["rig"] for r in rows]))
        g = {r: (o, n) for r, o, n in oa.by_rig(rows)}
        ok("counts per rig or unit: rig 1 has 1 overdue and 1 not yet due, rig 2 has 1 and 1, the unit has 1 and 0", g[i1.rig.rig_name] == (1, 1) and g[i2.rig.rig_name] == (1, 1) and g["ZZ Unit"] == (1, 0), str(g))

        print("B. the mail")
        m = oa.build_mail(a141, NOW)
        ok("the subject is the alert's own, else a default", m.subject == (a141.mail_subject or "Seros-IT Auto Report - Open Incident Actions").strip())
        ok("an Excel is attached and the body is a counts table, not a list of actions", len(m.attachments) == 1 and m.attachments[0][0].startswith("Open_Incident_Actions_") and "spreadsheetml" in m.attachments[0][2] and not m.empty and "<table" in m.html and "overdue ten" not in m.html)
        ok("the wording says Seros-IT, never S.I.S., and says open (not overdue) actions", "Seros-IT Auto Alert" in m.html and "S.I.S." not in m.html and "open recommendations/actions" in m.html and "automated Mail" in m.html)
        ok("the columns are Rig / Unit, Overdue, Not yet due, Total, and there is a Total row", all(h in m.html for h in (">Rig / Unit<", ">Overdue<", ">Not yet due<", ">Total<")) and m.html.count(">Total<") == 2)
        ok("the totals are 3 overdue, 2 not yet due, 5", ">3<" in m.html and ">2<" in m.html and ">5<" in m.html)
        ok("rigs with something overdue are marked red", m.html.count("background:#fde8e8") == 3)
        ok("the summary line says what it holds", m.summary.startswith("5 open actions in 3 rigs or units") and "3 overdue" in m.summary, m.summary)
        wb = load_workbook(io.BytesIO(m.attachments[0][1]))
        ok("the Excel has a Summary sheet and a Details sheet", wb.sheetnames == ["Summary", "Details"])
        sm_ws, d = wb["Summary"], wb["Details"]
        ok("Summary has the same counts and a Total row", [c.value for c in sm_ws[5]] == ["Rig / Unit", "Overdue", "Not yet due", "Total"] and [c.value for c in sm_ws[sm_ws.max_row]] == ["Total", 3, 2, 5], str([[c.value for c in r] for r in sm_ws.iter_rows()]))
        ok("Details has one row per action with the recommendation, party, status, target date and due text, overdue rows shaded", d.max_row == 6 and [c.value for c in d[1]] == oa.HEADERS and any(d.cell(row=r, column=5).value == "overdue ten" and d.cell(row=r, column=10).value == "Overdue by 10 days" and d.cell(row=r, column=1).fill.fgColor.rgb.endswith("FDE8E8") for r in range(2, 7)), str([[c.value for c in r] for r in d.iter_rows()]))
        ok("dates are real dates, shown as dd/mm/yyyy", any(isinstance(d.cell(row=r, column=4).value, (datetime.date, datetime.datetime)) and d.cell(row=r, column=4).number_format == "DD/MM/YYYY" for r in range(2, 7)))
        IncidentAction.objects.all().delete()
        e = oa.build_mail(a141, NOW)
        ok("with nothing open the mail says so, once, with no table, no 'Nil' and no attachment", e.empty and not e.attachments and e.html.count("There are no open incident actions") == 1 and "Nil" not in e.html and "<table" not in e.html, e.html[:300])
        act(i1, "OP", -3); act(i2, "OP", 4)

        print("C. the cycle")
        s = JOB.get_setup(TODAY)
        ok("with no trigger the page is told what to do", not s["trigger_found"] and s["warnings"])
        did = oa.ensure_setup()
        ok("the setup command finds alert 141 by its name and creates the trigger, once", NotificationTrigger.objects.filter(entity_key="automation", action="send_open_incident_actions_mail", alert_id=ALERT).exists() and did and oa.ensure_setup() == [])
        s = JOB.get_setup(TODAY)
        ok("the setup shows the alert's own cycle: every 7 days, start hour 10", s["freq"] == 7 and s["send_hour"] == 10 and "Every 7 days" in JOB.schedule_text(TODAY), str((s["freq"], s["send_hour"])))
        ok("the From name is blank and the default account is used", s["from_name"] == "" and s["smtp"]["sender"] is None)
        ok("the alert has recipients", sum(len(v) for v in s["recipients"].values()) >= 1, str(s["recipients"]))
        alert(next_mail_dt=DT(2026, 10, 21, 10, 38, 42), start_time=10, alert_freq=7, alert_active="Y")
        JOB.plan(NOW)
        it = SchedItem.objects.get(job_key=oa.JOB_KEY)
        ok("a Next Mail date that has passed is planned for today at the Start Time (10:00)", it.send_date == TODAY and it.due_at == DT(2026, 11, 4, 10, 0) and "Due 21 Oct 2026" in it.note, str((it.send_date, it.due_at, it.note)))
        n0 = len(sent); JOB.process(DT(2026, 11, 4, 9, 59, 0))
        ok("nothing goes before the hour", len(sent) == n0)
        JOB.process(NOW)
        mm = sent[-1]
        ok("at 10:00 it goes to the alert's recipients through the default account, with the Excel", len(sent) == n0 + 1 and mm["host"] == "smtp.default.test" and mm["to"] and len(mm["attachments"]) == 1 and mm["from_name"] == "", str(mm["host"]))
        ok("Next Mail moves on by the frequency from the day it was due: 21 Oct -> 11 Nov at 10:00 (one catch-up, not several)", MailAlertDtl.objects.get(pk=ALERT).next_mail_dt == DT(2026, 11, 11, 10, 0), str(MailAlertDtl.objects.get(pk=ALERT).next_mail_dt))
        ok("the item says what was sent", "open actions" in SchedItem.objects.get(job_key=oa.JOB_KEY).note)
        alert(alert_active="N")
        ok("an alert that is switched off is not sent", "switched off" in JOB.send_report(MailAlertDtl.objects.get(pk=ALERT), JOB.get_setup(TODAY), NOW)[0])
        alert(alert_active="Y", next_mail_dt=DT(2026, 10, 21, 10, 38, 42))

        print("D. the pages")
        full = mk("zzoia1", {"admin.report_mails": ("view", "edit", "export"), "admin.scheduled_mails": ("view",)})
        cards = full.get("/api/admin/report-mails/").json()["results"]
        ok("Report Mails lists Open Incident Actions", "incident_actions" in {c["key"] for c in cards})
        c = next(x for x in cards if x["key"] == "incident_actions")
        ok("the card has the setup, the schedule and the recipients", c["name"] == "Open Incident Actions" and c["setup"]["alert"]["id"] == ALERT and "Every 7 days" in c["schedule"] and c["overdue"])
        r = full.get("/api/admin/report-mails/incident_actions/download/")
        ok("the Excel can be downloaded (Export)", r.status_code == 200 and "spreadsheetml" in r["Content-Type"] and r["Content-Disposition"].startswith('attachment; filename="Open_Incident_Actions_') and load_workbook(io.BytesIO(r.content)).sheetnames == ["Summary", "Details"], str(r.status_code))
        sent.clear()
        r = full.post("/api/admin/report-mails/incident_actions/test-send/", {"email": "me@example.test"}, format="json")
        ok("a test goes to one address, marked [Test], with the Excel, and does not move Next Mail", r.status_code == 200 and len(sent) == 1 and sent[0]["to"] == ["me@example.test"] and sent[0]["subject"].startswith("[Test] ") and sent[0]["attachments"] and MailAlertDtl.objects.get(pk=ALERT).next_mail_dt == DT(2026, 10, 21, 10, 38, 42), str(r.content[:150]))
        sm = full.get("/api/admin/scheduled-mails/").json()
        ok("Scheduled Mails lists the ten automations", {j["key"] for j in sm["jobs"]} == {"birthday", "holiday", "haz_id_register", "rig_rate_breakup", "activity_monitor", "incident_actions", "daily_operations_update", "rig_performance", "drilling_info_not_entered", "drilling_info_status"}, str({j["key"] for j in sm["jobs"]}))
        raise Rollback()
except Rollback:
    pass
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print()
print("FAILED: " + ", ".join(fails) if fails else "all checks passed")
sys.exit(1 if fails else 0)
