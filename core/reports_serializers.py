import datetime

from rest_framework import serializers

from .models import HazardCard, Incident

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
