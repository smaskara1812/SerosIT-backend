from rest_framework import serializers

from .media_uploads import media_url
from .models import (
    Incident,
    IncidentAction,
    IncidentPhoto,
    IncidentRootCause,
    MstContactExposureType,
    MstIncidentCause,
    MstIncidentSubcause,
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


class IncidentRootCauseSerializer(serializers.ModelSerializer):
    """Straight read/write shape for one Incident Root Cause row — legacy's
    own frmIncident_Root_Cause.aspx(.cs).

    Legacy required Root_Subcause_Others whenever the picked subcause's id
    was in a hardcoded list (196-207, one "Others" catch-all per cause
    category) — our mst_incident_subcause import was stale and didn't have
    those rows at first (same root cause as the Mail_Alert_Dtl/
    Mail_Alert_To_User staleness fixed earlier), now backfilled via
    import_mst_incident_subcause_full.sql. Rather than reproduce legacy's
    own hardcoded id list (which silently breaks the moment anyone edits
    the master), validate() below detects "Others" by name pattern
    instead — every one of those rows is actually named "Others (...)"."""

    rig_incident_no = serializers.CharField(source="incident.rig_incident_no", read_only=True, default="")
    rig_name = serializers.SerializerMethodField()
    incident_date = serializers.DateTimeField(source="incident.incident_date", read_only=True, default=None)
    root_cause_name = serializers.CharField(source="root_cause.incident_cause_desc", read_only=True, default="")
    root_subcause_name = serializers.CharField(source="root_subcause.incident_subcause", read_only=True, default="")

    incident = serializers.PrimaryKeyRelatedField(queryset=Incident.objects.all(), required=True)
    root_cause = serializers.PrimaryKeyRelatedField(queryset=MstIncidentCause.objects.all(), required=True)
    root_subcause = serializers.PrimaryKeyRelatedField(queryset=MstIncidentSubcause.objects.all(), required=True)

    class Meta:
        model = IncidentRootCause
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, data):
        subcause = data.get("root_subcause") or getattr(self.instance, "root_subcause", None)
        others = data.get("root_subcause_others") if "root_subcause_others" in data else getattr(
            self.instance, "root_subcause_others", None
        )
        if subcause and subcause.incident_subcause.strip().lower().startswith("others") and not (others or "").strip():
            raise serializers.ValidationError(
                {"root_subcause_others": "Enter a description for this 'Others' subcause."}
            )
        return data

    def get_rig_name(self, obj):
        if not obj.incident_id:
            return ""
        inc = obj.incident
        return inc.rig.rig_name if inc.rig_id else (inc.unit_name or "")


class IncidentActionSerializer(serializers.ModelSerializer):
    """Straight read/write shape for one Incident Action row — legacy's own
    frmIncident_Actions.aspx(.cs). Two real business rules verified against
    InsertUpdateData rather than guessed:
      - Filling Completion Dt (Actual Closure Date) always forces
        Action_Status to 'CL', overriding whatever the status dropdown
        says — enforced in perform_update below, not left to the client.
      - Target Date and Completion Dt, when given, must each be >= the
        incident's own Incident_Date — legacy's own compareDates() check.
        (The mirror check — Closed status requires a Completion Date — is
        present in legacy's client JS but its own `return false` is
        commented out, i.e. dead/non-enforced in the live app, so it's not
        reproduced here either.)"""

    rig_incident_no = serializers.CharField(source="incident.rig_incident_no", read_only=True, default="")
    rig_name = serializers.SerializerMethodField()
    well_no = serializers.CharField(source="incident.well_no", read_only=True, default="")
    incident_type_name = serializers.CharField(source="incident.incident_type.incident_type", read_only=True, default="")
    incident_date = serializers.DateTimeField(source="incident.incident_date", read_only=True, default=None)
    action_status_display = serializers.SerializerMethodField()

    incident = serializers.PrimaryKeyRelatedField(queryset=Incident.objects.all(), required=True)
    # Not required: IncidentActionViewSet.perform_create always sets it to
    # 'OP' itself (legacy never lets the Add form choose a status either —
    # the dropdown is disabled until an existing row is selected for
    # Update). Still writable on update — see Meta's own note below.
    action_status = serializers.CharField(required=False)

    class Meta:
        model = IncidentAction
        fields = "__all__"
        # action_status is client-settable (Open/Closed/In Process) except
        # for the one override in IncidentActionViewSet.perform_update: a
        # filled-in completion_dt always forces it to 'CL' server-side,
        # same as legacy — see that view's own docstring.
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def get_rig_name(self, obj):
        if not obj.incident_id:
            return ""
        inc = obj.incident
        return inc.rig.rig_name if inc.rig_id else (inc.unit_name or "")

    def get_action_status_display(self, obj):
        return {"OP": "Open", "CL": "Closed", "IN": "In Process"}.get(obj.action_status, obj.action_status)

    def validate(self, data):
        incident = data.get("incident") or getattr(self.instance, "incident", None)
        incident_date = incident.incident_date.date() if incident else None
        target_date = data.get("target_date") if "target_date" in data else getattr(self.instance, "target_date", None)
        completion_dt = data.get("completion_dt") if "completion_dt" in data else getattr(
            self.instance, "completion_dt", None
        )
        if incident_date and target_date and target_date < incident_date:
            raise serializers.ValidationError({"target_date": "Target Date must be on or after the Incident Date."})
        if incident_date and completion_dt and completion_dt < incident_date:
            raise serializers.ValidationError(
                {"completion_dt": "Actual Closure Date must be on or after the Incident Date."}
            )
        return data
