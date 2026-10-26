from collections import OrderedDict

from rest_framework.permissions import BasePermission

from django.core.cache import cache

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


ACCESS_CACHE_SECONDS = 900  # same as the access-token life; a safety net, see invalidate_user_access


def _access_key(login_id):
    return "user_access:" + (login_id or "").strip().lower()


def invalidate_user_access(login_id):
    """Forget a person's cached rights so the next request reads them fresh.
    Called when they sign in or out and when an admin changes their rights."""
    cache.delete(_access_key(login_id))


def get_user_access(request):
    """
    Returns {"is_admin": bool, "perms": {menu_key: {action: bool, ...}}} for
    the current authenticated user. is_admin=True bypasses all permission
    checks — true for Django superusers and for is_app_admin profiles alike.

    Rights are read from the database when a person signs in (and when an
    admin saves their rights) and then kept in the cache, so a page that makes
    a dozen API calls does not repeat the same two lookups for each one.
    ACCESS_CACHE_SECONDS bounds how stale an entry can get if a server process
    missed an invalidation (several worker processes each have their own cache).
    """
    if not request.user.is_authenticated:
        return {"is_admin": False, "perms": {}}

    if request.user.is_superuser:
        return {"is_admin": True, "perms": {}}

    login_id = request.user.username
    held = getattr(request, "_user_access", None)
    if held is not None:
        return held
    key = _access_key(login_id)
    access = cache.get(key)
    if access is None:
        access = _load_user_access(login_id)
        cache.set(key, access, ACCESS_CACHE_SECONDS)
    try:
        request._user_access = access
    except Exception:
        pass
    return access


def _load_user_access(login_id):
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
    # Drilling Report's per-record CSV (method name export_one, since the
    # collection-level bulk /export/ already owns the plain "export" action
    # name) — same Export permission flag as the bulk export, not "view".
    "export_one": "export",
    # Hazard ID Card's Print Report PDF (method name `report`, since
    # "export" already means the plain listing's own bulk export/print
    # pattern elsewhere) — a printed report is an export of the underlying
    # records, not a "view", so it's gated the same way.
    "report": "export",
    "mark_scrap": "edit",
    "unscrap": "edit",
    "mark_lost": "edit",
    "unlost": "edit",
    "remove_assignment": "edit",
    "reassign": "add",
    # HSE Leading/Lagging Indicators: the batch detail save is an Edit.
    "save_details": "edit",
    # Incident Photos and HSE Drill photos: uploading/removing a photo on a
    # record needs Add or Edit on it — these used to fall back to View.
    "upload_photo": ("add", "edit"),
    "delete_photo": ("add", "edit"),
    # HSE Leading/Lagging Indicators: the per-report Excel export.
    "export_report": "export",
    # Printed PDFs of a record or a list (Incident Flash Report, HSE Drill report, Incident Register): printing is an export
    # of the underlying records, so it needs the Export right and not just View.
    "flash_report": "export",
    "print_pdf": "export",
    # Saving a picture or certificate file onto the server writes to the media folders, so it needs Add or Edit on the page
    # (these used to fall back to View, which let a view-only user upload).
    "upload_sign": ("add", "edit"),
    "upload_certificate": ("add", "edit"),
    # Birthday Mailer: uploading an Excel file of people adds people.
    "upload_people": "add",
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
        action = getattr(view, "action", None)
        # A view can widen what one of its actions needs (e.g. rank rows of a
        # group are allowed to whoever can Add or Edit the group).
        required = getattr(view, "action_perm_overrides", {}).get(action) or _ACTION_PERM.get(action, "view")
        # A tuple means "any of these flags" (e.g. photo upload on a record
        # is allowed to whoever can Add or Edit it).
        flags = required if isinstance(required, tuple) else (required,)
        entity_perms = access["perms"].get(entity_key, {})
        return any(entity_perms.get(flag) for flag in flags)


LOOKUP_ACTIONS = ("list", "retrieve")


def holds_a_right_on(request, keys, flags=("view", "add", "edit")):
    """True for an app admin, or for someone who holds one of `flags` on at least one of the menu keys."""
    access = get_user_access(request)
    return bool(access["is_admin"] or any(access["perms"].get(k, {}).get(f) for k in keys for f in flags))


class HasMenuPermissionOrLookup(HasMenuPermission):
    """HasMenuPermission, plus one rule: a person may READ a list as a dropdown source if they hold View, Add or Edit
    on a page that picks from it (see core/lookup_consumers.py), even without View on the list's own page. They get
    only its lookup columns. Nobody else gets it: being signed in is not enough.

    Why: a master's page rights say who may open and edit that master. They must not decide who can pick from it
    inside another page: a person who may add incidents needs the Rig list in the incident form whether or not they
    were ever given the Rigs master. But a person with no page that uses the Rig list must not be able to read it
    by typing the address. Writes, exports and full rows always need the matching right. A list can opt out with
    `lookup = False`."""

    def has_permission(self, request, view):
        if super().has_permission(request, view):
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(view, "action", None) in LOOKUP_ACTIONS and bool(getattr(view, "lookup_allowed", lambda: False)())


class HasLookupAccess(BasePermission):
    """For the small read-only lists that have no page of their own (users, employees, currencies, ...): readable
    only by an app admin or by someone who holds View, Add or Edit on a page that picks from the list."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(view, "action", None) not in LOOKUP_ACTIONS:
            return False
        return bool(getattr(view, "lookup_allowed", lambda: False)())
