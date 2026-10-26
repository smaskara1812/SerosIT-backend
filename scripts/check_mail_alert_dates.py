"""Checks the From and To dates on Alert To Users (Masters): the form accepts a To date, a To before the From is refused, the list can be
filtered to the recipients receiving the alert now, and the mailer really leaves out an expired recipient. One rolled-back transaction.

    cd backend
    .venv/bin/python scripts/check_mail_alert_dates.py
"""
import os, sys, django, datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.test import APIClient
from core.models import MailAlertDtl, MailAlertToUser
from core.notification_triggers import resolve_alert_recipients


class Rollback(Exception):
    pass


fails = []


def ok(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {detail}" if not cond else ""))
    if not cond:
        fails.append(name)


try:
    with transaction.atomic():
        U = get_user_model()
        c = APIClient(HTTP_HOST="localhost"); c.force_authenticate(U.objects.create_superuser(username="zzma0", password="x"))
        alert = MailAlertDtl.objects.filter(alert_id__gt=0).order_by("alert_id").first()
        today = datetime.date.today(); d = lambda n: (today + datetime.timedelta(days=n)).isoformat()
        base = {"alert": alert.alert_id, "recipient_name": "Check Person", "addressee_type": "T", "mail_alert_order": 1}
        url = "/api/masters/mail-alert-to-users/"

        def post(email, frm, to):
            return c.post(url, {**base, "email_addr": email, "mail_alert_from": frm, "mail_alert_to": to}, format="json")

        r = post("zz-before@example.com", d(0), d(-3))
        ok("a To date before the From date is refused, on the To field", r.status_code == 400 and "mail_alert_to" in r.json(), str(r.content[:160]))
        ok("a To equal to the From date is allowed (a one-day recipient)", post("zz-oneday@example.com", d(0), d(0)).status_code == 201)
        cur = post("zz-open@example.com", d(-10), None); ok("a recipient with no To date is accepted", cur.status_code == 201, str(cur.content[:160]))
        ok("the To date is returned by the API", "mail_alert_to" in cur.json() and cur.json()["mail_alert_to"] is None)
        gone = post("zz-expired@example.com", d(-30), d(-1)); ok("a recipient whose To has passed is accepted", gone.status_code == 201, str(gone.content[:160]))
        later = post("zz-later@example.com", d(5), d(30)); ok("a From date in the future is allowed", later.status_code == 201, str(later.content[:160]))
        # editing something else on an old row must not trip the date rule
        old = MailAlertToUser.objects.get(pk=gone.json()["mail_alert_to_user_id"])
        ok("editing the To date later than the From works", c.patch(f"{url}{old.pk}/", {"mail_alert_to": d(10)}, format="json").status_code == 200)
        ok("moving the To before the From is refused on edit too", c.patch(f"{url}{old.pk}/", {"mail_alert_to": d(-90)}, format="json").status_code == 400)
        c.patch(f"{url}{old.pk}/", {"mail_alert_to": d(-1)}, format="json")

        print("the list filter and the mailer")
        def emails(q):
            res = c.get(url + q + ("&" if "?" in q else "?") + f"alert={alert.alert_id}&page_size=500").json()
            return {x["email_addr"] for x in res.get("results", [])}
        act, ina = emails("?active=Y"), emails("?active=N")
        ok("Active shows the open one and the one ending today", {"zz-open@example.com", "zz-oneday@example.com"} <= act and "zz-expired@example.com" not in act, str(sorted(act))[:200])
        ok("Inactive shows the one whose To has passed", "zz-expired@example.com" in ina and "zz-open@example.com" not in ina)
        got = resolve_alert_recipients(alert.alert_id)["to"]
        ok("the mailer sends to the open and one-day recipients", "zz-open@example.com" in got and "zz-oneday@example.com" in got)
        ok("the mailer leaves out the expired one and the one not started yet", "zz-expired@example.com" not in got and "zz-later@example.com" not in got)
        raise Rollback()
except Rollback:
    pass

print()
print("FAILED: " + ", ".join(fails) if fails else "all checks passed")
sys.exit(1 if fails else 0)
