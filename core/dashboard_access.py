"""Shared rig-scoping policy for analytics dashboards.

Deliberately separate from Drilling Report's own rig-scope
(drilling_dtl_views.DrillingDtlViewSet._user_rig_ids), which also folds in
approver-mapping visibility ("can this user approve reports for this rig")
that has no meaning for a read-only analytics dashboard.

Every dashboard should call get_accessible_rig_ids(request) instead of
rolling its own is_superuser/is_app_admin check, so the scoping *policy*
for every dashboard can be changed fleet-wide by editing one constant here.
"""

from django.db.models import Q

from .models import MstRig, MstUserRigMapping, ProjectContractDtl, UserProfile
from .permissions import get_user_access

# Dashboards are about drilling-fleet operations, not the handful of
# non-drilling "rig" rows the master data also carries (Repair Yard,
# Office, Well Service) — same convention the legacy analytics tools
# already used (only Rig_Type_Id 1/2 ever surfaced there). Applied via
# dashboard_rig_queryset() below, so every dashboard's rig list/filters
# stay in sync automatically rather than each view repeating this filter.
DASHBOARD_RIG_TYPE_IDS = [1, 2]  # Offshore Rig, Onshore Rig


def dashboard_rig_queryset():
    """Base MstRig queryset every dashboard should build its rig list
    from — already restricted to real drilling rig types."""
    return MstRig.objects.filter(rig_type_id__in=DASHBOARD_RIG_TYPE_IDS)


def current_contract_by_rig(rig_ids, today):
    """{rig_id: ProjectContractDtl} for whichever contract line is active
    today, for each of rig_ids — shared by Fleet Operating Picture and
    Contract Exposure so "what contract is this rig on right now" is
    defined exactly once. Overlapping lines for the same rig shouldn't
    normally happen; if they do, the most recently-started one wins."""
    lines = (
        ProjectContractDtl.objects.filter(rig_id__in=rig_ids, rig_active_from__lte=today)
        .filter(Q(rig_active_to__isnull=True) | Q(rig_active_to__gte=today))
        .select_related("contract", "contract__operator", "contract__location")
        .order_by("rig_id", "-rig_active_from")
    )
    result = {}
    for line in lines:
        result.setdefault(line.rig_id, line)
    return result

# Change this one value to change how EVERY analytics dashboard scopes rig
# visibility:
#   "strict"       - only real Django superusers see every rig; App Admins
#                    are scoped to their own User -> Rig Mapping rows same
#                    as any other user. Matches how Drilling Report itself
#                    scopes rig visibility today. (default)
#   "admin_bypass" - App Admins (is_app_admin, checked via
#                    permissions.get_user_access) also see every rig;
#                    ordinary users stay scoped to their own mappings.
#   "none"         - scoping switched off entirely; every authenticated
#                    user sees every rig's data.
DASHBOARD_RIG_SCOPE_MODE = "strict"


def get_accessible_rig_ids(request):
    """None means "no filter, show every rig". Otherwise a set of rig_ids
    to restrict a dashboard's queries to."""
    if DASHBOARD_RIG_SCOPE_MODE == "none":
        return None
    if request.user.is_superuser:
        return None
    if DASHBOARD_RIG_SCOPE_MODE == "admin_bypass" and get_user_access(request)["is_admin"]:
        return None
    try:
        uid = UserProfile.objects.get(user_login_id=request.user.username).user_id
    except UserProfile.DoesNotExist:
        return set()
    return set(
        MstUserRigMapping.objects.filter(user_id=uid, mapping_to__isnull=True).values_list("rig_id", flat=True)
    )
