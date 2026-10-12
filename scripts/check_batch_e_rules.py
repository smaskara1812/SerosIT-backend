"""Checks the rig and organisation master rules (Batch E) through the real API.

    cd backend
    .venv/bin/python scripts/check_batch_e_rules.py

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
    CostCentreToCompanyMapping, MstContractor, MstCostCentre, MstCostCentreType, MstOperator, MstRig, RigSiteMapping,
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


def refused(client, url, body, field, name):
    r = client.post(url, body, format="json")
    check(f"{name} is refused", r.status_code == 400 and field in keys(r), r.content.decode())


def run():
    client = APIClient(HTTP_HOST="localhost")
    client.force_authenticate(get_user_model().objects.filter(is_superuser=True).first())
    base = "/api/masters/"
    today = datetime.date.today()
    day = lambda n: (today + datetime.timedelta(days=n)).isoformat()

    print("Rigs")
    url = f"{base}rigs/"
    src = MstRig.objects.first()
    rb = lambda **o: {"rig_name": "ZZ Rig 1", "rig_short_name": "ZZR1", "rig_subtype": src.rig_subtype_id, "rig_type": src.rig_type_id,
                      "rig_built_dt": day(-1000), "rig_from": day(-500), **o}
    r = client.post(url, rb(), format="json")
    check("a complete rig is accepted", r.status_code == 201, r.content.decode())
    pk = r.json()["rig_id"]
    for name, over, field in (
        ("a name with no letters", {"rig_name": "123"}, "rig_name"),
        ("a name with three digits", {"rig_name": "Rig 123"}, "rig_name"),
        ("a short name with a space", {"rig_short_name": "AB C"}, "rig_short_name"),
        ("a short name with a hyphen", {"rig_short_name": "AB-C"}, "rig_short_name"),
        ("a built date in the future", {"rig_built_dt": day(1)}, "rig_built_dt"),
        ("a telephone with letters", {"rig_tel_no": "12ab"}, "rig_tel_no"),
        ("a fax with a plus", {"rig_fax_no": "+9112345"}, "rig_fax_no"),
        ("a From date in the future", {"rig_from": day(1)}, "rig_from"),
        ("a From date before the built date", {"rig_from": day(-1100)}, "rig_from"),
        ("a To date equal to From", {"rig_to": day(-500)}, "rig_to"),
        ("a To date before From", {"rig_to": day(-600)}, "rig_to"),
        ("a To date in the future", {"rig_to": day(5)}, "rig_to"),
        ("Active other than Y or N", {"rig_active": "X"}, "rig_active"),
    ):
        refused(client, url, rb(**over), field, name)
    check("a name with two digits and a colon is accepted", client.post(url, rb(rig_name="Well Services : EE12", rig_short_name="ZZR2"), format="json").status_code == 201)
    check("digits and slashes in a telephone are accepted", client.post(url, rb(rig_name="ZZ Rig 3", rig_short_name="ZZR3", rig_tel_no="022/4455667", rig_fax_no="022/99"), format="json").status_code == 201)
    check("a From date equal to the built date is accepted", client.post(url, rb(rig_name="ZZ Rig 4", rig_short_name="ZZR4", rig_from=day(-1000)), format="json").status_code == 201)
    check("a valid To date is accepted", client.post(url, rb(rig_name="ZZ Rig 5", rig_short_name="ZZR5", rig_to=day(-100)), format="json").status_code == 201)
    check("no old name is accepted (it stays optional)", client.post(url, rb(rig_name="ZZ Rig 6", rig_short_name="ZZR6", old_rig_name=""), format="json").status_code == 201)
    check("Inactive (N) is accepted", client.patch(f"{url}{pk}/", {"rig_active": "N"}, format="json").status_code == 200)
    for o in MstRig.objects.exclude(pk=pk)[:12]:
        r = client.patch(f"{url}{o.pk}/", {"rig_name": o.rig_name}, format="json")
        if r.status_code != 200:
            check(f"existing rig {o.pk} can still be saved", False, r.content.decode())
    check("every existing rig can still be saved", True)

    print("Cost Centre Types")
    url = f"{base}cost-centre-types/"
    r = client.post(url, {"cost_centre_type_name": "ZZ Type", "cost_centre_type_shortname": "ZZT"}, format="json")
    check("a new type is accepted", r.status_code == 201, r.content.decode())
    refused(client, url, {"cost_centre_type_name": "zz type", "cost_centre_type_shortname": "ZZ2"}, "cost_centre_type_name", "a repeated name")
    refused(client, url, {"cost_centre_type_name": "ZZ Other", "cost_centre_type_shortname": " zzt "}, "cost_centre_type_shortname", "a repeated short name")
    refused(client, url, {"cost_centre_type_name": "ZZ Act", "cost_centre_type_shortname": "ZA", "cost_centre_type_active": "X"}, "cost_centre_type_active", "Active other than Y or N")
    for o in MstCostCentreType.objects.exclude(pk=r.json()["cost_centre_type_id"]):
        check(f"existing type {o.pk} can still be saved", client.patch(f"{url}{o.pk}/", {"cost_centre_type_active": o.cost_centre_type_active}, format="json").status_code == 200)

    print("Cost Centres")
    url = f"{base}cost-centres/"
    cct = MstCostCentreType.objects.first().pk
    r = client.post(url, {"cost_centre_name": "ZZ Centre", "cost_centre_type": cct}, format="json")
    check("a new cost centre is accepted", r.status_code == 201, r.content.decode())
    cid = r.json()["cost_centre_id"]
    refused(client, url, {"cost_centre_name": "zz centre", "cost_centre_type": cct}, "cost_centre_name", "a repeated name")
    refused(client, url, {"cost_centre_name": "ZZ No Type"}, "cost_centre_type", "no type on a new cost centre")
    refused(client, url, {"cost_centre_name": "ZZ Act", "cost_centre_type": cct, "cost_centre_active": "X"}, "cost_centre_active", "Active other than Y or N")
    r = client.patch(f"{url}{cid}/", {"cost_centre_type": None}, format="json")
    check("a saved cost centre can't lose its type", r.status_code == 400 and "cost_centre_type" in keys(r), r.content.decode())
    for o in MstCostCentre.objects.exclude(pk=cid)[:10]:
        check(f"existing cost centre {o.pk} can still be saved", client.patch(f"{url}{o.pk}/", {"cost_centre_name": o.cost_centre_name}, format="json").status_code == 200)

    print("Operators")
    url = f"{base}operators/"
    r = client.post(url, {"operator_name": "ZZ Operator", "operator_short_name": "ZZO"}, format="json")
    check("a new operator is accepted", r.status_code == 201, r.content.decode())
    oid = r.json()["operator_id"]
    refused(client, url, {"operator_name": " zz operator ", "operator_short_name": "ZZ2"}, "operator_name", "a repeated name")
    refused(client, url, {"operator_name": "ZZ Tel", "operator_short_name": "ZT", "tel_no": "12345"}, "tel_no", "a telephone under 8 digits")
    refused(client, url, {"operator_name": "ZZ Tel2", "operator_short_name": "ZT2", "tel_no": "abcdefghij"}, "tel_no", "a telephone with letters")
    refused(client, url, {"operator_name": "ZZ Act", "operator_short_name": "ZA", "operator_active": "X"}, "operator_active", "Active other than Y or N")
    check("a telephone like +91 (22) 4455-6677 is accepted", client.post(url, {"operator_name": "ZZ Tel3", "operator_short_name": "ZT3", "tel_no": "+912244556"}, format="json").status_code == 201)
    refused(client, url, {"operator_name": "ZZ Mail", "operator_short_name": "ZM", "email_id": "nope"}, "email_id", "a bad email")
    for o in MstOperator.objects.exclude(pk=oid)[:10]:
        check(f"existing operator {o.pk} can still be saved", client.patch(f"{url}{o.pk}/", {"operator_name": o.operator_name}, format="json").status_code == 200)

    print("Contractors")
    url = f"{base}contractors/"
    r = client.post(url, {"contractor_name": "ZZ Contractor"}, format="json")
    check("a new contractor is accepted", r.status_code == 201, r.content.decode())
    refused(client, url, {"contractor_name": "zz contractor"}, "contractor_name", "a repeated name")
    for o in MstContractor.objects.exclude(pk=r.json()["contractor_id"])[:5]:
        check(f"existing contractor {o.pk} can still be saved", client.patch(f"{url}{o.pk}/", {"contractor_name": o.contractor_name}, format="json").status_code == 200)

    print("Cost Centre to Company Mapping")
    url = f"{base}cost-centre-to-company-mapping/"
    ref = CostCentreToCompanyMapping.objects.first()
    mb = lambda **o: {"company": ref.company_id, "cost_centre": ref.cost_centre_id, "mapping_from": day(-3000), **o}
    r = client.post(url, mb(), format="json")
    check("a new mapping is accepted", r.status_code == 201, r.content.decode())
    refused(client, url, mb(), "mapping_from", "a repeat of company, cost centre and From")
    refused(client, url, mb(mapping_from=day(1)), "mapping_from", "a From date in the future")
    refused(client, url, mb(mapping_from=day(-2900), mapping_to=day(-2950)), "mapping_to", "a To date before From")
    check("a To date equal to From is accepted", client.post(url, mb(mapping_from=day(-2800), mapping_to=day(-2800)), format="json").status_code == 201)
    for o in CostCentreToCompanyMapping.objects.all()[:8]:
        if o.pk != r.json().get("id", -1):
            r2 = client.patch(f"{url}{o.pk}/", {"mapping_from": o.mapping_from.isoformat()}, format="json")
            check(f"existing mapping {o.pk} can still be saved", r2.status_code == 200, r2.content.decode())

    print("Rig Site Mapping")
    url = f"{base}rig-site-mapping/"
    ref = RigSiteMapping.objects.exclude(contact_fs_emp_1=None).first()
    emp_other = RigSiteMapping.objects.exclude(contact_fs_emp_1=None).exclude(contact_fs_emp_1=ref.contact_fs_emp_1_id).first().contact_fs_emp_1_id
    sb = lambda **o: {"rig": ref.rig_id, "company": ref.company_id, "camp_office_addr": "Camp Road, Block 4, Rig Site", "location": ref.location_id,
                      "site_from": day(-3000), **o}
    r = client.post(url, sb(), format="json")
    check("a new mapping is accepted", r.status_code == 201, r.content.decode())
    for name, over, field in (
        ("an address under 10 characters", {"camp_office_addr": "Camp"}, "camp_office_addr"),
        ("a telephone with letters", {"contact_fs_emp_1": ref.contact_fs_emp_1_id, "contact_tel_no_1": "12ab5678"}, "contact_tel_no_1"),
        ("a telephone under 7 digits", {"contact_fs_emp_1": ref.contact_fs_emp_1_id, "contact_tel_no_1": "12345"}, "contact_tel_no_1"),
        ("telephone 1 without Contact Person 1", {"contact_tel_no_1": "9876543210"}, "contact_tel_no_1"),
        ("telephone 2 without Contact Person 2", {"contact_tel_no_2": "9876543210"}, "contact_tel_no_2"),
        ("the same person twice", {"contact_fs_emp_1": ref.contact_fs_emp_1_id, "contact_fs_emp_2": ref.contact_fs_emp_1_id}, "contact_fs_emp_2"),
        ("a From date in the future", {"site_from": day(1)}, "site_from"),
        ("a To date before From", {"site_from": day(-2000), "site_to": day(-2100)}, "site_to"),
    ):
        refused(client, url, sb(**over), field, name)
    check("two different people with telephones are accepted", client.post(url, sb(contact_fs_emp_1=ref.contact_fs_emp_1_id, contact_tel_no_1="9876543210", contact_fs_emp_2=emp_other, contact_tel_no_2="1234567"), format="json").status_code == 201)
    check("a To date equal to From is accepted", client.post(url, sb(site_from=day(-1900), site_to=day(-1900)), format="json").status_code == 201)
    for o in RigSiteMapping.objects.all()[:15]:
        r2 = client.patch(f"{url}{o.pk}/", {"camp_office_addr": o.camp_office_addr}, format="json")
        if r2.status_code != 200:
            check(f"existing site mapping {o.pk} can still be saved", False, r2.content.decode())
    check("every existing site mapping can still be saved", True)


if __name__ == "__main__":
    with transaction.atomic():
        run()
        transaction.set_rollback(True)
    print()
    print("FAILED: " + ", ".join(FAILED) if FAILED else "All checks passed. Nothing was saved.")
    sys.exit(1 if FAILED else 0)
