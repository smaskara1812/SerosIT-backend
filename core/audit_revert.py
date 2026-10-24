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
# A page's own rule about when a record may be deleted, applied when undoing a creation would delete one.
# Returns the reason it may not, or None.
UNDO_CREATE_GUARDS = {
    "qhse.corrective_actions": lambda obj: "A Closed record can't be deleted." if getattr(obj, "action_status", "") == "CL" else None,
}


def _forget_missing_file(instance):
    """A trainee's certificate file is removed from disk when its log is deleted. After the row is put back
    the path would point at nothing, so it is cleared rather than left dangling."""
    import os

    from django.conf import settings

    path = getattr(instance, "certificate_path", None)
    if path and not os.path.isfile(os.path.join(settings.MEDIA_ROOT, str(path).lstrip("/"))):
        instance.certificate_path = None
        instance.save(update_fields=["certificate_path"])


# Fixes applied to child rows that come back with a restored record, by table.
CHILD_AFTER_RESTORE = {
    "hse_training_log_dtl": _forget_missing_file,
}

# Pages that never remove a record: "delete" there only marks it deleted. Undoing a creation would
# remove the row for real, so it is refused on these.
NO_DELETE_ENTITIES = {"qhse.activity_monitor"}  # no delete exists on the page
SOFT_DELETE_ENTITIES = {"qhse.hazard_id_card", "qhse.incident_details", "qhse.incident_root_cause", "qhse.incident_actions"}


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
    # Phase 2a: single-table pages with custom save code
    "masters.travel_eligibility",
    "masters.indicator_types",
    "masters.indicator_subtypes",
    "masters.fs_emp_cur_status",
    # Phase 2b: header and detail lines (deleting the header deletes its lines; restoring it brings them back)
    "masters.job_descriptions",
    "masters.project_contract",
    "masters.fs_employees",
    "it_asset.it_assets",
    # Phase 2c: pages with side effects, handled by after-restore hooks
    "it_asset.it_asset_holders",
    "admin.approver_mapping",
    # Phase 3a: QHSE and drilling pages without custom save code
    "qhse.activities",
    "drilling.drilling_information",
    "qhse.rig_certificates",
    "qhse.rig_certificate_schedule",
    # Phase 3b: custom save code
    "qhse.hazard_id_card",
    "qhse.incident_details",
    "qhse.incident_root_cause",
    "qhse.incident_actions",
    # Phase 3c: header and lines, soft deletes and file attachments
    "qhse.leading_indicators",
    "qhse.lagging_indicators",
    "qhse.hse_weekly_drill",
    "qhse.training_group",
    "qhse.training_org",
    "qhse.training_log",
    "qhse.hse_drill_record",
    "qhse.corrective_actions",
    # Phase 3d: the daily drilling report (roll-ups, time log, approval steps)
    "drilling.drilling_report",
    # Phase 4: pages with their own save code
    "qhse.activity_monitor",
    "qhse.cert_to_rank_mapping",
]

_VIEWSETS = None


def viewsets_by_entity():
    """{menu key: [master viewset classes that serve it]}, found once by scanning the app's modules."""
    global _VIEWSETS
    if _VIEWSETS is None:
        import importlib
        import inspect

        from .masters_views import BaseMasterViewSet
        from .project_apps import project_modules

        found = {}
        for _label, module_name in project_modules():
            try:
                module = importlib.import_module(module_name)
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


# Record types that belong to a page but are edited inside its screen, with no page of their own (the cells
# of the leading and lagging indicator grids): {menu key: [model names]}.
EXTRA_RECORD_TYPES = {
    "qhse.leading_indicators": ["LeadingIndicatorsDtl"],
    "qhse.lagging_indicators": ["LaggingIndicatorsDtl"],
    # Pages that are not built on the shared master page at all: their record types are listed here.
    "qhse.activity_monitor": ["ActivityMonitor"],
    "qhse.cert_to_rank_mapping": ["CertToRankMapping"],
}


