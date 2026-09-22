import calendar
import csv
from datetime import date
from decimal import Decimal

from django.db.models import Q, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DrillingDtl, MstFinancialYear
from .permissions import HasMenuPermission

NUMERIC_FIELDS = [
    "received_diesel",
    "consumption_diesel",
    "received_water",
    "generated_water",
    "consumption_water",
    "operating_hrs",
    "standby_hrs",
    "repair_service_hrs",
    "repair_rate_hrs",
    "zero_rate_hrs",
    "drilling_meterage",
]

CSV_HEADER = [
    "Rig", "Well", "Period",
    "Received Diesel", "Consumed Diesel", "Received Water", "Generated Water", "Consumed Water",
    "Operating Hrs", "Standby Hrs", "Service Hrs", "Repair Rate Hrs", "Zero Rate Hrs",
    "Drilling Meterage", "Efficiency %",
]

DEFAULT_PAGE_SIZE = 200
MAX_PAGE_SIZE = 500


def _well_label(location, anchor_dt):
    # Matches the legacy dashboard's "<location>(<first anchor down date>)"
    # well label — DrillingHdr.location is just the bare well name, the
    # anchor date is what disambiguates rig-moves back onto the same well.
    if not location:
        return ""
    if not anchor_dt:
        return location
    return f"{location}({anchor_dt:%d/%m/%Y})"


def _daily_efficiency(repair_service_hrs, repair_rate_hrs, zero_rate_hrs):
    # Legacy formula (the one branch of the source stored procedure that
    # isn't self-contradictory — see _monthly_efficiency below): a day's
    # downtime hours as a fraction of the 24 hours available that day,
    # subtracted from 100.
    downtime = (repair_service_hrs or 0) + (repair_rate_hrs or 0) + (zero_rate_hrs or 0)
    return round(Decimal(100) - (Decimal(downtime) / Decimal(24) * Decimal(100)), 2)


def _monthly_efficiency(repair_service_hrs, repair_rate_hrs, zero_rate_hrs, days_in_month):
    # The legacy stored procedure's monthly branch divides by a column
    # ("[Opr + Stdby / Tot Hrs]") that its own source only ever defines
    # inside a commented-out block — i.e. the original monthly formula
    # doesn't actually run as written. This generalizes the (working) daily
    # formula instead: total downtime hours across the month, as a fraction
    # of the total hours available that month (24 * days in month).
    downtime = (repair_service_hrs or 0) + (repair_rate_hrs or 0) + (zero_rate_hrs or 0)
    total_hrs = Decimal(24) * Decimal(days_in_month)
    return round(Decimal(100) - (Decimal(downtime) / total_hrs * Decimal(100)), 2)


def _daily_row(d):
    return {
        "rig": d.rig.rig_name if d.rig_id else "",
        "well": _well_label(d.drilling_hdr.location if d.drilling_hdr_id else "", d.drilling_hdr.first_anchor_down_dt if d.drilling_hdr_id else None),
        "period": d.drilling_dtl_dt.strftime("%d-%m-%Y"),
        **{f: getattr(d, f) or 0 for f in NUMERIC_FIELDS},
        "efficiency": _daily_efficiency(d.repair_service_hrs, d.repair_rate_hrs, d.zero_rate_hrs),
    }


def _monthly_row(r):
    days_in_month = calendar.monthrange(r["month"].year, r["month"].month)[1]
    return {
        "rig": r["rig__rig_name"],
        "well": _well_label(r["drilling_hdr__location"], r["drilling_hdr__first_anchor_down_dt"]),
        "period": r["month"].strftime("%b-%Y"),
        **{f: r[f] or 0 for f in NUMERIC_FIELDS},
        "efficiency": _monthly_efficiency(r["repair_service_hrs"], r["repair_rate_hrs"], r["zero_rate_hrs"], days_in_month),
    }


