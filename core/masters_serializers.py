from rest_framework import serializers

from .models import (
    DocToSignMapping,
    MstCertInstitute,
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
    MstEmployee,
    MstFsCategory,
    MstHazardType,
    MstHseActivity,
    MstHseConsumable,
    MstIndicatorSubtype,
    MstIndicatorType,
    MstInterviewer,
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
    ItAssetHolder,
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
    location_name = serializers.CharField(source="location.location_name", read_only=True, default="")

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
    location_name = serializers.CharField(source="location.location_name", read_only=True, default="")
    country_name = serializers.CharField(source="country.country_name", read_only=True, default="")

    class Meta:
        model = MstOperator
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


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


class FsCatgToRigTypeMappingSerializer(serializers.ModelSerializer):
    fs_category_name = serializers.CharField(
        source="fs_category.fs_category_name", read_only=True, default=""
    )
    rig_type_name = serializers.CharField(source="rig_type.rig_type_name", read_only=True, default="")

    class Meta:
        model = FsCatgToRigTypeMapping
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


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


class MstCompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = MstCompany
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


class CostCentreToCompanyMappingSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.company_name", read_only=True, default="")
    cost_centre_name = serializers.CharField(source="cost_centre.cost_centre_name", read_only=True, default="")
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = CostCentreToCompanyMapping
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def get_display_name(self, obj):
        return f"{obj.company.company_name} — {obj.cost_centre.cost_centre_name}"


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


class MstDrillingWorkShiftSerializer(serializers.ModelSerializer):
    work_shift_display = serializers.CharField(source="get_work_shift_display", read_only=True)
    rig_name = serializers.CharField(source="rig.rig_name", read_only=True, default="")
    contract_no = serializers.CharField(source="contract.prj_contract_no", read_only=True, default="")

    class Meta:
        model = MstDrillingWorkShift
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


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

    class Meta:
        model = MstxVendor
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


class MstCompanyLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MstCompanyLocation
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


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
    emp_name = serializers.SerializerMethodField()
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

    def get_emp_name(self, obj):
        return str(obj.emp) if obj.emp_id else ""
