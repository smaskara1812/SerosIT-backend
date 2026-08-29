import datetime

from django.db.models import ProtectedError
from django.db.models.functions import Coalesce
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import audit as _audit
from .models import (
    DocToSignMapping,
    JobDescriptionDtl,
    JobDescriptionHdr,
    MstCertInstitute,
    MstCompetency,
    MstContinent,
    MstCountry,
    MstCountryState,
    MstVesselDept,
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
    UserProfile,
    MstItAssetType,
    MstItAssetSubtype,
    MstItAssetMfg,
    MstItAssetModel,
    MstxVendor,
    MstItAsset,
    MstCompanyLocation,
    ItAssetHolder,
)
from .masters_serializers import (
    DocToSignMappingSerializer,
    JobDescriptionDtlSerializer,
    JobDescriptionHdrSerializer,
    MstCertInstituteSerializer,
    MstCompetencySerializer,
    MstContinentSerializer,
    MstCountrySerializer,
    MstCountryStateSerializer,
    MstVesselDeptSerializer,
    MstContactExposureTypeSerializer,
    MstContractorSerializer,
    MstCostCentreSerializer,
    MstCostCentreTypeSerializer,
    MstDepartmentSerializer,
    MstEmailNotificationTypeSerializer,
    MstEmployeeSerializer,
    MstFsCategorySerializer,
    MstHazardTypeSerializer,
    MstHseActivitySerializer,
    MstHseConsumableSerializer,
    MstIndicatorSubtypeSerializer,
    MstIndicatorTypeSerializer,
    MstInterviewerSerializer,
    FsCatgToRigTypeMappingSerializer,
    RankClassificationSerializer,
    MstEmpNatureSerializer,
    MstEmpTypeSerializer,
    NationalityToEmpTypeMappingSerializer,
    CrewChangeRelieverMappingSerializer,
    MstWorkgroupSerializer,
    WkgrpIndicatorTypeMappingSerializer,
    MstOrganisationalGrpSerializer,
    MstBusinessGrpSerializer,
    MstCompanySerializer,
    CostCentreToCompanyMappingSerializer,
    RigSiteMappingSerializer,
    RigCrewExceptionSerializer,
    CrewScheduleExceptionSerializer,
    MstOperatorSerializer,
    MstPartsOfBodySerializer,
    MstQhseCategorySerializer,
    MstRankSerializer,
    MstRigSerializer,
    MstRigTypeSerializer,
    MstRigSubtypeSerializer,
    MstRigOperationSerializer,
    MstUserSerializer,
    MstUserFsCatgMappingSerializer,
    MstUserRigMappingSerializer,
    MstCurrencySerializer,
    MstDrillingOperationSerializer,
    MstDrillingRateSerializer,
    MstDrillingSectionSerializer,
    MstDrillingWorkShiftSerializer,
    MstLocationSerializer,
    ProjectContractDtlSerializer,
    ProjectContractSerializer,
    ProjectDrillingRateSerializer,
    ReportingStructureSerializer,
    TravelEligibilitySerializer,
    MstItAssetTypeSerializer,
    MstItAssetSubtypeSerializer,
    MstItAssetMfgSerializer,
    MstItAssetModelSerializer,
    MstxVendorSerializer,
    MstItAssetSerializer,
    MstCompanyLocationSerializer,
    ItAssetHolderSerializer,
)
from .permissions import HasMenuPermission, HasMenuPermissionOrOpenRead


class BaseMasterViewSet(viewsets.ModelViewSet):
    """
    Shared CRUD behaviour for the simple lookup-table masters: gated by the
    real per-action User Rights permission (view/add/edit/delete on
    entity_key), stamps cr_/mod_ user+timestamp, audits create/update/delete,
    and turns a blocked delete (FK still points at this row) into a clean 400
    instead of a raw database error.

    Subclasses set: entity_key (audit/menu key), name_field (for audit
    labels and default ordering), reference_checks (list of
    (related_manager_accessor, human_label) — every other in-schema master
    that FKs to this one, so check-delete/destroy can report exactly what's
    blocking a deletion instead of a raw DB error).
    """

    permission_classes = [HasMenuPermission]
    entity_key = None
    name_field = None
    reference_checks = []

    def get_queryset(self):
        return self.queryset.order_by(self.name_field)

    def label_for(self, instance):
        """Override when the model has no plain name_field (e.g. FK-combo
        rows like TravelEligibility) to build a readable audit label."""
        return getattr(instance, self.name_field, "")

    def _current_user_id(self, request):
        try:
            return UserProfile.objects.get(user_login_id=request.user.username).user_id
        except UserProfile.DoesNotExist:
            return None

    # Fields that are bookkeeping, not user-entered data — never shown in a diff.
    _AUDIT_SKIP = {"cr_user_id", "cr_dt", "mod_user_id", "mod_dt"}

    def _snapshot(self, instance):
        """{field_name: value} for every real field on the instance, skipping
        the PK and audit bookkeeping columns. FK fields use the raw id
        (attname) — a plain, always-available value, not a resolved label."""
        snap = {}
        for f in instance._meta.fields:
            if f.name in self._AUDIT_SKIP or f.primary_key:
                continue
            val = getattr(instance, f.attname)
            if hasattr(val, "isoformat"):
                val = val.isoformat()
            snap[f.name] = val
        return snap

    def _diff(self, old, new):
        return {
            k: {"old": old.get(k), "new": new.get(k)} for k in new if old.get(k) != new.get(k)
        }

    def perform_create(self, serializer):
        from django.utils import timezone

        uid = self._current_user_id(self.request)
        instance = serializer.save(cr_user_id=uid or 1, cr_dt=timezone.now())
        changes = {
            k: {"old": None, "new": v} for k, v in self._snapshot(instance).items() if v not in (None, "")
        }
        _audit.record_action(
            self.request, "create", self.entity_key, instance.pk, self.label_for(instance), changes or None
        )

    def perform_update(self, serializer):
        from django.utils import timezone

        old_snapshot = self._snapshot(serializer.instance)
        uid = self._current_user_id(self.request)
        instance = serializer.save(mod_user_id=uid, mod_dt=timezone.now())
        changes = self._diff(old_snapshot, self._snapshot(instance))
        _audit.record_action(
            self.request, "update", self.entity_key, instance.pk, self.label_for(instance), changes or None
        )

    def _references(self, instance):
        references = []
        for accessor, label in self.reference_checks:
            count = getattr(instance, accessor).count()
            if count:
                references.append({"label": label, "count": count})
        return references

    @action(detail=True, methods=["get"], url_path="check-delete")
    def check_delete(self, request, pk=None):
        instance = self.get_object()
        references = self._references(instance)
        return Response({"can_delete": not references, "references": references})

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        references = self._references(instance)
        if references:
            return Response(
                {
                    "error": "This record is still referenced elsewhere and can't be deleted.",
                    "references": references,
                },
                status=400,
            )

        label = self.label_for(instance)
        pk = instance.pk
        try:
            instance.delete()
        except ProtectedError:
            # Safety net for any reference this viewset doesn't know to check yet.
            return Response(
                {"error": "This record is still referenced elsewhere and can't be deleted."},
                status=400,
            )
        _audit.record_action(request, "delete", self.entity_key, pk, label)
        return Response(status=204)


