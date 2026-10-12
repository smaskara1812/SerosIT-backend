"""Checks the Drilling master rules (Batch D) through the real API.

    cd backend
    .venv/bin/python scripts/check_batch_d_rules.py

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

from core.models import MstDrillingOperation, MstDrillingRate, MstDrillingWorkShift, ProjectContract, ProjectDrillingRate

FAILED = []


def check(name, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  {detail[:220]}" if detail and not ok else ""))
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
    base = "/api/masters/"
    today = datetime.date.today()
    day = lambda n: (today + datetime.timedelta(days=n)).isoformat()

    print("Drilling Operations")
    url = f"{base}drilling-operations/"
    code = max(MstDrillingOperation.objects.values_list("drilling_ops_code_no", flat=True)) + 1
    r = client.post(url, {"drilling_ops_code_no": code, "drilling_ops_name": "ZZ Operation"}, format="json")
    check("a new operation is accepted", r.status_code == 201, r.content.decode())
    pk = r.json()["drilling_ops_id"]
    r = client.post(url, {"drilling_ops_code_no": code, "drilling_ops_name": "ZZ Other"}, format="json")
    check("a repeated Code No is refused", r.status_code == 400 and "drilling_ops_code_no" in keys(r), r.content.decode())
    for v in ("zz operation", "  ZZ Operation "):
        r = client.post(url, {"drilling_ops_code_no": code + 1, "drilling_ops_name": v}, format="json")
        check(f"a repeated name ({v.strip()}) is refused", r.status_code == 400 and "drilling_ops_name" in keys(r), r.content.decode())
    check("saving its own code and name again is fine", client.patch(f"{url}{pk}/", {"drilling_ops_code_no": code, "drilling_ops_name": "ZZ Operation"}, format="json").status_code == 200)
    for o in MstDrillingOperation.objects.exclude(pk=pk)[:3]:
        check(f"existing operation {o.pk} can still be saved", client.patch(f"{url}{o.pk}/", {"drilling_ops_code_no": o.drilling_ops_code_no, "drilling_ops_name": o.drilling_ops_name}, format="json").status_code == 200)

    print("Drilling Work Shift")
    url = f"{base}drilling-work-shifts/"
    ref = MstDrillingWorkShift.objects.first()
    other_rig = MstDrillingWorkShift.objects.exclude(rig=ref.rig).first()
    body = {"contract": ref.contract_id, "rig": ref.rig_id, "work_shift": "M", "work_shift_start_time": "06:00", "work_shift_end_time": "18:00", "work_shift_days": 1}
    # a rig/contract pair without shifts, so nothing clashes
    used = set(MstDrillingWorkShift.objects.values_list("contract_id", "rig_id"))
    fresh = ProjectContract.objects.exclude(pk__in=[c for c, _ in used]).first() or ProjectContract.objects.first()
    body["contract"] = fresh.pk
    for days, ok in ((1, True), (2, True), (0, False), (3, False), (-1, False)):
        r = client.post(url, {**body, "work_shift": "E" if days == 2 else "M", "work_shift_days": days}, format="json")
        check(f"Shift Days {days} is {'accepted' if ok else 'refused'}", (r.status_code == 201) == ok and (ok or "work_shift_days" in keys(r)), r.content.decode())
    r = client.post(url, {**body, "work_shift": "E", "work_shift_active": "X"}, format="json")
    check("Active other than Y or N is refused", r.status_code == 400 and "work_shift_active" in keys(r), r.content.decode())
    r = client.post(url, {**body, "work_shift": "E", "work_shift_active": "N"}, format="json")
    check("Active N is accepted", r.status_code == 201, r.content.decode())
    check("an unknown shift is refused", "work_shift" in keys(client.post(url, {**body, "work_shift": "X"}, format="json")))
    for w in MstDrillingWorkShift.objects.all()[:3]:
        check(f"existing shift {w.pk} can still be saved", client.patch(f"{url}{w.pk}/", {"work_shift_days": w.work_shift_days}, format="json").status_code == 200)

    print("Drilling Rates")
    url = f"{base}drilling-rate-types/"
    r = client.post(url, {"rate_code": "ZZ-R", "rate_active": "Y"}, format="json")
    check("a new rate type is accepted", r.status_code == 201, r.content.decode())
    rid = r.json()["drilling_rate_id"]
    r = client.patch(f"{url}{rid}/", {"rate_active": "X"}, format="json")
    check("Active other than Y or N is refused", r.status_code == 400 and "rate_active" in keys(r), r.content.decode())
    check("Active N is accepted", client.patch(f"{url}{rid}/", {"rate_active": "N"}, format="json").status_code == 200)
    blank = MstDrillingRate.objects.filter(rate_active="").first()
    if blank:
        check("an old rate with a blank Active can still be edited for something else", client.patch(f"{url}{blank.pk}/", {"rate_description": blank.rate_description or "x"}, format="json").status_code == 200)
        r = client.patch(f"{url}{blank.pk}/", {"rate_active": ""}, format="json")
        check("sending a blank Active asks for a choice", r.status_code == 400 and "rate_active" in keys(r), r.content.decode())

    print("Project Contract")
    url = f"{base}project-contracts/"
    src = ProjectContract.objects.first()
    cb = lambda **o: {"location": src.location_id, "operator": src.operator_id, "prj_contract_no": "ZZ-CONTRACT-1", "prj_short_name": "ZZ1", "prj_start_dt": day(-30), **o}
    r = client.post(url, cb(), format="json")
    check("a complete contract is accepted", r.status_code == 201, r.content.decode())
    cid = r.json()["prj_contract_id"]
    for name, over, field in (
        ("a repeated Contract No", {"prj_contract_no": "zz-contract-1"}, "prj_contract_no"),
        ("a repeated Contract No with spaces", {"prj_contract_no": " ZZ-CONTRACT-1 "}, "prj_contract_no"),
        ("a missing Short Name", {"prj_contract_no": "ZZ-2", "prj_short_name": ""}, "prj_short_name"),
        ("a Short Name with a space", {"prj_contract_no": "ZZ-3", "prj_short_name": "AB CD"}, "prj_short_name"),
        ("a Short Name with a symbol", {"prj_contract_no": "ZZ-4", "prj_short_name": "AB_#"}, "prj_short_name"),
        ("a Start Date in the future", {"prj_contract_no": "ZZ-5", "prj_start_dt": day(1)}, "prj_start_dt"),
        ("an End Date before the Start Date", {"prj_contract_no": "ZZ-6", "prj_end_dt": day(-31)}, "prj_end_dt"),
    ):
        r = client.post(url, cb(**over), format="json")
        check(f"{name} is refused", r.status_code == 400 and field in keys(r), r.content.decode())
    check("a Short Name with a hyphen is accepted", client.post(url, cb(prj_contract_no="ZZ-7", prj_short_name="AB-12"), format="json").status_code == 201)
    check("an End Date equal to the Start Date is accepted", client.post(url, cb(prj_contract_no="ZZ-8", prj_end_dt=day(-30)), format="json").status_code == 201)
    check("a planned future End Date is accepted", client.post(url, cb(prj_contract_no="ZZ-9", prj_end_dt=day(200)), format="json").status_code == 201)
    check("saving its own Contract No again is fine", client.patch(f"{url}{cid}/", {"prj_contract_no": "ZZ-CONTRACT-1"}, format="json").status_code == 200)
    check("an End Date before the Start Date is refused on edit", "prj_end_dt" in keys(client.patch(f"{url}{cid}/", {"prj_end_dt": day(-40)}, format="json")))
    for c in ProjectContract.objects.exclude(pk=cid)[:5]:
        r = client.patch(f"{url}{c.pk}/", {"prj_contract_no": c.prj_contract_no}, format="json")
        check(f"existing contract {c.pk} can still be saved", r.status_code == 200, r.content.decode())
    odd = ProjectContract.objects.filter(prj_short_name__contains="-").exclude(pk=cid).first()
    if odd:
        check("a contract whose short name has a hyphen can still be saved", client.patch(f"{url}{odd.pk}/", {"prj_short_name": odd.prj_short_name}, format="json").status_code == 200)
    nos = ProjectContract.objects.filter(prj_short_name__isnull=True).first()
    if nos:
        check("a contract with no short name can still be saved", client.patch(f"{url}{nos.pk}/", {"prj_contract_no": nos.prj_contract_no}, format="json").status_code == 200)

    print("Project Drilling Rates")
    url = f"{base}project-drilling-rates/"
    ref = ProjectDrillingRate.objects.first()
    taken = set(ProjectDrillingRate.objects.filter(contract=ref.contract, rig=ref.rig).values_list("drilling_rate_id", flat=True))
    free = MstDrillingRate.objects.exclude(pk__in=taken).first()
    r = client.post(url, {"contract": ref.contract_id, "rig": ref.rig_id, "drilling_rate": free.pk}, format="json")
    check("a new rate row without an amount is accepted (the amount stays optional)", r.status_code == 201, r.content.decode())
    r = client.post(url, {"contract": ref.contract_id, "rig": ref.rig_id, "drilling_rate": free.pk}, format="json")
    check("a repeat of Contract + Rig + Rate Type is refused", r.status_code == 400 and "drilling_rate" in keys(r), r.content.decode())
    r = client.post(url, {"contract": ref.contract_id, "rig": ref.rig_id, "drilling_rate": ref.drilling_rate_id}, format="json")
    check("a repeat of an existing row is refused", r.status_code == 400, r.content.decode())
    check("saving an existing row again is fine", client.patch(f"{url}{ref.pk}/", {"rate": str(ref.rate or 0)}, format="json").status_code == 200)


if __name__ == "__main__":
    with transaction.atomic():
        run()
        transaction.set_rollback(True)
    print()
    print("FAILED: " + ", ".join(FAILED) if FAILED else "All checks passed. Nothing was saved.")
    sys.exit(1 if FAILED else 0)
