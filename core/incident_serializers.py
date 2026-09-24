from rest_framework import serializers

from .media_uploads import media_url
from .models import (
    Incident,
    IncidentPhoto,
    MstContactExposureType,
    MstRig,
    MstRigOperation,
    MstWorkLocation,
)


class IncidentPhotoSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = IncidentPhoto
        fields = ["incident_photo_id", "incident_photo_path", "url"]

    def get_url(self, obj):
        return media_url(self.context.get("request"), obj.incident_photo_path)


class IncidentDetailSerializer(serializers.ModelSerializer):
    """Full read/write shape for the Incident Details Add/Update page —
    distinct from reports_serializers.IncidentSerializer, which is a
    trimmed list-shaped read model for the read-only Incidents report.

    financial_year and incident_no are never client-writable — both are
    resolved server-side once, at create time (see IncidentViewSet.
    perform_create) — so they're declared read-only here even though
    incident_no is a plain required IntegerField on the model."""

    rig_name = serializers.CharField(source="rig.rig_name", read_only=True, default="")
    incident_type_name = serializers.CharField(source="incident_type.incident_type", read_only=True, default="")
    immediate_incident_cause_name = serializers.CharField(
        source="immediate_incident_cause.incident_cause_desc", read_only=True, default=""
    )
    immediate_incident_cause_2_name = serializers.CharField(
        source="immediate_incident_cause_2.incident_cause_desc", read_only=True, default=""
    )
    rig_operation_name = serializers.CharField(source="rig_operation.rig_operation_name", read_only=True, default="")
    work_location_name = serializers.CharField(source="work_location.work_location", read_only=True, default="")
    contact_expo_type_name = serializers.CharField(
        source="contact_expo_type.contact_expo_type_name", read_only=True, default=""
    )
    country_name = serializers.CharField(source="country.country_name", read_only=True, default="")
    operator_name = serializers.CharField(source="operator.operator_name", read_only=True, default="")
    contractor_name = serializers.CharField(source="contractor.contractor_name", read_only=True, default="")
    financial_loss_currency_name = serializers.CharField(
        source="financial_loss_currency.currency_name", read_only=True, default=""
    )
    part_of_body_1_name = serializers.CharField(source="part_of_body_1.part_of_body_name", read_only=True, default="")
    part_of_body_2_name = serializers.CharField(source="part_of_body_2.part_of_body_name", read_only=True, default="")
    part_of_body_3_name = serializers.CharField(source="part_of_body_3.part_of_body_name", read_only=True, default="")
    part_of_body_4_name = serializers.CharField(source="part_of_body_4.part_of_body_name", read_only=True, default="")
    rptd_by_rank_name = serializers.CharField(source="rptd_by_rank.rank_name", read_only=True, default="")
    financial_year_text = serializers.CharField(source="financial_year.fin_year_text", read_only=True, default="")
    severity_display = serializers.SerializerMethodField()
    severity_potential_display = serializers.SerializerMethodField()
    photos = IncidentPhotoSerializer(many=True, read_only=True)

    # These four are nullable at the model level (the column itself allows
    # it, e.g. for older bulk-imported rows with gaps), but the live form
    # requires all four — matches the red asterisks in the actual UI spec,
    # not the column's own nullability.
    rig = serializers.PrimaryKeyRelatedField(queryset=MstRig.objects.all(), required=True)
    rig_operation = serializers.PrimaryKeyRelatedField(queryset=MstRigOperation.objects.all(), required=True)
    work_location = serializers.PrimaryKeyRelatedField(queryset=MstWorkLocation.objects.all(), required=True)
    contact_expo_type = serializers.PrimaryKeyRelatedField(
        queryset=MstContactExposureType.objects.all(), required=True
    )

    class Meta:
        model = Incident
        fields = "__all__"
        read_only_fields = ["incident_no", "financial_year", "cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def get_severity_display(self, obj):
        return {"H": "High", "M": "Medium", "L": "Low"}.get(obj.incident_severity, "")

    def get_severity_potential_display(self, obj):
        return {"H": "High", "M": "Medium", "L": "Low"}.get(obj.incident_severity_potential, "")
