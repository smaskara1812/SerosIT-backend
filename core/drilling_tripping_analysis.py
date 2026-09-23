from datetime import date

from django.db.models import Avg
from django.db.models.functions import Abs
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import DrillingDtlOps, MstDrillingOperation, MstDrillingSection
from .permissions import HasMenuPermission
from .xlsx_export import build_xlsx_response

REPORT_TYPE_CODES = {"drilling": 2, "tripping": 6}  # Mst_Drilling_Operation.drilling_ops_code_no for "Drill actual" / "Trips"


def _location_label(location, anchor_dt):
    if not anchor_dt:
        return location or ""
    return f"{location}({anchor_dt:%d/%m/%Y})"


def _build_table(request):
    params = request.query_params
    rig_id = params.get("rig")
    from_dt = params.get("from_dt")
    to_dt = params.get("to_dt")
    report_type = params.get("report_type", "drilling")

    if not rig_id or not from_dt or not to_dt:
        return [], [], "Pick a rig and a From/To date."
    try:
        from_dt = date.fromisoformat(from_dt)
        to_dt = date.fromisoformat(to_dt)
    except ValueError:
        return [], [], "Invalid date."
    if from_dt > to_dt:
        return [], [], "From date must be before To date."

    code_no = REPORT_TYPE_CODES.get(report_type, REPORT_TYPE_CODES["drilling"])
    try:
        ops_id = MstDrillingOperation.objects.get(drilling_ops_code_no=code_no).drilling_ops_id
    except MstDrillingOperation.DoesNotExist:
        return [], [], None

    ops_qs = DrillingDtlOps.objects.filter(
        drilling_ops_id=ops_id,
        drilling_dtl__rig_id=rig_id,
        drilling_dtl__drilling_dtl_dt__gte=from_dt,
        drilling_dtl__drilling_dtl_dt__lte=to_dt,
    )

    hdrs = (
        ops_qs.filter(drilling_dtl__drilling_hdr__isnull=False)
        .values("drilling_dtl__drilling_hdr_id", "drilling_dtl__drilling_hdr__location", "drilling_dtl__drilling_hdr__first_anchor_down_dt")
        .distinct()
        .order_by("drilling_dtl__drilling_hdr__first_anchor_down_dt")
    )
    hdr_list = list(hdrs)
    columns = [
        _location_label(h["drilling_dtl__drilling_hdr__location"], h["drilling_dtl__drilling_hdr__first_anchor_down_dt"])
        for h in hdr_list
    ]
    hdr_ids = [h["drilling_dtl__drilling_hdr_id"] for h in hdr_list]

    # Average (not sum) of |ROP/Trip m/hr| per section per well — rop_trip_mh
    # is already server-computed per ops row (see DrillingDtlOps model /
    # drilling_report.recompute_dtl_totals), this just means the section's
    # rate for that well over however many logged entries went into it.
    avgs = (
        ops_qs.annotate(abs_rop=Abs("rop_trip_mh"))
        .values("drilling_section_id", "drilling_dtl__drilling_hdr_id")
        .annotate(avg_rop=Avg("abs_rop"))
    )
    by_section = {}
    for v in avgs:
        by_section.setdefault(v["drilling_section_id"], {})[v["drilling_dtl__drilling_hdr_id"]] = v["avg_rop"]

    rows = []
    for section in MstDrillingSection.objects.order_by("drilling_section_id"):
        section_data = by_section.get(section.drilling_section_id, {})
        rows.append({"label": section.drilling_section_name, "values": [section_data.get(hid) for hid in hdr_ids]})
    return columns, rows, None


class DrillingTrippingAnalysisView(APIView):
    """Drilling Details → Drilling & Tripping Analysis. For one rig, the
    average ROP (Drilling) or trip speed (Tripping) in m/hr per drilling
    section, per well it worked — rebuilding the
    Prc_Qry_Drilling_Dtl@Record_Status='Drilling_Tripping_Analysis' branch
    on top of DrillingDtlOps.rop_trip_mh, which is already computed per
    logged ops entry."""

    entity_key = "drilling.drilling_tripping_analysis"
    permission_classes = [HasMenuPermission]

    def get(self, request):
        columns, rows, error = _build_table(request)
        if error:
            return Response({"columns": [], "rows": [], "error": error}, status=400)
        return Response({"columns": columns, "rows": rows})


class DrillingTrippingAnalysisExportView(APIView):
    entity_key = "drilling.drilling_tripping_analysis"
    permission_classes = [HasMenuPermission]
    action = "export"

    def get(self, request):
        columns, rows, error = _build_table(request)
        filename = f"drilling-tripping-analysis-{date.today().isoformat()}.xlsx"
        if error:
            return build_xlsx_response(filename, "Drilling Tripping Analysis", [], ["Error"], [[error]])

        export_columns = ["Section", *columns]
        export_rows = [
            [r["label"], *[None if v is None else round(float(v), 2) for v in r["values"]]]
            for r in rows
        ]
        return build_xlsx_response(filename, "Drilling Tripping Analysis", [], export_columns, export_rows)
