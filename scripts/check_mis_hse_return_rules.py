"""Checks the MIS Monthly HSE Return validation rules through the real API.

    cd backend
    .venv/bin/python scripts/check_mis_hse_return_rules.py

Runs every request inside one transaction that is rolled back at the end, so
nothing is saved. Needs the normal dev data. Exits with status 1 if any check fails.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

import datetime

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.test import APIClient

from core.models import MisMonthlyHseReturnsHdr, MstCostCentre, MstHseActivity, MstHseConsumable, MstHseManhoursParty, MstHseMeeting

URL = "/api/qhse/mis-hse-return/"
FAILED = []


def check(name, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


def run():
    client = APIClient(HTTP_HOST="localhost")
    client.force_authenticate(get_user_model().objects.filter(is_superuser=True).first())
    first = datetime.date.today().replace(day=1)

    print("Header")
    used = set(MisMonthlyHseReturnsHdr.objects.filter(report_month="2015-01-01").values_list("cost_centre_id", flat=True))
    cc = MstCostCentre.objects.exclude(rig=None).exclude(pk__in=used).first()
    body = {"cost_centre": cc.pk, "report_no": "ZZ-1", "report_month": "2015-01-01"}
    r = client.post(URL, body, format="json")
    check("a return is created", r.status_code == 201, r.content[:200])
    pk = r.json()["monthly_hse_returns_hdr_id"]
    check("the same cost centre and month is refused", client.post(URL, body, format="json").status_code == 400)
    other = MstCostCentre.objects.filter(rig=cc.rig).exclude(pk=cc.pk).first()
    if other is None:  # a second cost centre on the same rig, inside the rolled-back transaction
        other = MstCostCentre.objects.get(pk=cc.pk)
        other.pk = None
        other.cost_centre_name = "ZZ rule check"
        other.save()
    r = client.post(URL, {**body, "cost_centre": other.pk}, format="json")
    check("the same rig and month is refused", r.status_code == 400 and "already has" in str(r.json().get("report_month")), r.content[:200])
    check("the current month is refused", client.post(URL, {**body, "report_month": first.isoformat(), "report_no": "ZZ-2"}, format="json").status_code == 400)

    base = f"{URL}{pk}/"
    put = lambda path, data: client.put(f"{base}{path}/", data, format="json")
    row_err = lambda r, rid, field: r.status_code == 400 and field in r.json().get("row_errors", {}).get(str(rid), {})

    print("Manhours")
    party = MstHseManhoursParty.objects.first().pk
    mk = lambda **o: {"rows": [{"hse_manhours_party_id": party, "no_of_personnel": 5, "hours_worked": 12, **o}]}
    check("a valid row is saved", put("manhours", mk()).status_code == 200)
    check("a blank personnel is accepted", put("manhours", mk(no_of_personnel=None)).status_code == 200)
    check("a decimal 10.5 hours is accepted", put("manhours", mk(hours_worked="10.5")).status_code == 200)
    for name, over, field in (
        ("blank hours is refused", {"hours_worked": None}, "hours_worked"),
        ("negative hours is refused", {"hours_worked": -1}, "hours_worked"),
        ("text hours is refused", {"hours_worked": "abc"}, "hours_worked"),
        ("hours with 3 decimals is refused", {"hours_worked": "1.234"}, "hours_worked"),
        ("hours over 99.99 is refused", {"hours_worked": 100}, "hours_worked"),
        ("negative personnel is refused", {"no_of_personnel": -2}, "no_of_personnel"),
        ("decimal personnel is refused", {"no_of_personnel": "1.5"}, "no_of_personnel"),
    ):
        r = put("manhours", mk(**over))
        check(name, row_err(r, party, field), r.content[:200])
    r = put("manhours", mk(hours_worked=-1))
    check("the message names the party", MstHseManhoursParty.objects.get(pk=party).hse_manhours_party_name in r.json()["detail"])

    print("LTI Free Days")
    check("LTI Free Days 0 is accepted", put("incidents", {"lti_free_days": 0}).status_code == 200)
    for name, v in (("blank", None), ("negative", -1), ("decimal", "2.5"), ("text", "x")):
        check(f"LTI Free Days {name} is refused", "lti_free_days" in put("incidents", {"lti_free_days": v}).json())

    print("Meetings")
    m = MstHseMeeting.objects.first().pk
    mm = lambda t, e, c: {"rows": [{"hse_meeting_id": m, "total_meetings": t, "total_seros_employees": e, "total_contractors": c}]}
    check("meetings with attendees are accepted", put("meetings", mm(2, 5, 0)).status_code == 200)
    check("0 meetings with 0 attendees is accepted", put("meetings", mm(0, 0, 0)).status_code == 200)
    check("a blank row is ignored", put("meetings", mm(None, None, None)).status_code == 200)
    for name, args, field in (
        ("a half-filled row is refused", (2, None, None), "total_seros_employees"),
        ("negative meetings is refused", (-1, 1, 1), "total_meetings"),
        ("decimal attendees is refused", (1, "1.5", 0), "total_seros_employees"),
        ("meetings with no attendees is refused", (3, 0, 0), "total_contractors"),
        ("0 meetings with employees is refused", (0, 4, 0), "total_seros_employees"),
        ("0 meetings with contractors is refused", (0, 0, 4), "total_contractors"),
    ):
        r = put("meetings", mm(*args))
        check(name, row_err(r, m, field), r.content[:200])

    print("Activities")
    a = MstHseActivity.objects.first().pk
    ma = lambda t, e, c: {"rows": [{"hse_activity_id": a, "total_activities": t, "seros_emp_count": e, "contractor_count": c}]}
    check("a complete row is accepted", put("activities", ma(3, 4, 5)).status_code == 200)
    check("a blank row is ignored", put("activities", ma(None, None, None)).status_code == 200)
    check("a half-filled row is refused", row_err(put("activities", ma(3, None, 1)), a, "seros_emp_count"))
    check("a negative number is refused", row_err(put("activities", ma(-3, 1, 1)), a, "total_activities"))

    print("Environment")
    c = MstHseConsumable.objects.first().pk
    me = lambda q, rem="": {"rows": [{"hse_consumable_id": c, "total_quantity": q, "remarks": rem}]}
    check("a quantity is accepted", put("environment", me("12.50")).status_code == 200)
    check("0 is accepted", put("environment", me(0)).status_code == 200)
    check("a blank row is ignored", put("environment", me(None)).status_code == 200)
    check("remarks without a quantity are refused", row_err(put("environment", me(None, "note")), c, "total_quantity"))
    check("a negative quantity is refused", row_err(put("environment", me(-1)), c, "total_quantity"))
    check("text is refused", row_err(put("environment", me("abc")), c, "total_quantity"))
    check("3 decimals is refused", row_err(put("environment", me("1.234")), c, "total_quantity"))

    print("Nothing is stored for refused or blank rows")
    hdr = MisMonthlyHseReturnsHdr.objects.get(pk=pk)
    check("only the saved rows exist", hdr.meetings.count() == 1 and hdr.hse_activities.count() == 1 and hdr.environment_rows.count() == 1)


if __name__ == "__main__":
    with transaction.atomic():
        run()
        transaction.set_rollback(True)
    print()
    print("FAILED: " + ", ".join(FAILED) if FAILED else "All checks passed. Nothing was saved.")
    sys.exit(1 if FAILED else 0)
