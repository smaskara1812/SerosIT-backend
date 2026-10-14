"""Record history and revert.

Built on the audit log (SysAuditLog), which stores every create, update and delete of a record as
{field: {old, new}}. From those rows this module can

  * list the history of one record, and
  * restore the record to how it was before or after any entry of that history.

Rules (see documents/audit_history_revert_plan.md):
  * A revert never edits history. It writes a new entry (action "revert") that points at the entry it
    is based on, and that entry can itself be reverted.
  * Nothing is changed unless every check passes. Each refusal carries a plain-language reason.
  * Only entities listed in REVERTIBLE can be reverted. The list grows phase by phase; the tracker in
    the plan document says which pages are done.
  * App Admin only (enforced by the API layer).

How the target state is worked out. For each field touched by the entries after the chosen point, the
value to restore is the "new" of the last entry at or before that point that touched the field, or, if
none did, the "old" of the first entry after it. A delete entry touches every field, so a deleted row can
be rebuilt from it.
"""

from django.db import transaction
from django.db.models import ProtectedError, Q
from django.utils import timezone

from . import audit as _audit
from .models import SysAuditLog

# "revert" changes fields, "revert_delete" removes a row (undo of a creation), "revert_restore" puts a
# deleted row back. All three are written by this module.
HISTORY_ACTIONS = ("create", "update", "delete", "revert", "revert_delete", "revert_restore")
GONE_ACTIONS = ("delete", "revert_delete")
# Workflow steps. They change a record's meaning without being edits, so a record can't be reverted past
# one of them: once it has been approved, an older version is no longer a state it may return to.
BARRIER_ACTIONS = {
    "approve": "approved",
    "reject": "rejected",
    "finalize": "finalized",
    "revise_self": "revised",
    "revise_previous": "revised",
}
MAX_DEPENDENT_CHECKS = 60


class RevertRefused(Exception):
    """The revert cannot be done safely. str(exc) is the reason shown to the admin."""


# Pages switched on for history and revert, by menu key. The tracker in
# documents/audit_history_revert_plan.md says which pages are in which phase; a page is added here only
# after scripts/check_revert_masters.py passes for it.
REVERTIBLE_ENTITIES = [
    # Phase 1a pilot (checked on SQL Server too)
    "masters.departments",
    "masters.contractors",
    "masters.rig_types",
    # Phase 1b: · General
    "masters.rigs",
    "masters.cost_centres",
    "masters.cost_centre_types",
    "masters.operators",
    "masters.cert_institutes",
    "masters.email_notification_types",
    "masters.company_locations",
    "masters.organisational_grps",
    "masters.business_grps",
    "masters.companies",
    "masters.financial_years",
    "masters.buss_cert_issue_authorities",
    "masters.buss_cert_types",
    "masters.buss_certs",
    "masters.rig_subtypes",
    "masters.vessel_depts",
    "masters.relations",
    "masters.business_systems",
    # Phase 1b: · HR
    "masters.competency",
    "masters.fs_categories",
    "masters.ranks",
    # Phase 1b: · Certificate Classification
    "masters.cert_types",
    "masters.certs",
    "masters.qualifications",
    # Phase 1b: · Employment Classification
    "masters.emp_natures",
    "masters.emp_types",
    # Phase 1b: · Service Particulars
    "masters.serv_types",
    "masters.serv_subtypes",
    "masters.fs_catg_to_sstype",
    # Phase 1b: · Incident Classification
    "masters.incident_types",
    "masters.incident_subcauses",
    "masters.work_locations",
    "masters.incident_causes",
    # Phase 1b: · QHSE
    "masters.rig_operations",
    "masters.contact_exposure_types",
    "masters.parts_of_body",
    "masters.qhse_categories",
    "masters.hse_activities",
    "masters.hse_consumables",
    "masters.hazard_types",
    "masters.hse_manhours_parties",
    "masters.hse_meetings",
    "masters.hse_drills",
    # Phase 1b: · Regional Information
    "masters.continents",
    "masters.countries",
    "masters.country_states",
    "masters.locations",
    # Phase 1b: · Leave Masters
    "masters.leaving_reasons",
    "masters.leaving_reason_details",
    # Phase 1b: · Mail Alert Masters
    "masters.mail_alerts",
    "masters.mail_alert_to_users",
    "masters.mail_recipient_mappings",
    "masters.notification_triggers",
    # Phase 1b: · User Mapping Masters
    "masters.user_rig_mapping",
    "masters.user_category_mapping",
    "masters.doc_to_sign_mapping",
    "masters.interviewer_mapping",
    # Phase 1b: · General Mapping Masters
    "masters.cost_centre_to_company_mapping",
    "masters.rig_site_mapping",
    "masters.fs_catg_to_rank_mapping",
    # Phase 1b: · HR Mapping Masters
    "masters.fs_catg_to_rig_type_mapping",
    "masters.nationality_to_emp_type_mapping",
    "masters.crew_change_reliever_mapping",
    # Phase 1b: · Exception Masters
    "masters.rig_crew_exceptions",
    "masters.crew_schedule_exceptions",
    # Phase 1b: · Projects
    "masters.project_drilling_rates",
    # Phase 1b: · Drilling
    "masters.drilling_operations",
    "masters.drilling_sections",
    "masters.drilling_work_shift",
    "masters.drilling_rates",
    # Phase 1b: · IT Asset Masters
    "masters.it_asset_types",
    "masters.it_asset_subtypes",
    "masters.it_asset_mfgs",
    "masters.it_asset_models",
    "masters.vendor_types",
    "masters.vendors",
    # Phase 1b: IT Asset
    "masters.it_accessories",
    "it_asset.it_accessory_holders",
    # Phase 1b: Admin
    "masters.approval_codes",
    # Phase 1b: (other)
    "masters.workgroups",
]