def _registry():
    """{db_table: (menu key, model)} for every record type of every page that is switched on. A page can
    serve more than one record type (Job Descriptions: sections and their lines)."""
    from django.apps import apps

    reg = {}
    for key in REVERTIBLE_ENTITIES:
        classes = viewsets_by_entity().get(key, [])
        if not classes and not EXTRA_RECORD_TYPES.get(key):
            raise RuntimeError(f"{key} is switched on for revert but no page serves it.")
        for cls in classes:
            model = cls.queryset.model
            reg.setdefault(model._meta.db_table, (key, model))
        for name in EXTRA_RECORD_TYPES.get(key, []):
            model = apps.get_model("core", name)
            reg.setdefault(model._meta.db_table, (key, model))
    return reg


_ENABLED_CACHE_KEY = "audit_history_enabled_pages"
_ENABLED_CACHE_SECONDS = 10


def enabled_entities():
    """Menu keys of the pages an App Admin has switched History and revert on for (Admin > History and
    Revert), among the pages the code supports. Read from the page's sys_menu row, so it is one setting
    for the whole system. Kept for a few seconds so a list of log rows does not ask the database for
    every row; changing a setting clears it straight away."""
    from django.core.cache import cache

    from .models import SysMenu

    keys = cache.get(_ENABLED_CACHE_KEY)
    if keys is None:
        keys = sorted(
            SysMenu.objects.filter(history_enabled=True, menu_key__in=REVERTIBLE_ENTITIES).values_list("menu_key", flat=True)
        )
        cache.set(_ENABLED_CACHE_KEY, keys, _ENABLED_CACHE_SECONDS)
    return set(keys)


def invalidate_enabled():
    from django.core.cache import cache

    cache.delete(_ENABLED_CACHE_KEY)


def supported_entities():
    """Pages the code can do History and revert for, whether or not an admin has switched them on."""
    return list(REVERTIBLE_ENTITIES)


def revertible_entities():
    """Pages where History and revert are available right now (supported and switched on)."""
    return sorted(enabled_entities())


def can_show_history(entity, table):
    """Whether a log row can offer History: its record type is on a page that is switched on."""
    reg = _registry()
    on = enabled_entities()
    if table:
        hit = reg.get(table)
        return hit is not None and hit[0] in on
    mine = [v for v in reg.values() if v[0] == entity]
    return len(mine) == 1 and entity in on


def _resolve(entity, table=""):
    """(menu key, model) for a log row or request. The table names the record type exactly; without one
    the page must have a single record type."""
    reg = _registry()
    if table:
        hit = reg.get(table)
        if hit is None:
            raise RevertRefused("Revert is not available for this page yet.")
        found = hit
    else:
        mine = [v for v in reg.values() if v[0] == entity]
        if not mine:
            raise RevertRefused("Revert is not available for this page yet.")
        if len(mine) > 1:
            raise RevertRefused("This page holds more than one kind of record, so the history needs to say which one.")
        found = mine[0]
    if found[0] not in enabled_entities():
        raise RevertRefused(
            "History and revert are switched off for this page. An App Admin can switch them on under "
            "Admin > History and Revert."
        )
    return found


def _model_by_table(table):
    """Any model of the app by its table, switched on or not (child rows of a restored record)."""
    from .project_apps import project_models

    for model in project_models():
        if model._meta.db_table == table:
            return model
    return None


def _viewset_for(entity, model):
    for cls in viewsets_by_entity().get(entity, []):
        if cls.queryset.model is model:
            return cls
    return None


def _pretty(name):
    return name.replace("_id", "").replace("_", " ").strip().capitalize() or name


def _same(a, b):
    """Equality that does not mind None versus an empty string (the log leaves empties out)."""
    if a in (None, "") and b in (None, ""):
        return True
    return a == b


def _entry_filter(entity, model, pk):
    """Which log rows belong to one record. Rows written before the target columns existed carry only
    the page and the record id, which identify a record only when the page has a single record type."""
    cond = Q(target_table=model._meta.db_table, target_pk=str(pk))
    if sum(1 for v in _registry().values() if v[0] == entity) == 1:
        cond |= Q(target_table="", entity=entity, record_id=str(pk))
    return cond


