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


def exercise(client, entity):
    """Returns None when the page passes; raises Manual or AssertionError otherwise."""
    if entity not in ar.REVERTIBLE_ENTITIES:
        ar.REVERTIBLE_ENTITIES.append(entity)  # switched on for this run only, so a page can be tried before it is added
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


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    enabled_only = "--enabled" in sys.argv
    if args:
        keys = args
    elif enabled_only:
        keys = list(ar.REVERTIBLE_ENTITIES)
    else:
        keys = candidates()

    client = APIClient(HTTP_HOST="localhost", HTTP_X_AUDIT_SOURCE="script")
    client.force_authenticate(get_user_model().objects.filter(is_superuser=True).first())

    passed, manual, failed = [], [], []
    for key in keys:
        try:
            with transaction.atomic():
                try:
                    exercise(client, key)
                finally:
                    transaction.set_rollback(True)
            passed.append(key)
            print(f"  ok      {key}")
        except Manual as exc:
            manual.append((key, str(exc)))
            print(f"  MANUAL  {key}: {exc}")
        except AssertionError as exc:
            failed.append((key, str(exc)))
            print(f"  FAIL    {key}: {exc}")
        except Exception as exc:  # noqa: BLE001 - report and carry on with the next page
            failed.append((key, f"{type(exc).__name__}: {exc}"))
            print(f"  FAIL    {key}: {type(exc).__name__}: {exc}")

    print()
    print(f"{len(passed)} passed, {len(manual)} need a person, {len(failed)} failed (of {len(keys)} pages)")
    if passed:
        print("PASSED: " + ", ".join(passed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
