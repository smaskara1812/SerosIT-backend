"""Checks the Incident Root Cause, Incident Actions, Incident Register and Activity Monitor
rules through the real API.

    cd backend
    .venv/bin/python scripts/check_batch_a_rules.py

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

from core.models import ActivityMonitor, IncidentAction, IncidentRootCause, MstActivity

FAILED = []


def check(name, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  {detail[:240]}" if detail and not ok else ""))
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
    today = datetime.date.today()
    day = lambda n: (today + datetime.timedelta(days=n)).isoformat()

    print("Incident Root Cause")
    RC = "/api/qhse/incident-root-causes/"
    src = IncidentRootCause.objects.exclude(marked_as_deleted="Y").exclude(root_subcause__incident_subcause__istartswith="others").first()
    body = {"incident": src.incident_id, "root_cause": src.root_cause_id, "root_subcause": src.root_subcause_id}
    r = client.post(RC, body, format="json")
    check("the same incident, cause and subcause is refused", r.status_code == 400 and "root_subcause" in keys(r), r.content.decode())
    other = IncidentRootCause.objects.exclude(marked_as_deleted="Y").exclude(pk=src.pk).exclude(root_subcause=src.root_subcause).exclude(root_subcause__incident_subcause__istartswith="others").first()
    r = client.post(RC, {**body, "root_cause": other.root_cause_id, "root_subcause": other.root_subcause_id}, format="json")
    check("a different cause and subcause on the same incident is accepted", r.status_code == 201, r.content.decode())
    new_pk = r.json()["incident_root_cause_id"]
    r = client.patch(f"{RC}{new_pk}/", {"root_cause": src.root_cause_id, "root_subcause": src.root_subcause_id}, format="json")
    check("changing it into an existing one is refused", r.status_code == 400 and "root_subcause" in keys(r), r.content.decode())
    check("saving the original again is not a repeat", client.patch(f"{RC}{src.pk}/", {"root_subcause_others": src.root_subcause_others or None}, format="json").status_code == 200)
    r = client.delete(f"{RC}{new_pk}/", {"deleted_remarks": "short"}, format="json")
    check("a delete reason under 10 characters is refused", r.status_code == 400 and "deleted_remarks" in keys(r), r.content.decode())
    r = client.delete(f"{RC}{new_pk}/", {}, format="json")
    check("a missing delete reason is refused", r.status_code == 400)
    check("a delete reason of 10 characters is accepted", client.delete(f"{RC}{new_pk}/", {"deleted_remarks": "0123456789"}, format="json").status_code == 204)
    r = client.post(RC, body, format="json")
    check("a deleted row no longer counts as a repeat... of itself", r.status_code == 400)  # src is still there

    print("Incident Actions")
    IA = "/api/qhse/incident-actions/"
    act = IncidentAction.objects.exclude(marked_as_deleted="Y").first()
    base = {"incident": act.incident_id, "action_recommended": "Rule check action", "action_party": "Rule party"}
    r = client.post(IA, base, format="json")
    check("a new action is accepted", r.status_code == 201, r.content.decode())
    ia = r.json()["incident_action_id"]
    check("a new action starts Open", r.json()["action_status"] == "OP")
    r = client.patch(f"{IA}{ia}/", {"action_status": "XX"}, format="json")
    check("an unknown action status is refused", r.status_code == 400 and "action_status" in keys(r), r.content.decode())
    for st in ("IN", "OP"):
        check(f"status {st} is accepted", client.patch(f"{IA}{ia}/", {"action_status": st}, format="json").status_code == 200)
    inc_day = act.incident.incident_date.date()
    r = client.patch(f"{IA}{ia}/", {"target_date": (inc_day - datetime.timedelta(days=1)).isoformat()}, format="json")
    check("a target date before the incident is refused", r.status_code == 400 and "target_date" in keys(r))
    r = client.patch(f"{IA}{ia}/", {"completion_dt": (inc_day - datetime.timedelta(days=1)).isoformat()}, format="json")
    check("a closure date before the incident is refused", r.status_code == 400 and "completion_dt" in keys(r))
    r = client.patch(f"{IA}{ia}/", {"completion_dt": inc_day.isoformat()}, format="json")
    check("a closure date on the incident date closes the action", r.status_code == 200 and r.json()["action_status"] == "CL", r.content.decode())
    r = client.post(IA, base, format="json")
    ib = r.json()["incident_action_id"]
    check("an action delete reason under 10 characters is refused", client.delete(f"{IA}{ib}/", {"deleted_remarks": "tiny"}, format="json").status_code == 400)
    check("an action delete reason of 10 characters is accepted", client.delete(f"{IA}{ib}/", {"deleted_remarks": "long enough"}, format="json").status_code == 204)

    print("Incident Register")
    IR = "/api/qhse/incident-register/"
    r = client.get(IR, {"date_from": day(1)})
    check("a From date in the future is refused", r.status_code == 400 and "date_from" in keys(r), r.content.decode())
    r = client.get(IR, {"date_to": day(1)})
    check("a To date in the future is refused", r.status_code == 400 and "date_to" in keys(r))
    r = client.get(IR, {"date_from": day(-1), "date_to": day(-10)})
    check("From after To is refused", r.status_code == 400 and "date_to" in keys(r))
    check("today as To is accepted", client.get(IR, {"date_to": day(0)}).status_code == 200)
    check("no dates is accepted", client.get(IR).status_code == 200)
    check("a normal range is accepted", client.get(IR, {"date_from": day(-400), "date_to": day(-30)}).status_code == 200)
    check("the Excel export refuses a bad range too", client.get(IR + "export/", {"date_from": day(-1), "date_to": day(-5)}).status_code == 400)
    check("the print refuses a bad range too", client.get(IR + "print/", {"date_to": day(2)}).status_code == 400)

    print("Activity Monitor")
    AM = "/api/qhse/activity-monitor/"
    # a fresh Office activity (inside the rolled-back transaction), so no open record blocks it
    activity = MstActivity.objects.exclude(activity_location__in=("V", "R")).first() or MstActivity.objects.first()
    activity.pk = None
    activity.activity_name = "ZZ rule check"
    activity.activity_location = "O"
    activity.save()
    ok_body = {"activity": activity.pk, "scheduled_dt": day(10)}
    r = client.post(AM, {"scheduled_dt": day(10)}, format="json")
    check("no activity is refused on the Activity box", r.status_code == 400 and "activity" in keys(r), r.content.decode())
    r = client.post(AM, {"activity": activity.pk}, format="json")
    check("no schedule date is refused on the Schedule Date box", r.status_code == 400 and "scheduled_dt" in keys(r))
    r = client.post(AM, {**ok_body, "scheduled_dt": "not-a-date"}, format="json")
    check("a bad schedule date is refused with a message, not a server error", r.status_code == 400 and "scheduled_dt" in keys(r), r.content.decode())
    rig_act = next((a for a in MstActivity.objects.filter(activity_location__in=("V", "R"))), None)
    if rig_act:
        r = client.post(AM, {"activity": rig_act.pk, "scheduled_dt": day(10)}, format="json")
        check("a rig activity without a rig is refused on the Rig box", r.status_code == 400 and "rig" in keys(r), r.content.decode())
    r = client.post(AM, ok_body, format="json")
    check("a complete row is accepted", r.status_code == 201, r.content.decode())
    am = r.json()["activity_monitor_id"]
    r = client.post(AM, ok_body, format="json")
    check("a second open record for the same activity is refused on the Activity box", r.status_code == 400 and "activity" in keys(r), r.content.decode())
    url = f"{AM}{am}/"
    r = client.patch(url, {"scheduled_dt": day(20), "planning_remark": ""}, format="json")
    check("a changed schedule date needs a planning remark", r.status_code == 400 and "planning_remark" in keys(r), r.content.decode())
    r = client.patch(url, {"scheduled_dt": day(10), "completion_dt": day(1), "completion_remark": "x"}, format="json")
    check("a future completion date is refused on its box", r.status_code == 400 and "completion_dt" in keys(r), r.content.decode())
    r = client.patch(url, {"scheduled_dt": day(10), "completion_dt": day(0), "completion_remark": ""}, format="json")
    check("a completion without a remark is refused on its box", r.status_code == 400 and "completion_remark" in keys(r))
    r = client.patch(url, {"scheduled_dt": day(10), "completion_dt": day(0), "completion_remark": "done"}, format="json")
    check("a completion needs the next-schedule choice", r.status_code == 400 and "next_schedule_required" in keys(r))
    r = client.patch(url, {"scheduled_dt": day(10), "completion_dt": day(0), "completion_remark": "done", "next_schedule_required": "Y"}, format="json")
    check("a next schedule needs a date", r.status_code == 400 and "next_scheduled_dt" in keys(r))
    r = client.patch(url, {"scheduled_dt": day(10), "completion_dt": day(0), "completion_remark": "done", "next_schedule_required": "Y", "next_scheduled_dt": day(5)}, format="json")
    check("a next date not after the schedule date is refused", r.status_code == 400 and "next_scheduled_dt" in keys(r))
    r = client.patch(url, {"scheduled_dt": day(10), "completion_dt": day(0), "completion_remark": "done", "next_schedule_required": "Y", "next_scheduled_dt": day(40)}, format="json")
    check("a complete completion is accepted and creates the next row", r.status_code == 200 and r.json().get("next_row"), r.content.decode())
    r = client.patch(url, {"scheduled_dt": day(10)}, format="json")
    check("a completed record can't be changed", r.status_code == 400)


if __name__ == "__main__":
    with transaction.atomic():
        run()
        transaction.set_rollback(True)
    print()
    print("FAILED: " + ", ".join(FAILED) if FAILED else "All checks passed. Nothing was saved.")
    sys.exit(1 if FAILED else 0)