def _filtered_queryset(request):
    """The flat (ungrouped) DrillingDtl queryset for the request's rig/date
    filters — one row per rig per day, same shape regardless of whether the
    caller wants a Daily or Monthly view. Returns None if the filters are
    incomplete (no rig picked, no financial year picked, etc.), same as
    "no results" rather than an error — the frontend already validates
    these before firing the request."""
    params = request.query_params
    rig_ids = [int(x) for x in params.get("rig_ids", "").split(",") if x.strip().isdigit()]
    if not rig_ids:
        return None

    qs = DrillingDtl.objects.filter(rig_id__in=rig_ids)

    if params.get("dates_entered", "dates") == "financial_yr":
        fy_ids = [int(x) for x in params.get("financial_years", "").split(",") if x.strip().isdigit()]
        fys = list(MstFinancialYear.objects.filter(financial_year_id__in=fy_ids))
        if not fys:
            return None
        date_q = Q()
        for fy in fys:
            date_q |= Q(drilling_dtl_dt__gte=fy.fin_year_from, drilling_dtl_dt__lte=fy.fin_year_to)
        qs = qs.filter(date_q)
    else:
        from_dt = params.get("from_dt")
        to_dt = params.get("to_dt")
        if not from_dt or not to_dt:
            return None
        qs = qs.filter(drilling_dtl_dt__gte=from_dt, drilling_dtl_dt__lte=to_dt)

    return qs


def _monthly_grouped(qs):
    return (
        qs.annotate(month=TruncMonth("drilling_dtl_dt"))
        .values("rig_id", "rig__rig_name", "drilling_hdr_id", "drilling_hdr__location", "drilling_hdr__first_anchor_down_dt", "month")
        .annotate(**{f: Sum(f) for f in NUMERIC_FIELDS})
        .order_by("-month", "rig__rig_name")
    )


def _numeric_totals(qs):
    """Column sums across every matching row — a single flat DB aggregate
    over the ungrouped queryset, correct for both Daily and Monthly (a sum
    of per-day values equals the sum of any grouping of those same values),
    and cheap regardless of how many rows match since the DB does the
    summing, not Python."""
    agg = qs.aggregate(**{f: Sum(f) for f in NUMERIC_FIELDS})
    return {f: agg[f] or 0 for f in NUMERIC_FIELDS}


def _avg_efficiency(record_status, qs):
    """Average of each row's own efficiency — not derivable from the flat
    sums above (efficiency is a ratio per row, not a summable quantity), so
    this does have to visit every matching row/group. It only pulls the 3
    downtime-hour columns rather than the full display row, and is used for
    the Totals figure alone — the actual page of rows returned to the
    client is bounded separately (see PerformanceDashboardView.get)."""
    if record_status == "monthly":
        values = _monthly_grouped(qs).values("month", "repair_service_hrs", "repair_rate_hrs", "zero_rate_hrs")
        effs = [
            _monthly_efficiency(
                v["repair_service_hrs"], v["repair_rate_hrs"], v["zero_rate_hrs"],
                calendar.monthrange(v["month"].year, v["month"].month)[1],
            )
            for v in values
        ]
    else:
        values = qs.values("repair_service_hrs", "repair_rate_hrs", "zero_rate_hrs")
        effs = [_daily_efficiency(v["repair_service_hrs"], v["repair_rate_hrs"], v["zero_rate_hrs"]) for v in values]
    if not effs:
        return None
    return round(sum(effs) / len(effs), 2)


def _paged_response(request):
    record_status = request.query_params.get("record_status", "daily")
    qs = _filtered_queryset(request)
    if qs is None:
        return {"rows": [], "totals": None, "count": 0, "page": 1, "page_size": DEFAULT_PAGE_SIZE, "has_more": False}

    try:
        page = max(int(request.query_params.get("page", 1)), 1)
    except ValueError:
        page = 1
    try:
        page_size = min(max(int(request.query_params.get("page_size", DEFAULT_PAGE_SIZE)), 1), MAX_PAGE_SIZE)
    except ValueError:
        page_size = DEFAULT_PAGE_SIZE
    offset = (page - 1) * page_size

    if record_status == "monthly":
        grouped = _monthly_grouped(qs)
        count = grouped.count()
        rows = [_monthly_row(r) for r in grouped[offset : offset + page_size]]
    else:
        daily_qs = qs.select_related("drilling_hdr", "rig").order_by("rig__rig_name", "drilling_hdr__location", "-drilling_dtl_dt")
        count = qs.count()
        rows = [_daily_row(d) for d in daily_qs[offset : offset + page_size]]

    totals = _numeric_totals(qs)
    totals["efficiency"] = _avg_efficiency(record_status, qs)

    return {
        "rows": rows,
        "totals": totals if count else None,
        "count": count,
        "page": page,
        "page_size": page_size,
        "has_more": offset + len(rows) < count,
    }