def entries_for(entity, model, record_id):
    """Log entries for one record, oldest first."""
    qs = SysAuditLog.objects.filter(action__in=HISTORY_ACTIONS).filter(_entry_filter(entity, model, record_id))
    rows = list(qs.order_by("id"))
    # A "create" entry starts a new record. Ids can come round again (after a reload of the data, or on a
    # database that reuses them), and the log rows of the earlier record that had this id must not become
    # part of this one's history. A restore after a delete is not a create, so it stays in the same life.
    for i in range(len(rows) - 1, -1, -1):
        if rows[i].action == "create":
            return rows[i:]
    return rows


def history(entity, record_id, table=""):
    """The history of one record for display: each entry with its before/after, newest last."""
    entity, model = _resolve(entity, table)
    rows = entries_for(entity, model, record_id)
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
    return {"entity": entity, "table": model._meta.db_table, "record_id": str(record_id), "exists": exists, "entries": out}


def _exists_after(entry):
    return entry.action not in GONE_ACTIONS


def _target_value(rows, cut, field):
    """Value of `field` at the point just after rows[cut] (cut = -1 means before the first entry)."""
    for e in reversed(rows[: cut + 1]):
        ch = (e.changes or {}).get(field)
        if isinstance(ch, dict):
            # A deletion's "new" is nothing; the value the row had (its "old") is what a later restore
            # puts back, and restores do not list the bookkeeping columns they bring back unchanged.
            return (ch.get("old") if e.action in GONE_ACTIONS else ch.get("new")), True
    for e in rows[cut + 1 :]:
        ch = (e.changes or {}).get(field)
        if isinstance(ch, dict):
            return ch.get("old"), True
    return None, False


def _serializer_class(entity, model):
    """The page's own serializer, so a revert obeys the same rules as typing the values in by hand
    (uniqueness, required fields, allowed choices). With no entity, any page serving the model will do."""
    entities = [entity] if entity else list(viewsets_by_entity())
    for key in entities:
        for cls in viewsets_by_entity().get(key, []):
            if cls.queryset.model is model:
                return cls.serializer_class
    return None


def _period_month_input(values):
    """Leading and lagging reports take the period as 'YYYY-MM' in a field of the form, but keep it as a
    date; give the page's rules the form it expects."""
    out = dict(values)
    if out.get("period") and not out.get("period_month"):
        out["period_month"] = str(out["period"])[:7]
    return out


def _drill_year_input(values):
    """HSE Weekly Drill takes the year as a number in the form but stores it as the 1 Jan date."""
    out = dict(values)
    if out.get("drill_year") and not out.get("year"):
        out["year"] = int(str(out["drill_year"])[:4])
    return out


# Pages whose form takes input in a different shape from what is stored: values are converted before
# they go through the page's rules.
PAGE_INPUT_ADAPTERS = {
    "qhse.hse_weekly_drill": _drill_year_input,
    "qhse.leading_indicators": _period_month_input,
    "qhse.lagging_indicators": _period_month_input,
}


def _check_page_rules(request, entity, model, instance, values, pk=None):
    """Run the restored values through the page's serializer. `instance` is the existing row for an
    update, None for a restore. Refuses with the page's own wording if a rule would be broken."""
    ser_cls = _serializer_class(entity, model)
    if ser_cls is None or not values:
        return
    adapter = PAGE_INPUT_ADAPTERS.get(entity)
    if adapter:
        values = adapter(values)
    # "restoring" tells the page's rules this is old data being put back, not a new entry: rules that depend
    # on today (a certificate that must still be valid, a person who must still be active on the rig, a
    # date that must not be in the past) do not apply to something that was valid when it was saved.
    ctx = {"request": request, "restoring": True}
    probe = ser_cls(context=ctx)
    writable = {n for n, f in probe.fields.items() if not f.read_only}
    data = {k: v for k, v in values.items() if k in writable}
    pk_name = model._meta.pk.name
    if instance is None and pk is not None and pk_name in writable:
        data[pk_name] = pk  # a page that takes the id as input (legacy ids) needs it to validate a restore
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
        .filter(_entry_filter(entity, model, pk))
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


def _dependents_since(model, obj, since, errors=None):
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
        except Exception as exc:
            # Never block a preview over this, but say what went wrong instead of hiding it.
            if errors is not None:
                errors.append(f"{related.__name__}: {type(exc).__name__}: {str(exc)[:200]}")
            continue
        if n:
            out.append({"label": _model_label(related), "count": n})
    return sorted(out, key=lambda x: -x["count"])


