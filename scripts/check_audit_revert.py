"""Checks record history and revert through the real API.

    cd backend
    .venv/bin/python scripts/check_audit_revert.py

Pilot pages: Contractors and Rig Types. Runs every request inside one transaction that is rolled back
at the end, so nothing is saved. Exits with status 1 if any check fails.
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

from core.models import MstContractor, MstRigSubtype, MstRigType, SysAuditLog

CONTRACTORS = "/api/masters/contractors/"
RIG_TYPES = "/api/masters/rig-types/"
ENTITY = "masters.contractors"
FAILED = []
HOST = "localhost"  # the self-test sets this to the host its other checks use


def check(name, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


def history(client, entity, pk):
    r = client.get("/api/admin/audit/history/", {"entity": entity, "record_id": pk})
    return r.json() if r.status_code == 200 else {"entries": [], "error": r.content[:200]}


def preview(client, entry_id, mode):
    return client.post(f"/api/admin/audit/{entry_id}/revert/preview/", {"mode": mode}, format="json").json()


def revert(client, entry_id, mode, reason=""):
    r = client.post(f"/api/admin/audit/{entry_id}/revert/", {"mode": mode, "reason": reason}, format="json")
    return r.status_code, r.json()


def run():
    client = APIClient(HTTP_HOST=HOST)
    admin = get_user_model().objects.filter(is_superuser=True).first()
    client.force_authenticate(admin)
    # The pilot pages are switched on in the database (Admin > History and Revert); this run is rolled back.
    from core import audit_revert as ar
    from core.models import SysMenu

    SysMenu.objects.filter(menu_key__in=[ENTITY, "masters.rig_types"]).update(history_enabled=True)
    ar.invalidate_enabled()

    # --- build a record with a known history: create, then two edits
    r = client.post(CONTRACTORS, {"contractor_name": "ZZ Revert One"}, format="json")
    check("a contractor is created", r.status_code == 201, r.content[:200])
    pk = r.json()["contractor_id"]
    client.patch(f"{CONTRACTORS}{pk}/", {"contractor_name": "ZZ Revert Two"}, format="json")
    client.patch(f"{CONTRACTORS}{pk}/", {"contractor_name": "ZZ Revert Three"}, format="json")

    h = history(client, ENTITY, pk)
    acts = [e["action"] for e in h["entries"]]
    check("history lists create, update, update in order", acts == ["create", "update", "update"], str(acts))
    check("the history says who and when", all(e["username"] and e["ts"] for e in h["entries"]))
    upd = h["entries"][1]["changes"]
    check("an edit shows before and after", any(c["field"] == "contractor_name" and c["old"] == "ZZ Revert One" and c["new"] == "ZZ Revert Two" for c in upd), str(upd))
    check("the latest entry is marked", h["entries"][-1]["is_latest"] and not h["entries"][0]["is_latest"])
    row = SysAuditLog.objects.filter(entity=ENTITY, action="update").order_by("-id").first()
    check("the log row names the exact record", row.target_table == "mst_contractor" and row.target_pk == str(pk), f"{row.target_table}/{row.target_pk}")
    check("the log row has a batch id and the kind 'change'", bool(row.batch_id) and row.kind == "change")

    e_create, e_up1, e_up2 = [e["id"] for e in h["entries"]]

    # --- restore to the state after the first edit
    p = preview(client, e_up1, "after")
    check("preview: restoring to after edit 1 is allowed and changes the name", p.get("allowed") and p["fields"] and p["fields"][0]["restore_to"] == "ZZ Revert Two", str(p))
    check("preview changes nothing", MstContractor.objects.get(pk=pk).contractor_name == "ZZ Revert Three")
    code, res = revert(client, e_up1, "after", "wrong name entered")
    check("restore to after edit 1 succeeds", code == 200 and res.get("ok"), str(res))
    check("the record has the earlier name", MstContractor.objects.get(pk=pk).contractor_name == "ZZ Revert Two")
    rv = SysAuditLog.objects.filter(action="revert", target_pk=str(pk)).order_by("-id").first()
    check("the revert is logged, linked to its source, with the reason", rv is not None and rv.reverted_of == e_up1 and rv.note == "wrong name entered")
    check("the revert stamps who modified the record", MstContractor.objects.get(pk=pk).mod_dt is not None)

    # --- the revert is in the history and can itself be reverted
    h = history(client, ENTITY, pk)
    check("history now includes the revert", [e["action"] for e in h["entries"]][-1] == "revert")
    code, res = revert(client, h["entries"][-1]["id"], "before")
    check("the revert can be undone", code == 200 and MstContractor.objects.get(pk=pk).contractor_name == "ZZ Revert Three", str(res))

    # --- restoring to the state the record is already in
    h = history(client, ENTITY, pk)
    p = preview(client, h["entries"][-1]["id"], "after")
    check("restoring to the current state is refused as nothing to change", not p["allowed"] and "Nothing to change" in (p.get("reason") or ""), str(p))

    # --- a change made outside the log is a conflict
    MstContractor.objects.filter(pk=pk).update(contractor_name="ZZ Changed Behind The Log")
    p = preview(client, e_up1, "after")
    check("a value changed outside the log blocks the revert", not p["allowed"] and "outside the logged" in (p.get("reason") or ""), str(p))
    code, res = revert(client, e_up1, "after")
    check("and nothing is changed", code == 400 and MstContractor.objects.get(pk=pk).contractor_name == "ZZ Changed Behind The Log")
    MstContractor.objects.filter(pk=pk).update(contractor_name="ZZ Revert Three")

    # --- delete, then restore it with the same id
    r = client.delete(f"{CONTRACTORS}{pk}/")
    check("the contractor is deleted", r.status_code == 204)
    h = history(client, ENTITY, pk)
    last = h["entries"][-1]
    check("the delete entry holds the whole row", last["action"] == "delete" and any(c["field"] == "contractor_name" and c["old"] == "ZZ Revert Three" for c in last["changes"]), str(last))
    check("history of a deleted record says it no longer exists", h["exists"] is False)
    p = preview(client, last["id"], "before")
    check("preview: the delete can be undone", p["allowed"] and p["action"] == "insert", str(p))
    code, res = revert(client, last["id"], "before")
    check("restoring the deleted contractor succeeds", code == 200, str(res))
    back = MstContractor.objects.filter(pk=pk).first()
    check("it comes back with the same id and name", back is not None and back.contractor_name == "ZZ Revert Three", str(back))
    check("and keeps who created it", back is not None and back.cr_user_id is not None and back.cr_dt is not None)

    # --- a restore must obey the page's own rules (duplicate names are not allowed)
    r = client.delete(f"{CONTRACTORS}{pk}/")
    h = history(client, ENTITY, pk)
    r2 = client.post(CONTRACTORS, {"contractor_name": "ZZ Revert Three"}, format="json")
    check("the name is free again, so a new record can take it", r2.status_code == 201, r2.content[:200])
    p = preview(client, h["entries"][-1]["id"], "before")
    check("restoring is refused when the name is now used", not p["allowed"] and "ZZ Revert Three" in (p.get("reason") or ""), str(p))
    code, res = revert(client, h["entries"][-1]["id"], "before")
    check("and nothing is restored", code == 400 and not MstContractor.objects.filter(pk=pk).exists())

    # --- undo a creation (removes the row)
    r = client.post(RIG_TYPES, {"rig_type_name": "ZZ Type"}, format="json")
    check("a rig type is created", r.status_code == 201, r.content[:200])
    tpk = r.json()["rig_type_id"]
    h = history(client, "masters.rig_types", tpk)
    create_id = h["entries"][0]["id"]
    p = preview(client, create_id, "before")
    check("preview: undoing a creation means deleting the row", p["allowed"] and p["action"] == "delete", str(p))

    # --- ...but not while something else still uses it
    sub = MstRigSubtype.objects.create(rig_subtype_name="ZZ Sub", rig_type_id=tpk, cr_user_id=1, cr_dt=django.utils.timezone.now())
    code, res = revert(client, create_id, "before")
    check("undoing a creation is refused while other records use it", code == 400 and "still use" in res.get("error", ""), str(res))
    check("and the rig type is still there", MstRigType.objects.filter(pk=tpk).exists())
    sub.delete()
    code, res = revert(client, create_id, "before")
    check("once nothing uses it, the creation can be undone", code == 200 and not MstRigType.objects.filter(pk=tpk).exists(), str(res))
    h = history(client, "masters.rig_types", tpk)
    check("the undo shows in the history as a removal", h["entries"][-1]["action"] == "revert_delete" and h["exists"] is False)
    code, res = revert(client, h["entries"][-1]["id"], "before")
    check("and that can be undone too (the rig type is back)", code == 200 and MstRigType.objects.filter(pk=tpk).exists(), str(res))

    # --- an approval is a barrier: a record can't be reverted past one
    r = client.post(CONTRACTORS, {"contractor_name": "ZZ Barrier"}, format="json")
    bpk = r.json()["contractor_id"]
    client.patch(f"{CONTRACTORS}{bpk}/", {"contractor_name": "ZZ Barrier Two"}, format="json")
    first = history(client, ENTITY, bpk)["entries"][0]["id"]
    SysAuditLog.objects.create(
        username="zz_approver", action="approve", entity=ENTITY, record_id=str(bpk), target_table="mst_contractor", target_pk=str(bpk)
    )
    p = preview(client, first, "after")
    check("restoring past an approval is refused", not p["allowed"] and "approved by zz_approver" in (p.get("reason") or ""), str(p))
    code, res = revert(client, first, "after")
    check("and nothing is changed", code == 400 and MstContractor.objects.get(pk=bpk).contractor_name == "ZZ Barrier Two", str(res))
    client.patch(f"{CONTRACTORS}{bpk}/", {"contractor_name": "ZZ Barrier Three"}, format="json")
    client.patch(f"{CONTRACTORS}{bpk}/", {"contractor_name": "ZZ Barrier Four"}, format="json")
    after_approval = history(client, ENTITY, bpk)["entries"][2]["id"]
    p = preview(client, after_approval, "after")
    check("a version created after the approval can still be restored", p["allowed"], str(p))

    # --- records created since the change are reported in the preview
    r = client.post(RIG_TYPES, {"rig_type_name": "ZZ Warn"}, format="json")
    wpk = r.json()["rig_type_id"]
    client.patch(f"{RIG_TYPES}{wpk}/", {"rig_type_name": "ZZ Warn Two"}, format="json")
    from datetime import timedelta
    from django.utils import timezone as tz

    MstRigSubtype.objects.create(rig_subtype_name="ZZ Old Sub", rig_type_id=wpk, cr_user_id=1, cr_dt=tz.now() - timedelta(days=2))
    MstRigSubtype.objects.create(rig_subtype_name="ZZ New Sub", rig_type_id=wpk, cr_user_id=1, cr_dt=tz.now() + timedelta(seconds=1))
    wh = history(client, "masters.rig_types", wpk)["entries"]
    p = preview(client, wh[-1]["id"], "before")
    check("the preview lists records created after the change", p["allowed"] and p["warnings"] == [{"label": "Rig Subtype", "count": 1}], f"warnings={p.get('warnings')} problems={p.get('warnings_problems')} since={p.get('since')}")
    check("the preview says since when", bool(p.get("since")))
    p = preview(client, e_up1, "after")
    check("a preview with nothing depending on it has no warnings", p.get("warnings") == [], str(p.get("warnings")))

    # --- the admin switch: History and revert per page, one setting for the whole system
    settings = client.get("/api/admin/history-settings/").json()["pages"]
    mine = next((x for x in settings if x["menu_key"] == ENTITY), None)
    check("the settings list shows the page as supported and switched on", mine is not None and mine["supported"] and mine["enabled"], str(mine))
    check("pages the code does not support yet are listed but cannot be enabled", any(not x["supported"] for x in settings))
    r = client.put("/api/admin/history-settings/", {"menu_keys": ["qhse.mis_hse_return"], "enabled": True}, format="json")
    check("an unsupported page cannot be switched on", r.status_code == 400, r.content[:160])
    r = client.put("/api/admin/history-settings/", {"menu_keys": [ENTITY], "enabled": False}, format="json")
    check("a page can be switched off", r.status_code == 200 and not next(x for x in r.json()["pages"] if x["menu_key"] == ENTITY)["enabled"], r.content[:160])
    logged = SysAuditLog.objects.filter(action="history_setting", record_id=ENTITY).order_by("-id").first()
    check("the change is written to the audit trail", logged is not None and logged.changes["history_enabled"]["new"] is False, str(logged and logged.changes))
    r = client.get("/api/admin/audit/history/", {"entity": ENTITY, "record_id": pk})
    check("switched off: the history is refused with a clear reason", r.status_code == 400 and "switched off" in r.json().get("error", ""), r.content[:200])
    p = preview(client, e_up1, "after")
    check("switched off: a revert is refused", not p["allowed"] and "switched off" in (p.get("reason") or ""), str(p))
    code, res = revert(client, e_up1, "after")
    check("switched off: nothing is restored", code == 400)
    check("switched off: the page is missing from the revertible list", ENTITY not in client.get("/api/admin/audit/facets/").json()["revertible"])
    rows = client.get("/api/admin/audit/", {"entity": ENTITY}).json()["results"]
    check("switched off: the Audit Trail offers no History link, but still lists the changes", rows and not any(x["has_history"] for x in rows))
    r = client.put("/api/admin/history-settings/", {"menu_keys": [ENTITY], "enabled": True}, format="json")
    check("switched back on", r.status_code == 200 and next(x for x in r.json()["pages"] if x["menu_key"] == ENTITY)["enabled"])
    check("switched on again: the history is back", len(history(client, ENTITY, pk)["entries"]) > 0)
    plain_admin_client = None

    # --- logging on the pages that are logged but not revertible: admin pages and the MIS return
    r = client.post("/api/admin/permission-presets/create/", {"name": "ZZ Log Preset", "description": "check", "menus": {"masters.rigs": {"view": True, "add": True}}}, format="json")
    check("a preset can be created", r.status_code == 201, r.content[:160])
    pid = r.json().get("id")
    made = SysAuditLog.objects.filter(entity="admin.permission_presets", action="create", record_id=str(pid)).first()
    check("creating a preset records what it grants", made is not None and (made.changes or {}).get("menus", {}).get("new", {}).get("masters.rigs", {}).get("add") is True, str(made and made.changes))
    r = client.delete(f"/api/admin/permission-presets/{pid}/delete/")
    gone = SysAuditLog.objects.filter(entity="admin.permission_presets", action="delete", record_id=str(pid)).first()
    check("deleting a preset records what it held", r.status_code == 204 and gone is not None and (gone.changes or {}).get("menus", {}).get("old", {}).get("masters.rigs", {}).get("view") is True, str(gone and gone.changes))
    r = client.post("/api/admin/user-management/create/", {"login_id": "zz_log_user", "name": "ZZ Log User", "password": "x1y2z3", "user_type": "N"}, format="json")
    uid_new = r.json().get("user_id") if r.status_code == 200 else None
    made = SysAuditLog.objects.filter(entity="admin.user_management", action="create", record_id=str(uid_new)).first() if uid_new else None
    check("creating a user is logged with the user row and that a password was set, never the password", made is not None and made.target_table == "mst_user" and (made.changes or {}).get("local_password", {}).get("new") is True and "x1y2z3" not in str(made.changes), str(made and made.changes))
    if uid_new:
        client.post(f"/api/admin/user-management/{uid_new}/set-password/", {"password": "p4ssw0rd!"}, format="json")
        pw = SysAuditLog.objects.filter(entity="admin.user_management", action="password_change", record_id=str(uid_new)).order_by("-id").first()
        check("a password change is logged without the password", pw is not None and "p4ssw0rd" not in str(pw.changes), str(pw and pw.changes))

    from core.models import MisMonthlyHseReturnsHdr, MstCostCentre

    cc = next((c for c in MstCostCentre.objects.order_by("pk")[:80] if not MisMonthlyHseReturnsHdr.objects.filter(cost_centre=c, report_month="2001-01-01").exists()
               and not (c.rig_id and MisMonthlyHseReturnsHdr.objects.filter(rig_id=c.rig_id, report_month="2001-01-01").exists())), None)
    if cc is None:
        check("MIS return logging (needs a free cost centre)", False, "no cost centre without a January 2001 return")
    else:
        r = client.post("/api/qhse/mis-hse-return/", {"cost_centre": cc.pk, "report_no": "ZZ", "report_month": "2001-01"}, format="json")
        check("a MIS return can be created", r.status_code == 201, r.content[:160])
        hid = r.json().get("monthly_hse_returns_hdr_id") or r.json().get("id")
        made = SysAuditLog.objects.filter(entity="qhse.mis_hse_return", action="create", target_table="mis_monthly_hse_returns_hdr", target_pk=str(hid)).first()
        check("creating a MIS return records its values", made is not None and made.changes, str(made and made.changes))
        r = client.put(f"/api/qhse/mis-hse-return/{hid}/incidents/", {"lti_free_days": 7}, format="json")
        e = SysAuditLog.objects.filter(entity="qhse.mis_hse_return", action="update", target_pk=str(hid)).order_by("-id").first()
        check("changing LTI free days records before and after", r.status_code == 200 and e is not None and "lti_free_days" in (e.changes or {}), str(e and e.changes))
        r = client.delete(f"/api/qhse/mis-hse-return/{hid}/")
        d = SysAuditLog.objects.filter(entity="qhse.mis_hse_return", action="delete", target_pk=str(hid)).first()
        check("deleting a MIS return records the whole return", r.status_code == 204 and d is not None and (d.changes or {}).get("report_no", {}).get("old") == "ZZ", str(d and d.changes))

    # --- pages that are not switched on, and non-admins
    p = client.post("/api/admin/audit/%d/revert/preview/" % e_create, {"mode": "bogus"}, format="json").json()
    check("an unknown mode is refused", not p["allowed"])
    other = SysAuditLog.objects.create(
        username="zz", action="update", entity="qhse.mis_hse_return", record_id="1", changes={"remarks": {"old": "a", "new": "b"}}
    )
    p = preview(client, other.id, "after")
    check("a page that is not switched on cannot be reverted", not p["allowed"] and "not available" in (p.get("reason") or ""), str(p))
    export_row = SysAuditLog.objects.create(username="zz", action="export", entity=ENTITY, kind="event")
    p = preview(client, export_row.id, "after")
    check("an export entry cannot be reverted", not p["allowed"], str(p))
    plain = get_user_model().objects.create_user("zz_plain_user", password="x")
    c2 = APIClient(HTTP_HOST=HOST)
    c2.force_authenticate(plain)
    check("a non-admin cannot see history", c2.get("/api/admin/audit/history/", {"entity": ENTITY, "record_id": pk}).status_code == 403)
    check("a non-admin cannot revert", c2.post(f"/api/admin/audit/{e_up1}/revert/", {"mode": "after"}, format="json").status_code == 403)
    check("a non-admin cannot read or change the settings", c2.get("/api/admin/history-settings/").status_code == 403 and c2.put("/api/admin/history-settings/", {"menu_keys": [ENTITY], "enabled": False}, format="json").status_code == 403)

    # --- the audit list carries the new fields and offers history on switched-on pages
    rows = client.get("/api/admin/audit/", {"entity": ENTITY}).json()["results"]
    check("the audit list offers History on a switched-on page", any(x.get("has_history") for x in rows))
    check("the audit list carries kind and source", all("kind" in x and "source" in x for x in rows))
    facets = client.get("/api/admin/audit/facets/").json()
    check("the facets list which pages support revert", ENTITY in facets.get("revertible", []))

    # --- source tag
    r = APIClient(HTTP_HOST=HOST, HTTP_X_AUDIT_SOURCE="selftest")
    r.force_authenticate(admin)
    r.post(CONTRACTORS, {"contractor_name": "ZZ Tagged"}, format="json")
    tagged = SysAuditLog.objects.filter(entity=ENTITY, action="create").order_by("-id").first()
    check("the self-test tag is recorded as the source", tagged.source == "selftest", tagged.source)


def main():
    crashed = False
    try:
        with transaction.atomic():
            run()
            transaction.set_rollback(True)
    except Exception:  # a crash is a failure, never a pass
        import traceback

        traceback.print_exc()
        crashed = True
    finally:
        print()
        if FAILED:
            print("FAILED: " + ", ".join(FAILED))
        elif crashed:
            print("FAILED: the script stopped with an error (see above).")
        else:
            print("All checks passed.")
    sys.exit(1 if (FAILED or crashed) else 0)


if __name__ == "__main__":
    main()
