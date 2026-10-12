"""Checks the HSE Drills / Exercises validation rules through the real API.

    cd backend
    .venv/bin/python scripts/check_hse_drill_record_rules.py

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

from core.models import HseDrillRecordHdr, MstHseDrill

URL = "/api/qhse/hse-drill-record/"
EVENTS = "/api/qhse/hse-drill-record-events/"
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
    src = HseDrillRecordHdr.objects.order_by("-drill_dt").first()
    other_drill = MstHseDrill.objects.exclude(pk=src.hse_drill_1_id).first()
    # A fixed past day: after every existing record of the rig (a new drill may not be dated
    # before the rig's latest one) and before now, however many records the checks add.
    start = datetime.datetime(2026, 6, 1, 8, 0)

    def payload(**over):
        base = {
            "rig": src.rig_id, "drill_dt": start.isoformat(), "drill_location": "Rule check", "hse_drill_1": src.hse_drill_1_id,
            "head_count": 20, "control_room_on_shore": "N", "initiated_by_fs_emp_1": src.initiated_by_fs_emp_1_id,
            "initial_response_time": "2.00", "no_of_participants": 15, "drill_muster": "5.00", "total_time_of_drill": "20.00",
            "approved_by_oim_fs_emp": src.approved_by_oim_fs_emp_id, "revision_value": 0,
        }
        base.update(over)
        return base

    n = [0]

    def post(**over):
        n[0] += 1
        over.setdefault("drill_dt", (start + datetime.timedelta(minutes=n[0] * 7)).isoformat())
        return client.post(URL, payload(**over), format="json")

    print("Dates and values")
    first = client.post(URL, payload(), format="json")
    check("a valid record is accepted", first.status_code == 201, first.content[:200])
    future = (datetime.datetime.now() + datetime.timedelta(days=2)).isoformat()
    r = post(drill_dt=future)
    check("a future drill date/time is refused", r.status_code == 400 and "drill_dt" in keys(r))
    for name, over, key in (
        ("Head Count of 0", {"head_count": 0}, "head_count"),
        ("No. of Participants of 0", {"no_of_participants": 0}, "no_of_participants"),
        ("participants above the head count", {"no_of_participants": 30}, "no_of_participants"),
        ("Initial Response Time of 0", {"initial_response_time": "0.00"}, "initial_response_time"),
        ("Drill Muster of 0", {"drill_muster": "0.00"}, "drill_muster"),
        ("Total Time of Drill of 0", {"total_time_of_drill": "0.00"}, "total_time_of_drill"),
        ("seconds above 59", {"initial_response_time": "2.75"}, "initial_response_time"),
        ("Control Room 'Q'", {"control_room_on_shore": "Q"}, "control_room_on_shore"),
    ):
        r = post(**over)
        check(f"{name} is refused", r.status_code == 400 and key in keys(r), r.content[:150])
    check("0.30 (30 seconds) is a valid Muster time", post(drill_muster="0.30").status_code == 201)
    check("Control Room 'Y' is accepted", post(control_room_on_shore="Y").status_code == 201)

    print("Unique drill")
    same_time = (start + datetime.timedelta(hours=10)).isoformat()
    check("first record at a given time is accepted", post(drill_dt=same_time).status_code == 201)
    r = post(drill_dt=same_time)
    check("the same rig, time and drill type again is refused", r.status_code == 400 and "drill_dt" in keys(r), r.content[:150])
    check("a different drill type at that time is accepted", post(drill_dt=same_time, hse_drill_1=other_drill.pk).status_code == 201)
    check("a different time is accepted", post(drill_dt=(start + datetime.timedelta(hours=11)).isoformat()).status_code == 201)

    print("Events")
    hdr = first.json()["drill_record_hdr_id"]
    when = start + datetime.timedelta(minutes=30)
    ev = lambda t, d="Rule check event": client.post(EVENTS, {"hdr": hdr, "drill_rec_event_time": t.isoformat(), "drill_rec_event_desc": d}, format="json")
    check("a first event is accepted", ev(when).status_code == 201)
    r = ev(when)
    check("a second event at the same time is refused", r.status_code == 400 and "drill_rec_event_time" in keys(r), r.content[:150])
    check("an event at another time is accepted", ev(when + datetime.timedelta(minutes=5)).status_code == 201)
    check("an event with no description is refused", ev(when + datetime.timedelta(minutes=9), "").status_code == 400)

    print("Existing records are left as they are")
    old = HseDrillRecordHdr.objects.filter(control_room_on_shore="").first() or src
    data = client.get(f"{URL}{old.pk}/").json()
    keep = {k: data[k] for k in payload() if k in data}
    keep["control_room_on_shore"] = keep.get("control_room_on_shore") or "N"  # the form shows blank as No
    keep["drill_location"] = "Edited"
    r = client.patch(f"{URL}{old.pk}/", keep, format="json")
    check("an old record can still be edited for something else", r.status_code == 200, r.content[:200])


if __name__ == "__main__":
    with transaction.atomic():
        run()
        transaction.set_rollback(True)
    print()
    print("FAILED: " + ", ".join(FAILED) if FAILED else "All checks passed. Nothing was saved.")
    sys.exit(1 if FAILED else 0)
