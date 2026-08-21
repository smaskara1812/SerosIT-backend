"""
Audit trail — records who did what, when, and (for permission edits) the
field-level before/after diff. Best-effort: swallows its own exceptions so
auditing never breaks the caller's primary action.
"""

import logging

logger = logging.getLogger(__name__)

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


def record_action(request, action, entity, record_id=None, record_label=None, changes=None):
    """Generic logger (deactivate, export, permission_change, etc.)."""
    try:
        _write(request, action, entity, record_id, record_label, changes)
    except Exception:
        logger.exception("audit.record_action failed for %s/%s", entity, action)


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


def _write(request, action, entity, record_id, record_label, changes):
    uid, username = current_user(request)
    _create(uid, username, action, entity, entity_label(entity), record_id, record_label, changes, request)


def _create(uid, username, action, entity, ent_label, record_id, record_label, changes, request):
    from .models import SysAuditLog

    ip, ua = _client(request)
    SysAuditLog.objects.create(
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
    )
