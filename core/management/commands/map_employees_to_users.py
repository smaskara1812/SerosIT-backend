"""Moves everything that depended on the legacy employee list (mst_employee, ~28k rows) onto users and plain names, so the app can stop
using that table.

What it does (dry run unless --apply; safe to run again, it only fills what is still empty):

  1. mst_user: for every user that has a legacy employee id, fills first/middle/last name, date of birth, company, mobile, working
     designation (when that designation exists in mst_working_designation), the end date (the legacy "date of leaving" goes into To,
     user_to, when To is empty) and the legacy photo text from the legacy employee row.

     Every employee detail (names included) is read from the legacy staging copy (--legacy-db, default Seros_Data, MySQL only), NEVER
     from the app's own mst_employee table. The employee id of a row in the tables below is not stored in the app any more either:
     the command reads it from the legacy source table of that row by primary key (the imports keep the legacy primary keys), see
     ROW_SOURCES. Without the staging copy the command stops instead of silently leaving names empty.
     Users that came from the legacy NON-employee list (shared and role accounts, `mst_user.nonemp_id`) are filled the same way from
     the staging table hr_Mst_NonEmployee: names, mobile, company, email (when the user has none), the end date (NonEmp_To into To)
     and the photo text. Title, type, SAP code, location and residence country are not carried.
  2. Doc To Sign Mapping: user = the user of the signer's employee id. A signer who has no user at all gets an inactive, no-login
     placeholder user (named like the employee) so every row points at a user.
  3. Alert To Users: user = the user of the employee id, left empty when there is none. A recipient with no user keeps the employee's
     name as text (recipient_name). The stored email is never changed.
  4. Business System owner, IT Asset Holder, IT Accessory Holder and IT Asset current holder: the employee's name is written as plain
     text (owner_name, holder_name, it_accessory_holder_name, cur_holder_name) when the text is still empty.

Which user for an employee id when several share it: an active user first, then the most recently created (latest cr_dt, then highest
user id). Every row that needed a rule, or could not be matched, is listed in the report CSV.

    python manage.py map_employees_to_users                    # dry run, prints counts, writes the report
    python manage.py map_employees_to_users --apply
    python manage.py map_employees_to_users --legacy-db Seros_Data --report path.csv
"""

import csv
import os
from collections import defaultdict

from django.conf import settings
from types import SimpleNamespace

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from core.models import (
    DocToSignMapping,
    ItAccessoryHolder,
    ItAssetHolder,
    MailAlertToUser,
    MstBusinessSystem,
    MstItAsset,
    MstUser,
    MstCompany,
    MstWorkingDesignation,
)

BATCH = 1000

# Where the employee id of a row lives in the legacy staging copy: app table -> (legacy table, its primary key, its employee id column).
# The imports keep the legacy primary keys, so a row here is the row with the same key there.
ROW_SOURCES = {
    "doc_to_sign_mapping": ("eos_Doc_To_Sign_Mapping", "Doc_To_Sign_Id", "Emp_Id"),
    "mail_alert_to_user": ("Mail_Alert_To_User", "Mail_Alert_To_User_Id", "EMP_ID"),
    "mst_business_system": ("Mst_Business_System", "Business_System_id", "Owner_Emp_Id"),
    "it_asset_holder": ("it_IT_Asset_Holder", "IT_Asset_Holder_Id", "Emp_Id"),
    "it_accessory_holder": ("it_IT_Accessory_Holder", "IT_Accessory_Holder_Id", "Emp_Id"),
    "mst_it_asset": ("it_Mst_IT_Asset", "IT_Asset_Id", "Emp_Id"),
}


def _full_name(e):
    return " ".join(p.strip() for p in (e.emp_fname, e.emp_mname, e.emp_sname) if p and p.strip())


def _blank(v):
    return v is None or (isinstance(v, str) and not v.strip())


