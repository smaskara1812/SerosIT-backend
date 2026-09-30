"""IT Asset Overview dashboard — fleet-wide view of the hardware estate.

Unlike the rig-based dashboards, IT assets have no rig FK at all (ownership
runs through own_company/department/emp instead), so this page does not use
dashboard_access.py's rig-scoping — it's gated purely by menu permission,
the same as ItAssetReportPage.

AMC data is present on the model but populated on only ~30 of 10,000+ rows
in practice, too thin to build a KPI on — warranty (populated on the large
majority of rows) is used instead as the "needs attention" signal.
"""

from django.db.models import Count
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MstItAsset, MstItAssetType
from .permissions import HasMenuPermission

WARRANTY_SOON_DAYS = 90

ALLOCATED_LABELS = {
    "Y": "Assigned",
    "N": "Unassigned",
    "S": "Scrap",
    "L": "Lost",
}

HOLDER_TYPE_LABELS = {
    "C": "Common",
    "I": "Individual",
    "V": "Vessel",
    "L": "Location",
}


class ItAssetDashboardView(APIView):
    permission_classes = [HasMenuPermission]
    entity_key = "dashboards.it_asset_overview"

    def get(self, request):
        today = timezone.now().date()

        qs = MstItAsset.objects.all()

        active_param = request.query_params.get("active", "Y")
        if active_param in ("Y", "N"):
            qs = qs.filter(it_asset_active=active_param)

        types_param = request.query_params.get("types")
        if types_param:
            type_ids = {int(x) for x in types_param.split(",") if x.strip().isdigit()}
            if type_ids:
                qs = qs.filter(it_asset_type_id__in=type_ids)

        companies_param = request.query_params.get("companies")
        if companies_param:
            company_ids = {int(x) for x in companies_param.split(",") if x.strip().isdigit()}
            if company_ids:
                qs = qs.filter(own_company_id__in=company_ids)

        total = qs.count()
        unassigned = qs.filter(it_asset_allocated="N").count()
        warranty_expired = qs.filter(it_asset_warranty_upto__lt=today).count()
        warranty_soon = qs.filter(
            it_asset_warranty_upto__gte=today,
            it_asset_warranty_upto__lte=today + timezone.timedelta(days=WARRANTY_SOON_DAYS),
        ).count()

        summary = {
            "total_assets": total,
            "unassigned": unassigned,
            "warranty_expired": warranty_expired,
            "warranty_expiring_soon": warranty_soon,
        }

        by_type = list(
            qs.values("it_asset_type_id", "it_asset_type__it_asset_type_name")
            .annotate(count=Count("it_asset_id"))
            .order_by("-count")
        )
        assets_by_type = [
            {"type_id": r["it_asset_type_id"], "type_name": r["it_asset_type__it_asset_type_name"], "count": r["count"]}
            for r in by_type
        ]

        by_year_type = (
            qs.exclude(it_asset_pur_dt=None)
            .values("it_asset_pur_dt__year", "it_asset_type_id", "it_asset_type__it_asset_type_name")
            .annotate(count=Count("it_asset_id"))
            .order_by("it_asset_pur_dt__year")
        )
        year_totals = {}
        by_year_detail = {}
        for row in by_year_type:
            year = row["it_asset_pur_dt__year"]
            year_totals[year] = year_totals.get(year, 0) + row["count"]
            by_year_detail.setdefault(year, []).append(
                {
                    "type_id": row["it_asset_type_id"],
                    "type_name": row["it_asset_type__it_asset_type_name"],
                    "count": row["count"],
                }
            )
        purchase_year_cohort = [{"year": y, "count": year_totals[y]} for y in sorted(year_totals)]
        purchase_year_cohort_detail = {y: sorted(rows, key=lambda r: -r["count"]) for y, rows in by_year_detail.items()}

        allocation_counts = dict(qs.values_list("it_asset_allocated").annotate(count=Count("it_asset_id")))
        allocation_status = [
            {"status": code, "label": ALLOCATED_LABELS.get(code, code or "Unspecified"), "count": count}
            for code, count in allocation_counts.items()
        ]

        warranty_no_data = qs.filter(it_asset_warranty_upto=None).count()
        warranty_valid = total - warranty_expired - warranty_soon - warranty_no_data
        warranty_status = [
            {"status": "expired", "label": "Expired", "count": warranty_expired},
            {"status": "expiring_soon", "label": f"Expiring ≤{WARRANTY_SOON_DAYS}d", "count": warranty_soon},
            {"status": "valid", "label": "Valid", "count": max(warranty_valid, 0)},
            {"status": "no_data", "label": "No Data", "count": warranty_no_data},
        ]

        top_companies = list(
            qs.values("own_company_id", "own_company__company_name")
            .annotate(count=Count("it_asset_id"))
            .order_by("-count")[:10]
        )
        assets_by_company = [
            {"company_id": r["own_company_id"], "company_name": r["own_company__company_name"], "count": r["count"]}
            for r in top_companies
        ]

        all_types = list(
            MstItAssetType.objects.order_by("it_asset_type_name").values("it_asset_type_id", "it_asset_type_name")
        )
        all_companies = list(
            MstItAsset.objects.exclude(own_company=None)
            .order_by("own_company__company_name")
            .values("own_company_id", "own_company__company_name")
            .distinct()
        )

        return Response(
            {
                "as_of": today,
                "summary": summary,
                "types": [{"type_id": t["it_asset_type_id"], "type_name": t["it_asset_type_name"]} for t in all_types],
                "companies": [
                    {"company_id": c["own_company_id"], "company_name": c["own_company__company_name"]}
                    for c in all_companies
                ],
                "assets_by_type": assets_by_type,
                "purchase_year_cohort": purchase_year_cohort,
                "purchase_year_cohort_detail": purchase_year_cohort_detail,
                "allocation_status": allocation_status,
                "warranty_status": warranty_status,
                "assets_by_company": assets_by_company,
            }
        )