def _derive_category_from_rank(obj, before=None, uid=None):
    """Travel Eligibility keeps the Rank's category alongside the Rank; keep it in step after a restore."""
    if obj.rank_id and obj.fs_category_id != obj.rank.fs_category_id:
        obj.fs_category_id = obj.rank.fs_category_id
        obj.save(update_fields=["fs_category"])


def _sync_asset_allocation(obj, before=None, uid=None):
    """An IT Asset keeps a plain Allocated flag worked out from its holder rows; recompute it for the
    asset this holder row belongs to (as the Holders page does after every change)."""
    from .models import ItAssetHolder, MstItAsset

    asset_id = obj if isinstance(obj, int) else obj.it_asset_id
    is_assigned = ItAssetHolder.objects.filter(it_asset_id=asset_id, it_asset_holder_to__isnull=True).exists()
    MstItAsset.objects.filter(it_asset_id=asset_id).update(it_asset_allocated="Y" if is_assigned else "N")


def _drilling_report_recompute(obj, before=None, uid=None):
    """Saving a Drilling Report rolls its time log up into the day's hour totals, and the day up into the
    well's running totals. After a restore the same roll-up is done, for the well the report is on now and
    the one it was on before if a rig or date change moved it."""
    from .drilling_report import recompute_dtl_totals, recompute_hdr_totals

    recompute_dtl_totals(obj, uid)
    old_hdr = (before or {}).get("drilling_hdr")
    if old_hdr and old_hdr != obj.drilling_hdr_id:
        recompute_hdr_totals(old_hdr)
    if obj.drilling_hdr_id:
        recompute_hdr_totals(obj.drilling_hdr_id)


def _drilling_report_removed(snap):
    from .drilling_report import recompute_hdr_totals

    if snap.get("drilling_hdr"):
        recompute_hdr_totals(int(snap["drilling_hdr"]))


def _single_open_holder(model, pk, merged):
    """An IT asset has one ongoing holder at a time. Restoring a holder row as ongoing (no end date) while
    another one is ongoing would leave the asset with two."""
    if merged.get("it_asset_holder_to") not in (None, "") or not merged.get("it_asset"):
        return
    other = model.objects.filter(it_asset_id=merged["it_asset"], it_asset_holder_to__isnull=True).exclude(pk=pk).first()
    if other is not None:
        raise RevertRefused(
            "This asset already has an ongoing holder (assignment " + str(other.pk) + "), and an asset can have "
            "only one. End that assignment first, or undo the reassignment that created it."
        )


def _single_open_activity(model, pk, merged):
    """One open (not completed) Activity Monitor record per activity and rig, as the page requires."""
    if merged.get("completion_dt") not in (None, "") or not merged.get("activity"):
        return
    other = model.objects.filter(activity_id=merged["activity"], rig_id=merged.get("rig"), completion_dt__isnull=True).exclude(pk=pk).first()
    if other is not None:
        raise RevertRefused(
            "There is already an open record for this activity and rig (record " + str(other.pk) + "); fill in its "
            "Completion Date first. Only one can be open at a time."
        )


def _no_repeat_mapping(model, pk, merged):
    """A certificate maps a rank once per category. Only a row being put back is held to it (the imported data
    repeats a few, and those are left as they are)."""
    if model.objects.filter(pk=pk).exists():
        return
    if model.objects.filter(cert_id=merged.get("cert"), fs_category_id=merged.get("fs_category"), rank_id=merged.get("rank")).exists():
        raise RevertRefused("This rank is already mapped to this certificate under that category, so the row can't be put back.")


def _completed_is_final(obj):
    if getattr(obj, "completion_dt", None) is not None:
        raise RevertRefused("A completed activity can't be altered, so it can't be reverted either.")


# Checks on the existing record before it is changed or removed by a revert: the page's own "this can no longer
# be altered" rules. Called with the record as it is now.
RECORD_GUARDS = {
    "qhse.activity_monitor": _completed_is_final,
}

