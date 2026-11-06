"""Checks the Mail Redirect page's API (App Admin only): a non-admin is refused, saving needs the typed phrase, switching on needs an address and valid addresses, the saved
row wins over .env and is used by the sender, and with no row .env still decides. Everything runs in a transaction that is rolled back.

    cd backend
    .venv/bin/python scripts/check_mail_redirect_page.py
"""
import os, sys, django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.db import transaction
from rest_framework.test import APIClient
from core import mailer
from core.models import MailRedirectSetting, UserProfile
from core.permissions import invalidate_user_access

settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
settings.EMAIL_USE_CONSOLE = False
mail.outbox = []
fails = []
PH = "CONFIRM REDIRECT UPDATE"


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
    c = APIClient(HTTP_HOST="localhost"); c.force_authenticate(u); return c


URL = "/api/admin/mail-redirect/"
try:
    with transaction.atomic():
        MailRedirectSetting.objects.all().delete(); mailer.clear_redirect_cache()
        settings.MAIL_REDIRECT, settings.MAIL_REDIRECT_TO = True, ["env@test.example"]
        adm, usr = mk("zz_redir_admin", True), mk("zz_redir_user", False)
        ok("a non-admin is refused (read and save)", usr.get(URL).status_code == 403 and usr.put(URL, {"enabled": False, "redirect_to": [], "confirm": PH}, format="json").status_code == 403)
        g = adm.get(URL).json()
        ok("with no saved row, .env decides", g["on"] and g["to"] == ["env@test.example"] and g["source"] == "env")
        ok("saving without the phrase is refused", adm.put(URL, {"enabled": False, "redirect_to": [], "confirm": "yes"}, format="json").status_code == 400 and not MailRedirectSetting.objects.exists())
        ok("switching on with no address is refused", adm.put(URL, {"enabled": True, "redirect_to": [], "confirm": PH}, format="json").status_code == 400)
        ok("a bad address is refused", adm.put(URL, {"enabled": True, "redirect_to": ["not-an-address"], "confirm": PH}, format="json").status_code == 400)
        r = adm.put(URL, {"enabled": True, "redirect_to": "a@test.example\nb@test.example, a@test.example", "confirm": PH}, format="json")
        j = r.json()
        ok("saved: two addresses, duplicates dropped, source is the page", r.status_code == 200 and j["on"] and j["to"] == ["a@test.example", "b@test.example"] and j["source"] == "page" and j["changed_by"], str(j))
        mail.outbox.clear()
        mailer.send_notification_email("Hi", "<p>x</p>", to=["real@seros.co.in"], is_html=True, trigger="check", trigger_code="check.redirectpage")
        ok("the sender uses the page's addresses, not .env", len(mail.outbox) == 1 and mail.outbox[0].to == ["a@test.example", "b@test.example"] and mail.outbox[0].subject.startswith("[Redirected]"))
        r = adm.put(URL, {"enabled": False, "redirect_to": ["a@test.example"], "confirm": PH}, format="json")
        mail.outbox.clear()
        mailer.send_notification_email("Hi", "<p>x</p>", to=["real@seros.co.in"], is_html=True, trigger="check", trigger_code="check.redirectpage")
        ok("switched off on the page beats .env being on: mail goes to the real person", r.status_code == 200 and mail.outbox and mail.outbox[0].to == ["real@seros.co.in"])
        raise Rollback
except Rollback:
    pass
except ImportError:
    pass
mailer.clear_redirect_cache()
print("\nFAILED: " + ", ".join(fails) if fails else "\nall checks passed")
sys.exit(1 if fails else 0)