_VIEWSETS = None


def viewsets_by_entity():
    """{menu key: [master viewset classes that serve it]}, found once by scanning the app's modules."""
    global _VIEWSETS
    if _VIEWSETS is None:
        import importlib
        import inspect
        import pkgutil

        import core

        from .masters_views import BaseMasterViewSet

        found = {}
        for mod in pkgutil.iter_modules(core.__path__):
            if mod.name in ("migrations", "management", "tests"):
                continue
            try:
                module = importlib.import_module(f"core.{mod.name}")
            except Exception:
                continue
            for _name, cls in inspect.getmembers(module, inspect.isclass):
                if cls.__module__ != module.__name__ or cls is BaseMasterViewSet or not issubclass(cls, BaseMasterViewSet):
                    continue
                key = getattr(cls, "entity_key", None)
                if key and getattr(getattr(cls, "queryset", None), "model", None) is not None:
                    found.setdefault(key, []).append(cls)
        _VIEWSETS = found
    return _VIEWSETS


def _revertible_models():
    out = {}
    for key in REVERTIBLE_ENTITIES:
        classes = viewsets_by_entity().get(key, [])
        if len(classes) != 1:
            raise RuntimeError(f"{key} is switched on for revert but is served by {len(classes)} viewsets; it must be exactly one.")
        out[key] = classes[0].queryset.model
    return out


def revertible_entities():
    return sorted(_revertible_models())


def _model_for(entity):
    model = _revertible_models().get(entity)
    if model is None:
        raise RevertRefused("Revert is not available for this page yet.")
    return model


def _pretty(name):
    return name.replace("_id", "").replace("_", " ").strip().capitalize() or name


def _same(a, b):
    """Equality that does not mind None versus an empty string (the log leaves empties out)."""
    if a in (None, "") and b in (None, ""):
        return True
    return a == b


