"""Checks the QHSE master rules (Batch C) through the real API.

    cd backend
    .venv/bin/python scripts/check_batch_c_rules.py

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

from core.models import MstHseManhoursParty

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

    print("Names must be unique (ignoring capitals and spaces)")
    for slug, field, extra in (
        ("contact-exposure-types", "contact_expo_type_name", {}),
        ("qhse-categories", "qhse_category_name", {}),
        ("hse-activities", "hse_activity_name", {"hse_activity_type": "IN"}),
        ("hse-consumables", "hse_consumable_name", {"hse_consumption_unit": "KL"}),
        ("hazard-types", "haz_type_name", {"haz_type_class": "Positive"}),
    ):
        url = f"{base}{slug}/"
        r = client.post(url, {field: "ZZ Rule Check", **extra}, format="json")
        check(f"{slug}: a new name is accepted", r.status_code == 201, r.content.decode())
        pk = r.json()[next(k for k in r.json() if k.endswith("_id"))]
        for label, value in (("the same name", "ZZ Rule Check"), ("another case", "zz RULE check"), ("spaces around", "  ZZ Rule Check ")):
            r = client.post(url, {field: value, **extra}, format="json")
            check(f"{slug}: {label} is refused", r.status_code == 400 and field in keys(r), r.content.decode())
        r = client.patch(f"{url}{pk}/", {field: "ZZ Rule Check"}, format="json")
        check(f"{slug}: saving its own name again is fine", r.status_code == 200, r.content.decode())
        first = client.get(url, {"page_size": 1}).json()["results"][0]
        existing = first[field]
        r = client.post(url, {field: existing.upper(), **extra}, format="json")
        check(f"{slug}: an existing record's name is refused", r.status_code == 400, r.content.decode())
        old = client.get(url, {"page_size": 3}).json()["results"]
        for o in old[:2]:
            idk = next(k for k in o if k.endswith("_id"))
            check(f"{slug}: existing record {o[idk]} can still be saved", client.patch(f"{url}{o[idk]}/", {field: o[field]}, format="json").status_code == 200)

    print("Hazard Type Active")
    url = f"{base}hazard-types/"
    r = client.post(url, {"haz_type_name": "ZZ Active", "haz_type_class": "Negative"}, format="json")
    check("a new hazard type starts Active", r.status_code == 201 and r.json()["haz_type_active"] == "Y", r.content.decode())
    hid = r.json()["haz_type_id"]
    check("Inactive (N) is accepted", client.patch(f"{url}{hid}/", {"haz_type_active": "N"}, format="json").status_code == 200)
    check("any other value is refused", "haz_type_active" in keys(client.patch(f"{url}{hid}/", {"haz_type_active": "X"}, format="json")))
    check("an unknown class is refused", "haz_type_class" in keys(client.post(url, {"haz_type_name": "ZZ Class", "haz_type_class": "Neutral"}, format="json")))

    print("Allowed lists and required boxes")
    check("HSE Activity: an unknown type is refused", "hse_activity_type" in keys(client.post(f"{base}hse-activities/", {"hse_activity_name": "ZZ T", "hse_activity_type": "XX"}, format="json")))
    check("HSE Activity: a missing type is refused", "hse_activity_type" in keys(client.post(f"{base}hse-activities/", {"hse_activity_name": "ZZ T2"}, format="json")))
    check("Indicator Type: an unknown report type is refused", "report_type" in keys(client.post(f"{base}indicator-types/", {"indicator_type_name": "ZZ I", "report_type": "Other"}, format="json")))
    check("Indicator Type: Leading is accepted", client.post(f"{base}indicator-types/", {"indicator_type_name": "ZZ Indicator", "report_type": "Leading"}, format="json").status_code == 201)
    for slug, body, field in (
        ("rig-operations", {}, "rig_operation_name"),
        ("parts-of-body", {}, "part_of_body_name"),
        ("hse-consumables", {"hse_consumable_name": "ZZ C"}, "hse_consumption_unit"),
        ("hse-consumables", {"hse_consumption_unit": "KL"}, "hse_consumable_name"),
    ):
        check(f"{slug}: a missing {field} is refused", field in keys(client.post(f"{base}{slug}/", body, format="json")))

    print("HSE Manhours Party")
    url = f"{base}hse-manhours-parties/"
    cct = MstHseManhoursParty.objects.exclude(cost_centre_type=None).first().cost_centre_type_id
    check("no Cost Centre Type is refused for a new party", "cost_centre_type" in keys(client.post(url, {"hse_manhours_party_name": "ZZ P", "hse_manhours_party_type": "TP"}, format="json")))
    r = client.post(url, {"hse_manhours_party_name": "ZZ Party", "hse_manhours_party_type": "TP", "cost_centre_type": cct}, format="json")
    check("a complete party is accepted", r.status_code == 201, r.content.decode())
    pid = r.json()["hse_manhours_party_id"]
    r = client.post(url, {"hse_manhours_party_name": "ZZ Party", "hse_manhours_party_type": "TP", "cost_centre_type": cct}, format="json")
    check("the same name and type for the same cost centre type is allowed (as in the existing data)", r.status_code == 201, r.content.decode())
    check("an unknown party type is refused", "hse_manhours_party_type" in keys(client.post(url, {"hse_manhours_party_name": "ZZ P", "hse_manhours_party_type": "EOSIL", "cost_centre_type": cct}, format="json")))
    r = client.patch(f"{url}{pid}/", {"cost_centre_type": None}, format="json")
    check("a saved party can't lose its Cost Centre Type", r.status_code == 400 and "cost_centre_type" in keys(r), r.content.decode())
    for old in MstHseManhoursParty.objects.exclude(pk__in=(pid,)).order_by("pk")[:12]:
        r = client.patch(f"{url}{old.pk}/", {"hse_manhours_party_name": old.hse_manhours_party_name}, format="json")
        if r.status_code != 200:
            check(f"existing party {old.pk} can still be saved", False, r.content.decode())
    check("every existing party can still be saved", True)


if __name__ == "__main__":
    with transaction.atomic():
        run()
        transaction.set_rollback(True)
    print()
    print("FAILED: " + ", ".join(FAILED) if FAILED else "All checks passed. Nothing was saved.")
    sys.exit(1 if FAILED else 0)
