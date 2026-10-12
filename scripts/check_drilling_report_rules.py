"""Checks the Drilling Report (Daily Report) rules through the real API.

    cd backend
    .venv/bin/python scripts/check_drilling_report_rules.py

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

from core.models import DrillingDtl, DrillingDtlOps

URL = "/api/drilling/drilling-report/"
FAILED = []


def check(name, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  {detail[:260]}" if detail and not ok else ""))
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
    src = DrillingDtl.objects.filter(ops__isnull=False).order_by("-pk").first()
    rate = lambda code: DrillingOps_rate(code)
    day = datetime.date(2001, 1, 1)
    counter = [0]

    def DrillingOps_rate(code):
        return DrillingDtlOps.objects.filter(prj_drilling_rate__drilling_rate__rate_code=code).select_related("prj_drilling_rate").first().prj_drilling_rate_id

    ref = src.ops.first()

    def op(hours=2, code="R1", start=0, **over):
        t0 = datetime.datetime(2001, 1, 1, start, 0)
        row = {
            "time_from": t0.isoformat(), "time_to": (t0 + datetime.timedelta(hours=hours)).isoformat(), "work_shift": "M",
            "drilling_ops": ref.drilling_ops_id, "drilling_section": ref.drilling_section_id, "depth_from": "100.00", "depth_to": "110.00",
            "operation_desc": "Rule check", "prj_drilling_rate": rate(code),
        }
        row.update(over)
        return row

    def body(**over):
        counter[0] += 1
        base = {
            "rig": src.rig_id, "drilling_dtl_dt": (day + datetime.timedelta(days=counter[0])).isoformat(),
            "pob_operator": 5, "pob_essar": 5, "wind_speed": 10, "current_k": "1.5", "at_press_mbar": 1000, "vdl": 10, "avdl": 10, "tot_vdl": 20,
            "kg": "1.50", "kg_margin": "0.50", "draft": "5.00", "consumption_diesel": 10, "consumption_water": 10, "received_water": 0,
            "remark": "Rule check summary text", "ops": [op()],
        }
        base.update(over)
        return base

    print("Create")
    r = client.post(URL, body(), format="json")
    check("a complete report is accepted", r.status_code == 201, r.content.decode())
    pk = r.json()["drilling_dtl_id"]

    refused = [
        ("a future report date", {"drilling_dtl_dt": (datetime.date.today() + datetime.timedelta(days=1)).isoformat()}, "drilling_dtl_dt"),
        ("a blank Operations Summary", {"remark": "  "}, "remark"),
        ("a too short Operations Summary", {"remark": "short"}, "remark"),
        ("a missing Received Water", {"received_water": None}, "received_water"),
        ("hours above 24", {"ops": [op(hours=13, start=0), op(hours=12, start=13)]}, "ops"),
        ("downtime time without a reason", {"ops": [op(code="R0")]}, "downtime_reason"),
        ("a blank downtime reason", {"ops": [op(code="R3")], "downtime_reason": " "}, "downtime_reason"),
    ]
    for f in ("at_press_mbar", "vdl", "avdl", "kg", "kg_margin", "draft", "consumption_diesel", "consumption_water", "received_diesel", "received_water", "generated_water"):
        refused.append((f"a negative {f}", {f: -1}, f))
    refused += [
        ("KG above 99.99", {"kg": "100.00"}, "kg"),
        ("KG Margin above 9.99", {"kg_margin": "10.00"}, "kg_margin"),
        ("Draft above 99.99", {"draft": "100.00"}, "draft"),
        ("Current K above 9.9", {"current_k": "10.0"}, "current_k"),
    ]
    for name, over, field in refused:
        r = client.post(URL, body(**over), format="json")
        check(f"{name} is refused", r.status_code == 400 and field in keys(r), r.content.decode())
    check("the digit-limit message is plain", "99.99" in str(client.post(URL, body(kg="100.00"), format="json").json().get("kg")))

    check("0 is accepted for every number", client.post(URL, body(vdl=0, avdl=0, kg="0", kg_margin="0", draft="0", consumption_diesel=0, consumption_water=0, received_diesel=0, generated_water=0), format="json").status_code == 201)
    check("exactly 24 hours is accepted", client.post(URL, body(ops=[op(hours=12, start=0), op(hours=12, start=12)]), format="json").status_code == 201)
    check("downtime time with a reason is accepted", client.post(URL, body(ops=[op(code="R0")], downtime_reason="Waiting on weather"), format="json").status_code == 201)
    check("a summary of exactly 10 characters is accepted", client.post(URL, body(remark="0123456789"), format="json").status_code == 201)
    check("received diesel and generated water may be blank", client.post(URL, body(received_diesel=None, generated_water=None), format="json").status_code == 201)

    r = client.post(URL, body(ops=[]), format="json")
    check("a report without a time log is accepted", r.status_code == 201, r.content.decode())
    empty_pk = r.json()["drilling_dtl_id"]
    r = client.post(URL, body(ops=[], remark="Another summary text"), format="json")
    check("a second report without a time log is accepted", r.status_code == 201, r.content.decode())
    r = client.patch(f"{URL}{empty_pk}/", {"wind_speed": 11}, format="json")
    check("a report without a time log can be edited", r.status_code == 200, r.content.decode())
    r = client.patch(f"{URL}{empty_pk}/", {"ops": [op()]}, format="json")
    check("time-log rows can be added to it later", r.status_code == 200 and len(r.json()["ops"]) == 1, r.content.decode())

    print("Edit")
    detail = f"{URL}{pk}/"
    check("a negative number is refused on edit", "vdl" in keys(client.patch(detail, {"vdl": -5}, format="json")))
    check("a short summary is refused on edit", "remark" in keys(client.patch(detail, {"remark": "tiny"}, format="json")))
    r = client.patch(detail, {"ops": [op(hours=13, start=0), op(hours=12, start=13)]}, format="json")
    check("a changed time log above 24 hours is refused", r.status_code == 400 and "ops" in keys(r), r.content.decode())
    r = client.patch(detail, {"ops": [op(code="R3")]}, format="json")
    check("a changed time log with downtime needs a reason", r.status_code == 400 and "downtime_reason" in keys(r), r.content.decode())

    print("Existing reports are left as they are")
    old_long = next((d for d in DrillingDtl.objects.filter(ops__isnull=False).distinct() if sum((x or 0) for x in [d.operating_hrs, d.standby_hrs, d.repair_service_hrs, d.repair_rate_hrs, d.zero_rate_hrs, d.rig_move_hrs]) > 24), None)
    if old_long:
        r = client.patch(f"{URL}{old_long.pk}/", {"wind_speed": old_long.wind_speed}, format="json")
        check("a report above 24 hours can still be edited for something else", r.status_code == 200, r.content.decode())
    old_nodown = next((d for d in DrillingDtl.objects.filter(ops__isnull=False).distinct() if (d.zero_rate_hrs or d.repair_rate_hrs) and not d.downtime_reason), None)
    if old_nodown:
        r = client.patch(f"{URL}{old_nodown.pk}/", {"wind_speed": old_nodown.wind_speed}, format="json")
        check("a day with downtime and no reason can still be edited for something else", r.status_code == 200, r.content.decode())
        same = [
            {"time_from": o.time_from.isoformat(), "time_to": o.time_to.isoformat(), "work_shift": o.work_shift, "drilling_ops": o.drilling_ops_id,
             "drilling_section": o.drilling_section_id, "depth_from": str(o.depth_from), "depth_to": str(o.depth_to), "operation_desc": o.operation_desc or "x",
             "prj_drilling_rate": o.prj_drilling_rate_id, "drilling_dtl_ops_id": o.drilling_dtl_ops_id}
            for o in old_nodown.ops.all()
        ]
        r = client.patch(f"{URL}{old_nodown.pk}/", {"ops": same}, format="json")
        check("sending the same time log again is not a change", r.status_code == 200, r.content.decode())
    short = next((d for d in DrillingDtl.objects.all()[:3000] if len((d.remark or "").strip()) < 10 and d.remark), None)
    if short:
        r = client.patch(f"{URL}{short.pk}/", {"wind_speed": short.wind_speed}, format="json")
        check("a report with a short summary can still be edited for something else", r.status_code == 200, r.content.decode())


if __name__ == "__main__":
    with transaction.atomic():
        run()
        transaction.set_rollback(True)
    print()
    print("FAILED: " + ", ".join(FAILED) if FAILED else "All checks passed. Nothing was saved.")
    sys.exit(1 if FAILED else 0)