class MstCostCentreTypeViewSet(BaseMasterViewSet):
    queryset = MstCostCentreType.objects.all()
    serializer_class = MstCostCentreTypeSerializer
    entity_key = "masters.cost_centre_types"
    name_field = "cost_centre_type_name"
    reference_checks = [("cost_centres", "Cost Centres")]
    search_fields = ["cost_centre_type_name", "cost_centre_type_shortname"]


class MstContractorViewSet(BaseMasterViewSet):
    queryset = MstContractor.objects.all()
    serializer_class = MstContractorSerializer
    entity_key = "masters.contractors"
    name_field = "contractor_name"
    search_fields = ["contractor_name"]


class MstCertInstituteViewSet(BaseMasterViewSet):
    queryset = MstCertInstitute.objects.select_related("location").all()
    serializer_class = MstCertInstituteSerializer
    entity_key = "masters.cert_institutes"
    name_field = "cert_institute_name"
    search_fields = ["cert_institute_name", "cert_institute_shortname"]


class MstEmailNotificationTypeViewSet(BaseMasterViewSet):
    queryset = MstEmailNotificationType.objects.all()
    serializer_class = MstEmailNotificationTypeSerializer
    entity_key = "masters.email_notification_types"
    name_field = "en_type_name"
    search_fields = ["en_type_name"]


class MstOperatorViewSet(BaseMasterViewSet):
    queryset = MstOperator.objects.select_related("location", "country").all()
    serializer_class = MstOperatorSerializer
    entity_key = "masters.operators"
    name_field = "operator_name"
    search_fields = ["operator_name", "operator_short_name"]


class MstRigTypeViewSet(BaseMasterViewSet):
    """No dedicated nav page yet — reachable only as a dropdown source for
    the Rigs form and via direct API access, gated the same as any other
    master through entity_key."""

    queryset = MstRigType.objects.all()
    serializer_class = MstRigTypeSerializer
    entity_key = "masters.rig_types"
    permission_classes = [HasMenuPermissionOrOpenRead]
    name_field = "rig_type_name"
    reference_checks = [("rigs", "Rigs"), ("subtypes", "Rig Subtypes")]
    search_fields = ["rig_type_name"]


class MstRigSubtypeViewSet(BaseMasterViewSet):
    """No dedicated nav page yet — reachable only as a dropdown source for
    the Rigs form and via direct API access, gated the same as any other
    master through entity_key."""

    queryset = MstRigSubtype.objects.select_related("rig_type").all()
    serializer_class = MstRigSubtypeSerializer
    entity_key = "masters.rig_subtypes"
    permission_classes = [HasMenuPermissionOrOpenRead]
    name_field = "rig_subtype_name"
    reference_checks = [("rigs", "Rigs")]
    search_fields = ["rig_subtype_name"]


class MstRigViewSet(BaseMasterViewSet):
    queryset = MstRig.objects.select_related("rig_type", "rig_subtype").all()
    serializer_class = MstRigSerializer
    entity_key = "masters.rigs"
    name_field = "rig_name"
    reference_checks = [("cost_centres", "Cost Centres")]
    search_fields = ["rig_name", "rig_short_name"]


class MstCostCentreViewSet(BaseMasterViewSet):
    queryset = MstCostCentre.objects.select_related("cost_centre_type", "rig", "fs_emp", "location").all()
    serializer_class = MstCostCentreSerializer
    entity_key = "masters.cost_centres"
    name_field = "cost_centre_name"
    search_fields = ["cost_centre_name", "old_cost_centre_name"]


class MstCompetencyViewSet(BaseMasterViewSet):
    queryset = MstCompetency.objects.select_related("department").all()
    serializer_class = MstCompetencySerializer
    entity_key = "masters.competency"
    name_field = "competency_name"
    search_fields = ["competency_name"]


class MstDepartmentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only lookup for other masters' Department dropdowns (Competency,
    and Mst_User's own department field) — not yet its own delegable master,
    just data anyone authenticated can read to populate a select.
    """

    queryset = MstDepartment.objects.filter(dept_active="Y").order_by("dept_dispname")
    serializer_class = MstDepartmentSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["dept_dispname"]
    # Paginated like every other lookup (see MstUserViewSet) so the frontend
    # combobox can tell from `count` whether it's safe to preload in full.

    def get_queryset(self):
        qs = self.queryset
        ids = self.request.query_params.get("ids")
        if ids:
            qs = qs.filter(dept_id__in=[i for i in ids.split(",") if i.isdigit()])
        return qs


class MstFsCategoryViewSet(BaseMasterViewSet):
    queryset = MstFsCategory.objects.all()
    serializer_class = MstFsCategorySerializer
    entity_key = "masters.fs_categories"
    name_field = "fs_category_name"
    reference_checks = [("ranks", "Ranks")]
    search_fields = ["fs_category_name"]


class MstRankViewSet(BaseMasterViewSet):
    queryset = MstRank.objects.select_related("fs_category", "vessel_dept").all()
    serializer_class = MstRankSerializer
    entity_key = "masters.ranks"
    name_field = "rank_name"
    search_fields = ["rank_name", "rank_abrv"]

    def get_queryset(self):
        qs = self.queryset
        fs_category_id = self.request.query_params.get("fs_category")
        if fs_category_id:
            qs = qs.filter(fs_category_id=fs_category_id)
        return qs.order_by(self.name_field)


class JobDescriptionHdrViewSet(BaseMasterViewSet):
    """Sections for a Rank's job description. GET supports ?rank=<id> to
    scope the list — the editor always works one rank at a time."""

    queryset = JobDescriptionHdr.objects.select_related("fs_category", "rank").prefetch_related(
        "details"
    )
    serializer_class = JobDescriptionHdrSerializer
    entity_key = "masters.job_descriptions"
    name_field = "jd_hdr_description"

    def get_queryset(self):
        qs = self.queryset
        rank_id = self.request.query_params.get("rank")
        if rank_id:
            qs = qs.filter(rank_id=rank_id)
        return qs

    def perform_create(self, serializer):
        from django.utils import timezone

        uid = self._current_user_id(self.request)
        rank = serializer.validated_data.get("rank")
        instance = serializer.save(
            cr_user_id=uid or 1,
            cr_dt=timezone.now(),
            fs_category_id=rank.fs_category_id,
        )
        changes = {
            k: {"old": None, "new": v} for k, v in self._snapshot(instance).items() if v not in (None, "")
        }
        _audit.record_action(
            self.request, "create", self.entity_key, instance.pk, instance.jd_hdr_description, changes or None
        )


class JobDescriptionDtlViewSet(BaseMasterViewSet):
    """Detail lines under one section. GET supports ?header=<id>."""

    queryset = JobDescriptionDtl.objects.select_related("header")
    serializer_class = JobDescriptionDtlSerializer
    entity_key = "masters.job_descriptions"
    name_field = "jd_dtl_description"

    def get_queryset(self):
        qs = self.queryset
        header_id = self.request.query_params.get("header")
        if header_id:
            qs = qs.filter(header_id=header_id)
        return qs


class TravelEligibilityViewSet(BaseMasterViewSet):
    queryset = TravelEligibility.objects.select_related("rank", "fs_category").all()
    serializer_class = TravelEligibilitySerializer
    entity_key = "masters.travel_eligibility"
    search_fields = ["rank__rank_name", "travel_class"]

    def get_queryset(self):
        return self.queryset.order_by("rank__rank_name", "travel_mode")

    def label_for(self, instance):
        return f"{instance.rank.rank_name} — {instance.get_travel_mode_display()}"

    def perform_create(self, serializer):
        from django.utils import timezone

        uid = self._current_user_id(self.request)
        rank = serializer.validated_data.get("rank")
        instance = serializer.save(
            cr_user_id=uid or 1, cr_dt=timezone.now(), fs_category_id=rank.fs_category_id
        )
        changes = {
            k: {"old": None, "new": v} for k, v in self._snapshot(instance).items() if v not in (None, "")
        }
        _audit.record_action(
            self.request, "create", self.entity_key, instance.pk, self.label_for(instance), changes or None
        )

    def perform_update(self, serializer):
        from django.utils import timezone

        old_snapshot = self._snapshot(serializer.instance)
        uid = self._current_user_id(self.request)
        rank = serializer.validated_data.get("rank", serializer.instance.rank)
        instance = serializer.save(
            mod_user_id=uid, mod_dt=timezone.now(), fs_category_id=rank.fs_category_id
        )
        changes = self._diff(old_snapshot, self._snapshot(instance))
        _audit.record_action(
            self.request, "update", self.entity_key, instance.pk, self.label_for(instance), changes or None
        )


class ReportingStructureViewSet(BaseMasterViewSet):
    queryset = ReportingStructure.objects.select_related("rank", "reporting_rank").all()
    serializer_class = ReportingStructureSerializer
    entity_key = "masters.reporting_structure"
    search_fields = ["rank__rank_name", "reporting_rank__rank_name"]

    def get_queryset(self):
        return self.queryset.order_by("rank__rank_name")

    def label_for(self, instance):
        if instance.reporting_rank_id:
            return f"{instance.rank.rank_name} → {instance.reporting_rank.rank_name}"
        return f"{instance.rank.rank_name} (top of chain)"


class MstRigOperationViewSet(BaseMasterViewSet):
    queryset = MstRigOperation.objects.all()
    serializer_class = MstRigOperationSerializer
    entity_key = "masters.rig_operations"
    name_field = "rig_operation_name"
    search_fields = ["rig_operation_name"]


class MstContactExposureTypeViewSet(BaseMasterViewSet):
    queryset = MstContactExposureType.objects.all()
    serializer_class = MstContactExposureTypeSerializer
    entity_key = "masters.contact_exposure_types"
    name_field = "contact_expo_type_name"
    search_fields = ["contact_expo_type_name"]


class MstIndicatorTypeViewSet(BaseMasterViewSet):
    queryset = MstIndicatorType.objects.all()
    serializer_class = MstIndicatorTypeSerializer
    entity_key = "masters.indicator_types"
    name_field = "indicator_type_name"
    search_fields = ["indicator_type_name"]
    reference_checks = [("subtypes", "Indicator Subtypes")]

    def perform_create(self, serializer):
        from django.db.models import Max
        from django.utils import timezone

        uid = self._current_user_id(self.request)
        report_type = serializer.validated_data.get("report_type")
        next_order = (
            MstIndicatorType.objects.filter(report_type=report_type).aggregate(m=Max("indicator_type_order"))["m"]
            or 0
        ) + 1
        instance = serializer.save(
            cr_user_id=uid or 1, cr_dt=timezone.now(), indicator_type_order=next_order
        )
        changes = {
            k: {"old": None, "new": v} for k, v in self._snapshot(instance).items() if v not in (None, "")
        }
        _audit.record_action(
            self.request, "create", self.entity_key, instance.pk, self.label_for(instance), changes or None
        )


class MstIndicatorSubtypeViewSet(BaseMasterViewSet):
    queryset = MstIndicatorSubtype.objects.select_related("indicator_type").all()
    serializer_class = MstIndicatorSubtypeSerializer
    entity_key = "masters.indicator_subtypes"
    name_field = "indicator_subtype_name"
    search_fields = ["indicator_subtype_name", "indicator_type__indicator_type_name"]

    def perform_create(self, serializer):
        from django.db.models import Max
        from django.utils import timezone

        uid = self._current_user_id(self.request)
        indicator_type = serializer.validated_data.get("indicator_type")
        next_order = (
            MstIndicatorSubtype.objects.filter(indicator_type=indicator_type).aggregate(
                m=Max("indicator_subtype_order")
            )["m"]
            or 0
        ) + 1
        instance = serializer.save(
            cr_user_id=uid or 1, cr_dt=timezone.now(), indicator_subtype_order=next_order
        )
        changes = {
            k: {"old": None, "new": v} for k, v in self._snapshot(instance).items() if v not in (None, "")
        }
        _audit.record_action(
            self.request, "create", self.entity_key, instance.pk, self.label_for(instance), changes or None
        )


class MstPartsOfBodyViewSet(BaseMasterViewSet):
    queryset = MstPartsOfBody.objects.all()
    serializer_class = MstPartsOfBodySerializer
    entity_key = "masters.parts_of_body"
    name_field = "part_of_body_name"
    search_fields = ["part_of_body_name"]


class MstQhseCategoryViewSet(BaseMasterViewSet):
    queryset = MstQhseCategory.objects.all()
    serializer_class = MstQhseCategorySerializer
    entity_key = "masters.qhse_categories"
    name_field = "qhse_category_name"
    search_fields = ["qhse_category_name"]


class MstHseActivityViewSet(BaseMasterViewSet):
    queryset = MstHseActivity.objects.all()
    serializer_class = MstHseActivitySerializer
    entity_key = "masters.hse_activities"
    name_field = "hse_activity_name"
    search_fields = ["hse_activity_name"]


class MstHseConsumableViewSet(BaseMasterViewSet):
    queryset = MstHseConsumable.objects.all()
    serializer_class = MstHseConsumableSerializer
    entity_key = "masters.hse_consumables"
    name_field = "hse_consumable_name"
    search_fields = ["hse_consumable_name"]


class MstHazardTypeViewSet(BaseMasterViewSet):
    queryset = MstHazardType.objects.all()
    serializer_class = MstHazardTypeSerializer
    entity_key = "masters.hazard_types"
    name_field = "haz_type_name"
    search_fields = ["haz_type_name"]


class MstUserViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only lookup for other masters' User dropdowns. Not its own
    delegable master (User Management owns the real CRUD for Mst_User).

    Paginated (the default MastersPagination, not disabled) on purpose:
    the frontend combobox probes this endpoint's `count` to decide whether
    to preload the full list or fall back to server-side search, so a
    growing user roster degrades gracefully instead of silently truncating
    a preloaded dropdown at some hardcoded page size."""

    queryset = MstUser.objects.filter(user_active="Y").order_by("user_name")
    serializer_class = MstUserSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["user_name", "user_login_id"]


class MstEmployeeViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only lookup for Document To Sign Mapping's Employee field.
    Mst_Employee is a ~28k-row HR roster this app doesn't own — always
    paginated/searched, never fetched in full like the small lookups."""

    queryset = MstEmployee.objects.filter(emp_active="Y").order_by("emp_sname", "emp_fname")
    serializer_class = MstEmployeeSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["emp_fname", "emp_mname", "emp_sname"]


class MstUserRigMappingViewSet(BaseMasterViewSet):
    queryset = MstUserRigMapping.objects.select_related("user", "rig").all()
    serializer_class = MstUserRigMappingSerializer
    entity_key = "masters.user_rig_mapping"
    search_fields = ["user__user_name", "user__user_login_id", "rig__rig_name"]

    def get_queryset(self):
        return self.queryset.order_by("user__user_name")

    def label_for(self, instance):
        return f"{instance.user.user_name} — {instance.rig.rig_name}"


class MstUserFsCatgMappingViewSet(BaseMasterViewSet):
    queryset = MstUserFsCatgMapping.objects.select_related("user", "fs_category").all()
    serializer_class = MstUserFsCatgMappingSerializer
    entity_key = "masters.user_category_mapping"
    search_fields = ["user__user_name", "user__user_login_id", "fs_category__fs_category_name"]

    def get_queryset(self):
        return self.queryset.order_by("user__user_name")

    def label_for(self, instance):
        return f"{instance.user.user_name} — {instance.fs_category.fs_category_name}"


class DocToSignMappingViewSet(BaseMasterViewSet):
    queryset = DocToSignMapping.objects.select_related("employee").all()
    serializer_class = DocToSignMappingSerializer
    entity_key = "masters.doc_to_sign_mapping"
    search_fields = ["doc_name", "employee__emp_fname", "employee__emp_sname"]

    def get_queryset(self):
        return self.queryset.order_by("doc_name")

    def label_for(self, instance):
        return f"{instance.doc_name} — {instance.employee}"


class MstInterviewerViewSet(BaseMasterViewSet):
    queryset = MstInterviewer.objects.select_related("user", "department").all()
    serializer_class = MstInterviewerSerializer
    entity_key = "masters.interviewer_mapping"
    search_fields = ["user__user_name", "user__user_login_id", "department__dept_dispname"]

    def get_queryset(self):
        return self.queryset.order_by("department__dept_dispname")

    def label_for(self, instance):
        return f"{instance.department.dept_dispname} — {instance.user.user_name}"

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    @action(detail=False, methods=["post"], url_path="upload-sign")
    def upload_sign(self, request):
        """Save an interviewer's signature under MEDIA_ROOT, named by the
        user's id — mirrors the legacy convention of an id-based filename
        (its data has e.g. /Images/Crew_Interviewer/470.zip) rather than the
        random-uuid naming an interim rewrite used before this app existed."""
        import os

        from django.conf import settings

        user_id = request.data.get("user_id")
        f = request.FILES.get("file")
        if not user_id or not f:
            return Response({"error": "user_id and file are required"}, status=400)

        ext = os.path.splitext(f.name)[1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".pdf"):
            return Response({"error": "Only JPG, PNG, or PDF files are allowed"}, status=400)
        if f.size > 5 * 1024 * 1024:
            return Response({"error": "File exceeds 5 MB limit"}, status=400)

        rel_dir = "interviewer_signatures"
        abs_dir = os.path.join(settings.MEDIA_ROOT, rel_dir)
        os.makedirs(abs_dir, exist_ok=True)
        filename = f"{user_id}{ext}"
        abs_path = os.path.join(abs_dir, filename)
        with open(abs_path, "wb") as out:
            for chunk in f.chunks():
                out.write(chunk)

        rel_path = f"{rel_dir}/{filename}"
        url = request.build_absolute_uri(settings.MEDIA_URL + rel_path)
        return Response({"path": rel_path, "url": url})


class FsCatgToRigTypeMappingViewSet(BaseMasterViewSet):
    """Which Rig Types a Fs Category applies to. GET supports
    ?fs_category=<id> to scope to one category's checklist — the custom
    frontend page manages one category's full Rig Type set at a time,
    toggling mapping_active rather than deleting rows."""

    queryset = FsCatgToRigTypeMapping.objects.select_related("fs_category", "rig_type").all()
    serializer_class = FsCatgToRigTypeMappingSerializer
    entity_key = "masters.fs_catg_to_rig_type_mapping"
    search_fields = ["fs_category__fs_category_name", "rig_type__rig_type_name"]

    def get_queryset(self):
        qs = self.queryset
        fs_category_id = self.request.query_params.get("fs_category")
        if fs_category_id:
            qs = qs.filter(fs_category_id=fs_category_id)
        return qs.order_by("fs_category__fs_category_name", "rig_type__rig_type_name")

    def label_for(self, instance):
        return f"{instance.fs_category.fs_category_name} — {instance.rig_type.rig_type_name}"


class RankClassificationViewSet(BaseMasterViewSet):
    queryset = RankClassification.objects.select_related("rank").all()
    serializer_class = RankClassificationSerializer
    entity_key = "masters.rank_classification"
    search_fields = ["rank__rank_name"]

    def get_queryset(self):
        return self.queryset.order_by("rank__rank_name")

    def label_for(self, instance):
        return f"{instance.rank.rank_name} — {instance.get_rank_class_display()}"


class MstEmpNatureViewSet(BaseMasterViewSet):
    """No dedicated nav page yet — reachable only as a dropdown source for
    Emp Type and via direct API access."""

    queryset = MstEmpNature.objects.all()
    serializer_class = MstEmpNatureSerializer
    entity_key = "masters.emp_natures"
    permission_classes = [HasMenuPermissionOrOpenRead]
    name_field = "emp_nature_name"
    reference_checks = [("emp_types", "Emp Types")]
    search_fields = ["emp_nature_name"]


class MstEmpTypeViewSet(BaseMasterViewSet):
    """No dedicated nav page yet — reachable only as a dropdown source for
    Nationality To Emp Type Mapping and via direct API access."""

    queryset = MstEmpType.objects.select_related("emp_nature", "currency").all()
    serializer_class = MstEmpTypeSerializer
    entity_key = "masters.emp_types"
    permission_classes = [HasMenuPermissionOrOpenRead]
    name_field = "emp_type_name"
    reference_checks = [("nationality_mappings", "Nationality To Emp Type Mapping")]
    search_fields = ["emp_type_name"]


class NationalityToEmpTypeMappingViewSet(BaseMasterViewSet):
    queryset = NationalityToEmpTypeMapping.objects.select_related("fs_category", "emp_type").all()
    serializer_class = NationalityToEmpTypeMappingSerializer
    entity_key = "masters.nationality_to_emp_type_mapping"
    search_fields = ["fs_category__fs_category_name", "emp_type__emp_type_name"]

    def get_queryset(self):
        return self.queryset.order_by("fs_category__fs_category_name", "nationality")

    def label_for(self, instance):
        return f"{instance.fs_category.fs_category_name} — {instance.nationality} — {instance.emp_type.emp_type_name}"


class CrewChangeRelieverMappingViewSet(BaseMasterViewSet):
    queryset = CrewChangeRelieverMapping.objects.select_related("fs_category", "rank", "reliever_rank").all()
    serializer_class = CrewChangeRelieverMappingSerializer
    entity_key = "masters.crew_change_reliever_mapping"
    search_fields = ["rank__rank_name", "reliever_rank__rank_name"]

    def get_queryset(self):
        return self.queryset.order_by("rank__rank_name")

    def label_for(self, instance):
        return f"{instance.rank.rank_name} — {instance.reliever_rank.rank_name}"


class MstWorkgroupViewSet(BaseMasterViewSet):
    """No dedicated nav page yet — reachable only as a dropdown source for
    Workgroup To Indicator Type Mapping and via direct API access."""

    queryset = MstWorkgroup.objects.all()
    serializer_class = MstWorkgroupSerializer
    entity_key = "masters.workgroups"
    permission_classes = [HasMenuPermissionOrOpenRead]
    name_field = "workgroup_name"
    reference_checks = [("indicator_type_mappings", "Workgroup To Indicator Type Mapping")]
    search_fields = ["workgroup_name"]


class WkgrpIndicatorTypeMappingViewSet(BaseMasterViewSet):
    queryset = WkgrpIndicatorTypeMapping.objects.select_related("workgroup", "indicator_type").all()
    serializer_class = WkgrpIndicatorTypeMappingSerializer
    entity_key = "masters.wkgrp_indicator_type_mapping"
    search_fields = ["workgroup__workgroup_name", "indicator_type__indicator_type_name"]

    def get_queryset(self):
        return self.queryset.order_by("workgroup__workgroup_name", "indicator_type__indicator_type_name")

    def label_for(self, instance):
        return f"{instance.workgroup.workgroup_name} — {instance.indicator_type.indicator_type_name}"


class MstOrganisationalGrpViewSet(BaseMasterViewSet):
    """No dedicated nav page yet — reachable only as a dropdown source for
    Company and via direct API access."""

    queryset = MstOrganisationalGrp.objects.all()
    serializer_class = MstOrganisationalGrpSerializer
    entity_key = "masters.organisational_grps"
    permission_classes = [HasMenuPermissionOrOpenRead]
    name_field = "organisational_grp_name"
    reference_checks = [("companies", "Companies")]
    search_fields = ["organisational_grp_name"]


class MstBusinessGrpViewSet(BaseMasterViewSet):
    """No dedicated nav page yet — reachable only as a dropdown source for
    Company and via direct API access."""

    queryset = MstBusinessGrp.objects.select_related("parent_business_grp").all()
    serializer_class = MstBusinessGrpSerializer
    entity_key = "masters.business_grps"
    permission_classes = [HasMenuPermissionOrOpenRead]
    name_field = "business_grp_name"
    reference_checks = [("companies", "Companies"), ("children", "Business Groups")]
    search_fields = ["business_grp_name", "business_grp_abrv"]


class MstCompanyViewSet(BaseMasterViewSet):
    """No dedicated nav page yet — reachable only as a dropdown source for
    Cost Centre To Company Mapping and via direct API access."""

    queryset = MstCompany.objects.select_related(
        "organisational_grp", "business_grp", "parent_company", "country", "currency"
    ).all()
    serializer_class = MstCompanySerializer
    entity_key = "masters.companies"
    permission_classes = [HasMenuPermissionOrOpenRead]
    name_field = "company_name"
    reference_checks = [("cost_centre_mappings", "Cost Centre To Company Mapping"), ("subsidiaries", "Companies")]
    search_fields = ["company_name", "company_abrv", "company_code"]


class CostCentreToCompanyMappingViewSet(BaseMasterViewSet):
    queryset = CostCentreToCompanyMapping.objects.select_related("company", "cost_centre").all()
    serializer_class = CostCentreToCompanyMappingSerializer
    entity_key = "masters.cost_centre_to_company_mapping"
    search_fields = ["company__company_name", "cost_centre__cost_centre_name"]

    def get_queryset(self):
        return self.queryset.order_by("company__company_name")

    def label_for(self, instance):
        return f"{instance.company.company_name} — {instance.cost_centre.cost_centre_name}"


class RigSiteMappingViewSet(BaseMasterViewSet):
    queryset = RigSiteMapping.objects.select_related(
        "rig", "company", "location", "contact_fs_emp_1", "contact_fs_emp_2"
    ).all()
    serializer_class = RigSiteMappingSerializer
    entity_key = "masters.rig_site_mapping"
    search_fields = ["rig__rig_name", "company__company_name", "camp_office_addr"]

    def get_queryset(self):
        return self.queryset.order_by("rig__rig_name")

    def label_for(self, instance):
        return f"{instance.rig.rig_name} — {instance.company.company_name}"


class RigCrewExceptionViewSet(BaseMasterViewSet):
    queryset = RigCrewException.objects.select_related("fs_category", "emp_type", "rank", "fs_emp").all()
    serializer_class = RigCrewExceptionSerializer
    entity_key = "masters.rig_crew_exceptions"
    search_fields = ["fs_category__fs_category_name", "rank__rank_name", "emp_type__emp_type_name"]

    def get_queryset(self):
        return self.queryset.order_by("fs_category__fs_category_name")

    def label_for(self, instance):
        return str(instance)


class CrewScheduleExceptionViewSet(BaseMasterViewSet):
    queryset = CrewScheduleException.objects.select_related("fs_category", "emp_type", "rank", "fs_emp").all()
    serializer_class = CrewScheduleExceptionSerializer
    entity_key = "masters.crew_schedule_exceptions"
    search_fields = ["fs_category__fs_category_name", "rank__rank_name", "emp_type__emp_type_name"]

    def get_queryset(self):
        return self.queryset.order_by("fs_category__fs_category_name")

    def label_for(self, instance):
        return str(instance)


# ── Project masters ──────────────────────────────────────────────────────────


class MstContinentViewSet(BaseMasterViewSet):
    """No dedicated nav page yet — reachable only as a dropdown source for
    Countries and via direct API access, gated the same as any other master
    through entity_key."""

    queryset = MstContinent.objects.all()
    serializer_class = MstContinentSerializer
    entity_key = "masters.continents"
    permission_classes = [HasMenuPermissionOrOpenRead]
    name_field = "continent_name"
    reference_checks = [("countries", "Countries")]
    search_fields = ["continent_name"]


class MstCountryViewSet(BaseMasterViewSet):
    """No dedicated nav page yet — reachable only as a dropdown source for
    Locations/Operators and via direct API access."""

    queryset = MstCountry.objects.select_related("continent").all()
    serializer_class = MstCountrySerializer
    entity_key = "masters.countries"
    permission_classes = [HasMenuPermissionOrOpenRead]
    name_field = "country_name"
    reference_checks = [("states", "Country States"), ("locations", "Locations"), ("operators", "Operators")]
    search_fields = ["country_name", "country_known_name", "country_iso_cd"]


class MstCountryStateViewSet(BaseMasterViewSet):
    """No dedicated nav page yet — reachable only as a dropdown source for
    Locations and via direct API access."""

    queryset = MstCountryState.objects.select_related("country").all()
    serializer_class = MstCountryStateSerializer
    entity_key = "masters.country_states"
    permission_classes = [HasMenuPermissionOrOpenRead]
    name_field = "country_state_name"
    reference_checks = [("locations", "Locations")]
    search_fields = ["country_state_name", "country_state_abrv"]


class MstVesselDeptViewSet(BaseMasterViewSet):
    """No dedicated nav page yet — reachable only as a dropdown source for
    Ranks and via direct API access."""

    queryset = MstVesselDept.objects.all()
    serializer_class = MstVesselDeptSerializer
    entity_key = "masters.vessel_depts"
    permission_classes = [HasMenuPermissionOrOpenRead]
    name_field = "vessel_dept_name"
    reference_checks = [("ranks", "Ranks")]
    search_fields = ["vessel_dept_name"]


class MstLocationViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only lookup for Project Contract's Location field. ~700 rows —
    paginated/searched like every other lookup so the frontend combobox can
    tell from `count` whether it's safe to preload in full.

    GET supports ?country=<id> so a form can narrow the Location picker to
    whatever Country was picked first (e.g. Operators)."""

    queryset = (
        MstLocation.objects.select_related("country", "country_state")
        .filter(location_active="Y")
        .order_by("location_name")
    )
    serializer_class = MstLocationSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["location_name"]

    def get_queryset(self):
        qs = self.queryset
        country_id = self.request.query_params.get("country")
        if country_id:
            qs = qs.filter(country_id=country_id)
        return qs


class MstCurrencyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MstCurrency.objects.filter(currency_active="Y").order_by("currency_name")
    serializer_class = MstCurrencySerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["currency_name", "currency_abrv"]


class MstDrillingRateViewSet(BaseMasterViewSet):
    """Doubles as a full CRUD master (its own admin page, per legacy) and a
    dropdown source for Project Drilling Rates' Rate Type picker."""

    queryset = MstDrillingRate.objects.all()
    serializer_class = MstDrillingRateSerializer
    entity_key = "masters.drilling_rates"
    name_field = "rate_code"
    reference_checks = [("rate_usages", "Project Drilling Rates")]
    search_fields = ["rate_code", "rate_description"]


class ProjectContractViewSet(BaseMasterViewSet):
    """Real header+detail master — Rig assignments (below) live under one
    contract at a time, so this gets its own editor page instead of the
    generic single-table masters page."""

    queryset = ProjectContract.objects.select_related("location", "operator").prefetch_related("lines")
    serializer_class = ProjectContractSerializer
    entity_key = "masters.project_contract"
    name_field = "prj_contract_no"
    # Rig assignments and drilling rates are this contract's own detail
    # lines (CASCADE), not other masters referencing it — deleting a
    # contract is meant to take them with it, same as Job Descriptions'
    # header/detail relationship, not be blocked by them.
    search_fields = ["prj_contract_no", "prj_short_name", "location__location_name", "operator__operator_name"]

    def get_queryset(self):
        qs = self.queryset
        operator_id = self.request.query_params.get("operator")
        status = self.request.query_params.get("status")
        if operator_id:
            qs = qs.filter(operator_id=operator_id)
        if status == "active":
            qs = qs.filter(prj_end_dt__isnull=True)
        elif status == "closed":
            qs = qs.filter(prj_end_dt__isnull=False)
        return qs.order_by("-prj_start_dt")

    def label_for(self, instance):
        return instance.prj_contract_no


