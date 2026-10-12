"""Checks the Training Group and Training Org rules through the real API.

    cd backend
    .venv/bin/python scripts/check_training_group_org_rules.py

Runs every request inside one transaction that is rolled back at the end, so
nothing is saved. Needs the normal dev data. Exits with status 1 if any check fails.
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

from core.models import HseTrainingGroupHdr, HseTrainingOrgDtl, HseTrainingOrgHdr

GROUP = "/api/qhse/training-group/"
ORG = "/api/qhse/training-org/"
TRAINER = "/api/qhse/training-org-trainers/"
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

    print("Training Group")
    r = client.post(GROUP, {"training_group_hdr_name": "ZZ Rule Check"}, format="json")
    check("a new group is created", r.status_code == 201, r.content[:200])
    for name, v in (("the same name", "ZZ Rule Check"), ("the same name in other letters", "zz rule CHECK"), ("the same name with spaces around", "  ZZ Rule Check  ")):
        r = client.post(GROUP, {"training_group_hdr_name": v}, format="json")
        check(f"{name} is refused", r.status_code == 400 and "training_group_hdr_name" in keys(r), r.content[:200])
    check("a blank name is refused", "training_group_hdr_name" in keys(client.post(GROUP, {"training_group_hdr_name": "  "}, format="json")))
    existing = HseTrainingGroupHdr.objects.exclude(training_group_hdr_name="ZZ Rule Check").first()
    r = client.post(GROUP, {"training_group_hdr_name": existing.training_group_hdr_name.upper()}, format="json")
    check("an existing group's name is refused", r.status_code == 400, r.content[:200])
    pk = HseTrainingGroupHdr.objects.get(training_group_hdr_name="ZZ Rule Check").pk
    r = client.patch(f"{GROUP}{pk}/", {"training_group_hdr_name": "ZZ Rule Check"}, format="json")
    check("saving the same name again is not a duplicate", r.status_code == 200, r.content[:200])

    print("Training Org")
    src = HseTrainingOrgHdr.objects.first()
    body = {"training_org_name": "ZZ Rule Org", "training_org_address": "1 Test Road", "location": src.location_id}
    r = client.post(ORG, body, format="json")
    check("a new organisation is created", r.status_code == 201, r.content[:200])
    org = r.json()["training_org_hdr_id"]
    for name, v in (("the same name", "ZZ Rule Org"), ("the same name in other letters", "zz rule org"), ("the existing organisation's name", src.training_org_name.upper())):
        r = client.post(ORG, {**body, "training_org_name": v}, format="json")
        check(f"{name} is refused", r.status_code == 400 and "training_org_name" in keys(r), r.content[:200])
    check("a bad org email is refused", "training_org_email" in keys(client.patch(f"{ORG}{org}/", {"training_org_email": "nope"}, format="json")))
    r = client.patch(f"{ORG}{org}/", {"training_org_address": "2 Test Road"}, format="json")
    check("editing the address is accepted", r.status_code == 200, r.content[:200])

    print("Trainers")
    t = lambda **o: {"hdr": org, "trainer_fname": "Ann", "trainer_lname": "Lee", "trainer_mobile_no": "9000000001", **o}
    r = client.post(TRAINER, t(), format="json")
    check("a trainer is added", r.status_code == 201, r.content[:200])
    first = r.json()["training_org_dtl_id"]
    r = client.post(TRAINER, t(trainer_fname="Bob"), format="json")
    check("the same mobile in the same organisation is refused", r.status_code == 400 and "trainer_mobile_no" in keys(r), r.content[:200])
    check("trainers without a mobile don't clash", client.post(TRAINER, t(trainer_mobile_no=None, trainer_fname="C"), format="json").status_code == 201
          and client.post(TRAINER, t(trainer_mobile_no=None, trainer_fname="D"), format="json").status_code == 201)
    other = HseTrainingOrgDtl.objects.exclude(hdr=org).exclude(trainer_mobile_no__isnull=True).exclude(trainer_mobile_no="").first()
    r = client.post(TRAINER, t(trainer_mobile_no=other.trainer_mobile_no, trainer_fname="E"), format="json")
    check("a mobile used at another organisation is accepted", r.status_code == 201, r.content[:200])
    second = client.post(TRAINER, t(trainer_mobile_no="9000000002", trainer_fname="F"), format="json").json()["training_org_dtl_id"]
    r = client.patch(f"{TRAINER}{second}/", {"trainer_mobile_no": "9000000001"}, format="json")
    check("changing a mobile to a used one is refused", r.status_code == 400 and "trainer_mobile_no" in keys(r))
    check("saving the same mobile again is not a duplicate", client.patch(f"{TRAINER}{first}/", {"trainer_mobile_no": "9000000001"}, format="json").status_code == 200)
    check("a bad trainer email is refused", "trainer_email_id" in keys(client.patch(f"{TRAINER}{first}/", {"trainer_email_id": "x"}, format="json")))
    check("a mobile with letters is refused", "trainer_mobile_no" in keys(client.patch(f"{TRAINER}{first}/", {"trainer_mobile_no": "12ab"}, format="json")))

    print("Existing records are left as they are")
    for g in HseTrainingGroupHdr.objects.exclude(pk=pk)[:3]:
        check(f"group {g.pk} can still be saved", client.patch(f"{GROUP}{g.pk}/", {"training_group_hdr_name": g.training_group_hdr_name}, format="json").status_code == 200)
    for d in HseTrainingOrgDtl.objects.exclude(hdr=org)[:3]:
        r = client.patch(f"{TRAINER}{d.pk}/", {"trainer_qualification": "rule check"}, format="json")
        check(f"trainer {d.pk} can still be edited", r.status_code == 200, r.content[:200])


if __name__ == "__main__":
    with transaction.atomic():
        run()
        transaction.set_rollback(True)
    print()
    print("FAILED: " + ", ".join(FAILED) if FAILED else "All checks passed. Nothing was saved.")
    sys.exit(1 if FAILED else 0)
