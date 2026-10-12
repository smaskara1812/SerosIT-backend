"""Checks the Corrective Actions validation rules through the real API.

    cd backend
    .venv/bin/python scripts/check_corrective_actions_rules.py

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

from core.models import OtherQhseAction

URL = "/api/qhse/corrective-actions/"
FAILED = []


def check(name, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


def keys(resp):
    try:
        return set(resp.json().keys())
    except Exception:
        return set()


def run():
    client = APIClient(HTTP_HOST="localhost")
    client.force_authenticate(get_user_model().objects.filter(is_superuser=True).first())
    src = OtherQhseAction.objects.order_by("-pk").first()
    day = datetime.date(2025, 10, 1)
    n = [0]

    def payload(**over):
        n[0] += 1
        base = {
            "qhse_category": src.qhse_category_id, "icr_no": f"ZZ-{n[0]}", "other_qhse_action_dt": day.isoformat(), "rig": src.rig_id,
            "action_recommended": "Rule check", "action_party": "Rule check", "target_date": (day + datetime.timedelta(days=30)).isoformat(),
        }
        base.update(over)
        return base

    post = lambda **over: client.post(URL, payload(**over), format="json")

    print("Create")
    first = client.post(URL, payload(icr_no="ZZ-ICR"), format="json")
    check("a valid record is accepted", first.status_code == 201, first.content[:200])
    check("it starts Open", first.json().get("action_status") == "OP")
    r = post(icr_no="zz-icr")
    check("the same ICR No. in other capitals is refused", r.status_code == 400 and "icr_no" in keys(r), r.content[:150])
    r = post(icr_no="  ZZ-ICR  ")
    check("the same ICR No. with spaces around it is refused", r.status_code == 400 and "icr_no" in keys(r))
    check("a different ICR No. is accepted", post(icr_no="ZZ-ICR2").status_code == 201)
    check("the same ICR No. on another rig is refused too (unique across all)", post(icr_no="ZZ-ICR", rig=src.rig_id).status_code == 400)

    print("Dates and required fields")
    future = (datetime.date.today() + datetime.timedelta(days=3)).isoformat()
    r = post(other_qhse_action_dt=future, target_date=future)
    check("a future Date is refused", r.status_code == 400 and "other_qhse_action_dt" in keys(r))
    r = post(target_date=(day - datetime.timedelta(days=1)).isoformat())
    check("a Target Date before the Date is refused", r.status_code == 400 and "target_date" in keys(r))
    check("a Target Date equal to the Date is accepted", post(target_date=day.isoformat()).status_code == 201)
    for name in ("qhse_category", "icr_no", "rig", "action_recommended", "action_party", "target_date"):
        p = payload()
        p.pop(name)
        r = client.post(URL, p, format="json")
        check(f"a missing {name} is refused", r.status_code == 400 and name in keys(r), r.content[:100])

    print("Closing and the lock")
    pk = first.json()["other_qhse_action_id"]
    r = client.patch(f"{URL}{pk}/", {"completion_dt": (day - datetime.timedelta(days=1)).isoformat()}, format="json")
    check("a closure date before the Date is refused", r.status_code == 400 and "completion_dt" in keys(r))
    r = client.patch(f"{URL}{pk}/", {"action_status": "CL"}, format="json")
    check("Closed without a closure date is refused", r.status_code == 400 and "completion_dt" in keys(r))
    check("an unknown status is refused", client.patch(f"{URL}{pk}/", {"action_status": "XX"}, format="json").status_code == 400)
    check("In Process is accepted", client.patch(f"{URL}{pk}/", {"action_status": "IN"}, format="json").json().get("action_status") == "IN")
    r = client.patch(f"{URL}{pk}/", {"completion_dt": (day + datetime.timedelta(days=5)).isoformat()}, format="json")
    check("a closure date closes the record", r.status_code == 200 and r.json().get("action_status") == "CL", r.content[:150])
    check("a Closed record can't be edited", client.patch(f"{URL}{pk}/", {"action_taken": "x"}, format="json").status_code == 400)
    check("a Closed record can't be deleted", client.delete(f"{URL}{pk}/").status_code == 400)

    print("Existing records are left as they are")
    old = OtherQhseAction.objects.exclude(action_status="CL").first()
    if old is None:
        print("  skip  no open record")
    else:
        data = client.get(f"{URL}{old.pk}/").json()
        keep = {k: data[k] for k in payload() if k in data}
        keep["action_taken"] = "edited by rule check"
        r = client.patch(f"{URL}{old.pk}/", keep, format="json")
        check("an open old record can still be edited for something else", r.status_code == 200, r.content[:200])


if __name__ == "__main__":
    with transaction.atomic():
        run()
        transaction.set_rollback(True)
    print()
    print("FAILED: " + ", ".join(FAILED) if FAILED else "All checks passed. Nothing was saved.")
    sys.exit(1 if FAILED else 0)
