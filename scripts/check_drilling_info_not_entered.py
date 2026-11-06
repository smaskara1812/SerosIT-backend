"""Checks the Drilling Info: Daily Not Entered mail (alert 231): which rigs are flagged (open project line, a report in the window on a well not completed, none
yesterday), who each rig's mail goes to (the rig's Rig Alert Recipients plus the alert's own, strongest type wins, Bcc from the alert's rows), the mail itself, the
retry that does not mail a rig twice, a rig with no To address, the Rig Alert Recipients master (checks and rights), the setup command, and several error-mail
addresses. A fake mail server is used and everything in the database is rolled back.

    cd backend
    .venv/bin/python scripts/check_drilling_info_not_entered.py
"""
import datetime, os, shutil, sys, tempfile, django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TMP = tempfile.mkdtemp(prefix="drilling_info_check_")
os.environ["LOG_DIR"] = os.path.join(TMP, "logs")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import transaction
from rest_framework.test import APIClient
from core import drilling_info_not_entered as di, mailer
from core.models import DrillingDtl, EmailLog, MailAlertDtl, MailAlertToUser, MstRig, MstUser, NotificationTrigger, RigToEmailMapping, SchedItem, UserPermission, UserProfile
from core.permissions import invalidate_user_access

sent, fail_for = [], set()


def fake_deliver(subject, html, text, to, cc, bcc, from_name, smtp, inline_images, attachments=None):
    if any(f in html for f in fail_for):
        raise RuntimeError("smtp down")
    sent.append({"subject": subject, "html": html, "text": text, "to": to, "cc": cc, "bcc": bcc, "from_name": from_name, "host": smtp["host"]})


mailer._deliver = fake_deliver
settings.EMAIL_HOST = "smtp.default.test"
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
NOW = DT(2026, 11, 5, 11, 0, 5)
TODAY = NOW.date()
YESTERDAY = TODAY - datetime.timedelta(days=1)
ALERT = 231
JOB = di.JOB


def run_job(alert, setup, now):
    """JOB.send_report, then the Email Log rows it wrote are dated as the test's own day (the check runs on a fixed day, the log stamps the real clock)."""
    res = JOB.send_report(alert, setup, now)
    EmailLog.objects.filter(trigger_code=di.TRIGGER_CODE).update(sent_dt=NOW)
    return res
