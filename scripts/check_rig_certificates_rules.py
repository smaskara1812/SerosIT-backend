"""Checks the Rig Certificates and Rig Certificate Schedule rules through the real API.

    cd backend
    .venv/bin/python scripts/check_rig_certificates_rules.py

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

from core.models import RigCert, RigCertSchedule

CERT = "/api/qhse/rig-certificates/"
SCHED = "/api/qhse/rig-certificate-schedule/"
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
    src = RigCert.objects.order_by("pk").first()
    today = datetime.date.today()
    day = lambda n: (today + datetime.timedelta(days=n)).isoformat()
    n = [0]

    def cert(**over):
        n[0] += 1
        base = {
            "rig": src.rig_id, "buss_cert": src.buss_cert_id, "buss_cert_issue_authority": src.buss_cert_issue_authority_id,
            "certificate_no": f"ZZ-{n[0]}", "cert_date": day(-400 - n[0]), "valid_till": day(300),
        }
        base.update(over)
        return base

    print("Rig Certificates")
    r = client.post(CERT, cert(), format="json")
    check("a complete certificate is accepted", r.status_code == 201, r.content[:200])
    first = r.json()
    check("no Valid Till is accepted", client.post(CERT, cert(valid_till=None), format="json").status_code == 201)
    for name, over, field in (
        ("a future Certificate Date is refused", {"cert_date": day(1), "valid_till": day(300)}, "cert_date"),
        ("Valid Till equal to the Date is refused", {"cert_date": day(-10), "valid_till": day(-10)}, "valid_till"),
        ("Valid Till before the Date is refused", {"cert_date": day(-10), "valid_till": day(-20)}, "valid_till"),
        ("a used Certificate No. is refused", {"certificate_no": first["certificate_no"]}, "certificate_no"),
        ("the same number in other letters is refused", {"certificate_no": first["certificate_no"].lower()}, "certificate_no"),
        ("the same rig, certificate and date is refused", {"cert_date": first["cert_date"]}, "cert_date"),
    ):
        r = client.post(CERT, cert(**over), format="json")
        check(name, r.status_code == 400 and field in keys(r), r.content[:200])
    check("today is accepted as the Date", client.post(CERT, cert(cert_date=day(0), valid_till=day(30)), format="json").status_code == 201)

    pk = first["rig_cert_id"]
    r = client.patch(f"{CERT}{pk}/", {"remark": "edited"}, format="json")
    check("editing a remark is accepted", r.status_code == 200, r.content[:200])
    r = client.patch(f"{CERT}{pk}/", {"certificate_no": first["certificate_no"]}, format="json")
    check("saving the same number again is not a duplicate", r.status_code == 200, r.content[:200])
    r = client.patch(f"{CERT}{pk}/", {"valid_till": first["cert_date"]}, format="json")
    check("changing Valid Till to the Date is refused", r.status_code == 400 and "valid_till" in keys(r))

    print("Existing certificates are left as they are")
    for old in RigCert.objects.exclude(pk=pk)[:5]:
        r = client.patch(f"{CERT}{old.pk}/", {"remark": "rule check"}, format="json")
        check(f"certificate {old.pk} can still be edited", r.status_code == 200, r.content[:200])

    print("Rig Certificate Schedule")
    sc = lambda **o: {"rig_cert": pk, "scheduled_dt": day(10), "schedule_type": "A", **o}
    r = client.post(SCHED, sc(), format="json")
    check("a future schedule is accepted", r.status_code == 201, r.content[:200])
    sid = r.json()["rig_cert_schedule_id"]
    check("today is accepted as Scheduled Date", client.post(SCHED, sc(scheduled_dt=day(0)), format="json").status_code == 201)
    r = client.post(SCHED, sc(scheduled_dt=day(-1)), format="json")
    check("a past Scheduled Date is refused", r.status_code == 400 and "scheduled_dt" in keys(r), r.content[:200])
    r = client.post(SCHED, sc(completion_dt=day(1)), format="json")
    check("a future Completion Date is refused", r.status_code == 400 and "completion_dt" in keys(r), r.content[:200])
    check("a Completion Date of today is accepted", client.post(SCHED, sc(completion_dt=day(0)), format="json").status_code == 201)
    check("an unknown schedule type is refused", client.post(SCHED, sc(schedule_type="X"), format="json").status_code == 400)
    r = client.patch(f"{SCHED}{sid}/", {"scheduled_dt": day(-3)}, format="json")
    check("changing the date to the past is refused", r.status_code == 400 and "scheduled_dt" in keys(r))
    old = RigCertSchedule.objects.filter(scheduled_dt__lt=today, completion_dt__isnull=True).first()
    if old is None:
        print("  skip  no old past schedule")
    else:
        r = client.patch(f"{SCHED}{old.pk}/", {"completion_dt": day(-1)}, format="json")
        check("an old past schedule can still be completed", r.status_code == 200, r.content[:200])
        r = client.patch(f"{SCHED}{old.pk}/", {"remark": "rule check", "scheduled_dt": old.scheduled_dt.isoformat()}, format="json")
        check("the same past date sent again is not a change", r.status_code == 200, r.content[:200])


if __name__ == "__main__":
    with transaction.atomic():
        run()
        transaction.set_rollback(True)
    print()
    print("FAILED: " + ", ".join(FAILED) if FAILED else "All checks passed. Nothing was saved.")
    sys.exit(1 if FAILED else 0)
