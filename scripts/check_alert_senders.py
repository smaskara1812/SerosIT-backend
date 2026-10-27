"""Checks Masters > Alert Senders and how the mailer uses it, with a fake mail server and people holding exactly the rights named:
  * with no sender row nothing changes (environment account, then default: the way it worked before the table existed);
  * an alert with an active sender row is sent through it first, then the environment account, then the default account;
  * the password is encrypted at rest, never returned by the API, never in the audit trail, never in an error or a log line;
  * a blank password on an edit keeps the saved one; an unreadable one is skipped, not fatal; an inactive row is ignored;
  * one active sender per alert; the fields are checked; the rights are the page's own.
Everything in the database is rolled back.

    cd backend
    .venv/bin/python scripts/check_alert_senders.py
"""
import datetime, io, json, logging, os, shutil, sys, tempfile, django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TMP = tempfile.mkdtemp(prefix="alert_senders_check_")
os.environ["LOG_DIR"] = os.path.join(TMP, "logs")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.test import APIClient
from core import mailer, secret_box
from core.models import AlertSenderDtl, EmailLog, MailAlertDtl, SysAuditLog, UserPermission, UserProfile
from core.permissions import invalidate_user_access

SECRET = "Sup3r-Secret-Pw!"
sent, down = [], set()


def fake_deliver(subject, html, text, to, cc, bcc, from_name, smtp, inline_images):
    if smtp.get("broken"):
        raise RuntimeError(smtp["broken"])
    if smtp["host"] in down:
        raise ConnectionError(f"{smtp['host']} refused the connection")
    sent.append({"host": smtp["host"], "port": smtp["port"], "user": smtp["user"], "password": smtp["password"], "from": smtp["from_address"], "tls": smtp["use_tls"], "ssl": smtp["use_ssl"], "to": to})


# the real _deliver does the "broken" test itself; the fake copies it and records what it was given
_real_deliver = mailer._deliver
mailer._deliver = fake_deliver


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


def send(alert_id, **kw):
    sent.clear()
    return mailer.send_scheduled_email("S", "<p>x</p>", "x", to=["a@example.test"], trigger_code="t.t", alert_id=alert_id, **kw)