def entries_for(entity, record_id):
    """Log entries for one record, oldest first. Covers entries written before the target columns
    existed by also matching on entity plus record_id."""
    model = _model_for(entity)
    pk = str(record_id)
    qs = SysAuditLog.objects.filter(action__in=HISTORY_ACTIONS).filter(
        Q(target_table=model._meta.db_table, target_pk=pk) | Q(target_table="", entity=entity, record_id=pk)
    )
    rows = list(qs.order_by("id"))
    # A "create" entry starts a new record. Ids can come round again (after a reload of the data, or on a
    # database that reuses them), and the log rows of the earlier record that had this id must not become
    # part of this one's history. A restore after a delete is not a create, so it stays in the same life.
    for i in range(len(rows) - 1, -1, -1):
        if rows[i].action == "create":
            return rows[i:]
    return rows


def history(entity, record_id):
    """The history of one record for display: each entry with its before/after, newest last."""
    model = _model_for(entity)
    rows = entries_for(entity, record_id)
    out = []
    for i, e in enumerate(rows):
        changes = e.changes or {}
        out.append(
            {
                "id": e.id,
                "ts": e.ts.strftime("%Y-%m-%d %H:%M:%S") if e.ts else "",
                "username": e.username,
                "action": e.action,
                "note": e.note,
                "reverted_of": e.reverted_of,
                "record_label": e.record_label,
                "is_latest": i == len(rows) - 1,
                "is_first": i == 0,
                "changes": [
                    {"field": k, "label": _pretty(k), "old": v.get("old"), "new": v.get("new")}
                    for k, v in changes.items()
                    if isinstance(v, dict) and k not in _audit.BOOKKEEPING_FIELDS
                ],
            }
        )
    exists = model.objects.filter(pk=record_id).exists()
    return {"entity": entity, "record_id": str(record_id), "exists": exists, "entries": out}


def _exists_after(entry):
    return entry.action not in GONE_ACTIONS


def _target_value(rows, cut, field):
    """Value of `field` at the point just after rows[cut] (cut = -1 means before the first entry)."""
    for e in reversed(rows[: cut + 1]):
        ch = (e.changes or {}).get(field)
        if isinstance(ch, dict):
            return ch.get("new"), True
    for e in rows[cut + 1 :]:
        ch = (e.changes or {}).get(field)
        if isinstance(ch, dict):
            return ch.get("old"), True
    return None, False


def _serializer_class(entity, model):
    """The page's own serializer, so a revert obeys the same rules as typing the values in by hand
    (uniqueness, required fields, allowed choices)."""
    for cls in viewsets_by_entity().get(entity, []):
        if cls.queryset.model is model:
            return cls.serializer_class
    return None


def _check_page_rules(request, entity, model, instance, values):
    """Run the restored values through the page's serializer. `instance` is the existing row for an
    update, None for a restore. Refuses with the page's own wording if a rule would be broken."""
    ser_cls = _serializer_class(entity, model)
    if ser_cls is None or not values:
        return
    ctx = {"request": request}
    probe = ser_cls(context=ctx)
    writable = {n for n, f in probe.fields.items() if not f.read_only}
    data = {k: v for k, v in values.items() if k in writable}
    if instance is None:
        ser = ser_cls(data=data, context=ctx)
    else:
        ser = ser_cls(instance=instance, data=data, partial=True, context=ctx)
    if not ser.is_valid():
        parts = []
        for field, msgs in ser.errors.items():
            msgs = msgs if isinstance(msgs, (list, tuple)) else [msgs]
            text = " ".join(str(m) for m in msgs)
            parts.append(text if field in ("non_field_errors", "__all__") else f"{_pretty(field)}: {text}")
        raise RevertRefused("Can't restore this because " + "; ".join(parts))


def _check_barriers(entity, model, pk, after_entry_id):
    """Refuse when an approval (or other workflow step) was recorded for this record after the version
    being restored."""
    pk = str(pk)
    hit = (
        SysAuditLog.objects.filter(action__in=BARRIER_ACTIONS, id__gt=after_entry_id)
        .filter(Q(target_table=model._meta.db_table, target_pk=pk) | Q(target_table="", entity=entity, record_id=pk))
        .order_by("id")
        .first()
    )
    if hit is not None:
        when = hit.ts.strftime("%d %b %Y %H:%M") if hit.ts else ""
        raise RevertRefused(
            f"This record was {BARRIER_ACTIONS[hit.action]} by {hit.username} on {when}, after the version you chose. "
            "A record can't be reverted past an approval or other workflow step."
        )


