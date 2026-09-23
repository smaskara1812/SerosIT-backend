import re
from datetime import date

from django.db.models import Min
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DrillingDtlOps, MstRig
from .permissions import HasMenuPermission
from .xlsx_export import build_xlsx_response

DTL_AGGREGATE_FIELDS = [
    "consumption_diesel",
    "consumption_water",
    "received_diesel",
    "received_water",
    "generated_water",
    "operating_hrs",
    "standby_hrs",
    "repair_service_hrs",
    "repair_rate_hrs",
    "zero_rate_hrs",
    "rig_move_hrs",
]

EXPORT_COLUMNS = [
    "Date", "Consumption Diesel", "Consumption Water", "Received Diesel", "Received Water", "Generated Water",
    "Operating Hrs", "Standby Hrs", "Repair Service Hrs", "Repair Rate Hrs", "Zero Rate Hrs", "Rig Move Hrs",
    "Drilling Date", "Time From", "Time To", "Duration", "Location", "Code No. Operations", "Section",
    "Depth From", "Depth To", "ROP/Trip", "Rate", "Operations in sequence and remarks",
]

DEFAULT_PAGE_SIZE = 200
MAX_PAGE_SIZE = 500


def _op_label(op):
    # This report's own punctuation ("1: Rig up/...") — confirmed against
    # the legacy Excel sample, distinct from Operations Analytics' "1. "
    # format even though both come from the same Mst_Drilling_Operation.
    return f"{op.drilling_ops_code_no}: {op.drilling_ops_name}"


def _row_dict(o, is_first_of_day):
    dtl = o.drilling_dtl
    row = {
        "date": dtl.drilling_dtl_dt.strftime("%d/%m/%Y") if is_first_of_day else None,
        **{f: (getattr(dtl, f) if is_first_of_day else None) for f in DTL_AGGREGATE_FIELDS},
        "drilling_date": dtl.drilling_dtl_dt.strftime("%d/%m/%Y"),
        "time_from": o.time_from.strftime("%H:%M"),
        "time_to": o.time_to.strftime("%H:%M"),
        "duration": o.duration,
        "location": dtl.drilling_hdr.location if dtl.drilling_hdr_id else "",
        "operations": _op_label(o.drilling_ops),
        "section": o.drilling_section.drilling_section_name,
        "depth_from": o.depth_from,
        "depth_to": o.depth_to,
        "rop_trip": o.rop_trip_mh,
        "rate": o.prj_drilling_rate.drilling_rate.rate_code if o.prj_drilling_rate_id else "",
        "remarks": o.operation_desc,
    }
    return row


def _filtered_queryset(request):
    """Returns (qs, rig_id, from_dt, to_dt, error) — the parsed filter
    values are handed back too since the export view's report header needs
    them (rig name, the actual date range) without re-parsing the request
    a second time."""
    params = request.query_params
    rig_id = params.get("rig")
    from_dt = params.get("from_dt")
    to_dt = params.get("to_dt")
    if not rig_id or not from_dt or not to_dt:
        return None, None, None, None, "Pick a rig and a From/To date."
    try:
        from_dt = date.fromisoformat(from_dt)
        to_dt = date.fromisoformat(to_dt)
    except ValueError:
        return None, None, None, None, "Invalid date."
    if from_dt > to_dt:
        return None, None, None, None, "From date must be before To date."

    qs = DrillingDtlOps.objects.filter(
        drilling_dtl__rig_id=rig_id,
        drilling_dtl__drilling_dtl_dt__gte=from_dt,
        drilling_dtl__drilling_dtl_dt__lte=to_dt,
    ).select_related(
        "drilling_dtl", "drilling_dtl__drilling_hdr", "drilling_ops", "drilling_section",
        "prj_drilling_rate", "prj_drilling_rate__drilling_rate",
    )
    return qs, rig_id, from_dt, to_dt, None


def _rig_name(rig_id):
    return MstRig.objects.filter(pk=rig_id).values_list("rig_name", flat=True).first() or ""