MK = "masters.alert_senders"
log_stream = io.StringIO()
h = logging.StreamHandler(log_stream); logging.getLogger().addHandler(h); logging.getLogger("seros.scheduler").addHandler(h)
try:
    with transaction.atomic():
        AlertSenderDtl.objects.all().delete()
        a1 = MailAlertDtl.objects.filter(alert_id__gt=0).order_by("alert_id")[0]; a2 = MailAlertDtl.objects.filter(alert_id__gt=0).order_by("alert_id")[1]
        settings.BIRTHDAY_EMAIL_HOST = ""
        settings.EMAIL_HOST = "smtp.default.test"

        print("A. nothing changes when an alert has no sender")
        r = send(a1.pk)
        ok("the default account sends it, as before", r["ok"] and r["smtp_used"] == "default" and sent[0]["host"] == "smtp.default.test" and not r["fell_back"], str(r))
        settings.BIRTHDAY_EMAIL_HOST = "smtp.env.test"; settings.BIRTHDAY_EMAIL_FROM = "env@example.test"
        r = send(a1.pk)
        ok("with an environment account, that one sends it, as before", r["smtp_used"] == "designated" and sent[0]["host"] == "smtp.env.test" and sent[0]["from"] == "env@example.test")
        down.add("smtp.env.test"); r = send(a1.pk)
        ok("and when it refuses the default account takes over, marked as a fallback, as before", r["ok"] and r["smtp_used"] == "default" and r["fell_back"] and EmailLog.objects.order_by("-pk").first().used_fallback)
        down.clear()
        r = send(a1.pk, designated=False)
        ok("designated=False still means the default account only", r["smtp_used"] == "default" and sent[0]["host"] == "smtp.default.test")
        r = send(None)
        ok("a mail with no alert behaves the same", r["ok"] and r["smtp_used"] == "designated")

        print("B. an alert with its own sender")
        row = AlertSenderDtl.objects.create(alert=a1, mail_host="smtp.sender.test", mail_port=587, mail_security="T", mail_user_name="hr_user", password=secret_box.encrypt(SECRET), from_address="hr@example.test", is_active="Y", cr_user_id=0, cr_dt=datetime.datetime.now())
        ok("the password is encrypted at rest", row.password.startswith("enc1:") and SECRET not in row.password)
        r = send(a1.pk)
        s = sent[0]
        ok("the alert's own account sends it first", r["ok"] and r["smtp_used"] == "alert" and not r["fell_back"] and s["host"] == "smtp.sender.test", str(r))
        ok("with the port, security, user, decrypted password and From address from the row", s["port"] == 587 and s["tls"] and not s["ssl"] and s["user"] == "hr_user" and s["password"] == SECRET and s["from"] == "hr@example.test", str(s))
        ok("another alert is not affected", send(a2.pk)["smtp_used"] == "designated" and sent[0]["host"] == "smtp.env.test")
        down.add("smtp.sender.test"); r = send(a1.pk)
        ok("if the alert's account refuses, the environment account is tried next", r["ok"] and r["smtp_used"] == "designated" and r["fell_back"])
        down.add("smtp.env.test"); r = send(a1.pk)
        ok("and then the default account", r["ok"] and r["smtp_used"] == "default" and r["fell_back"])
        down.add("smtp.default.test"); r = send(a1.pk)
        ok("if all three refuse the mail fails with every reason, logged once", not r["ok"] and r["error"].count("refused") == 3 and EmailLog.objects.filter(pk=r["email_log_id"], success=False).exists(), r["error"][:200])
        down.clear()
        ok("the EmailLog row records the From address that was used", EmailLog.objects.get(pk=send(a1.pk)["email_log_id"]).from_address == "hr@example.test")
        ok("a different security setting is respected (SSL)", (AlertSenderDtl.objects.filter(pk=row.pk).update(mail_security="S"), send(a1.pk)["ok"])[1] and sent[0]["ssl"] and not sent[0]["tls"])
        AlertSenderDtl.objects.filter(pk=row.pk).update(mail_security="T")
        AlertSenderDtl.objects.filter(pk=row.pk).update(is_active="N")
        ok("an inactive row is ignored", send(a1.pk)["smtp_used"] == "designated")
        AlertSenderDtl.objects.filter(pk=row.pk).update(is_active="Y", password="enc1:not-a-valid-token")
        r = send(a1.pk)
        ok("a stored password that cannot be read is skipped, not fatal", r["ok"] and r["smtp_used"] == "designated" and r["fell_back"])
        ok("and the setup panel says so", mailer.sender_info(a1.pk)["broken"] and "CREDENTIAL_KEY" in mailer.sender_info(a1.pk)["broken"])
        AlertSenderDtl.objects.filter(pk=row.pk).update(password="plain-text-from-sql")
        ok("a plain-text password put in by hand (SQL) still works", send(a1.pk)["smtp_used"] == "alert" and sent[0]["password"] == "plain-text-from-sql")
        AlertSenderDtl.objects.filter(pk=row.pk).update(password="", mail_user_name="")
        ok("no user and no password means no sign-in", send(a1.pk)["smtp_used"] == "alert" and sent[0]["user"] is None and sent[0]["password"] is None)
        AlertSenderDtl.objects.filter(pk=row.pk).update(password=secret_box.encrypt(SECRET), mail_user_name="hr_user")
        info = mailer.sender_info(a1.pk)
        ok("the setup panel gets server, port, user and From address, never the password", set(info) == {"host", "port", "user", "from_address", "broken"} and SECRET not in json.dumps(info))
        row.delete()

        print("C. the real delivery refuses an unreadable account")
        mailer._deliver = _real_deliver
        try:
            _real_deliver("S", "h", "t", ["a@b.co"], [], [], "", {"host": "x", "port": 25, "user": None, "password": None, "use_tls": False, "use_ssl": False, "from_address": "f@b.co", "broken": "bad key"}, None)
            ok("_deliver raises for a broken account", False)
        except RuntimeError as exc:
            ok("_deliver raises for a broken account", "bad key" in str(exc))
        mailer._deliver = fake_deliver

        print("D. the page: rights, validation and the secret")
        full = mk("zzas1", {MK: ("view", "add", "edit", "delete"), "masters.mail_alerts": ("view",)})
        viewer = mk("zzas2", {MK: ("view",)})
        nobody = mk("zzas3", {})
        body = dict(alert=a1.pk, mail_host="smtp.page.test", mail_port=25, mail_security="N", mail_user_name="u", password=SECRET, from_address="page@example.test", is_active="Y")
        ok("no rights: nothing opens", nobody.get("/api/masters/alert-senders/").status_code == 403)
        ok("view-only can read but not add, change or delete", viewer.get("/api/masters/alert-senders/").status_code == 200 and viewer.post("/api/masters/alert-senders/", body, format="json").status_code == 403)
        r = full.post("/api/masters/alert-senders/", body, format="json")
        ok("a sender can be added", r.status_code == 201, str(r.content[:300]))
        j = r.json(); sid = j["alert_sender_dtl_id"]
        ok("the password is never in the reply, only whether one is set", "password" not in j and j["has_password"] is True and SECRET not in r.content.decode())
        ok("it is stored encrypted", AlertSenderDtl.objects.get(pk=sid).password.startswith("enc1:"))
        lst = full.get("/api/masters/alert-senders/").content.decode(); one = full.get(f"/api/masters/alert-senders/{sid}/").content.decode()
        ok("the list and the single record never carry the password", SECRET not in lst and SECRET not in one and "enc1:" not in lst and "enc1:" not in one)
        ok("the alert's name is shown", '"alert_name"' in one)
        audit = json.dumps(list(SysAuditLog.objects.filter(entity=MK).values_list("changes", "record_label", flat=False)), default=str)
        ok("the audit trail records the add without the password, readable or encrypted", "smtp.page.test" in audit and SECRET not in audit and "enc1:" not in audit, audit[:200])
        before = AlertSenderDtl.objects.get(pk=sid).password
        r = full.patch(f"/api/masters/alert-senders/{sid}/", {"password": "", "mail_host": "smtp.page2.test"}, format="json")
        ok("a blank password on an edit keeps the saved one", r.status_code == 200 and AlertSenderDtl.objects.get(pk=sid).password == before and AlertSenderDtl.objects.get(pk=sid).mail_host == "smtp.page2.test")
        r = full.patch(f"/api/masters/alert-senders/{sid}/", {"password": "new-secret-Pw"}, format="json")
        after = AlertSenderDtl.objects.get(pk=sid).password
        ok("a new password replaces it, encrypted", r.status_code == 200 and after != before and secret_box.decrypt(after) == "new-secret-Pw" and "new-secret-Pw" not in r.content.decode())
        audit = json.dumps(list(SysAuditLog.objects.filter(entity=MK).values_list("changes", flat=True)), default=str)
        ok("and the audit trail never holds it either", "new-secret-Pw" not in audit and SECRET not in audit and "enc1:" not in audit)
        ok("a second active sender for the same alert is refused", full.post("/api/masters/alert-senders/", {**body, "from_address": "two@example.test"}, format="json").status_code == 400)
        ok("a second one for another alert, or an inactive one for the same alert, is fine", full.post("/api/masters/alert-senders/", {**body, "alert": a2.pk}, format="json").status_code == 201 and full.post("/api/masters/alert-senders/", {**body, "is_active": "N", "from_address": "off@example.test"}, format="json").status_code == 201)
        ok("switching an inactive one on while another is active is refused", full.patch(f"/api/masters/alert-senders/{AlertSenderDtl.objects.filter(alert=a1, is_active='N').first().pk}/", {"is_active": "Y"}, format="json").status_code == 400)
        ok("a bad server name, port or From address is refused", full.post("/api/masters/alert-senders/", {**body, "alert": a2.pk, "is_active": "N", "mail_host": "bad host/x"}, format="json").status_code == 400
           and full.post("/api/masters/alert-senders/", {**body, "alert": a2.pk, "is_active": "N", "mail_port": 70000}, format="json").status_code == 400
           and full.post("/api/masters/alert-senders/", {**body, "alert": a2.pk, "is_active": "N", "from_address": "not-an-address"}, format="json").status_code == 400)
        ok("view-only cannot delete", viewer.delete(f"/api/masters/alert-senders/{sid}/").status_code == 403)
        ok("it is not exportable (no Export right is offered)", full.get("/api/masters/alert-senders/export/").status_code in (403, 404))
        ok("the mailer now uses the saved row", send(a1.pk)["smtp_used"] == "alert" and sent[0]["host"] == "smtp.page2.test" and sent[0]["password"] == "new-secret-Pw")
        ok("deleting needs the Delete right and works", full.delete(f"/api/masters/alert-senders/{sid}/").status_code == 204 and send(a1.pk)["smtp_used"] == "designated")

        print("E. no password in any log")
        send(a1.pk)
        text = log_stream.getvalue()
        ok("the logs hold no password", SECRET not in text and "new-secret-Pw" not in text)
        ok("the Email Log holds no password", not EmailLog.objects.filter(error__contains=SECRET).exists() and not EmailLog.objects.filter(error__contains="new-secret-Pw").exists())
        raise Rollback()
except Rollback:
    pass
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print()
print("FAILED: " + ", ".join(fails) if fails else "all checks passed")
sys.exit(1 if fails else 0)
