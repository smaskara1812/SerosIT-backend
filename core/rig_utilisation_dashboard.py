"""Rig Utilisation dashboard — the first of the analytics dashboards
(management/corporate-facing, distinct from the operational Drilling
Report / Performance Dashboard pages, which are per-rig data-entry and
data-export tools respectively).

Utilisation % here matches the legacy serosIS dashboard's own formula
exactly:

    Operating_Hrs / (Operating + Standby + RepairService + RepairRate +
    ZeroRate + RigMove) * 100

This is a DIFFERENT number from Performance Dashboard's "Efficiency %"
(100 - downtime/24), which measures something else (how much of a day's 24
hours were lost to downtime) — both are legitimate, kept intentionally
distinct rather than merged, same reasoning as keeping Notification
Triggers and Mail Recipient Mapping separate.
"""

from datetime import date

from django.db.models import Sum
from django.db.models.functions import TruncMonth
from rest_framework.response import Response
from rest_framework.views import APIView

from .dashboard_access import dashboard_rig_queryset, get_accessible_rig_ids
from .models import DrillingDtl, DrillingDtlOps
from .permissions import HasMenuPermission

NPT_DRILLING_OPS_ID = 24  # "Non productive time" — see mst_drilling_operation

HOUR_FIELDS = [
    "operating_hrs",
    "standby_hrs",
    "repair_service_hrs",
    "repair_rate_hrs",
    "zero_rate_hrs",
    "rig_move_hrs",
]


def _utilisation_pct(totals):
    denom = sum(float(totals.get(f) or 0) for f in HOUR_FIELDS)
    if not denom:
        return None
    return round(float(totals.get("operating_hrs") or 0) / denom * 100, 2)


class RigUtilisationDashboardView(APIView):
    permission_classes = [HasMenuPermission]
    entity_key = "dashboards.rig_utilisation"

    def get(self, request):
        accessible = get_accessible_rig_ids(request)  # None = every rig

        rig_qs = dashboard_rig_queryset()
        if accessible is not None:
            rig_qs = rig_qs.filter(rig_id__in=accessible)
        rig_qs = rig_qs.order_by("rig_name")
        accessible_rigs = list(rig_qs.values("rig_id", "rig_name", "rig_active"))

        # Further narrow to whatever the filter bar asked for, but never
        # outside what this user can actually see — a requested id outside
        # `accessible` is silently dropped rather than erroring, same as
        # any other "?rigs=" filter would just return nothing for it.
        requested = request.query_params.get("rigs")
        if requested:
            requested_ids = {int(x) for x in requested.split(",") if x.strip().isdigit()}
            effective_rig_ids = {r["rig_id"] for r in accessible_rigs} & requested_ids
        else:
            effective_rig_ids = {r["rig_id"] for r in accessible_rigs}

        year_param = request.query_params.get("year")
        year = int(year_param) if year_param and year_param.isdigit() else date.today().year

        dtl_qs = DrillingDtl.objects.filter(rig_id__in=effective_rig_ids, drilling_dtl_dt__year=year)

        available_years = sorted(
            {
                y
                for y in DrillingDtl.objects.filter(rig_id__in={r["rig_id"] for r in accessible_rigs})
                .dates("drilling_dtl_dt", "year")
            }
        )
        available_years = [d.year for d in available_years] or [date.today().year]

        fleet_totals = dtl_qs.aggregate(**{f: Sum(f) for f in HOUR_FIELDS})
        npt_hrs = (
            DrillingDtlOps.objects.filter(
                drilling_ops_id=NPT_DRILLING_OPS_ID,
                drilling_dtl__rig_id__in=effective_rig_ids,
                drilling_dtl__drilling_dtl_dt__year=year,
            ).aggregate(total=Sum("duration"))["total"]
            or 0
        )

        summary = {
            "avg_utilisation_pct": _utilisation_pct(fleet_totals),
            "active_rigs": sum(1 for r in accessible_rigs if r["rig_id"] in effective_rig_ids and r["rig_active"] == "Y"),
            "total_rigs": len(effective_rig_ids),
            "operating_hrs": float(fleet_totals.get("operating_hrs") or 0),
            "npt_hrs": float(npt_hrs),
        }

        # Utilisation % by rig, by month — one line per rig on the frontend.
        rig_names = {r["rig_id"]: r["rig_name"] for r in accessible_rigs}
        monthly_rows = (
            dtl_qs.annotate(month=TruncMonth("drilling_dtl_dt"))
            .values("month", "rig_id")
            .annotate(**{f: Sum(f) for f in HOUR_FIELDS})
            .order_by("month")
        )
        utilisation_by_rig_month = [
            {
                "month": row["month"].strftime("%Y-%m"),
                "rig_id": row["rig_id"],
                "rig_name": rig_names.get(row["rig_id"], ""),
                "utilisation_pct": _utilisation_pct(row),
            }
            for row in monthly_rows
        ]

        # Fleet-wide hours breakdown by category, by month — stacked bar.
        fleet_monthly_rows = (
            dtl_qs.annotate(month=TruncMonth("drilling_dtl_dt"))
            .values("month")
            .annotate(**{f: Sum(f) for f in HOUR_FIELDS})
            .order_by("month")
        )
        hours_by_month = [
            {
                "month": row["month"].strftime("%Y-%m"),
                **{f: float(row.get(f) or 0) for f in HOUR_FIELDS},
            }
            for row in fleet_monthly_rows
        ]

        # Per-rig utilisation comparison for the year — ratio computed from
        # the rig's own yearly totals, not an average of its monthly
        # percentages (a low-activity month would otherwise skew it).
        per_rig_rows = dtl_qs.values("rig_id").annotate(**{f: Sum(f) for f in HOUR_FIELDS})
        utilisation_by_rig = sorted(
            (
                {
                    "rig_id": row["rig_id"],
                    "rig_name": rig_names.get(row["rig_id"], ""),
                    "utilisation_pct": _utilisation_pct(row),
                }
                for row in per_rig_rows
            ),
            key=lambda r: r["rig_name"],
        )

        return Response(
            {
                "years": available_years,
                "year": year,
                "rigs": [{"rig_id": r["rig_id"], "rig_name": r["rig_name"]} for r in accessible_rigs],
                "summary": summary,
                "utilisation_by_rig_month": utilisation_by_rig_month,
                "hours_by_month": hours_by_month,
                "utilisation_by_rig": utilisation_by_rig,
            }
        )
