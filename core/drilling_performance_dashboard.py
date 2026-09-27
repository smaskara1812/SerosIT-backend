"""Drilling Performance dashboard — the fleet-wide rollup of the same
measures Operations Analytics / Drilling & Tripping Analysis already
compute one rig (and one date range) at a time. Deliberately reuses their
exact formulas rather than the legacy serosIS chatbot's own (different)
ROP formula, so this app doesn't end up with two conflicting definitions
of "ROP" the way Rig Utilisation's "Utilisation %" and Performance
Dashboard's "Efficiency %" are two different, intentionally-kept-separate
numbers.

ROP (m/hr)   = average of |DrillingDtlOps.rop_trip_mh| for "Drill actual"
               ops rows — same as DrillingTrippingAnalysisView.
Meterage     = sum(DrillingDtl.drilling_meterage) — same as
               OperationsAnalyticsView.
Ops hours    = sum(DrillingDtlOps.duration) grouped by operation — same
               as OperationsAnalyticsView.
Flat time    = "Drill actual" ops rows with rop_trip_mh <= 0 (hours spent
               drilling with no forward depth progress) — a plain fact off
               the same rop_trip_mh field, no separate formula invented.
"""

from datetime import date

from django.db.models import Count, Sum
from django.db.models.functions import Abs
from rest_framework.response import Response
from rest_framework.views import APIView

from .dashboard_access import dashboard_rig_queryset, get_accessible_rig_ids
from .models import DrillingDtl, DrillingDtlOps, MstDrillingOperation
from .permissions import HasMenuPermission

DRILL_ACTUAL_CODE_NO = 2


def _drill_actual_ops_id():
    try:
        return MstDrillingOperation.objects.get(drilling_ops_code_no=DRILL_ACTUAL_CODE_NO).drilling_ops_id
    except MstDrillingOperation.DoesNotExist:
        return None


class DrillingPerformanceDashboardView(APIView):
    permission_classes = [HasMenuPermission]
    entity_key = "dashboards.drilling_performance"

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

        available_years = sorted(
            {
                d.year
                for d in DrillingDtl.objects.filter(
                    rig_id__in={r["rig_id"] for r in accessible_rigs}
                ).dates("drilling_dtl_dt", "year")
            }
        ) or [date.today().year]

        dtl_qs = DrillingDtl.objects.filter(rig_id__in=effective_rig_ids, drilling_dtl_dt__year=year)
        drill_actual_id = _drill_actual_ops_id()
        drill_ops_qs = DrillingDtlOps.objects.filter(
            drilling_ops_id=drill_actual_id,
            drilling_dtl__rig_id__in=effective_rig_ids,
            drilling_dtl__drilling_dtl_dt__year=year,
        )

        total_metres = dtl_qs.aggregate(total=Sum("drilling_meterage"))["total"] or 0
        # Avg() over Abs() needs the annotate-then-aggregate form, not a
        # bare expression inside aggregate().
        rop_row = drill_ops_qs.annotate(abs_rop=Abs("rop_trip_mh")).aggregate(
            avg_rop=Sum("abs_rop"), n=Count("abs_rop")
        )
        avg_rop = round(float(rop_row["avg_rop"]) / rop_row["n"], 2) if rop_row["n"] else None

        drill_hours = drill_ops_qs.aggregate(total=Sum("duration"))["total"] or 0
        drill_ops_count = drill_ops_qs.count()
        flat_hours = (
            drill_ops_qs.filter(rop_trip_mh__lte=0).aggregate(total=Sum("duration"))["total"] or 0
        )

        summary = {
            "avg_rop_m_hr": avg_rop,
            "total_metres": float(total_metres),
            "drill_hours": float(drill_hours),
            "drill_ops_count": drill_ops_count,
            "flat_hours": float(flat_hours),
        }

        # ROP by hole section — same "average of |rop_trip_mh|" as Drilling
        # & Tripping Analysis, just rolled up across every accessible rig
        # instead of asking for one well at a time.
        section_rows = (
            drill_ops_qs.annotate(abs_rop=Abs("rop_trip_mh"))
            .values("drilling_section__drilling_section_name")
            .annotate(avg_rop=Sum("abs_rop"), n=Count("abs_rop"))
            .order_by("drilling_section__drilling_section_name")
        )
        rop_by_section = [
            {
                "section": row["drilling_section__drilling_section_name"],
                "avg_rop": round(float(row["avg_rop"]) / row["n"], 2) if row["n"] else None,
            }
            for row in section_rows
        ]

        # Ops breakdown by type — fleet total hours, top 10 by hours.
        ops_rows = (
            DrillingDtlOps.objects.filter(
                drilling_dtl__rig_id__in=effective_rig_ids, drilling_dtl__drilling_dtl_dt__year=year
            )
            .values("drilling_ops__drilling_ops_name")
            .annotate(total_hrs=Sum("duration"))
            .order_by("-total_hrs")[:10]
        )
        total_all_hours = float(drill_hours) or 0
        total_logged_hours = (
            DrillingDtlOps.objects.filter(
                drilling_dtl__rig_id__in=effective_rig_ids, drilling_dtl__drilling_dtl_dt__year=year
            ).aggregate(total=Sum("duration"))["total"]
            or 0
        )
        ops_breakdown = [
            {
                "operation": row["drilling_ops__drilling_ops_name"],
                "hours": float(row["total_hrs"] or 0),
                "pct_of_total": round(float(row["total_hrs"] or 0) / float(total_logged_hours) * 100, 1)
                if total_logged_hours
                else None,
            }
            for row in ops_rows
        ]

        # Metres drilled by rig.
        metres_rows = dtl_qs.values("rig_id").annotate(total=Sum("drilling_meterage"))
        metres_by_rig = sorted(
            (
                {"rig_id": row["rig_id"], "rig_name": rig_names.get(row["rig_id"], ""), "metres": float(row["total"] or 0)}
                for row in metres_rows
            ),
            key=lambda r: r["rig_name"],
        )

        # Flat time by rig — which rigs are logging Drill Actual hours with
        # zero/negative depth progress, and how many hours that is.
        flat_rows = (
            drill_ops_qs.filter(rop_trip_mh__lte=0)
            .values("drilling_dtl__rig_id")
            .annotate(total=Sum("duration"))
        )
        flat_by_rig = sorted(
            (
                {
                    "rig_id": row["drilling_dtl__rig_id"],
                    "rig_name": rig_names.get(row["drilling_dtl__rig_id"], ""),
                    "flat_hours": float(row["total"] or 0),
                }
                for row in flat_rows
            ),
            key=lambda r: -r["flat_hours"],
        )

        return Response(
            {
                "years": available_years,
                "year": year,
                "rigs": accessible_rigs,
                "summary": summary,
                "rop_by_section": rop_by_section,
                "ops_breakdown": ops_breakdown,
                "metres_by_rig": metres_by_rig,
                "flat_by_rig": flat_by_rig,
            }
        )
