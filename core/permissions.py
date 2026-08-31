from collections import OrderedDict

from rest_framework.permissions import BasePermission

from .models import SysMenu, UserPermission, UserProfile


def get_menu_registry():
    """Active menu definitions from cb_menu, ordered by group/menu order."""
    registry = OrderedDict()
    for m in SysMenu.objects.filter(is_active=True).order_by("group_order", "menu_order"):
        registry[m.menu_key] = {
            "label": m.menu_label,
            "group": m.menu_group,
            "actions": m.get_actions(),
        }
    return registry


def get_user_access(request):
    """
    Returns {"is_admin": bool, "perms": {menu_key: {action: bool, ...}}} for
    the current authenticated user. is_admin=True bypasses all permission
    checks — true for Django superusers and for is_app_admin profiles alike.

    Unlike the legacy version this isn't session-cached: JWT requests are
    stateless here, so it's recomputed per request (fine at this scale).
    """
    if not request.user.is_authenticated:
        return {"is_admin": False, "perms": {}}

    if request.user.is_superuser:
        return {"is_admin": True, "perms": {}}

    login_id = request.user.username
    try:
        profile = UserProfile.objects.get(user_login_id=login_id)
        is_admin = profile.is_app_admin
        user_id = profile.user_id
    except UserProfile.DoesNotExist:
        is_admin = False
        user_id = None

    perms = {}
    if not is_admin and user_id is not None:
        for p in UserPermission.objects.filter(user_id=user_id):
            perms[p.menu_key] = {
                "view": p.can_view,
                "add": p.can_add,
                "edit": p.can_edit,
                "delete": p.can_delete,
                "export": p.can_export,
            }

    return {"is_admin": is_admin, "perms": perms}


class IsAppAdmin(BasePermission):
    """Mirrors legacy _require_app_admin: superuser or is_app_admin profile.
    Reserved for the admin pages themselves (User Rights, User Management,
    Audit Trail) — those are never delegable, matching legacy, so they don't
    go through the menu-permission system at all."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return get_user_access(request)["is_admin"]


_ACTION_PERM = {
    "list": "view",
    "retrieve": "view",
    "create": "add",
    "update": "edit",
    "partial_update": "edit",
    "destroy": "delete",
    "check_delete": "view",
    "export": "export",
    "mark_scrap": "edit",
    "unscrap": "edit",
    "mark_lost": "edit",
    "unlost": "edit",
    "remove_assignment": "edit",
    "reassign": "add",
}


class HasMenuPermission(BasePermission):
    """
    Real per-action enforcement of the User Rights grid: App Admins bypass
    everything; everyone else needs the matching view/add/edit/delete flag
    on view.entity_key for the action being performed.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        access = get_user_access(request)
        if access["is_admin"]:
            return True
        entity_key = getattr(view, "entity_key", None)
        required = _ACTION_PERM.get(getattr(view, "action", None), "view")
        return bool(access["perms"].get(entity_key, {}).get(required))


class HasMenuPermissionOrOpenRead(HasMenuPermission):
    """Same real per-action enforcement as HasMenuPermission for writes, but
    list/retrieve/check-delete are open to any authenticated user.

    Reserved for lookup-only masters that exist purely as a dropdown source
    for some other page's form (Rig Type, Company, IT Asset Mfg, ...) and
    have no dedicated nav page of their own — which means no sys_menu row,
    which means a User Rights admin has no row in the grid to grant a
    non-admin explicit view rights on. Gating reads the same way as a real
    delegable master would silently make these permanently unreachable for
    every non-admin, however legitimately they're permitted on the page
    that needs the dropdown — this happened for real (an IT Asset page's
    lookups 403'd for a user who had view rights on the page itself)."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(view, "action", None) in ("list", "retrieve", "check_delete"):
            return True
        return super().has_permission(request, view)
