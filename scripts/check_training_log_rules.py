"""Checks the Training Log validation rules through the real API.

    cd backend
    .venv/bin/python scripts/check_training_log_rules.py

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

from core.models import HseTrainingLogDtl, HseTrainingLogHdr

HDR = "/api/qhse/training-log/"
DTL = "/api/qhse/training-log-trainees/"
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
    src = HseTrainingLogHdr.objects.order_by("pk").first()
    today = datetime.date.today()
    day = lambda n: (today + datetime.timedelta(days=n)).isoformat()

    def payload(**over):
        base = {
            "rig": src.rig_id, "cert": src.cert_id, "training_dt": day(-5), "training_location": "Rule check", "training_type": "Internal",
            "course_duration": 3, "training_org": src.training_org_id, "training_org_dtl": src.training_org_dtl_id, "assessment_conducted": "Y",
        }
        base.update(over)
        return base

    print("Log")
    r = client.post(HDR, payload(), format="json")
    check("a complete log is accepted", r.status_code == 201, r.content[:200])
    pk = r.json()["training_log_hdr_id"]
    for name, over, field in (
        ("a future Training Date is refused", {"training_dt": day(1)}, "training_dt"),
        ("duration 0 is refused", {"course_duration": 0}, "course_duration"),
        ("duration 256 is refused", {"course_duration": 256}, "course_duration"),
        ("a blank location is refused", {"training_location": "  "}, "training_location"),
        ("a location over 50 characters is refused", {"training_location": "x" * 51}, "training_location"),
        ("an unknown Training Type is refused", {"training_type": "Other"}, "training_type"),
        ("an unknown Assessment value is refused", {"assessment_conducted": "X"}, "assessment_conducted"),
    ):
        r = client.post(HDR, payload(**over), format="json")
        check(name, r.status_code == 400 and field in keys(r), r.content[:200])
    check("duration 255 is accepted", client.post(HDR, payload(course_duration=255), format="json").status_code == 201)

    print("Trainee certificate")
    # a Visitor is typed in, so these checks don't depend on who is on the rig today
    base = {
        "hdr": src.pk, "training_party": "Visitor", "fs_category": HseTrainingLogDtl.objects.filter(hdr=src).first().fs_category_id,
        "trainee_fname": "Rule", "trainee_lname": "Check", "trainee_designation": "Visitor", "trainee_department": "None", "company_name": "ZZ",
    }
    def trainee(**over):
        return {**base, "certificate_issued": "Y", "certificate_no": "ZZ1", "certificate_dt": day(-3), "cert_valid_upto": day(300), **over}
    for name, over, field in (
        ("a future Certificate Date is refused", {"certificate_dt": day(1)}, "certificate_dt"),
        ("Valid Upto before the Certificate Date is refused", {"cert_valid_upto": day(-10)}, "cert_valid_upto"),
        ("Valid Upto today is refused", {"cert_valid_upto": day(0), "certificate_dt": day(-3)}, "cert_valid_upto"),
        ("a missing Certificate No. is refused", {"certificate_no": ""}, "certificate_no"),
        ("a Certificate No. over 25 characters is refused", {"certificate_no": "x" * 26}, "certificate_no"),
        ("an unknown Certificate Issued value is refused", {"certificate_issued": "X"}, "certificate_issued"),
    ):
        r = client.post(DTL, trainee(**over), format="json")
        check(name, r.status_code == 400 and field in keys(r), r.content[:200])
    check("Valid Upto tomorrow is accepted", client.post(DTL, trainee(cert_valid_upto=day(1)), format="json").status_code == 201)
    r = client.post(DTL, {**base, "certificate_issued": "N"}, format="json")
    check("No certificate needs no details", r.status_code == 201, r.content[:200])
    check("a missing Employee is refused for Seros", "fs_emp" in keys(client.post(DTL, {"hdr": src.pk, "training_party": "Seros", "certificate_issued": "N"}, format="json")))
    check("an unknown Training Party is refused", "training_party" in keys(client.post(DTL, {**base, "training_party": "Nobody", "certificate_issued": "N"}, format="json")))
    check("a Visitor without details is refused", {"fs_category", "trainee_fname", "trainee_lname"} <= keys(client.post(DTL, {"hdr": src.pk, "training_party": "Visitor", "certificate_issued": "N"}, format="json")))

    print("Saved trainee")
    tid = client.post(DTL, {**base, "certificate_issued": "N"}, format="json").json()["training_log_dtl_id"]
    r = client.patch(f"{DTL}{tid}/", {"certificate_issued": "Y", "certificate_no": "A1", "certificate_dt": day(-2), "cert_valid_upto": day(100)}, format="json")
    check("certificate details can be saved", r.status_code == 200, r.content[:200])
    r = client.patch(f"{DTL}{tid}/", {"cert_valid_upto": day(-1)}, format="json")
    check("a changed Valid Upto in the past is refused", r.status_code == 400 and "cert_valid_upto" in keys(r), r.content[:200])


if __name__ == "__main__":
    with transaction.atomic():
        run()
        transaction.set_rollback(True)
    print()
    print("FAILED: " + ", ".join(FAILED) if FAILED else "All checks passed. Nothing was saved.")
    sys.exit(1 if FAILED else 0)
