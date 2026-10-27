import os
import re
from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from .media_uploads import media_url
from .validation_helpers import dms_error, fields_changed, phone_error


def _check_unique_name(serializer, attrs, field, what):
    """Refuse a name another record already has (ignoring capitals and spaces). Only when the
    name is new or changed, so an old record that repeats a name can still be edited."""
    if field not in attrs:
        return
    name = (attrs[field] or "").strip()
    attrs[field] = name
    inst = serializer.instance
    if name and fields_changed(inst, attrs, field):
        others = serializer.Meta.model.objects.filter(**{f"{field}__iexact": name})
        if inst is not None:
            others = others.exclude(pk=inst.pk)
        if others.exists():
            raise serializers.ValidationError({field: f"{what} named {name} already exists."})

from .models import (
    AlertSenderDtl,
    DocToSignMapping,
    MstSignableDoc,
    MstCert,
    MstCertInstitute,
    MstCertType,
    MstQualification,
    MstServType,
    MstServSubtype,
    MstFsCatgToSstype,
    MstIncidentType,
    MstIncidentCause,
    MstIncidentSubcause,
    MstWorkLocation,
    MstRelationDtl,
    MstLeavingReason,
    MstLeavingReasonDtl,
    MstBusinessSystem,
    MailAlertDtl,
    MailAlertToUser,
    MailRecipientMapping,
    NotificationTrigger,
    MstApprovalCode,
    MstCompetency,
    MstContactExposureType,
    MstContinent,
    MstCountry,
    MstCountryState,
    MstVesselDept,
    MstContractor,
    MstCostCentre,
    MstCostCentreType,
    MstDepartment,
    MstEmailNotificationType,
    MstFsCategory,
    MstHazardType,
    MstHseActivity,
    MstHseConsumable,
    MstHseDrill,
    MstHseManhoursParty,
    MstHseMeeting,
    MstIndicatorSubtype,
    MstIndicatorType,
    MstInterviewer,
    FsCatgToRankMapping,
    FsEmpCurStatus,
    MstFsEmployee,
    FsCatgToRigTypeMapping,
    RankClassification,
    MstEmpNature,
    MstEmpType,
    NationalityToEmpTypeMapping,
    CrewChangeRelieverMapping,
    MstWorkgroup,
    WkgrpIndicatorTypeMapping,
    MstOrganisationalGrp,
    MstBusinessGrp,
    MstCompany,
    CostCentreToCompanyMapping,
    CompanyToLocationMapping,
    RigSiteMapping,
    RigCrewException,
    CrewScheduleException,
    MstOperator,
    MstPartsOfBody,
    MstQhseCategory,
    MstRank,
    MstRig,
    MstRigType,
    MstRigSubtype,
    MstRigOperation,
    MstUser,
    MstUserFsCatgMapping,
    MstUserRigMapping,
    JobDescriptionDtl,
    JobDescriptionHdr,
    MstCurrency,
    MstDrillingOperation,
    MstDrillingRate,
    MstDrillingSection,
    MstDrillingWorkShift,
    MstLocation,
    ProjectContract,
    ProjectContractDtl,
    ProjectDrillingRate,
    ReportingStructure,
    TravelEligibility,
    MstItAssetType,
    MstItAssetSubtype,
    MstItAssetMfg,
    MstItAssetModel,
    MstxVendor,
    MstItAsset,
    MstCompanyLocation,
    MstCompanyLocType,
    MstCompanyLocOwnership,
    ItAssetHolder,
    MstVendorType,
    MstItAccessory,
    ItAccessoryHolder,
    MstFinancialYear,
    MstBussCertIssueAuthority,
    MstBussCertType,
    MstBussCert,
    RigCert,
    RigCertSchedule,
    MstActivity,
)


def _get(serializer, attrs, name):
    """The value being saved, falling back to the saved record's."""
    return attrs.get(name, getattr(serializer.instance, name, None))


def _changed(serializer, attrs, *names):
    return fields_changed(serializer.instance, attrs, *names)


def _check_active(serializer, attrs, errors, field="rig_active"):
    """Active is Y or N. Judged only when it is changed, so an old blank value can stay."""
    if field in attrs and _changed(serializer, attrs, field) and attrs[field] not in ("Y", "N"):
        errors[field] = "Choose Active or Inactive."


def _check_unique_value(serializer, attrs, errors, field, message):
    """Another record with this text (ignoring capitals and spaces) is refused, when it is new or changed."""
    if field not in attrs:
        return
    value = (attrs[field] or "").strip()
    attrs[field] = value
    if value and _changed(serializer, attrs, field):
        others = serializer.Meta.model.objects.filter(**{f"{field}__iexact": value})
        if serializer.instance is not None:
            others = others.exclude(pk=serializer.instance.pk)
        if others.exists():
            errors[field] = message.format(value=value)


def _check_date_not_future(serializer, attrs, errors, field, label):
    value = _get(serializer, attrs, field)
    if value and _changed(serializer, attrs, field) and value > timezone.now().date():
        errors[field] = f"{label} can't be in the future."


def _check_to_after_from(serializer, attrs, errors, start, end, label, equal_ok=True):
    a, b = _get(serializer, attrs, start), _get(serializer, attrs, end)
    if a and b and _changed(serializer, attrs, start, end) and (b < a if equal_ok else b <= a):
        errors[end] = f"{label} can't be before the From date." if equal_ok else f"{label} must be after the From date."


class MstDepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstDepartment
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstCostCentreTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstCostCentreType
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        errors = {}
        _check_unique_value(self, attrs, errors, "cost_centre_type_name", "A cost centre type named {value} already exists.")
        _check_unique_value(self, attrs, errors, "cost_centre_type_shortname", "A cost centre type with the short name {value} already exists.")
        _check_active(self, attrs, errors, "cost_centre_type_active")
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class MstContractorSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstContractor
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        errors = {}
        _check_unique_value(self, attrs, errors, "contractor_name", "A contractor named {value} already exists.")
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class MstCertInstituteSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.location_name", read_only=True, default="")

    class Meta:
        model = MstCertInstitute
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        tel = (attrs.get("tel_no") or "").strip()
        if "tel_no" in attrs:
            attrs["tel_no"] = tel
        if tel and _changed(self, attrs, "tel_no") and phone_error(tel):
            raise serializers.ValidationError({"tel_no": phone_error(tel)})
        return attrs


class MstEmailNotificationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstEmailNotificationType
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstOperatorSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.location_name", read_only=True, default="")
    country_name = serializers.CharField(source="country.country_name", read_only=True, default="")

    class Meta:
        model = MstOperator
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        errors = {}
        _check_unique_value(self, attrs, errors, "operator_name", "An operator named {value} already exists.")
        tel = (attrs.get("tel_no") or "").strip() if "tel_no" in attrs else None
        if tel is not None:
            attrs["tel_no"] = tel or None
            if tel and _changed(self, attrs, "tel_no"):
                if not re.fullmatch(r"[0-9+()/ -]+", tel):
                    errors["tel_no"] = "Telephone can have only digits and + - ( ) / and spaces."
                elif len(re.findall(r"\d", tel)) < 8:
                    errors["tel_no"] = "Telephone must have at least 8 digits."
        _check_active(self, attrs, errors, "operator_active")
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class MstRigTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstRigType
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstRigSubtypeSerializer(serializers.ModelSerializer):
    # Lets the Rigs form derive Rig Type straight from a picked Rig Subtype
    # without a second round trip.
    rig_type_name = serializers.CharField(source="rig_type.rig_type_name", read_only=True, default="")

    class Meta:
        model = MstRigSubtype
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstRigSerializer(serializers.ModelSerializer):
    rig_type_name = serializers.CharField(source="rig_type.rig_type_name", read_only=True, default="")
    rig_subtype_name = serializers.CharField(
        source="rig_subtype.rig_subtype_name", read_only=True, default=""
    )

    class Meta:
        model = MstRig
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        errors = {}
        name = (attrs.get("rig_name") or "").strip() if "rig_name" in attrs else None
        if name is not None:
            attrs["rig_name"] = name
            if name and _changed(self, attrs, "rig_name"):
                if not re.search(r"[A-Za-z]", name):
                    errors["rig_name"] = "Rig Name must contain letters."
                elif len(re.findall(r"\d", name)) > 2:
                    errors["rig_name"] = "Rig Name can have at most two digits."
        short = (attrs.get("rig_short_name") or "").strip() if "rig_short_name" in attrs else None
        if short is not None:
            attrs["rig_short_name"] = short
            if short and _changed(self, attrs, "rig_short_name") and not re.fullmatch(r"[A-Za-z0-9]+", short):
                errors["rig_short_name"] = "Short Name can have only letters and digits."
        _check_date_not_future(self, attrs, errors, "rig_built_dt", "Built date")
        for field, label in (("rig_tel_no", "Telephone"), ("rig_fax_no", "Fax")):
            value = (attrs.get(field) or "").strip() if field in attrs else None
            if value is not None:
                attrs[field] = value or None
                if value and _changed(self, attrs, field) and not re.fullmatch(r"[0-9/]+", value):
                    errors[field] = f"{label} can have only digits and forward slashes."
        built, start, end = (_get(self, attrs, f) for f in ("rig_built_dt", "rig_from", "rig_to"))
        if start and _changed(self, attrs, "rig_from"):
            if start > timezone.now().date():
                errors["rig_from"] = "From date can't be in the future."
            elif built and start < built:
                errors["rig_from"] = "From date can't be before the Built date."
        if end and _changed(self, attrs, "rig_from", "rig_to"):
            if start and end <= start:
                errors["rig_to"] = "To date must be after the From date."
            elif end > timezone.now().date():
                errors["rig_to"] = "To date can't be in the future."
        _check_active(self, attrs, errors, "rig_active")
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class MstCostCentreSerializer(serializers.ModelSerializer):
    cost_centre_type_name = serializers.CharField(
        source="cost_centre_type.cost_centre_type_name", read_only=True, default=""
    )
    rig_name = serializers.CharField(source="rig.rig_name", read_only=True, default="")
    fs_emp_name = serializers.SerializerMethodField()
    location_name = serializers.CharField(source="location.location_name", read_only=True, default="")

    class Meta:
        model = MstCostCentre
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        errors = {}
        _check_unique_value(self, attrs, errors, "cost_centre_name", "A cost centre named {value} already exists.")
        # A new cost centre needs its type, and a saved one can't lose it.
        if (self.instance is None or "cost_centre_type" in attrs) and _get(self, attrs, "cost_centre_type") is None:
            errors["cost_centre_type"] = "This field is required."
        _check_active(self, attrs, errors, "cost_centre_active")
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def get_fs_emp_name(self, obj):
        return str(obj.fs_emp) if obj.fs_emp_id else ""


class MstCompetencySerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(
        source="department.dept_dispname", read_only=True, default=""
    )

    class Meta:
        model = MstCompetency
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        errors = {}
        _check_active(self, attrs, errors, "active")
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class MstFsCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MstFsCategory
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstRankSerializer(serializers.ModelSerializer):
    fs_category_name = serializers.CharField(
        source="fs_category.fs_category_name", read_only=True, default=""
    )
    vessel_dept_name = serializers.CharField(
        source="vessel_dept.vessel_dept_name", read_only=True, default=""
    )

    class Meta:
        model = MstRank
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class JobDescriptionDtlSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobDescriptionDtl
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        errors = {}
        text = (attrs.get("jd_dtl_description") or "").strip() if "jd_dtl_description" in attrs else None
        if text is not None:
            attrs["jd_dtl_description"] = text
            if text and _changed(self, attrs, "jd_dtl_description") and len(text) < 10:
                errors["jd_dtl_description"] = "Give a fuller description (at least 10 characters)."
        header, order = _get(self, attrs, "header"), _get(self, attrs, "jd_dtl_order")
        if header and order is not None and _changed(self, attrs, "header", "jd_dtl_order"):
            repeats = JobDescriptionDtl.objects.filter(header=header, jd_dtl_order=order)
            if self.instance is not None:
                repeats = repeats.exclude(pk=self.instance.pk)
            if repeats.exists():
                errors["jd_dtl_order"] = f"Order {order} is already used under this heading."
        _check_active(self, attrs, errors, "jd_dtl_active")
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class JobDescriptionHdrSerializer(serializers.ModelSerializer):
    details = JobDescriptionDtlSerializer(many=True, read_only=True)

    class Meta:
        model = JobDescriptionHdr
        fields = "__all__"
        # fs_category is derived from rank in the view's perform_create, not
        # sent by the client — required-but-missing was exactly the 400.
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt", "fs_category"]

    def validate(self, attrs):
        errors = {}
        rank, order = _get(self, attrs, "rank"), _get(self, attrs, "jd_hdr_order")
        # The category follows the rank, so Category + Rank + Order is Rank + Order.
        if rank and order is not None and _changed(self, attrs, "rank", "jd_hdr_order"):
            repeats = JobDescriptionHdr.objects.filter(rank=rank, jd_hdr_order=order)
            if self.instance is not None:
                repeats = repeats.exclude(pk=self.instance.pk)
            if repeats.exists():
                errors["jd_hdr_order"] = f"Order {order} is already used for this rank."
        _check_active(self, attrs, errors, "jd_hdr_active")
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class TravelEligibilitySerializer(serializers.ModelSerializer):
    rank_name = serializers.CharField(source="rank.rank_name", read_only=True, default="")
    travel_mode_display = serializers.CharField(source="get_travel_mode_display", read_only=True)
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = TravelEligibility
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt", "fs_category"]

    def validate(self, attrs):
        errors = {}
        _check_date_not_future(self, attrs, errors, "eligible_from", "Eligible From")
        _check_to_after_from(self, attrs, errors, "eligible_from", "eligible_to", "Eligible To")
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def get_display_name(self, obj):
        return f"{obj.rank.rank_name} — {obj.get_travel_mode_display()}"


class ReportingStructureSerializer(serializers.ModelSerializer):
    rank_name = serializers.CharField(source="rank.rank_name", read_only=True, default="")
    reporting_rank_name = serializers.CharField(
        source="reporting_rank.rank_name", read_only=True, default=""
    )
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = ReportingStructure
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        category, rank = _get(self, attrs, "fs_category"), _get(self, attrs, "rank")
        if category and rank and _changed(self, attrs, "fs_category", "rank"):
            repeats = ReportingStructure.objects.filter(fs_category=category, rank=rank)
            if self.instance is not None:
                repeats = repeats.exclude(pk=self.instance.pk)
            if repeats.exists():
                raise serializers.ValidationError({"rank": "This rank already has a reporting line in this category."})
        return attrs

    def get_display_name(self, obj):
        if obj.reporting_rank_id:
            return f"{obj.rank.rank_name} → {obj.reporting_rank.rank_name}"
        return f"{obj.rank.rank_name} (top of chain)"


class MstRigOperationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstRigOperation
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstContactExposureTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstContactExposureType
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        _check_unique_name(self, attrs, "contact_expo_type_name", "A contact exposure type")
        return attrs


class MstIndicatorTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstIndicatorType
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt", "indicator_type_order"]


class MstIndicatorSubtypeSerializer(serializers.ModelSerializer):
    indicator_type_name = serializers.CharField(
        source="indicator_type.indicator_type_name", read_only=True, default=""
    )

    class Meta:
        model = MstIndicatorSubtype
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt", "indicator_subtype_order"]


class MstPartsOfBodySerializer(serializers.ModelSerializer):
    class Meta:
        model = MstPartsOfBody
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstQhseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MstQhseCategory
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        _check_unique_name(self, attrs, "qhse_category_name", "A QHSE category")
        return attrs


class MstHseActivitySerializer(serializers.ModelSerializer):
    hse_activity_type_display = serializers.CharField(
        source="get_hse_activity_type_display", read_only=True
    )

    class Meta:
        model = MstHseActivity
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        _check_unique_name(self, attrs, "hse_activity_name", "An HSE activity")
        return attrs


class MstHseConsumableSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstHseConsumable
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        _check_unique_name(self, attrs, "hse_consumable_name", "A consumable")
        return attrs


class MstHseManhoursPartySerializer(serializers.ModelSerializer):
    cost_centre_type_name = serializers.CharField(
        source="cost_centre_type.cost_centre_type_name", read_only=True, default=""
    )

    class Meta:
        model = MstHseManhoursParty
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        # A new party needs its Cost Centre Type, and a saved one can't lose it. (The same name and type
        # may appear more than once: the legacy data already has such pairs, and that is allowed.)
        if self.instance is None and attrs.get("cost_centre_type") is None:
            raise serializers.ValidationError({"cost_centre_type": "This field is required."})
        if self.instance is not None and "cost_centre_type" in attrs and attrs["cost_centre_type"] is None:
            raise serializers.ValidationError({"cost_centre_type": "This field is required."})
        return attrs


class MstHseMeetingSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstHseMeeting
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstHseDrillSerializer(serializers.ModelSerializer):
    """Mirrors legacy frmMst_HSE_Drill: Rig Type is a required Onshore/
    Offshore/Both choice ("Both" is stored as NULL, this form only), and a
    saved drill's Name/Frequency/Rig Type can never change — only Active.
    rig_type_choice is the form-facing value ("1"/"2"/"BOTH"); rig_type
    stays the real FK column."""

    RIG_TYPE_CHOICES = [("1", "Offshore Rig"), ("2", "Onshore Rig"), ("BOTH", "Both")]
    LOCKED_ON_EDIT = ("hse_drill_name", "hse_drill_frequency")

    hse_drill_frequency_display = serializers.CharField(source="get_hse_drill_frequency_display", read_only=True)
    rig_type_name = serializers.CharField(source="rig_type.rig_type_name", read_only=True, default="")
    rig_type_choice = serializers.ChoiceField(choices=RIG_TYPE_CHOICES, required=False)
    rig_type = serializers.PrimaryKeyRelatedField(read_only=True)
    hse_drill_active = serializers.ChoiceField(choices=("Y", "N"), required=False)

    class Meta:
        model = MstHseDrill
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["rig_type_choice"] = str(instance.rig_type_id) if instance.rig_type_id else "BOTH"
        if not instance.rig_type_id:
            data["rig_type_name"] = "Both"
        return data

    def validate(self, attrs):
        choice = attrs.pop("rig_type_choice", None)
        if self.instance is None:
            if not choice:
                raise serializers.ValidationError({"rig_type_choice": "This field is required."})
            if not attrs.get("hse_drill_name") or not attrs.get("hse_drill_frequency"):
                raise serializers.ValidationError("Drill Name and Frequency are required.")
        if choice:
            attrs["rig_type"] = None if choice == "BOTH" else MstRigType.objects.get(pk=int(choice))
        if self.instance is not None:
            for field in self.LOCKED_ON_EDIT:
                if field in attrs and attrs[field] != getattr(self.instance, field):
                    raise serializers.ValidationError({field: "Can't be changed once the drill is saved — deactivate it and add a new one."})
            if "rig_type" in attrs and (attrs["rig_type"].pk if attrs["rig_type"] else None) != self.instance.rig_type_id:
                raise serializers.ValidationError({"rig_type_choice": "Can't be changed once the drill is saved — deactivate it and add a new one."})
        return attrs


class MstHazardTypeSerializer(serializers.ModelSerializer):
    haz_type_active = serializers.ChoiceField(choices=("Y", "N"), required=False)

    class Meta:
        model = MstHazardType
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        _check_unique_name(self, attrs, "haz_type_name", "A hazard type")
        return attrs


class MstUserSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = MstUser
        # emp_id is the legacy employee number this user came from (a plain number, nothing is linked to it any more).
        fields = ["user_id", "user_name", "user_login_id", "emp_id", "display_name", "user_email"]

    def get_display_name(self, obj):
        return f"{obj.user_name} ({obj.user_login_id})"


class MstUserRigMappingSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user_login_id = serializers.CharField(source="user.user_login_id", read_only=True, default="")
    rig_name = serializers.CharField(source="rig.rig_name", read_only=True, default="")
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = MstUserRigMapping
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        errors = {}
        _check_date_not_future(self, attrs, errors, "mapping_from", "From date")
        _check_to_after_from(self, attrs, errors, "mapping_from", "mapping_to", "To date")
        user, target, start = (_get(self, attrs, f) for f in ("user", "rig", "mapping_from"))
        if user and target and start and _changed(self, attrs, "user", "rig", "mapping_from"):
            repeats = MstUserRigMapping.objects.filter(user=user, rig=target, mapping_from=start)
            if self.instance is not None:
                repeats = repeats.exclude(pk=self.instance.pk)
            if repeats.exists():
                errors.setdefault("mapping_from", "This user already has this mapping from this date.")
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def get_user_name(self, obj):
        return f"{obj.user.user_name} ({obj.user.user_login_id})"

    def get_display_name(self, obj):
        # A name HR recognizes, not a login id they'd have to look up.
        return f"{obj.user.user_name} — {obj.rig.rig_name}"


class MstUserFsCatgMappingSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user_login_id = serializers.CharField(source="user.user_login_id", read_only=True, default="")
    fs_category_name = serializers.CharField(
        source="fs_category.fs_category_name", read_only=True, default=""
    )
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = MstUserFsCatgMapping
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        errors = {}
        _check_date_not_future(self, attrs, errors, "mapping_from", "From date")
        _check_to_after_from(self, attrs, errors, "mapping_from", "mapping_to", "To date")
        user, target, start = (_get(self, attrs, f) for f in ("user", "fs_category", "mapping_from"))
        if user and target and start and _changed(self, attrs, "user", "fs_category", "mapping_from"):
            repeats = MstUserFsCatgMapping.objects.filter(user=user, fs_category=target, mapping_from=start)
            if self.instance is not None:
                repeats = repeats.exclude(pk=self.instance.pk)
            if repeats.exists():
                errors.setdefault("mapping_from", "This user already has this mapping from this date.")
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def get_user_name(self, obj):
        return f"{obj.user.user_name} ({obj.user.user_login_id})"

    def get_display_name(self, obj):
        return f"{obj.user.user_name} — {obj.fs_category.fs_category_name}"


class MstSignableDocSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstSignableDoc
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        errors = {}
        _check_unique_value(self, attrs, errors, "signable_doc_name", "A document named {value} already exists.")
        name = attrs.get("signable_doc_name")
        if name and _changed(self, attrs, "signable_doc_name") and not re.fullmatch(r"[A-Za-z0-9_]+", name):
            errors["signable_doc_name"] = "Use only letters, digits and underscores, like Offer_Ltr_Onshore (the document's template name)."
        _check_active(self, attrs, errors, "signable_doc_active")
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class DocToSignMappingSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user_label = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    sign_url = serializers.SerializerMethodField()

    class Meta:
        model = DocToSignMapping
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]
        # a legacy row always has its user now, and a new one must pick one
        extra_kwargs = {"user": {"required": True, "allow_null": False}}

    def validate(self, attrs):
        errors = {}
        if "doc_name" in attrs:
            attrs["doc_name"] = (attrs["doc_name"] or "").strip()
        if attrs.get("doc_name") and _changed(self, attrs, "doc_name") and not MstSignableDoc.objects.filter(signable_doc_name=attrs["doc_name"], signable_doc_active="Y").exists():
            errors["doc_name"] = "Choose a document from the list."
        # A new signature comes from the upload on the form (a file under signatures/); an old legacy path can stay as it is.
        path = (attrs.get("sign_path") or "").strip()
        if "sign_path" in attrs:
            attrs["sign_path"] = path or None
        if path and _changed(self, attrs, "sign_path") and not re.fullmatch(r"signatures/[A-Za-z0-9_.-]+", path):
            errors["sign_path"] = "Upload the signature image again."
        _check_date_not_future(self, attrs, errors, "sign_from", "From date")
        _check_to_after_from(self, attrs, errors, "sign_from", "sign_to", "To date")
        name, signer, start = (_get(self, attrs, f) for f in ("doc_name", "user", "sign_from"))
        if name and signer and start and _changed(self, attrs, "doc_name", "user", "sign_from"):
            repeats = DocToSignMapping.objects.filter(doc_name__iexact=name, user=signer, sign_from=start)
            if self.instance is not None:
                repeats = repeats.exclude(pk=self.instance.pk)
            if repeats.exists():
                errors.setdefault("sign_from", "This user already signs this document from this date.")
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def get_sign_url(self, obj):
        # A migrated row can still hold a legacy "/Images/..." path that is not a file here; only a real file gets a link.
        path = (obj.sign_path or "").lstrip("/")
        if not path or not os.path.isfile(os.path.join(settings.MEDIA_ROOT, path)):
            return None
        return media_url(self.context.get("request"), path)

    def get_user_name(self, obj):
        return obj.user.user_name.strip() if obj.user_id else ""

    def get_user_label(self, obj):
        """The user as the dropdown lists them ("Name (login id)"), so the saved value and the options read the same."""
        return f"{obj.user.user_name.strip()} ({obj.user.user_login_id})" if obj.user_id else ""

    def get_display_name(self, obj):
        return f"{obj.doc_name} — {self.get_user_name(obj)}"


class MstInterviewerSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user_login_id = serializers.CharField(source="user.user_login_id", read_only=True, default="")
    department_name = serializers.CharField(
        source="department.dept_dispname", read_only=True, default=""
    )
    sign_url = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = MstInterviewer
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        errors = {}
        _check_active(self, attrs, errors, "active")
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def get_user_name(self, obj):
        return f"{obj.user.user_name} ({obj.user.user_login_id})"

    def get_sign_url(self, obj):
        # only a real file gets a link (a legacy path whose file never came across shows no preview)
        path = (obj.sign_path or "").lstrip("/")
        if not path or not os.path.isfile(os.path.join(str(settings.MEDIA_ROOT), path)):
            return None
        return media_url(self.context.get("request"), obj.sign_path)

    def get_display_name(self, obj):
        return f"{obj.department.dept_dispname} — {obj.user.user_name}"


class FsCatgToRigTypeMappingSerializer(serializers.ModelSerializer):
    fs_category_name = serializers.CharField(
        source="fs_category.fs_category_name", read_only=True, default=""
    )
    rig_type_name = serializers.CharField(source="rig_type.rig_type_name", read_only=True, default="")

    class Meta:
        model = FsCatgToRigTypeMapping
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        errors = {}
        category, rig_type = _get(self, attrs, "fs_category"), _get(self, attrs, "rig_type")
        if category and rig_type and _changed(self, attrs, "fs_category", "rig_type"):
            repeats = FsCatgToRigTypeMapping.objects.filter(fs_category=category, rig_type=rig_type)
            if self.instance is not None:
                repeats = repeats.exclude(pk=self.instance.pk)
            if repeats.exists():
                errors["rig_type"] = "This category already has this rig type."
        _check_active(self, attrs, errors, "mapping_active")
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class RankClassificationSerializer(serializers.ModelSerializer):
    rank_name = serializers.CharField(source="rank.rank_name", read_only=True, default="")
    rank_class_display = serializers.CharField(source="get_rank_class_display", read_only=True)
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = RankClassification
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def get_display_name(self, obj):
        return f"{obj.rank.rank_name} — {obj.get_rank_class_display()}"


class MstEmpNatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstEmpNature
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstEmpTypeSerializer(serializers.ModelSerializer):
    emp_nature_name = serializers.CharField(source="emp_nature.emp_nature_name", read_only=True, default="")
    currency_abrv = serializers.CharField(source="currency.currency_abrv", read_only=True, default="")

    class Meta:
        model = MstEmpType
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class NationalityToEmpTypeMappingSerializer(serializers.ModelSerializer):
    fs_category_name = serializers.CharField(
        source="fs_category.fs_category_name", read_only=True, default=""
    )
    emp_type_name = serializers.CharField(source="emp_type.emp_type_name", read_only=True, default="")
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = NationalityToEmpTypeMapping
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        errors = {}
        category, nationality, emp_type = (_get(self, attrs, f) for f in ("fs_category", "nationality", "emp_type"))
        if category and nationality and emp_type and _changed(self, attrs, "fs_category", "nationality", "emp_type"):
            repeats = NationalityToEmpTypeMapping.objects.filter(fs_category=category, nationality=nationality, emp_type=emp_type)
            if self.instance is not None:
                repeats = repeats.exclude(pk=self.instance.pk)
            if repeats.exists():
                errors["emp_type"] = "This category, nationality and employee type are already mapped."
        _check_active(self, attrs, errors, "active")
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def get_display_name(self, obj):
        return f"{obj.fs_category.fs_category_name} — {obj.nationality} — {obj.emp_type.emp_type_name}"


class CrewChangeRelieverMappingSerializer(serializers.ModelSerializer):
    fs_category_name = serializers.CharField(
        source="fs_category.fs_category_name", read_only=True, default=""
    )
    rank_name = serializers.CharField(source="rank.rank_name", read_only=True, default="")
    reliever_rank_name = serializers.CharField(source="reliever_rank.rank_name", read_only=True, default="")
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = CrewChangeRelieverMapping
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def get_display_name(self, obj):
        return f"{obj.rank.rank_name} — {obj.reliever_rank.rank_name}"


class MstWorkgroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstWorkgroup
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class WkgrpIndicatorTypeMappingSerializer(serializers.ModelSerializer):
    workgroup_name = serializers.CharField(source="workgroup.workgroup_name", read_only=True, default="")
    indicator_type_name = serializers.CharField(
        source="indicator_type.indicator_type_name", read_only=True, default=""
    )
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = WkgrpIndicatorTypeMapping
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        workgroup, indicator = _get(self, attrs, "workgroup"), _get(self, attrs, "indicator_type")
        if workgroup and indicator and _changed(self, attrs, "workgroup", "indicator_type"):
            repeats = WkgrpIndicatorTypeMapping.objects.filter(workgroup=workgroup, indicator_type=indicator)
            if self.instance is not None:
                repeats = repeats.exclude(pk=self.instance.pk)
            if repeats.exists():
                raise serializers.ValidationError({"indicator_type": "This workgroup already has this indicator type."})
        return attrs

    def get_display_name(self, obj):
        return f"{obj.workgroup.workgroup_name} — {obj.indicator_type.indicator_type_name}"


class MstOrganisationalGrpSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstOrganisationalGrp
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstBusinessGrpSerializer(serializers.ModelSerializer):
    parent_business_grp_name = serializers.CharField(
        source="parent_business_grp.business_grp_name", read_only=True, default=""
    )

    class Meta:
        model = MstBusinessGrp
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        parent = attrs.get("parent_business_grp")
        if parent is not None and self.instance is not None and parent.pk == self.instance.pk:
            raise serializers.ValidationError({"parent_business_grp": "A business group can't be its own parent."})
        return attrs


class MstCompanySerializer(serializers.ModelSerializer):
    organisational_grp_name = serializers.CharField(
        source="organisational_grp.organisational_grp_name", read_only=True, default=""
    )
    business_grp_name = serializers.CharField(source="business_grp.business_grp_name", read_only=True, default="")
    parent_company_name = serializers.CharField(
        source="parent_company.company_name", read_only=True, default=""
    )
    country_name = serializers.CharField(source="country.country_name", read_only=True, default="")
    currency_name = serializers.CharField(source="currency.currency_name", read_only=True, default="")

    class Meta:
        model = MstCompany
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        parent = attrs.get("parent_company")
        if parent is not None and self.instance is not None and parent.pk == self.instance.pk:
            raise serializers.ValidationError({"parent_company": "A company can't be its own parent."})
        return attrs


class CostCentreToCompanyMappingSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.company_name", read_only=True, default="")
    cost_centre_name = serializers.CharField(source="cost_centre.cost_centre_name", read_only=True, default="")
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = CostCentreToCompanyMapping
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        errors = {}
        _check_date_not_future(self, attrs, errors, "mapping_from", "From date")
        _check_to_after_from(self, attrs, errors, "mapping_from", "mapping_to", "To date")
        company, cost_centre, start = (_get(self, attrs, f) for f in ("company", "cost_centre", "mapping_from"))
        if company and cost_centre and start and _changed(self, attrs, "company", "cost_centre", "mapping_from"):
            repeats = CostCentreToCompanyMapping.objects.filter(company=company, cost_centre=cost_centre, mapping_from=start)
            if self.instance is not None:
                repeats = repeats.exclude(pk=self.instance.pk)
            if repeats.exists():
                errors.setdefault("mapping_from", "This company and cost centre already have a mapping from this date.")
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def get_display_name(self, obj):
        return f"{obj.company.company_name} — {obj.cost_centre.cost_centre_name}"


class CompanyToLocationMappingSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.company_name", read_only=True, default="")
    company_loc_name = serializers.CharField(source="company_loc.company_loc_name", read_only=True, default="")
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = CompanyToLocationMapping
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def get_display_name(self, obj):
        return f"{obj.company.company_name} — {obj.company_loc.company_loc_name}"


