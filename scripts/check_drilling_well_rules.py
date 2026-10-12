"""Checks the Drilling Well (Drilling Information) rules through the real API.

    cd backend
    .venv/bin/python scripts/check_drilling_well_rules.py

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

from core.models import DrillingHdr

URL = "/api/drilling/drilling-information/"
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
    src = DrillingHdr.objects.exclude(drilling_rate=None).exclude(contract=None).order_by("pk").first()
    today = datetime.datetime.now().replace(microsecond=0)
    iso = lambda dt: dt.isoformat()
    day = lambda n: iso(today - datetime.timedelta(days=n))

    def body(**over):
        base = {
            "contract": src.contract_id, "rig": src.rig_id, "latitude": "08°36'00.00\"N", "longitude": "108°49'00.00\"E", "location": "Rule check",
            "total_water_depth": 50, "first_anchor_down_dt": day(30), "distance_covered_kms_knots": "12.50", "drilling_rate": src.drilling_rate_id,
        }
        base.update(over)
        return base

    print("Create")
    r = client.post(URL, body(), format="json")
    check("a complete record is accepted", r.status_code == 201, r.content[:200])
    pk = r.json()["drilling_hdr_id"]
    for name, over, field in (
        ("no project is refused", {"contract": None}, "contract"),
        ("no water depth is refused", {"total_water_depth": None}, "total_water_depth"),
        ("a negative water depth is refused", {"total_water_depth": -5}, "total_water_depth"),
        ("no distance is refused", {"distance_covered_kms_knots": None}, "distance_covered_kms_knots"),
        ("a negative distance is refused", {"distance_covered_kms_knots": "-1"}, "distance_covered_kms_knots"),
        ("no rate type is refused", {"drilling_rate": None}, "drilling_rate"),
        ("a future first anchor down is refused", {"first_anchor_down_dt": iso(today + datetime.timedelta(days=1))}, "first_anchor_down_dt"),
        ("a blank location is refused", {"location": "  "}, "location"),
        ("a location over 25 characters is refused", {"location": "x" * 26}, "location"),
        ("latitude degrees over 90 are refused", {"latitude": "91°00'00.00\"N"}, "latitude"),
        ("longitude degrees over 180 are refused", {"longitude": "181°00'00.00\"E"}, "longitude"),
        ("minutes over 59 are refused", {"latitude": "08°60'00.00\"N"}, "latitude"),
        ("seconds over 59 are refused", {"longitude": "108°49'60.00\"E"}, "longitude"),
        ("text instead of a coordinate is refused", {"latitude": "north"}, "latitude"),
        ("a missing fraction is refused", {"latitude": "08°36'00.\"N"}, "latitude"),
        ("the wrong zone for latitude is refused", {"latitude": "08°36'00.00\"E"}, "latitude"),
        ("the wrong zone for longitude is refused", {"longitude": "108°49'00.00\"N"}, "longitude"),
        ("a completion in the future is refused", {"drilling_completion_dt": iso(today + datetime.timedelta(days=1))}, "drilling_completion_dt"),
        ("a completion before the anchor date is refused", {"drilling_completion_dt": day(40)}, "drilling_completion_dt"),
        ("a Total Depth not above the water depth is refused", {"total_depth": 50}, "total_depth"),
    ):
        r = client.post(URL, body(**over), format="json")
        check(name, r.status_code == 400 and field in keys(r), r.content[:200])
    check("90 and 180 degrees are accepted", client.post(URL, body(latitude="90°00'00.00\"S", longitude="180°00'00.00\"W"), format="json").status_code == 201)
    check("distance 0 and 9999.99 are accepted", client.post(URL, body(distance_covered_kms_knots="0"), format="json").status_code == 201
          and client.post(URL, body(distance_covered_kms_knots="9999.99"), format="json").status_code == 201)
    check("a completion on the anchor date is accepted", client.post(URL, body(drilling_completion_dt=day(30)), format="json").status_code == 201)
    check("a completion today is accepted", client.post(URL, body(drilling_completion_dt=iso(today - datetime.timedelta(minutes=1))), format="json").status_code == 201)
    check("a Total Depth above the water depth is accepted", client.post(URL, body(total_depth=60), format="json").status_code == 201)

    print("Edit")
    r = client.patch(f"{URL}{pk}/", {"drilling_completion_dt": iso(today + datetime.timedelta(days=2))}, format="json")
    check("a future completion is refused on edit", r.status_code == 400 and "drilling_completion_dt" in keys(r))
    r = client.patch(f"{URL}{pk}/", {"drilling_completion_dt": day(10)}, format="json")
    check("a completion date can be added", r.status_code == 200, r.content[:200])
    r = client.patch(f"{URL}{pk}/", {"distance_covered_kms_knots": None}, format="json")
    check("clearing the distance is refused", r.status_code == 400 and "distance_covered_kms_knots" in keys(r))
    r = client.patch(f"{URL}{pk}/", {"latitude": "99°00'00.00\"N"}, format="json")
    check("a changed bad coordinate is refused", r.status_code == 400 and "latitude" in keys(r))

    print("Existing records are left as they are")
    cases = (
        ("with no distance", DrillingHdr.objects.filter(distance_covered_kms_knots__isnull=True)),
        ("with no rate type", DrillingHdr.objects.filter(drilling_rate__isnull=True)),
        ("with no water depth", DrillingHdr.objects.filter(total_water_depth__isnull=True)),
    )
    for label, qs in cases:
        old = qs.first()
        if old is None:
            print(f"  skip  no record {label}")
            continue
        r = client.patch(f"{URL}{old.pk}/", {"location": old.location}, format="json")
        check(f"a record {label} can still be saved", r.status_code == 200, r.content[:200])
    odd = next((d for d in DrillingHdr.objects.all() if d.latitude and "." in d.latitude and d.latitude.split(".")[1].startswith('"')), None)
    if odd:
        r = client.patch(f"{URL}{odd.pk}/", {"drilling_completion_dt": day(1) if odd.first_anchor_down_dt.date() < datetime.date.today() else None}, format="json")
        check("a record with an unreadable coordinate can still be completed", r.status_code == 200, r.content[:200])


if __name__ == "__main__":
    with transaction.atomic():
        run()
        transaction.set_rollback(True)
    print()
    print("FAILED: " + ", ".join(FAILED) if FAILED else "All checks passed. Nothing was saved.")
    sys.exit(1 if FAILED else 0)
