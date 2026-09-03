import csv
import datetime

from django.db.models import DateTimeField, ProtectedError, Q, Value
from django.db.models.functions import Cast, Coalesce
from django.http import HttpResponse
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
    CompanyToLocationMappingSerializer,
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
    MstCompanyLocTypeSerializer,
    MstCompanyLocOwnershipSerializer,
    ItAssetHolderSerializer,
    MstVendorTypeSerializer,
    MstItAccessorySerializer,
    ItAccessoryHolderSerializer,
    MstFinancialYearSerializer,
    MstBussCertIssueAuthoritySerializer,
    MstBussCertTypeSerializer,
    MstBussCertSerializer,
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
    blocking a deletion instead of a raw DB error), and optionally
    active_field (the model's real Active-flag column, if it has one) to
    turn on generic ?active=Y/N filtering.

    Generic list-page sort/filter, on by default for every subclass that
    doesn't override get_queryset itself: ?ordering=name / -name sorts by
    name_field (frontend only ever needs to know its own nameField, not
    the real column), and ?active=Y/N filters on active_field when set.
    """

    permission_classes = [HasMenuPermission]
    entity_key = None
    name_field = None
    reference_checks = []
    # Set ONE of these when the master has an Active concept: active_field
    # for a real Y/N column, date_active_field for masters where "active"
    # is really "no end date yet, or one still in the future" (mapping_to /
    # eligible_to / exception_to / sign_to style columns).
    active_field = None
    date_active_field = None
    # Plain-value fields safe to filter on exactly via ?<field>=<value> —
    # e.g. Rank Classification's rank_class (J/S). Deliberately only for
    # small fixed-choice fields, not FK ids (those already have their own
    # remote-search pickers on the frontend).
    filterable_fields = []

    def _apply_active_filter(self, qs):
        """Shared by the default get_queryset below and by subclasses that
        override get_queryset for their own ordering/scoping — call this
        from inside that override to still get ?active=Y/N support."""
        if self.active_field:
            active = self.request.query_params.get("active")
            # Some legacy rows have '' rather than a real 'N' — treat
            # anything but an explicit 'Y' as Inactive rather than
            # requiring an exact 'N' match (same reasoning as IT Asset's
            # Allocated flag elsewhere in this app).
            if active == "Y":
                qs = qs.filter(**{self.active_field: "Y"})
            elif active == "N":
                qs = qs.exclude(**{self.active_field: "Y"})
        elif self.date_active_field:
            active = self.request.query_params.get("active")
            if active in ("Y", "N"):
                from django.utils import timezone

                today = timezone.localdate()
                ongoing = Q(**{f"{self.date_active_field}__isnull": True}) | Q(
                    **{f"{self.date_active_field}__gte": today}
                )
                qs = qs.filter(ongoing) if active == "Y" else qs.exclude(ongoing)
        return qs

    def _apply_filterable_fields(self, qs):
        for field in self.filterable_fields:
            value = self.request.query_params.get(field)
            if value:
                qs = qs.filter(**{field: value})
        return qs

    def get_queryset(self):
        qs = self._apply_filterable_fields(self._apply_active_filter(self.queryset))
        ordering = self.request.query_params.get("ordering")
        if ordering in ("name", "-name"):
            qs = qs.order_by(f"-{self.name_field}" if ordering.startswith("-") else self.name_field)
        else:
            qs = qs.order_by(self.name_field)
        return qs

    def label_for(self, instance):
        """Override when the model has no plain name_field (e.g. FK-combo
        rows like TravelEligibility) to build a readable audit label."""
        return getattr(instance, self.name_field, "")

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        """CSV export, generic across every master — whatever the list
        endpoint currently returns (same search/ordering/active/filterable
        params already applied via get_queryset, plus DRF's own ?search=)
        is what gets exported, so "export" always matches what's on
        screen. Columns are exactly the serializer's own fields — every
        master gets this for free, at the cost of raw field names rather
        than hand-picked friendly ones."""
        qs = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(qs, many=True)
        rows = serializer.data
        filename = (self.entity_key or "export").split(".")[-1]
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
        if not rows:
            self._audit_export(request, len(rows))
            return response
        fieldnames = list(rows[0].keys())
        writer = csv.DictWriter(response, fieldnames=fieldnames)
        writer.writerow({f: f.replace("_", " ").title() for f in fieldnames})
        for row in rows:
            writer.writerow(row)
        self._audit_export(request, len(rows))
        return response

    def _audit_export(self, request, row_count):
        """Same shape as the report exports' own _audit_export in
        reports_views.py — the filters that produced the download go in
        the changes column (no real "old" side for an export, so it's left
        blank) rather than inventing a separate audit shape for this one
        action."""
        changes = {
            k: {"old": None, "new": v} for k, v in request.query_params.items() if v not in (None, "")
        }
        changes["rows_exported"] = {"old": None, "new": row_count}
        title = (self.entity_key or "export").split(".")[-1].replace("_", " ").title()
        _audit.record_action(request, "export", self.entity_key, record_label=f"{title} export", changes=changes)

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
    active_field = "cost_centre_type_active"
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


class MstBussCertIssueAuthorityViewSet(BaseMasterViewSet):
    queryset = MstBussCertIssueAuthority.objects.all()
    serializer_class = MstBussCertIssueAuthoritySerializer
    entity_key = "masters.buss_cert_issue_authorities"
    permission_classes = [HasMenuPermissionOrOpenRead]
    name_field = "buss_cert_issue_authority"
    search_fields = ["buss_cert_issue_authority", "buss_cert_issue_abrv"]


class MstBussCertTypeViewSet(BaseMasterViewSet):
    queryset = MstBussCertType.objects.all()
    serializer_class = MstBussCertTypeSerializer
    entity_key = "masters.buss_cert_types"
    permission_classes = [HasMenuPermissionOrOpenRead]
    name_field = "buss_cert_type"
    search_fields = ["buss_cert_type", "buss_cert_type_abrv"]


class MstBussCertViewSet(BaseMasterViewSet):
    queryset = MstBussCert.objects.select_related("buss_cert_type").all()
    serializer_class = MstBussCertSerializer
    entity_key = "masters.buss_certs"
    name_field = "buss_cert_name"
    active_field = "buss_cert_active"
    search_fields = ["buss_cert_name", "buss_cert_type__buss_cert_type"]


class MstEmailNotificationTypeViewSet(BaseMasterViewSet):
    queryset = MstEmailNotificationType.objects.all()
    serializer_class = MstEmailNotificationTypeSerializer
    entity_key = "masters.email_notification_types"
    name_field = "en_type_name"
    active_field = "en_type_active"
    search_fields = ["en_type_name"]


class MstOperatorViewSet(BaseMasterViewSet):
    queryset = MstOperator.objects.select_related("location", "country").all()
    serializer_class = MstOperatorSerializer
    entity_key = "masters.operators"
    name_field = "operator_name"
    active_field = "operator_active"
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
    active_field = "rig_active"
    reference_checks = [("cost_centres", "Cost Centres")]
    search_fields = ["rig_name", "rig_short_name"]


class MstCostCentreViewSet(BaseMasterViewSet):
    queryset = MstCostCentre.objects.select_related("cost_centre_type", "rig", "fs_emp", "location").all()
    serializer_class = MstCostCentreSerializer
    entity_key = "masters.cost_centres"
    name_field = "cost_centre_name"
    active_field = "cost_centre_active"
    search_fields = ["cost_centre_name", "old_cost_centre_name"]


class MstCompetencyViewSet(BaseMasterViewSet):
    queryset = MstCompetency.objects.select_related("department").all()
    serializer_class = MstCompetencySerializer
    entity_key = "masters.competency"
    name_field = "competency_name"
    search_fields = ["competency_name"]


class MstDepartmentViewSet(BaseMasterViewSet):
    """Promoted from a read-only dropdown source to a real delegable master
    (General section) — reads stay open to any authenticated user via
    HasMenuPermissionOrOpenRead so the many forms that use Department as a
    lookup (Competency, User, IT Asset Holder, ...) keep working for
    everyone; only add/edit/delete now go through the real permission grid.
    List shows every row (active and inactive) like any other real master —
    dropdown consumers that only want active options filter with ?ids= or
    client-side, same as before."""

    queryset = MstDepartment.objects.all()
    serializer_class = MstDepartmentSerializer
    entity_key = "masters.departments"
    permission_classes = [HasMenuPermissionOrOpenRead]
    name_field = "dept_name"
    reference_checks = [
        ("competencies", "Competency"),
        ("users", "Users"),
        ("it_assets", "IT Assets"),
        ("it_asset_holdings", "IT Asset Holders"),
    ]
    # dept_name is the full name shown on the IT Asset Holder form's
    # Department picker (dept_dispname is a shorter display variant used
    # elsewhere) — search has to cover whichever field a caller displays,
    # so both (plus the abbreviation) are searchable regardless of which
    # one a given dropdown shows.
    search_fields = ["dept_name", "dept_dispname", "dept_abrv"]
    # Paginated like every other lookup (see MstUserViewSet) so the frontend
    # combobox can tell from `count` whether it's safe to preload in full.

    def get_queryset(self):
        qs = self.queryset.order_by(self.name_field)
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
    date_active_field = "eligible_to"
    search_fields = ["rank__rank_name", "travel_class"]

    def get_queryset(self):
        qs = self._apply_active_filter(self.queryset)
        ordering = self.request.query_params.get("ordering")
        if ordering == "-name":
            return qs.order_by("-rank__rank_name", "travel_mode")
        return qs.order_by("rank__rank_name", "travel_mode")

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

    def get_queryset(self):
        qs = self.queryset
        # IT Asset Holder's Employee picker only wants users that resolve
        # to a real emp_id (that's what actually gets saved) — a login
        # with no linked employee record isn't a valid pick there.
        if self.request.query_params.get("has_emp"):
            qs = qs.filter(emp__isnull=False)
        return qs


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
    date_active_field = "mapping_to"
    search_fields = ["user__user_name", "user__user_login_id", "rig__rig_name"]

    def get_queryset(self):
        qs = self._apply_active_filter(self.queryset)
        ordering = self.request.query_params.get("ordering")
        return qs.order_by("-user__user_name" if ordering == "-name" else "user__user_name")

    def label_for(self, instance):
        return f"{instance.user.user_name} — {instance.rig.rig_name}"


class MstUserFsCatgMappingViewSet(BaseMasterViewSet):
    queryset = MstUserFsCatgMapping.objects.select_related("user", "fs_category").all()
    serializer_class = MstUserFsCatgMappingSerializer
    entity_key = "masters.user_category_mapping"
    date_active_field = "mapping_to"
    search_fields = ["user__user_name", "user__user_login_id", "fs_category__fs_category_name"]

    def get_queryset(self):
        qs = self._apply_active_filter(self.queryset)
        ordering = self.request.query_params.get("ordering")
        return qs.order_by("-user__user_name" if ordering == "-name" else "user__user_name")

    def label_for(self, instance):
        return f"{instance.user.user_name} — {instance.fs_category.fs_category_name}"


class DocToSignMappingViewSet(BaseMasterViewSet):
    queryset = DocToSignMapping.objects.select_related("employee").all()
    serializer_class = DocToSignMappingSerializer
    entity_key = "masters.doc_to_sign_mapping"
    date_active_field = "sign_to"
    search_fields = ["doc_name", "employee__emp_fname", "employee__emp_sname"]

    def get_queryset(self):
        qs = self._apply_active_filter(self.queryset)
        ordering = self.request.query_params.get("ordering")
        return qs.order_by("-doc_name" if ordering == "-name" else "doc_name")

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
    filterable_fields = ["rank_class"]
    search_fields = ["rank__rank_name"]

    def get_queryset(self):
        qs = self._apply_filterable_fields(self.queryset)
        ordering = self.request.query_params.get("ordering")
        if ordering == "-name":
            return qs.order_by("-rank__rank_name")
        return qs.order_by("rank__rank_name")

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


class MstFinancialYearViewSet(BaseMasterViewSet):
    queryset = MstFinancialYear.objects.all()
    serializer_class = MstFinancialYearSerializer
    entity_key = "masters.financial_years"
    permission_classes = [HasMenuPermissionOrOpenRead]
    name_field = "fin_year_text"
    reference_checks = [("incidents", "Incidents")]
    search_fields = ["fin_year_text", "fin_year_subtext", "assessment_year"]

    def get_queryset(self):
        qs = self.queryset
        ordering = self.request.query_params.get("ordering")
        if ordering in ("name", "-name"):
            return qs.order_by(f"-{self.name_field}" if ordering.startswith("-") else self.name_field)
        return qs.order_by("-fin_year_from")


class MstBusinessGrpViewSet(BaseMasterViewSet):
    """No dedicated nav page yet — reachable only as a dropdown source for
    Company and via direct API access."""

    queryset = MstBusinessGrp.objects.select_related("parent_business_grp").all()
    serializer_class = MstBusinessGrpSerializer
    entity_key = "masters.business_grps"
    permission_classes = [HasMenuPermissionOrOpenRead]
    name_field = "business_grp_name"
    active_field = "business_grp_active"
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
    active_field = "company_active"
    reference_checks = [("cost_centre_mappings", "Cost Centre To Company Mapping"), ("subsidiaries", "Companies")]
    search_fields = ["company_name", "company_abrv", "company_code"]


class CostCentreToCompanyMappingViewSet(BaseMasterViewSet):
    queryset = CostCentreToCompanyMapping.objects.select_related("company", "cost_centre").all()
    serializer_class = CostCentreToCompanyMappingSerializer
    entity_key = "masters.cost_centre_to_company_mapping"
    date_active_field = "mapping_to"
    search_fields = ["company__company_name", "cost_centre__cost_centre_name"]

    def get_queryset(self):
        qs = self._apply_active_filter(self.queryset)
        ordering = self.request.query_params.get("ordering")
        return qs.order_by("-company__company_name" if ordering == "-name" else "company__company_name")

    def label_for(self, instance):
        return f"{instance.company.company_name} — {instance.cost_centre.cost_centre_name}"


class CompanyToLocationMappingViewSet(BaseMasterViewSet):
    queryset = CompanyToLocationMapping.objects.select_related("company", "company_loc").all()
    serializer_class = CompanyToLocationMappingSerializer
    entity_key = "masters.company_to_location_mapping"
    active_field = "company_loc_mapp_active"
    search_fields = ["company__company_name", "company_loc__company_loc_name"]

    def get_queryset(self):
        qs = self._apply_active_filter(self.queryset)
        ordering = self.request.query_params.get("ordering")
        return qs.order_by("-company__company_name" if ordering == "-name" else "company__company_name")

    def label_for(self, instance):
        return f"{instance.company.company_name} — {instance.company_loc.company_loc_name}"


class RigSiteMappingViewSet(BaseMasterViewSet):
    queryset = RigSiteMapping.objects.select_related(
        "rig", "company", "location", "contact_fs_emp_1", "contact_fs_emp_2"
    ).all()
    serializer_class = RigSiteMappingSerializer
    entity_key = "masters.rig_site_mapping"
    date_active_field = "site_to"
    search_fields = ["rig__rig_name", "company__company_name", "camp_office_addr"]

    def get_queryset(self):
        qs = self._apply_active_filter(self.queryset)
        ordering = self.request.query_params.get("ordering")
        return qs.order_by("-rig__rig_name" if ordering == "-name" else "rig__rig_name")

    def label_for(self, instance):
        return f"{instance.rig.rig_name} — {instance.company.company_name}"


class RigCrewExceptionViewSet(BaseMasterViewSet):
    queryset = RigCrewException.objects.select_related("fs_category", "emp_type", "rank", "fs_emp").all()
    serializer_class = RigCrewExceptionSerializer
    entity_key = "masters.rig_crew_exceptions"
    date_active_field = "exception_to"
    search_fields = ["fs_category__fs_category_name", "rank__rank_name", "emp_type__emp_type_name"]

    def get_queryset(self):
        qs = self._apply_active_filter(self.queryset)
        ordering = self.request.query_params.get("ordering")
        return qs.order_by(
            "-fs_category__fs_category_name" if ordering == "-name" else "fs_category__fs_category_name"
        )

    def label_for(self, instance):
        return str(instance)


class CrewScheduleExceptionViewSet(BaseMasterViewSet):
    queryset = CrewScheduleException.objects.select_related("fs_category", "emp_type", "rank", "fs_emp").all()
    serializer_class = CrewScheduleExceptionSerializer
    entity_key = "masters.crew_schedule_exceptions"
    date_active_field = "exception_to"
    search_fields = ["fs_category__fs_category_name", "rank__rank_name", "emp_type__emp_type_name"]

    def get_queryset(self):
        qs = self._apply_active_filter(self.queryset)
        ordering = self.request.query_params.get("ordering")
        return qs.order_by(
            "-fs_category__fs_category_name" if ordering == "-name" else "fs_category__fs_category_name"
        )

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
        ordering = self.request.query_params.get("ordering")
        if ordering in ("name", "-name"):
            return qs.order_by(f"-{self.name_field}" if ordering.startswith("-") else self.name_field)
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
    """Reachable as the IT Assets form's Model search (which derives
    Subtype/Type/Manufacturer from the picked row) and via direct API
    access. Also supports narrowing the other way: the IT Assets form lets
    Manufacturer/Type/Subtype be picked first to filter this list down via
    ?mfg=/?type=/?subtype=, before Model is even opened."""

    queryset = MstItAssetModel.objects.select_related(
        "it_asset_mfg", "it_asset_subtype", "it_asset_subtype__it_asset_type"
    ).all()
    serializer_class = MstItAssetModelSerializer
    entity_key = "masters.it_asset_models"
    permission_classes = [HasMenuPermissionOrOpenRead]
    name_field = "it_asset_model_name"
    reference_checks = [("assets", "IT Assets")]
    search_fields = ["it_asset_model_name"]

    def get_queryset(self):
        qs = super().get_queryset()
        mfg_id = self.request.query_params.get("mfg")
        if mfg_id:
            qs = qs.filter(it_asset_mfg_id=mfg_id)
        subtype_id = self.request.query_params.get("subtype")
        if subtype_id:
            qs = qs.filter(it_asset_subtype_id=subtype_id)
        type_id = self.request.query_params.get("type")
        if type_id:
            qs = qs.filter(it_asset_subtype__it_asset_type_id=type_id)
        return qs


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


class MstVendorTypeViewSet(BaseMasterViewSet):
    queryset = MstVendorType.objects.all()
    serializer_class = MstVendorTypeSerializer
    entity_key = "masters.vendor_types"
    permission_classes = [HasMenuPermissionOrOpenRead]
    name_field = "vendor_type_name"
    reference_checks = [("vendors", "Vendors")]
    search_fields = ["vendor_type_name"]


class MstItAccessoryViewSet(BaseMasterViewSet):
    queryset = MstItAccessory.objects.all()
    serializer_class = MstItAccessorySerializer
    entity_key = "masters.it_accessories"
    permission_classes = [HasMenuPermissionOrOpenRead]
    name_field = "it_accessory_name"
    active_field = "it_accessory_active"
    reference_checks = [("holders", "IT Accessory Holders")]
    search_fields = ["it_accessory_name"]


class ItAccessoryHolderViewSet(BaseMasterViewSet):
    """Standalone accessory holder record — not linked to a specific
    Mst_IT_Asset row, straight copy of legacy it_IT_Accessory_Holder."""

    queryset = ItAccessoryHolder.objects.select_related("it_accessory", "emp", "it_asset_mfg")
    serializer_class = ItAccessoryHolderSerializer
    entity_key = "it_asset.it_accessory_holders"
    name_field = "it_accessory_holder_id"
    date_active_field = "it_accessory_holder_to"
    reference_checks = []
    search_fields = [
        "it_accessory__it_accessory_name", "it_accessory_holder_name", "emp__emp_fname", "emp__emp_sname",
        "it_accessory_sr_no",
    ]

    def get_queryset(self):
        qs = self._apply_active_filter(self.queryset)
        accessory = self.request.query_params.get("it_accessory")
        if accessory:
            qs = qs.filter(it_accessory_id=accessory)
        return qs.order_by("-it_accessory_holder_from")

    def label_for(self, instance):
        return f"{instance.it_accessory} — {instance.it_accessory_holder_name or instance.emp}"


IT_ASSET_ORDERING_FIELDS = {
    "sr_no": "it_asset_sr_no",
    "model": "it_asset_model__it_asset_model_name",
    "asset_tag": "it_asset_tag",
    "mfg": "it_asset_mfg__it_asset_mfg_name",
    "own_company": "own_company__company_name",
    "cur_company": "cur_company__company_name",
    "pur_dt": "it_asset_pur_dt",
}


def _parse_action_date(request):
    """Mark as Scrap / Mark as Lost / Remove Assignment / Reassign all take
    an optional `action_date` (default: today) so a past or future-dated
    record can be entered, not just "right now". Returns None on a missing
    or unparseable value's caller-visible sentinel: missing -> today,
    invalid -> None (caller turns that into a 400)."""
    from django.utils import timezone
    from django.utils.dateparse import parse_date

    raw = request.data.get("action_date")
    if not raw:
        return timezone.localdate()
    return parse_date(raw)


def _close_datetime_for(action_date):
    """it_asset_holder_to is a DateTimeField specifically so a *today*
    close is unambiguous the instant it happens (see the model's note) —
    so today keeps that exact-moment precision, while a backdated or
    future-dated close uses that day's last moment, the same convention
    used when an end date is typed into the holder edit form."""
    from django.utils import timezone

    if action_date == timezone.localdate():
        return timezone.now()
    return timezone.make_aware(datetime.datetime.combine(action_date, datetime.time(23, 59, 59)))


class MstItAssetViewSet(BaseMasterViewSet):
    """Listed as a reports-style table (not the generic masters drawer —
    too many fields for that) with its own list page driving ?search=,
    ?active=, ?holder_type=, ?allocated=(Y|N|S|L — S is Scrap, L is Lost),
    ?own_company=, ?it_asset_type=, ?it_asset_subtype=, ?it_asset_mfg= and
    ?ordering= (one of sr_no/model/asset_tag/mfg/own_company/cur_company/
    pur_dt, prefix '-' to reverse)."""

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
        # `it_asset_allocated` was backfilled from real holder history (was
        # stale — see ItAssetHolderViewSet) and is now kept in sync on every
        # holder create/update/delete, so filtering on it directly is safe
        # and avoids a join on every list request. Scrap and Lost are two
        # further mutually-exclusive buckets on top of it (see
        # mark_scrap/unscrap, mark_lost/unlost) — Unassigned excludes both
        # so none of the three overlap.
        allocated = params.get("allocated")
        if allocated == "Y":
            qs = qs.filter(it_asset_allocated="Y")
        elif allocated == "N":
            qs = qs.filter(
                it_asset_allocated="N", it_asset_scrap_dt__isnull=True, it_asset_lost_dt__isnull=True
            )
        elif allocated == "S":
            qs = qs.filter(it_asset_scrap_dt__isnull=False)
        elif allocated == "L":
            qs = qs.filter(it_asset_lost_dt__isnull=False)
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

    def _retire(self, request, dt_field, label, other_dt_field, other_label):
        """Shared body for mark_scrap/mark_lost: close out whatever holder
        row is currently ongoing (as of an optionally backdated/future-dated
        `action_date`) and retire the asset. Scrap and Lost are mutually
        exclusive — trying to mark one while the other is already set is
        rejected rather than silently overwritten."""
        from django.utils import timezone

        asset = self.get_object()
        if getattr(asset, dt_field) is not None:
            return Response({"error": f"Already marked as {label}."}, status=400)
        if getattr(asset, other_dt_field) is not None:
            return Response(
                {"error": f"This asset is marked as {other_label} — unmark it first."}, status=400
            )
        action_date = _parse_action_date(request)
        if action_date is None:
            return Response({"error": "Invalid action_date."}, status=400)
        close_dt = _close_datetime_for(action_date)
        closed = ItAssetHolder.objects.filter(it_asset=asset, it_asset_holder_to__isnull=True).update(
            it_asset_holder_to=close_dt
        )
        old_snapshot = self._snapshot(asset)
        asset.it_asset_active = "N"
        asset.it_asset_allocated = "N"
        setattr(asset, dt_field, action_date)
        asset.mod_user_id = self._current_user_id(request)
        asset.mod_dt = timezone.now()
        asset.save()
        changes = self._diff(old_snapshot, self._snapshot(asset))
        _audit.record_action(
            request, "update", self.entity_key, asset.pk, f"{self.label_for(asset)} (marked {label})", changes or None
        )
        return Response({"closed_holder_rows": closed, **MstItAssetSerializer(asset).data})

    def _unretire(self, request, dt_field, label):
        from django.utils import timezone

        asset = self.get_object()
        if getattr(asset, dt_field) is None:
            return Response({"error": f"This asset isn't marked as {label}."}, status=400)
        old_snapshot = self._snapshot(asset)
        asset.it_asset_active = "Y"
        setattr(asset, dt_field, None)
        asset.mod_user_id = self._current_user_id(request)
        asset.mod_dt = timezone.now()
        asset.save()
        changes = self._diff(old_snapshot, self._snapshot(asset))
        _audit.record_action(
            request, "update", self.entity_key, asset.pk, f"{self.label_for(asset)} (un-{label})", changes or None
        )
        return Response(MstItAssetSerializer(asset).data)

    @action(detail=True, methods=["post"], url_path="mark-scrap")
    def mark_scrap(self, request, pk=None):
        """Replaces the old manual workaround (typing 'SCRAP' into a holder
        row's name and leaving it open) with one real action. Accepts an
        optional `action_date` (default: today) in the POST body to
        backdate or future-date the record."""
        return self._retire(request, "it_asset_scrap_dt", "scrap", "it_asset_lost_dt", "lost")

    @action(detail=True, methods=["post"], url_path="unscrap")
    def unscrap(self, request, pk=None):
        """Reverses Mark as Scrap: brings the asset back into the active
        fleet. Does not reopen the holder row that scrapping closed — it
        stays Unassigned until reassigned through the normal flow."""
        return self._unretire(request, "it_asset_scrap_dt", "scrap")

    @action(detail=True, methods=["post"], url_path="mark-lost")
    def mark_lost(self, request, pk=None):
        """Same as Mark as Scrap but for a device that's gone missing
        rather than been decommissioned — a separate filter bucket. Accepts
        an optional `action_date` (default: today) to backdate/future-date."""
        return self._retire(request, "it_asset_lost_dt", "lost", "it_asset_scrap_dt", "scrap")

    @action(detail=True, methods=["post"], url_path="unlost")
    def unlost(self, request, pk=None):
        """Reverses Mark as Lost (the device turned up) — same shape as
        Unscrap."""
        return self._unretire(request, "it_asset_lost_dt", "lost")


class MstCompanyLocTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only lookup for Company Location's Type dropdown — writes go
    through Django admin only (see MstCompanyLocType's docstring), so
    there's no BaseMasterViewSet CRUD here, same pattern as Department."""

    queryset = MstCompanyLocType.objects.filter(company_loc_type_active="Y").order_by("company_loc_type_order")
    serializer_class = MstCompanyLocTypeSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["company_loc_type_name", "company_loc_type_code"]


class MstCompanyLocOwnershipViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only lookup for Company Location's Ownership dropdown — same
    admin-only-writes pattern as MstCompanyLocTypeViewSet above."""

    queryset = MstCompanyLocOwnership.objects.filter(company_loc_ownership_active="Y").order_by(
        "company_loc_ownership_order"
    )
    serializer_class = MstCompanyLocOwnershipSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ["company_loc_ownership_name", "company_loc_ownership_code"]


class MstCompanyLocationViewSet(BaseMasterViewSet):
    """Promoted from a read-only dropdown source to a real delegable master
    (General section) — reads stay open to any authenticated user via
    HasMenuPermissionOrOpenRead so the IT Assets/IT Assets Holder forms'
    Location picker keeps working for everyone, same as before; only
    add/edit/delete now go through the real per-user permission grid."""

    queryset = MstCompanyLocation.objects.select_related("location", "country").all()
    serializer_class = MstCompanyLocationSerializer
    entity_key = "masters.company_locations"
    permission_classes = [HasMenuPermissionOrOpenRead]
    name_field = "company_loc_name"
    active_field = "company_loc_active"
    reference_checks = [("it_assets", "IT Assets"), ("it_asset_holdings", "IT Asset Holders")]
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
        "it_asset__own_company", "holder_company", "emp", "holder_user", "department", "company_loc",
    ).all()
    serializer_class = ItAssetHolderSerializer
    entity_key = "it_asset.it_asset_holders"
    name_field = "it_asset_holder_id"
    reference_checks = []
    search_fields = [
        "it_asset__it_asset_sr_no", "it_asset__it_asset_tag", "it_asset__it_asset_sap_code", "holder_name",
        "holder_user__user_name",
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
        # `it_asset_holder_to` is a DateTimeField specifically so this
        # comparison is unambiguous: "ongoing" means no end date, or an end
        # moment still in the future — never "ended earlier today". Remove
        # Assignment / Reassign / Mark as Scrap all close a row by stamping
        # timezone.now(), so a row they closed a second ago is immediately
        # >lte< now and reads as ended, not ongoing-for-the-rest-of-today.
        from django.utils import timezone

        now = timezone.now()
        status = params.get("status")
        if status == "ongoing":
            qs = qs.filter(it_asset_holder_to__isnull=True) | qs.filter(it_asset_holder_to__gt=now)
        elif status == "ended":
            qs = qs.filter(it_asset_holder_to__lte=now)

        ordering = params.get("ordering")
        if ordering and ordering.lstrip("-") == "sr_no":
            field = "it_asset__it_asset_sr_no"
            return qs.order_by(f"-{field}" if ordering.startswith("-") else field)

        # Same intent as legacy's ORDER BY ISNULL(To, GETDATE()+50) DESC —
        # ongoing assignments (no end date) sort first, then most-recently
        # ended first.
        # MySQL's own COALESCE(datetime_column, string_literal_param) comes
        # back over the wire typed as a string, not a datetime — even with
        # the fallback wrapped in Value(output_field=DateTimeField()) — so
        # Django's result converter (which trusts the annotation's declared
        # output_field) crashes trying to timezone-convert a str. Wrapping
        # the whole thing in Cast(..., DateTimeField()) forces MySQL to
        # CAST(... AS DATETIME) and actually report the right column type.
        far_future = Value(
            datetime.datetime(2100, 1, 1, tzinfo=datetime.timezone.utc), output_field=DateTimeField()
        )
        return qs.annotate(
            _sort_to=Cast(Coalesce("it_asset_holder_to", far_future), output_field=DateTimeField())
        ).order_by("-_sort_to", "-it_asset_holder_from")

    def perform_create(self, serializer):
        instance = serializer.save()
        changes = {
            k: {"old": None, "new": v} for k, v in self._snapshot(instance).items() if v not in (None, "")
        }
        _audit.record_action(
            self.request, "create", self.entity_key, instance.pk, self.label_for(instance), changes or None
        )
        self._sync_allocated(instance.it_asset_id)

    def perform_update(self, serializer):
        from django.utils import timezone

        old_snapshot = self._snapshot(serializer.instance)
        uid = self._current_user_id(self.request)
        instance = serializer.save(mod_user_id=uid, mod_dt=timezone.now())
        changes = self._diff(old_snapshot, self._snapshot(instance))
        _audit.record_action(
            self.request, "update", self.entity_key, instance.pk, self.label_for(instance), changes or None
        )
        self._sync_allocated(instance.it_asset_id)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        it_asset_id = instance.it_asset_id
        response = super().destroy(request, *args, **kwargs)
        if response.status_code < 400:
            self._sync_allocated(it_asset_id)
        return response

    @action(detail=True, methods=["post"], url_path="remove-assignment")
    def remove_assignment(self, request, pk=None):
        """One-click close: ends this holder row as of an optionally
        backdated/future-dated `action_date` (default: today — and today
        closes at the exact instant, not just "as of today", see
        it_asset_holder_to's DateTimeField note on the model) without
        needing the full edit form, then syncs the asset back to
        Unassigned."""
        from django.utils import timezone

        instance = self.get_object()
        action_date = _parse_action_date(request)
        if action_date is None:
            return Response({"error": "Invalid action_date."}, status=400)
        now = timezone.now()
        if instance.it_asset_holder_to is not None and instance.it_asset_holder_to <= now:
            return Response({"error": "This assignment has already ended."}, status=400)
        old_snapshot = self._snapshot(instance)
        instance.it_asset_holder_to = _close_datetime_for(action_date)
        instance.mod_user_id = self._current_user_id(request)
        instance.mod_dt = timezone.now()
        instance.save()
        changes = self._diff(old_snapshot, self._snapshot(instance))
        _audit.record_action(
            request, "update", self.entity_key, instance.pk, self.label_for(instance), changes or None
        )
        self._sync_allocated(instance.it_asset_id)
        return Response(self.get_serializer(instance).data)

    @action(detail=False, methods=["post"], url_path="reassign")
    def reassign(self, request):
        """Closes whatever holder row is currently ongoing for the given
        asset (if any) — as of the new record's own `it_asset_holder_from`,
        so a backdated/future-dated reassignment closes the old row and
        opens the new one on the same chosen day — and creates the new one
        in the same request, so a reassignment never leaves the asset
        transiently Unassigned between two separate calls."""
        from django.db import transaction
        from django.utils.dateparse import parse_date

        it_asset_id = request.data.get("it_asset")
        if not it_asset_id:
            return Response({"error": "it_asset is required"}, status=400)
        effective_date = parse_date(request.data.get("it_asset_holder_from") or "")
        if not effective_date:
            return Response(
                {"error": "it_asset_holder_from is required and must be a valid date."}, status=400
            )
        with transaction.atomic():
            ItAssetHolder.objects.filter(it_asset_id=it_asset_id, it_asset_holder_to__isnull=True).update(
                it_asset_holder_to=_close_datetime_for(effective_date)
            )
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            instance = serializer.save()
            changes = {
                k: {"old": None, "new": v} for k, v in self._snapshot(instance).items() if v not in (None, "")
            }
            _audit.record_action(
                request, "create", self.entity_key, instance.pk, f"{self.label_for(instance)} (reassigned)", changes or None
            )
            self._sync_allocated(instance.it_asset_id)
        return Response(self.get_serializer(instance).data, status=201)

    def _sync_allocated(self, it_asset_id):
        """`it_asset_allocated` is kept as a plain column (not derived live)
        so the IT Assets list can filter on it directly without joining —
        recomputed here on every holder create/update/delete so it never
        drifts from the real ongoing-holder-row truth again."""
        is_assigned = ItAssetHolder.objects.filter(
            it_asset_id=it_asset_id, it_asset_holder_to__isnull=True
        ).exists()
        MstItAsset.objects.filter(it_asset_id=it_asset_id).update(
            it_asset_allocated="Y" if is_assigned else "N"
        )

    def label_for(self, instance):
        if instance.holder_user_id:
            who = instance.holder_user.user_name.strip()
        else:
            who = instance.emp or instance.holder_name or "Common"
        return f"{instance.it_asset.it_asset_sr_no} — {who}"
