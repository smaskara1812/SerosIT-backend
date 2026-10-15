"""Runs the history and revert flow on every plain master page, through the real API.

    cd backend
    .venv/bin/python scripts/check_revert_masters.py                      # every candidate page
    .venv/bin/python scripts/check_revert_masters.py masters.ranks ...    # only these menu keys
    .venv/bin/python scripts/check_revert_masters.py --enabled            # only pages already switched on

For each page it copies an existing record under a new name, edits it twice, restores an earlier
version, deletes it, restores the deleted record (same id), and undoes the creation. A page passes when
all of that works. A page that cannot be exercised this way (no editable name, a copy is refused, the
delete is blocked) is listed as MANUAL with the reason, and needs a person to decide.

Everything runs inside a transaction that is rolled back, so nothing is saved.
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

from core import audit_revert as ar
from core.urls import router

HOST = "localhost"  # the self-test sets this to the host its other checks use
READ_ONLY_KEYS = {"cr_user_id", "cr_dt", "mod_user_id", "mod_dt"}
SKIP_PREFIXES = ("qhse.", "drilling.")  # document pages: later phases


# Pages whose name cannot be used for the edits (it is not editable, or follows a pattern): the field to
# edit instead, and three valid values for it, used for the copy and the two edits.
EDIT_OVERRIDES = {
    "it_asset.it_accessory_holders": ("it_accessory_holder_remark", ["ZZ remark 1", "ZZ remark 2", "ZZ remark 3"]),
    "masters.hse_drills": ("hse_drill_active", ["Y", "N", "Y"]),  # name and frequency are locked once a drill is saved
    "masters.notification_triggers": ("notification_trigger_active", ["Y", "N", "Y"]),
    "masters.mail_recipient_mappings": ("event_type", ["FINALIZE", "APPROVE", "REJECT"]),
    "masters.rigs": ("rig_name", ["ZZ Rig A", "ZZ Rig B", "ZZ Rig C"]),  # at most two digits in a rig name
    # Mapping pages have no name; an ordinary editable field of each stands in.
    "masters.cost_centre_to_company_mapping": ("mapping_to", ["2090-01-01", "2090-01-02", "2090-01-03"]),
    "masters.crew_change_reliever_mapping": ("active", ["Y", "N", "Y"]),
    "masters.crew_schedule_exceptions": ("exception_to", ["2090-01-01", "2090-01-02", "2090-01-03"]),
    "masters.doc_to_sign_mapping": ("sign_path", ["ZZ/a.png", "ZZ/b.png", "ZZ/c.png"]),
    "masters.drilling_work_shift": ("work_shift_days", [1, 2, 1]),  # shift days must be 1 or 2
    "masters.fs_catg_to_rank_mapping": ("rank_order", [901, 902, 903]),
    "masters.fs_catg_to_rig_type_mapping": ("mapping_active", ["Y", "N", "Y"]),
    "masters.fs_catg_to_sstype": ("business_system_id_2", ["Y", "N", "Y"]),
    "masters.interviewer_mapping": ("sign_path", ["ZZ/a.png", "ZZ/b.png", "ZZ/c.png"]),
    "masters.nationality_to_emp_type_mapping": ("active", ["Y", "N", "Y"]),
    "masters.project_drilling_rates": ("rate", ["101", "102", "103"]),
    "masters.rig_crew_exceptions": ("exception_to", ["2090-01-01", "2090-01-02", "2090-01-03"]),
    "masters.rig_site_mapping": ("camp_office_addr", ["ZZ camp office address 1", "ZZ camp office address 2", "ZZ camp office address 3"]),
    "masters.user_category_mapping": ("mapping_to", ["2090-01-01", "2090-01-02", "2090-01-03"]),
    "masters.user_rig_mapping": ("mapping_to", ["2090-01-01", "2090-01-02", "2090-01-03"]),
    # Phase 2 pages
    "masters.travel_eligibility": ("travel_class", ["ZZ class one", "ZZ class two", "ZZ class three"]),
    "masters.fs_emp_cur_status": ("appx_end_dt", ["2089-12-31", "2090-01-02", "2090-01-03"]),
    "it_asset.it_asset_holders": ("holder_remark", ["ZZ r1", "ZZ r2", "ZZ r3"]),
    "admin.approver_mapping": ("approver_level", [7, 8, 9]),
    # Phase 3 pages
    "qhse.rig_certificates": ("remark", ["ZZ remark 1", "ZZ remark 2", "ZZ remark 3"]),
    "qhse.rig_certificate_schedule": ("remark", ["ZZ remark 1", "ZZ remark 2", "ZZ remark 3"]),
    "qhse.hazard_id_card": ("action_taken", ["ZZ action one", "ZZ action two", "ZZ action three"]),
    "qhse.incident_details": ("comments", ["ZZ comment one", "ZZ comment two", "ZZ comment three"]),
    "qhse.incident_root_cause": ("root_subcause_others", ["ZZ other one", "ZZ other two", "ZZ other three"]),
    "qhse.incident_actions": ("action_taken", ["ZZ taken one", "ZZ taken two", "ZZ taken three"]),
    "qhse.corrective_actions": ("action_taken", ["ZZ taken one", "ZZ taken two", "ZZ taken three"]),
}

# Pages where "delete" only marks the record deleted (the row stays). Deleting is a logged edit, restoring
# the version before it un-deletes the record, and undoing the creation must be refused.
SOFT_DELETE = {
    key: ("marked_as_deleted", "N", "Y", {"deleted_remarks": "ZZ reason for the check"})
    for key in ("qhse.hazard_id_card", "qhse.incident_details", "qhse.incident_root_cause", "qhse.incident_actions")
}

# Extra values for the copy a page is given, where a straight copy would clash with the original.
CREATE_EXTRA = {
    "it_asset.it_asset_holders": {"it_asset_holder_from": "1999-01-01", "it_asset_holder_to": "1999-02-01T00:00:00"},
    "admin.approver_mapping": {"approver_active": "Y"},  # older rows hold a blank the page would refuse
    "qhse.activities": {"intimate_vessel": "N"},
    "drilling.drilling_information": {"distance_covered_kms_knots": 5},
    "qhse.rig_certificate_schedule": {"scheduled_dt": "2090-01-01"},
}

# Pages whose records cannot be created or deleted on their own (the record belongs to another one, so
# a copy cannot be made): an existing record is edited twice and its versions restored instead.
EDIT_ONLY = {"masters.fs_emp_cur_status"}


# Pages with a header and detail lines: (header viewset, line viewset, the line's field that points at the
# header, a header field to give the copy a new value, a line field to do the same). Deleting the header
# deletes its lines; restoring it has to bring them back too.
CHILD_PAIRS = {
    "masters.job_descriptions": ("JobDescriptionHdrViewSet", "JobDescriptionDtlViewSet", "header", "jd_hdr_description", "jd_dtl_description"),
    "masters.project_contract": ("ProjectContractViewSet", "ProjectContractDtlViewSet", "contract", "prj_contract_no", None),
    "masters.fs_employees": ("MstFsEmployeeViewSet", "FsEmpCurStatusViewSet", "fs_emp", "fs_emp_fname", None),
    "qhse.hse_weekly_drill": ("HseWeeklyDrillHdrViewSet", "HseWeeklyDrillDtlViewSet", "hdr", {"drill_week": 53}, {"drill_conducted_dt": "2019-01-02"}),
    "qhse.training_group": ("TrainingGroupHdrViewSet", "TrainingGroupDtlViewSet", "hdr", "training_group_hdr_name", None),
    "qhse.training_org": ("TrainingOrgHdrViewSet", "TrainingOrgDtlViewSet", "hdr", "training_org_name", None),
    "qhse.training_log": ("TrainingLogHdrViewSet", "TrainingLogDtlViewSet", "hdr", "training_location", "active_on_rig"),
    "qhse.hse_drill_record": ("HseDrillRecordHdrViewSet", "HseDrillRecordEventViewSet", "hdr", {"drill_dt": __import__("datetime").date.today().isoformat() + "T00:00:00", "control_room_on_shore": "N"}, None),
}

# Pages whose detail rows are created by the page itself when the header is created, and that have no edit:
# (header viewset, the header fields to give the copy). Create, delete, restore, undo and redo are checked,
# and the detail rows must come back in the same number.
AUTO_LINES = {
    "qhse.leading_indicators": ("LeadingIndicatorsViewSet", {"period_month": "2001-01"}),
    "qhse.lagging_indicators": ("LaggingIndicatorsViewSet", {"period_month": "2001-01"}),
}


class Manual(Exception):
    """The page cannot be exercised automatically; str(exc) says why."""


def base_urls():
    out = {}
    for prefix, viewset, _basename in router.registry:
        out.setdefault(viewset, f"/api/{prefix}/")
    return out


def candidates():
    """Master pages that look plain: one viewset, a name field, no custom save code, no child rows."""
    urls = base_urls()
    found = []
    for key, classes in sorted(ar.viewsets_by_entity().items()):
        if key.startswith(SKIP_PREFIXES) or len(classes) != 1:
            continue
        cls = classes[0]
        if any(name in cls.__dict__ for name in ("perform_create", "perform_update", "destroy")):
            continue
        model = cls.queryset.model
        if any(rel.on_delete.__name__ == "CASCADE" for rel in model._meta.related_objects):
            continue
        if (not getattr(cls, "name_field", None) and key not in EDIT_OVERRIDES) or cls not in urls:
            continue
        found.append(key)
    return found


def same(a, b):
    """Compare a stored value with the text the check sent: dates and decimals come back as objects."""
    from decimal import Decimal, InvalidOperation

    if hasattr(a, "isoformat"):
        a = a.isoformat()[:10] if len(str(b)) == 10 else a.isoformat()
    if str(a) == str(b):
        return True
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except InvalidOperation:
        return False


def culprit_fields(errors):
    """Field names a 400 response complains about, including the "fields a, b must make a unique set" form."""
    import re

    names = []
    if isinstance(errors, dict):
        for key, msgs in errors.items():
            if key in ("non_field_errors", "__all__"):
                for m in msgs if isinstance(msgs, list) else [msgs]:
                    hit = re.search(r"fields? (.+?) must make a unique set", str(m))
                    if hit:
                        names.extend(n.strip() for n in hit.group(1).split(","))
            else:
                names.append(key)
    return names


def history(client, entity, pk):
    r = client.get("/api/admin/audit/history/", {"entity": entity, "record_id": pk})
    return r.json()["entries"] if r.status_code == 200 else []


def fire(client, entry_id, mode):
    r = client.post(f"/api/admin/audit/{entry_id}/revert/", {"mode": mode}, format="json")
    return r.status_code == 200 and r.json().get("ok"), r.json()


def switch_on(entity):
    """Supported for this run, and switched on in the database (the admin setting); both are undone: the second
    by the transaction this runs in, the first only exists in this process."""
    from core.models import SysMenu

    if entity not in ar.REVERTIBLE_ENTITIES:
        ar.REVERTIBLE_ENTITIES.append(entity)
    SysMenu.objects.filter(menu_key=entity).update(history_enabled=True)
    ar.invalidate_enabled()


def exercise(client, entity):
    """Returns None when the page passes; raises Manual or AssertionError otherwise."""
    switch_on(entity)
    exercise_basic(client, entity)
    extra = EXTRAS.get(entity)
    if extra:
        extra(client, entity)


def exercise_basic(client, entity):
    own = OWN_CHECKS.get(entity)
    if own:
        return own(client, entity)
    if entity not in ar.REVERTIBLE_ENTITIES:
        ar.REVERTIBLE_ENTITIES.append(entity)  # supported for this run only, so a page can be tried before it is added
    # Switched on in the database too (the admin setting); this runs inside a transaction that is rolled back.
    from core.models import SysMenu

    SysMenu.objects.filter(menu_key=entity).update(history_enabled=True)
    ar.invalidate_enabled()
    if entity in CHILD_PAIRS:
        return exercise_children(client, entity)
    if entity in AUTO_LINES:
        return exercise_auto_lines(client, entity)
    if entity == "drilling.drilling_report":
        return exercise_drilling_report(client, entity)
    cls = ar.viewsets_by_entity()[entity][0]
    model = cls.queryset.model
    url = base_urls()[cls]
    pk_name = model._meta.pk.name
    edit_field, edit_values = EDIT_OVERRIDES.get(entity, (cls.name_field, None))
    name_field = cls.name_field or edit_field
    field = model._meta.get_field(name_field)
    limit = getattr(field, "max_length", None) or 40

    sample = model.objects.order_by(pk_name).first()
    if sample is None:
        raise Manual("no existing record to copy")

    if entity in CHILD_PAIRS:
        return exercise_children(client, entity)
    if entity in EDIT_ONLY:
        return exercise_edit_only(client, entity, url, model, sample, edit_field, edit_values or [])

    def uniq(n):
        if edit_values:
            return edit_values[n - 1]
        return f"ZZ{os.getpid() % 1000}{n}"[:limit]

    detail = client.get(f"{url}{sample.pk}/")
    if detail.status_code != 200:
        raise Manual(f"cannot read a record ({detail.status_code})")
    payload = {k: v for k, v in detail.json().items() if k != pk_name and k not in READ_ONLY_KEYS}
    for f in model._meta.fields:
        if f.get_internal_type() == "DateField" and isinstance(payload.get(f.name), str):
            payload[f.name] = payload[f.name][:10]
    payload[edit_field] = uniq(1)
    payload.update(CREATE_EXTRA.get(entity, {}))
    if edit_field != name_field:
        payload[name_field] = f"ZZ{os.getpid() % 1000}"[:limit]  # keep the copy's name unique as well

    r = client.post(url, payload, format="json")
    # A copy can clash with another unique field (a short name, a code, a unique pair). Give each field
    # the page names in its refusal a value of its own and try again.
    for attempt in range(8):
        if r.status_code != 400:
            break
        bad = culprit_fields(r.json())
        changed = False
        for name in bad:
            if name == edit_field or name not in payload:
                continue
            value = payload[name]
            mfield = next((f for f in model._meta.fields if f.name == name), None)
            if mfield is not None and mfield.many_to_one:
                others = list(mfield.related_model._default_manager.exclude(pk=value).values_list("pk", flat=True)[:attempt + 1])
                if len(others) > attempt:
                    payload[name] = others[attempt]
                    changed = True
                continue
            if mfield is not None and mfield.get_internal_type() == "DateField":
                payload[name] = f"2001-01-{attempt + 1:02d}"
                changed = True
                continue
            if isinstance(value, str):
                lim = getattr(model._meta.get_field(name), "max_length", None) or 40 if name in {f.name for f in model._meta.fields} else 40
                payload[name] = f"Z{os.getpid() % 100}{attempt}"[:lim]
                changed = True
            elif isinstance(value, int) and not isinstance(value, bool):
                payload[name] = 900000 + os.getpid() % 1000 + attempt
                changed = True
        if not changed:
            break
        r = client.post(url, payload, format="json")
    if r.status_code != 201:
        raise Manual(f"a copy of an existing record was refused ({r.status_code}): {str(r.content[:160])}")
    pk = r.json()[pk_name]

    for n in (2, 3):
        r = client.patch(f"{url}{pk}/", {edit_field: uniq(n)}, format="json")
        if r.status_code != 200 or not same(r.json().get(edit_field), uniq(n)):
            raise Manual(f"the name could not be edited through the page ({r.status_code}): {str(r.content[:140])}")

    entries = history(client, entity, pk)
    assert [e["action"] for e in entries] == ["create", "update", "update"], f"history is {[e['action'] for e in entries]}"

    ok, res = fire(client, entries[1]["id"], "after")
    assert ok, f"restore to version 2 failed: {res}"
    assert same(getattr(model.objects.get(pk=pk), edit_field), uniq(2)), "the value was not restored"

    if entity in SOFT_DELETE:
        flag, live, gone, body = SOFT_DELETE[entity]
        r = client.delete(f"{url}{pk}/", body, format="json")
        assert r.status_code == 204, f"marking the copy deleted failed ({r.status_code}): {str(r.content[:160])}"
        assert getattr(model.objects.get(pk=pk), flag) == gone, "the record was not marked deleted"
        entries = history(client, entity, pk)
        assert entries[-1]["action"] == "update" and any(c["field"] == flag for c in entries[-1]["changes"]), "the deletion was not logged as an edit with its fields"
        ok, res = fire(client, entries[-1]["id"], "before")
        assert ok, f"un-deleting from the history failed: {res}"
        assert getattr(model.objects.get(pk=pk), flag) != gone, "the record is still marked deleted"
        p = client.post(f"/api/admin/audit/{entries[0]['id']}/revert/preview/", {"mode": "before"}, format="json").json()
        assert not p["allowed"] and "never removes records" in (p.get("reason") or ""), f"undoing a creation was not refused: {p}"
        return
    r = client.delete(f"{url}{pk}/")
    if r.status_code == 405:
        # A page that never deletes: restoring versions works, but undoing the creation must be refused.
        p = client.post(f"/api/admin/audit/{entries[0]['id']}/revert/preview/", {"mode": "before"}, format="json").json()
        assert not p["allowed"] and "doesn't allow records to be deleted" in (p.get("reason") or ""), f"undoing a creation on a no-delete page was not refused: {p}"
        return
    if r.status_code != 204:
        raise Manual(f"the copy could not be deleted ({r.status_code})")
    entries = history(client, entity, pk)
    assert entries[-1]["action"] == "delete" and entries[-1]["changes"], "the delete was not logged with the row"
    ok, res = fire(client, entries[-1]["id"], "before")
    assert ok, f"restoring the deleted record failed: {res}"
    back = model.objects.filter(pk=pk).first()
    assert back is not None and same(getattr(back, edit_field), uniq(2)), "the deleted record did not come back as it was"

    ok, res = fire(client, entries[0]["id"], "before")
    assert ok, f"undoing the creation failed: {res}"
    assert not model.objects.filter(pk=pk).exists(), "the record is still there after undoing its creation"


def find_viewset(name):
    for classes in ar.viewsets_by_entity().values():
        for cls in classes:
            if cls.__name__ == name:
                return cls
    raise Manual(f"no viewset named {name}")


def copy_record(client, cls, sample, overrides, unique_text=None):
    """POST a copy of `sample` through the page, with `overrides` applied. Fields a refusal names get a
    value of their own and the copy is tried again. Returns the created record's JSON."""
    model = cls.queryset.model
    url = base_urls()[cls]
    pk_name = model._meta.pk.name
    detail = client.get(f"{url}{sample.pk}/")
    if detail.status_code != 200:
        raise Manual(f"cannot read a record of {cls.__name__} ({detail.status_code})")
    payload = {k: v for k, v in detail.json().items() if k != pk_name and k not in READ_ONLY_KEYS}
    for f in model._meta.fields:
        if f.get_internal_type() == "DateField" and isinstance(payload.get(f.name), str):
            payload[f.name] = payload[f.name][:10]
    payload.update(overrides)
    r = client.post(url, payload, format="json")
    for attempt in range(8):
        if r.status_code != 400:
            break
        changed = False
        for name in culprit_fields(r.json()):
            if name in overrides or name not in payload:
                continue
            mfield = next((f for f in model._meta.fields if f.name == name), None)
            value = payload[name]
            if mfield is not None and mfield.many_to_one:
                others = list(mfield.related_model._default_manager.exclude(pk=value).values_list("pk", flat=True)[: attempt + 1])
                if len(others) > attempt:
                    payload[name] = others[attempt]
                    changed = True
                continue
            if mfield is not None and mfield.get_internal_type() == "DateField":
                payload[name] = f"2001-01-{attempt + 1:02d}"
                changed = True
            elif isinstance(value, str):
                lim = getattr(mfield, "max_length", None) or 40
                payload[name] = f"Z{os.getpid() % 100}{attempt}"[:lim]
                changed = True
            elif isinstance(value, int) and not isinstance(value, bool):
                payload[name] = 900000 + os.getpid() % 1000 + attempt
                changed = True
        if not changed:
            break
        r = client.post(url, payload, format="json")
    if r.status_code != 201:
        raise Manual(f"a copy through {cls.__name__} was refused ({r.status_code}): {str(r.content[:200])}")
    return r.json()