# Checks on the whole record as it would be after a restore, for rules between rows that a single field
# check cannot see. Called with (model, record id, the record's values after the restore).
STATE_GUARDS = {
    "it_asset.it_asset_holders": _single_open_holder,
    "qhse.activity_monitor": _single_open_activity,
    "qhse.cert_to_rank_mapping": _no_repeat_mapping,
}


def _holder_companions(entry, model, obj):
    """A reassignment ends the asset's ongoing holder and starts a new one in one request. Undoing the
    new holder's creation alone would leave the asset with no holder at all, so the holder it ended is
    re-opened in the same step (if it is still exactly as the reassignment left it)."""
    if not entry.batch_id:
        return []
    out = []
    sibs = SysAuditLog.objects.filter(
        batch_id=entry.batch_id, action="update", target_table=model._meta.db_table
    ).exclude(target_pk=str(obj.pk))
    for sib in sibs:
        ch = (sib.changes or {}).get("it_asset_holder_to")
        if not isinstance(ch, dict) or ch.get("old") not in (None, ""):
            continue
        other = model.objects.filter(pk=sib.target_pk, it_asset_id=obj.it_asset_id).first()
        if other is None or other.it_asset_holder_to is None:
            continue
        if _audit.snapshot(other).get("it_asset_holder_to") != ch.get("new"):
            continue  # it has been changed since the reassignment; leave it alone
        out.append({"model": model, "pk": str(other.pk), "fields": {"it_asset_holder_to": None}, "label": f"Re-open the assignment that the reassignment ended (assignment {other.pk})"})
    return out


# Other records that go along with undoing a creation, as a list of {"model", "pk", "fields", "label"}.
UNDO_COMPANIONS = {
    "it_asset.it_asset_holders": _holder_companions,
}


# Values a page works out from other fields when it saves. A restore sets the fields directly, so the
# derived values are brought back in line here, inside the same transaction.
AFTER_RESTORE = {
    "masters.travel_eligibility": _derive_category_from_rank,
    "it_asset.it_asset_holders": _sync_asset_allocation,
    "drilling.drilling_report": _drilling_report_recompute,
}
# Same, but run once a restored record's child rows are back too (a roll-up needs them).
AFTER_INSERT_ALL = {
    "drilling.drilling_report": _drilling_report_recompute,
}
# Same, after a record is removed by undoing its creation; called with the record's last values.
AFTER_REMOVE = {
    "it_asset.it_asset_holders": lambda snap: _sync_asset_allocation(int(snap["it_asset"])),
    "drilling.drilling_report": _drilling_report_removed,
}


def _get_row(model, pk):
    """The current row, locked for the length of the transaction where the database supports it."""
    from django.db import connection

    qs = model.objects.filter(pk=pk)
    if connection.features.has_select_for_update:
        qs = qs.select_for_update()
    return qs.first()


def _summarise(rows):
    """[(table, ...)] or child dicts -> [{"label", "count"}] for the preview."""
    counts = {}
    for r in rows:
        table = r["model"]._meta.db_table if isinstance(r, dict) else r[0]
        model = r["model"] if isinstance(r, dict) else _model_by_table(table)
        label = _model_label(model) if model is not None else table
        counts[label] = counts.get(label, 0) + 1
    return [{"label": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])]


