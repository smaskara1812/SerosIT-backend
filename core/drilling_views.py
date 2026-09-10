from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .drilling_serializers import DrillingHdrSerializer
from .masters_views import BaseMasterViewSet
from .models import DrillingHdr, MstRig, MstUserRigMapping, ProjectContractDtl, UserProfile


class DrillingHdrViewSet(BaseMasterViewSet):
    """Drilling Information — one record per well/rig-move. Rig assignment
    on the contract is scoped to whatever the current user is actually
    mapped to (see rig_options_api), but that scoping is only enforced at
    pick-time on the frontend; this endpoint itself lists/edits every row
    like any other master."""

    queryset = DrillingHdr.objects.select_related("contract", "rig", "drilling_rate").all()
    serializer_class = DrillingHdrSerializer
    entity_key = "drilling.drilling_information"
    name_field = "location"
    search_fields = ["location", "rig__rig_name", "contract__prj_contract_no"]
    # latitude_decimal/longitude_decimal exist only to feed the map widget —
    # not real column data, so left out of the CSV alongside the actual
    # latitude/longitude strings.
    export_exclude_fields = ["latitude_decimal", "longitude_decimal"]

    def get_queryset(self):
        qs = self.queryset
        params = self.request.query_params
        contract_id = params.get("contract")
        rig_id = params.get("rig")
        drilling_rate_id = params.get("drilling_rate")
        date_from = params.get("date_from")
        date_to = params.get("date_to")
        if contract_id:
            qs = qs.filter(contract_id=contract_id)
        if rig_id:
            qs = qs.filter(rig_id=rig_id)
        if drilling_rate_id:
            qs = qs.filter(drilling_rate_id=drilling_rate_id)
        if date_from:
            qs = qs.filter(first_anchor_down_dt__date__gte=date_from)
        if date_to:
            qs = qs.filter(first_anchor_down_dt__date__lte=date_to)
        return qs.order_by("-first_anchor_down_dt")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def rig_options_api(request):
    """Rigs available to pick for the Drilling Information form's Rig field
    — the intersection of "actively assigned to the selected Project" and
    "the current user is actively mapped to this Rig" (see the legacy
    note's step 2 + 2.1: this mirrors that two-part filter exactly)."""
    project_id = request.query_params.get("project")
    if not project_id:
        return Response([])

    project_rig_ids = ProjectContractDtl.objects.filter(
        contract_id=project_id, rig_active_to__isnull=True
    ).values_list("rig_id", flat=True)

    try:
        profile_user_id = UserProfile.objects.get(user_login_id=request.user.username).user_id
    except UserProfile.DoesNotExist:
        profile_user_id = None

    if request.user.is_superuser or profile_user_id is None:
        # Superuser (no Mst_User row of their own) or an unmapped profile —
        # fall back to every rig active on the project rather than an
        # empty list, so admin/testing accounts aren't locked out.
        my_rig_ids = None
    else:
        my_rig_ids = MstUserRigMapping.objects.filter(
            user_id=profile_user_id, mapping_to__isnull=True
        ).values_list("rig_id", flat=True)

    rig_ids = set(project_rig_ids)
    if my_rig_ids is not None:
        rig_ids &= set(my_rig_ids)

    rigs = MstRig.objects.filter(rig_id__in=rig_ids).order_by("rig_name")
    return Response([{"rig_id": r.rig_id, "rig_name": r.rig_name} for r in rigs])