class ProjectContractDtlViewSet(BaseMasterViewSet):
    """Rig lines under one contract. GET supports ?contract=<id> — the
    editor always works one contract at a time."""

    queryset = ProjectContractDtl.objects.select_related("rig", "contract")
    serializer_class = ProjectContractDtlSerializer
    entity_key = "masters.project_contract"
    name_field = "rig_active_from"

    def get_queryset(self):
        qs = self.queryset
        contract_id = self.request.query_params.get("contract")
        if contract_id:
            qs = qs.filter(contract_id=contract_id)
        return qs.order_by("rig_active_from")

    def label_for(self, instance):
        return f"{instance.contract.prj_contract_no} — {instance.rig.rig_name}"


class ProjectDrillingRateViewSet(BaseMasterViewSet):
    """Rates for one (contract, rig) pair are managed together as a small
    table — the editor always works one pair at a time. GET supports
    ?contract=<id>&rig=<id> to scope the list."""

    queryset = ProjectDrillingRate.objects.select_related("drilling_rate", "contract", "rig", "currency")
    serializer_class = ProjectDrillingRateSerializer
    entity_key = "masters.project_drilling_rates"
    search_fields = ["contract__prj_contract_no", "rig__rig_name", "drilling_rate__rate_code"]

    def get_queryset(self):
        qs = self.queryset
        contract_id = self.request.query_params.get("contract")
        rig_id = self.request.query_params.get("rig")
        if contract_id:
            qs = qs.filter(contract_id=contract_id)
        if rig_id:
            qs = qs.filter(rig_id=rig_id)
        return qs.order_by("-contract__prj_start_dt", "drilling_rate__rate_code")

    def label_for(self, instance):
        return f"{instance.contract.prj_contract_no} — {instance.rig.rig_name} — {instance.drilling_rate.rate_code}"