def _filename_slug(text):
    # "Axom Rhino" -> "Axom-Rhino", "Well Services : SEPL" -> "Well-Services-SEPL"
    slug = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")
    return slug or "rig"


def _first_of_day_times(qs):
    """{drilling_dtl_id: earliest time_from} across the *entire* filtered
    result — computed once up front, not per page, so the "only the day's
    first logged entry shows the daily totals" rule (matching the legacy
    report's Top_Entry logic) holds correctly across a pagination
    boundary."""
    return {
        v["drilling_dtl_id"]: v["min_time"]
        for v in qs.values("drilling_dtl_id").annotate(min_time=Min("time_from"))
    }


class DrillingDailyDataView(APIView):
    """Drilling Details → Drilling Daily Data. One row per logged
    operations entry (ordered chronologically), with the day's diesel/
    water/hour totals shown only on that day's first entry — rebuilding
    Prc_Qry_Drilling_Daily_Data's master/detail print layout. Paginated
    like the other analytics pages here, since a wide date range can mean
    many hundreds of ops entries."""

    entity_key = "drilling.drilling_daily_data"
    permission_classes = [HasMenuPermission]

    def get(self, request):
        qs, _rig_id, _from_dt, _to_dt, error = _filtered_queryset(request)
        if error:
            return Response({"rows": [], "count": 0, "error": error}, status=400)

        try:
            page = max(int(request.query_params.get("page", 1)), 1)
        except ValueError:
            page = 1
        try:
            page_size = min(max(int(request.query_params.get("page_size", DEFAULT_PAGE_SIZE)), 1), MAX_PAGE_SIZE)
        except ValueError:
            page_size = DEFAULT_PAGE_SIZE
        offset = (page - 1) * page_size

        first_of_day = _first_of_day_times(qs)
        ordered = qs.order_by("time_from")
        rows = [
            _row_dict(o, o.time_from == first_of_day.get(o.drilling_dtl_id))
            for o in ordered[offset : offset + page_size]
        ]
        has_more = ordered[offset + page_size : offset + page_size + 1].exists()
        # A full COUNT costs the same whether the filtered range is a week or
        # a year, so it only runs once, on the first page — has_more (a
        # cheap "does one more row exist" check) drives every later page,
        # and the frontend keeps the page-1 count across subsequent merges.
        count = qs.count() if page == 1 else None
        return Response({"rows": rows, "count": count, "page": page, "page_size": page_size, "has_more": has_more})


class DrillingDailyDataExportView(APIView):
    entity_key = "drilling.drilling_daily_data"
    permission_classes = [HasMenuPermission]
    action = "export"

    def get(self, request):
        qs, rig_id, from_dt, to_dt, error = _filtered_queryset(request)
        rig_name = _rig_name(rig_id) if rig_id else ""

        filename_bits = ["drilling-daily-data"]
        if rig_name:
            filename_bits.append(_filename_slug(rig_name))
        filename_bits.append(date.today().isoformat())
        filename = "-".join(filename_bits) + ".xlsx"

        if error:
            return build_xlsx_response(filename, "Drilling Daily Data", [], ["Error"], [[error]])

        header_lines = [
            f"Drilling Daily Data : Rig ({rig_name})",
            f"SIS Report Date: {date.today():%d/%m/%Y}",
            f"Rig : {rig_name}   From : {from_dt:%d/%m/%Y}   To : {to_dt:%d/%m/%Y}",
        ]

        first_of_day = _first_of_day_times(qs)
        rows = []
        for o in qs.order_by("time_from"):
            r = _row_dict(o, o.time_from == first_of_day.get(o.drilling_dtl_id))
            rows.append(
                [
                    r["date"], *[r[f] for f in DTL_AGGREGATE_FIELDS],
                    r["drilling_date"], r["time_from"], r["time_to"], r["duration"], r["location"],
                    r["operations"], r["section"], r["depth_from"], r["depth_to"], r["rop_trip"], r["rate"], r["remarks"],
                ]
            )
        return build_xlsx_response(
            filename, "Drilling Daily Data", header_lines, EXPORT_COLUMNS, rows,
            wide_columns=[len(EXPORT_COLUMNS) - 1],
        )