class PerformanceDashboardView(APIView):
    """Drilling Details → Performance Dashboard. Aggregates DrillingDtl rows
    per rig+well, either by day or by month, over either an explicit date
    range or a set of financial years — rebuilding the legacy
    Prc_Qry_Drilling_Operation_Dashboard stored procedure's two summary
    modes on top of the already-computed per-day hour buckets (see
    drilling_report.recompute_dtl_totals).

    Paginated (?page=&page_size=, default 200, capped at 500) — a wide
    Daily selection (many rigs across many financial years) can match tens
    of thousands of rows, and rendering that many as real table rows would
    hang the browser tab. Totals reflect the *entire* filtered result, not
    just the page returned, computed via DB-side aggregates rather than by
    materializing every row."""

    entity_key = "drilling.performance_dashboard"
    permission_classes = [HasMenuPermission]

    def get(self, request):
        return Response(_paged_response(request))


class PerformanceDashboardExportView(APIView):
    """Full (unpaginated) CSV of the same filtered result — this is a file
    download, not something rendered as DOM rows, so the row-count safety
    concern that caps the JSON endpoint doesn't apply here."""

    entity_key = "drilling.performance_dashboard"
    permission_classes = [HasMenuPermission]
    # HasMenuPermission reads view.action to look up the required flag in
    # _ACTION_PERM (view/add/edit/.../export) — a plain APIView has no
    # DRF-router-assigned .action, so it's set explicitly here to require
    # Export rather than falling back to the default "view".
    action = "export"

    def get(self, request):
        record_status = request.query_params.get("record_status", "daily")
        qs = _filtered_queryset(request)

        response = HttpResponse(content_type="text/csv")
        # The frontend's <a download> attribute wins over this in normal use,
        # but this still matters if the endpoint is ever hit directly (a new
        # tab, curl, an API client) — keep the two names in sync.
        response["Content-Disposition"] = f'attachment; filename="performance-dashboard-{date.today().isoformat()}.csv"'
        writer = csv.writer(response)
        writer.writerow(CSV_HEADER)

        if qs is None:
            return response

        if record_status == "monthly":
            rows = (_monthly_row(r) for r in _monthly_grouped(qs))
        else:
            daily_qs = qs.select_related("drilling_hdr", "rig").order_by("rig__rig_name", "drilling_hdr__location", "-drilling_dtl_dt")
            rows = (_daily_row(d) for d in daily_qs)

        row_count = 0
        for r in rows:
            row_count += 1
            writer.writerow(
                [
                    r["rig"], r["well"], r["period"],
                    r["received_diesel"], r["consumption_diesel"], r["received_water"], r["generated_water"], r["consumption_water"],
                    r["operating_hrs"], r["standby_hrs"], r["repair_service_hrs"], r["repair_rate_hrs"], r["zero_rate_hrs"],
                    r["drilling_meterage"], r["efficiency"],
                ]
            )

        if row_count:
            totals = _numeric_totals(qs)
            totals["efficiency"] = _avg_efficiency(record_status, qs)
            writer.writerow(
                [
                    "Total", "", "",
                    totals["received_diesel"], totals["consumption_diesel"], totals["received_water"], totals["generated_water"], totals["consumption_water"],
                    totals["operating_hrs"], totals["standby_hrs"], totals["repair_service_hrs"], totals["repair_rate_hrs"], totals["zero_rate_hrs"],
                    totals["drilling_meterage"], totals["efficiency"],
                ]
            )
        return response
