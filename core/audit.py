"""
Audit trail — records who did what, when, and (for permission edits) the
field-level before/after diff. Best-effort: swallows its own exceptions so
auditing never breaks the caller's primary action.
"""

import logging
import uuid
from decimal import Decimal

logger = logging.getLogger(__name__)

# Rows of this kind are routine events, purged after six months (manage.py purge_audit_events).
# Everything else is a data change and is kept for good.
EVENT_ACTIONS = {"export", "login", "logout", "login_failed"}
# Bookkeeping columns: stamped by the app, not entered by the user, so a diff never shows them.
BOOKKEEPING_FIELDS = {"cr_user_id", "cr_dt", "mod_user_id", "mod_dt"}

def snapshot(instance, full=False):
    """{field_name: json-safe value} for every real field on a model instance.

    FK fields use the raw id (attname), dates are ISO strings, decimals strings. Without full=True the
    primary key and the bookkeeping columns (cr_*/mod_*) are left out, which is what a diff wants. A
    delete is logged with full=True so the row can be put back exactly as it was (bookkeeping included;
    the primary key goes in target_pk).
    """
    snap = {}
    for f in instance._meta.fields:
        if f.primary_key:
            continue
        if not full and f.name in BOOKKEEPING_FIELDS:
            continue
        val = getattr(instance, f.attname)
        if hasattr(val, "isoformat"):
            val = val.isoformat()
        elif isinstance(val, Decimal):
            val = str(val)
        snap[f.name] = val
    return snap


def as_delete_changes(snap):
    """A full row snapshot in the log's change format: every field went from its value to nothing."""
    return {k: {"old": v, "new": None} for k, v in snap.items()}


def cascade_snapshots(instance):
    """Rows that deleting `instance` will delete with it (CASCADE relations, any depth), as
    (table, pk, label, snapshot). The row itself is not included. Call before deleting."""
    from django.db import router
    from django.db.models.deletion import Collector

    collector = Collector(using=router.db_for_write(instance.__class__, instance=instance))
    try:
        collector.collect([instance])
    except Exception:
        # A PROTECTed reference: the delete itself will be refused, so there is nothing to record.
        return []
    objs = []
    for model, rows in collector.data.items():
        for obj in rows:
            if obj is not instance and not (model is instance.__class__ and obj.pk == instance.pk):
                objs.append(obj)
    for qs in collector.fast_deletes:
        objs.extend(list(qs))
    out = []
    for obj in objs:
        out.append((obj._meta.db_table, str(obj.pk), f"{obj.__class__.__name__} #{obj.pk}", snapshot(obj, full=True)))
    return out


_EXTRA_LABELS = {
    "auth": "Authentication",
    "admin.user_rights": "User Rights",
    "admin.user_management": "User Management",
    "admin.audit_trail": "Audit Trail",
}


def entity_label(entity):
    if entity in _EXTRA_LABELS:
        return _EXTRA_LABELS[entity]
    try:
        from .permissions import get_menu_registry

        m = get_menu_registry().get(entity)
        if m and m.get("label"):
            return m["label"]
    except Exception:
        pass
    return entity


def _client(request):
    if request is None:
        return "", ""
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip = (fwd.split(",")[0].strip() if fwd else request.META.get("REMOTE_ADDR", "")) or ""
    ua = (request.META.get("HTTP_USER_AGENT", "") or "")[:300]
    return ip[:45], ua


def current_user(request):
    """Return (user_id | None, username). user_id is the Mst_User user_id;
    None for a superuser with no cb_user_profile row."""
    try:
        if not getattr(request, "user", None) or not request.user.is_authenticated:
            return None, "anonymous"
        username = request.user.username
        from .models import UserProfile

        try:
            uid = UserProfile.objects.get(user_login_id=username).user_id
        except UserProfile.DoesNotExist:
            uid = None
        return uid, username
    except Exception:
        return None, "unknown"


def record_action(request, action, entity, record_id=None, record_label=None, changes=None, *, target=None, reverted_of=None, note=""):
    """Generic logger (create, update, delete, deactivate, export, permission_change, etc.).

    target: the model instance the entry is about (or a (table, pk) pair). It fills target_table and
    target_pk, which record history and revert work from. Returns the saved entry, or None if auditing
    failed (it never raises).
    """
    try:
        return _write(request, action, entity, record_id, record_label, changes, target, reverted_of, note)
    except Exception:
        logger.exception("audit.record_action failed for %s/%s", entity, action)
        return None


def log_auth(action, username, request=None, extra=None):
    """Auth events — login / logout / login_failed."""
    try:
        uid = None
        if username:
            try:
                from .models import UserProfile

                uid = UserProfile.objects.get(user_login_id=username).user_id
            except Exception:
                uid = None
        _create(uid, username or "", action, "auth", "Authentication", None, None, extra, request)
    except Exception:
        logger.exception("audit.log_auth failed")


def _write(request, action, entity, record_id, record_label, changes, target=None, reverted_of=None, note=""):
    uid, username = current_user(request)
    return _create(
        uid, username, action, entity, entity_label(entity), record_id, record_label, changes, request,
        target=target, reverted_of=reverted_of, note=note,
    )


def _target_parts(target):
    if target is None:
        return "", ""
    if isinstance(target, (tuple, list)):
        return str(target[0])[:64], str(target[1])[:60]
    return target._meta.db_table[:64], str(target.pk)[:60]


def batch_id(request):
    """One id per request, shared by every entry the request writes (a header and its child rows)."""
    if request is None:
        return ""
    bid = getattr(request, "_audit_batch_id", None)
    if not bid:
        bid = str(uuid.uuid4())
        try:
            request._audit_batch_id = bid
        except Exception:
            pass
    return bid


def _source(request):
    # The self-test tags its requests so its exports and edits can be told apart from real use.
    if request is None:
        return "system"
    tag = (getattr(request, "META", {}).get("HTTP_X_AUDIT_SOURCE", "") or "").strip().lower()
    return tag if tag in ("selftest", "script") else "user"


def _create(uid, username, action, entity, ent_label, record_id, record_label, changes, request,
            target=None, reverted_of=None, note=""):
    from .models import SysAuditLog

    ip, ua = _client(request)
    table, pk = _target_parts(target)
    if target is not None and record_id is None:
        record_id = pk
    return SysAuditLog.objects.create(
        user_id=uid,
        username=(username or "")[:50],
        action=action,
        entity=entity,
        entity_label=(ent_label or "")[:80],
        record_id=("" if record_id is None else str(record_id))[:40],
        record_label=(record_label or "")[:200],
        changes=changes,
        ip=ip,
        user_agent=ua,
        target_table=table,
        target_pk=pk,
        batch_id=batch_id(request),
        reverted_of=reverted_of,
        source=_source(request),
        kind="event" if action in EVENT_ACTIONS else "change",
        note=(note or "")[:255],
    )
