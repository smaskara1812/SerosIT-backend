from datetime import date, timedelta

from django.db.models import Sum
from django.db.models.functions import TruncMonth
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DrillingDtl, DrillingDtlOps, MstDrillingOperation
from .permissions import HasMenuPermission
from .xlsx_export import build_xlsx_response

METERAGE_ROW_LABEL = "Drilling Meterage"


def _op_label(op):
    return f"{op.drilling_ops_code_no}. {op.drilling_ops_name}"


def _daily_columns(from_dt, to_dt):
    days = []
    d = from_dt
    while d <= to_dt:
        days.append(d)
        d += timedelta(days=1)
    return days


def _month_start(d):
    return date(d.year, d.month, 1)


def _monthly_columns(from_dt, to_dt):
    months = []
    m = _month_start(from_dt)
    end = _month_start(to_dt)
    while m <= end:
        months.append(m)
        if m.month == 12:
            m = date(m.year + 1, 1, 1)
        else:
            m = date(m.year, m.month + 1, 1)
    return months


def _location_label(location, anchor_dt):
    if not anchor_dt:
        return location or ""
    return f"{location}({anchor_dt:%d/%m/%Y})"


def _build_table(request):
    """Returns (columns, column_keys, rows, error) where `rows` is a list
    of {label, values} with `values` aligned 1:1 to `column_keys` — the
    operations catalog (~34 rows) and every day/month in the requested
    range are always all present, filled with None where there's no data,
    matching the legacy report's "every operation, every day always shows
    a row/column even when empty" behavior."""
    params = request.query_params
    rig_id = params.get("rig")
    from_dt = params.get("from_dt")
    to_dt = params.get("to_dt")
    report_type = params.get("report_type", "daily")

    if not rig_id or not from_dt or not to_dt:
        return [], [], [], "Pick a rig and a From/To date."
    try:
        from_dt = date.fromisoformat(from_dt)
        to_dt = date.fromisoformat(to_dt)
    except ValueError:
        return [], [], [], "Invalid date."
    if from_dt > to_dt:
        return [], [], [], "From date must be before To date."

    dtl_qs = DrillingDtl.objects.filter(rig_id=rig_id, drilling_dtl_dt__gte=from_dt, drilling_dtl_dt__lte=to_dt)
    ops_qs = DrillingDtlOps.objects.filter(
        drilling_dtl__rig_id=rig_id, drilling_dtl__drilling_dtl_dt__gte=from_dt, drilling_dtl__drilling_dtl_dt__lte=to_dt
    )
    operations = list(MstDrillingOperation.objects.order_by("drilling_ops_code_no"))

    if report_type == "monthly":
        columns = _monthly_columns(from_dt, to_dt)
        column_keys = [c.strftime("%b-%Y") for c in columns]

        meterage = {v["month"]: v["total"] for v in dtl_qs.annotate(month=TruncMonth("drilling_dtl_dt")).values("month").annotate(total=Sum("drilling_meterage"))}
        meterage_by_key = {c.strftime("%b-%Y"): meterage.get(_month_start(c)) for c in columns}

        op_sums = (
            ops_qs.annotate(month=TruncMonth("drilling_dtl__drilling_dtl_dt"))
            .values("drilling_ops_id", "month")
            .annotate(total=Sum("duration"))
        )
        by_op = {}
        for v in op_sums:
            by_op.setdefault(v["drilling_ops_id"], {})[v["month"]] = v["total"]

        rows = [{"label": METERAGE_ROW_LABEL, "values": [meterage_by_key[k] for k in column_keys]}]
        for op in operations:
            op_data = by_op.get(op.drilling_ops_id, {})
            rows.append({"label": _op_label(op), "values": [op_data.get(_month_start(c)) for c in columns]})
        return columns, column_keys, rows, None

    if report_type == "location":
        hdrs = (
            dtl_qs.filter(drilling_hdr__isnull=False)
            .values("drilling_hdr_id", "drilling_hdr__location", "drilling_hdr__first_anchor_down_dt")
            .distinct()
            .order_by("-drilling_hdr__first_anchor_down_dt")
        )
        hdr_list = list(hdrs)
        column_keys = [_location_label(h["drilling_hdr__location"], h["drilling_hdr__first_anchor_down_dt"]) for h in hdr_list]
        hdr_ids = [h["drilling_hdr_id"] for h in hdr_list]

        meterage = {v["drilling_hdr_id"]: v["total"] for v in dtl_qs.values("drilling_hdr_id").annotate(total=Sum("drilling_meterage"))}
        meterage_by_key = [meterage.get(hid) for hid in hdr_ids]

        op_sums = ops_qs.values("drilling_ops_id", "drilling_dtl__drilling_hdr_id").annotate(total=Sum("duration"))
        by_op = {}
        for v in op_sums:
            by_op.setdefault(v["drilling_ops_id"], {})[v["drilling_dtl__drilling_hdr_id"]] = v["total"]

        rows = [{"label": METERAGE_ROW_LABEL, "values": meterage_by_key}]
        for op in operations:
            op_data = by_op.get(op.drilling_ops_id, {})
            rows.append({"label": _op_label(op), "values": [op_data.get(hid) for hid in hdr_ids]})
        return column_keys, column_keys, rows, None

    # daily
    columns = _daily_columns(from_dt, to_dt)
    column_keys = [c.strftime("%d-%m-%Y") for c in columns]

    meterage = {v["drilling_dtl_dt"]: v["total"] for v in dtl_qs.values("drilling_dtl_dt").annotate(total=Sum("drilling_meterage"))}
    meterage_by_key = [meterage.get(c) for c in columns]

    op_sums = ops_qs.values("drilling_ops_id", "drilling_dtl__drilling_dtl_dt").annotate(total=Sum("duration"))
    by_op = {}
    for v in op_sums:
        by_op.setdefault(v["drilling_ops_id"], {})[v["drilling_dtl__drilling_dtl_dt"]] = v["total"]

    rows = [{"label": METERAGE_ROW_LABEL, "values": meterage_by_key}]
    for op in operations:
        op_data = by_op.get(op.drilling_ops_id, {})
        rows.append({"label": _op_label(op), "values": [op_data.get(c) for c in columns]})
    return column_keys, column_keys, rows, None


class OperationsAnalyticsView(APIView):
    """Drilling Details → Operations Analytics. A single rig's operation
    durations (and drilling meterage) pivoted across either every day,
    every month, or every well/location it worked in over a date range —
    rebuilding the legacy Prc_Qry_Drilling_Dtl stored procedure's dynamic
    PIVOT on top of DrillingDtlOps.duration, which recompute_dtl_totals
    already keeps in sync per operation per day."""

    entity_key = "drilling.operations_analytics"
    permission_classes = [HasMenuPermission]

    def get(self, request):
        column_keys, _, rows, error = _build_table(request)
        if error:
            return Response({"columns": [], "rows": [], "error": error}, status=400)
        return Response({"columns": column_keys, "rows": rows, "total_rows": len(rows)})


class OperationsAnalyticsExportView(APIView):
    entity_key = "drilling.operations_analytics"
    permission_classes = [HasMenuPermission]
    action = "export"

    def get(self, request):
        column_keys, _, rows, error = _build_table(request)
        filename = f"operations-analytics-{date.today().isoformat()}.xlsx"
        if error:
            return build_xlsx_response(filename, "Operations Analytics", [], ["Error"], [[error]])

        columns = ["Operations", *column_keys]
        export_rows = [[r["label"], *r["values"]] for r in rows]
        return build_xlsx_response(filename, "Operations Analytics", [], columns, export_rows)
