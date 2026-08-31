import datetime

from rest_framework import serializers

from .models import HazardCard, Incident, MstItAsset

SEVERITY_LABELS = {"H": "High", "M": "Medium", "L": "Low"}


class IncidentSerializer(serializers.ModelSerializer):
    """List-shaped read model for the Incidents report — mirrors the columns
    serosIS's chatbot listing (get_incident_listing) surfaced, resolved
    through the now-real FKs instead of raw joins."""

    rig_name = serializers.CharField(source="rig.rig_name", read_only=True, default="Unknown")
    incident_type_name = serializers.CharField(source="incident_type.incident_type", read_only=True, default="")
    immediate_cause = serializers.CharField(
        source="immediate_incident_cause.incident_cause_desc", read_only=True, default=""
    )
    work_location_name = serializers.CharField(source="work_location.work_location", read_only=True, default="")
    severity_display = serializers.SerializerMethodField()
    person_injured_bool = serializers.SerializerMethodField()
    year = serializers.SerializerMethodField()

    class Meta:
        model = Incident
        fields = [
            "incident_id",
            "incident_no",
            "incident_date",
            "year",
            "rig",
            "rig_name",
            "incident_severity",
            "severity_display",
            "incident_type",
            "incident_type_name",
            "person_injured",
            "person_injured_bool",
            "npt_hrs_loss",
            "manhours_loss",
            "financial_loss_amt",
            "incident_descr",
            "immediate_cause",
            "immediate_cause_descr",
            "corrective_action",
            "preventive_action",
            "comments",
            "emp_name",
            "rank_name",
            "work_location_name",
            "drilling_superintendent",
            "safety_officer",
            "reported_by",
        ]

    def get_severity_display(self, obj):
        return SEVERITY_LABELS.get(obj.incident_severity, "Unknown")

    def get_person_injured_bool(self, obj):
        return obj.person_injured == "Y"

    def get_year(self, obj):
        return obj.incident_date.year


class HazardCardSerializer(serializers.ModelSerializer):
    """List-shaped read model for the Hazard Cards report — mirrors
    serosIS's get_hazard_card_listing columns."""

    rig_name = serializers.CharField(source="rig.rig_name", read_only=True, default="Unknown")
    haz_type_name = serializers.CharField(source="haz_type.haz_type_name", read_only=True, default="")
    work_location_name = serializers.CharField(source="work_location.work_location", read_only=True, default="")
    resp_dept_name = serializers.CharField(source="resp_dept.dept_dispname", read_only=True, default="")
    resp_rank_name = serializers.CharField(source="resp_rank.rank_name", read_only=True, default="")
    status_label = serializers.SerializerMethodField()
    tfs_bool = serializers.SerializerMethodField()
    age_days = serializers.SerializerMethodField()
    year = serializers.SerializerMethodField()

    class Meta:
        model = HazardCard
        fields = [
            "haz_card_id",
            "haz_id_card_no",
            "event_dt",
            "year",
            "rig",
            "rig_name",
            "haz_type",
            "haz_type_name",
            "work_location",
            "work_location_name",
            "haz_id_card_status",
            "status_label",
            "timeout_for_safety",
            "tfs_bool",
            "hazard_desc",
            "action_taken",
            "resp_dept_name",
            "resp_rank_name",
            "reported_by_name",
            "close_out_dt",
            "age_days",
        ]

    def get_status_label(self, obj):
        return "Closed" if obj.haz_id_card_status == "C" else "Open"

    def get_tfs_bool(self, obj):
        return obj.timeout_for_safety == "Y"

    def get_age_days(self, obj):
        end = obj.close_out_dt.date() if obj.close_out_dt else datetime.date.today()
        return (end - obj.event_dt.date()).days

    def get_year(self, obj):
        return obj.event_dt.year


class ItAssetReportSerializer(serializers.ModelSerializer):
    """Backs both of legacy's 'Select report' variants (Asset Report / Asset
    Tech Dtls) — a single row shape wide enough for either; the frontend
    just picks which columns to show. 'Current holder' is whichever of the
    asset's holder-history rows is still ongoing (no To date), prefetched
    via `current_holders` (see ItAssetReportViewSet.get_queryset) rather
    than queried per-row."""

    it_asset_type_name = serializers.CharField(source="it_asset_type.it_asset_type_name", read_only=True, default="")
    it_asset_subtype_name = serializers.CharField(
        source="it_asset_subtype.it_asset_subtype_name", read_only=True, default=""
    )
    it_asset_mfg_name = serializers.CharField(source="it_asset_mfg.it_asset_mfg_name", read_only=True, default="")
    it_asset_model_name = serializers.CharField(
        source="it_asset_model.it_asset_model_name", read_only=True, default=""
    )
    own_company_abrv = serializers.CharField(source="own_company.company_abrv", read_only=True, default="")
    vendor_name = serializers.CharField(source="vendor.vendor_name", read_only=True, default="")
    holder_name = serializers.SerializerMethodField()
    location_name = serializers.SerializerMethodField()
    holder_remark = serializers.SerializerMethodField()
    holding_company_abrv = serializers.SerializerMethodField()

    class Meta:
        model = MstItAsset
        fields = [
            "it_asset_id", "it_asset_type_name", "it_asset_sr_no", "it_asset_tag", "it_asset_sap_code",
            "it_asset_mfg_name", "it_asset_model_name", "it_asset_subtype_name", "it_asset_ram", "it_asset_hdd",
            "it_asset_particulars", "it_asset_product_no", "it_asset_mac_addr", "own_company_abrv",
            "vendor_name", "it_asset_pur_dt", "it_asset_warranty_upto", "it_asset_active",
            "holder_name", "location_name", "holder_remark", "holding_company_abrv",
        ]

    def _current_holder(self, obj):
        holders = getattr(obj, "current_holders", None)
        return holders[0] if holders else None

    def get_holder_name(self, obj):
        h = self._current_holder(obj)
        if not h:
            return ""
        if h.holder_user_id:
            return h.holder_user.user_name.strip()
        return str(h.emp) if h.emp_id else (h.holder_name or "")

    def get_location_name(self, obj):
        h = self._current_holder(obj)
        return h.company_loc.company_loc_name if h and h.company_loc_id else ""

    def get_holder_remark(self, obj):
        h = self._current_holder(obj)
        return (h.holder_remark or "") if h else ""

    def get_holding_company_abrv(self, obj):
        h = self._current_holder(obj)
        return h.holder_company.company_abrv if h and h.holder_company_id else ""
