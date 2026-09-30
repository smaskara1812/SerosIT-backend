from rest_framework import serializers

from .models import HazardCard


class HazardCardDetailSerializer(serializers.ModelSerializer):
    """Full read/write shape for the QHSE → Hazard ID Card Add/Update page
    — distinct from reports_serializers.HazardCardSerializer, which is a
    trimmed list-shaped read model for the read-only Hazard Cards report.

    haz_id_card_no and contract are never client-writable: haz_id_card_no
    is assigned server-side at create (see HazardCardViewSet.perform_create),
    and contract is auto-resolved from whichever rig is picked (the rig's
    currently active ProjectContractDtl line) — the legacy form has no
    manual picker for it at all, only a read-only display, per
    Get_Prj_No_Operator_Location_Of_Rig.

    event_dt/close_out_dt need no custom field handling — settings.py's
    TIME_ZONE="Asia/Kolkata" + USE_TZ=False means every datetime in this
    app (including these, imported from legacy as raw IST wall-clock
    values) is naive and round-trips through DRF's default DateTimeField
    exactly as typed, with no UTC tagging or offset to strip. (An earlier
    version of this serializer had a NaiveDateTimeField that did that
    stripping by hand, from before the app-wide switch to USE_TZ=False —
    removed once confirmed redundant.)"""

    rig_name = serializers.CharField(source="rig.rig_name", read_only=True, default="")
    contract_label = serializers.SerializerMethodField()
    reported_by_fs_emp_name = serializers.SerializerMethodField()
    work_location_name = serializers.CharField(source="work_location.work_location", read_only=True, default="")
    haz_type_name = serializers.CharField(source="haz_type.haz_type_name", read_only=True, default="")
    resp_dept_name = serializers.CharField(source="resp_dept.vessel_dept_name", read_only=True, default="")
    resp_rank_name = serializers.CharField(source="resp_rank.rank_name", read_only=True, default="")

    class Meta:
        model = HazardCard
        fields = [
            "haz_card_id",
            "haz_id_card_no",
            "contract",
            "contract_label",
            "rig",
            "rig_name",
            "event_dt",
            "reported_by_party",
            "reported_by_fs_emp",
            "reported_by_fs_emp_name",
            "reported_by_name",
            "work_location",
            "work_location_name",
            "haz_type",
            "haz_type_name",
            "timeout_for_safety",
            "hazard_desc",
            "action_taken",
            "resp_dept",
            "resp_dept_name",
            "resp_rank",
            "resp_rank_name",
            "close_out_dt",
            "haz_id_card_status",
        ]
        read_only_fields = ["haz_card_id", "haz_id_card_no", "contract"]

    def get_contract_label(self, obj):
        if not obj.contract_id:
            return ""
        c = obj.contract
        return f"{c.prj_contract_no} ({c.operator.operator_name}) - {c.location.location_name}"

    def get_reported_by_fs_emp_name(self, obj):
        if not obj.reported_by_fs_emp_id:
            return ""
        e = obj.reported_by_fs_emp
        return " ".join(p for p in [e.emp_fname, e.emp_mname, e.emp_sname] if p)