# ── Drilling masters ──────────────────────────────────────────────────────────


class MstDrillingOperationViewSet(BaseMasterViewSet):
    queryset = MstDrillingOperation.objects.all()
    serializer_class = MstDrillingOperationSerializer
    entity_key = "masters.drilling_operations"
    name_field = "drilling_ops_name"
    search_fields = ["drilling_ops_name"]

    @action(detail=False, methods=["get"], url_path="check-code")
    def check_code(self, request):
        """Is this Code No already taken by another operation, and if so,
        what's the next free one — backs the frontend's debounced amber-banner
        check on the Code No field."""
        raw = request.query_params.get("code", "")
        if not raw.lstrip("-").isdigit():
            return Response({"taken": False, "suggestion": None})
        code = int(raw)
        qs = self.queryset.filter(drilling_ops_code_no=code)
        exclude_id = request.query_params.get("exclude")
        if exclude_id:
            qs = qs.exclude(pk=exclude_id)
        taken = qs.exists()
        suggestion = None
        if taken:
            used = set(self.queryset.values_list("drilling_ops_code_no", flat=True))
            candidate = code + 1
            while candidate in used:
                candidate += 1
            suggestion = candidate
        return Response({"taken": taken, "suggestion": suggestion})


class MstDrillingSectionViewSet(BaseMasterViewSet):
    queryset = MstDrillingSection.objects.all()
    serializer_class = MstDrillingSectionSerializer
    entity_key = "masters.drilling_sections"
    name_field = "drilling_section_name"
    search_fields = ["drilling_section_name"]


class MstDrillingWorkShiftViewSet(BaseMasterViewSet):
    """Shift timings for one (contract, rig) pair are managed together as a
    small table — same workflow as ProjectDrillingRateViewSet. GET supports
    ?contract=<id>&rig=<id> to scope the list."""

    queryset = MstDrillingWorkShift.objects.select_related("contract", "rig")
    serializer_class = MstDrillingWorkShiftSerializer
    entity_key = "masters.drilling_work_shift"
    search_fields = ["rig__rig_name", "contract__prj_contract_no"]

    def get_queryset(self):
        qs = self.queryset
        contract_id = self.request.query_params.get("contract")
        rig_id = self.request.query_params.get("rig")
        if contract_id:
            qs = qs.filter(contract_id=contract_id)
        if rig_id:
            qs = qs.filter(rig_id=rig_id)
        return qs.order_by("work_shift")

    def label_for(self, instance):
        return f"{instance.rig.rig_name} — {instance.get_work_shift_display()}"


class MstItAssetTypeViewSet(BaseMasterViewSet):
    """No dedicated nav page — reachable only as a dropdown source (derived
    read-only on the IT Assets form) and via direct API access."""

    queryset = MstItAssetType.objects.all()
    serializer_class = MstItAssetTypeSerializer
    entity_key = "masters.it_asset_types"
    permission_classes = [HasMenuPermissionOrOpenRead]
    name_field = "it_asset_type_name"
    reference_checks = [("subtypes", "IT Asset Subtypes"), ("assets", "IT Assets")]
    search_fields = ["it_asset_type_name"]


class MstItAssetSubtypeViewSet(BaseMasterViewSet):
    """No dedicated nav page — reachable only as a dropdown source (derived
    read-only on the IT Assets form) and via direct API access."""

    queryset = MstItAssetSubtype.objects.select_related("it_asset_type").all()
    serializer_class = MstItAssetSubtypeSerializer
    entity_key = "masters.it_asset_subtypes"
    permission_classes = [HasMenuPermissionOrOpenRead]
    name_field = "it_asset_subtype_name"
    reference_checks = [("models", "IT Asset Models"), ("assets", "IT Assets")]
    search_fields = ["it_asset_subtype_name"]


class MstItAssetMfgViewSet(BaseMasterViewSet):
    """No dedicated nav page — reachable only as a dropdown source (derived
    read-only on the IT Assets form) and via direct API access."""

    queryset = MstItAssetMfg.objects.all()
    serializer_class = MstItAssetMfgSerializer
    entity_key = "masters.it_asset_mfgs"
    permission_classes = [HasMenuPermissionOrOpenRead]
    name_field = "it_asset_mfg_name"
    reference_checks = [("models", "IT Asset Models"), ("assets", "IT Assets")]
    search_fields = ["it_asset_mfg_name"]


class MstItAssetModelViewSet(BaseMasterViewSet):
    """No dedicated nav page yet — reachable as the IT Assets form's Model
    search (which derives Subtype/Type/Manufacturer from the picked row) and
    via direct API access."""

    queryset = MstItAssetModel.objects.select_related(
        "it_asset_mfg", "it_asset_subtype", "it_asset_subtype__it_asset_type"
    ).all()
    serializer_class = MstItAssetModelSerializer
    entity_key = "masters.it_asset_models"
    permission_classes = [HasMenuPermissionOrOpenRead]
    name_field = "it_asset_model_name"
    reference_checks = [("assets", "IT Assets")]
    search_fields = ["it_asset_model_name"]


class MstxVendorViewSet(BaseMasterViewSet):
    """No dedicated nav page yet — reachable as the IT Assets form's Vendor
    search and via direct API access."""

    queryset = MstxVendor.objects.select_related("vendor_type", "country", "currency").all()
    serializer_class = MstxVendorSerializer
    entity_key = "masters.vendors"
    permission_classes = [HasMenuPermissionOrOpenRead]
    name_field = "vendor_name"
    reference_checks = [("it_assets", "IT Assets")]
    search_fields = ["vendor_name"]