def make_pair(client, entity):
    """A header and one line under it, created through the pages (copies of existing ones)."""
    hdr_name, child_name, fk, hdr_edit, child_extra = CHILD_PAIRS[entity]
    hdr_cls, child_cls = find_viewset(hdr_name), find_viewset(child_name)
    hmodel, cmodel = hdr_cls.queryset.model, child_cls.queryset.model
    fk_attname = cmodel._meta.get_field(fk).attname
    candidates = list(cmodel.objects.order_by(cmodel._meta.pk.name)[:40])
    if not candidates:
        raise Manual("no existing line to copy")

    if isinstance(hdr_edit, dict):
        hdr_overrides = hdr_edit
    else:
        hdr_overrides = {hdr_edit: f"ZZ{os.getpid() % 1000}"[: getattr(hmodel._meta.get_field(hdr_edit), "max_length", None) or 40]}
    # Some existing lines cannot be copied (the person is no longer active on that rig, ...). Try the next one.
    last_problem = None
    for sample_child in candidates:
        sample_header = hmodel.objects.get(pk=getattr(sample_child, fk_attname))
        sid = transaction.savepoint()
        try:
            extra = child_extra if isinstance(child_extra, dict) else {}
            header_over = dict(hdr_overrides)
            if child_extra == "active_on_rig":
                # a trainee has to be active on the log's rig: put the log on a rig where someone is
                from core.models import FsEmpCurStatus

                status = FsEmpCurStatus.objects.filter(fs_emp_active="Y", rig_id__isnull=False).first()
                if status is None:
                    raise Manual("nobody is active on any rig to add as a trainee")
                header_over["rig"] = status.rig_id
                extra = {"fs_emp": status.fs_emp_id}
            h = copy_record(client, hdr_cls, sample_header, header_over)
            hpk = h[hmodel._meta.pk.name]
            c = copy_record(client, child_cls, sample_child, {fk: hpk, **extra})
            transaction.savepoint_commit(sid)
            break
        except Manual as exc:
            transaction.savepoint_rollback(sid)
            last_problem = exc
    else:
        raise last_problem
    cpk = c[cmodel._meta.pk.name]
    return dict(hdr_cls=hdr_cls, child_cls=child_cls, hmodel=hmodel, cmodel=cmodel, hpk=hpk, cpk=cpk, fk=fk)


