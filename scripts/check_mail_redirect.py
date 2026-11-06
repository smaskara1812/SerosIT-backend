"""Checks the mail redirect (MAIL_REDIRECT / MAIL_REDIRECT_TO in .env): with it on, every mail the application sends goes only to the redirect addresses (several, comma
separated), whoever the recipients are in the data, and says in its subject and body who it was meant for; with it on and no address nothing is sent; with it off nothing
changes. Both ways of sending (the notification one and the automatic-mail one) are checked, with Cc, Bcc, attachments, HTML and plain text. Nothing is really sent
(Django's in-memory mail box is used) and the Email Log rows made are removed.

    cd backend
    .venv/bin/python scripts/check_mail_redirect.py
"""
import os, sys, django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from django.conf import settings
from django.core import mail
from django.db import transaction
from core import mailer
from core.models import EmailLog

settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
settings.EMAIL_USE_CONSOLE = False
fails = []
mail.outbox = []


def ok(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {detail}" if not cond else ""))
    if not cond:
        fails.append(name)


class Rollback(Exception):
    pass


def notify(**kw):
    mail.outbox.clear()
    mailer.send_notification_email("Approval needed", "<p>Please approve.</p>", to=["real.to@seros.co.in"], cc=["real.cc@seros.co.in"], bcc=["real.bcc@seros.co.in"], is_html=True, trigger="check", trigger_code="check.redirect", attachments=[("a.txt", b"x", "text/plain")], **kw)
    return list(mail.outbox)


def scheduled(**kw):
    mail.outbox.clear()
    res = mailer.send_scheduled_email("Daily report", "<html><body><p>Hello</p></body></html>", "Hello", to=["real.to@seros.co.in"], cc=["real.cc@seros.co.in"], bcc=["real.bcc@seros.co.in"], trigger="check", trigger_code="check.redirect", attachments=[("r.xlsx", b"y", "application/octet-stream")], **kw)
    return res, list(mail.outbox)


try:
    with transaction.atomic():
        print("Off")
        settings.MAIL_REDIRECT, settings.MAIL_REDIRECT_TO = False, ["me@test.example"]
        out = notify()
        ok("notification mail unchanged: real To, Cc, Bcc and subject", len(out) == 1 and out[0].to == ["real.to@seros.co.in"] and out[0].cc == ["real.cc@seros.co.in"] and out[0].bcc == ["real.bcc@seros.co.in"] and out[0].subject == "Approval needed")
        res, out = scheduled()
        ok("automatic mail unchanged", res["ok"] and out[0].to == ["real.to@seros.co.in"] and out[0].subject == "Daily report" and "Redirected" not in out[0].body)

        print("On, two addresses (comma separated in .env)")
        os.environ["MAIL_REDIRECT_TO"] = "a@test.example, b@test.example"
        parsed = [x.strip() for x in os.environ["MAIL_REDIRECT_TO"].split(",") if x.strip()]
        settings.MAIL_REDIRECT, settings.MAIL_REDIRECT_TO = True, parsed
        out = notify()
        m = out[0]
        ok("notification mail goes only to the two redirect addresses, no Cc, no Bcc", len(out) == 1 and m.to == ["a@test.example", "b@test.example"] and not m.cc and not m.bcc, str((m.to, m.cc, m.bcc)))
        ok("its subject says redirected and its body names the intended people", m.subject == "[Redirected] Approval needed" and "real.to@seros.co.in" in m.body and "real.cc@seros.co.in" in m.body and "real.bcc@seros.co.in" in m.body and "Please approve." in m.body, m.body[:200])
        ok("the attachment still goes", len(m.attachments) == 1)
        res, out = scheduled()
        m = out[0]
        html = next(a[0] for a in m.alternatives if a[1] == "text/html")
        ok("automatic mail goes only to the redirect addresses", res["ok"] and m.to == ["a@test.example", "b@test.example"] and not m.cc and not m.bcc)
        ok("HTML gets the notice after the body tag (the page stays valid); the plain text gets it first", html.lower().index("<body") < html.index("Redirected mail.") < html.index("Hello") and m.body.startswith("[Redirected mail]") and "real.to@seros.co.in" in m.body and "real.bcc@seros.co.in" in html)
        ok("subject is marked and the attachment still goes", m.subject == "[Redirected] Daily report" and len(m.attachments) == 1)
        row = EmailLog.objects.filter(trigger_code="check.redirect").order_by("-email_log_id").first()
        ok("the Email Log shows where it really went and keeps the notice in its body", row is not None and "a@test.example" in row.recipients and "real.to@seros.co.in" not in row.recipients and "real.to@seros.co.in" in row.body, str(row and row.recipients))
        mail.outbox.clear()
        r = mailer.send_scheduled_email("No one", "<p>x</p>", "x", to=[], trigger_code="check.redirect")
        ok("a mail with no recipients at all is still 'No recipients', not sent to the redirect address", not r["ok"] and "No recipients" in r["error"] and not mail.outbox)

        print("On, no address")
        settings.MAIL_REDIRECT, settings.MAIL_REDIRECT_TO = True, []
        out = notify()
        ok("nothing is sent (never the real people)", out == [])
        res, out = scheduled()
        ok("automatic mail: not sent, and the error says why", not res["ok"] and out == [] and "MAIL_REDIRECT_TO is empty" in res["error"], str(res))
        row = EmailLog.objects.filter(trigger_code="check.redirect").order_by("-email_log_id").first()
        ok("it is in the Email Log as failed", row is not None and not row.success and "MAIL_REDIRECT_TO" in row.error)
        raise Rollback
except Rollback:
    pass
print("\nFAILED: " + ", ".join(fails) if fails else "\nall checks passed")
sys.exit(1 if fails else 0)