IT_ASSET_ORDERING_FIELDS = {
    "sr_no": "it_asset_sr_no",
    "model": "it_asset_model__it_asset_model_name",
    "asset_tag": "it_asset_tag",
    "mfg": "it_asset_mfg__it_asset_mfg_name",
    "own_company": "own_company__company_name",
    "cur_company": "cur_company__company_name",
    "pur_dt": "it_asset_pur_dt",
}


class MstItAssetViewSet(BaseMasterViewSet):
    """Listed as a reports-style table (not the generic masters drawer —
    too many fields for that) with its own list page driving ?search=,
    ?active=, ?holder_type=, ?own_company=, ?it_asset_type=,
    ?it_asset_subtype=, ?it_asset_mfg= and ?ordering= (one of
    sr_no/model/asset_tag/mfg/own_company/cur_company/pur_dt, prefix '-' to
    reverse)."""

    queryset = MstItAsset.objects.select_related(
        "it_asset_model", "it_asset_type", "it_asset_subtype", "it_asset_mfg",
        "own_company", "cur_company", "vendor",
    ).all()
    serializer_class = MstItAssetSerializer
    entity_key = "it_asset.it_assets"
    name_field = "it_asset_sr_no"
    reference_checks = [("holders", "IT Asset Holders")]
    search_fields = ["it_asset_sr_no", "it_asset_tag", "it_asset_sap_code"]

    def get_queryset(self):
        qs = self.queryset
        params = self.request.query_params

        active = params.get("active")
        if active in ("Y", "N"):
            qs = qs.filter(it_asset_active=active)
        holder_type = params.get("holder_type")
        if holder_type:
            qs = qs.filter(it_asset_holder_type=holder_type)
        own_company = params.get("own_company")
        if own_company:
            qs = qs.filter(own_company_id=own_company)
        it_asset_type = params.get("it_asset_type")
        if it_asset_type:
            qs = qs.filter(it_asset_type_id=it_asset_type)
        it_asset_subtype = params.get("it_asset_subtype")
        if it_asset_subtype:
            qs = qs.filter(it_asset_subtype_id=it_asset_subtype)
        it_asset_mfg = params.get("it_asset_mfg")
        if it_asset_mfg:
            qs = qs.filter(it_asset_mfg_id=it_asset_mfg)

        ordering = params.get("ordering", "-cr_dt")
        reverse = ordering.startswith("-")
        field = IT_ASSET_ORDERING_FIELDS.get(ordering.lstrip("-"))
        if field:
            qs = qs.order_by(f"-{field}" if reverse else field)
        else:
            qs = qs.order_by("-cr_dt")
        return qs


class MstCompanyLocationViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only lookup for other masters' Company Location dropdowns (IT
    Assets, IT Assets Holder) — not yet its own delegable master, just data
    anyone authenticated can read to populate a select."""

    queryset = MstCompanyLocation.objects.filter(company_loc_active="Y").order_by("company_loc_name")
    serializer_class = MstCompanyLocationSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["company_loc_name", "company_loc_abrv"]


class ItAssetHolderViewSet(BaseMasterViewSet):
    """Reassignment history for one IT Asset — who/where it's currently (or
    was previously) held by. Listed as a reports-style table like IT Assets.
    GET supports ?it_asset=, ?holder_company=, ?own_company=,
    ?it_asset_type=, ?it_asset_subtype=, ?it_asset_mfg=,
    ?status=(ongoing|ended), ?search= (asset sr no/tag/SAP code, holder
    name), and ?ordering=sr_no (prefix '-' to reverse; defaults to legacy's
    ongoing-first sort).

    Legacy's Cr_User_Id/Cr_Dt don't exist on it_IT_Asset_Holder — only
    Mod_User_Id/Mod_Dt — so perform_create is overridden to skip them
    rather than crash on an unknown kwarg."""

    queryset = ItAssetHolder.objects.select_related(
        "it_asset", "it_asset__it_asset_model", "it_asset__it_asset_subtype", "it_asset__it_asset_mfg",
        "it_asset__own_company", "holder_company", "emp", "department", "company_loc",
    ).all()
    serializer_class = ItAssetHolderSerializer
    entity_key = "it_asset.it_asset_holders"
    name_field = "it_asset_holder_id"
    reference_checks = []
    search_fields = [
        "it_asset__it_asset_sr_no", "it_asset__it_asset_tag", "it_asset__it_asset_sap_code", "holder_name",
    ]

    def get_queryset(self):
        qs = self.queryset
        params = self.request.query_params

        it_asset = params.get("it_asset")
        if it_asset:
            qs = qs.filter(it_asset_id=it_asset)
        holder_company = params.get("holder_company")
        if holder_company:
            qs = qs.filter(holder_company_id=holder_company)
        own_company = params.get("own_company")
        if own_company:
            qs = qs.filter(it_asset__own_company_id=own_company)
        it_asset_type = params.get("it_asset_type")
        if it_asset_type:
            qs = qs.filter(it_asset__it_asset_type_id=it_asset_type)
        it_asset_subtype = params.get("it_asset_subtype")
        if it_asset_subtype:
            qs = qs.filter(it_asset__it_asset_subtype_id=it_asset_subtype)
        it_asset_mfg = params.get("it_asset_mfg")
        if it_asset_mfg:
            qs = qs.filter(it_asset__it_asset_mfg_id=it_asset_mfg)
        today = datetime.date.today()
        status = params.get("status")
        if status == "ongoing":
            qs = qs.filter(it_asset_holder_to__isnull=True) | qs.filter(it_asset_holder_to__gte=today)
        elif status == "ended":
            qs = qs.filter(it_asset_holder_to__lt=today)

        ordering = params.get("ordering")
        if ordering and ordering.lstrip("-") == "sr_no":
            field = "it_asset__it_asset_sr_no"
            return qs.order_by(f"-{field}" if ordering.startswith("-") else field)

        # Same intent as legacy's ORDER BY ISNULL(To, GETDATE()+50) DESC —
        # ongoing assignments (no end date) sort first, then most-recently
        # ended first.
        far_future = datetime.date(2100, 1, 1)
        return qs.annotate(
            _sort_to=Coalesce("it_asset_holder_to", far_future)
        ).order_by("-_sort_to", "-it_asset_holder_from")

    def perform_create(self, serializer):
        instance = serializer.save()
        changes = {
            k: {"old": None, "new": v} for k, v in self._snapshot(instance).items() if v not in (None, "")
        }
        _audit.record_action(
            self.request, "create", self.entity_key, instance.pk, self.label_for(instance), changes or None
        )

    def label_for(self, instance):
        who = instance.emp or instance.holder_name or "Common"
        return f"{instance.it_asset.it_asset_sr_no} — {who}"