def exercise_children(client, entity):
    pair = make_pair(client, entity)
    hdr_cls, child_cls, hmodel, cmodel = pair["hdr_cls"], pair["child_cls"], pair["hmodel"], pair["cmodel"]
    hpk, cpk, fk = pair["hpk"], pair["cpk"], pair["fk"]
    assert cmodel.objects.filter(pk=cpk).exists(), "the line was not created"
    htable, ctable = hmodel._meta.db_table, cmodel._meta.db_table

    def fire_h(entry_id, mode):
        return fire(client, entry_id, mode)

    hist = lambda: [e for e in history_t(client, entity, hpk, htable)]
    entries = hist()
    assert [e["action"] for e in entries] == ["create"], f"history of the header is {[e['action'] for e in entries]}"
    create_id = entries[0]["id"]

    # delete the header: its line goes with it, and both are logged
    r = client.delete(f"{base_urls()[hdr_cls]}{hpk}/")
    if r.status_code != 204:
        raise Manual(f"the header copy could not be deleted ({r.status_code}): {str(r.content[:160])}")
    assert not cmodel.objects.filter(pk=cpk).exists(), "the line is still there after deleting its header"
    entries = hist()
    last = entries[-1]
    assert last["action"] == "delete", f"history is {[e['action'] for e in entries]}"
    p = client.post(f"/api/admin/audit/{last['id']}/revert/preview/", {"mode": "before"}, format="json").json()
    assert p["allowed"] and p["action"] == "insert", f"restoring the deleted header was refused: {p}"
    assert p.get("child_summary") and p["child_summary"][0]["count"] == 1, f"the preview does not mention the line: {p.get('child_summary')}"
    assert not hmodel.objects.filter(pk=hpk).exists(), "the preview changed something"
    ok, res = fire_h(last["id"], "before")
    assert ok, f"restoring the header with its line failed: {res}"
    assert hmodel.objects.filter(pk=hpk).exists() and cmodel.objects.filter(pk=cpk).exists(), "the header and its line did not both come back"

    # undo the creation: the line goes too, and everything can be put back again
    p = client.post(f"/api/admin/audit/{create_id}/revert/preview/", {"mode": "before"}, format="json").json()
    assert p["allowed"] and p["action"] == "delete", f"undoing the creation was refused: {p}"
    assert p.get("child_summary"), "the preview does not say the line goes too"
    ok, res = fire_h(create_id, "before")
    assert ok, f"undoing the creation failed: {res}"
    assert not hmodel.objects.filter(pk=hpk).exists() and not cmodel.objects.filter(pk=cpk).exists(), "header and line should both be gone"
    entries = hist()
    assert entries[-1]["action"] == "revert_delete", f"history is {[e['action'] for e in entries]}"
    ok, res = fire_h(entries[-1]["id"], "before")
    assert ok, f"putting the undone creation back failed: {res}"
    assert hmodel.objects.filter(pk=hpk).exists() and cmodel.objects.filter(pk=cpk).exists(), "the header and its line did not both come back"