def _collect_children(last, parent_table, parent_pk):
    """Rows deleted in the same request as `last` that belonged under it (directly, or through one
    another), oldest first, ready to be put back after it."""
    if not last.batch_id:
        return []
    sibs = list(SysAuditLog.objects.filter(batch_id=last.batch_id, action__in=GONE_ACTIONS).exclude(pk=last.pk).order_by("id"))
    included = {(parent_table, str(parent_pk))}
    out = []
    grew = True
    while grew:
        grew = False
        for sib in list(sibs):
            model = _model_by_table(sib.target_table)
            if model is None or not sib.changes:
                continue
            state = {f: v.get("old") for f, v in sib.changes.items() if isinstance(v, dict)}
            owned = False
            pk_field = model._meta.pk
            if pk_field.is_relation and (pk_field.related_model._meta.db_table, str(sib.target_pk)) in included:
                owned = True  # the row is keyed by its parent (a one-to-one extension row)
            for f in model._meta.fields:
                if owned:
                    break
                if f.is_relation and f.many_to_one and state.get(f.name) is not None:
                    if (f.related_model._meta.db_table, str(state[f.name])) in included:
                        owned = True
            if owned:
                out.append({"model": model, "pk": str(sib.target_pk), "state": state, "label": sib.record_label or f"{model.__name__} {sib.target_pk}"})
                included.add((sib.target_table, str(sib.target_pk)))
                sibs.remove(sib)
                grew = True
    return out


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
    entity, model = _resolve(entry.entity, entry.target_table)
    pk = entry.target_pk or entry.record_id
    rows = entries_for(entity, model, pk)
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
        "table": model._meta.db_table,
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
        rec_guard = RECORD_GUARDS.get(entity)
        if rec_guard:
            rec_guard(obj)
        current = _audit.snapshot(obj)
        # A logged change can name something that is not a plain field of this record (a list of
        # detail lines, a computed value). Restoring only the plain fields would leave the record
        # half restored, so it is refused instead.
        extra = [f for f in touched if f not in current]
        if extra:
            raise RevertRefused(
                "A change after that version also changed " + ", ".join(_pretty(f) for f in extra)
                + ", which can't be restored automatically yet. Nothing was changed."
            )
        for f in touched:
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
        guard = STATE_GUARDS.get(entity)
        if guard:
            guard(model, pk, {**current, **{i["field"]: i["restore_to"] for i in plan["fields"]}})
        # The change being undone is the first one after the chosen version.
        since = later[0].ts if later else None
        if since is not None and since.tzinfo is not None:
            # SQL Server hands dates back tagged as UTC even though the app stores plain local times
            # (USE_TZ is off). Compared against the plain cr_dt columns, the tagged value matches nothing.
            since = since.replace(tzinfo=None)
        if since is not None:
            problems = []
            plan["warnings"] = _dependents_since(model, obj, since, problems)
            if problems:
                plan["warnings_problems"] = problems
            plan["since"] = since.strftime("%Y-%m-%d %H:%M")
        plan["allowed"] = True
        return plan, obj

    if not exists_at_cut and exists_in_db:
        # Undoing a creation deletes the record. A page that never lets records be deleted (it can only
        # deactivate them) must not have them deleted through here either.
        view = _viewset_for(entity, model)
        if entity in NO_DELETE_ENTITIES:
            raise RevertRefused("This page doesn't allow records to be deleted, so a creation can't be undone.")
        if entity in SOFT_DELETE_ENTITIES:
            raise RevertRefused("This page never removes records (it marks them deleted), so a creation can't be undone. Mark the record deleted instead.")
        if view is not None and "delete" not in getattr(view, "http_method_names", ["delete"]):
            raise RevertRefused("This page doesn't allow records to be deleted, so a creation can't be undone. Deactivate it instead.")
        # The page's own "in use" rule (it checks references before it lets a record be deleted).
        if view is not None:
            try:
                refs = view()._references(obj)
            except Exception:
                refs = []
            if refs:
                raise RevertRefused(
                    "Can't undo this creation because other records still use it ("
                    + ", ".join(f"{r['count']} {r['label']}" for r in refs) + ")."
                )
        rec_guard = RECORD_GUARDS.get(entity)
        if rec_guard:
            rec_guard(obj)
        guard = UNDO_CREATE_GUARDS.get(entity)
        if guard:
            why = guard(obj)
            if why:
                raise RevertRefused("Can't undo this creation: " + why)
        _check_barriers(entity, model, pk, cut_entry_id)
        plan["action"] = "delete"
        kids = _audit.cascade_snapshots(obj)
        if kids:
            plan["child_summary"] = _summarise(kids)
        companion_fn = UNDO_COMPANIONS.get(entity)
        if companion_fn:
            companions = companion_fn(entry, model, obj)
            if companions:
                plan["companions"] = companions
                plan["also"] = [c["label"] for c in companions]
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
        children = _collect_children(last, model._meta.db_table, pk)
        if children and cut != len(rows) - 2:
            # The lines (time log rows, trainees, ...) come from the moment of deletion. Rewinding the record
            # itself to an older version while taking its lines from the deletion would mix two different
            # states, and any roll-up over the lines would then overwrite the record's own figures.
            raise RevertRefused(
                "This record's lines are only available as they were when it was deleted. Use \"Bring the "
                "record back\" on the deletion, then restore an earlier version of the record itself."
            )
        state = {}
        for f in (last.changes or {}):
            val, found = _target_value(rows, cut, f)
            if found:
                state[f] = val
        _check_barriers(entity, model, pk, cut_entry_id)
        _check_page_rules(request, entity, model, None, state, pk)
        guard = STATE_GUARDS.get(entity)
        if guard:
            guard(model, pk, state)
        plan["action"] = "insert"
        plan["state"] = state
        plan["child_rows"] = children
        if children:
            plan["child_summary"] = _summarise(children)
        plan["fields"] = [{"field": f, "label": _pretty(f), "current": None, "restore_to": v} for f, v in state.items() if f not in _audit.BOOKKEEPING_FIELDS]
        plan["allowed"] = True
        return plan, None

    plan["reason"] = "The record doesn't exist in that state and doesn't exist now. Nothing to change."
    return plan, None


