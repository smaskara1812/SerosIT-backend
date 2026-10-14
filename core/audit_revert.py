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


class RevertRefused(Exception):
    """The revert cannot be done safely. str(exc) is the reason shown to the admin."""


def _revertible_models():
    # Imported here so the registry can name models without a circular import at module load.
    from . import models as m

    return {
        # Phase 1a pilot
        "masters.departments": m.MstDepartment,
        "masters.contractors": m.MstContractor,
        "masters.rig_types": m.MstRigType,
    }


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
    return list(qs.order_by("id"))


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
    import inspect

    from . import masters_views

    for _name, cls in inspect.getmembers(masters_views, inspect.isclass):
        if getattr(cls, "entity_key", None) == entity and getattr(getattr(cls, "queryset", None), "model", None) is model:
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
        "reason": None,
        "allowed": False,
    }

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
        _check_page_rules(request, entity, model, obj, {i["field"]: i["restore_to"] for i in plan["fields"]})
        plan["allowed"] = True
        return plan, obj

    if not exists_at_cut and exists_in_db:
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