def exercise_auto_lines(client, entity):
    hdr_name, overrides = AUTO_LINES[entity]
    hdr_cls = find_viewset(hdr_name)
    hmodel = hdr_cls.queryset.model
    url = base_urls()[hdr_cls]
    sample = hmodel.objects.order_by(hmodel._meta.pk.name).first()
    if sample is None:
        raise Manual("no existing report to copy")
    h = copy_record(client, hdr_cls, sample, overrides)
    hpk = h[hmodel._meta.pk.name]
    htable = hmodel._meta.db_table
    child_rel = next(r for r in hmodel._meta.related_objects if r.on_delete.__name__ == "CASCADE")
    cmodel, cfield = child_rel.related_model, child_rel.field.name
    lines = cmodel.objects.filter(**{cfield: hpk}).count()
    assert lines > 0, "the page created no detail rows for the copy"

    hist = lambda: history_t(client, entity, hpk, htable)
    create_id = hist()[0]["id"]
    r = client.delete(f"{url}{hpk}/")
    assert r.status_code == 204, f"deleting the copy failed ({r.status_code}): {str(r.content[:160])}"
    assert cmodel.objects.filter(**{cfield: hpk}).count() == 0, "the detail rows are still there"
    last = hist()[-1]
    assert last["action"] == "delete"
    p = client.post(f"/api/admin/audit/{last['id']}/revert/preview/", {"mode": "before"}, format="json").json()
    assert p["allowed"] and p.get("child_summary") and p["child_summary"][0]["count"] == lines, f"the preview does not list the {lines} detail rows: {p}"
    ok, res = fire(client, last["id"], "before")
    assert ok, f"restoring the report failed: {res}"
    assert cmodel.objects.filter(**{cfield: hpk}).count() == lines, "not all detail rows came back"

    ok, res = fire(client, create_id, "before")
    assert ok, f"undoing the creation failed: {res}"
    assert not hmodel.objects.filter(pk=hpk).exists() and cmodel.objects.filter(**{cfield: hpk}).count() == 0
    ok, res = fire(client, hist()[-1]["id"], "before")
    assert ok, f"putting the undone creation back failed: {res}"
    assert cmodel.objects.filter(**{cfield: hpk}).count() == lines, "not all detail rows came back after the undo"


