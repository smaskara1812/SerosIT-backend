"""Checks the Drilling Info Status mail (alert 244): which rigs and companies are listed (open project line, sub-type 2 or 3, open cost-centre mapping), each column,
the days (blank at 0, red above 1), who each company's mail goes to, one mail per company, the retry that does not mail a company twice, and the Rig Alert Recipients rules
(a rig or a company, not both; only companies that own a rig). A fake mail server is used and everything in the database is rolled back.

    cd backend
    .venv/bin/python scripts/check_drilling_info_status.py
"""
import datetime, os, shutil, sys, tempfile, django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TMP = tempfile.mkdtemp(prefix="drilling_info_status_check_")
os.environ["LOG_DIR"] = os.path.join(TMP, "logs")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.test import APIClient
from core import drilling_info_status as ds, mailer
from core.models import DrillingDtl, EmailLog, MailAlertDtl, MstCompany, MstRig, MstUser, NotificationTrigger, RigToEmailMapping, SchedItem, UserPermission, UserProfile
from core.permissions import invalidate_user_access

sent, fail_for = [], set()


def fake_deliver(subject, html, text, to, cc, bcc, from_name, smtp, inline_images, attachments=None):
    if any(f in html for f in fail_for):
        raise RuntimeError("smtp down")
    sent.append({"subject": subject, "html": html, "text": text, "to": to, "cc": cc, "bcc": bcc, "from_name": from_name, "host": smtp["host"]})


mailer._deliver = fake_deliver
settings.EMAIL_HOST = "smtp.default.test"


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
NOW = DT(2026, 11, 5, 11, 0, 5)
TODAY = NOW.date()
ALERT = 244
JOB = ds.JOB


def run_job(alert, setup, now):
    """JOB.send_report, then the Email Log rows it wrote are dated as the test's own day (the check runs on a fixed day, the log stamps the real clock)."""
    res = JOB.send_report(alert, setup, now)
    EmailLog.objects.filter(trigger_code=ds.TRIGGER_CODE).update(sent_dt=NOW)
    return res
