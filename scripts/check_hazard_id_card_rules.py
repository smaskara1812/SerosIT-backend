"""Checks the Hazard ID Card validation rules through the real API.

    cd backend
    .venv/bin/python scripts/check_hazard_id_card_rules.py

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

from core.models import HazardCard

URL = "/api/qhse/hazard-id-card/"
FAILED = []


def check(name, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


def fields(resp):
    try:
        return set(resp.json().keys())
    except Exception:
        return set()


def run():
    client = APIClient(HTTP_HOST="localhost")
    client.force_authenticate(get_user_model().objects.filter(is_superuser=True).first())
    src = HazardCard.objects.exclude(marked_as_deleted="Y").exclude(reported_by_name__isnull=True).order_by("-event_dt").first()
    event = datetime.datetime(2026, 2, 3, 10, 0)

    def payload(**over):
        base = {
            "rig": src.rig_id, "event_dt": event.isoformat(), "reported_by_party": "SEROS", "reported_by_name": "Rule Check",
            "work_location": src.work_location_id, "haz_type": src.haz_type_id, "timeout_for_safety": "N",
            "hazard_desc": "Rule check", "resp_dept": src.resp_dept_id, "resp_rank": src.resp_rank_id,
            "haz_id_card_status": "O", "close_out_dt": None,
        }
        base.update(over)
        return base

    def post(**over):
        return client.post(URL, payload(**over), format="json")

    first = post()
    if first.status_code != 201:
        # the newest card's rig may have no active contract today; try other rigs
        for rid in HazardCard.objects.exclude(marked_as_deleted="Y").order_by("-event_dt").values_list("rig_id", flat=True).distinct()[:40]:
            src_rig = rid
            first = client.post(URL, payload(rig=src_rig), format="json")
            if first.status_code == 201:
                payload.__defaults__ = None
                src.rig_id = src_rig
                break
    print("Create")
    check("valid card is accepted", first.status_code == 201, first.content[:200])

    print("Event and close-out dates")
    future = (datetime.datetime.now() + datetime.timedelta(days=2)).isoformat()
    r = post(event_dt=future)
    check("event in the future is rejected", r.status_code == 400 and "event_dt" in fields(r))
    r = post(haz_id_card_status="C")
    check("Closed without a close-out is rejected", r.status_code == 400 and "close_out_dt" in fields(r))
    r = post(haz_id_card_status="C", close_out_dt=(event - datetime.timedelta(minutes=1)).isoformat())
    check("close-out before the event is rejected", r.status_code == 400 and "close_out_dt" in fields(r))
    r = post(haz_id_card_status="C", close_out_dt=event.isoformat())
    check("close-out equal to the event is accepted", r.status_code == 201, r.content[:200])
    r = post(haz_id_card_status="C", close_out_dt=(event + datetime.timedelta(hours=3)).isoformat())
    check("close-out after the event is accepted", r.status_code == 201, r.content[:200])
    r = post(haz_id_card_status="C", close_out_dt=future)
    check("close-out in the future is rejected", r.status_code == 400 and "close_out_dt" in fields(r))

    print("Values and required fields")
    check("unknown status is rejected", post(haz_id_card_status="X").status_code == 400)
    check("blank description is rejected", post(hazard_desc="").status_code == 400)
    check("party OGDSL is accepted", post(reported_by_party="OGDSL", reported_by_name="Someone").status_code == 201)
    r = post(reported_by_name=None)
    check("a reporter name is required for a non-EOSIL party", r.status_code == 400 and "reported_by_name" in fields(r))

    print("Date filters (list, report)")
    base = f"{URL}?date_from=2026-03-01&date_to=2026-02-01"
    check("From after To is rejected on the list", client.get(base).status_code == 400)
    check("From after To is rejected on the report", client.get(f"{URL}report/?date_from=2026-03-01&date_to=2026-02-01").status_code == 400)
    check("a future To date is rejected", client.get(f"{URL}?date_to=2099-01-01").status_code == 400)
    check("a normal range is accepted", client.get(f"{URL}?date_from=2026-01-01&date_to=2026-02-01").status_code == 200)

    print("Existing cards are left as they are")
    cases = {
        "no reporter name": HazardCard.objects.exclude(marked_as_deleted="Y").filter(reported_by_name__isnull=True, reported_by_fs_emp__isnull=True).exclude(reported_by_party="EOSIL").first(),
        "close-out equal to the event": next((c for c in HazardCard.objects.exclude(marked_as_deleted="Y").filter(close_out_dt__isnull=False).order_by("-pk")[:400] if c.close_out_dt == c.event_dt), None),
        "close-out in the future": HazardCard.objects.filter(pk=10888).first(),
    }
    for label, rec in cases.items():
        if rec is None:
            print(f"  skip  no card with {label}")
            continue
        data = client.get(f"{URL}{rec.pk}/").json()
        keep = {k: data[k] for k in payload() if k in data}
        keep["timeout_for_safety"] = keep.get("timeout_for_safety") or "N"  # old cards store blank for No; the form sends N
        keep["action_taken"] = "edited by rule check"
        r = client.patch(f"{URL}{rec.pk}/", keep, format="json")
        check(f"a card with {label} can still be edited for something else", r.status_code == 200, r.content[:200])
    if cases["close-out in the future"] is not None:
        rec = cases["close-out in the future"]
        data = client.get(f"{URL}{rec.pk}/").json()
        keep = {k: data[k] for k in payload() if k in data}
        keep["timeout_for_safety"] = keep.get("timeout_for_safety") or "N"
        keep["close_out_dt"] = future
        check("...but changing that close-out to another future date is refused", client.patch(f"{URL}{rec.pk}/", keep, format="json").status_code == 400)


if __name__ == "__main__":
    with transaction.atomic():
        run()
        transaction.set_rollback(True)
    print()
    print("FAILED: " + ", ".join(FAILED) if FAILED else "All checks passed. Nothing was saved.")
    sys.exit(1 if FAILED else 0)
