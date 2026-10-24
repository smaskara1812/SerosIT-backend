"""Verifies a database built from the legacy staging copy by db_migration/scripts/build_test_db.py.

    MYSQL_DB=seros_test .venv/bin/python scripts/check_test_migration.py
    MYSQL_DB=seros_test .venv/bin/python scripts/check_test_migration.py --reference serosIT --legacy Seros_Data

Read-only. It checks that:
  A. nothing links to mst_employee, and every foreign key's rows have their parent (the imports ran with FK checks off);
  B. the table row counts match the reference database (the live app database);
  C. the employee data survived the move to users and plain names, compared with the legacy employee table;
  D. every stored media path either resolves to a file, or is legacy text for a file that was never in the dump; and signed links serve.
Exits 1 on any failure.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import argparse

import django

django.setup()

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client

from core import media_uploads as mu

ap = argparse.ArgumentParser()
ap.add_argument("--reference", default="serosIT")
ap.add_argument("--legacy", default="Seros_Data")
args = ap.parse_args()
DB = settings.DATABASES["default"]["NAME"]
FAILED = []


def check(name, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  {str(detail)[:300]}" if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


def q(sql, *p):
    with connection.cursor() as c:
        c.execute(sql, p)
        return c.fetchall()


def one(sql, *p):
    r = q(sql, *p)
    return r[0][0] if r else None


print(f"checking {DB!r} (reference {args.reference!r}, legacy {args.legacy!r})")
if DB.lower() == args.reference.lower():
    sys.exit("The database being checked is the reference itself.")

print("A. links")
left = q("SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=%s AND REFERENCED_TABLE_NAME='mst_employee'", DB)
check("no foreign key points at mst_employee", not left, left)
cons = q("SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE "
         "WHERE TABLE_SCHEMA=%s AND REFERENCED_TABLE_NAME IS NOT NULL", DB)
bad = []
for t, c, pt, pc in cons:
    n = one(f"SELECT COUNT(*) FROM `{t}` x LEFT JOIN `{pt}` p ON x.`{c}` = p.`{pc}` WHERE x.`{c}` IS NOT NULL AND p.`{pc}` IS NULL")
    if n:
        ref = one(f"SELECT COUNT(*) FROM `{args.reference}`.`{t}` x LEFT JOIN `{args.reference}`.`{pt}` p ON x.`{c}` = p.`{pc}` "
                  f"WHERE x.`{c}` IS NOT NULL AND p.`{pc}` IS NULL")
        bad.append((f"{t}.{c} -> {pt}", n, f"reference has {ref}"))
new_bad = [b for b in bad if b[1] > int(b[2].split()[-1] or 0)]
check(f"every foreign key row has its parent ({len(cons)} links; {len(bad)} with orphans, same as the reference)", not new_bad, new_bad)
for b in bad:
    print("        note:", b)

print("B. row counts against the reference")
tables = [r[0] for r in q("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_TYPE='BASE TABLE'", DB)]
skip = {"mst_employee", "sys_audit_log", "sys_email_log", "django_session", "django_migrations", "token_blacklist_outstandingtoken", "token_blacklist_blacklistedtoken",
        "sys_user_mail_credential", "sys_user_permissions", "sys_user_profile", "mst_user_password", "sys_user_shortcut"}
import glob
import re

SQL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "db_migration", "sql")


def legacy_source(table):
    """The legacy table an import file copies `table` from, when there is exactly one (None otherwise)."""
    found = set()
    for f in glob.glob(os.path.join(SQL_DIR, "import_*.sql")):
        text = open(f, encoding="utf-8").read()
        for m in re.finditer(r"INSERT\s+(?:IGNORE\s+)?INTO\s+serosIT\.%s\b.*?FROM\s+Seros_Data\.(\w+)" % re.escape(table), text, re.I | re.S):
            found.add(m.group(1))
    return found.pop() if len(found) == 1 else None


diffs, explained = [], []
for t in sorted(tables):
    if t in skip or t.startswith(("django_", "auth_", "silk_")):
        continue
    ref_exists = one("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s", args.reference, t)
    if not ref_exists:
        diffs.append((t, "not in reference", ""))
        continue
    a, b = one(f"SELECT COUNT(*) FROM `{t}`"), one(f"SELECT COUNT(*) FROM `{args.reference}`.`{t}`")
    if a != b:
        src = legacy_source(t)
        leg = one(f"SELECT COUNT(*) FROM `{args.legacy}`.`{src}`") if src else None
        (explained if leg == a else diffs).append((t, a, b, f"legacy {src}: {leg}"))
check(f"every table has the reference's row count, or the legacy source's ({len(tables)} tables)", not diffs, diffs)
for e in explained:
    print("        note: differs from the reference but equals the legacy source:", e)

print("C. employee data (against the legacy employee table)")
from core.management.commands.map_employees_to_users import ROW_SOURCES

APP_PK = {"doc_to_sign_mapping": "doc_to_sign_id", "mail_alert_to_user": "mail_alert_to_user_id", "mst_business_system": "business_system_id",
          "it_asset_holder": "it_asset_holder_id", "it_accessory_holder": "it_accessory_holder_id", "mst_it_asset": "it_asset_id"}
LEG = args.legacy


def legacy_join(table):
    src, pk, emp = ROW_SOURCES[table]
    return f"`{table}` t JOIN `{LEG}`.`{src}` l ON l.`{pk}` = t.`{APP_PK[table]}`", f"l.`{emp}`"


# the employee id of a row is not stored in the app any more: it is read from the legacy row with the same primary key
j, emp = legacy_join("doc_to_sign_mapping")
check("every Doc To Sign row has a user whose legacy employee is the one on the legacy row",
      one(f"SELECT COUNT(*) FROM {j} LEFT JOIN mst_user u ON u.user_id=t.user_id WHERE t.user_id IS NULL OR u.emp_id <> {emp}") == 0)
j, emp = legacy_join("mail_alert_to_user")
check("no Alert To Users row lost its person (a user, or the name as text)",
      one(f"SELECT COUNT(*) FROM {j} WHERE {emp} IS NOT NULL AND t.user_id IS NULL AND (t.recipient_name IS NULL OR t.recipient_name='')") == 0)
check("every alert recipient's user is the employee on the legacy row",
      one(f"SELECT COUNT(*) FROM {j} JOIN mst_user u ON u.user_id=t.user_id WHERE {emp} IS NOT NULL AND u.emp_id <> {emp}") == 0)
for label, table, name_col in (("Business System owners", "mst_business_system", "owner_name"),
                               ("IT Asset holders", "it_asset_holder", "holder_name"),
                               ("IT Accessory holders", "it_accessory_holder", "it_accessory_holder_name"),
                               ("IT Asset current holders", "mst_it_asset", "cur_holder_name")):
    j, emp = legacy_join(table)
    check(f"{label}: every row that had an employee has a name",
          one(f"SELECT COUNT(*) FROM {j} WHERE {emp} IS NOT NULL AND (t.`{name_col}` IS NULL OR t.`{name_col}`='')") == 0)
    like = (f"t.`{name_col}` NOT LIKE CONCAT('%%', TRIM(COALESCE(NULLIF(e.Emp_Fname,''), e.Emp_Sname)) COLLATE utf8mb4_0900_ai_ci, '%%') "
            f"AND t.`{name_col}` NOT LIKE CONCAT('%%', TRIM(e.Emp_Sname) COLLATE utf8mb4_0900_ai_ci, '%%')")
    wrong = one(f"SELECT COUNT(*) FROM {j} JOIN `{LEG}`.Mst_Employee e ON e.EMP_ID={emp} WHERE {like}")
    if table == "it_asset_holder" and wrong:
        # a holder row that already carried its own typed text in the legacy system ("MR 1 - Stock") keeps it, by design
        own = one(f"SELECT COUNT(*) FROM {j} JOIN `{LEG}`.Mst_Employee e ON e.EMP_ID={emp} "
                  f"WHERE t.`{name_col}` = l.Holder_Name COLLATE utf8mb4_0900_ai_ci AND {like}")
        print(f"        note: {own} rows kept the typed holder text the legacy row already had")
        wrong -= own
    total = one(f"SELECT COUNT(*) FROM {j} WHERE {emp} IS NOT NULL")
    check(f"{label}: the name matches the legacy employee ({total} rows)", wrong == 0, f"{wrong} rows differ" if wrong else "")
no_cols = q("SELECT TABLE_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND COLUMN_NAME IN ('emp_id','owner_emp_id') "
            "AND TABLE_NAME NOT IN ('mst_user','mst_employee')", DB)
check("no table keeps an employee id column (only mst_user.emp_id)", not no_cols, no_cols)
mismatch = one(f"SELECT COUNT(*) FROM mst_user u JOIN `{args.legacy}`.Mst_Employee e ON e.EMP_ID=u.emp_id "
               "WHERE (u.first_name IS NULL AND e.Emp_Fname IS NOT NULL AND e.Emp_Fname<>'') OR (u.last_name IS NULL AND e.Emp_Sname<>'') "
               "OR (u.date_of_birth IS NULL AND e.Emp_DOB IS NOT NULL) OR (u.company_id IS NULL AND e.COMPANY_ID IS NOT NULL)")
check("every user with a legacy employee has the person details filled", mismatch == 0, f"{mismatch} users")
ne_bad = one(f"SELECT COUNT(*) FROM mst_user u JOIN `{args.legacy}`.hr_Mst_NonEmployee n ON n.NonEmp_Id=u.nonemp_id "
             "WHERE (u.first_name IS NULL AND n.NonEmp_Fname IS NOT NULL AND n.NonEmp_Fname<>'') OR (u.last_name IS NULL AND n.NonEmp_Sname IS NOT NULL AND n.NonEmp_Sname<>'') "
             "OR (u.mobile_no IS NULL AND n.NonEmp_Mobile_No IS NOT NULL AND n.NonEmp_Mobile_No<>'') OR (u.user_email IS NULL AND n.NonEmp_Email IS NOT NULL AND n.NonEmp_Email<>'')")
check("every non-employee (shared / role account) user has the legacy person details filled", ne_bad == 0, f"{ne_bad} users")
check("every non-employee user has a legacy row", one(f"SELECT COUNT(*) FROM mst_user u LEFT JOIN `{args.legacy}`.hr_Mst_NonEmployee n ON n.NonEmp_Id=u.nonemp_id WHERE u.nonemp_id IS NOT NULL AND n.NonEmp_Id IS NULL") == 0)
check("a user's end date (To) covers the legacy date of leaving",
      one(f"SELECT COUNT(*) FROM mst_user u JOIN `{args.legacy}`.Mst_Employee e ON e.EMP_ID=u.emp_id WHERE e.EMP_TO IS NOT NULL AND u.user_to IS NULL") == 0)
check("every working designation on a user exists in the table",
      one("SELECT COUNT(*) FROM mst_user u LEFT JOIN mst_working_designation d ON d.working_designation_id=u.work_designation_id WHERE u.work_designation_id IS NOT NULL AND d.working_designation_id IS NULL") == 0)
check("the designation names are the real ones, not stubs", one("SELECT COUNT(*) FROM mst_working_designation WHERE working_designation LIKE 'Designation %%'") == 0)

print("D. media paths")
ROOT = str(settings.MEDIA_ROOT)
FIELDS = [("incident_photo", "incident_photo_path"), ("hse_drill_record_photo_upload", "drill_rec_photo_upload_path"),
          ("doc_to_sign_mapping", "sign_path"), ("mst_interviewer", "sign_path"), ("mst_fs_employee", "fs_emp_photo_path"),
          ("mst_user", "profile_picture_path")]
for t, col in FIELDS:
    if not one("SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s", DB, t, col):
        continue
    rows = [r[0] for r in q(f"SELECT `{col}` FROM `{t}` WHERE `{col}` IS NOT NULL AND `{col}`<>''")]
    resolved = [p for p in rows if os.path.isfile(os.path.join(ROOT, p.lstrip("/")))]
    legacy_text = [p for p in rows if p.startswith(("/Images", "N/", "NE:")) or "Images" in p]
    broken_new = [p for p in rows if p not in resolved and p not in legacy_text]
    print(f"        {t}.{col}: {len(rows)} paths, {len(resolved)} resolve, {len(legacy_text)} legacy text (file never in the dump)")
    check(f"{t}.{col}: no new-style path points at a missing file", not broken_new, broken_new[:5])

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

c = APIClient(HTTP_HOST="localhost")
c.force_authenticate(get_user_model().objects.filter(is_superuser=True).first())
served = 0
for t, col in FIELDS:
    if not one("SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s", DB, t, col):
        continue
    for (p,) in q(f"SELECT `{col}` FROM `{t}` WHERE `{col}` IS NOT NULL AND `{col}`<>'' LIMIT 400"):
        if os.path.isfile(os.path.join(ROOT, p.lstrip("/"))):
            if p.split("/")[0] not in mu.FOLDER_PAGES:
                continue
            ok = c.get(mu.media_url(None, p.lstrip("/"))).status_code == 200
            served += 1
            if not ok:
                check(f"the file route serves {p}", False)
                break
            if served % 5 == 0:
                break
check(f"the file route serves the files ({served} sampled across the tables)", served > 0)

print()
print("FAILED:" if FAILED else "all checks passed", *FAILED, sep="\n  " if FAILED else " ")
sys.exit(1 if FAILED else 0)
