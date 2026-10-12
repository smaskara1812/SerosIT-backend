"""Checks the access, mapping and approval master rules (Batch G) through the real API.

    cd backend
    .venv/bin/python scripts/check_batch_g_rules.py

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

from core.models import (
    ApproverMapping, DocToSignMapping, MstApprovalCode, MstInterviewer, MstRig, MstUserFsCatgMapping, MstUserRigMapping,
)

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

    def refused(url, body, field, name):
        r = client.post(url, body, format="json")
        check(f"{name} is refused", r.status_code == 400 and field in keys(r), r.content.decode())

    def resave(url, qs, field_fn, label, limit=25):
        bad = []
        for o in qs[:limit]:
            r = client.patch(f"{url}{o.pk}/", field_fn(o), format="json")
            if r.status_code != 200:
                bad.append((o.pk, r.content.decode()[:120]))
        check(f"every existing {label} can still be saved", not bad, str(bad[:2]))

    print("Approval Code")
    url = f"{base}approval-codes/"
    r = client.post(url, {"approval_code": "ZZ_CODE", "approval_desc": "Rule check"}, format="json")
    check("a new code is accepted", r.status_code == 201, r.content.decode())
    refused(url, {"approval_code": "zz_code", "approval_desc": "Again"}, "approval_code", "a repeated code")
    refused(url, {"approval_code": " ZZ_CODE ", "approval_desc": "Again"}, "approval_code", "a repeated code with spaces")
    refused(url, {"approval_code": "ZZ_2", "approval_desc": "x", "approval_active": "X"}, "approval_active", "Active other than Y or N")
    check("Inactive (N) is accepted", client.post(url, {"approval_code": "ZZ_3", "approval_desc": "x", "approval_active": "N"}, format="json").status_code == 201)
    resave(url, MstApprovalCode.objects.exclude(pk=r.json()["approval_code_id"]), lambda o: {"approval_desc": o.approval_desc}, "approval code")

    print("Approver Mapping")
    url = f"{base}approver-mappings/"
    src = ApproverMapping.objects.first()
    rigs = list(MstRig.objects.values_list("pk", flat=True)[:2])
    new_code = MstApprovalCode.objects.exclude(pk=src.approval_code_id).first().pk
    body = lambda **o: {"approval_code": new_code, "approver_user": src.approver_user_id, "approver_level": 1, "approver_active": "Y",
                        "details": [{"rig": rigs[0], "approve_yn": "Y"}], **o}
    r = client.post(url, body(), format="json")
    check("a new mapping is accepted", r.status_code == 201, r.content.decode())
    mid = r.json()["approver_mapping_id"]
    r = client.post(url, body(approver_level=2), format="json")
    check("the same user at another level of the same approval code is accepted (no one-per-code rule, by decision)", r.status_code == 201, r.content.decode())
    refused(url, body(approval_code=MstApprovalCode.objects.exclude(pk__in=(new_code, src.approval_code_id)).first().pk, approver_active="X"), "approver_active", "Active other than Y or N")
    other_user = ApproverMapping.objects.exclude(approver_user=src.approver_user_id).first().approver_user_id
    refused(url, body(approver_user=other_user, details=[{"rig": rigs[0]}, {"rig": rigs[0]}]), "details", "the same rig and department twice")
    refused(url, body(approver_user=other_user, details=[{"rig": rigs[0], "approve_yn": "X"}]), "details", "a flag other than Yes or No")
    check("two different rigs are accepted", client.post(url, body(approver_user=other_user, details=[{"rig": rigs[0]}, {"rig": rigs[1]}]), format="json").status_code == 201)
    check("a level is required", "approver_level" in keys(client.post(url, {k: v for k, v in body(approver_user=other_user).items() if k != "approver_level"}, format="json")))
    check("saving a mapping again is fine", client.patch(f"{url}{mid}/", {"approver_level": 2}, format="json").status_code == 200)
    bad = []
    for m in ApproverMapping.objects.exclude(pk=mid)[:60]:
        r2 = client.patch(f"{url}{m.pk}/", {"approver_level": m.approver_level}, format="json")
        if r2.status_code != 200:
            bad.append((m.pk, r2.content.decode()[:100]))
    check("every existing mapping can still be saved (including the old repeated user and code pairs)", not bad, str(bad[:2]))

    for label, slug, Model, target, tfield in (("User Rig Mapping", "user-rig-mapping", MstUserRigMapping, "rig", MstRig), ("User Category Mapping", "user-category-mapping", MstUserFsCatgMapping, "fs_category", None)):
        print(label)
        url = f"{base}{slug}/"
        ref = Model.objects.first()
        mb = lambda **o: {"user": ref.user_id, target: getattr(ref, f"{target}_id"), "mapping_from": day(-4000), **o}
        r = client.post(url, mb(), format="json")
        check("a new mapping is accepted", r.status_code == 201, r.content.decode())
        refused(url, mb(), "mapping_from", "a repeat of User + target + From")
        refused(url, mb(mapping_from=day(1)), "mapping_from", "a From date in the future")
        refused(url, mb(mapping_from=day(-3900), mapping_to=day(-3950)), "mapping_to", "a To date before From")
        check("a To date equal to From is accepted", client.post(url, mb(mapping_from=day(-3800), mapping_to=day(-3800)), format="json").status_code == 201)
        check("a planned future To date is accepted", client.post(url, mb(mapping_from=day(-3700), mapping_to=day(60)), format="json").status_code == 201)
        resave(url, Model.objects.exclude(pk=r.json().get("user_rig_mapping_id", r.json().get("user_fs_catg_mapping_id"))), lambda o: {"mapping_from": o.mapping_from.isoformat()}, "mapping", 120)

    print("Document To Sign Mapping")
    url = f"{base}doc-to-sign-mapping/"
    ref = DocToSignMapping.objects.first()
    sb = lambda **o: {"doc_name": ref.doc_name, "employee": ref.employee_id, "sign_from": day(-4000), **o}
    r = client.post(url, sb(), format="json")
    check("a new signer is accepted", r.status_code == 201, r.content.decode())
    refused(url, sb(doc_name=ref.doc_name.lower()), "sign_from", "a repeat of Document + Employee + From (other capitals)")
    refused(url, sb(sign_from=day(1)), "sign_from", "a From date in the future")
    refused(url, sb(sign_from=day(-3900), sign_to=day(-3950)), "sign_to", "a To date before From")
    check("a planned future To date is accepted", client.post(url, sb(sign_from=day(-3700), sign_to=day(90)), format="json").status_code == 201)
    resave(url, DocToSignMapping.objects.exclude(pk=r.json()["doc_to_sign_id"]), lambda o: {"doc_name": o.doc_name}, "signer", 140)

    print("Department To Interviewer Mapping")
    url = f"{base}interviewer-mapping/"
    ref = MstInterviewer.objects.first()
    check("Active other than Y or N is refused", "active" in keys(client.patch(f"{url}{ref.pk}/", {"active": "X"}, format="json")))
    check("Inactive (N) is accepted", client.patch(f"{url}{ref.pk}/", {"active": "N"}, format="json").status_code == 200)
    resave(url, MstInterviewer.objects.all(), lambda o: {"active": o.active}, "interviewer")


if __name__ == "__main__":
    with transaction.atomic():
        run()
        transaction.set_rollback(True)
    print()
    print("FAILED: " + ", ".join(FAILED) if FAILED else "All checks passed. Nothing was saved.")
    sys.exit(1 if FAILED else 0)
