from rest_framework import serializers

from .models import (
    DocToSignMapping,
    MstCertInstitute,
    MstCompetency,
    MstContactExposureType,
    MstContractor,
    MstCostCentre,
    MstCostCentreType,
    MstDepartment,
    MstEmailNotificationType,
    MstEmployee,
    MstFsCategory,
    MstHazardType,
    MstHseActivity,
    MstHseConsumable,
    MstIndicatorSubtype,
    MstIndicatorType,
    MstInterviewer,
    MstOperator,
    MstPartsOfBody,
    MstQhseCategory,
    MstRank,
    MstRig,
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
    MstLocation,
    ProjectContract,
    ProjectContractDtl,
    ProjectDrillingRate,
    ReportingStructure,
    TravelEligibility,
)


class MstDepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstDepartment
        fields = "__all__"


class MstCostCentreTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstCostCentreType
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstContractorSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstContractor
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstCertInstituteSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstCertInstitute
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstEmailNotificationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstEmailNotificationType
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstOperatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstOperator
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstRigSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstRig
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstCostCentreSerializer(serializers.ModelSerializer):
    cost_centre_type_name = serializers.CharField(
        source="cost_centre_type.cost_centre_type_name", read_only=True, default=""
    )
    rig_name = serializers.CharField(source="rig.rig_name", read_only=True, default="")

    class Meta:
        model = MstCostCentre
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstCompetencySerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(
        source="department.dept_dispname", read_only=True, default=""
    )

    class Meta:
        model = MstCompetency
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstFsCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MstFsCategory
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstRankSerializer(serializers.ModelSerializer):
    fs_category_name = serializers.CharField(
        source="fs_category.fs_category_name", read_only=True, default=""
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


class JobDescriptionHdrSerializer(serializers.ModelSerializer):
    details = JobDescriptionDtlSerializer(many=True, read_only=True)

    class Meta:
        model = JobDescriptionHdr
        fields = "__all__"
        # fs_category is derived from rank in the view's perform_create, not
        # sent by the client — required-but-missing was exactly the 400.
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt", "fs_category"]


class TravelEligibilitySerializer(serializers.ModelSerializer):
    rank_name = serializers.CharField(source="rank.rank_name", read_only=True, default="")
    travel_mode_display = serializers.CharField(source="get_travel_mode_display", read_only=True)
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = TravelEligibility
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt", "fs_category"]

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


class MstHseActivitySerializer(serializers.ModelSerializer):
    hse_activity_type_display = serializers.CharField(
        source="get_hse_activity_type_display", read_only=True
    )

    class Meta:
        model = MstHseActivity
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstHseConsumableSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstHseConsumable
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstHazardTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstHazardType
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstUserSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = MstUser
        fields = ["user_id", "user_name", "user_login_id", "display_name"]

    def get_display_name(self, obj):
        return f"{obj.user_name} ({obj.user_login_id})"


class MstEmployeeSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = MstEmployee
        fields = ["emp_id", "emp_fname", "emp_mname", "emp_sname", "display_name"]

    def get_display_name(self, obj):
        return str(obj)


class MstUserRigMappingSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user_login_id = serializers.CharField(source="user.user_login_id", read_only=True, default="")
    rig_name = serializers.CharField(source="rig.rig_name", read_only=True, default="")
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = MstUserRigMapping
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

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

    def get_user_name(self, obj):
        return f"{obj.user.user_name} ({obj.user.user_login_id})"

    def get_display_name(self, obj):
        return f"{obj.user.user_name} — {obj.fs_category.fs_category_name}"


class DocToSignMappingSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee", read_only=True, default="")
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = DocToSignMapping
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def get_display_name(self, obj):
        return f"{obj.doc_name} — {obj.employee}"


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

    def get_user_name(self, obj):
        return f"{obj.user.user_name} ({obj.user.user_login_id})"

    def get_sign_url(self, obj):
        if not obj.sign_path:
            return None
        request = self.context.get("request")
        from django.conf import settings

        url = settings.MEDIA_URL + obj.sign_path
        return request.build_absolute_uri("/" + url) if request else url

    def get_display_name(self, obj):
        return f"{obj.department.dept_dispname} — {obj.user.user_name}"


class MstLocationSerializer(serializers.ModelSerializer):
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

    def get_display_name(self, obj):
        return f"{obj.contract.prj_contract_no} — {obj.rig.rig_name} — {obj.drilling_rate.rate_code}"


class MstDrillingOperationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstDrillingOperation
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class MstDrillingSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstDrillingSection
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]