def exercise_drilling_report(client, entity):
    """A daily drilling report: copy one (with its time log) onto a free date, edit it, restore versions,
    delete and restore it with its time log, undo and redo the creation, and a recorded approval blocks
    going back past it. The well's running totals must match its reports at every step."""
    import datetime

    from django.db.models import Sum

    from core.models import DrillingDtl, DrillingDtlOps, DrillingHdr, SysAuditLog

    cls = find_viewset("DrillingDtlViewSet")
    url = base_urls()[cls]
    sample = None
    for cand in DrillingDtl.objects.filter(ops__isnull=False, cr_status__isnull=True).distinct().order_by("-drilling_dtl_dt")[:30]:
        free = None
        for back in range(1, 90):
            day = cand.drilling_dtl_dt - datetime.timedelta(days=back)
            if not DrillingDtl.objects.filter(rig_id=cand.rig_id, drilling_dtl_dt=day).exists():
                free = day
                break
        if free is not None:
            sample, free_day = cand, free
            break
    if sample is None:
        raise Manual("no draft report with a time log and a free date to copy it onto")

    detail = client.get(f"{url}{sample.pk}/").json()
    delta = free_day - sample.drilling_dtl_dt
    payload = {k: v for k, v in detail.items() if k not in ("drilling_dtl_id", "cr_user_id", "cr_dt", "mod_user_id", "mod_dt", "drilling_hdr")}
    payload["drilling_dtl_dt"] = free_day.isoformat()
    ops = []
    for o in detail["ops"]:
        o = {k: v for k, v in o.items() if k != "drilling_dtl_ops_id"}
        for key in ("time_from", "time_to"):
            o[key] = (datetime.datetime.fromisoformat(o[key]) + delta).isoformat()
        ops.append(o)
    payload["ops"] = ops
    r = client.post(url, payload, format="json")
    if r.status_code != 201:
        raise Manual(f"a copy of a report was refused ({r.status_code}): {str(r.content[:240])}")
    pk = r.json()["drilling_dtl_id"]
    hdr_id = DrillingDtl.objects.get(pk=pk).drilling_hdr_id
    n_ops = DrillingDtlOps.objects.filter(drilling_dtl_id=pk).count()
    assert n_ops == len(ops) and n_ops > 0, f"the copy has {n_ops} time log rows, expected {len(ops)}"

    def consistent(step):
        if not hdr_id:
            return
        want = DrillingDtl.objects.filter(drilling_hdr_id=hdr_id).aggregate(t=Sum("consumption_diesel"))["t"] or 0
        have = DrillingHdr.objects.get(pk=hdr_id).tot_consumption_diesel or 0
        assert want == have, f"after {step} the well's diesel total is {have}, its reports add up to {want}"

    consistent("creating the copy")
    table = DrillingDtl._meta.db_table
    entries = history_t(client, entity, pk, table)
    assert [e["action"] for e in entries] == ["create"], f"history is {[e['action'] for e in entries]}"
    create_id = entries[0]["id"]

    for v in (111, 222):
        r = client.patch(f"{url}{pk}/", {"consumption_diesel": v}, format="json")
        if r.status_code != 200:
            raise Manual(f"a field of the report could not be edited ({r.status_code}): {str(r.content[:160])}")
    consistent("two edits")
    entries = history_t(client, entity, pk, table)
    assert [e["action"] for e in entries] == ["create", "update", "update"], f"history is {[e['action'] for e in entries]}"
    ok, res = fire(client, entries[1]["id"], "after")
    assert ok, f"restoring version 2 failed: {res}"
    assert DrillingDtl.objects.get(pk=pk).consumption_diesel == 111, "the diesel figure was not restored"
    consistent("restoring version 2")

    # the time log counts as an edit that cannot be restored automatically: it is refused, nothing changes
    rows = [e for e in entries]
    before_delete = DrillingDtl.objects.get(pk=pk)
    kept = (before_delete.downtime_reason, before_delete.operating_hrs, before_delete.drilling_meterage)
    r = client.delete(f"{url}{pk}/")
    assert r.status_code == 204, f"deleting the copy failed ({r.status_code}): {str(r.content[:160])}"
    consistent("deleting the copy")
    assert DrillingDtlOps.objects.filter(drilling_dtl_id=pk).count() == 0
    last = history_t(client, entity, pk, table)[-1]
    assert last["action"] == "delete"
    # an older version of a deleted report cannot be mixed with the time log it had when it was deleted
    older = next(e for e in history_t(client, entity, pk, table) if e["action"] == "update")
    p = client.post(f"/api/admin/audit/{older['id']}/revert/preview/", {"mode": "after"}, format="json").json()
    assert not p["allowed"] and "only available as they were when it was deleted" in (p.get("reason") or ""), f"restoring an older version of a deleted report was not refused: {p}"
    p = client.post(f"/api/admin/audit/{last['id']}/revert/preview/", {"mode": "before"}, format="json").json()
    assert p["allowed"] and p.get("child_summary") and p["child_summary"][0]["count"] == n_ops, f"the preview does not list the {n_ops} time log rows: {p}"
    ok, res = fire(client, last["id"], "before")
    assert ok, f"restoring the deleted report failed: {res}"
    assert DrillingDtlOps.objects.filter(drilling_dtl_id=pk).count() == n_ops, "the time log did not come back in full"
    consistent("restoring the deleted report")
    after_restore = DrillingDtl.objects.get(pk=pk)
    assert (after_restore.downtime_reason, after_restore.operating_hrs, after_restore.drilling_meterage) == kept, (
        f"the report's downtime reason and hour totals changed by the restore: {kept} -> "
        f"{(after_restore.downtime_reason, after_restore.operating_hrs, after_restore.drilling_meterage)}"
    )

    ok, res = fire(client, create_id, "before")
    assert ok, f"undoing the creation failed: {res}"
    assert not DrillingDtl.objects.filter(pk=pk).exists() and DrillingDtlOps.objects.filter(drilling_dtl_id=pk).count() == 0
    consistent("undoing the creation")
    ok, res = fire(client, history_t(client, entity, pk, table)[-1]["id"], "before")
    assert ok, f"putting the undone creation back failed: {res}"
    consistent("redoing the creation")
    assert DrillingDtlOps.objects.filter(drilling_dtl_id=pk).count() == n_ops

    # an approval recorded after a version blocks going back to it
    SysAuditLog.objects.create(username="zz_approver", action="finalize", entity=entity, record_id=str(pk), target_table=table, target_pk=str(pk))
    first_edit = history_t(client, entity, pk, table)
    target_entry = next(e for e in first_edit if e["action"] == "update")
    p = client.post(f"/api/admin/audit/{target_entry['id']}/revert/preview/", {"mode": "before"}, format="json").json()
    assert not p["allowed"] and "finalized" in (p.get("reason") or ""), f"going back past a finalize was not refused: {p}"