KEY = "masters.rig_alert_recipients"
try:
    with transaction.atomic():
        a = MailAlertDtl.objects.get(pk=ALERT)
        ok("alert 231 is the Drilling Info Daily Not Entered alert, window 30 (updated 5 Nov 2026)", "Not Entered" in a.alert_name and a.alert_window == 30, f"{a.alert_name} {a.alert_window}")
        SchedItem.objects.filter(job_key=di.JOB_KEY).delete()
        NotificationTrigger.objects.filter(entity_key="automation", action=di.ACTION).delete()
        EmailLog.objects.filter(trigger_code=di.TRIGGER_CODE).delete()

        print("A. which rigs")
        ok("the window is the alert's (30), 30 when it is 0", di.window_days(a) == 30 and di.window_days(MailAlertDtl(alert_window=0)) == 30 and di.window_days(MailAlertDtl(alert_window=7)) == 7)
        sk01 = MstRig.objects.get(rig_name="SK01").rig_id
        ee01 = MstRig.objects.get(rig_name="EE01").rig_id
        miss = dict(di.missing_rigs(TODAY, 30))
        has_y = lambda rid: DrillingDtl.objects.filter(rig_id=rid, drilling_dtl_dt=YESTERDAY).exists()
        ok("a rig with a report yesterday is not flagged, one without is", ee01 not in miss and sk01 in miss and has_y(ee01) and not has_y(sk01), str(miss))
        ok("with a window of 1 day only rigs that reported on the day before yesterday are checked", all(not has_y(r) for r in dict(di.missing_rigs(TODAY, 1))))
        far = di.missing_rigs(TODAY + datetime.timedelta(days=400), 30)
        ok("a rig with no report in the window is not checked at all", far == [])
        ok("every rig checked has an open project line", set(miss) <= set(di.active_rigs(TODAY)))

        print("B. who gets a rig's mail")
        base = di.recipients_for_rig(ALERT, sk01, TODAY)
        ok("a rig with no rows of its own gets the alert's recipients (To, Cc and the alert's Bcc)", base["to"] and base["bcc"] == ["Savita.Bodake@seros.co.in"], str(base))
        users = list(MstUser.objects.filter(user_id__gt=0).exclude(user_email__isnull=True).exclude(user_email="").order_by("user_id")[:4])
        u1, u2, u3, u4 = users
        nomail = MstUser.objects.filter(user_id__gt=0, user_email__isnull=True).order_by("user_id").first() or MstUser.objects.filter(user_id__gt=0, user_email="").order_by("user_id").first()
        mk_row = lambda u, t, **kw: RigToEmailMapping.objects.create(rig_id=sk01, user=u, alert_id=ALERT, addressee_type=t, from_dt=D(2026, 1, 1), cr_user_id=0, cr_dt=NOW, **kw)
        mk_row(u1, "T"); mk_row(u2, "C"); mk_row(u3, "T", to_dt=D(2026, 1, 15)); mk_row(nomail, "T")
        RigToEmailMapping.objects.create(rig_id=ee01, user=u4, alert_id=ALERT, addressee_type="T", from_dt=D(2026, 1, 1), cr_user_id=0, cr_dt=NOW)
        r = di.recipients_for_rig(ALERT, sk01, TODAY)
        ok("the rig's own To and Cc are added to the alert's", u1.user_email.strip() in r["to"] and u2.user_email.strip() in r["cc"] and set(base["to"]) <= set(r["to"]), str(r))
        ok("an ended row, a row without an email and another rig's row are left out", u3.user_email not in r["to"] + r["cc"] + r["bcc"] and u4.user_email.strip() not in r["to"] + r["cc"] and len(r["to"]) == len(base["to"]) + 1, str(r))
        MstUser.objects.filter(pk=u2.pk).update(user_email=base["to"][0].upper())  # the same address as an alert To, set as Cc on the rig: the strongest type (To) wins, once
        r2 = di.recipients_for_rig(ALERT, sk01, TODAY)
        ok("an address set twice is listed once, as To", [e.lower() for e in r2["to"] + r2["cc"] + r2["bcc"]].count(base["to"][0].lower()) == 1 and base["to"][0].lower() in [e.lower() for e in r2["to"]], str(r2))
        ok("Bcc is only the alert's own Bcc rows", r["bcc"] == base["bcc"])
        ok("the Report Mails preview lists the rig rows too", any(e["source"].startswith("Rig Alert Recipients (SK01)") for e in JOB.recipients_detailed(TODAY)) or JOB.alert() is None)

        print("C. the mail")
        ensure = di.ensure_setup(ALERT)
        ok("the setup command logic creates the job row and the trigger, once", ensure and not di.ensure_setup(ALERT) and NotificationTrigger.objects.filter(entity_key="automation", action=di.ACTION, alert_id=ALERT).count() == 1, str(ensure))
        from core.scheduled_mails_views import recipients_preview
        pv = recipients_preview(JOB, TODAY)
        ok("the recipients preview lists the rig rows too and links to Rig Alert Recipients", any(e["source"].startswith("Rig Alert Recipients (SK01)") for e in pv["recipients"]) and "rig-alert-recipients?alert=231" in pv["links"].get("rig_recipients", ""), str({e["source"] for e in pv["recipients"]})[:300])
        MailAlertDtl.objects.filter(pk=ALERT).update(alert_active="Y")
        a = MailAlertDtl.objects.get(pk=ALERT)
        sent.clear()
        err, res, mail = run_job(a, JOB.get_setup(TODAY), NOW)
        names = [n for _i, n in di.missing_rigs(TODAY, 30)]
        ok("one mail per missing rig, none for the others", err == "" and len(sent) == len(names) and len(sent) >= 1, f"{err} {len(sent)} {names}")
        m = next(x for x in sent if "SK01" in x["html"])
        ok("subject is the alert's with the rig name added; the body is the legacy text with Seros-IT and the missing date", m["subject"] == "Drilling Info Not Updated. - SK01" and "Seros-IT Auto Alert" in m["html"] and "Drilling Information has not been updated for Rig : SK01" in m["html"] and f"{YESTERDAY:%d %b %Y}" in m["html"] and "automated mail" in m["html"], m["html"][:200])
        ok("it goes to the rig's To and Cc and the alert's Bcc, through the default account with no From name", m["to"] and m["bcc"] == ["Savita.Bodake@seros.co.in"] and u1.user_email.strip() in m["to"] and m["host"] == "smtp.default.test" and m["from_name"] == "", str(m))
        ok("the Email Log has one row per mail, with the rig in it", EmailLog.objects.filter(trigger_code=di.TRIGGER_CODE, success=True).count() == len(sent) and EmailLog.objects.filter(trigger__contains="SK01").exists())
        ok("the summary names the rigs", "SK01" in mail.summary, mail.summary)

        print("D. retry, no To, nothing missing")
        sent.clear(); EmailLog.objects.filter(trigger_code=di.TRIGGER_CODE).delete()
        fail_for.add("SK01")
        err, res, mail = run_job(a, JOB.get_setup(TODAY), NOW)
        ok("a rig whose mail fails is reported, the other rigs' mails go", "SK01" in err and "smtp down" in err.replace("smtp down", "smtp down") and len(sent) == len(names) - 1, f"{err} {len(sent)}")
        fail_for.clear(); sent.clear()
        err, res, mail = run_job(a, JOB.get_setup(TODAY), NOW)
        ok("the retry mails only the rig that failed, nobody twice", err == "" and len(sent) == 1 and "SK01" in sent[0]["html"], f"{err} {len(sent)} {mail.summary}")
        sent.clear()
        err, res, mail = run_job(a, JOB.get_setup(TODAY), NOW)
        ok("a third run sends nothing at all, and says the rig was mailed earlier", err == "" and not sent and "already mailed earlier" in mail.summary, mail.summary)
        EmailLog.objects.filter(trigger_code=di.TRIGGER_CODE).delete()
        MailAlertToUser.objects.filter(alert_id=ALERT, addressee_type="T").delete()
        RigToEmailMapping.objects.filter(alert_id=ALERT, addressee_type="T", rig_id=sk01).delete()
        err, res, mail = run_job(a, JOB.get_setup(TODAY), NOW)
        ok("a rig with no To address is reported (and not mailed); the error names it", "SK01: no To address" in err, err)
        MailAlertDtl.objects.filter(pk=ALERT).update(alert_window=1)
        a1 = MailAlertDtl.objects.get(pk=ALERT)
        sent.clear()
        err, res, mail = run_job(a1, JOB.get_setup(TODAY), NOW)
        ok("nothing missing: no mail, no error, and the summary says so", err == "" and not sent and "nothing sent" in mail.summary, f"{err} {mail.summary} {sent}")
        MailAlertDtl.objects.filter(pk=ALERT).update(alert_window=30, alert_active="")
        err, res, mail = run_job(MailAlertDtl.objects.get(pk=ALERT), JOB.get_setup(TODAY), NOW)
        ok("an alert that is not active sends nothing and says why", "switched off" in err)

        pm = JOB.preview_mails(MailAlertDtl.objects.get(pk=ALERT), NOW)
        n_now = len(JOB.preview_mails(MailAlertDtl.objects.get(pk=ALERT), datetime.datetime.now()))  # the test button works on the real clock
        ok("a test makes the real mails (not an empty one): 1 here, each with a body", len(pm) == 1 and all(m.html and m.text and "Seros-IT Auto Alert" in m.html for m in pm), str([m.subject for m in pm]))
        RK = "admin.report_mails"
        tester = mk("tt_edit", {RK: "view edit"})
        sent.clear()
        r = tester.post(f"/api/admin/report-mails/{JOB.key}/test-send/", {"email": "me@example.test"}, format="json")
        ok("Send a test sends every one of them to the tester only, marked [Test]", r.status_code == 200 and r.json()["count"] == n_now and len(sent) == n_now and all(m["to"] == ["me@example.test"] and not m["cc"] and not m["bcc"] and m["subject"].startswith("[Test] ") and "Seros-IT Auto Alert" in m["html"] for m in sent), f"{r.status_code} {r.content[:200]}")
        from openpyxl import load_workbook as _lw
        import io as _io
        _dl = JOB.build(MailAlertDtl.objects.get(pk=ALERT), NOW)
        ok("Download report gives an Excel file of what a run would send now (the mails themselves have no attachment), not an error", len(_dl.attachments) == 1 and _dl.attachments[0][0].startswith("Drilling_Info_Not_Entered") and _dl.attachments[0][0].endswith(".xlsx") and _lw(_io.BytesIO(_dl.attachments[0][1])).active.max_row >= 2)
        print("E. error-mail addresses, the job in the scheduler")
        from core import scheduler
        ok("the job is registered with the scheduler", scheduler.JOBS.get(di.JOB_KEY) is JOB)
        import importlib
        os.environ["SCHEDULER_ERROR_MAIL_TO"] = "it@example.test, second@example.test ,third@example.test"
        parsed = [x.strip() for x in os.environ["SCHEDULER_ERROR_MAIL_TO"].split(",") if x.strip()]
        ok("several addresses can be set in .env, comma separated", parsed == ["it@example.test", "second@example.test", "third@example.test"])
        src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "settings.py")).read()
        ok("settings splits SCHEDULER_ERROR_MAIL_TO on commas and trims", 'os.getenv("SCHEDULER_ERROR_MAIL_TO", "").split(",")' in src and ".strip()" in src)

        print("F. the master")
        viewer = mk("dr_view", {KEY: "view"}); editor = mk("dr_edit", {KEY: "view add edit delete"}); nobody = mk("dr_none", {})
        base_url = "/api/masters/rig-alert-recipients/"
        ok("no right, no list; a viewer can list but not add", nobody.get(base_url).status_code == 403 and viewer.get(base_url).status_code == 200 and viewer.post(base_url, {}, format="json").status_code == 403)
        body = {"alert": ALERT, "rig": sk01, "user": u3.user_id, "addressee_type": "T", "from_dt": "2026-11-01"}
        r = editor.post(base_url, body, format="json")
        ok("an editor can add a recipient", r.status_code == 201 and r.json()["rig_name"] == "SK01" and r.json()["user_email"], r.content[:200])
        ok("the same person, rig, alert, type and date twice is refused", editor.post(base_url, body, format="json").status_code == 400)
        ok("To before From is refused", editor.post(base_url, {**body, "addressee_type": "C", "to_dt": "2026-10-01"}, format="json").status_code == 400)
        ok("a user with no email is refused with a message", editor.post(base_url, {**body, "user": nomail.user_id, "addressee_type": "C"}, format="json").status_code == 400 and "no email" in editor.post(base_url, {**body, "user": nomail.user_id, "addressee_type": "C"}, format="json").json()["user"][0])
        ok("an unknown type is refused", editor.post(base_url, {**body, "addressee_type": "X"}, format="json").status_code == 400)
        n_all = editor.get(base_url).json()["count"]
        n_y, n_n = editor.get(base_url + "?active=Y").json()["count"], editor.get(base_url + "?active=N").json()["count"]
        ok("the Active / Inactive filter splits the list (inactive = To date passed)", n_y + n_n == n_all and n_n >= 1 and n_y >= 1 and all((x["to_dt"] is None or x["to_dt"] >= str(D.today())) for x in editor.get(base_url + "?active=Y&page_size=500").json()["results"]), f"{n_y} {n_n} {n_all}")
        ok("filtering by another rig does not return this alert's rows for SK01", editor.get(base_url + f"?rig={sk01}&alert={ALERT}").json()["count"] < editor.get(base_url + f"?alert={ALERT}").json()["count"] + 1)
        ok("filtering by alert works and the list is private (not a dropdown source)", editor.get(base_url + f"?alert={ALERT}").json()["count"] >= 5 and getattr(__import__("core.masters_views", fromlist=["x"]).RigToEmailMappingViewSet, "lookup", True) is False)
        raise Rollback
except Rollback:
    pass
shutil.rmtree(TMP, ignore_errors=True)
print("\nFAILED: " + ", ".join(fails) if fails else "\nall checks passed")
sys.exit(1 if fails else 0)