def _model_label(model):
    import re

    name = model.__name__
    if name.startswith("Mst") and len(name) > 3:
        name = name[3:]
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)


def _dependents_since(model, obj, since):
    """Records that point at `obj` and were created after `since`, as [{"label", "count"}]. They were
    entered while the newer values were in force and will now see the older ones. Best-effort: a model
    with no creation date cannot be counted this way and is left out; a failure never blocks a preview."""
    out = []
    checked = 0
    for rel in model._meta.related_objects:
        if rel.many_to_many or not getattr(rel, "field", None):
            continue
        related = rel.related_model
        names = {f.name for f in related._meta.fields}
        if "cr_dt" not in names:
            continue
        checked += 1
        if checked > MAX_DEPENDENT_CHECKS:
            break
        try:
            n = related._default_manager.filter(**{rel.field.name: obj}, cr_dt__gte=since).count()
        except Exception:
            continue
        if n:
            out.append({"label": _model_label(related), "count": n})
    return sorted(out, key=lambda x: -x["count"])


def _get_row(model, pk):
    """The current row, locked for the length of the transaction where the database supports it."""
    from django.db import connection

    qs = model.objects.filter(pk=pk)
    if connection.features.has_select_for_update:
        qs = qs.select_for_update()
    return qs.first()


def _plan(entry_id, mode, request=None):
    """Work out what restoring would do. Returns a dict; raises RevertRefused for hard stops."""
    if mode not in ("after", "before"):
        raise RevertRefused("Unknown revert mode.")
    try:
        entry = SysAuditLog.objects.get(pk=entry_id)
    except SysAuditLog.DoesNotExist:
        raise RevertRefused("That history entry no longer exists.")
    if entry.action not in HISTORY_ACTIONS:
        raise RevertRefused("This kind of entry can't be reverted.")
    entity = entry.entity
    model = _model_for(entity)
    pk = entry.target_pk or entry.record_id
    rows = entries_for(entity, pk)
    ids = [r.id for r in rows]
    if entry.id not in ids:
        raise RevertRefused("That entry doesn't belong to this record's history.")
    pos = ids.index(entry.id)
    cut = pos if mode == "after" else pos - 1

    # Did the record exist at the chosen point, and does the log say it exists now?
    if cut >= 0:
        exists_at_cut = _exists_after(rows[cut])
    else:
        exists_at_cut = rows[0].action != "create"
    exists_by_log = _exists_after(rows[-1])
    obj = _get_row(model, pk)
    exists_in_db = obj is not None
    label = rows[-1].record_label or f"{model.__name__} {pk}"
    if exists_by_log != exists_in_db:
        raise RevertRefused(
            "The record's current state doesn't match its history (it was "
            + ("deleted" if not exists_in_db else "created")
            + " outside the logged changes), so it can't be reverted safely."
        )

    later = rows[cut + 1 :]
    touched = []
    for e in later:
        for f in (e.changes or {}):
            if f not in touched and f not in _audit.BOOKKEEPING_FIELDS:
                touched.append(f)

    plan = {
        "entry_id": entry.id,
        "mode": mode,
        "entity": entity,
        "record_id": str(pk),
        "record_label": label,
        "action": "none",
        "fields": [],
        "warnings": [],
        "reason": None,
        "allowed": False,
    }
    cut_entry_id = rows[cut].id if cut >= 0 else 0

    if exists_at_cut and exists_in_db:
        current = _audit.snapshot(obj)
        for f in touched:
            if f not in current:
                continue
            want, _ = _target_value(rows, cut, f)
            # The current value must be what the log says the last edit left behind.
            expected = None
            for e in reversed(rows):
                ch = (e.changes or {}).get(f)
                if isinstance(ch, dict):
                    expected = ch.get("new")
                    break
            if not _same(current[f], expected):
                raise RevertRefused(
                    f"{_pretty(f)} was changed outside the logged edits (now '{current[f]}', the history expects "
                    f"'{expected}'), so it can't be reverted safely."
                )
            if not _same(current[f], want):
                plan["fields"].append({"field": f, "label": _pretty(f), "current": current[f], "restore_to": want})
        plan["action"] = "update"
        if not plan["fields"]:
            plan["reason"] = "The record is already in that state. Nothing to change."
            return plan, obj
        _check_barriers(entity, model, pk, cut_entry_id)
        _check_page_rules(request, entity, model, obj, {i["field"]: i["restore_to"] for i in plan["fields"]})
        # The change being undone is the first one after the chosen version.
        since = later[0].ts if later else None
        if since is not None:
            plan["warnings"] = _dependents_since(model, obj, since)
            plan["since"] = since.strftime("%Y-%m-%d %H:%M")
        plan["allowed"] = True
        return plan, obj

    if not exists_at_cut and exists_in_db:
        # Undoing a creation deletes the record. A page that never lets records be deleted (it can only
        # deactivate them) must not have them deleted through here either.
        view = viewsets_by_entity().get(entity, [None])[0]
        if view is not None and "delete" not in getattr(view, "http_method_names", ["delete"]):
            raise RevertRefused("This page doesn't allow records to be deleted, so a creation can't be undone. Deactivate it instead.")
        _check_barriers(entity, model, pk, cut_entry_id)
        plan["action"] = "delete"
        plan["allowed"] = True
        plan["fields"] = [
            {"field": f, "label": _pretty(f), "current": v, "restore_to": None} for f, v in _audit.snapshot(obj).items()
        ]
        return plan, obj

    if exists_at_cut and not exists_in_db:
        # Rebuild the row from the delete entry (it holds every field), then apply the chosen state.
        last = rows[-1]
        if last.action not in GONE_ACTIONS or not last.changes:
            raise RevertRefused("The deleted record's contents were not logged, so it can't be restored.")
        sibling_deletes = (
            SysAuditLog.objects.filter(batch_id=last.batch_id, action="delete").exclude(pk=last.pk).count()
            if last.batch_id
            else 0
        )
        if sibling_deletes:
            raise RevertRefused(
                "Deleting this record also deleted related rows. Restoring a record together with its related "
                "rows isn't supported yet."
            )
        state = {}
        for f in (last.changes or {}):
            val, found = _target_value(rows, cut, f)
            if found:
                state[f] = val
        _check_barriers(entity, model, pk, cut_entry_id)
        _check_page_rules(request, entity, model, None, state)
        plan["action"] = "insert"
        plan["state"] = state
        plan["fields"] = [{"field": f, "label": _pretty(f), "current": None, "restore_to": v} for f, v in state.items() if f not in _audit.BOOKKEEPING_FIELDS]
        plan["allowed"] = True
        return plan, None

    plan["reason"] = "The record doesn't exist in that state and doesn't exist now. Nothing to change."
    return plan, None