class Command(BaseCommand):
    help = "Map employee ids onto users / plain names (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--legacy-db", default="Seros_Data", help="staging copy of the legacy database (MySQL); '' to skip")
        parser.add_argument("--report", default=None)

    # -- the rule for "which user is this employee" -----------------------------------------------------------------
    def _user_map(self):
        by_emp = defaultdict(list)
        for u in MstUser.objects.exclude(emp_id__isnull=True):
            by_emp[u.emp_id].append(u)
        chosen, ambiguous = {}, {}
        for emp_id, users in by_emp.items():
            users.sort(key=lambda u: (u.user_active == "Y", u.cr_dt, u.user_id), reverse=True)
            chosen[emp_id] = users[0]
            if len(users) > 1:
                ambiguous[emp_id] = users
        return chosen, ambiguous

    def _legacy_employees(self, db):
        """emp_id -> dict of the legacy employee columns (names and the ones mst_user takes) from the MySQL staging copy; {} when it is
        not readable."""
        if not db or connection.vendor != "mysql":
            return {}
        with connection.cursor() as c:
            try:
                c.execute(
                    f"SELECT EMP_ID, Emp_Fname, Emp_Mname, Emp_Sname, COMPANY_ID, Emp_DOB, EMP_MOBILE_NO, Working_Designation_Id, EMP_TO, "
                    f"EMP_PHOTO_PATH, EMP_FROM FROM `{db}`.Mst_Employee"
                )
            except Exception as exc:
                self.stderr.write(f"Legacy staging table not readable ({exc}).")
                return {}
            keys = ("fname", "mname", "sname", "company_id", "dob", "mobile", "designation", "emp_to", "photo", "emp_from")
            return {row[0]: dict(zip(keys, row[1:])) for row in c.fetchall()}

    def _legacy_nonemployees(self, db):
        """nonemp_id -> dict of the legacy non-employee columns that mst_user takes (staging copy only)."""
        with connection.cursor() as c:
            try:
                c.execute(f"SELECT NonEmp_Id, NonEmp_Fname, NonEmp_Mname, NonEmp_Sname, Company_Id, NonEmp_Mobile_No, NonEmp_Email, "
                          f"NonEmp_To, NonEmp_Photo_Path FROM `{db}`.hr_Mst_NonEmployee")
            except Exception as exc:
                self.stderr.write(f"Legacy non-employee table not readable ({exc}); those users are left as they are.")
                return {}
            keys = ("fname", "mname", "sname", "company_id", "mobile", "email", "nonemp_to", "photo")
            return {r[0]: dict(zip(keys, r[1:])) for r in c.fetchall()}

    def _row_employees(self, db, table):
        """primary key -> legacy employee id, for the rows of one app table, from the legacy staging copy."""
        src, pk, emp = ROW_SOURCES[table]
        with connection.cursor() as c:
            c.execute(f"SELECT `{pk}`, `{emp}` FROM `{db}`.`{src}` WHERE `{emp}` IS NOT NULL")
            return {r[0]: r[1] for r in c.fetchall()}

    def handle(self, *args, **opts):
        apply = opts["apply"]
        project = os.path.dirname(os.path.abspath(settings.BASE_DIR))
        report = opts["report"] or os.path.join(project, "documents", "employee_independence", "report.csv")
        rows = []  # (table, row id, employee id, what, detail)
        counts = defaultdict(int)

        designations = set(MstWorkingDesignation.objects.values_list("pk", flat=True))
        legacy = self._legacy_employees(opts["legacy_db"])
        if not legacy:
            raise CommandError(
                "The legacy staging copy is not readable (--legacy-db; MySQL only), and it is the only source of employee data. "
                "Nothing was changed.")
        emps = {i: SimpleNamespace(emp_fname=v["fname"], emp_mname=v["mname"], emp_sname=v["sname"]) for i, v in legacy.items()}
        row_emp = {t: self._row_employees(opts["legacy_db"], t) for t in ROW_SOURCES}
        chosen, ambiguous = self._user_map()
        for emp_id, users in sorted(ambiguous.items()):
            rows.append(("mst_user", chosen[emp_id].user_id, emp_id, "several users share this employee", f"chose user {chosen[emp_id].user_id} of {[u.user_id for u in users]}"))

        with transaction.atomic():
            # 1. mst_user details ---------------------------------------------------------------------------------
            to_save = []
            for u in MstUser.objects.exclude(emp_id__isnull=True):
                e, lg = emps.get(u.emp_id), legacy.get(u.emp_id, {})
                changed = False

                def fill(field, value):
                    nonlocal changed
                    if value not in (None, "") and _blank(getattr(u, field)) :
                        setattr(u, field, value.strip() if isinstance(value, str) else value)
                        changed = True

                if e:
                    fill("first_name", e.emp_fname)
                    fill("middle_name", e.emp_mname)
                    fill("last_name", e.emp_sname)
                fill("date_of_birth", lg.get("dob"))
                fill("mobile_no", lg.get("mobile"))
                if lg.get("designation") in designations and u.work_designation_id is None:
                    u.work_designation_id = lg["designation"]
                    changed = True
                fill("user_to", lg.get("emp_to"))
                fill("profile_picture_path", lg.get("photo"))
                if lg.get("company_id") is not None and u.company_id is None:
                    u.company_id = lg["company_id"]
                    changed = True
                if changed:
                    to_save.append(u)
            # the same for users that came from the non-employee list (shared and role accounts)
            nonemps = self._legacy_nonemployees(opts["legacy_db"])
            companies = set(MstCompany.objects.values_list("pk", flat=True))
            for u in MstUser.objects.filter(emp_id__isnull=True, nonemp_id__isnull=False):
                ne = nonemps.get(u.nonemp_id)
                if not ne:
                    rows.append(("mst_user", u.user_id, u.nonemp_id, "no legacy non-employee row for this user", ""))
                    continue
                changed = False

                def fill_ne(field, value):
                    nonlocal changed
                    if value not in (None, "", "NULL") and _blank(getattr(u, field)):
                        setattr(u, field, value.strip() if isinstance(value, str) else value)
                        changed = True

                fill_ne("first_name", ne["fname"])
                fill_ne("middle_name", ne["mname"])
                fill_ne("last_name", ne["sname"])
                fill_ne("mobile_no", ne["mobile"])
                fill_ne("user_email", ne["email"])
                fill_ne("user_to", ne["nonemp_to"])
                fill_ne("profile_picture_path", ne["photo"])
                if ne["company_id"] in companies and u.company_id is None:
                    u.company_id = ne["company_id"]
                    changed = True
                if changed:
                    to_save.append(u)
                    counts["non-employee users filled"] += 1
            counts["users filled"] = len(to_save)
            if apply:
                MstUser.objects.bulk_update(
                    to_save, ["first_name", "middle_name", "last_name", "date_of_birth", "mobile_no", "work_designation",
                              "user_to", "profile_picture_path", "company", "user_email"], batch_size=BATCH)

            # 2. Doc To Sign ---------------------------------------------------------------------------------------
            placeholders = {}
            unmapped = list(DocToSignMapping.objects.filter(user__isnull=True))
            for emp_id in sorted({row_emp["doc_to_sign_mapping"].get(d.pk) for d in unmapped} - {None}):
                if emp_id in chosen:
                    continue
                e, lg = emps.get(emp_id), legacy.get(emp_id, {})
                name = _full_name(e) if e else f"Employee {emp_id}"
                rows.append(("mst_user", "", emp_id, "placeholder user created for a Doc To Sign signer who is not a user", name))
                counts["placeholder users"] += 1
                if apply:
                    u = MstUser.objects.create(
                        user_name=name[:60], emp_id=emp_id, user_login_id=f"emp{emp_id}"[:20], user_active="N", user_type_id="E",
                        user_from=(lg.get("emp_from") or timezone.localdate()), user_email=None,
                        first_name=e.emp_fname if e else None, middle_name=e.emp_mname if e else None, last_name=e.emp_sname if e else None,
                        date_of_birth=lg.get("dob"), mobile_no=lg.get("mobile"), work_designation_id=(lg.get("designation") if lg.get("designation") in designations else None),
                        user_to=lg.get("emp_to"), company_id=lg.get("company_id"), profile_picture_path=lg.get("photo"),
                        cr_user_id=0, cr_dt=timezone.now(),
                    )
                    placeholders[emp_id] = u
            chosen.update(placeholders)

            todo = unmapped
            for d in todo:
                u = chosen.get(row_emp["doc_to_sign_mapping"].get(d.pk))
                if u:
                    d.user_id = u.user_id
                    counts["doc to sign rows -> user"] += 1
                else:  # dry run: the placeholder does not exist yet
                    counts["doc to sign rows -> placeholder user"] += 1
            if apply:
                DocToSignMapping.objects.bulk_update([d for d in todo if d.user_id], ["user"], batch_size=BATCH)

            # 3. Alert To Users ------------------------------------------------------------------------------------
            todo = []
            for m in MailAlertToUser.objects.filter(user__isnull=True, recipient_name__isnull=True, pk__in=list(row_emp["mail_alert_to_user"])):
                emp_of_row = row_emp["mail_alert_to_user"][m.pk]
                u = chosen.get(emp_of_row)
                if u:
                    m.user_id = u.user_id
                    counts["alert rows -> user"] += 1
                else:
                    e = emps.get(emp_of_row)
                    m.recipient_name = _full_name(e)[:100] if e else None
                    counts["alert rows with no user (name kept as text)"] += 1
                    rows.append(("mail_alert_to_user", m.mail_alert_to_user_id, emp_of_row, "no user for this employee", f"{m.recipient_name} <{m.email_addr}>"))
                todo.append(m)
            if apply:
                MailAlertToUser.objects.bulk_update(todo, ["user", "recipient_name"], batch_size=BATCH)

            # 4. plain names ---------------------------------------------------------------------------------------
            for label, model, name_field in (
                ("business system owner names", MstBusinessSystem, "owner_name"),
                ("asset holder names", ItAssetHolder, "holder_name"),
                ("accessory holder names", ItAccessoryHolder, "it_accessory_holder_name"),
                ("asset current holder names", MstItAsset, "cur_holder_name"),
            ):
                table = model._meta.db_table
                todo = []
                for obj in model.objects.filter(pk__in=list(row_emp[table])):
                    if not _blank(getattr(obj, name_field)):
                        continue
                    emp_of_row = row_emp[table][obj.pk]
                    e = emps.get(emp_of_row)
                    if not e:
                        rows.append((table, obj.pk, emp_of_row, "employee not found, name left empty", ""))
                        continue
                    setattr(obj, name_field, _full_name(e)[:100])
                    todo.append(obj)
                counts[label] = len(todo)
                if apply:
                    model.objects.bulk_update(todo, [name_field], batch_size=BATCH)

            if not apply:
                transaction.set_rollback(True)

        os.makedirs(os.path.dirname(report), exist_ok=True)
        with open(report, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["table", "row id", "employee id", "what", "detail"])
            w.writerows(rows)
        self.stdout.write(f"{'APPLIED' if apply else 'DRY RUN (nothing changed)'}")
        for k, v in counts.items():
            self.stdout.write(f"  {k}: {v}")
        self.stdout.write(f"  rows listed in the report: {len(rows)}  ->  {report}")