class RigSiteMappingSerializer(serializers.ModelSerializer):
    rig_name = serializers.CharField(source="rig.rig_name", read_only=True, default="")
    company_name = serializers.CharField(source="company.company_name", read_only=True, default="")
    location_name = serializers.CharField(source="location.location_name", read_only=True, default="")
    contact_fs_emp_1_name = serializers.SerializerMethodField()
    contact_fs_emp_2_name = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = RigSiteMapping
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        errors = {}
        addr = (attrs.get("camp_office_addr") or "").strip() if "camp_office_addr" in attrs else None
        if addr is not None:
            attrs["camp_office_addr"] = addr
            if addr and _changed(self, attrs, "camp_office_addr") and len(addr) < 10:
                errors["camp_office_addr"] = "Enter the full camp office address (at least 10 characters)."
        for n in ("1", "2"):
            tel_field, person_field = f"contact_tel_no_{n}", f"contact_fs_emp_{n}"
            tel = (attrs.get(tel_field) or "").strip() if tel_field in attrs else None
            if tel is not None:
                attrs[tel_field] = tel or None
            tel = _get(self, attrs, tel_field) or ""
            if tel and _changed(self, attrs, tel_field):
                if not re.fullmatch(r"\d{7,10}", tel):
                    errors[tel_field] = "Enter a valid telephone number (7 to 10 digits, digits only)."
            if tel and _changed(self, attrs, tel_field, person_field) and _get(self, attrs, person_field) is None:
                errors.setdefault(tel_field, f"Enter Contact Person {n} for this telephone number.")
        first, second = _get(self, attrs, "contact_fs_emp_1"), _get(self, attrs, "contact_fs_emp_2")
        if first and second and first == second and _changed(self, attrs, "contact_fs_emp_1", "contact_fs_emp_2"):
            errors["contact_fs_emp_2"] = "Contact Person 2 must be a different person from Contact Person 1."
        _check_date_not_future(self, attrs, errors, "site_from", "From date")
        _check_to_after_from(self, attrs, errors, "site_from", "site_to", "To date")
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def get_contact_fs_emp_1_name(self, obj):
        return str(obj.contact_fs_emp_1) if obj.contact_fs_emp_1_id else ""

    def get_contact_fs_emp_2_name(self, obj):
        return str(obj.contact_fs_emp_2) if obj.contact_fs_emp_2_id else ""

    def get_display_name(self, obj):
        return f"{obj.rig.rig_name} — {obj.company.company_name}"


class RigCrewExceptionSerializer(serializers.ModelSerializer):
    fs_category_name = serializers.CharField(
        source="fs_category.fs_category_name", read_only=True, default=""
    )
    emp_type_name = serializers.CharField(source="emp_type.emp_type_name", read_only=True, default="")
    rank_name = serializers.CharField(source="rank.rank_name", read_only=True, default="")
    fs_emp_name = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = RigCrewException
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        errors = {}
        who = ("emp_type", "rank", "fs_emp")
        if all(_get(self, attrs, f) is None for f in who) and (self.instance is None or any(f in attrs for f in who)):
            errors["fs_emp"] = "Choose an Emp Type, a Rank or an Employee for this exception."
        _check_date_not_future(self, attrs, errors, "exception_from", "From date")
        _check_to_after_from(self, attrs, errors, "exception_from", "exception_to", "To date")
        category = _get(self, attrs, "fs_category")
        keys = ("fs_category", "emp_type", "rank", "fs_emp", "exception_to")
        if category and not errors and _changed(self, attrs, *keys):
            repeats = RigCrewException.objects.filter(**{f: _get(self, attrs, f) for f in keys})
            if self.instance is not None:
                repeats = repeats.exclude(pk=self.instance.pk)
            if repeats.exists():
                errors["exception_to"] = "This exception already exists."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def get_fs_emp_name(self, obj):
        return str(obj.fs_emp) if obj.fs_emp_id else ""

    def get_display_name(self, obj):
        exception_for = obj.fs_emp or obj.rank or obj.emp_type
        return f"{obj.fs_category.fs_category_name} — {exception_for}" if exception_for else obj.fs_category.fs_category_name


class CrewScheduleExceptionSerializer(serializers.ModelSerializer):
    fs_category_name = serializers.CharField(
        source="fs_category.fs_category_name", read_only=True, default=""
    )
    emp_type_name = serializers.CharField(source="emp_type.emp_type_name", read_only=True, default="")
    rank_name = serializers.CharField(source="rank.rank_name", read_only=True, default="")
    fs_emp_name = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = CrewScheduleException
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        errors = {}
        who = ("emp_type", "rank", "fs_emp")
        if all(_get(self, attrs, f) is None for f in who) and (self.instance is None or any(f in attrs for f in who)):
            errors["fs_emp"] = "Choose an Emp Type, a Rank or an Employee for this exception."
        _check_date_not_future(self, attrs, errors, "exception_from", "From date")
        _check_to_after_from(self, attrs, errors, "exception_from", "exception_to", "To date")
        category = _get(self, attrs, "fs_category")
        keys = ("fs_category", "emp_type", "rank", "fs_emp", "exception_to")
        if category and not errors and _changed(self, attrs, *keys):
            repeats = CrewScheduleException.objects.filter(**{f: _get(self, attrs, f) for f in keys})
            if self.instance is not None:
                repeats = repeats.exclude(pk=self.instance.pk)
            if repeats.exists():
                errors["exception_to"] = "This exception already exists."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def get_fs_emp_name(self, obj):
        return str(obj.fs_emp) if obj.fs_emp_id else ""

    def get_display_name(self, obj):
        exception_for = obj.fs_emp or obj.rank or obj.emp_type
        return f"{obj.fs_category.fs_category_name} — {exception_for}" if exception_for else obj.fs_category.fs_category_name


class MstContinentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstContinent
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstCountrySerializer(serializers.ModelSerializer):
    continent_name = serializers.CharField(source="continent.continent_name", read_only=True, default="")

    class Meta:
        model = MstCountry
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstCountryStateSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source="country.country_name", read_only=True, default="")

    class Meta:
        model = MstCountryState
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstVesselDeptSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstVesselDept
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstLocationSerializer(serializers.ModelSerializer):
    country_name = serializers.CharField(source="country.country_name", read_only=True, default="")
    country_state_name = serializers.CharField(
        source="country_state.country_state_name", read_only=True, default=""
    )

    class Meta:
        model = MstLocation
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstCurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = MstCurrency
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstDrillingRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstDrillingRate
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        # Active is Y or N. Judged only when it is changed, so the old rates with a blank Active still save.
        if "rate_active" in attrs and fields_changed(self.instance, attrs, "rate_active") and attrs["rate_active"] not in ("Y", "N"):
            raise serializers.ValidationError({"rate_active": "Choose Active or Inactive."})
        return attrs


class ProjectContractDtlSerializer(serializers.ModelSerializer):
    rig_name = serializers.CharField(source="rig.rig_name", read_only=True, default="")

    class Meta:
        model = ProjectContractDtl
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class ProjectContractSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.location_name", read_only=True, default="")
    operator_name = serializers.CharField(source="operator.operator_name", read_only=True, default="")
    display_name = serializers.SerializerMethodField()
    lines = ProjectContractDtlSerializer(many=True, read_only=True)

    class Meta:
        model = ProjectContract
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        inst = self.instance
        get = lambda name: attrs.get(name, getattr(inst, name, None))
        errors = {}
        if "prj_contract_no" in attrs:
            attrs["prj_contract_no"] = attrs["prj_contract_no"].strip()
        no = get("prj_contract_no")
        if no and fields_changed(inst, attrs, "prj_contract_no"):
            others = ProjectContract.objects.filter(prj_contract_no__iexact=no)
            if inst is not None:
                others = others.exclude(pk=inst.pk)
            if others.exists():
                errors["prj_contract_no"] = f"A contract numbered {no} already exists."
        # Short Name: required for a new contract; letters, digits and hyphens only (no spaces).
        short = (attrs.get("prj_short_name") or "").strip() if "prj_short_name" in attrs else (getattr(inst, "prj_short_name", None) or "")
        if "prj_short_name" in attrs:
            attrs["prj_short_name"] = short or None
        if inst is None and not short:
            errors["prj_short_name"] = "Enter the Short Name."
        elif short and fields_changed(inst, attrs, "prj_short_name") and not re.fullmatch(r"[A-Za-z0-9-]+", short):
            errors["prj_short_name"] = "Short Name can have only letters, digits and hyphens."
        start, end = get("prj_start_dt"), get("prj_end_dt")
        if start and fields_changed(inst, attrs, "prj_start_dt") and start > timezone.now().date():
            errors["prj_start_dt"] = "Start Date can't be in the future."
        if start and end and fields_changed(inst, attrs, "prj_start_dt", "prj_end_dt") and end < start:
            errors["prj_end_dt"] = "End Date can't be before the Start Date."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def get_display_name(self, obj):
        return f"{obj.prj_contract_no} — {obj.location.location_name}"


