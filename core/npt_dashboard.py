"""NPT (Non-Productive Time) Analysis dashboard — hours lost to drilling_ops
code 24 ("Non productive time"), by month and by rig.

This is a flat hours dashboard, not a "by reason" breakdown: NPT is a single
lumped ops code in this schema (no sub-category/cause code exists), so there
is no structured field to group by. Every NPT row does carry a mandatory
free-text `operation_desc` narrative (100% populated on existing NPT rows),
but a raw text table of those isn't the "quick glance for management" this
page is meant to be — it was tried and deliberately pulled back out. Until
there's a real visual treatment for that text (keyword/theme tagging,
classification into causes, etc.), this view stays hours-only.
"""

from datetime import date

from django.db.models import Sum
from django.db.models.functions import TruncMonth
from rest_framework.response import Response
from rest_framework.views import APIView

from .dashboard_access import dashboard_rig_queryset, get_accessible_rig_ids
from .models import DrillingDtlOps
from .permissions import HasMenuPermission

NPT_DRILLING_OPS_ID = 24  # "Non productive time" — see mst_drilling_operation


class NptDashboardView(APIView):
    permission_classes = [HasMenuPermission]
    entity_key = "dashboards.npt_analysis"

    def get(self, request):
        accessible = get_accessible_rig_ids(request)  # None = every rig

        rig_qs = dashboard_rig_queryset()
        if accessible is not None:
            rig_qs = rig_qs.filter(rig_id__in=accessible)
        accessible_rigs = list(rig_qs.order_by("rig_name").values("rig_id", "rig_name"))
        rig_names = {r["rig_id"]: r["rig_name"] for r in accessible_rigs}

        requested = request.query_params.get("rigs")
        if requested:
            requested_ids = {int(x) for x in requested.split(",") if x.strip().isdigit()}
            effective_rig_ids = {r["rig_id"] for r in accessible_rigs} & requested_ids
        else:
            effective_rig_ids = {r["rig_id"] for r in accessible_rigs}

        year_param = request.query_params.get("year")
        year = int(year_param) if year_param and year_param.isdigit() else date.today().year

        npt_qs = DrillingDtlOps.objects.filter(
            drilling_ops_id=NPT_DRILLING_OPS_ID,
            drilling_dtl__rig_id__in=effective_rig_ids,
            drilling_dtl__drilling_dtl_dt__year=year,
        )

        available_years = sorted(
            {
                d.year
                for d in DrillingDtlOps.objects.filter(
                    drilling_ops_id=NPT_DRILLING_OPS_ID,
                    drilling_dtl__rig_id__in={r["rig_id"] for r in accessible_rigs},
                ).dates("drilling_dtl__drilling_dtl_dt", "year")
            }
        ) or [date.today().year]

        total_npt_hrs = float(npt_qs.aggregate(total=Sum("duration"))["total"] or 0)
        event_count = npt_qs.count()

        by_rig_rows = list(
            npt_qs.values("drilling_dtl__rig_id").annotate(hours=Sum("duration")).order_by("-hours")
        )
        rigs_with_npt = sum(1 for r in by_rig_rows if r["hours"])

        summary = {
            "total_npt_hrs": total_npt_hrs,
            "event_count": event_count,
            "rigs_with_npt": rigs_with_npt,
            "total_rigs": len(effective_rig_ids),
            "avg_npt_hrs_per_rig": round(total_npt_hrs / len(effective_rig_ids), 1) if effective_rig_ids else 0,
        }

        npt_by_rig = [
            {
                "rig_id": row["drilling_dtl__rig_id"],
                "rig_name": rig_names.get(row["drilling_dtl__rig_id"], ""),
                "hours": float(row["hours"] or 0),
            }
            for row in by_rig_rows
        ]

        monthly_fleet_rows = (
            npt_qs.annotate(month=TruncMonth("drilling_dtl__drilling_dtl_dt"))
            .values("month")
            .annotate(hours=Sum("duration"))
            .order_by("month")
        )
        npt_by_month = [
            {"month": row["month"].strftime("%Y-%m"), "hours": float(row["hours"] or 0)}
            for row in monthly_fleet_rows
        ]

        # Powers the trend chart's month drill-down into a per-rig
        # breakdown, same reuse pattern as Rig Utilisation's
        # hours_by_rig_month (one aggregation query, not a second one fired
        # only when a month is clicked).
        monthly_rig_rows = (
            npt_qs.annotate(month=TruncMonth("drilling_dtl__drilling_dtl_dt"))
            .values("month", "drilling_dtl__rig_id")
            .annotate(hours=Sum("duration"))
            .order_by("month")
        )
        npt_by_rig_month = [
            {
                "month": row["month"].strftime("%Y-%m"),
                "rig_id": row["drilling_dtl__rig_id"],
                "rig_name": rig_names.get(row["drilling_dtl__rig_id"], ""),
                "hours": float(row["hours"] or 0),
            }
            for row in monthly_rig_rows
        ]

        return Response(
            {
                "years": available_years,
                "year": year,
                "rigs": [{"rig_id": r["rig_id"], "rig_name": r["rig_name"]} for r in accessible_rigs],
                "summary": summary,
                "npt_by_month": npt_by_month,
                "npt_by_rig": npt_by_rig,
                "npt_by_rig_month": npt_by_rig_month,
            }
        )
