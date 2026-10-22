import json

from django.db import transaction
from django.db.models import Q
from django.utils import timezone as dj_timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

import os

from django.conf import settings

from .media_uploads import IMAGE_EXTENSIONS, media_url, next_sequence, save_media_file
from .validation_helpers import EMAIL_MESSAGE, is_valid_email, phone_error, year_message
from . import audit as _audit
from . import audit_revert as _audit_revert
from .auth_backend import _fetch_mst_user, _sha256
from .models import (
    EmailLog,
    MailAlertToUser,
    SysAuditLog,
    SysMenu,
    MstUser,
    MstUserPassword,
    UserMailCredential,
    UserPermission,
    UserProfile,
    PermissionPreset,
)
from .permissions import IsAppAdmin, get_menu_registry, get_user_access, invalidate_user_access


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok"})


class AuditedTokenObtainPairView(TokenObtainPairView):
    """Same JWT login as the stock simplejwt view, plus an audit trail
    entry — success or failure — since login/logout are otherwise invisible
    to the audit log entirely."""

    def post(self, request, *args, **kwargs):
        username = (request.data.get("username") or "").strip()
        password = request.data.get("password") or ""
        # Bad credentials raise AuthenticationFailed inside simplejwt's
        # serializer validation — that propagates straight past this method
        # (DRF's dispatch() catches it, not us), so the failure path has to
        # be logged from an except block, not by checking the response.
        try:
            response = super().post(request, *args, **kwargs)
        except Exception:
            _audit.log_auth("login_failed", username, request)
            raise
        _audit.log_auth("login", username, request)
        invalidate_user_access(username)  # every sign-in reads the rights fresh
        # Cache the password just used — this is the only place it's ever
        # available server-side — so outgoing approval-notification mail
        # can later authenticate to SMTP as this same user. Overwritten on
        # every login; see UserMailCredential's own docstring for why this
        # is deliberately unencrypted.
        if password:
            try:
                uid = UserProfile.objects.get(user_login_id=username).user_id
                UserMailCredential.objects.update_or_create(user_id=uid, defaults={"password": password})
            except UserProfile.DoesNotExist:
                pass
        return response


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_api(request):
    _audit.log_auth("logout", request.user.username, request)
    invalidate_user_access(request.user.username)
    try:
        uid = UserProfile.objects.get(user_login_id=request.user.username).user_id
        UserMailCredential.objects.filter(user_id=uid).delete()
    except UserProfile.DoesNotExist:
        pass
    # Blacklist the refresh token this session is actually holding — the
    # access token expires on its own in 15 minutes, but without this the
    # refresh token (7-day lifetime) stayed valid after "Sign out" and
    # could still mint new access tokens with it, same as rotation's own
    # BLACKLIST_AFTER_ROTATION already does for every *other* refresh, just
    # never for the one still live in the browser at logout time.
    refresh = request.data.get("refresh")
    if refresh:
        try:
            RefreshToken(refresh).blacklist()
        except TokenError:
            pass
    return Response({"success": True})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    access = get_user_access(request)
    mst_user = _fetch_mst_user(request.user.username)
    display_name = (mst_user.user_name or "").strip() if mst_user else ""
    return Response(
        {
            "id": request.user.id,
            "username": request.user.username,
            "display_name": display_name or request.user.username,
            "is_app_admin": access["is_admin"],
            "perms": access["perms"],
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_api(request):
    """Landing-page data for the common dashboard. Deliberately open to any
    authenticated user regardless of their User Rights grid — same trust
    level as the login screen itself, so only non-sensitive, own-account
    data belongs here (never a shared business figure)."""
    last_login = (
        SysAuditLog.objects.filter(username=request.user.username, action="login")
        .order_by("-ts")
        .values_list("ts", flat=True)
        .first()
    )
    return Response(
        {
            "server_time": dj_timezone.now().isoformat(),
            "last_login": last_login.isoformat() if last_login else None,
        }
    )


# ── User Rights ─────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAppAdmin])
def admin_users_api(request):
    """Paginated, searchable list of Mst_User rows for the user picker."""
    q = request.GET.get("q", "").strip()
    admin_only = request.GET.get("admin_only") == "1"
    active_filter = request.GET.get("active", "")
    page = max(int(request.GET.get("page", 1)), 1)
    limit = 50

    admin_ids = set(
        UserProfile.objects.filter(is_app_admin=True).values_list("user_id", flat=True)
    )

    base_qs = MstUser.objects.all()
    if q:
        base_qs = base_qs.filter(Q(user_name__icontains=q) | Q(user_login_id__icontains=q))

    # Tab counts reflect the search text but not the tab selection itself,
    # so switching tabs doesn't make the other counts jump around.
    active_count = base_qs.filter(user_active="Y").count()
    inactive_count = base_qs.exclude(user_active="Y").count()
    admin_count_in_search = base_qs.filter(user_id__in=admin_ids).count() if admin_ids else 0

    qs = base_qs
    if admin_only:
        qs = qs.filter(user_id__in=admin_ids) if admin_ids else qs.none()
    if active_filter == "1":
        qs = qs.filter(user_active="Y")
    elif active_filter == "0":
        qs = qs.exclude(user_active="Y")

    total = qs.count()

    rows = qs.order_by("user_name")[(page - 1) * limit : page * limit]
    users = [
        {
            "user_id": r.user_id,
            "login_id": r.user_login_id,
            "name": r.user_name or r.user_login_id,
            "email": r.user_email or "",
            "active": r.user_active == "Y",
            "is_app_admin": r.user_id in admin_ids,
        }
        for r in rows
    ]
    return Response(
        {
            "users": users,
            "page": page,
            "total": total,
            "active_count": active_count,
            "inactive_count": inactive_count,
            "admin_count": admin_count_in_search,
            "has_more": page * limit < total,
        }
    )


@api_view(["GET"])
@permission_classes([IsAppAdmin])
def admin_user_perms_api(request, user_id):
    try:
        profile = UserProfile.objects.get(user_id=user_id)
        is_admin = profile.is_app_admin
    except UserProfile.DoesNotExist:
        is_admin = False

    perm_rows = {p.menu_key: p for p in UserPermission.objects.filter(user_id=user_id)}

    menus = []
    for key, meta in get_menu_registry().items():
        row = perm_rows.get(key)
        menus.append(
            {
                "key": key,
                "label": meta["label"],
                "group": meta["group"],
                "actions": meta["actions"],
                "perms": {
                    "view": row.can_view if row else False,
                    "add": row.can_add if row else False,
                    "edit": row.can_edit if row else False,
                    "delete": row.can_delete if row else False,
                    "export": row.can_export if row else False,
                },
            }
        )

    return Response({"is_app_admin": is_admin, "menus": menus})


def _perm_summary(user_id):
    return {
        up.menu_key: ",".join(
            a for a in ("view", "add", "edit", "delete", "export") if getattr(up, f"can_{a}")
        )
        or "—"
        for up in UserPermission.objects.filter(user_id=user_id)
    }


@api_view(["POST"])
@permission_classes([IsAppAdmin])
def admin_user_perms_save_api(request, user_id):
    data = request.data
    is_admin = bool(data.get("is_app_admin", False))
    login_id = data.get("login_id", "")

    profile, _ = UserProfile.objects.get_or_create(
        user_id=user_id, defaults={"user_login_id": login_id}
    )
    old_admin = profile.is_app_admin
    old_perms = _perm_summary(user_id)

    if login_id and profile.user_login_id != login_id:
        profile.user_login_id = login_id
    profile.is_app_admin = is_admin
    profile.save()

    menus = data.get("menus", {})
    granted_by = request.user.username
    valid_keys = set(get_menu_registry().keys())

    for key in valid_keys:
        if key not in menus:
            continue
        p = menus[key]
        UserPermission.objects.update_or_create(
            user_id=user_id,
            menu_key=key,
            defaults={
                "can_view": bool(p.get("view")),
                "can_add": bool(p.get("add")),
                "can_edit": bool(p.get("edit")),
                "can_delete": bool(p.get("delete")),
                "can_export": bool(p.get("export")),
                "granted_by": granted_by,
            },
        )

    invalidate_user_access(profile.user_login_id)  # after the rows are written
    new_perms = _perm_summary(user_id)
    changes = {}
    if old_admin != is_admin:
        changes["is_app_admin"] = {"old": old_admin, "new": is_admin}
    for k in sorted(set(old_perms) | set(new_perms)):
        ov, nv = old_perms.get(k, "—"), new_perms.get(k, "—")
        if ov != nv:
            changes[k] = {"old": ov, "new": nv}

    _audit.record_action(
        request,
        "permission_change",
        "admin.user_rights",
        user_id,
        login_id or profile.user_login_id,
        changes or None,
        target=("mst_user", str(user_id)),
    )

    return Response({"success": True})


@api_view(["POST"])
@permission_classes([IsAppAdmin])
def admin_user_admin_toggle_api(request, user_id):
    login_id = request.data.get("login_id", "")
    profile, _ = UserProfile.objects.get_or_create(
        user_id=user_id, defaults={"user_login_id": login_id}
    )
    was_admin = profile.is_app_admin
    profile.is_app_admin = not profile.is_app_admin
    profile.save()
    invalidate_user_access(profile.user_login_id)
    _audit.record_action(
        request,
        "permission_change",
        "admin.user_rights",
        user_id,
        profile.user_login_id,
        {"is_app_admin": {"old": was_admin, "new": profile.is_app_admin}},
        target=("mst_user", str(user_id)),
    )
    return Response({"is_app_admin": profile.is_app_admin})


# ── Permission presets ───────────────────────────────────────────────────────
# Named, reusable checkbox selections for the User Rights grid — save one
# from whatever's currently checked (e.g. "Req Master View Only"), then
# apply it to any other user with one click. Applying only pre-fills that
# user's grid client-side; the real Save still has to be clicked.

@api_view(["GET"])
@permission_classes([IsAppAdmin])
def admin_permission_presets_api(request):
    presets = PermissionPreset.objects.all()
    return Response(
        [
            {
                "id": p.preset_id,
                "name": p.name,
                "description": p.description or "",
                "menus": json.loads(p.menus_json),
            }
            for p in presets
        ]
    )


@api_view(["POST"])
@permission_classes([IsAppAdmin])
def admin_permission_preset_create_api(request):
    name = (request.data.get("name") or "").strip()
    description = (request.data.get("description") or "").strip()
    menus = request.data.get("menus") or {}

    if not name:
        return Response({"error": "Name is required"}, status=400)
    if PermissionPreset.objects.filter(name=name).exists():
        return Response({"error": "A preset with this name already exists"}, status=400)

    valid_keys = set(get_menu_registry().keys())
    cleaned = {}
    for key, p in menus.items():
        if key not in valid_keys:
            continue
        flags = {a: bool(p.get(a)) for a in ("view", "add", "edit", "delete", "export")}
        if any(flags.values()):
            cleaned[key] = flags
    if not cleaned:
        return Response({"error": "Select at least one permission before saving a preset"}, status=400)

    try:
        creator_id = UserProfile.objects.get(user_login_id=request.user.username).user_id
    except UserProfile.DoesNotExist:
        creator_id = None

    preset = PermissionPreset.objects.create(
        name=name,
        description=description or None,
        menus_json=json.dumps(cleaned),
        created_by_user_id=creator_id,
    )
    _audit.record_action(
        request,
        "create",
        "admin.permission_presets",
        preset.preset_id,
        name,
        {
            "name": {"old": None, "new": name},
            "description": {"old": None, "new": description or None},
            "menu_count": {"old": None, "new": len(cleaned)},
            "menus": {"old": None, "new": cleaned},  # which pages and which actions the preset grants
        },
        target=preset,
    )
    return Response({"id": preset.preset_id, "name": preset.name}, status=201)


@api_view(["DELETE"])
@permission_classes([IsAppAdmin])
def admin_permission_preset_delete_api(request, preset_id):
    try:
        preset = PermissionPreset.objects.get(preset_id=preset_id)
    except PermissionPreset.DoesNotExist:
        return Response(status=204)
    name = preset.name
    before = {
        "name": name,
        "description": preset.description,
        "menus": json.loads(preset.menus_json),  # what the preset granted, so the entry says what was removed
    }
    table = preset._meta.db_table
    preset.delete()
    _audit.record_action(
        request, "delete", "admin.permission_presets", preset_id, name,
        {k: {"old": v, "new": None} for k, v in before.items()}, target=(table, preset_id),
    )
    return Response(status=204)


# ── Audit Trail ──────────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAppAdmin])
def admin_audit_facets_api(request):
    base = SysAuditLog.objects.order_by()
    actions = sorted(set(base.values_list("action", flat=True)))
    users = sorted({u for u in base.values_list("username", flat=True) if u})
    seen = {}
    for key, label in base.values_list("entity", "entity_label"):
        if key not in seen:
            seen[key] = label or key
    entities = sorted(({"key": k, "label": v} for k, v in seen.items()), key=lambda x: x["label"])
    return Response(
        {"actions": actions, "users": users, "entities": entities, "revertible": _audit_revert.revertible_entities()}
    )


@api_view(["GET"])
@permission_classes([IsAppAdmin])
def admin_audit_list_api(request):
    qs = SysAuditLog.objects.all()
    action = request.GET.get("action", "").strip()
    entity = request.GET.get("entity", "").strip()
    user = request.GET.get("user", "").strip()
    q = request.GET.get("q", "").strip()
    dfrom = request.GET.get("from", "").strip()
    dto = request.GET.get("to", "").strip()
    kind = request.GET.get("kind", "").strip()
    if kind in ("change", "event"):
        qs = qs.filter(kind=kind)
    if action:
        qs = qs.filter(action=action)
    if entity:
        qs = qs.filter(entity=entity)
    if user:
        qs = qs.filter(username=user)
    if q:
        qs = qs.filter(
            Q(record_label__icontains=q) | Q(username__icontains=q) | Q(entity_label__icontains=q)
        )
    if dfrom:
        qs = qs.filter(ts__date__gte=dfrom)
    if dto:
        qs = qs.filter(ts__date__lte=dto)

    total = qs.count()
    try:
        page = max(1, int(request.GET.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    size = 30
    rows = list(
        qs.order_by("-ts")[(page - 1) * size : page * size].values(
            "id",
            "ts",
            "user_id",
            "username",
            "action",
            "entity",
            "entity_label",
            "record_id",
            "record_label",
            "changes",
            "ip",
            "target_table",
            "target_pk",
            "reverted_of",
            "note",
            "kind",
            "source",
        )
    )
    for r in rows:
        r["ts"] = r["ts"].strftime("%Y-%m-%d %H:%M:%S") if r["ts"] else ""
        # Offer History where there is a record to show it for and the page supports revert.
        r["has_history"] = bool(
            (r["target_pk"] or r["record_id"])
            and r["kind"] == "change"
            and _audit_revert.can_show_history(r["entity"], r["target_table"])
        )
    return Response(
        {
            "results": rows,
            "total": total,
            "page": page,
            "page_size": size,
            "pages": (total + size - 1) // size,
        }
    )


@api_view(["GET"])
@permission_classes([IsAppAdmin])
def admin_audit_history_api(request):
    """Every logged change of one record, oldest first, with before/after for each."""
    entity = request.GET.get("entity", "").strip()
    record_id = request.GET.get("record_id", "").strip()
    table = request.GET.get("table", "").strip()
    if not entity or not record_id:
        return Response({"error": "entity and record_id are required."}, status=400)
    try:
        return Response(_audit_revert.history(entity, record_id, table))
    except _audit_revert.RevertRefused as exc:
        return Response({"error": str(exc)}, status=400)


@api_view(["POST"])
@permission_classes([IsAppAdmin])
def admin_audit_revert_preview_api(request, entry_id):
    """What restoring to before/after this entry would change, with a plain reason if it can't be done."""
    mode = request.data.get("mode", "after")
    return Response(_audit_revert.preview(entry_id, mode, request))


@api_view(["POST"])
@permission_classes([IsAppAdmin])
def admin_audit_revert_api(request, entry_id):
    mode = request.data.get("mode", "after")
    reason = str(request.data.get("reason", "") or "").strip()[:255]
    try:
        result = _audit_revert.apply(request, entry_id, mode, reason)
    except _audit_revert.RevertRefused as exc:
        return Response({"ok": False, "error": str(exc)}, status=400)
    return Response({"ok": True, **result})


def _history_settings_rows():
    from .models import SysMenu

    supported = set(_audit_revert.supported_entities())
    rows = (
        SysMenu.objects.filter(is_active=True)
        .filter(Q(menu_key__in=supported) | Q(add_available=True) | Q(edit_available=True) | Q(delete_available=True))
        .order_by("group_order", "menu_order", "menu_label")
    )
    return [
        {
            "menu_key": r.menu_key,
            "label": r.menu_label,
            "group": r.menu_group,
            "group_order": r.group_order,
            "supported": r.menu_key in supported,
            "enabled": bool(r.history_enabled and r.menu_key in supported),
        }
        for r in rows
    ]


@api_view(["GET", "PUT"])
@permission_classes([IsAppAdmin])
def admin_history_settings_api(request):
    """Which pages have History and revert switched on. One setting for the whole system (it lives on
    the page's sys_menu row). GET lists the pages; PUT {menu_keys: [...], enabled: true|false} changes
    them. Only pages the code supports can be switched on."""
    from .models import SysMenu

    if request.method == "PUT":
        keys = request.data.get("menu_keys") or []
        enabled = request.data.get("enabled")
        if not isinstance(keys, list) or not keys or not isinstance(enabled, bool):
            return Response({"error": "menu_keys (a list) and enabled (true or false) are required."}, status=400)
        supported = set(_audit_revert.supported_entities())
        unsupported = [k for k in keys if k not in supported]
        if unsupported:
            return Response(
                {"error": "History and revert are not supported yet for: " + ", ".join(unsupported)}, status=400
            )
        with transaction.atomic():
            for row in SysMenu.objects.filter(menu_key__in=keys):
                if row.history_enabled == enabled:
                    continue
                row.history_enabled = enabled
                row.save(update_fields=["history_enabled", "mod_dt"])
                _audit.record_action(
                    request, "history_setting", "admin.history_settings", row.menu_key, row.menu_label,
                    {"history_enabled": {"old": not enabled, "new": enabled}},
                )
        _audit_revert.invalidate_enabled()
    return Response({"pages": _history_settings_rows()})


# ── Email Log ─────────────────────────────────────────────────────────────
# Every outgoing email this app attempts (core/mailer.py writes one row per
# attempt, success or failure) — same read-only admin-list shape as Audit
# Trail above, not a DRF router viewset, since nothing here is ever created
# or edited through the API itself.

def _prettify_trigger_code(code):
    # "drilling_report.finalize" -> "Drilling Report — Finalize". Generic on
    # purpose — works for whatever dotted-namespace code a future feature
    # (another approval code, an auto-alert, a custom alert...) picks,
    # without this needing to know about it up front.
    return " — ".join(part.replace("_", " ").title() for part in code.split("."))


@api_view(["GET"])
@permission_classes([IsAppAdmin])
def admin_email_log_facets_api(request):
    users = sorted(
        {
            u
            for u in MstUser.objects.filter(user_id__in=EmailLog.objects.values_list("sent_by_user_id", flat=True))
            .values_list("user_login_id", flat=True)
            if u
        }
    )
    # trigger_code is the stable filter facet (e.g. "drilling_report.finalize")
    # — trigger itself is a per-record human label (e.g. "Drilling Report
    # #7821 Finalize") and would give one facet entry per record, not per
    # kind of event.
    trigger_codes = sorted({t for t in EmailLog.objects.values_list("trigger_code", flat=True) if t})
    triggers = [{"value": t, "label": _prettify_trigger_code(t)} for t in trigger_codes]
    return Response({"users": users, "triggers": triggers})


@api_view(["GET"])
@permission_classes([IsAppAdmin])
def admin_email_log_list_api(request):
    qs = EmailLog.objects.all()
    status_filter = request.GET.get("status", "").strip()
    trigger = request.GET.get("trigger", "").strip()
    q = request.GET.get("q", "").strip()
    dfrom = request.GET.get("from", "").strip()
    dto = request.GET.get("to", "").strip()
    if status_filter == "success":
        qs = qs.filter(success=True)
    elif status_filter == "failed":
        qs = qs.filter(success=False)
    if trigger:
        qs = qs.filter(trigger_code=trigger)
    if q:
        qs = qs.filter(Q(subject__icontains=q) | Q(recipients__icontains=q) | Q(trigger__icontains=q))
    if dfrom:
        qs = qs.filter(sent_dt__date__gte=dfrom)
    if dto:
        qs = qs.filter(sent_dt__date__lte=dto)

    total = qs.count()
    try:
        page = max(1, int(request.GET.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    size = 30
    rows = list(
        qs.order_by("-sent_dt")[(page - 1) * size : page * size].values(
            "email_log_id",
            "subject",
            "body",
            "recipients",
            "trigger",
            "success",
            "used_fallback",
            "error",
            "attachment_names",
            "sent_by_user_id",
            "sent_dt",
        )
    )
    sender_ids = {r["sent_by_user_id"] for r in rows if r["sent_by_user_id"]}
    sender_names = dict(MstUser.objects.filter(user_id__in=sender_ids).values_list("user_id", "user_login_id"))
    for r in rows:
        r["sent_dt"] = r["sent_dt"].strftime("%Y-%m-%d %H:%M:%S") if r["sent_dt"] else ""
        r["sent_by"] = sender_names.get(r["sent_by_user_id"], "") or "System"
    return Response(
        {
            "results": rows,
            "total": total,
            "page": page,
            "page_size": size,
            "pages": (total + size - 1) // size,
        }
    )


# ── User Management ──────────────────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAppAdmin])
def admin_user_management_list_api(request):
    q = request.GET.get("q", "").strip()
    page = max(int(request.GET.get("page", 1)), 1)
    local_only = request.GET.get("local_only") == "1"
    active_filter = request.GET.get("active", "")
    limit = 50

    all_local_ids = set(MstUserPassword.objects.values_list("user_id", flat=True))

    base_qs = MstUser.objects.all()
    if q:
        base_qs = base_qs.filter(Q(user_name__icontains=q) | Q(user_login_id__icontains=q))

    active_count = base_qs.filter(user_active="Y").count()
    inactive_count = base_qs.exclude(user_active="Y").count()
    local_count_in_search = base_qs.filter(user_id__in=all_local_ids).count() if all_local_ids else 0

    qs = base_qs
    if local_only:
        qs = qs.filter(user_id__in=all_local_ids) if all_local_ids else qs.none()
    if active_filter == "1":
        qs = qs.filter(user_active="Y")
    elif active_filter == "0":
        qs = qs.exclude(user_active="Y")

    total = qs.count()

    rows = qs.order_by("user_name")[(page - 1) * limit : page * limit]
    users = [
        {
            "user_id": r.user_id,
            "login_id": r.user_login_id,
            "name": r.user_name or r.user_login_id,
            "email": r.user_email or "",
            "active": r.user_active == "Y",
            "auth_type": "local" if r.user_id in all_local_ids else "ad",
        }
        for r in rows
    ]
    return Response(
        {
            "users": users,
            "page": page,
            "total": total,
            "active_count": active_count,
            "inactive_count": inactive_count,
            "local_count": local_count_in_search,
            "has_more": page * limit < total,
        }
    )


PERSON_FIELDS = ("first_name", "middle_name", "last_name", "date_of_birth", "mobile_no", "company_id", "work_designation_id")


def _person_details(u, request):
    """The person columns on a user (moved here from the legacy employee table) plus a link to the profile picture, when its file exists."""
    def _d(v):
        return v.strftime("%Y-%m-%d") if v else ""

    path = (u.profile_picture_path or "").lstrip("/")
    has_file = bool(path) and os.path.isfile(os.path.join(str(settings.MEDIA_ROOT), path))
    return {
        "first_name": u.first_name or "",
        "middle_name": u.middle_name or "",
        "last_name": u.last_name or "",
        "date_of_birth": _d(u.date_of_birth),
        "mobile_no": u.mobile_no or "",
        "company_id": u.company_id,
        "company_name": u.company.company_name if u.company_id else "",
        "work_designation_id": u.work_designation_id,
        "work_designation_name": u.work_designation.working_designation if u.work_designation_id else "",
        "photo_url": media_url(request, path) if has_file else None,
    }


def _clean_person(data, u=None):
    """The person details sent with a user (new or existing), cleaned and checked. Returns (values to set, error text). Only the fields
    that were sent are returned; a value is judged when new or changed, so an old user can still be saved."""
    from .models import MstCompany, MstWorkingDesignation

    person = {}
    for f in PERSON_FIELDS:
        if f in data:
            v = data.get(f)
            person[f] = (v.strip() if isinstance(v, str) else v) or None
    for f, limit in (("first_name", 26), ("middle_name", 20), ("last_name", 35)):
        if person.get(f) and len(person[f]) > limit:
            return None, f"{f.replace('_', ' ').capitalize()} can be at most {limit} characters."
    if person.get("date_of_birth") and person["date_of_birth"] != str(getattr(u, "date_of_birth", "") or "")[:10] and year_message(person["date_of_birth"]):
        return None, year_message(person["date_of_birth"])
    if person.get("mobile_no") and person["mobile_no"] != (getattr(u, "mobile_no", "") or "") and phone_error(person["mobile_no"]):
        return None, phone_error(person["mobile_no"])
    for f, model, label in (("company_id", MstCompany, "company"), ("work_designation_id", MstWorkingDesignation, "working designation")):
        if person.get(f) is not None:
            try:
                person[f] = int(person[f])
            except (TypeError, ValueError):
                return None, f"Choose a valid {label}."
            if person[f] != getattr(u, f, None) and not model.objects.filter(pk=person[f]).exists():
                return None, f"Choose a valid {label}."
    return person, None


@api_view(["GET"])
@permission_classes([IsAppAdmin])
def admin_user_management_designations_api(request):
    """The working designations to pick from on the user form (active ones, plus none else)."""
    from .models import MstWorkingDesignation

    rows = MstWorkingDesignation.objects.order_by("working_designation").values("working_designation_id", "working_designation", "working_designation_active")
    return Response([{"id": r["working_designation_id"], "name": r["working_designation"], "active": r["working_designation_active"] == "Y"} for r in rows])


@api_view(["GET"])
@permission_classes([IsAppAdmin])
def admin_user_management_get_api(request, user_id):
    try:
        u = MstUser.objects.select_related("department", "company", "work_designation").get(user_id=user_id)
    except MstUser.DoesNotExist:
        return Response({"error": "User not found"}, status=404)

    has_local = MstUserPassword.objects.filter(user_id=user_id).exists()

    def _dt(v):
        return v.strftime("%Y-%m-%d") if v else ""

    return Response(
        {
            "user_id": u.user_id,
            "login_id": u.user_login_id or "",
            "name": u.user_name or u.user_login_id or "",
            "email": u.user_email or "",
            "active": u.user_active == "Y",
            "user_type": u.user_type_id or "",
            "dept_id": u.department_id,
            "dept_name": u.department.dept_dispname if u.department_id else "",
            "user_from": _dt(u.user_from),
            "user_to": _dt(u.user_to),
            "emp_id": u.emp_id,
            "nonemp_id": u.nonemp_id,
            **_person_details(u, request),
            "created_at": _dt(u.cr_dt),
            "modified_at": _dt(u.mod_dt),
            "auth_type": "local" if has_local else "ad",
        }
    )


@api_view(["POST"])
@permission_classes([IsAppAdmin])
def admin_user_management_update_api(request, user_id):
    data = request.data
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    dept_id = data.get("dept_id") or None
    user_type = (data.get("user_type") or "").strip().upper() or None
    user_from = (data.get("user_from") or "").strip() or None
    user_to = (data.get("user_to") or "").strip() or None

    if not name:
        return Response({"error": "Name is required"}, status=400)
    if user_type and user_type not in ("E", "N"):
        return Response({"error": "User type must be E or N"}, status=400)

    try:
        u = MstUser.objects.get(user_id=user_id)
    except MstUser.DoesNotExist:
        return Response({"error": "User not found"}, status=404)

    # An email must be a real address and a date's year a sensible one, judged when new or changed so an old user stays editable.
    if email and email != (u.user_email or "") and not is_valid_email(email):
        return Response({"error": EMAIL_MESSAGE}, status=400)
    for text, was in ((user_from, u.user_from), (user_to, u.user_to)):
        if text and text != str(was or "")[:10] and year_message(text):
            return Response({"error": year_message(text)}, status=400)

    # Person details (optional: only the ones sent are touched).
    person, problem = _clean_person(data, u)
    if problem:
        return Response({"error": problem}, status=400)

    # Changing the email: alert recipients that are this user and still carry the old email can follow it. The person decides.
    new_email = email or None
    sync_rows = MailAlertToUser.objects.none()
    if (u.user_email or "") != (new_email or "") and u.user_email:
        sync_rows = MailAlertToUser.objects.filter(user_id=u.user_id, email_addr__iexact=u.user_email)
    choice = (data.get("alert_email_sync") or "").strip()
    if sync_rows.exists() and choice not in ("all", "user_only"):
        return Response(
            {"needs_choice": "alert_email", "alert_rows": sync_rows.count(), "old_email": u.user_email, "new_email": new_email,
             "error": "This email is also used on alert recipients."},
            status=409,
        )

    try:
        mod_user_id = UserProfile.objects.get(user_login_id=request.user.username).user_id
    except UserProfile.DoesNotExist:
        mod_user_id = None

    before = {
        "user_name": u.user_name,
        "user_email": u.user_email,
        "department_id": u.department_id,
        "user_type_id": u.user_type_id,
        "user_from": str(u.user_from) if u.user_from else None,
        "user_to": str(u.user_to) if u.user_to else None,
        **{f: (str(getattr(u, f)) if getattr(u, f) is not None else None) for f in PERSON_FIELDS},
    }

    u.user_name = name
    u.user_email = email or None
    u.department_id = dept_id
    u.user_type_id = user_type
    u.user_from = user_from or u.user_from
    u.user_to = user_to
    for f, v in person.items():
        setattr(u, f, v)
    u.mod_user_id = mod_user_id
    u.save()
    synced = 0
    if choice == "all" and sync_rows.exists() and new_email:
        synced = sync_rows.update(email_addr=new_email, mod_user_id=mod_user_id, mod_dt=dj_timezone.now())

    after = {
        "user_name": u.user_name,
        "user_email": u.user_email,
        "department_id": u.department_id,
        "user_type_id": u.user_type_id,
        "user_from": str(u.user_from) if u.user_from else None,
        "user_to": str(u.user_to) if u.user_to else None,
        **{f: (str(getattr(u, f)) if getattr(u, f) is not None else None) for f in PERSON_FIELDS},
    }
    changes = {k: {"old": before[k], "new": after[k]} for k in before if before[k] != after[k]}
    _audit.record_action(
        request, "update", "admin.user_management", u.user_id, u.user_login_id, changes or None, target=u
    )

    return Response({"success": True, "alert_rows_updated": synced})


@api_view(["POST", "DELETE"])
@permission_classes([IsAppAdmin])
def admin_user_management_photo_api(request, user_id):
    """POST a picture to set the user's profile picture (saved as mst_employee_images/<user id>_<n>.<ext>); DELETE clears it. Nothing is
    ever deleted from disk: the old file stays and the history log records the old and the new name."""
    try:
        u = MstUser.objects.select_related("company").get(user_id=user_id)
    except MstUser.DoesNotExist:
        return Response({"error": "User not found"}, status=404)
    old = u.profile_picture_path or ""
    if request.method == "DELETE":
        new = None
    else:
        f = request.FILES.get("file")
        if not f:
            return Response({"error": "file is required"}, status=400)
        seq = next_sequence("mst_employee_images", u.user_id)
        new, error = save_media_file(f, "mst_employee_images", f"{u.user_id}_{seq}", allowed_extensions=IMAGE_EXTENSIONS, max_size_mb=5)
        if error:
            return Response({"error": error}, status=400)
    try:
        mod_user_id = UserProfile.objects.get(user_login_id=request.user.username).user_id
    except UserProfile.DoesNotExist:
        mod_user_id = None
    u.profile_picture_path = new
    u.mod_user_id, u.mod_dt = mod_user_id, dj_timezone.now()
    u.save(update_fields=["profile_picture_path", "mod_user_id", "mod_dt"])
    _audit.record_action(
        request, "update", "admin.user_management", u.user_id, u.user_login_id,
        {"profile_picture_path": {"old": old or None, "new": new}}, target=u,
    )
    return Response(_person_details(u, request))


@api_view(["POST"])
@permission_classes([IsAppAdmin])
def admin_user_management_create_api(request):
    data = request.data
    login_id = (data.get("login_id") or "").strip()
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    password = (data.get("password") or "").strip()
    user_type = (data.get("user_type") or "E").strip().upper()
    dept_id = data.get("dept_id") or None
    user_from = data.get("user_from") or None
    user_to = data.get("user_to") or None

    if not login_id or not name:
        return Response({"error": "login_id and name are required"}, status=400)
    if user_type not in ("E", "N"):
        user_type = "E"

    if MstUser.objects.filter(user_login_id__iexact=login_id).exists():
        return Response({"error": "Login ID already exists"}, status=400)
    if email and not is_valid_email(email):
        return Response({"error": EMAIL_MESSAGE}, status=400)
    if year_message(user_from) or year_message(user_to):
        return Response({"error": year_message(user_from) or year_message(user_to)}, status=400)
    person, problem = _clean_person(data)
    if problem:
        return Response({"error": problem}, status=400)

    try:
        cr_user_id = UserProfile.objects.get(user_login_id=request.user.username).user_id
    except UserProfile.DoesNotExist:
        cr_user_id = 1

    from django.utils import timezone

    u = MstUser.objects.create(
        user_login_id=login_id,
        user_name=name,
        user_email=email or None,
        user_active="Y",
        user_type_id=user_type,
        department_id=dept_id,
        user_from=user_from or timezone.now().date(),
        user_to=user_to,
        cr_user_id=cr_user_id,
        cr_dt=timezone.now(),
        **person,
    )

    if password:
        MstUserPassword.objects.create(user=u, password_hash=_sha256(password))

    changes = {
        k: {"old": None, "new": v}
        for k, v in {
            "user_login_id": login_id,
            "user_name": name,
            "user_email": email or None,
            "user_type_id": user_type,
            "department_id": dept_id,
            **person,
        }.items()
        if v not in (None, "")
    }
    if password:
        changes["local_password"] = {"old": None, "new": True}  # that one was set, never what it is
    _audit.record_action(request, "create", "admin.user_management", u.user_id, u.user_login_id, changes, target=u)

    return Response({"success": True, "user_id": u.user_id})


@api_view(["POST"])
@permission_classes([IsAppAdmin])
def admin_user_management_set_password_api(request, user_id):
    password = (request.data.get("password") or "").strip()
    if not password:
        return Response({"error": "password is required"}, status=400)

    try:
        u = MstUser.objects.get(user_id=user_id)
    except MstUser.DoesNotExist:
        return Response({"error": "User not found"}, status=404)

    MstUserPassword.objects.update_or_create(
        user=u, defaults={"password_hash": _sha256(password)}
    )
    _audit.record_action(
        request, "password_change", "admin.user_management", u.user_id, u.user_login_id,
        {"local_password": {"old": None, "new": "changed"}}, target=u,
    )
    return Response({"success": True, "auth_type": "local"})


@api_view(["POST"])
@permission_classes([IsAppAdmin])
def admin_user_management_remove_password_api(request, user_id):
    try:
        u = MstUser.objects.get(user_id=user_id)
    except MstUser.DoesNotExist:
        return Response({"error": "User not found"}, status=404)
    MstUserPassword.objects.filter(user_id=user_id).delete()
    _audit.record_action(
        request, "password_change", "admin.user_management", u.user_id, u.user_login_id,
        {"local_password": {"old": "set", "new": None}}, target=u,
    )
    return Response({"success": True, "auth_type": "ad"})


@api_view(["POST"])
@permission_classes([IsAppAdmin])
def admin_user_management_toggle_active_api(request, user_id):
    try:
        u = MstUser.objects.get(user_id=user_id)
    except MstUser.DoesNotExist:
        return Response({"error": "User not found"}, status=404)
    was_active = u.user_active == "Y"
    u.user_active = "N" if was_active else "Y"
    u.save()
    _audit.record_action(
        request,
        "deactivate" if was_active else "update",
        "admin.user_management",
        u.user_id,
        u.user_login_id,
        {"user_active": {"old": was_active, "new": not was_active}},
        target=u,
    )
    return Response({"success": True, "active": u.user_active == "Y"})