def _stamp(model, now):
    """The 'modified' moment in the form the column wants (some tables keep only a date)."""
    f = model._meta.get_field("mod_dt")
    return now.date() if f.get_internal_type() == "DateField" else now


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


def _insert_rows(plan, request, now, uid):
    """Put the record back, then the rows that were deleted with it. Every check a normal save would
    make is made on each row; any refusal raises RevertRefused and the caller's transaction undoes it."""
    model = _resolve(plan["entity"], plan["table"])[1]
    instance = _build_instance(model, plan["record_id"], plan["state"])
    _check_insertable(model, instance)
    names = {f.name for f in model._meta.fields}
    if "mod_user_id" in names and uid is not None:
        instance.mod_user_id = uid
    if "mod_dt" in names:
        instance.mod_dt = _stamp(model, now)
    instance.save(force_insert=True)
    hook = AFTER_RESTORE.get(plan["entity"])
    # A roll-up that needs the child rows runs once they are back (below), not on the bare record.
    if hook and plan["entity"] not in AFTER_INSERT_ALL:
        hook(instance, None, uid)
    inserted = [(instance, None)]
    for child in plan.get("child_rows", []):
        cmodel = child["model"]
        cinst = _build_instance(cmodel, child["pk"], child["state"])
        _check_page_rules(request, None, cmodel, None, child["state"], child["pk"])
        _check_insertable(cmodel, cinst)
        cinst.save(force_insert=True)
        fix = CHILD_AFTER_RESTORE.get(cmodel._meta.db_table)
        if fix:
            fix(cinst)
        inserted.append((cinst, child))
    after_all = AFTER_INSERT_ALL.get(plan["entity"])
    if after_all:
        after_all(instance, None, uid)
    return inserted


def preview(entry_id, mode="after", request=None):
    """What a revert would do, without doing it. Never raises: a refusal comes back as
    {"allowed": False, "reason": ...}."""
    try:
        with transaction.atomic():
            plan, obj = _plan(entry_id, mode, request)
            if plan["action"] == "insert" and plan["allowed"]:
                # Try it for real inside a savepoint that is rolled back: the whole record and its
                # rows go through every check, and nothing is kept.
                sid = transaction.savepoint()
                try:
                    _insert_rows(plan, request, timezone.now(), _audit.current_user(request)[0])
                finally:
                    transaction.savepoint_rollback(sid)
            plan.pop("state", None)
            plan.pop("child_rows", None)
            plan.pop("companions", None)
            return plan
    except RevertRefused as exc:
        return {"allowed": False, "reason": str(exc), "action": "none", "fields": [], "entry_id": entry_id, "mode": mode}