class ProjectDrillingRateSerializer(serializers.ModelSerializer):
    rate_code = serializers.CharField(source="drilling_rate.rate_code", read_only=True, default="")
    contract_no = serializers.CharField(source="contract.prj_contract_no", read_only=True, default="")
    rig_name = serializers.CharField(source="rig.rig_name", read_only=True, default="")
    currency_abrv = serializers.CharField(source="currency.currency_abrv", read_only=True, default="")
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = ProjectDrillingRate
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        inst = self.instance
        get = lambda name: attrs.get(name, getattr(inst, name, None))
        contract, rig, rate = get("contract"), get("rig"), get("drilling_rate")
        if contract and rig and rate and fields_changed(inst, attrs, "contract", "rig", "drilling_rate"):
            repeats = ProjectDrillingRate.objects.filter(contract=contract, rig=rig, drilling_rate=rate)
            if inst is not None:
                repeats = repeats.exclude(pk=inst.pk)
            if repeats.exists():
                raise serializers.ValidationError({"drilling_rate": "This rig already has this rate type on this contract."})
        return attrs

    def get_display_name(self, obj):
        return f"{obj.contract.prj_contract_no} — {obj.rig.rig_name} — {obj.drilling_rate.rate_code}"


class MstDrillingOperationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstDrillingOperation
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        inst = self.instance
        if "drilling_ops_code_no" in attrs and fields_changed(inst, attrs, "drilling_ops_code_no"):
            taken = MstDrillingOperation.objects.filter(drilling_ops_code_no=attrs["drilling_ops_code_no"])
            if inst is not None:
                taken = taken.exclude(pk=inst.pk)
            if taken.exists():
                raise serializers.ValidationError({"drilling_ops_code_no": f"Code No {attrs['drilling_ops_code_no']} is already used by another operation."})
        _check_unique_name(self, attrs, "drilling_ops_name", "An operation")
        return attrs


class MstDrillingSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstDrillingSection
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstDrillingWorkShiftSerializer(serializers.ModelSerializer):
    work_shift_display = serializers.CharField(source="get_work_shift_display", read_only=True)
    rig_name = serializers.CharField(source="rig.rig_name", read_only=True, default="")
    contract_no = serializers.CharField(source="contract.prj_contract_no", read_only=True, default="")

    class Meta:
        model = MstDrillingWorkShift
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    work_shift_active = serializers.ChoiceField(choices=("Y", "N"), required=False)

    def validate(self, attrs):
        if "work_shift_days" in attrs and attrs["work_shift_days"] not in (1, 2):
            raise serializers.ValidationError({"work_shift_days": "Shift Days must be 1 or 2."})
        return attrs


class MstItAssetTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstItAssetType
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstItAssetSubtypeSerializer(serializers.ModelSerializer):
    it_asset_type_name = serializers.CharField(
        source="it_asset_type.it_asset_type_name", read_only=True, default=""
    )

    class Meta:
        model = MstItAssetSubtype
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstItAssetMfgSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstItAssetMfg
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstItAssetModelSerializer(serializers.ModelSerializer):
    # Lets the IT Assets form derive Subtype/Type/Manufacturer straight from
    # a picked Model without a second round trip (same pattern as Rig
    # Subtype deriving Rig Type).
    it_asset_subtype_name = serializers.CharField(
        source="it_asset_subtype.it_asset_subtype_name", read_only=True, default=""
    )
    it_asset_type = serializers.IntegerField(
        source="it_asset_subtype.it_asset_type_id", read_only=True, default=None
    )
    it_asset_type_name = serializers.CharField(
        source="it_asset_subtype.it_asset_type.it_asset_type_name", read_only=True, default=""
    )
    it_asset_mfg_name = serializers.CharField(
        source="it_asset_mfg.it_asset_mfg_name", read_only=True, default=""
    )

    class Meta:
        model = MstItAssetModel
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstxVendorSerializer(serializers.ModelSerializer):
    vendor_type_name = serializers.CharField(
        source="vendor_type.vendor_type_name", read_only=True, default=""
    )
    country_name = serializers.CharField(source="country.country_name", read_only=True, default="")
    currency_name = serializers.CharField(
        source="currency.currency_name", read_only=True, default=""
    )

    class Meta:
        model = MstxVendor
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstVendorTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstVendorType
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstItAccessorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MstItAccessory
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstFinancialYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstFinancialYear
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstBussCertIssueAuthoritySerializer(serializers.ModelSerializer):
    class Meta:
        model = MstBussCertIssueAuthority
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstBussCertTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstBussCertType
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstBussCertSerializer(serializers.ModelSerializer):
    buss_cert_type_name = serializers.CharField(source="buss_cert_type.buss_cert_type", read_only=True, default="")

    class Meta:
        model = MstBussCert
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstCertTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstCertType
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstCertSerializer(serializers.ModelSerializer):
    cert_type_name = serializers.CharField(source="cert_type.cert_type_name", read_only=True, default="")
    vessel_dept_name = serializers.CharField(
        source="vessel_dept.vessel_dept_name", read_only=True, default=""
    )

    class Meta:
        model = MstCert
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstQualificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstQualification
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstServTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstServType
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstServSubtypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstServSubtype
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstFsCatgToSstypeSerializer(serializers.ModelSerializer):
    fs_category_name = serializers.CharField(source="fs_category.fs_category_name", read_only=True, default="")
    emp_type_name = serializers.CharField(source="emp_type.emp_type_name", read_only=True, default="")
    serv_type_name = serializers.CharField(source="serv_type.serv_type_name", read_only=True, default="")
    serv_subtype_name = serializers.CharField(source="serv_subtype.serv_subtype_name", read_only=True, default="")
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = MstFsCatgToSstype
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def get_display_name(self, obj):
        return f"{obj.fs_category.fs_category_name} — {obj.emp_type.emp_type_name} — {obj.serv_subtype.serv_subtype_name}"


class MstIncidentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstIncidentType
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstIncidentCauseSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstIncidentCause
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstIncidentSubcauseSerializer(serializers.ModelSerializer):
    incident_cause_desc = serializers.CharField(
        source="incident_cause.incident_cause_desc", read_only=True, default=""
    )

    class Meta:
        model = MstIncidentSubcause
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstWorkLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstWorkLocation
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstRelationDtlSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstRelationDtl
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstLeavingReasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstLeavingReason
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstLeavingReasonDtlSerializer(serializers.ModelSerializer):
    leaving_reason_name = serializers.CharField(
        source="leaving_reason.leaving_reason", read_only=True, default=""
    )

    class Meta:
        model = MstLeavingReasonDtl
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstBusinessSystemSerializer(serializers.ModelSerializer):
    # The mail account password is write-only: it is stored encrypted and never sent back (the form shows a blank box; leaving it blank on an
    # edit keeps the stored one).
    mail_user_password = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True, max_length=200)
    has_mail_password = serializers.SerializerMethodField()

    class Meta:
        model = MstBusinessSystem
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def get_has_mail_password(self, obj):
        return bool(obj.mail_user_password)

    def _protect(self, validated):
        from . import secret_box

        if "mail_user_password" in validated:
            if validated["mail_user_password"]:
                validated["mail_user_password"] = secret_box.encrypt(validated["mail_user_password"])
            else:
                validated.pop("mail_user_password")  # blank = keep what is stored
        return validated

    def create(self, validated_data):
        return super().create(self._protect(validated_data))

    def update(self, instance, validated_data):
        return super().update(instance, self._protect(validated_data))


class AlertSenderSerializer(serializers.ModelSerializer):
    """The password is write-only: stored encrypted, never sent back (the form shows a blank box; leaving it blank on an edit keeps the stored one)."""

    password = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True, max_length=200)
    has_password = serializers.SerializerMethodField()
    alert_name = serializers.CharField(source="alert.alert_name", read_only=True, default="")

    class Meta:
        model = AlertSenderDtl
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def get_has_password(self, obj):
        return bool(obj.password)

    def validate_mail_host(self, v):
        v = (v or "").strip()
        if not v or any(c in v for c in " /@\\"):
            raise serializers.ValidationError("Enter the mail server's name, for example smtp.example.com.")
        return v

    def validate_mail_port(self, v):
        if not 1 <= int(v) <= 65535:
            raise serializers.ValidationError("The port must be a number from 1 to 65535.")
        return v

    def validate_from_address(self, v):
        import re

        v = (v or "").strip()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", v):
            raise serializers.ValidationError("Enter the From address as an e-mail address.")
        return v

    def validate(self, data):
        active = data.get("is_active", getattr(self.instance, "is_active", "Y"))
        alert = data.get("alert", getattr(self.instance, "alert", None))
        if active == "Y" and alert is not None:
            others = AlertSenderDtl.objects.filter(alert=alert, is_active="Y")
            if self.instance is not None:
                others = others.exclude(pk=self.instance.pk)
            if others.exists():
                raise serializers.ValidationError({"alert": "This alert already has an active sender. Change that one, or switch it off first."})
        return data

    def _protect(self, validated):
        from . import secret_box

        if "password" in validated:
            if validated["password"]:
                validated["password"] = secret_box.encrypt(validated["password"])
            else:
                validated.pop("password")  # blank = keep what is stored
        return validated

    def create(self, validated_data):
        return super().create(self._protect(validated_data))

    def update(self, instance, validated_data):
        return super().update(instance, self._protect(validated_data))