def _build_instance(model, pk, state):
    """A new model instance from a logged snapshot, ready for force_insert."""
    kwargs = {model._meta.pk.attname: model._meta.pk.to_python(pk)}
    for f in model._meta.fields:
        if f.primary_key or f.name not in state:
            continue
        kwargs[f.attname] = f.to_python(state[f.name])
    return model(**kwargs)


def _check_insertable(model, instance):
    """Refuse (with the clashing value named) when the row can't be put back."""
    from django.core.exceptions import ValidationError

    for f in model._meta.fields:
        if f.is_relation and f.many_to_one:
            val = getattr(instance, f.attname)
            if val is not None and not f.related_model._default_manager.filter(pk=val).exists():
                raise RevertRefused(
                    f"Can't restore: the linked {_pretty(f.name).lower()} (id {val}) no longer exists."
                )
    if model.objects.filter(pk=instance.pk).exists():
        raise RevertRefused(f"Can't restore: a record with id {instance.pk} already exists.")
    try:
        instance.validate_unique()
    except ValidationError as exc:
        names = []
        for field, msgs in exc.message_dict.items():
            if field == "__all__":
                names.append("; ".join(msgs))
                continue
            val = getattr(instance, model._meta.get_field(field).attname, "")
            other = model.objects.filter(**{model._meta.get_field(field).attname: val}).exclude(pk=instance.pk).first()
            who = f" (id {other.pk})" if other is not None else ""
            names.append(f"{_pretty(field)} '{val}' is now used by another record{who}")
        raise RevertRefused("Can't restore this record because " + "; ".join(names) + ".")


