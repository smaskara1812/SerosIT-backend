"""Checks the HSE Drills master rules through the real API.

    cd backend
    .venv/bin/python scripts/check_hse_drills_master_rules.py

Runs every request inside one transaction that is rolled back at the end, so
nothing is saved. Exits with status 1 if any check fails.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.test import APIClient

from core.models import MstHseDrill

URL = "/api/masters/hse-drills/"
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
    body = {"hse_drill_name": "ZZ Rule Drill", "hse_drill_frequency": "W", "rig_type_choice": "BOTH"}
    r = client.post(URL, body, format="json")
    check("a drill is created", r.status_code == 201, r.content[:200])
    check("a new drill starts Active (Y)", r.json().get("hse_drill_active") == "Y", r.content[:200])
    pk = r.json()["hse_drill_id"]
    for name, over, field in (
        ("a blank name is refused", {"hse_drill_name": ""}, "hse_drill_name"),
        ("a missing Frequency is refused", {"hse_drill_frequency": ""}, "hse_drill_frequency"),
        ("an unknown Frequency is refused", {"hse_drill_frequency": "X"}, "hse_drill_frequency"),
        ("a missing Rig Type is refused", {"rig_type_choice": ""}, "rig_type_choice"),
        ("Active 'X' is refused", {"hse_drill_active": "X"}, "hse_drill_active"),
    ):
        r = client.post(URL, {**body, **over}, format="json")
        check(name, r.status_code == 400 and field in keys(r), r.content[:200])
    for f in "WMQBA":
        check(f"Frequency {f} is accepted", client.post(URL, {**body, "hse_drill_name": f"ZZ {f}", "hse_drill_frequency": f}, format="json").status_code == 201)
    r = client.patch(f"{URL}{pk}/", {"hse_drill_active": "N"}, format="json")
    check("Active can be switched to N", r.status_code == 200 and r.json()["hse_drill_active"] == "N", r.content[:200])
    check("Active 'Z' is refused on edit", "hse_drill_active" in keys(client.patch(f"{URL}{pk}/", {"hse_drill_active": "Z"}, format="json")))
    check("the name is locked once saved", "hse_drill_name" in keys(client.patch(f"{URL}{pk}/", {"hse_drill_name": "Other"}, format="json")))
    check("a drill can't be deleted", client.delete(f"{URL}{pk}/").status_code == 405)
    for d in MstHseDrill.objects.exclude(pk=pk)[:3]:
        check(f"existing drill {d.pk} can still be saved", client.patch(f"{URL}{d.pk}/", {"hse_drill_active": d.hse_drill_active}, format="json").status_code == 200)


if __name__ == "__main__":
    with transaction.atomic():
        run()
        transaction.set_rollback(True)
    print()
    print("FAILED: " + ", ".join(FAILED) if FAILED else "All checks passed. Nothing was saved.")
    sys.exit(1 if FAILED else 0)
