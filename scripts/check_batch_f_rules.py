"""Checks the people, crew and mapping master rules (Batch F) through the real API.

    cd backend
    .venv/bin/python scripts/check_batch_f_rules.py

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
    CrewScheduleException, FsCatgToRigTypeMapping, JobDescriptionDtl, JobDescriptionHdr, MstCompetency, MstEmpType, MstFsCategory, MstRank,
    MstRigType, NationalityToEmpTypeMapping, ReportingStructure, RigCrewException, TravelEligibility, WkgrpIndicatorTypeMapping,
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

    def resave(url, qs, field_fn, label, limit=8):
        bad = []
        for o in qs[:limit]:
            r = client.patch(f"{url}{o.pk}/", field_fn(o), format="json")
            if r.status_code != 200:
                bad.append((o.pk, r.content.decode()[:120]))
        check(f"every existing {label} can still be saved", not bad, str(bad[:2]))

    print("Travel Eligibility")
    url = f"{base}travel-eligibility/"
    rank = MstRank.objects.first().pk
    tb = lambda **o: {"rank": rank, "travel_mode": "A", "travel_class": "Economy", "eligible_from": day(-300), **o}
    r = client.post(url, tb(), format="json")
    check("a new rule is accepted", r.status_code == 201, r.content.decode())
    refused(url, tb(eligible_from=day(1)), "eligible_from", "an Eligible From in the future")
    refused(url, tb(eligible_to=day(-400)), "eligible_to", "an Eligible To before From")
    check("an Eligible To equal to From is accepted", client.post(url, tb(eligible_to=day(-300)), format="json").status_code == 201)
    check("a planned future Eligible To is accepted", client.post(url, tb(eligible_to=day(90)), format="json").status_code == 201)
    resave(url, TravelEligibility.objects.exclude(pk=r.json()["travel_eligibility_id"]), lambda o: {"travel_class": o.travel_class}, "travel rule")

    print("Reporting Structure")
    url = f"{base}reporting-structure/"
    src = ReportingStructure.objects.exclude(reporting_rank=None).first()
    used = set(ReportingStructure.objects.filter(fs_category=src.fs_category).values_list("rank_id", flat=True))
    free = MstRank.objects.exclude(pk__in=used).first().pk
    r = client.post(url, {"fs_category": src.fs_category_id, "rank": free, "reporting_rank": src.reporting_rank_id}, format="json")
    check("a new line is accepted", r.status_code == 201, r.content.decode())
    refused(url, {"fs_category": src.fs_category_id, "rank": free}, "rank", "a repeat of Category + Rank")
    check("a line with no Reports To is accepted (it stays optional)", client.post(url, {"fs_category": MstFsCategory.objects.exclude(pk=src.fs_category_id).first().pk, "rank": free}, format="json").status_code == 201)
    resave(url, ReportingStructure.objects.exclude(pk=r.json()["reporting_structure_id"]), lambda o: {"reporting_rank": o.reporting_rank_id}, "reporting line", 20)

    print("Job Descriptions")
    uh, ud = f"{base}job-description-headers/", f"{base}job-description-details/"
    hdr_src = JobDescriptionHdr.objects.first()
    top = max(JobDescriptionHdr.objects.filter(rank=hdr_src.rank).values_list("jd_hdr_order", flat=True))
    r = client.post(uh, {"rank": hdr_src.rank_id, "jd_hdr_description": "ZZ Section", "jd_hdr_order": top + 1}, format="json")
    check("a new heading is accepted", r.status_code == 201, r.content.decode())
    hid = r.json()["jd_hdr_id"]
    refused(uh, {"rank": hdr_src.rank_id, "jd_hdr_description": "ZZ Again", "jd_hdr_order": top + 1}, "jd_hdr_order", "a repeated heading Order for the rank")
    refused(uh, {"rank": hdr_src.rank_id, "jd_hdr_description": "ZZ Act", "jd_hdr_order": top + 2, "jd_hdr_active": "X"}, "jd_hdr_active", "heading Active other than Y or N")
    check("a heading without an Order is accepted (Order is not required)", client.post(uh, {"rank": hdr_src.rank_id, "jd_hdr_description": "ZZ NoOrder"}, format="json").status_code == 201)
    r = client.post(ud, {"header": hid, "jd_dtl_description": "A fuller description here", "jd_dtl_order": 1}, format="json")
    check("a new line is accepted", r.status_code == 201, r.content.decode())
    did = r.json()["jd_dtl_id"]
    refused(ud, {"header": hid, "jd_dtl_description": "Another full description", "jd_dtl_order": 1}, "jd_dtl_order", "a repeated line Order under a heading")
    refused(ud, {"header": hid, "jd_dtl_description": "short", "jd_dtl_order": 2}, "jd_dtl_description", "a line under 10 characters")
    refused(ud, {"header": hid, "jd_dtl_description": "Another full description", "jd_dtl_order": 3, "jd_dtl_active": "X"}, "jd_dtl_active", "line Active other than Y or N")
    check("exactly 10 characters is accepted", client.post(ud, {"header": hid, "jd_dtl_description": "0123456789", "jd_dtl_order": 4}, format="json").status_code == 201)
    r = client.patch(f"{ud}{did}/", {"jd_dtl_description": "tiny"}, format="json")
    check("shortening a line under 10 characters is refused", r.status_code == 400 and "jd_dtl_description" in keys(r), r.content.decode())
    short = next((d for d in JobDescriptionDtl.objects.all() if len((d.jd_dtl_description or "").strip()) < 10), None)
    if short:
        check("an old short line can still be saved for something else", client.patch(f"{ud}{short.pk}/", {"jd_dtl_active": short.jd_dtl_active}, format="json").status_code == 200)
    resave(uh, JobDescriptionHdr.objects.exclude(pk=hid), lambda o: {"jd_hdr_description": o.jd_hdr_description}, "heading", 40)
    dups = JobDescriptionHdr.objects.values("rank", "jd_hdr_order").order_by()
    from django.db.models import Count
    rep = list(dups.annotate(n=Count("pk")).filter(n__gt=1).order_by("rank", "jd_hdr_order")[:1])
    rep = rep[0] if rep else None
    if rep:
        old = JobDescriptionHdr.objects.filter(rank=rep["rank"], jd_hdr_order=rep["jd_hdr_order"]).first()
        check("a heading that repeats an Order can still be renamed", client.patch(f"{uh}{old.pk}/", {"jd_hdr_description": old.jd_hdr_description}, format="json").status_code == 200)

    print("Competency")
    url = f"{base}competency/"
    c = MstCompetency.objects.first()
    r = client.post(url, {"competency_name": "ZZ Comp", "department": c.department_id}, format="json")
    check("a new competency is accepted", r.status_code == 201, r.content.decode())
    refused(url, {"competency_name": "ZZ Comp2", "department": c.department_id, "active": "X"}, "active", "Active other than Y or N")

    print("Category to Rig Type")
    url = f"{base}fs-catg-to-rig-type-mapping/"
    f = FsCatgToRigTypeMapping.objects.first()
    refused(url, {"fs_category": f.fs_category_id, "rig_type": f.rig_type_id}, "rig_type", "a repeat of Category + Rig Type")
    check("Active other than Y or N is refused", "mapping_active" in keys(client.patch(f"{url}{f.pk}/", {"mapping_active": "X"}, format="json")))
    resave(url, FsCatgToRigTypeMapping.objects.all(), lambda o: {"mapping_active": o.mapping_active}, "mapping")

    print("Nationality to Emp Type")
    url = f"{base}nationality-to-emp-type-mapping/"
    n = NationalityToEmpTypeMapping.objects.first()
    refused(url, {"fs_category": n.fs_category_id, "nationality": n.nationality, "emp_type": n.emp_type_id}, "emp_type", "a repeat of the three")
    check("Active other than Y or N is refused", "active" in keys(client.patch(f"{url}{n.pk}/", {"active": "X"}, format="json")))
    resave(url, NationalityToEmpTypeMapping.objects.all(), lambda o: {"active": o.active}, "mapping")

    print("Workgroup to Indicator Type")
    url = f"{base}wkgrp-indicator-type-mapping/"
    w = WkgrpIndicatorTypeMapping.objects.first()
    refused(url, {"workgroup": w.workgroup_id, "indicator_type": w.indicator_type_id}, "indicator_type", "a repeat of Workgroup + Indicator Type")
    resave(url, WkgrpIndicatorTypeMapping.objects.all(), lambda o: {"indicator_type": o.indicator_type_id}, "mapping", 15)

    for label, slug, Model in (("Rig Crew Exceptions", "rig-crew-exceptions", RigCrewException), ("Crew Schedule Exceptions", "crew-schedule-exceptions", CrewScheduleException)):
        print(label)
        url = f"{base}{slug}/"
        cat = MstFsCategory.objects.first().pk
        et = MstEmpType.objects.first().pk
        eb = lambda **o: {"fs_category": cat, "emp_type": et, "exception_from": day(-100), **o}
        r = client.post(url, eb(), format="json")
        check("a new exception is accepted", r.status_code == 201, r.content.decode())
        pk = next(v for k, v in r.json().items() if k.endswith("exception_id") or k == "cs_exception_id")
        refused(url, {"fs_category": cat, "exception_from": day(-100)}, "fs_emp", "no Emp Type, Rank or Employee")
        refused(url, eb(), "exception_to", "the same exception again")
        refused(url, eb(exception_from=day(1), rank=MstRank.objects.first().pk), "exception_from", "a From date in the future")
        refused(url, eb(exception_to=day(-200), rank=MstRank.objects.first().pk), "exception_to", "a To date before From")
        check("a To date equal to From is accepted", client.post(url, eb(exception_to=day(-100), rank=MstRank.objects.first().pk), format="json").status_code == 201)
        check("a planned future To date is accepted", client.post(url, eb(exception_to=day(60), rank=MstRank.objects.exclude(pk=MstRank.objects.first().pk).first().pk), format="json").status_code == 201)
        r = client.patch(f"{url}{pk}/", {"emp_type": None}, format="json")
        check("clearing the only Emp Type is refused", r.status_code == 400 and "fs_emp" in keys(r), r.content.decode())
        resave(url, Model.objects.exclude(pk=pk), lambda o: {"fs_category": o.fs_category_id}, "exception", 40)


if __name__ == "__main__":
    with transaction.atomic():
        run()
        transaction.set_rollback(True)
    print()
    print("FAILED: " + ", ".join(FAILED) if FAILED else "All checks passed. Nothing was saved.")
    sys.exit(1 if FAILED else 0)
