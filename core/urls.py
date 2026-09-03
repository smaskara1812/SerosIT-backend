from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import masters_views, reports_views, views

router = DefaultRouter()
router.register("reports/incidents", reports_views.IncidentViewSet, basename="report-incident")
router.register("reports/hazard-cards", reports_views.HazardCardViewSet, basename="report-hazard-card")
router.register("reports/it-assets", reports_views.ItAssetReportViewSet, basename="report-it-asset")
router.register("masters/cost-centre-types", masters_views.MstCostCentreTypeViewSet, basename="mst-cost-centre-type")
router.register("masters/contractors", masters_views.MstContractorViewSet, basename="mst-contractor")
router.register("masters/cert-institutes", masters_views.MstCertInstituteViewSet, basename="mst-cert-institute")
router.register(
    "masters/email-notification-types",
    masters_views.MstEmailNotificationTypeViewSet,
    basename="mst-email-notification-type",
)
router.register("masters/operators", masters_views.MstOperatorViewSet, basename="mst-operator")
router.register("masters/rig-types", masters_views.MstRigTypeViewSet, basename="mst-rig-type")
router.register("masters/rig-subtypes", masters_views.MstRigSubtypeViewSet, basename="mst-rig-subtype")
router.register("masters/rigs", masters_views.MstRigViewSet, basename="mst-rig")
router.register("masters/cost-centres", masters_views.MstCostCentreViewSet, basename="mst-cost-centre")
router.register("masters/competency", masters_views.MstCompetencyViewSet, basename="mst-competency")
router.register("masters/departments", masters_views.MstDepartmentViewSet, basename="mst-department")
router.register("masters/fs-categories", masters_views.MstFsCategoryViewSet, basename="mst-fs-category")
router.register("masters/ranks", masters_views.MstRankViewSet, basename="mst-rank")
router.register(
    "masters/job-description-headers",
    masters_views.JobDescriptionHdrViewSet,
    basename="jd-header",
)
router.register(
    "masters/job-description-details",
    masters_views.JobDescriptionDtlViewSet,
    basename="jd-detail",
)
router.register(
    "masters/travel-eligibility",
    masters_views.TravelEligibilityViewSet,
    basename="travel-eligibility",
)
router.register(
    "masters/reporting-structure",
    masters_views.ReportingStructureViewSet,
    basename="reporting-structure",
)
router.register("masters/rig-operations", masters_views.MstRigOperationViewSet, basename="rig-operation")
router.register(
    "masters/contact-exposure-types",
    masters_views.MstContactExposureTypeViewSet,
    basename="contact-exposure-type",
)
router.register("masters/indicator-types", masters_views.MstIndicatorTypeViewSet, basename="indicator-type")
router.register(
    "masters/indicator-subtypes",
    masters_views.MstIndicatorSubtypeViewSet,
    basename="indicator-subtype",
)
router.register("masters/parts-of-body", masters_views.MstPartsOfBodyViewSet, basename="parts-of-body")
router.register("masters/qhse-categories", masters_views.MstQhseCategoryViewSet, basename="qhse-category")
router.register("masters/hse-activities", masters_views.MstHseActivityViewSet, basename="hse-activity")
router.register("masters/hse-consumables", masters_views.MstHseConsumableViewSet, basename="hse-consumable")
router.register("masters/hazard-types", masters_views.MstHazardTypeViewSet, basename="hazard-type")
router.register("masters/users", masters_views.MstUserViewSet, basename="mst-user")
router.register("masters/employees", masters_views.MstEmployeeViewSet, basename="mst-employee")
router.register(
    "masters/user-rig-mapping",
    masters_views.MstUserRigMappingViewSet,
    basename="user-rig-mapping",
)
router.register(
    "masters/user-category-mapping",
    masters_views.MstUserFsCatgMappingViewSet,
    basename="user-category-mapping",
)
router.register(
    "masters/doc-to-sign-mapping",
    masters_views.DocToSignMappingViewSet,
    basename="doc-to-sign-mapping",
)
router.register(
    "masters/interviewer-mapping",
    masters_views.MstInterviewerViewSet,
    basename="interviewer-mapping",
)
router.register(
    "masters/fs-catg-to-rig-type-mapping",
    masters_views.FsCatgToRigTypeMappingViewSet,
    basename="fs-catg-to-rig-type-mapping",
)
router.register(
    "masters/rank-classification",
    masters_views.RankClassificationViewSet,
    basename="rank-classification",
)
router.register("masters/emp-natures", masters_views.MstEmpNatureViewSet, basename="mst-emp-nature")
router.register("masters/emp-types", masters_views.MstEmpTypeViewSet, basename="mst-emp-type")
router.register(
    "masters/nationality-to-emp-type-mapping",
    masters_views.NationalityToEmpTypeMappingViewSet,
    basename="nationality-to-emp-type-mapping",
)
router.register(
    "masters/crew-change-reliever-mapping",
    masters_views.CrewChangeRelieverMappingViewSet,
    basename="crew-change-reliever-mapping",
)
router.register("masters/workgroups", masters_views.MstWorkgroupViewSet, basename="mst-workgroup")
router.register(
    "masters/wkgrp-indicator-type-mapping",
    masters_views.WkgrpIndicatorTypeMappingViewSet,
    basename="wkgrp-indicator-type-mapping",
)
router.register(
    "masters/organisational-grps", masters_views.MstOrganisationalGrpViewSet, basename="mst-organisational-grp"
)
router.register("masters/business-grps", masters_views.MstBusinessGrpViewSet, basename="mst-business-grp")
router.register("masters/companies", masters_views.MstCompanyViewSet, basename="mst-company")
router.register(
    "masters/cost-centre-to-company-mapping",
    masters_views.CostCentreToCompanyMappingViewSet,
    basename="cost-centre-to-company-mapping",
)
router.register(
    "masters/company-to-location-mapping",
    masters_views.CompanyToLocationMappingViewSet,
    basename="company-to-location-mapping",
)
router.register(
    "masters/rig-site-mapping", masters_views.RigSiteMappingViewSet, basename="rig-site-mapping"
)
router.register(
    "masters/rig-crew-exceptions", masters_views.RigCrewExceptionViewSet, basename="rig-crew-exception"
)
router.register(
    "masters/crew-schedule-exceptions",
    masters_views.CrewScheduleExceptionViewSet,
    basename="crew-schedule-exception",
)
router.register("masters/continents", masters_views.MstContinentViewSet, basename="mst-continent")
router.register("masters/countries", masters_views.MstCountryViewSet, basename="mst-country")
router.register("masters/country-states", masters_views.MstCountryStateViewSet, basename="mst-country-state")
router.register("masters/vessel-depts", masters_views.MstVesselDeptViewSet, basename="mst-vessel-dept")
router.register("masters/locations", masters_views.MstLocationViewSet, basename="location")
router.register("masters/currencies", masters_views.MstCurrencyViewSet, basename="currency")
router.register("masters/drilling-rate-types", masters_views.MstDrillingRateViewSet, basename="drilling-rate-type")
router.register("masters/project-contracts", masters_views.ProjectContractViewSet, basename="project-contract")
router.register(
    "masters/project-contract-lines",
    masters_views.ProjectContractDtlViewSet,
    basename="project-contract-line",
)
router.register(
    "masters/project-drilling-rates",
    masters_views.ProjectDrillingRateViewSet,
    basename="project-drilling-rate",
)
router.register(
    "masters/drilling-operations",
    masters_views.MstDrillingOperationViewSet,
    basename="drilling-operation",
)
router.register(
    "masters/drilling-sections",
    masters_views.MstDrillingSectionViewSet,
    basename="drilling-section",
)
router.register(
    "masters/drilling-work-shifts",
    masters_views.MstDrillingWorkShiftViewSet,
    basename="drilling-work-shift",
)
router.register("masters/it-asset-types", masters_views.MstItAssetTypeViewSet, basename="mst-it-asset-type")
router.register(
    "masters/it-asset-subtypes", masters_views.MstItAssetSubtypeViewSet, basename="mst-it-asset-subtype"
)
router.register("masters/it-asset-mfgs", masters_views.MstItAssetMfgViewSet, basename="mst-it-asset-mfg")
router.register(
    "masters/it-asset-models", masters_views.MstItAssetModelViewSet, basename="mst-it-asset-model"
)
router.register("masters/vendors", masters_views.MstxVendorViewSet, basename="mstx-vendor")
router.register("masters/vendor-types", masters_views.MstVendorTypeViewSet, basename="mst-vendor-type")
router.register("it-asset/it-assets", masters_views.MstItAssetViewSet, basename="it-asset")
router.register(
    "masters/company-locations", masters_views.MstCompanyLocationViewSet, basename="mst-company-location"
)
router.register(
    "masters/company-loc-types", masters_views.MstCompanyLocTypeViewSet, basename="mst-company-loc-type"
)
router.register(
    "masters/company-loc-ownerships",
    masters_views.MstCompanyLocOwnershipViewSet,
    basename="mst-company-loc-ownership",
)
router.register(
    "it-asset/it-asset-holders", masters_views.ItAssetHolderViewSet, basename="it-asset-holder"
)
router.register("masters/it-accessories", masters_views.MstItAccessoryViewSet, basename="mst-it-accessory")
router.register(
    "masters/financial-years", masters_views.MstFinancialYearViewSet, basename="mst-financial-year"
)
router.register(
    "masters/buss-cert-issue-authorities",
    masters_views.MstBussCertIssueAuthorityViewSet,
    basename="mst-buss-cert-issue-authority",
)
router.register(
    "masters/buss-cert-types", masters_views.MstBussCertTypeViewSet, basename="mst-buss-cert-type"
)
router.register("masters/buss-certs", masters_views.MstBussCertViewSet, basename="mst-buss-cert")
router.register(
    "it-asset/it-accessory-holders", masters_views.ItAccessoryHolderViewSet, basename="it-accessory-holder"
)

