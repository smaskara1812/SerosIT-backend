"""Checks that printing needs the Export right and that saving a file needs Add or Edit, with real requests made by people
holding exactly the rights named. Everything runs in one transaction that is rolled back.

    cd backend
    .venv/bin/python scripts/check_row_rights.py

Before this check existed a view-only user could print the Incident Flash Report and the HSE Drill report (and the Monthly
HSE Review) and could upload signature and certificate files, because those actions had no entry in the rights table and
fell back to View.
"""
import os, sys, django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.test import APIClient
from core.models import Incident, HseDrillRecordHdr, UserProfile, UserPermission
from core.permissions import invalidate_user_access


class Rollback(Exception):
    pass


fails = []


def ok(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {detail}" if not cond else ""))
    if not cond:
        fails.append(name)


def mk(name, grants):
    """grants: {menu_key: (flags...)}"""
    U = get_user_model()
    u = U.objects.create_user(username=name, password="x")
    uid = (UserProfile.objects.order_by("-user_id").first().user_id or 0) + 1
    UserProfile.objects.create(user_id=uid, user_login_id=name, is_app_admin=False)
    for key, flags in grants.items():
        UserPermission.objects.create(
            user_id=uid, menu_key=key, can_view="view" in flags, can_add="add" in flags, can_edit="edit" in flags,
            can_delete="delete" in flags, can_export="export" in flags,
        )
    invalidate_user_access(name)
    c = APIClient(HTTP_HOST="localhost")
    c.force_authenticate(u)
    return c


KEYS = ["qhse.incident_details", "qhse.hse_drill_record", "qhse.mis_hse_review", "qhse.incident_register",
        "masters.doc_to_sign_mapping", "masters.interviewer_mapping", "qhse.rig_certificates"]

try:
    with transaction.atomic():
        viewer = mk("zzrr1", {k: ("view",) for k in KEYS})
        exporter = mk("zzrr2", {k: ("view", "export") for k in KEYS})
        adder = mk("zzrr3", {k: ("view", "add") for k in KEYS})

        inc = Incident.objects.exclude(marked_as_deleted="Y").order_by("-incident_id").first()
        drill = HseDrillRecordHdr.objects.order_by("-drill_record_hdr_id").first()

        print("A. printing needs Export")
        if inc:
            u = f"/api/qhse/incidents/{inc.incident_id}/flash-report/"
            ok("view-only: the list and the record still open", viewer.get("/api/qhse/incidents/?page_size=1").status_code == 200 and viewer.get(f"/api/qhse/incidents/{inc.incident_id}/").status_code == 200)
            ok("view-only cannot print the Incident Flash Report", viewer.get(u).status_code == 403)
            ok("Export holder can print the Incident Flash Report", exporter.get(u).status_code == 200)
        else:
            print("skip incident (no incident in this database)")
        if drill:
            u = f"/api/qhse/hse-drill-record/{drill.drill_record_hdr_id}/print/"
            ok("view-only cannot print the HSE Drill report", viewer.get(u).status_code == 403)
            ok("Export holder can print the HSE Drill report", exporter.get(u).status_code == 200)
        else:
            print("skip drill (no drill in this database)")
        ok("view-only cannot print the Incident Register", viewer.get("/api/qhse/incident-register/print/").status_code == 403)
        ok("Export holder can print the Incident Register", exporter.get("/api/qhse/incident-register/print/").status_code in (200, 400))
        u = "/api/qhse/mis-hse-review/print/"
        ok("view-only cannot print the Monthly HSE Review", viewer.get(u).status_code == 403)
        ok("Export holder passes the right check for the Monthly HSE Review", exporter.get(u).status_code != 403)

        print("B. saving a file needs Add or Edit")
        for label, path in (("a Doc To Sign signature", "/api/masters/doc-to-sign-mapping/upload-sign/"),
                            ("an interviewer signature", "/api/masters/interviewer-mapping/upload-sign/"),
                            ("a rig certificate", "/api/qhse/rig-certificates/upload-certificate/")):
            ok(f"view-only cannot upload {label}", viewer.post(path, {}, format="multipart").status_code == 403)
            ok(f"Export-only cannot upload {label}", exporter.post(path, {}, format="multipart").status_code == 403)
            ok(f"an Add holder passes the right check for {label}", adder.post(path, {}, format="multipart").status_code == 400, "expected 400 (no file sent), not 403")
        raise Rollback()
except Rollback:
    pass

print()
print("FAILED: " + ", ".join(fails) if fails else "all checks passed")
sys.exit(1 if fails else 0)
