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
    client = APIClient(HTTP_HOST="localhost")
    admin = get_user_model().objects.filter(is_superuser=True).first()
    client.force_authenticate(admin)

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

    # --- pages that are not switched on, and non-admins
    p = client.post("/api/admin/audit/%d/revert/preview/" % e_create, {"mode": "bogus"}, format="json").json()
    check("an unknown mode is refused", not p["allowed"])
    other = SysAuditLog.objects.create(
        username="zz", action="update", entity="masters.ranks", record_id="1", changes={"rank_name": {"old": "a", "new": "b"}}
    )
    p = preview(client, other.id, "after")
    check("a page that is not switched on cannot be reverted", not p["allowed"] and "not available" in (p.get("reason") or ""), str(p))
    export_row = SysAuditLog.objects.create(username="zz", action="export", entity=ENTITY, kind="event")
    p = preview(client, export_row.id, "after")
    check("an export entry cannot be reverted", not p["allowed"], str(p))
    plain = get_user_model().objects.create_user("zz_plain_user", password="x")
    c2 = APIClient(HTTP_HOST="localhost")
    c2.force_authenticate(plain)
    check("a non-admin cannot see history", c2.get("/api/admin/audit/history/", {"entity": ENTITY, "record_id": pk}).status_code == 403)
    check("a non-admin cannot revert", c2.post(f"/api/admin/audit/{e_up1}/revert/", {"mode": "after"}, format="json").status_code == 403)

    # --- the audit list carries the new fields and offers history on switched-on pages
    rows = client.get("/api/admin/audit/", {"entity": ENTITY}).json()["results"]
    check("the audit list offers History on a switched-on page", any(x.get("has_history") for x in rows))
    check("the audit list carries kind and source", all("kind" in x and "source" in x for x in rows))
    facets = client.get("/api/admin/audit/facets/").json()
    check("the facets list which pages support revert", ENTITY in facets.get("revertible", []))

    # --- source tag
    r = APIClient(HTTP_HOST="localhost", HTTP_X_AUDIT_SOURCE="selftest")
    r.force_authenticate(admin)
    r.post(CONTRACTORS, {"contractor_name": "ZZ Tagged"}, format="json")
    tagged = SysAuditLog.objects.filter(entity=ENTITY, action="create").order_by("-id").first()
    check("the self-test tag is recorded as the source", tagged.source == "selftest", tagged.source)


def main():
    try:
        with transaction.atomic():
            run()
            transaction.set_rollback(True)
    finally:
        print()
        print("FAILED: " + ", ".join(FAILED) if FAILED else "All checks passed.")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