def history_t(client, entity, pk, table):
    r = client.get("/api/admin/audit/history/", {"entity": entity, "record_id": pk, "table": table})
    return r.json()["entries"] if r.status_code == 200 else []


def exercise_edit_only(client, entity, url, model, sample, edit_field, values):
    # A record whose current value is one the page itself accepts (older data can hold blanks the page
    # would refuse, and a restore to those is rightly refused).
    qs = model.objects.exclude(**{f"{edit_field}__isnull": True})
    if model._meta.get_field(edit_field).get_internal_type() == "CharField":
        qs = qs.exclude(**{edit_field: ""})
    good = qs.order_by(model._meta.pk.name).first()
    sample = good or sample
    pk = sample.pk
    original = getattr(sample, edit_field)
    for v in values[1:3]:
        r = client.patch(f"{url}{pk}/", {edit_field: v}, format="json")
        if r.status_code != 200 or not same(r.json().get(edit_field), v):
            raise Manual(f"the field could not be edited through the page ({r.status_code}): {str(r.content[:140])}")
    entries = history(client, entity, pk)
    assert [e["action"] for e in entries][-2:] == ["update", "update"], f"history is {[e['action'] for e in entries]}"
    first = entries[-2]["id"]
    ok, res = fire(client, first, "before")
    assert ok, f"restoring the original version failed: {res}"
    assert same(getattr(model.objects.get(pk=pk), edit_field), original), "the original value was not restored"
    ok, res = fire(client, first, "after")
    assert ok, f"restoring version 2 failed: {res}"
    assert same(getattr(model.objects.get(pk=pk), edit_field), values[1]), "version 2 was not restored"


def exercise_activity_monitor(client, entity):
    """Activity Monitor: create, change the schedule (twice), restore versions, and the rules of the page: a
    completed activity is final (cannot be reverted), only one open record per activity and rig, and there
    is no delete so a creation cannot be undone."""
    import datetime

    from core.models import ActivityMonitor, MstActivity

    url = "/api/qhse/activity-monitor/"
    from core.models import MstRig

    act = rig_id = None
    for a in MstActivity.objects.order_by("pk"):
        if a.activity_location in ("V", "R"):
            for rig in MstRig.objects.order_by("pk"):
                if not ActivityMonitor.objects.filter(activity=a, rig=rig, completion_dt__isnull=True).exists():
                    act, rig_id = a, rig.pk
                    break
        elif not ActivityMonitor.objects.filter(activity=a, completion_dt__isnull=True).exists():
            act = a
        if act:
            break
    if act is None:
        raise Manual("every activity already has an open record on every rig")
    today = datetime.date.today()
    r = client.post(url, {"activity": act.pk, "rig": rig_id, "scheduled_dt": today.isoformat(), "planning_remark": "ZZ plan"}, format="json")
    assert r.status_code == 201, f"creating a monitor record failed ({r.status_code}): {str(r.content[:200])}"
    pk = r.json()["id"] if "id" in r.json() else r.json()["activity_monitor_id"]
    table = ActivityMonitor._meta.db_table

    entries = history_t(client, entity, pk, table)
    assert [e["action"] for e in entries] == ["create"] and entries[0]["changes"], f"the creation is not logged with its values: {entries}"
    d1, d2 = today + datetime.timedelta(days=10), today + datetime.timedelta(days=20)
    for d in (d1, d2):
        r = client.patch(f"{url}{pk}/", {"scheduled_dt": d.isoformat(), "planning_remark": f"ZZ moved to {d}"}, format="json")
        assert r.status_code == 200, f"changing the schedule failed ({r.status_code}): {str(r.content[:200])}"
    entries = history_t(client, entity, pk, table)
    assert [e["action"] for e in entries] == ["create", "update", "update"], f"history is {[e['action'] for e in entries]}"
    assert any(c["field"] == "original_scheduled_dt" for c in entries[1]["changes"]), "the original schedule date change was not logged"
    ok, res = fire(client, entries[1]["id"], "after")
    assert ok, f"restoring the first change failed: {res}"
    assert ActivityMonitor.objects.get(pk=pk).scheduled_dt == d1, "the schedule date was not restored"
    p = client.post(f"/api/admin/audit/{entries[0]['id']}/revert/preview/", {"mode": "before"}, format="json").json()
    assert not p["allowed"] and "doesn't allow records to be deleted" in (p.get("reason") or ""), f"undoing a creation on a page with no delete was not refused: {p}"

    # a second open record for the same activity is not allowed, also not by restoring an older one
    ActivityMonitor.objects.filter(pk=pk).update(completion_dt=today, completion_remark="ZZ done")
    p = client.post(f"/api/admin/audit/{entries[1]['id']}/revert/preview/", {"mode": "before"}, format="json").json()
    assert not p["allowed"] and "completed activity can't be altered" in (p.get("reason") or ""), f"reverting a completed activity was not refused: {p}"


