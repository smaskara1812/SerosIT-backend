"""Checks Masters > HR > Earnings and Deductions (mst_ed) and Earning / Deduction Types (mst_ed_type) through the real API.

    cd backend
    .venv/bin/python scripts/check_ed_masters.py

Runs inside one transaction that is rolled back at the end, so nothing is saved. Exits with status 1 if any check fails.
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
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import MstEd, MstUser, UserPermission, UserProfile
from core.permissions import invalidate_user_access

ED, TYPE = "/api/masters/eds/", "/api/masters/ed-types/"
FAILED = []


def check(name, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


def make_user(login, admin=False, keys=()):
    mst = MstUser.objects.create(user_name=login, user_login_id=login, user_active="Y", user_type_id="N", user_from=datetime.date(2020, 1, 1), cr_user_id=1, cr_dt=timezone.now())
    UserProfile.objects.create(user_id=mst.user_id, user_login_id=login, is_app_admin=admin)
    for key, flags in keys:
        UserPermission.objects.create(user_id=mst.user_id, menu_key=key, can_view=flags.get("view", False), can_add=flags.get("add", False), can_edit=flags.get("edit", False),
                                      can_delete=flags.get("delete", False), can_export=False)
    invalidate_user_access(login)
    c = APIClient(HTTP_HOST="localhost")
    c.force_authenticate(get_user_model().objects.create_user(username=login, password="x"))
    return c


def run():
    admin = make_user("zz_ed_admin", admin=True)
    viewer = make_user("zz_ed_viewer", keys=[("masters.eds", {"view": True})])
    nobody = make_user("zz_ed_nobody")

    print("What was loaded")
    check("35 components and 2 types", MstEd.objects.count() >= 35 and admin.get(TYPE).json()["count"] == 2 if isinstance(admin.get(TYPE).json(), dict) else len(admin.get(TYPE).json()) == 2)
    check("13 components can go on a letter", MstEd.objects.filter(in_offer_letter="Y").count() == 13)
    check("Basic is an earning, counts in the total, and is taxable", MstEd.objects.filter(pk=1, ed_type_id=1, counts_in_total="Y", taxable="Y").exists())
    r = admin.get(ED, {"page_size": 100}).json()
    rows = r["results"] if isinstance(r, dict) else r
    check("the list answers with the type name", rows and all("ed_type_name" in x for x in rows))
    check("filter by 'can be on a letter' works", len(admin.get(ED, {"in_offer_letter": "Y", "page_size": 100}).json()["results"]) == 13)

    print("Rules")
    base = {"ed_name": "Zz Test Allowance", "ed_abrv": "ZZ", "ed_type": 1, "ed_order": 90}
    r = admin.post(ED, base, format="json")
    check("a component can be added", r.status_code == 201 and r.json()["ed_type_name"] == "Earning", r.content[:200])
    new_id = r.json()["ed_id"]
    check("the same name (any capitals) is refused", admin.post(ED, {**base, "ed_name": "zz test allowance "}, format="json").status_code == 400)
    check("a blank name is refused", admin.post(ED, {**base, "ed_name": " "}, format="json").status_code == 400)
    r = admin.patch(f"{ED}{new_id}/", {"counts_in_total": "Y"}, format="json")
    check("counting in the total needs 'can be on a letter'", r.status_code == 400 and "counts_in_total" in r.json(), r.content[:200])
    r = admin.patch(f"{ED}{new_id}/", {"in_offer_letter": "Y", "counts_in_total": "Y"}, format="json")
    check("both together are fine", r.status_code == 200 and r.json()["in_offer_letter"] == "Y")
    letters = admin.get("/api/hr/fs-offer-letters/components/").json()
    check("the offer letter picks it up at once", any(c["component"] == new_id for c in letters))
    admin.patch(f"{ED}{new_id}/", {"ed_active": "N"}, format="json")
    check("an inactive component leaves the offer letter list", not any(c["component"] == new_id for c in admin.get("/api/hr/fs-offer-letters/components/").json()))
    check("it can be deleted when unused", admin.delete(f"{ED}{new_id}/").status_code == 204)
    r = admin.delete(f"{ED}1/")
    check("Basic cannot be deleted: offer letters use it", r.status_code == 400, r.content[:200])
    check("a type with components cannot be deleted", admin.delete(f"{TYPE}1/").status_code == 400)
    t = admin.post(TYPE, {"ed_type_name": "Zz Type", "ed_type_abrv": "Z"}, format="json")
    check("a type can be added and deleted", t.status_code == 201 and admin.delete(f"{TYPE}{t.json()['ed_type_id']}/").status_code == 204, t.content[:200])

    print("Rights")
    check("view-only can read but not add", viewer.get(ED).status_code == 200 and viewer.post(ED, base, format="json").status_code == 403)
    check("no rights: closed", nobody.get(ED).status_code == 403)
    check("signed out: refused", APIClient(HTTP_HOST="localhost").get(ED).status_code in (401, 403))


if __name__ == "__main__":
    with transaction.atomic():
        run()
        transaction.set_rollback(True)
    if FAILED:
        print(f"\n{len(FAILED)} FAILED: " + "; ".join(FAILED))
        sys.exit(1)
    print("\nAll checks passed.")
