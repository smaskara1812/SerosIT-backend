"""Checks that the app no longer depends on the legacy employee list (mst_employee), and that what replaced it works.

    cd backend
    .venv/bin/python scripts/check_employee_independence.py

 1. nothing in the database or in the models links to mst_employee (no foreign key constraints, no model foreign key);
 2. no source file other than the models, the migrations and the mapping command mentions the model;
 3. the mapping command has nothing left to do (a second run is a no-op);
 4. Doc To Sign works with users (signature files named by user id), Alert To Users with a user or a name, the user list shows
    inactive users on request, and the User Management email prompt and profile photo behave;
 5. a free-text name is accepted where an employee used to be picked (Business System, holders).

Requests run inside one transaction that is rolled back; files written by the photo check are removed. Exits 1 on failure.
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection, transaction
from rest_framework.test import APIClient

from core.models import DocToSignMapping, MailAlertToUser, MstUser

FAILED = []
ROOT = str(settings.MEDIA_ROOT)
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 60


def check(name, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  {str(detail)[:260]}" if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


class Rollback(Exception):
    pass


def run():
    print("1. the employee table is gone")
    check("the MstEmployee model no longer exists", not any(m.__name__ == "MstEmployee" for m in apps.get_app_config("core").get_models()))
    check("the mst_employee table no longer exists", "mst_employee" not in connection.introspection.table_names())
    refs = [f"{m.__name__}.{f.name}" for m in apps.get_app_config("core").get_models() for f in m._meta.get_fields()
            if f.is_relation and getattr(f.related_model, "__name__", "") == "MstEmployee"]
    check("no model has a foreign key to MstEmployee", not refs, refs)
    if connection.vendor == "mysql":
        with connection.cursor() as c:
            c.execute("SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE "
                      "WHERE TABLE_SCHEMA = DATABASE() AND REFERENCED_TABLE_NAME = 'mst_employee'")
            left = c.fetchall()
        check("no foreign key constraint in the database points at mst_employee", not left, left)

    print("2. no code reads the employee model")
    core = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core")
    skip = ("models.py",)
    hits = []
    for dirpath, dirs, files in os.walk(core):
        if "migrations" in dirpath or "__pycache__" in dirpath:
            continue
        for f in files:
            if f.endswith(".py") and f not in skip:
                text = open(os.path.join(dirpath, f), encoding="utf-8").read()
                if "MstEmployee" in text or "masters/employees" in text:
                    hits.append(f)
    check("only the models and the mapping command mention MstEmployee", not hits, hits)

    print("3. the mapping is complete")
    cols = [f"{m.__name__}.{f.name}" for m in apps.get_app_config("core").get_models() for f in m._meta.concrete_fields
            if f.column in ("emp_id", "owner_emp_id") and m.__name__ not in ("MstUser", "MstEmployee")]
    check("no table keeps an employee id column (only mst_user.emp_id, the legacy employee a user came from)", not cols, cols)
    if connection.vendor == "mysql":
        buf = io.StringIO()
        call_command("map_employees_to_users", report="/tmp/_emp_check.csv", stdout=buf)
        counts = [int(line.rsplit(":", 1)[1]) for line in buf.getvalue().splitlines() if line.startswith("  ") and "rows listed" not in line]
        check("a second run of map_employees_to_users changes nothing", counts and not any(counts), buf.getvalue())
    check("every Doc To Sign row has a user", not DocToSignMapping.objects.filter(user__isnull=True).exists())

    client = APIClient(HTTP_HOST="localhost")
    client.force_authenticate(get_user_model().objects.filter(is_superuser=True).first())
    base = "/api/masters/"

    print("4. users instead of employees")
    r = client.get(f"{base}users/?page_size=1")
    active_only = r.json()["count"]
    r = client.get(f"{base}users/?page_size=1&include_inactive=1")
    check("the user list shows inactive users when asked", r.json()["count"] > active_only, (active_only, r.json()["count"]))
    check("the old employees list is gone", client.get(f"{base}employees/").status_code == 404)

    signer = MstUser.objects.exclude(emp_id=None).first()
    up = f"{base}doc-to-sign-mapping/upload-sign/"
    r = client.post(up, {"user_id": str(signer.pk), "file": SimpleUploadedFile("s.png", PNG, content_type="image/png")}, format="multipart")
    path = r.json().get("path", "")
    check("a signature is saved as signatures/<user id>_<n>", r.status_code == 200 and path.startswith(f"signatures/{signer.pk}_"), r.content.decode())
    r2 = client.post(up, {"emp_id": str(signer.pk), "file": SimpleUploadedFile("s.png", PNG, content_type="image/png")}, format="multipart")
    check("the old emp_id parameter no longer works", r2.status_code == 400)
    try:
        os.remove(os.path.join(ROOT, path))
    except OSError:
        pass
    r = client.post(f"{base}doc-to-sign-mapping/", {"doc_name": DocToSignMapping.objects.first().doc_name, "sign_from": "2026-01-01"}, format="json")
    check("a Doc To Sign row without a user is refused", r.status_code == 400 and "user" in r.json(), r.content.decode())

    print("5. user management")
    target = MstUser.objects.filter(user_email__isnull=False).exclude(user_email="").first()
    alert = MailAlertToUser.objects.exclude(alert__isnull=True).first()
    from core.models import MailAlertDtl
    alert_dtl = MailAlertDtl.objects.filter(pk__gt=0).first()
    row = MailAlertToUser.objects.create(
        alert=alert_dtl, user=target, email_addr=target.user_email[:45], addressee_type="T", mail_alert_from="2026-01-01", cr_user_id=0,
        cr_dt=target.cr_dt)
    url = f"/api/admin/user-management/{target.pk}/update/"
    body = {"name": target.user_name, "email": "zz.changed@seros.in", "user_type": target.user_type_id}
    r = client.post(url, body, format="json")
    check("changing an email used on alert rows asks first (nothing saved)", r.status_code == 409 and r.json().get("alert_rows", 0) >= 1, r.content.decode())
    target.refresh_from_db()
    check("... and the email is unchanged after that", target.user_email != "zz.changed@seros.in")
    r = client.post(url, {**body, "alert_email_sync": "user_only"}, format="json")
    row.refresh_from_db()
    target.refresh_from_db()
    check("'only the user' changes the user and leaves the alert row", r.status_code == 200 and target.user_email == "zz.changed@seros.in" and row.email_addr != "zz.changed@seros.in", r.content.decode())
    target.user_email = row.email_addr
    target.save(update_fields=["user_email"])
    r = client.post(url, {**body, "alert_email_sync": "all"}, format="json")
    row.refresh_from_db()
    check("'both' changes the user and the alert row", r.status_code == 200 and row.email_addr == "zz.changed@seros.in" and r.json().get("alert_rows_updated", 0) >= 1, r.content.decode())
    r = client.post(url, {**body, "first_name": "Zed", "mobile_no": "abc"}, format="json")
    check("a mobile number with letters is refused", r.status_code == 400, r.content.decode())
    r = client.post(url, {**body, "first_name": "Zed", "date_of_birth": "0012-01-01"}, format="json")
    check("a date of birth in year 12 is refused", r.status_code == 400, r.content.decode())
    r = client.post(url, {**body, "first_name": "Zed", "mobile_no": "9876543210", "date_of_birth": "1990-05-04"}, format="json")
    got = client.get(f"/api/admin/user-management/{target.pk}/").json()
    check("person details are saved", r.status_code == 200 and got["first_name"] == "Zed" and got["date_of_birth"] == "1990-05-04" and got["mobile_no"] == "9876543210", r.content.decode())

    from core.models import MstWorkingDesignation
    desig = MstWorkingDesignation.objects.filter(working_designation_active="Y").first()
    r = client.post(url, {**body, "work_designation_id": desig.pk}, format="json")
    got = client.get(f"/api/admin/user-management/{target.pk}/").json()
    check("a working designation is chosen from the table and shown by name", r.status_code == 200 and got["work_designation_name"] == desig.working_designation, r.content.decode())
    r = client.post(url, {**body, "work_designation_id": 999999}, format="json")
    check("a designation that is not in the table is refused", r.status_code == 400, r.content.decode())
    check("the designations list is served", len(client.get("/api/admin/user-management/designations/").json()) > 200)
    check("there is no date of leaving any more", "date_of_leaving" not in got)

    r = client.post("/api/admin/user-management/create/", {"login_id": "zzind1", "name": "zz new person", "first_name": "Zed", "last_name": "Person",
                    "date_of_birth": "1991-02-03", "mobile_no": "9876543210", "work_designation_id": desig.pk, "user_from": "2026-01-01"}, format="json")
    nu = MstUser.objects.filter(user_login_id="zzind1").first()
    check("a new user is created with person details", r.status_code in (200, 201) and nu and nu.first_name == "Zed" and nu.work_designation_id == desig.pk and str(nu.date_of_birth) == "1991-02-03", r.content.decode())
    r = client.post("/api/admin/user-management/create/", {"login_id": "zzind2", "name": "zz bad", "mobile_no": "abc", "user_from": "2026-01-01"}, format="json")
    check("a new user with a bad mobile number is refused", r.status_code == 400, r.content.decode())

    ph = f"/api/admin/user-management/{target.pk}/photo/"
    r = client.post(ph, {"file": SimpleUploadedFile("p.png", PNG, content_type="image/png")}, format="multipart")
    first = r.json().get("photo_url")
    stored = MstUser.objects.get(pk=target.pk).profile_picture_path
    check("a profile picture is saved under mst_employee_images/<user id>_<n>", r.status_code == 200 and first and stored.startswith(f"mst_employee_images/{target.pk}_"), r.content.decode())
    r = client.post(ph, {"file": SimpleUploadedFile("p.png", PNG, content_type="image/png")}, format="multipart")
    stored2 = MstUser.objects.get(pk=target.pk).profile_picture_path
    check("a new picture gets a new name and the old file is kept", r.status_code == 200 and stored2 != stored and os.path.isfile(os.path.join(ROOT, stored)))
    r = client.post(ph, {"file": SimpleUploadedFile("p.gif", b"GIF89a" + b"0" * 20, content_type="image/gif")}, format="multipart")
    check("a GIF picture is refused", r.status_code == 400)
    for p in (stored, stored2):
        try:
            os.remove(os.path.join(ROOT, p))
        except OSError:
            pass

    print("6. free text instead of an employee")
    from core.models import MstBusinessSystem
    bs = MstBusinessSystem.objects.first()
    r = client.patch(f"{base}business-systems/{bs.pk}/", {"owner_name": "Typed Owner Name"}, format="json")
    check("a Business System owner is typed as a name", r.status_code == 200 and r.json().get("owner_name") == "Typed Owner Name", r.content.decode())
    check("the old employee field is no longer in the data", "owner_emp" not in r.json() and "owner_emp_name" not in r.json())
    r = client.get(f"/api/it-asset/it-accessory-holders/?page_size=1").json()["results"][0]
    check("an accessory holder shows its name, with no employee field", "emp_name" not in r and "it_accessory_holder_name" in r)
    raise Rollback()


try:
    with transaction.atomic():
        run()
except Rollback:
    pass

print()
print("FAILED:" if FAILED else "all checks passed", *FAILED, sep="\n  " if FAILED else " ")
sys.exit(1 if FAILED else 0)