class MailAlertDtlSerializer(serializers.ModelSerializer):
    class Meta:
        model = MailAlertDtl
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        # Next Mail must be filled for a new alert and can't be cleared on an old one; the many old alerts that have none can still be edited.
        had = self.instance is not None and self.instance.next_mail_dt is not None
        if (self.instance is None and not attrs.get("next_mail_dt")) or ("next_mail_dt" in attrs and not attrs["next_mail_dt"] and (self.instance is None or had)):
            raise serializers.ValidationError({"next_mail_dt": "Enter the date of the next mail."})
        return attrs


_ADDRESSEE_TYPE_LABELS = {"T": "To", "C": "Cc", "B": "Bcc"}


def _mail_alert_to_user_label(entry):
    """'AlertName — email@x.com (To)' — the same combined label everywhere
    this table shows up (its own list, and anywhere else it's picked by
    email alone, which is ambiguous since the same address can appear
    under several different alerts/addressee types)."""
    if entry is None:
        return ""
    alert_name = entry.alert.alert_name if entry.alert_id else ""
    type_label = _ADDRESSEE_TYPE_LABELS.get(entry.addressee_type, entry.addressee_type or "")
    return f"{alert_name} — {entry.email_addr} ({type_label})"


class MailAlertToUserSerializer(serializers.ModelSerializer):
    alert_name = serializers.CharField(source="alert.alert_name", read_only=True, default="")
    user_name = serializers.SerializerMethodField()
    user_label = serializers.SerializerMethodField()
    display_label = serializers.SerializerMethodField()

    class Meta:
        model = MailAlertToUser
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def get_user_name(self, obj):
        """Who the recipient is: the user's name, or the name typed for someone who is not a user."""
        return (obj.user.user_name.strip() if obj.user_id else (obj.recipient_name or "")) or ""

    def get_user_label(self, obj):
        """The user as the dropdown lists them ("Name (login id)"), so the saved value and the options read the same."""
        return f"{obj.user.user_name.strip()} ({obj.user.user_login_id})" if obj.user_id else ""

    def validate(self, attrs):
        errors = {}
        # The name is optional: a recipient can be just an email address. A blank name is stored as empty (not as spaces).
        if "recipient_name" in attrs:
            attrs["recipient_name"] = (attrs["recipient_name"] or "").strip() or None
        # The alert reaches this person from the From date until the To date (blank = still receiving). A From in the future is allowed.
        _check_to_after_from(self, attrs, errors, "mail_alert_from", "mail_alert_to", "To date")
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def get_display_label(self, obj):
        return _mail_alert_to_user_label(obj)


class MailRecipientMappingSerializer(serializers.ModelSerializer):
    approval_code_name = serializers.CharField(source="approval_code.approval_code", read_only=True, default="")
    event_type_display = serializers.CharField(source="get_event_type_display", read_only=True, default="")
    mail_alert_to_user_email = serializers.CharField(source="mail_alert_to_user.email_addr", read_only=True, default="")
    mail_alert_to_user_type = serializers.CharField(source="mail_alert_to_user.addressee_type", read_only=True, default="")
    mail_alert_to_user_label = serializers.SerializerMethodField()

    class Meta:
        model = MailRecipientMapping
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def get_mail_alert_to_user_label(self, obj):
        return _mail_alert_to_user_label(obj.mail_alert_to_user)


class NotificationTriggerSerializer(serializers.ModelSerializer):
    alert_name = serializers.CharField(source="alert.alert_name", read_only=True, default="")

    class Meta:
        model = NotificationTrigger
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class ItAccessoryHolderSerializer(serializers.ModelSerializer):
    it_accessory_name = serializers.CharField(
        source="it_accessory.it_accessory_name", read_only=True, default=""
    )
    it_asset_mfg_name = serializers.CharField(
        source="it_asset_mfg.it_asset_mfg_name", read_only=True, default=""
    )

    class Meta:
        model = ItAccessoryHolder
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstItAssetSerializer(serializers.ModelSerializer):
    it_asset_model_name = serializers.CharField(
        source="it_asset_model.it_asset_model_name", read_only=True, default=""
    )
    it_asset_type_name = serializers.CharField(
        source="it_asset_type.it_asset_type_name", read_only=True, default=""
    )
    it_asset_subtype_name = serializers.CharField(
        source="it_asset_subtype.it_asset_subtype_name", read_only=True, default=""
    )
    it_asset_mfg_name = serializers.CharField(
        source="it_asset_mfg.it_asset_mfg_name", read_only=True, default=""
    )
    own_company_name = serializers.CharField(
        source="own_company.company_name", read_only=True, default=""
    )
    cur_company_name = serializers.CharField(
        source="cur_company.company_name", read_only=True, default=""
    )
    vendor_name = serializers.CharField(source="vendor.vendor_name", read_only=True, default="")

    class Meta:
        model = MstItAsset
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstCompanyLocTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstCompanyLocType
        fields = "__all__"


class MstCompanyLocOwnershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstCompanyLocOwnership
        fields = "__all__"


class MstCompanyLocationSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.location_name", read_only=True, default="")
    country_name = serializers.CharField(source="country.country_name", read_only=True, default="")

    class Meta:
        model = MstCompanyLocation
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        errors = {}
        for field, axis in (("latitude", "lat"), ("longitude", "lon")):
            value = (attrs.get(field) or "").strip()
            if field in attrs:
                attrs[field] = value
            if value and _changed(self, attrs, field) and dms_error(value, axis):
                errors[field] = dms_error(value, axis)
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class ItAssetHolderSerializer(serializers.ModelSerializer):
    # Read-only context about the asset being (re)assigned — lets the IT
    # Assets Holder form show what it's holding without a second round trip,
    # the same way the IT Assets form derives Type/Subtype from Model.
    it_asset_sr_no = serializers.CharField(source="it_asset.it_asset_sr_no", read_only=True, default="")
    it_asset_tag = serializers.CharField(source="it_asset.it_asset_tag", read_only=True, default="")
    it_asset_sap_code = serializers.CharField(
        source="it_asset.it_asset_sap_code", read_only=True, default=""
    )
    it_asset_model_name = serializers.CharField(
        source="it_asset.it_asset_model.it_asset_model_name", read_only=True, default=""
    )
    it_asset_subtype_name = serializers.CharField(
        source="it_asset.it_asset_subtype.it_asset_subtype_name", read_only=True, default=""
    )
    it_asset_mfg_name = serializers.CharField(
        source="it_asset.it_asset_mfg.it_asset_mfg_name", read_only=True, default=""
    )
    it_asset_active = serializers.CharField(source="it_asset.it_asset_active", read_only=True, default="")
    own_company_name = serializers.CharField(
        source="it_asset.own_company.company_name", read_only=True, default=""
    )
    holder_company_name = serializers.CharField(
        source="holder_company.company_name", read_only=True, default=""
    )
    holder_company_abrv = serializers.CharField(
        source="holder_company.company_abrv", read_only=True, default=""
    )
    holder_user_name = serializers.SerializerMethodField()
    department_name = serializers.CharField(
        source="department.dept_dispname", read_only=True, default=""
    )
    department_abrv = serializers.CharField(source="department.dept_abrv", read_only=True, default="")
    company_loc_name = serializers.CharField(
        source="company_loc.company_loc_name", read_only=True, default=""
    )

    class Meta:
        model = ItAssetHolder
        fields = "__all__"
        read_only_fields = ["mod_user_id", "mod_dt"]

    def get_holder_user_name(self, obj):
        return obj.holder_user.user_name.strip() if obj.holder_user_id else ""


class MstApprovalCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstApprovalCode
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        errors = {}
        _check_unique_value(self, attrs, errors, "approval_code", "An approval code {value} already exists.")
        _check_active(self, attrs, errors, "approval_active")
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class RigCertSerializer(serializers.ModelSerializer):
    rig_name = serializers.CharField(source="rig.rig_name", read_only=True, default="")
    buss_cert_name = serializers.CharField(source="buss_cert.buss_cert_name", read_only=True, default="")
    buss_cert_issue_authority_name = serializers.CharField(
        source="buss_cert_issue_authority.buss_cert_issue_authority", read_only=True, default=""
    )
    # The legacy form's read-only "Validity" box — always just the linked
    # certificate's own text, read live off that FK rather than stored here.
    validity = serializers.CharField(source="buss_cert.buss_cert_validity", read_only=True, default="")
    certificate_url = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = RigCert
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def get_certificate_url(self, obj):
        path = (obj.certificate_path or "").lstrip("/")
        if not path or not os.path.isfile(os.path.join(str(settings.MEDIA_ROOT), path)):
            return None
        return media_url(self.context.get("request"), obj.certificate_path)

    def get_display_name(self, obj):
        return f"{obj.rig.rig_name} — {obj.buss_cert.buss_cert_name} ({obj.certificate_no})"

    def validate(self, attrs):
        inst = self.instance
        get = lambda name: attrs.get(name, getattr(inst, name, None))
        errors = {}
        if "certificate_no" in attrs:
            attrs["certificate_no"] = (attrs["certificate_no"] or "").strip()
        cert_date, valid_till = get("cert_date"), get("valid_till")
        if cert_date and fields_changed(inst, attrs, "cert_date") and cert_date > timezone.now().date():
            errors["cert_date"] = "Certificate Date can't be in the future."
        if cert_date and valid_till and fields_changed(inst, attrs, "cert_date", "valid_till") and valid_till <= cert_date:
            errors["valid_till"] = "Valid Till must be after the Certificate Date."
        others = RigCert.objects.exclude(pk=inst.pk) if inst else RigCert.objects.all()
        no = get("certificate_no")
        if no and fields_changed(inst, attrs, "certificate_no") and others.filter(certificate_no__iexact=no).exists():
            errors["certificate_no"] = f"Certificate No. {no} is already used."
        rig, cert = get("rig"), get("buss_cert")
        if rig and cert and cert_date and fields_changed(inst, attrs, "rig", "buss_cert", "cert_date") and others.filter(rig=rig, buss_cert=cert, cert_date=cert_date).exists():
            errors["cert_date"] = errors.get("cert_date") or "This rig already has this certificate dated that day."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class RigCertScheduleSerializer(serializers.ModelSerializer):
    rig_name = serializers.CharField(source="rig_cert.rig.rig_name", read_only=True, default="")
    rig_cert_display = serializers.SerializerMethodField()
    schedule_type_display = serializers.CharField(source="get_schedule_type_display", read_only=True)

    class Meta:
        model = RigCertSchedule
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def get_rig_cert_display(self, obj):
        return str(obj.rig_cert)

    def validate(self, attrs):
        inst = self.instance
        today = timezone.now().date()
        errors = {}
        scheduled = attrs.get("scheduled_dt", getattr(inst, "scheduled_dt", None))
        completed = attrs.get("completion_dt", getattr(inst, "completion_dt", None))
        if scheduled and fields_changed(inst, attrs, "scheduled_dt") and scheduled < today and not self.context.get("restoring"):
            errors["scheduled_dt"] = "Scheduled Date can't be in the past."
        if completed and fields_changed(inst, attrs, "completion_dt") and completed > today:
            errors["completion_dt"] = "Completion Date can't be in the future."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class MstActivitySerializer(serializers.ModelSerializer):
    activity_type_display = serializers.CharField(source="get_activity_type_display", read_only=True)
    activity_nature_display = serializers.CharField(source="get_activity_nature_display", read_only=True)
    activity_location_display = serializers.CharField(source="get_activity_location_display", read_only=True)

    class Meta:
        model = MstActivity
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class FsCatgToRankMappingSerializer(serializers.ModelSerializer):
    """Which ranks belong to an FS category. The vessel department is taken
    from the rank itself, so it isn't asked for."""

    fs_category_name = serializers.CharField(source="fs_category.fs_category_name", read_only=True, default="")
    rank_name = serializers.CharField(source="rank.rank_name", read_only=True, default="")
    vessel_dept_name = serializers.CharField(source="vessel_dept.vessel_dept_name", read_only=True, default="")

    class Meta:
        model = FsCatgToRankMapping
        fields = "__all__"
        read_only_fields = ["vessel_dept", "cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def validate(self, attrs):
        inst = self.instance
        category = attrs.get("fs_category", getattr(inst, "fs_category", None))
        rank = attrs.get("rank", getattr(inst, "rank", None))
        changed = inst is None or category != inst.fs_category or rank != inst.rank
        if changed and FsCatgToRankMapping.objects.filter(fs_category=category, rank=rank).exists():
            raise serializers.ValidationError({"rank": "This rank is already mapped to this category."})
        if rank is not None:
            attrs["vessel_dept"] = rank.vessel_dept
        return attrs


FS_FLAGS = (
    "fs_emp_temporary", "fs_emp_active", "pp_ecnr", "key_personnel",
    "vfd_rig_exp", "scr_rig_exp", "hpht_exp", "erd_exp", "nov_exp", "canrig_exp",
)


def _yes_no(value):
    """The legacy flags hold 'Y', 'N' or blank; blank means No."""
    return "Y" if value == "Y" else "N"


def _check_flags(attrs, names):
    for name in names:
        if name in attrs and attrs[name] not in ("Y", "N", "", None):
            raise serializers.ValidationError({name: "Choose Yes or No."})


class MstFsEmployeeSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    nationality_name = serializers.CharField(source="nationality.country_name", read_only=True)
    home_town_name = serializers.CharField(source="home_town.location_name", read_only=True, default="")
    domicile_state_name = serializers.CharField(source="domicile_state.country_state_name", read_only=True, default="")
    qualification_name = serializers.CharField(source="qualification.qualification_name", read_only=True, default="")
    pp_country_name = serializers.CharField(source="pp_country.country_name", read_only=True, default="")
    pp_place_name = serializers.CharField(source="pp_place.location_name", read_only=True, default="")
    cdc_country_name = serializers.CharField(source="cdc_country.country_name", read_only=True, default="")
    cdc_place_name = serializers.CharField(source="cdc_place.location_name", read_only=True, default="")
    fs_category_name = serializers.CharField(source="fs_category.fs_category_name", read_only=True)
    rank_name = serializers.CharField(source="rank.rank_name", read_only=True)
    emp_type_name = serializers.CharField(source="emp_type.emp_type_name", read_only=True)
    rig_name = serializers.CharField(source="rig.rig_name", read_only=True, default="")
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = MstFsEmployee
        fields = "__all__"
        # the photo path is only ever set by the photo upload endpoint (guarded, named by the employee id), never typed in
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt", "fs_emp_photo_path"]

    def get_full_name(self, obj):
        return str(obj)

    def get_photo_url(self, obj):
        """A signed link to the photo, only when the file is really in the media folder (a path carried over from the legacy system
        whose file never came across shows no photo; the old text stays in the record)."""
        path = obj.fs_emp_photo_path
        if not path or not os.path.isfile(os.path.join(str(settings.MEDIA_ROOT), path.lstrip("/"))):
            return None
        return media_url(self.context.get("request"), path)

    def validate(self, attrs):
        _check_flags(attrs, FS_FLAGS)
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for name in FS_FLAGS:
            data[name] = _yes_no(getattr(instance, name))
        return data


class FsEmpCurStatusSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    fs_emp_name = serializers.SerializerMethodField()
    fs_category_name = serializers.CharField(source="fs_category.fs_category_name", read_only=True)
    rank_name = serializers.CharField(source="rank.rank_name", read_only=True)
    emp_type_name = serializers.CharField(source="emp_type.emp_type_name", read_only=True)
    serv_type_name = serializers.CharField(source="serv_type.serv_type_name", read_only=True)
    serv_subtype_name = serializers.CharField(source="serv_subtype.serv_subtype_name", read_only=True)
    rig_name = serializers.CharField(source="rig.rig_name", read_only=True, default="")

    class Meta:
        model = FsEmpCurStatus
        fields = "__all__"
        read_only_fields = ["mod_user_id", "mod_dt"]
        # The default "already exists" text names the table; validate() says it plainly.
        extra_kwargs = {"fs_emp": {"validators": []}}

    def get_full_name(self, obj):
        return str(obj.fs_emp)

    def get_fs_emp_name(self, obj):
        return str(obj.fs_emp)

    def validate(self, attrs):
        _check_flags(attrs, ("fs_emp_active",))
        if self.instance is not None and "fs_emp" in attrs and attrs["fs_emp"] != self.instance.fs_emp:
            raise serializers.ValidationError({"fs_emp": "The employee can't be changed — add a status for the other person instead."})
        if self.instance is None and FsEmpCurStatus.objects.filter(pk=attrs["fs_emp"].pk).exists():
            raise serializers.ValidationError({"fs_emp": "This employee already has a status record."})
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["fs_emp_active"] = _yes_no(instance.fs_emp_active)
        return data
