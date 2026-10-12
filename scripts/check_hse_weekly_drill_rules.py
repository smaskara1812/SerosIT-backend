"""Checks the HSE Weekly Drill validation rules through the real API.

    cd backend
    .venv/bin/python scripts/check_hse_weekly_drill_rules.py

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

from core.hse_weekly_drill import week_range
from core.models import HseWeeklyDrillDtl, MstHseDrill, MstRig

HDR = "/api/qhse/hse-weekly-drill/"
DTL = "/api/qhse/hse-weekly-drill-details/"
FAILED = []
D = datetime.date


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
    print("Week maths")
    check("2025 week 1 = Sun 29 Dec 2024 to Sat 4 Jan 2025", week_range(2025, 1) == (D(2024, 12, 29), D(2025, 1, 4)))
    check("2025 week 2 starts Sun 5 Jan", week_range(2025, 2)[0] == D(2025, 1, 5))
    check("2023 week 1 starts on 1 Jan (a Sunday)", week_range(2023, 1) == (D(2023, 1, 1), D(2023, 1, 7)))
    check("2020 week 53 = 27 Dec 2020 to 2 Jan 2021", week_range(2020, 53) == (D(2020, 12, 27), D(2021, 1, 2)))
    check("every week starts on a Sunday", all(week_range(y, w)[0].weekday() == 6 for y in range(2015, 2031) for w in (1, 27, 53)))
    check("week 1 always holds 1 January", all(week_range(y, 1)[0] <= D(y, 1, 1) <= week_range(y, 1)[1] for y in range(2015, 2031)))

    client = APIClient(HTTP_HOST="localhost")
    client.force_authenticate(get_user_model().objects.filter(is_superuser=True).first())
    rig = MstRig.objects.filter(rig_type__isnull=False).exclude(pk__in=HseWeeklyDrillDtl.objects.values("hdr__rig_id")).order_by("rig_id").first()
    if rig is None:
        print("  skip  every rig already has weekly drills")
        return
    used = set(HseWeeklyDrillDtl.objects.filter(hdr__rig=rig).values_list("hse_drill_id", flat=True))
    drills = [d for d in MstHseDrill.objects.filter(hse_drill_active="Y", rig_type__isnull=True).order_by("pk") if d.pk not in used][:3]

    print("Header")
    r = client.post(HDR, {"rig": rig.pk, "year": 2099, "drill_week": 1}, format="json")
    check("week 1 is accepted", r.status_code == 201, r.content[:150])
    h1 = r.json()
    check("the header reports its week span", h1.get("week_start") == "2098-12-28" or h1.get("week_start", "").startswith("2098-12"), h1)
    check("week 53 is accepted", client.post(HDR, {"rig": rig.pk, "year": 2099, "drill_week": 53}, format="json").status_code == 201)
    check("week 54 is refused", client.post(HDR, {"rig": rig.pk, "year": 2099, "drill_week": 54}, format="json").status_code == 400)
    check("week 0 is refused", client.post(HDR, {"rig": rig.pk, "year": 2099, "drill_week": 0}, format="json").status_code == 400)
    check("the same rig/year/week is refused", client.post(HDR, {"rig": rig.pk, "year": 2099, "drill_week": 1}, format="json").status_code == 400)

    print("Drill Conducted Date inside the week")
    start, end = week_range(2099, 1)
    first = {"hdr": h1["hse_weekly_drill_hdr_id"], "hse_drill": drills[0].pk}
    day_before = start - datetime.timedelta(days=1)
    r = client.post(DTL, {**first, "drill_conducted_dt": day_before.isoformat(), "drill_last_conducted_dt": (start - datetime.timedelta(days=9)).isoformat()}, format="json")
    check("the day before the week is refused", r.status_code == 400 and "drill_conducted_dt" in keys(r), r.content[:200])
    check("the message names the week", "week 1" in str(r.json().get("drill_conducted_dt", "")), r.content[:200])
    r = client.post(DTL, {**first, "drill_conducted_dt": (end + datetime.timedelta(days=1)).isoformat(), "drill_last_conducted_dt": (start - datetime.timedelta(days=9)).isoformat()}, format="json")
    check("the day after the week is refused", r.status_code == 400 and "drill_conducted_dt" in keys(r))
    r = client.post(DTL, {**first, "drill_conducted_dt": start.isoformat(), "drill_last_conducted_dt": (start - datetime.timedelta(days=9)).isoformat()}, format="json")
    check("the first day (Sunday) is accepted", r.status_code == 201, r.content[:200])
    dtl = r.json()
    r = client.post(DTL, {"hdr": first["hdr"], "hse_drill": drills[1].pk, "drill_conducted_dt": end.isoformat(), "drill_last_conducted_dt": (start - datetime.timedelta(days=9)).isoformat()}, format="json")
    check("the last day (Saturday) is accepted", r.status_code == 201, r.content[:200])
    r = client.post(DTL, {"hdr": first["hdr"], "hse_drill": drills[2].pk, "drill_conducted_dt": end.isoformat(), "drill_last_conducted_dt": end.isoformat()}, format="json")
    check("last conducted not before the conducted date is refused", r.status_code == 400 and "drill_last_conducted_dt" in keys(r), r.content[:200])

    print("Editing a row")
    pk = dtl["hse_weekly_drill_dtl_id"]
    r = client.patch(f"{DTL}{pk}/", {"drill_conducted_dt": (end + datetime.timedelta(days=3)).isoformat()}, format="json")
    check("moving the date outside the week is refused", r.status_code == 400 and "drill_conducted_dt" in keys(r))
    r = client.patch(f"{DTL}{pk}/", {"drill_conducted_dt": (start + datetime.timedelta(days=2)).isoformat()}, format="json")
    check("moving the date inside the week is accepted", r.status_code == 200, r.content[:200])

    print("Existing rows are left as they are")
    old = next((d for d in HseWeeklyDrillDtl.objects.select_related("hdr").exclude(pk=pk) if not (week_range(d.hdr.drill_year.year, d.hdr.drill_week)[0] <= d.drill_conducted_dt <= week_range(d.hdr.drill_year.year, d.hdr.drill_week)[1])), None)
    if old is None:
        print("  skip  no old row outside its week")
    else:
        r = client.patch(f"{DTL}{old.pk}/", {"remarks": "edited by rule check"}, format="json")
        check("an old row outside its week can still be edited for remarks", r.status_code == 200, r.content[:200])
        r = client.patch(f"{DTL}{old.pk}/", {"drill_conducted_dt": old.drill_conducted_dt.isoformat()}, format="json")
        check("sending the same date again is not a change", r.status_code == 200, r.content[:200])


if __name__ == "__main__":
    with transaction.atomic():
        run()
        transaction.set_rollback(True)
    print()
    print("FAILED: " + ", ".join(FAILED) if FAILED else "All checks passed. Nothing was saved.")
    sys.exit(1 if FAILED else 0)