def exercise_cert_to_rank(client, entity):
    """Cert to Rank Mapping: add a rank, switch it off, restore, delete the row, put it back, undo and redo."""
    from core.models import CertToRankMapping, FsCatgToRankMapping, MstCert

    base = "/api/qhse/cert-to-rank-mapping/"
    table = CertToRankMapping._meta.db_table
    pick = None
    for cert in MstCert.objects.order_by("pk")[:60]:
        for m in FsCatgToRankMapping.objects.order_by("pk")[:400]:
            if not CertToRankMapping.objects.filter(cert=cert, fs_category_id=m.fs_category_id, rank_id=m.rank_id).exists():
                pick = (cert, m)
                break
        if pick:
            break
    if not pick:
        raise Manual("no certificate and rank left to map")
    cert, m = pick
    r = client.post(f"{base}save/", {"cert": cert.pk, "adds": [{"category": m.fs_category_id, "rank": m.rank_id, "active": "Y"}]}, format="json")
    assert r.status_code == 200, f"adding a rank failed ({r.status_code}): {str(r.content[:200])}"
    row = CertToRankMapping.objects.get(cert=cert, fs_category_id=m.fs_category_id, rank_id=m.rank_id)
    entries = history_t(client, entity, row.pk, table)
    assert [e["action"] for e in entries] == ["create"] and entries[0]["changes"], f"the new mapping is not logged with its values: {entries}"

    r = client.post(f"{base}save/", {"cert": cert.pk, "updates": [{"id": row.pk, "active": "N"}]}, format="json")
    assert r.status_code == 200, f"switching the rank off failed ({r.status_code}): {str(r.content[:200])}"
    entries = history_t(client, entity, row.pk, table)
    assert [e["action"] for e in entries] == ["create", "update"], f"history is {[e['action'] for e in entries]}"
    ok, res = fire(client, entries[0]["id"], "after")
    assert ok, f"restoring the original version failed: {res}"
    assert CertToRankMapping.objects.get(pk=row.pk).cert_to_rank_mapping_active == "Y", "the active flag was not restored"

    r = client.delete(f"{base}row/{row.pk}/")
    assert r.status_code == 204, f"deleting the row failed ({r.status_code})"
    last = history_t(client, entity, row.pk, table)[-1]
    assert last["action"] == "delete" and last["changes"], "the delete was not logged with the row"
    ok, res = fire(client, last["id"], "before")
    assert ok and CertToRankMapping.objects.filter(pk=row.pk).exists(), f"putting the deleted row back failed: {res}"
    ok, res = fire(client, entries[0]["id"], "before")
    assert ok and not CertToRankMapping.objects.filter(pk=row.pk).exists(), f"undoing the creation failed: {res}"
    ok, res = fire(client, history_t(client, entity, row.pk, table)[-1]["id"], "before")
    assert ok and CertToRankMapping.objects.filter(pk=row.pk).exists(), f"putting the undone creation back failed: {res}"


# Pages that are not built on the shared master page: each has a check of its own.
OWN_CHECKS = {
    "qhse.activity_monitor": exercise_activity_monitor,
    "qhse.cert_to_rank_mapping": exercise_cert_to_rank,
}


def extra_holders_reassign(client, entity):
    """A reassignment ends the ongoing holder and starts a new one. Restoring the ended one while the new one
    is ongoing must be refused (two ongoing holders), and undoing the new holder must re-open the old one."""
    import datetime

    from core.models import ItAssetHolder, MstItAsset

    cls = find_viewset("ItAssetHolderViewSet")
    url = base_urls()[cls]
    h1 = ItAssetHolder.objects.filter(it_asset_holder_to__isnull=True).exclude(it_asset__it_asset_allocated="N").order_by("pk").first()
    if h1 is None:
        raise Manual("no ongoing holder to reassign")
    asset_id = h1.it_asset_id
    detail = client.get(f"{url}{h1.pk}/").json()
    payload = {k: v for k, v in detail.items() if k not in ("it_asset_holder_id", "mod_user_id", "mod_dt", "it_asset_holder_to")}
    payload["it_asset_holder_from"] = datetime.date.today().isoformat()
    payload["holder_remark"] = "ZZ reassigned"
    r = client.post(f"{url}reassign/", payload, format="json")
    if r.status_code != 201:
        raise Manual(f"the reassignment was refused ({r.status_code}): {str(r.content[:200])}")
    h2 = r.json()["it_asset_holder_id"]
    assert ItAssetHolder.objects.get(pk=h1.pk).it_asset_holder_to is not None, "the old holder was not ended"
    table = ItAssetHolder._meta.db_table

    old_hist = history_t(client, entity, h1.pk, table)
    closure = next(e for e in old_hist if e["action"] == "update")
    p = client.post(f"/api/admin/audit/{closure['id']}/revert/preview/", {"mode": "before"}, format="json").json()
    assert not p["allowed"] and "already has an ongoing holder" in (p.get("reason") or ""), f"re-opening the old holder next to the new one was not refused: {p}"

    new_hist = history_t(client, entity, h2, table)
    create = new_hist[0]
    p = client.post(f"/api/admin/audit/{create['id']}/revert/preview/", {"mode": "before"}, format="json").json()
    assert p["allowed"] and p.get("also"), f"undoing the new holder does not say it re-opens the old one: {p}"
    ok, res = fire(client, create["id"], "before")
    assert ok, f"undoing the reassignment failed: {res}"
    assert not ItAssetHolder.objects.filter(pk=h2).exists(), "the new holder is still there"
    assert ItAssetHolder.objects.get(pk=h1.pk).it_asset_holder_to is None, "the old holder was not re-opened"
    assert MstItAsset.objects.get(pk=asset_id).it_asset_allocated == "Y", "the asset is not marked allocated again"