def apply(request, entry_id, mode="after", reason=""):
    """Do the revert. Raises RevertRefused (nothing changed) or returns the plan plus the new entry id."""
    with transaction.atomic():
        plan, obj = _plan(entry_id, mode, request)
        if not plan["allowed"]:
            raise RevertRefused(plan["reason"] or "Nothing to revert.")
        entity, model = _resolve(plan["entity"], plan["table"])
        uid, _username = _audit.current_user(request)
        now = timezone.now()
        pk = plan["record_id"]
        extra_entries = []  # (action, table, pk, label, changes) for the rows that went along with the record

        if plan["action"] == "update":
            changes = {}
            update_fields = []
            before_values = _audit.snapshot(obj)
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
                obj.mod_dt = _stamp(model, now)
                update_fields.append("mod_dt")
            obj.save(update_fields=update_fields)
            hook = AFTER_RESTORE.get(plan["entity"])
            if hook:
                hook(obj, before_values, uid)
            # Log what is really stored now: a page's after-restore step can change other columns too (a
            # roll-up of hours, a derived category), and the history must agree with the database.
            obj.refresh_from_db()
            stored = _audit.snapshot(obj)
            changes = {
                f: {"old": before_values.get(f), "new": v}
                for f, v in stored.items()
                if f not in _audit.BOOKKEEPING_FIELDS and before_values.get(f) != v
            }
            audit_action = "revert"
            target = (model._meta.db_table, str(pk))
        elif plan["action"] == "delete":
            changes = _audit.as_delete_changes(_audit.snapshot(obj, full=True))
            # Rows that go with the record (CASCADE) are written to the log first, so they can be put back.
            for t, cpk, label, snap in _audit.cascade_snapshots(obj):
                extra_entries.append(("revert_delete", t, cpk, label, _audit.as_delete_changes(snap)))
            try:
                obj.delete()
            except ProtectedError as exc:
                used = sorted({o.__class__.__name__ for o in exc.protected_objects})
                raise RevertRefused(
                    "Can't undo this creation because other records still use it (" + ", ".join(used) + ")."
                )
            gone = _audit.snapshot(obj)
            for comp in plan.get("companions", []):
                row = comp["model"].objects.get(pk=comp["pk"])
                before_row = _audit.snapshot(row)
                for f, v in comp["fields"].items():
                    setattr(row, f, v)
                if "mod_user_id" in {x.name for x in comp["model"]._meta.fields} and uid is not None:
                    row.mod_user_id = uid
                if "mod_dt" in {x.name for x in comp["model"]._meta.fields}:
                    row.mod_dt = _stamp(comp["model"], now)
                row.save()
                after_row = _audit.snapshot(row)
                extra_entries.append(
                    (
                        "revert", comp["model"]._meta.db_table, comp["pk"], plan["record_label"],
                        {f: {"old": before_row.get(f), "new": after_row.get(f)} for f in comp["fields"]},
                    )
                )
            hook = AFTER_REMOVE.get(plan["entity"])
            if hook:
                hook(gone)
            audit_action = "revert_delete"
            target = (model._meta.db_table, str(pk))
        else:  # insert: the record, then the rows that were deleted with it
            inserted = _insert_rows(plan, request, now, uid)
            # What is stored after the restore and any roll-up, not what the plan intended.
            parent = inserted[0][0]
            parent.refresh_from_db()
            changes = {k: {"old": None, "new": v} for k, v in _audit.snapshot(parent).items() if k not in _audit.BOOKKEEPING_FIELDS}
            for cinst, child in inserted[1:]:
                cinst.refresh_from_db()
                extra_entries.append(
                    (
                        "revert_restore", cinst._meta.db_table, str(cinst.pk), child["label"],
                        {k: {"old": None, "new": v} for k, v in _audit.snapshot(cinst).items() if k not in _audit.BOOKKEEPING_FIELDS},
                    )
                )
            audit_action = "revert_restore"
            target = (model._meta.db_table, str(pk))

        entry = _audit.record_action(
            request, audit_action, entity, pk, plan["record_label"], changes or None,
            target=target, reverted_of=plan["entry_id"], note=reason or "",
        )
        if entry is None:
            # The revert itself must always be on record; undo it if the log write failed.
            raise RevertRefused("The revert could not be recorded in the audit log, so it was not applied.")
        for act, table, cpk, label, cchanges in extra_entries:
            _audit.record_action(
                request, act, entity, cpk, label, cchanges or None, target=(table, cpk),
                reverted_of=plan["entry_id"], note=reason or "",
            )
        plan.pop("state", None)
        plan.pop("child_rows", None)
        plan.pop("companions", None)
        plan["new_entry_id"] = entry.id
        return plan
