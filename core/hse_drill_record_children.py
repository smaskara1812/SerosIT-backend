"""QHSE → HSE Drills / Exercises — the four text-only child tables shown
as tabs on the legacy frmHSE_Drill_Record_Hdr_Details.aspx page: Events,
Observations, Improvements, Corrective Action. (Photo Upload is the fifth
tab and stays separate — file handling, not a plain CRUD grid.)

All four are the exact same shape in legacy (frmHSE_Drill_Record_Event/
Observation/Improvement/Corrective_Action.aspx(.cs)): a grid scoped to one
Drill Record Hdr at a time, footer-row Insert, per-row Edit/Delete, no
soft-delete, no extra business rules — so unlike incident_views.py's
per-feature classes, these four are kept intentionally terse rather than
each re-explaining the same shape. Events carries one extra field (a
per-line time, stored as a full datetime — see HseDrillRecordEvent's own
model docstring for why) that the other three don't have.

BaseMasterViewSet's own perform_create/perform_update/destroy already do
everything these need (cr_/mod_ stamping, audit logging, clean 400 on a
blocked delete) — none of these four override them.

All four share the parent header's own entity_key ("qhse.hse_drill_record")
rather than getting one each — legacy threads a single intMenu_id through
every child iframe's querystring (see fmHSE_Drill_Record_Hdr_Details.aspx.cs
btnEvents_Click etc.), i.e. one menu/permission entry governs the header
page and every tab under it, not one per tab. Mirrored here rather than
minting four more sys_menu rows nobody would ever grant separately."""

from rest_framework import serializers

from .masters_views import BaseMasterViewSet
from .models import (
    HseDrillRecordCorrectiveAction,
    HseDrillRecordEvent,
    HseDrillRecordImprovement,
    HseDrillRecordObservation,
)
from .permissions import HasMenuPermission

_AUDIT_READ_ONLY = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class HseDrillRecordEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = HseDrillRecordEvent
        fields = "__all__"
        read_only_fields = _AUDIT_READ_ONLY
        extra_kwargs = {"drill_rec_event_desc": {"required": True, "allow_blank": False, "allow_null": False}}


class HseDrillRecordObservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = HseDrillRecordObservation
        fields = "__all__"
        read_only_fields = _AUDIT_READ_ONLY
        extra_kwargs = {"drill_rec_observation_desc": {"required": True, "allow_blank": False, "allow_null": False}}


class HseDrillRecordImprovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = HseDrillRecordImprovement
        fields = "__all__"
        read_only_fields = _AUDIT_READ_ONLY
        extra_kwargs = {"drill_rec_improvement_desc": {"required": True, "allow_blank": False, "allow_null": False}}


class HseDrillRecordCorrectiveActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = HseDrillRecordCorrectiveAction
        fields = "__all__"
        read_only_fields = _AUDIT_READ_ONLY
        extra_kwargs = {
            "drill_rec_corrective_action_desc": {"required": True, "allow_blank": False, "allow_null": False}
        }


class _HseDrillChildViewSet(BaseMasterViewSet):
    """Shared scoping for all four: list is always for one header at a
    time (?hdr=<drill_record_hdr_id>), same as the legacy grid, which only
    ever shows rows for whichever header the iframe was opened for."""

    permission_classes = [HasMenuPermission]
    desc_field = None  # set by subclass — used for both ordering fallback and label_for

    def get_queryset(self):
        qs = self.queryset
        hdr_id = self.request.query_params.get("hdr")
        if hdr_id:
            qs = qs.filter(hdr_id=hdr_id)
        return qs.order_by(self.order_field)

    def label_for(self, instance):
        desc = getattr(instance, self.desc_field) or ""
        return f"{instance.hdr.drill_record_no} — {desc[:40]}"


class HseDrillRecordEventViewSet(_HseDrillChildViewSet):
    queryset = HseDrillRecordEvent.objects.select_related("hdr")
    serializer_class = HseDrillRecordEventSerializer
    entity_key = "qhse.hse_drill_record"
    desc_field = "drill_rec_event_desc"
    order_field = "drill_rec_event_time"


class HseDrillRecordObservationViewSet(_HseDrillChildViewSet):
    queryset = HseDrillRecordObservation.objects.select_related("hdr")
    serializer_class = HseDrillRecordObservationSerializer
    entity_key = "qhse.hse_drill_record"
    desc_field = "drill_rec_observation_desc"
    order_field = "drill_rec_observation_id"


class HseDrillRecordImprovementViewSet(_HseDrillChildViewSet):
    queryset = HseDrillRecordImprovement.objects.select_related("hdr")
    serializer_class = HseDrillRecordImprovementSerializer
    entity_key = "qhse.hse_drill_record"
    desc_field = "drill_rec_improvement_desc"
    order_field = "drill_rec_improvement_id"


class HseDrillRecordCorrectiveActionViewSet(_HseDrillChildViewSet):
    queryset = HseDrillRecordCorrectiveAction.objects.select_related("hdr")
    serializer_class = HseDrillRecordCorrectiveActionSerializer
    entity_key = "qhse.hse_drill_record"
    desc_field = "drill_rec_corrective_action_desc"
    order_field = "drill_rec_corrective_action_id"