KEY = "masters.rig_alert_recipients"
try:
    with transaction.atomic():
        a = MailAlertDtl.objects.get(pk=ALERT)
        ok("alert 244 is Drilling Info Status", a.alert_name == "Drilling Info Status")
        SchedItem.objects.filter(job_key=ds.JOB_KEY).delete()
        NotificationTrigger.objects.filter(entity_key="automation", action=ds.ACTION).delete()
        EmailLog.objects.filter(trigger_code=ds.TRIGGER_CODE).delete()

        print("A. the table")
        rows = ds.status_rows(TODAY)
        groups = ds.by_company(rows)
        names = {n: [r["rig"] for r in rs] for _c, n, rs in groups}
        ok("three companies, in company order: SDPL, SEPL, SOSIL", [n for _c, n, _r in groups] == ["SDPL", "SEPL", "SOSIL"], str(list(names)))
        ok("SDPL has EE01 (LR 3), SR03 (MR 11) and DR01 (MR 1)", set(names["SDPL"]) == {"EE01 (LR 3)", "SR03 (MR 11)", "DR01 (MR 1)"}, str(names))
        ok("SEPL has SK1, SK02, EE02, New Projects - Rig and SK01; SOSIL has Axom Rhino (EE05)", set(names["SEPL"]) == {"SK1 (SK1)", "SK02 (SK02)", "EE02 (LR 4)", "New Projects - Rig (New Projects - Rig)", "SK01 (SK01)"} and names["SOSIL"] == ["Axom Rhino (EE05)"], str(names))
        by_rig = {r["rig"]: r for r in rows}
        ee = by_rig["EE01 (LR 3)"]
        last = DrillingDtl.objects.filter(rig__rig_name="EE01").order_by("-drilling_dtl_dt").first().drilling_dtl_dt
        ok("last update is the rig's latest daily report and the days are today less that date", ee["last"] == last and ee["days"] == (TODAY - last).days, str((ee["last"], ee["days"])))
        ok("the contract number has its spaces removed, the project start is the project's", by_rig["SK01 (SK01)"]["contract_no"] == "Yettoreceive" and by_rig["SK01 (SK01)"]["prj_start"] == D(2026, 10, 23))
        ok("a rig with no report has blank last update and 0 days", by_rig["New Projects - Rig (New Projects - Rig)"]["last"] is None and by_rig["New Projects - Rig (New Projects - Rig)"]["days"] == 0)
        ok("first anchor down is the rig's well that is not completed", by_rig["SK02 (SK02)"]["anchor"] == D(2026, 10, 23) and by_rig["SR03 (MR 11)"]["anchor"] is None)
        html, text = ds.build_company_mail("SDPL", [r for _c, n, rs in groups if n == "SDPL" for r in rs])
        ok("the mail has the heading, the seven columns, the date format dd/mm/yyyy and the automated line", all(h in html for h in ds.HEADERS) and "Drilling Info Status" in html and "Seros-IT Auto Alert" in html and f"{last:%d/%m/%Y}" in html and "automated mail" in html)
        ok("days above 1 are red, a day of 1 is not, 0 is blank", html.count("color:red") == sum(1 for r in rows if r["company"] == "SDPL" and r["days"] > 1))
        ok("a plain-text version is made too", "EE01 (LR 3)" in text and "Days Diff." in text)

        print("B. who gets a company's mail")
        sepl = next(c for c, n, _r in groups if n == "SEPL"); sdpl = next(c for c, n, _r in groups if n == "SDPL"); sosil = next(c for c, n, _r in groups if n == "SOSIL")
        r_sepl = ds.recipients_for_company(ALERT, sepl, TODAY)
        r_sosil = ds.recipients_for_company(ALERT, sosil, TODAY)
        ok("a company gets its own rows plus the alert's: SEPL has more Cc than SOSIL", len(r_sepl["cc"]) > len(r_sosil["cc"]) and r_sepl["to"] and r_sosil["to"], f"{r_sepl} {r_sosil}")
        ok("the alert's To (Get.2023@essar.com) is in every company's mail", all("get.2023@essar.com" in [e.lower() for e in ds.recipients_for_company(ALERT, c, TODAY)["to"]] for c in (sepl, sdpl, sosil)))
        ok("a company's rows are not mixed with another company's", set(map(str.lower, r_sepl["to"] + r_sepl["cc"])).isdisjoint({"ranvir.singh@seros.co.in"}) and "ranvir.singh@seros.co.in" in [e.lower() for e in r_sosil["cc"]], str(r_sosil))

        print("C. the mails")
        ds.ensure_setup(ALERT)
        from core.scheduled_mails_views import recipients_preview
        pv = recipients_preview(JOB, TODAY)
        srcs = {e["source"] for e in pv["recipients"]}
        ok("the recipients preview (Report Mails > Recipients) also lists the company rows, labelled, and links to Rig Alert Recipients", any(x.startswith("Rig Alert Recipients (SEPL)") for x in srcs) and any(x.startswith("Rig Alert Recipients (SOSIL)") for x in srcs) and any(x.startswith("Alert To Users") for x in srcs) and "rig-alert-recipients?alert=244" in pv["links"].get("rig_recipients", ""), str(srcs)[:300])
        MailAlertDtl.objects.filter(pk=ALERT).update(alert_active="Y")
        a = MailAlertDtl.objects.get(pk=ALERT)
        sent.clear()
        err, res, mail = run_job(a, JOB.get_setup(TODAY), NOW)
        ok("one mail per company, every day, whether or not a rig is late, each with its company in the subject", err == "" and len(sent) == 3 and all(m["subject"].startswith("Drilling Info Status - ") for m in sent) and len({m["subject"] for m in sent}) == 3, f"{err} {len(sent)} {[m['subject'] for m in sent]}")
        m = next(x for x in sent if "Axom Rhino" in x["html"])
        ok("the SOSIL mail has only its rig, goes to its recipients through the default account", "SK01" not in m["html"] and m["to"] and m["host"] == "smtp.default.test" and m["from_name"] == "", str(m["to"]))
        ok("the Email Log has one row per mail", EmailLog.objects.filter(trigger_code=ds.TRIGGER_CODE, success=True).count() == 3)
        sent.clear()
        err, res, mail = run_job(a, JOB.get_setup(TODAY), NOW)
        ok("run again the same day: nobody is mailed twice", err == "" and not sent and "already mailed earlier" in mail.summary, mail.summary)
        # a resend (and a run started by hand) must send again: the once-a-day guard is for the automatic retries only
        sent.clear()
        res_fresh = JOB.send_report(a, JOB.get_setup(TODAY), NOW, fresh=True)
        ok("a fresh send (resend, run by hand) mails every company again even though they were mailed today", res_fresh[0] == "" and len(sent) == 3, str((res_fresh[0], len(sent))))
        from core.models import SchedItem as _SI
        it = _SI.objects.create(job_key=ds.JOB_KEY, subject_key=str(ALERT), label="Drilling Info Status check", send_date=TODAY, due_at=NOW, status="sent", cr_dt=NOW)
        sent.clear()
        ok_resend, err_resend = JOB.resend(it, NOW)
        ok("Resend on the Scheduled Mails page really sends (3 mails), and says so", ok_resend and len(sent) == 3 and EmailLog.objects.filter(trigger_code=ds.TRIGGER_CODE).count() >= 6, f"{ok_resend} {err_resend} {len(sent)}")
        EmailLog.objects.filter(trigger_code=ds.TRIGGER_CODE).delete(); sent.clear(); fail_for.add("Axom Rhino")
        err, res, mail = run_job(a, JOB.get_setup(TODAY), NOW)
        ok("a company whose mail fails is reported; the others go", "SOSIL" in err and len(sent) == 2, f"{err} {len(sent)}")
        fail_for.clear(); sent.clear()
        err, res, mail = run_job(a, JOB.get_setup(TODAY), NOW)
        ok("the retry sends only that company", err == "" and len(sent) == 1 and "Axom Rhino" in sent[0]["html"], f"{err} {len(sent)}")
        EmailLog.objects.filter(trigger_code=ds.TRIGGER_CODE).delete()
        from core.models import MailAlertToUser
        MailAlertToUser.objects.filter(alert_id=ALERT, addressee_type="T").delete()
        RigToEmailMapping.objects.filter(alert_id=ALERT, company_id=sosil, addressee_type="T").delete()
        sent.clear()
        err, res, mail = run_job(a, JOB.get_setup(TODAY), NOW)
        ok("a company with no To address is reported and not mailed; the other companies still go", "SOSIL: no To address" in err and len(sent) == 2, f"{err} {len(sent)}")
        MailAlertDtl.objects.filter(pk=ALERT).update(alert_active="")
        err, _r, _m = run_job(MailAlertDtl.objects.get(pk=ALERT), JOB.get_setup(TODAY), NOW)
        ok("an alert that is not active sends nothing and says why", "switched off" in err)
        from core import scheduler
        ok("the job is registered with the scheduler", scheduler.JOBS.get(ds.JOB_KEY) is JOB)

        pm = JOB.preview_mails(MailAlertDtl.objects.get(pk=ALERT), NOW)
        ok("a test makes the real mails (not an empty one): 3 here, each with a body", len(pm) == 3 and all(m.html and m.text and "Seros-IT Auto Alert" in m.html for m in pm), str([m.subject for m in pm]))
        RK = "admin.report_mails"
        tester = mk("tt_edit", {RK: "view edit"})
        sent.clear()
        r = tester.post(f"/api/admin/report-mails/{JOB.key}/test-send/", {"email": "me@example.test"}, format="json")
        ok("Send a test sends every one of them to the tester only, marked [Test]", r.status_code == 200 and r.json()["count"] == 3 and len(sent) == 3 and all(m["to"] == ["me@example.test"] and not m["cc"] and not m["bcc"] and m["subject"].startswith("[Test] ") and "Seros-IT Auto Alert" in m["html"] for m in sent), f"{r.status_code} {r.content[:200]}")
        from openpyxl import load_workbook as _lw
        import io as _io
        _dl = JOB.build(MailAlertDtl.objects.get(pk=ALERT), NOW)
        ok("Download report gives an Excel file of what a run would send now (the mails themselves have no attachment), not an error", len(_dl.attachments) == 1 and _dl.attachments[0][0].startswith("Drilling_Info_Status") and _dl.attachments[0][0].endswith(".xlsx") and _lw(_io.BytesIO(_dl.attachments[0][1])).active.max_row >= 2)
        print("D. Rig Alert Recipients: a rig or a company")
        full = mk("ds_edit", {KEY: "view add edit delete"})
        url = "/api/masters/rig-alert-recipients/"
        u = MstUser.objects.filter(user_id__gt=0).exclude(user_email__isnull=True).exclude(user_email="").order_by("user_id").first()
        sk01 = MstRig.objects.get(rig_name="SK01").rig_id
        body = {"alert": ALERT, "user": u.user_id, "addressee_type": "T", "from_dt": "2026-11-01"}
        ok("neither a rig nor a company is refused", full.post(url, body, format="json").status_code == 400)
        ok("both a rig and a company are refused", full.post(url, {**body, "rig": sk01, "company": sepl}, format="json").status_code == 400)
        ok("a company is accepted", full.post(url, {**body, "company": sosil}, format="json").status_code == 201)
        ok("a rig is accepted", full.post(url, {**body, "rig": sk01}, format="json").status_code == 201)
        other = MstCompany.objects.exclude(cost_centre_mappings__cost_centre__rig__isnull=False).first()
        ok("a company that owns no rig is refused", full.post(url, {**body, "company": other.company_id, "addressee_type": "C"}, format="json").status_code == 400)
        resp = full.get("/api/masters/companies/?owns_rigs=1&page_size=100")
        lst = resp.json()
        items = lst.get("results", lst) if isinstance(lst, dict) else lst
        got = {c.get("company_id") for c in items}
        ok("the Company dropdown lists only the companies that own a rig (5 of 318)", resp.status_code == 200 and len(items) == 5 and {sepl, sdpl, sosil} <= got, f"{resp.status_code} {str(lst)[:200]}")
        raise Rollback
except Rollback:
    pass
shutil.rmtree(TMP, ignore_errors=True)
print("\nFAILED: " + ", ".join(fails) if fails else "\nall checks passed")
sys.exit(1 if fails else 0)