def extra_training_leaver(client, entity):
    """Putting a training log back is not judged by today's state: a trainee who has left the rig and a
    certificate that has since expired must not stop the log (and everyone else on it) coming back."""
    import datetime

    from core.models import FsEmpCurStatus

    pair = make_pair(client, entity)
    hmodel, cmodel, hpk, cpk = pair["hmodel"], pair["cmodel"], pair["hpk"], pair["cpk"]
    emp = cmodel.objects.get(pk=cpk).fs_emp_id
    FsEmpCurStatus.objects.filter(fs_emp_id=emp).update(fs_emp_active="N")
    cmodel.objects.filter(pk=cpk).update(cert_valid_upto=datetime.date(2001, 1, 1))
    r = client.delete(f"{base_urls()[pair['hdr_cls']]}{hpk}/")
    assert r.status_code == 204, f"deleting the training log failed ({r.status_code}): {str(r.content[:160])}"
    last = history_t(client, entity, hpk, hmodel._meta.db_table)[-1]
    p = client.post(f"/api/admin/audit/{last['id']}/revert/preview/", {"mode": "before"}, format="json").json()
    assert p["allowed"], f"a leaver or an expired certificate blocked putting the training log back: {p}"
    ok, res = fire(client, last["id"], "before")
    assert ok and hmodel.objects.filter(pk=hpk).exists() and cmodel.objects.filter(pk=cpk).exists(), f"the log did not come back: {res}"


def extra_indicator_grid(client, entity):
    """The body of these pages is a grid saved through "save details". Each changed cell has to have its own
    history (before and after) and be restorable like any other field."""
    hdr_name, overrides = AUTO_LINES[entity]
    hdr_cls = find_viewset(hdr_name)
    hmodel = hdr_cls.queryset.model
    url = base_urls()[hdr_cls]
    sample = hmodel.objects.order_by(hmodel._meta.pk.name).first()
    if sample is None:
        raise Manual("no existing report to copy")
    # another month than the basic cycle used, which leaves its own copy behind inside this transaction
    h = copy_record(client, hdr_cls, sample, {**overrides, "period_month": "2001-02"})
    hpk = h[hmodel._meta.pk.name]
    child_rel = next(r for r in hmodel._meta.related_objects if r.on_delete.__name__ == "CASCADE")
    cmodel = child_rel.related_model
    ctable = cmodel._meta.db_table

    rows = client.get(f"{url}{hpk}/details/").json()
    if not rows:
        raise Manual("the copy has no grid rows")
    row = rows[0]
    field = next((k for k in ("total_sessions", "total_count") if k in row), None)
    if field is None:
        raise Manual(f"no count column found in the grid row: {sorted(row)}")
    original = int(row[field])

    def save(value):
        r = client.post(f"{url}{hpk}/save-details/", {"rows": [{**row, field: value}]}, format="json")
        assert r.status_code == 200, f"saving the grid failed ({r.status_code}): {str(r.content[:200])}"

    save(original + 1)
    save(original + 2)
    entries = history_t(client, entity, row["id"], ctable)
    assert [e["action"] for e in entries] == ["update", "update"], f"the grid cell's history is {[e['action'] for e in entries]}"
    assert any(c["field"] == field and str(c["old"]) == str(original) and str(c["new"]) == str(original + 1) for c in entries[0]["changes"]), f"the first save is not shown as before and after: {entries[0]['changes']}"
    assert [e["action"] for e in history_t(client, entity, hpk, hmodel._meta.db_table)] == ["create"], "the grid saves were also written onto the report's own history"
    ok, res = fire(client, entries[0]["id"], "after")
    assert ok, f"restoring the first saved value failed: {res}"
    assert getattr(cmodel.objects.get(pk=row["id"]), field) == original + 1, "the grid cell was not restored"
    ok, res = fire(client, entries[0]["id"], "before")
    assert ok, f"restoring the original value failed: {res}"
    assert getattr(cmodel.objects.get(pk=row["id"]), field) == original, "the original grid value was not restored"


# Checks added on top of a page's basic cycle.
EXTRAS = {
    "qhse.leading_indicators": extra_indicator_grid,
    "qhse.lagging_indicators": extra_indicator_grid,
    "it_asset.it_asset_holders": extra_holders_reassign,
    "qhse.training_log": extra_training_leaver,
}


def run_pages(keys, client):
    """Exercise each page and yield (status, key, detail): "ok", "warn" (needs a person) or "fail". Every
    page runs in a transaction that is rolled back, so nothing is saved."""
    for key in keys:
        try:
            with transaction.atomic():
                try:
                    exercise(client, key)
                finally:
                    transaction.set_rollback(True)
                    ar.invalidate_enabled()
            yield "ok", key, ""
        except Manual as exc:
            yield "warn", key, str(exc)
        except AssertionError as exc:
            yield "fail", key, str(exc)
        except Exception as exc:  # noqa: BLE001 - report it and carry on with the next page
            yield "fail", key, f"{type(exc).__name__}: {exc}"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    enabled_only = "--enabled" in sys.argv
    if args:
        keys = args
    elif enabled_only:
        keys = list(ar.REVERTIBLE_ENTITIES)
    else:
        keys = candidates()

    client = APIClient(HTTP_HOST=HOST, HTTP_X_AUDIT_SOURCE="script")
    client.force_authenticate(get_user_model().objects.filter(is_superuser=True).first())

    passed, manual, failed = [], [], []
    for status, key, detail in run_pages(keys, client):
        if status == "ok":
            passed.append(key)
            print(f"  ok      {key}")
        elif status == "warn":
            manual.append((key, detail))
            print(f"  MANUAL  {key}: {detail}")
        else:
            failed.append((key, detail))
            print(f"  FAIL    {key}: {detail}")

    print()
    print(f"{len(passed)} passed, {len(manual)} need a person, {len(failed)} failed (of {len(keys)} pages)")
    if passed:
        print("PASSED: " + ", ".join(passed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
