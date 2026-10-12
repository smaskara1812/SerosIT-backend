"""Checks the Incident Details validation rules through the real API.

    cd backend
    .venv/bin/python scripts/check_incident_details_rules.py

Runs every request inside one transaction that is rolled back at the end, so
nothing is saved and no e-mail is sent. It needs the normal dev data (an active
rig, a financial year, the lookup masters and a few existing incidents).
Exits with status 1 if any check fails.
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

from core import mail_templates
from core.incident_flash_report import render_flash_report_pdf
from core.models import Incident, MstRig

URL = "/api/qhse/incidents/"
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

    # A clean, valid incident to copy: not injured, every required lookup present.
    src = (
        Incident.objects.exclude(marked_as_deleted="Y")
        .exclude(person_injured="Y")
        .filter(rig__isnull=False, rig_operation__isnull=False, contact_expo_type__isnull=False)
        .exclude(incident_reported_dt__isnull=True)
        .order_by("-incident_date")
        .first()
    )
    other_rig = MstRig.objects.exclude(pk=src.rig_id).first()
    when = datetime.datetime(2026, 1, 10, 8, 30)

    def payload(**over):
        base = {
            "rig": src.rig_id, "unit_name": None, "rig_incident_no": "ZZ-TEST-1", "incident_party": "10",
            "incident_date": when.isoformat(), "incident_reported_dt": (when + datetime.timedelta(hours=2)).isoformat(),
            "incident_type": src.incident_type_id, "incident_severity": "L", "incident_severity_potential": "M",
            "incident_descr": "Rule check", "immediate_incident_cause": src.immediate_incident_cause_id,
            "rig_operation": src.rig_operation_id, "work_location": src.work_location_id,
            "contact_expo_type": src.contact_expo_type_id, "person_injured": "N",
        }
        base.update(over)
        return base

    def post(**over):
        return client.post(URL, payload(**over), format="json")

    print("Create: valid and rig / unit")
    r = post()
    check("valid incident is accepted", r.status_code == 201, r.content[:200])
    check("no rig and no unit is rejected on rig", post(rig=None, rig_incident_no=None).status_code == 400 and "rig" in fields(post(rig=None, rig_incident_no=None)))
    r = post(unit_name="Some Unit", rig_incident_no="ZZ-TEST-2")
    check("rig and unit together is rejected on unit_name", r.status_code == 400 and "unit_name" in fields(r))
    r = post(rig=None, unit_name="Test Unit", rig_incident_no=None)
    check("a unit with no rig is accepted", r.status_code == 201, r.content[:200])
    if r.status_code == 201:
        inc = Incident.objects.get(pk=r.json()["incident_id"])
        try:
            render_flash_report_pdf(inc)
            mail_templates.incident_created_mail(inc)
            check("flash report and e-mail work for a unit-only incident", True)
        except Exception as exc:  # noqa: BLE001
            check("flash report and e-mail work for a unit-only incident", False, repr(exc))

    print("Dates")
    future = (datetime.datetime.now() + datetime.timedelta(days=2)).isoformat()
    r = post(incident_date=future, incident_reported_dt=future, rig_incident_no="ZZ-TEST-3")
    check("incident date in the future is rejected", r.status_code == 400 and "incident_date" in fields(r))
    r = post(incident_reported_dt=(when - datetime.timedelta(minutes=1)).isoformat(), rig_incident_no="ZZ-TEST-4")
    check("reported before incident is rejected", r.status_code == 400 and "incident_reported_dt" in fields(r))
    r = post(incident_reported_dt=when.isoformat(), rig_incident_no="ZZ-TEST-5")
    check("reported equal to incident is accepted", r.status_code == 201, r.content[:200])
    p = payload(rig_incident_no="ZZ-TEST-6")
    p.pop("incident_reported_dt")
    r = client.post(URL, p, format="json")
    check("missing reported date is rejected", r.status_code == 400 and "incident_reported_dt" in fields(r))

    print("Allowed values")
    for name, over in {
        "missing Belongs To": {"incident_party": None},
        "unknown Belongs To": {"incident_party": "7"},
        "unknown severity": {"incident_severity": "X"},
        "missing potential severity": {"incident_severity_potential": None},
        "unknown Person Injured": {"person_injured": "Q"},
    }.items():
        r = post(rig_incident_no=f"ZZ-{name[:6]}", **over)
        check(f"{name} is rejected", r.status_code == 400, r.content[:150])
    check("blank Person Injured is accepted", post(person_injured="", rig_incident_no="ZZ-BLANK").status_code == 201)

    print("Currency")
    r = post(financial_loss_amt=500, rig_incident_no="ZZ-CUR1")
    check("loss amount without currency is rejected", r.status_code == 400 and "financial_loss_currency" in fields(r))
    cur = Incident.objects.exclude(financial_loss_currency__isnull=True).values_list("financial_loss_currency_id", flat=True).first()
    check("loss amount with currency is accepted", post(financial_loss_amt=500, financial_loss_currency=cur, rig_incident_no="ZZ-CUR2").status_code == 201)

    print("Injured person")
    r = post(person_injured="Y", rig_incident_no="ZZ-INJ1")
    check("injured with no details is rejected on all four", r.status_code == 400 and {"emp_name", "rank", "total_rig_exp_months", "part_of_body_1"} <= fields(r), sorted(fields(r)))
    donor = Incident.objects.filter(person_injured="Y", part_of_body_1__isnull=False, rank__isnull=False, total_rig_exp_months__isnull=False).exclude(emp_name__isnull=True).first()
    r = post(person_injured="Y", rig_incident_no="ZZ-INJ2", emp_name="Test Person", rank=donor.rank_id, total_rig_exp_months=0, part_of_body_1=donor.part_of_body_1_id, third_party="10")
    check("injured with name, designation, experience (0) and a body part is accepted", r.status_code == 201, r.content[:200])

    print("Rig Incident No.")
    check("duplicate number on the same rig is rejected", post(rig_incident_no="ZZ-TEST-1").status_code == 400)
    check("same number on another rig is accepted", post(rig=other_rig.pk, rig_incident_no="ZZ-TEST-1").status_code == 201)

    print("Existing incidents are left as they are")
    both = Incident.objects.exclude(marked_as_deleted="Y").filter(rig__isnull=False).exclude(unit_name__isnull=True).exclude(unit_name="").first()
    nameless = Incident.objects.exclude(marked_as_deleted="Y").filter(person_injured="Y").filter(emp_name__isnull=True, fs_emp__isnull=True).first()
    for label, rec in (("rig and unit both set", both), ("injured with no name", nameless)):
        if rec is None:
            print(f"  skip  no existing incident with {label}")
            continue
        data = client.get(f"{URL}{rec.pk}/").json()
        keep = {k: v for k, v in data.items() if k in payload() or k in ("unit_name", "emp_name", "rank", "fs_emp", "third_party", "contractor", "total_rig_exp_months", "part_of_body_1", "part_of_body_2", "part_of_body_3", "part_of_body_4", "rig_incident_no")}
        keep["comments"] = "edited by rule check"
        r = client.patch(f"{URL}{rec.pk}/", keep, format="json")
        check(f"incident with {label} can still be edited for something else", r.status_code == 200, r.content[:200])
    if both is not None:
        data = client.get(f"{URL}{both.pk}/").json()
        keep = {k: v for k, v in data.items() if k in payload()}
        keep["incident_date"] = future
        check("...but moving its date into the future is still refused", client.patch(f"{URL}{both.pk}/", keep, format="json").status_code == 400)


if __name__ == "__main__":
    with transaction.atomic():
        run()
        transaction.set_rollback(True)
    print()
    print("FAILED: " + ", ".join(FAILED) if FAILED else "All checks passed. Nothing was saved.")
    sys.exit(1 if FAILED else 0)