urlpatterns = [
    path("", include(router.urls)),
    path("health/", views.health, name="health"),
    path("auth/token/", views.AuditedTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/me/", views.me, name="me"),
    path("auth/logout/", views.logout_api, name="logout"),
    # User Rights
    path("admin/users/", views.admin_users_api, name="admin_users"),
    path("admin/users/<int:user_id>/perms/", views.admin_user_perms_api, name="admin_user_perms"),
    path("admin/users/<int:user_id>/perms/save/",views.admin_user_perms_save_api,name="admin_user_perms_save"),
    path("admin/users/<int:user_id>/toggle-admin/",views.admin_user_admin_toggle_api,name="admin_user_admin_toggle"),
    # Permission presets
    path("admin/permission-presets/", views.admin_permission_presets_api, name="admin_permission_presets"),
    path(
        "admin/permission-presets/create/",
        views.admin_permission_preset_create_api,
        name="admin_permission_preset_create",
    ),
    path(
        "admin/permission-presets/<int:preset_id>/delete/",
        views.admin_permission_preset_delete_api,
        name="admin_permission_preset_delete",
    ),
    # Audit Trail
    path("admin/audit/facets/", views.admin_audit_facets_api, name="admin_audit_facets"),
    path("admin/audit/", views.admin_audit_list_api, name="admin_audit_list"),
    # User Management
    path("admin/user-management/",views.admin_user_management_list_api,name="admin_user_management_list"),
    path("admin/user-management/<int:user_id>/",views.admin_user_management_get_api,name="admin_user_management_get"),
    path("admin/user-management/<int:user_id>/update/",views.admin_user_management_update_api,name="admin_user_management_update"),
    path("admin/user-management/create/",views.admin_user_management_create_api,name="admin_user_management_create"),
    path("admin/user-management/<int:user_id>/set-password/",views.admin_user_management_set_password_api,name="admin_user_management_set_password"),
    path("admin/user-management/<int:user_id>/remove-password/",views.admin_user_management_remove_password_api,name="admin_user_management_remove_password"),
    path("admin/user-management/<int:user_id>/toggle-active/",views.admin_user_management_toggle_active_api,name="admin_user_management_toggle_active"),
]
