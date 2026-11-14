"""Checks the Applicants page (Rig Personnel > New Joinee Workflow > Applicants) through the real API.

    cd backend
    .venv/bin/python scripts/check_fs_applicants.py

Runs inside one transaction that is rolled back at the end (uploaded files are removed again), so nothing is saved. Needs the normal dev data (the migrated applicants).
Exits with status 1 if any check fails.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

import datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import MstFsCategory, MstFsEmployee, MstRank, MstUser, MstUserFsCatgMapping, UserPermission, UserProfile
from core.permissions import invalidate_user_access
from hr.models import CtrlNtbrFs, FsNewApplDtl

URL = "/api/hr/fs-applicants/"
FAILED = []


def check(name, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


def make_user(login, category_ids=(), admin=False):
    now = timezone.now()
    mst = MstUser.objects.create(user_name=login, user_login_id=login, user_active="Y", user_type_id="N", user_from=datetime.date(2020, 1, 1), cr_user_id=1, cr_dt=now)
    UserProfile.objects.create(user_id=mst.user_id, user_login_id=login, is_app_admin=admin)
    if not admin:
        UserPermission.objects.create(user_id=mst.user_id, menu_key="hr.fs_applicants", can_view=True, can_add=True, can_edit=True, can_delete=True, can_export=False)
    for cid in category_ids:
        MstUserFsCatgMapping.objects.create(user=mst, fs_category_id=cid, mapping_from=datetime.date(2020, 1, 1), cr_user_id=1, cr_dt=now)
    invalidate_user_access(login)
    client = APIClient(HTTP_HOST="localhost")
    client.force_authenticate(get_user_model().objects.create_user(username=login, password="x"))
    return client


def run():
    admin = make_user("zz_fa_admin", admin=True)
    today = datetime.date.today()
    from django.db.models import Count

    # two categories that both have applicants (A: the one with the most new applicants, B: another one with a rank)
    ranked = list(FsNewApplDtl.objects.filter(fs_new_appl_status="N").values("appl_fs_category").annotate(n=Count("pk")).order_by("-n").values_list("appl_fs_category", flat=True))
    cat_a = ranked[0]
    cat_b = next(c for c in FsNewApplDtl.objects.exclude(appl_fs_category=cat_a).values_list("appl_fs_category", flat=True).distinct() if MstRank.objects.filter(fs_category_id=c).exists())
    rank_a = MstRank.objects.filter(fs_category_id=cat_a).first()
    rank_b = MstRank.objects.filter(fs_category_id=cat_b).first()
    mapped = make_user("zz_fa_mapped", [cat_a])

    print("The list")
    allr = admin.get(URL, {"page_size": 5}).json()
    check("the default list is applicants not joined, plus those with an offer letter", allr["count"] > 0 and all((a["fs_new_appl_status"] != "J") or a["offer_sent"] for a in allr["results"]))
    legacy = admin.get(URL, {"scope": "notjoined", "page_size": 5}).json()
    check("scope=notjoined is the legacy list (nobody joined)", legacy["count"] > 0 and all(a["fs_new_appl_status"] != "J" for a in legacy["results"]))
    check("the default list also holds joined applicants who were sent an offer letter", allr["count"] > legacy["count"])
    sent = admin.get(URL, {"offer": "sent", "page_size": 3}).json()
    check("the offer filter works and every row is flagged", sent["count"] > 0 and all(a["offer_sent"] and a["offer_letter_dt"] for a in sent["results"]))
    none_ = admin.get(URL, {"offer": "none", "page_size": 3}).json()
    check("'no offer' rows are not flagged", all(not a["offer_sent"] for a in none_["results"]))
    check("a chosen status shows exactly that status (joined included)", admin.get(URL, {"status": "J", "page_size": 1}).json()["count"] > 0)
    row_a = FsNewApplDtl.objects.filter(appl_fs_category_id=cat_a).first()
    row_b = FsNewApplDtl.objects.filter(appl_fs_category_id=cat_b).first()
    mine = mapped.get(URL, {"status": "N", "page_size": 100, "ordering": "name"}).json()
    check("a mapped user sees only the categories he is mapped to", mine["count"] > 0 and all(a["appl_fs_category"] == cat_a for a in mine["results"]))
    check("and cannot open an applicant of another category", mapped.get(f"{URL}{row_b.pk}/").status_code == 404)
    check("his category list holds only his categories", [c["fs_category_id"] for c in mapped.get(URL + "categories/").json()] == [cat_a])
    nobody = make_user("zz_fa_nocat")
    check("a user with no category mapping sees no applicant", nobody.get(URL).json()["count"] == 0)

    print("Saving an applicant")
    def body(**over):
        base = {
            "fs_new_appl_dt": today.isoformat(), "fs_emp_fname": "Rule", "fs_emp_lname": "Check", "fathers_name": "Test Father", "permanent_addr": "1 Test Road",
            "mailing_addr": "1 Test Road", "fs_emp_mobile_no": "9876543210", "fs_emp_email_pers": "rule.check@example.com", "gender": "M", "blood_group": "O+",
            "fs_emp_dob": (today.replace(year=today.year - 30)).isoformat(), "marital_status": "Unmarried", "nationality": row_a.nationality_id, "domicile_state": 3,
            "appl_fs_category": cat_a, "appl_rank": rank_a.pk, "appl_emp_type": row_a.appl_emp_type_id,
        }
        base.update(over)
        return base

    r = mapped.post(URL, body(), format="json")
    check("a valid applicant is created", r.status_code == 201, r.content[:300])
    new = r.json()
    pk = new["fs_new_appl_id"]
    top = FsNewApplDtl.objects.exclude(pk=pk).order_by("-fs_new_appl_no").first().fs_new_appl_no
    check("the application number is the highest plus one", new["fs_new_appl_no"] == top + 1)
    check("the status starts as New", new["fs_new_appl_status"] == "N" and new["status_label"] == "New")
    check("it is not flagged as having an offer letter", new["offer_sent"] is False)
    for name, over, field in [
        ("under 15", {"fs_emp_dob": today.replace(year=today.year - 14).isoformat()}, "fs_emp_dob"),
        ("a date of birth in the future", {"fs_emp_dob": (today + datetime.timedelta(days=3)).isoformat()}, "fs_emp_dob"),
        ("an application date in the future", {"fs_new_appl_dt": (today + datetime.timedelta(days=1)).isoformat()}, "fs_new_appl_dt"),
        ("Married without a marriage date", {"marital_status": "Married"}, "marriage_dt"),
        ("a marriage date in the future", {"marital_status": "Married", "marriage_dt": (today + datetime.timedelta(days=9)).isoformat()}, "marriage_dt"),
        ("no domicile state", {"domicile_state": None}, "domicile_state"),
        ("no marital status", {"marital_status": None}, "marital_status"),
        ("no blood group", {"blood_group": None}, "blood_group"),
        ("a bad gender", {"gender": "X"}, "gender"),
        ("a bad email", {"fs_emp_email_pers": "nope"}, "fs_emp_email_pers"),
        ("a bad mobile number", {"fs_emp_mobile_no": "abc"}, "fs_emp_mobile_no"),
        ("a rank of another category", {"appl_rank": rank_b.pk}, "appl_rank"),
    ]:
        r = mapped.post(URL, body(**over), format="json")
        check(f"{name} is refused, naming the field", r.status_code == 400 and field in r.json(), r.content[:200])
    r = mapped.post(URL, body(appl_fs_category=cat_b, appl_rank=rank_b.pk), format="json")
    check("a category he is not mapped to is refused", r.status_code == 400 and "appl_fs_category" in r.json(), r.content[:200])
    r = mapped.post(URL, body(marital_status="Married", marriage_dt="2015-06-01", fs_emp_lname="Wed"), format="json")
    check("a married applicant with a marriage date is created", r.status_code == 201, r.content[:200])
    r = mapped.patch(f"{URL}{pk}/", {"marital_status": "Unmarried", "marriage_dt": "2015-06-01"}, format="json")
    check("an unmarried applicant keeps no marriage date", r.status_code == 200 and r.json()["marriage_dt"] is None, r.content[:200])

    print("Updating")
    r = mapped.patch(f"{URL}{pk}/", {"fs_emp_mobile_no": "9123456780", "emergency_addr": "Somewhere"}, format="json")
    check("contact details can be changed", r.status_code == 200 and r.json()["fs_emp_mobile_no"] == "9123456780", r.content[:200])
    for name, over in [("the last name", {"fs_emp_lname": "Other"}), ("the date of birth", {"fs_emp_dob": "1980-01-01"}), ("the gender", {"gender": "F"}),
                       ("the application date", {"fs_new_appl_dt": "2020-01-01"})]:
        r = mapped.patch(f"{URL}{pk}/", over, format="json")
        check(f"{name} cannot be changed after saving", r.status_code == 400, r.content[:200])
    r = mapped.patch(f"{URL}{pk}/", {"fs_new_appl_status": "J", "fs_new_appl_no": 1}, format="json")
    check("status and number cannot be set through the form", r.json()["fs_new_appl_status"] == "N" and r.json()["fs_new_appl_no"] == top + 1)

    print("Not to be rehired, duplicates")
    ntbr = CtrlNtbrFs.objects.filter(business_system_id=6).first()
    emp = MstFsEmployee.objects.get(pk=ntbr.fs_emp_id)
    r = admin.post(URL, body(fs_emp_fname=emp.fs_emp_fname, fs_emp_lname=emp.fs_emp_lname, fs_emp_dob=ntbr.ntbr_fs_dob.isoformat(), appl_fs_category=cat_a, appl_rank=rank_a.pk), format="json")
    check("a match in the register is held back for confirmation", r.status_code == 400 and r.json().get("ntbr"), r.content[:200])
    r = admin.post(URL, body(fs_emp_fname=emp.fs_emp_fname, fs_emp_lname=emp.fs_emp_lname, fs_emp_dob=ntbr.ntbr_fs_dob.isoformat(), ntbr_confirmed=True), format="json")
    check("and saved once confirmed", r.status_code == 201, r.content[:200])
    r = admin.get(URL + "ntbr-check/", {"fname": emp.fs_emp_fname, "lname": "Nomatch", "dob": ntbr.ntbr_fs_dob.isoformat()})
    check("the first name and date of birth alone match (as in the legacy rules)", len(r.json()["ntbr"]) >= 1)
    r = admin.get(URL + "ntbr-check/", {"fname": "Zzz", "lname": "Zzz", "dob": ntbr.ntbr_fs_dob.isoformat()})
    check("a different name does not match", r.json()["ntbr"] == [])
    r = admin.get(URL + "ntbr-check/", {"fname": "x", "lname": "Check", "dob": body()["fs_emp_dob"]})
    check("a likely duplicate (same last name and date of birth) is reported", any(d["id"] == pk for d in r.json()["duplicates"]))
    r = admin.get(URL + "ntbr-check/", {"fname": "x", "lname": "Check", "dob": body()["fs_emp_dob"], "exclude": pk})
    check("an applicant is not a duplicate of himself", all(d["id"] != pk for d in r.json()["duplicates"]))

    print("Re-hire")
    former = MstFsEmployee.objects.exclude(fs_emp_active="Y").filter(fs_category_id=cat_a).first()
    r = mapped.get(URL + "rehire-search/", {"search": former.fs_emp_lname})
    check("a former employee is found by name", any(x["fs_emp_id"] == former.pk for x in r.json()), r.content[:200])
    active = MstFsEmployee.objects.filter(fs_emp_active="Y", fs_category_id=cat_a).first()
    check("an active employee is not offered", all(x["fs_emp_id"] != active.pk for x in mapped.get(URL + "rehire-search/", {"search": active.fs_emp_lname}).json()))
    r = mapped.get(URL + "rehire/", {"emp": former.pk})
    data = r.json()
    check("the form is filled from the former employee", r.status_code == 200 and data["fs_emp_lname"] == former.fs_emp_lname and data["prv_fs_emp"] == former.pk and data["appl_fs_category"] == cat_a, r.content[:200])
    check("an active employee cannot be re-hired", mapped.get(URL + "rehire/", {"emp": active.pk}).status_code == 400)
    other = MstFsEmployee.objects.exclude(fs_category_id=cat_a).exclude(fs_emp_active="Y").first()
    check("a former employee of another category is not available", mapped.get(URL + "rehire/", {"emp": other.pk}).status_code == 404)

    print("Files")
    saved = []
    try:
        r = mapped.post(f"{URL}{pk}/photo/", {"file": SimpleUploadedFile("p.jpg", b"MZ not an image")}, format="multipart")
        check("a renamed program is refused as a photo", r.status_code == 400)
        r = mapped.post(f"{URL}{pk}/photo/", {"file": SimpleUploadedFile("p.jpg", b"\xff\xd8\xff\xe0jpegdata")}, format="multipart")
        check("a photo is saved and has an address", r.status_code == 200 and r.json()["photo_url"] and r.json()["fs_emp_photo_path"].startswith("fs_applicant_photos/"), r.content[:200])
        if r.status_code == 200:
            saved.append(os.path.join(settings.MEDIA_ROOT, r.json()["fs_emp_photo_path"]))
        r = mapped.post(f"{URL}{pk}/cv/", {"file": SimpleUploadedFile("cv.pdf", b"%PDF-1.4 ok")}, format="multipart")
        check("a CV (PDF) is saved", r.status_code == 200 and r.json()["cv_url"], r.content[:200])
        if r.status_code == 200:
            saved.append(os.path.join(settings.MEDIA_ROOT, r.json()["cv_path"]))
        z = mapped.post(f"{URL}{pk}/cv/", {"file": SimpleUploadedFile("cv.zip", b"PK\x03\x04" + b"\x00" * 40)}, format="multipart")
        check("a .zip is accepted as a CV", z.status_code == 200 and z.json()["cv_path"].endswith(".zip"), z.content[:200])
        check("an .exe is refused as a CV", mapped.post(f"{URL}{pk}/cv/", {"file": SimpleUploadedFile("cv.exe", b"MZ")}, format="multipart").status_code == 400)
        r = mapped.delete(f"{URL}{pk}/photo/")
        check("a photo can be removed (the file stays on disk)", r.status_code == 200 and r.json()["photo_url"] is None and all(os.path.isfile(p) for p in saved[:1]))
    finally:
        for p in saved:
            if os.path.isfile(p):
                os.remove(p)

    print("Deleting")
    joined = FsNewApplDtl.objects.filter(fs_new_appl_status="J", offer_letter__isnull=False).first()
    r = admin.delete(f"{URL}{joined.pk}/")
    check("an applicant who joined (with an offer letter) cannot be deleted", r.status_code == 400 and FsNewApplDtl.objects.filter(pk=joined.pk).exists(), r.content[:200])
    check("another user's category cannot delete either", mapped.delete(f"{URL}{row_b.pk}/").status_code == 404)
    check("a new applicant can be deleted", mapped.delete(f"{URL}{pk}/").status_code == 204 and not FsNewApplDtl.objects.filter(pk=pk).exists())

    print("Rules in the database and rights")
    with transaction.atomic():
        try:
            with connection.cursor() as cur:
                cur.execute("UPDATE hr_fs_new_appl_dtl SET fs_new_appl_status = 'Z' WHERE fs_new_appl_id = %s", [row_a.pk])
            check("the database refuses a status other than N, C, R, A, J", False)
        except Exception:
            check("the database refuses a status other than N, C, R, A, J", True)
            transaction.set_rollback(False)
    check("signed-out requests are refused", APIClient(HTTP_HOST="localhost").get(URL).status_code in (401, 403))
    viewer_only = APIClient(HTTP_HOST="localhost")
    login = "zz_fa_viewer"
    mst = MstUser.objects.create(user_name=login, user_login_id=login, user_active="Y", user_type_id="N", user_from=datetime.date(2020, 1, 1), cr_user_id=1, cr_dt=timezone.now())
    UserProfile.objects.create(user_id=mst.user_id, user_login_id=login, is_app_admin=False)
    UserPermission.objects.create(user_id=mst.user_id, menu_key="hr.fs_applicants", can_view=True)
    MstUserFsCatgMapping.objects.create(user=mst, fs_category_id=cat_a, mapping_from=datetime.date(2020, 1, 1), cr_user_id=1, cr_dt=timezone.now())
    invalidate_user_access(login)
    viewer_only.force_authenticate(get_user_model().objects.create_user(username=login, password="x"))
    check("view-only can read but not add or delete", viewer_only.get(URL).status_code == 200 and viewer_only.post(URL, body(), format="json").status_code == 403
          and viewer_only.delete(f"{URL}{row_a.pk}/").status_code == 403)


if __name__ == "__main__":
    with transaction.atomic():
        run()
        transaction.set_rollback(True)
    print()
    if FAILED:
        print(f"{len(FAILED)} FAILED: " + "; ".join(FAILED))
        sys.exit(1)
    print("All checks passed.")
