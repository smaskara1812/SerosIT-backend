from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from . import audit as _audit
from .auth_backend import _sha256
from .models import SysAuditLog, SysMenu, MstUser, MstUserPassword, UserPermission, UserProfile
from .permissions import IsAppAdmin, get_menu_registry, get_user_access


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
        return response


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_api(request):
    _audit.log_auth("logout", request.user.username, request)
    return Response({"success": True})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    access = get_user_access(request)
    return Response(
        {
            "id": request.user.id,
            "username": request.user.username,
            "is_app_admin": access["is_admin"],
            "perms": access["perms"],
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
    _audit.record_action(
        request,
        "permission_change",
        "admin.user_rights",
        user_id,
        profile.user_login_id,
        {"is_app_admin": {"old": was_admin, "new": profile.is_app_admin}},
    )
    return Response({"is_app_admin": profile.is_app_admin})


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
    return Response({"actions": actions, "users": users, "entities": entities})


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
        )
    )
    for r in rows:
        r["ts"] = r["ts"].strftime("%Y-%m-%d %H:%M:%S") if r["ts"] else ""
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


@api_view(["GET"])
@permission_classes([IsAppAdmin])
def admin_user_management_get_api(request, user_id):
    try:
        u = MstUser.objects.select_related("department").get(user_id=user_id)
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
    }

    u.user_name = name
    u.user_email = email or None
    u.department_id = dept_id
    u.user_type_id = user_type
    u.user_from = user_from or u.user_from
    u.user_to = user_to
    u.mod_user_id = mod_user_id
    u.save()

    after = {
        "user_name": u.user_name,
        "user_email": u.user_email,
        "department_id": u.department_id,
        "user_type_id": u.user_type_id,
        "user_from": str(u.user_from) if u.user_from else None,
        "user_to": str(u.user_to) if u.user_to else None,
    }
    changes = {k: {"old": before[k], "new": after[k]} for k in before if before[k] != after[k]}
    _audit.record_action(
        request, "update", "admin.user_management", u.user_id, u.user_login_id, changes or None
    )

    return Response({"success": True})


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
        }.items()
        if v not in (None, "")
    }
    _audit.record_action(request, "create", "admin.user_management", u.user_id, u.user_login_id, changes)

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
    _audit.record_action(request, "password_change", "admin.user_management", u.user_id, u.user_login_id)
    return Response({"success": True, "auth_type": "local"})


@api_view(["POST"])
@permission_classes([IsAppAdmin])
def admin_user_management_remove_password_api(request, user_id):
    try:
        u = MstUser.objects.get(user_id=user_id)
    except MstUser.DoesNotExist:
        return Response({"error": "User not found"}, status=404)
    MstUserPassword.objects.filter(user_id=user_id).delete()
    _audit.record_action(request, "password_change", "admin.user_management", u.user_id, u.user_login_id)
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
    )
    return Response({"success": True, "active": u.user_active == "Y"})