def preview(entry_id, mode="after", request=None):
    """What a revert would do, without doing it. Never raises: a refusal comes back as
    {"allowed": False, "reason": ...}."""
    try:
        with transaction.atomic():
            plan, obj = _plan(entry_id, mode, request)
            if plan["action"] == "insert" and plan["allowed"]:
                model = _model_for(plan["entity"])
                _check_insertable(model, _build_instance(model, plan["record_id"], plan["state"]))
            plan.pop("state", None)
            return plan
    except RevertRefused as exc:
        return {"allowed": False, "reason": str(exc), "action": "none", "fields": [], "entry_id": entry_id, "mode": mode}


def apply(request, entry_id, mode="after", reason=""):
    """Do the revert. Raises RevertRefused (nothing changed) or returns the plan plus the new entry id."""
    with transaction.atomic():
        plan, obj = _plan(entry_id, mode, request)
        if not plan["allowed"]:
            raise RevertRefused(plan["reason"] or "Nothing to revert.")
        model = _model_for(plan["entity"])
        uid, _username = _audit.current_user(request)
        now = timezone.now()
        pk = plan["record_id"]

        if plan["action"] == "update":
            changes = {}
            update_fields = []
            for item in plan["fields"]:
                f = model._meta.get_field(item["field"])
                setattr(obj, f.attname, f.to_python(item["restore_to"]) if item["restore_to"] is not None else None)
                update_fields.append(f.attname)
                changes[item["field"]] = {"old": item["current"], "new": item["restore_to"]}
            names = {f.name for f in model._meta.fields}
            if "mod_user_id" in names and uid is not None:
                obj.mod_user_id = uid
                update_fields.append("mod_user_id")
            if "mod_dt" in names:
                obj.mod_dt = now
                update_fields.append("mod_dt")
            obj.save(update_fields=update_fields)
            audit_action = "revert"
            target = obj
        elif plan["action"] == "delete":
            changes = _audit.as_delete_changes(_audit.snapshot(obj, full=True))
            try:
                obj.delete()
            except ProtectedError as exc:
                used = sorted({o.__class__.__name__ for o in exc.protected_objects})
                raise RevertRefused(
                    "Can't undo this creation because other records still use it (" + ", ".join(used) + ")."
                )
            audit_action = "revert_delete"
            target = (model._meta.db_table, pk)
        else:  # insert
            instance = _build_instance(model, pk, plan["state"])
            _check_insertable(model, instance)
            names = {f.name for f in model._meta.fields}
            if "mod_user_id" in names and uid is not None:
                instance.mod_user_id = uid
            if "mod_dt" in names:
                instance.mod_dt = now
            instance.save(force_insert=True)
            changes = {k: {"old": None, "new": v} for k, v in plan["state"].items() if k not in _audit.BOOKKEEPING_FIELDS}
            audit_action = "revert_restore"
            target = instance

        entry = _audit.record_action(
            request, audit_action, plan["entity"], pk, plan["record_label"], changes or None,
            target=target if isinstance(target, tuple) else (target._meta.db_table, str(target.pk)),
            reverted_of=plan["entry_id"], note=reason or "",
        )
        if entry is None:
            # The revert itself must always be on record; undo it if the log write failed.
            raise RevertRefused("The revert could not be recorded in the audit log, so it was not applied.")
        plan.pop("state", None)
        plan["new_entry_id"] = entry.id
        return plan
