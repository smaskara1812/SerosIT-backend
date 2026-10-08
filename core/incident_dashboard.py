"""Incident Dashboard — ports the legacy dfrmIncident_Dashboard.aspx pivot
(11 "Select" items, each a rows-by-financial-year grid with a Total row and
column). See the investigation this was built from: every legacy pivot is
hand-rolled inline SQL with a SQL PIVOT operator, no stored procedures.

Deliberate departures from the legacy page (the user explicitly asked for a
redesign, not a byte-exact port):
  - Row universe is always "every master-table value" (a LEFT JOIN style
    listing, zero-count rows included) for every lookup-table-backed
    dimension, even where legacy only ever showed values that actually
    occurred (e.g. Positions Injured, Incident Cause). This is simpler to
    reason about and more informative for a management pivot ("this
    category has zero" is itself useful to see), and it costs nothing since
    every one of these master tables is small.
  - The legacy Category dropdown for Rig/Unit Incidents lets the sub-filter
    ("All"/Well Service/Repair Yard/Onshore Rig/Offshore Rig/Office) select
    ANY rig type, unlike the analytics dashboards elsewhere in this app
    (dashboard_access.py) which restrict to Offshore/Onshore only — this
    page intentionally does NOT reuse dashboard_access's rig-type
    restriction, since the legacy page itself offers the full rig-type
    list here.
  - Drill-down passes structured, ID-based query params and resolves them
    server-side, rather than the legacy's own mechanism (an encrypted raw
    SQL WHERE-clause fragment built from formatted display text) — same
    result, without carrying that injection-shaped design forward.

"ICR Actions" is relabeled "Other QHSE Actions" throughout — the legacy
label is misleading (the table it reads, eos_Other_QHSE_Actions, has
nothing to do with Incident Root Cause; see OtherQhseAction's own
docstring in models.py).
"""

from collections import defaultdict

from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from . import audit as _audit
from .models import (
    Incident,
    IncidentAction,
    IncidentRootCause,
    MstContactExposureType,
    MstFinancialYear,
    MstIncidentCause,
    MstIncidentType,
    MstPartsOfBody,
    MstRank,
    MstRig,
    MstRigOperation,
    MstRigType,
    MstWorkLocation,
    OtherQhseAction,
)
from .permissions import HasMenuPermission
from .xlsx_export import build_xlsx_response

ENTITY_KEY = "dashboards.incident_dashboard"


def _audit_export(request, label, row_count):
    """Same convention as Incident Register's own export logging
    (reports_views._audit_export) — records the query params that produced
    the file plus the row count, no "before" state since an export has
    nothing to diff against."""
    changes = {k: {"old": None, "new": v} for k, v in request.query_params.items() if v not in (None, "")}
    changes["rows_exported"] = {"old": None, "new": row_count}
    _audit.record_action(request, "export", ENTITY_KEY, record_label=label, changes=changes)

NEAR_MISS_TYPE_ID = 5  # MstIncidentType — "Near Miss Incident"
CONTACT_NOT_APPLICABLE_ID = 20  # MstContactExposureType — "Not Applicable", excluded from the pivot
ACTION_STATUS_LABELS = {"OP": "Open", "CL": "Closed"}

DIMENSION_LABELS = {
    "rig_unit": "Rig/Unit Incidents",
    "incident_type": "Incident Type",
    "incident_cause": "Incident Cause",
    "near_miss": "Near Miss Incidents",
    "rig_operation": "Rig Operation",
    "work_location": "Work Location",
    "positions_injured": "Positions Injured",
    "contact_exposure": "Types of Contact/Exposure",
    "part_of_body": "Part of Body Injured",
    "incident_actions": "Incident Actions",
    "other_qhse_actions": "Other QHSE Actions",
}


def _parse_ids(raw):
    if not raw:
        return []
    return [int(x) for x in raw.split(",") if x.strip().isdigit()]


def _parse_strs(raw):
    if not raw:
        return []
    return [x for x in raw.split(",") if x.strip()]


def _financial_years():
    return list(
        MstFinancialYear.objects.order_by("-fin_year_from").values(
            "financial_year_id", "fin_year_text", "fin_year_from", "fin_year_to"
        )
    )


def _apply_population_filter(qs, mode, rig_ids, unit_names):
    """The Rig/Unit toggle + picker — restricts which incidents feed EVERY
    dimension's pivot (not just Rig/Unit Incidents' own rows), matching the
    legacy page's shared filter panel."""
    if mode == "units":
        qs = qs.filter(rig__isnull=True).exclude(unit_name__isnull=True).exclude(unit_name="")
        if unit_names:
            qs = qs.filter(unit_name__in=unit_names)
        return qs
    qs = qs.filter(rig__isnull=False)
    if rig_ids:
        qs = qs.filter(rig_id__in=rig_ids)
    return qs


def _pivot_from_counts(row_universe, counts_by_row_and_year, year_ids):
    """row_universe: list of (row_key, row_label). counts_by_row_and_year:
    {(row_key, financial_year_id): count}. Builds the {rows, column_totals,
    grand_total} shape every dimension returns, filling in zeros."""
    rows = []
    column_totals = defaultdict(int)
    grand_total = 0
    for row_key, row_label in row_universe:
        counts = {}
        row_total = 0
        for fy in year_ids:
            n = counts_by_row_and_year.get((row_key, fy), 0)
            counts[str(fy)] = n
            row_total += n
            column_totals[str(fy)] += n
        rows.append({"key": row_key, "label": row_label, "counts": counts, "total": row_total})
        grand_total += row_total
    return rows, dict(column_totals), grand_total


def _build_simple_dimension(qs, year_ids, group_field, row_universe):
    """Shared path for every dimension that's a single FK straight off
    Incident (incident_type, rig_operation, work_location, contact_exposure,
    rig_id in Rigs mode)."""
    grouped = qs.values(group_field, "financial_year_id").annotate(n=Count("incident_id"))
    counts = {(row[group_field], row["financial_year_id"]): row["n"] for row in grouped}
    return _pivot_from_counts(row_universe, counts, year_ids)


def _build_rig_unit(qs, year_ids, mode, sub):
    if mode == "units":
        grouped = qs.values("unit_name", "financial_year_id").annotate(n=Count("incident_id"))
        counts = {(row["unit_name"], row["financial_year_id"]): row["n"] for row in grouped}
        universe = sorted({row["unit_name"] for row in grouped})
        return _pivot_from_counts([(u, u) for u in universe], counts, year_ids)

    rig_qs = MstRig.objects.all()
    if sub and sub != "all" and sub.isdigit():
        rig_qs = rig_qs.filter(rig_type_id=sub)
    universe = [(r["rig_id"], r["rig_name"]) for r in rig_qs.order_by("rig_name").values("rig_id", "rig_name")]
    if sub and sub != "all" and sub.isdigit():
        qs = qs.filter(rig__rig_type_id=sub)
    return _build_simple_dimension(qs, year_ids, "rig_id", universe)


def _build_incident_type(qs, year_ids):
    universe = [
        (t["incident_type_id"], t["incident_type"])
        for t in MstIncidentType.objects.order_by("incident_type").values("incident_type_id", "incident_type")
    ]
    return _build_simple_dimension(qs, year_ids, "incident_type_id", universe)


def _build_incident_cause(qs, year_ids, sub):
    qs = qs.exclude(incident_type_id=NEAR_MISS_TYPE_ID)
    if sub == "root":
        universe = [
            (c["incident_cause_id"], c["incident_cause_desc"])
            for c in MstIncidentCause.objects.filter(incident_cause_category__in=["R", "B"])
            .order_by("incident_cause_desc")
            .values("incident_cause_id", "incident_cause_desc")
        ]
        grouped = (
            IncidentRootCause.objects.filter(incident__in=qs)
            .exclude(marked_as_deleted="Y")
            .values("root_cause_id", "incident__financial_year_id")
            .annotate(n=Count("incident_root_cause_id"))
        )
        counts = {(row["root_cause_id"], row["incident__financial_year_id"]): row["n"] for row in grouped}
        return _pivot_from_counts(universe, counts, year_ids)

    universe = [
        (c["incident_cause_id"], c["incident_cause_desc"])
        for c in MstIncidentCause.objects.filter(incident_cause_category__in=["I", "B"])
        .order_by("incident_cause_desc")
        .values("incident_cause_id", "incident_cause_desc")
    ]
    return _build_simple_dimension(qs, year_ids, "immediate_incident_cause_id", universe)


def _build_near_miss(qs, year_ids):
    qs = qs.filter(incident_type_id=NEAR_MISS_TYPE_ID)
    universe = [(r["rig_id"], r["rig_name"]) for r in MstRig.objects.order_by("rig_name").values("rig_id", "rig_name")]
    return _build_simple_dimension(qs, year_ids, "rig_id", universe)


def _build_rig_operation(qs, year_ids):
    universe = [
        (r["rig_operation_id"], r["rig_operation_name"])
        for r in MstRigOperation.objects.order_by("rig_operation_name").values(
            "rig_operation_id", "rig_operation_name"
        )
    ]
    return _build_simple_dimension(qs, year_ids, "rig_operation_id", universe)


def _build_work_location(qs, year_ids):
    universe = [
        (w["work_location_id"], w["work_location"])
        for w in MstWorkLocation.objects.order_by("work_location").values("work_location_id", "work_location")
    ]
    return _build_simple_dimension(qs, year_ids, "work_location_id", universe)


def _build_positions_injured(qs, year_ids):
    qs = qs.filter(person_injured="Y")
    universe = [(r["rank_id"], r["rank_name"]) for r in MstRank.objects.order_by("rank_name").values("rank_id", "rank_name")]
    return _build_simple_dimension(qs, year_ids, "rank_id", universe)


def _build_contact_exposure(qs, year_ids):
    universe = [
        (c["contact_expo_type_id"], c["contact_expo_type_name"])
        for c in MstContactExposureType.objects.exclude(pk=CONTACT_NOT_APPLICABLE_ID)
        .order_by("contact_expo_type_name")
        .values("contact_expo_type_id", "contact_expo_type_name")
    ]
    return _build_simple_dimension(qs, year_ids, "contact_expo_type_id", universe)


def _build_part_of_body(qs, year_ids):
    universe = [
        (p["part_of_body_id"], p["part_of_body_name"])
        for p in MstPartsOfBody.objects.order_by("part_of_body_name").values("part_of_body_id", "part_of_body_name")
    ]
    counts = defaultdict(int)
    # Summing each slot's own Count() independently double-counted an
    # incident that has the same part in two slots (e.g. Hand in both
    # part_of_body_1 and part_of_body_3) — confirmed against real data: 32
    # incidents have a repeated part across their 4 slots, inflating that
    # part's pivot cell above what the drill-down actually lists (Hand was
    # off by 16). Dedupe per incident instead: each incident contributes
    # at most one count per distinct part_id, however many slots it's in.
    rows = qs.values(
        "financial_year_id", "part_of_body_1_id", "part_of_body_2_id", "part_of_body_3_id", "part_of_body_4_id"
    )
    for row in rows:
        parts = {row[f"part_of_body_{i}_id"] for i in (1, 2, 3, 4)} - {None}
        for part_id in parts:
            counts[(part_id, row["financial_year_id"])] += 1
    return _pivot_from_counts(universe, counts, year_ids)


def _build_incident_actions(qs, year_ids):
    universe = [(code, label) for code, label in ACTION_STATUS_LABELS.items()]
    grouped = (
        IncidentAction.objects.filter(incident__in=qs)
        .exclude(marked_as_deleted="Y")
        .values("action_status", "incident__financial_year_id")
        .annotate(n=Count("incident_action_id"))
    )
    counts = {(row["action_status"], row["incident__financial_year_id"]): row["n"] for row in grouped}
    return _pivot_from_counts(universe, counts, year_ids)


def _financial_year_id_for_date(d, years):
    for y in years:
        if y["fin_year_from"] <= d <= y["fin_year_to"]:
            return y["financial_year_id"]
    return None


def _build_other_qhse_actions(rig_ids, year_ids, all_years):
    qs = OtherQhseAction.objects.all()
    if rig_ids:
        qs = qs.filter(rig_id__in=rig_ids)
    universe = [(code, label) for code, label in ACTION_STATUS_LABELS.items()]
    counts = defaultdict(int)
    for row in qs.values("action_status", "other_qhse_action_dt"):
        fy = _financial_year_id_for_date(row["other_qhse_action_dt"], all_years)
        if fy is not None:
            counts[(row["action_status"], fy)] += 1
    return _pivot_from_counts(universe, counts, year_ids)


def _resolve_pivot(request):
    """Shared by the JSON pivot endpoint and the Export Excel endpoint —
    resolves the request's params into the full pivot shape plus a
    filter_summary (mirrors _resolve_drilldown's own summary lines), so the
    export's header states exactly which dimension/population/years it
    covers rather than a bare numbers grid."""
    params = request.query_params
    dimension = params.get("dimension", "rig_unit")
    mode = params.get("mode", "rigs")
    sub = params.get("sub", "")
    rig_ids = _parse_ids(params.get("rig_ids"))
    unit_names = _parse_strs(params.get("unit_names"))

    all_years = _financial_years()
    year_ids = _parse_ids(params.get("years")) or [y["financial_year_id"] for y in all_years]
    dimension_label = DIMENSION_LABELS.get(dimension, dimension)

    rig_names = {r["rig_id"]: r["rig_name"] for r in MstRig.objects.values("rig_id", "rig_name")}
    meta_lookup = {("rig", rid): name for rid, name in rig_names.items()}
    population_line = f"Population: {_mode_description(dimension, mode, rig_ids, unit_names, meta_lookup)}"

    if dimension == "other_qhse_actions":
        rows, column_totals, grand_total = _build_other_qhse_actions(rig_ids, year_ids, all_years)
    else:
        qs = Incident.objects.exclude(marked_as_deleted="Y").filter(financial_year_id__in=year_ids)
        qs = _apply_population_filter(qs, mode, rig_ids, unit_names)

        if dimension == "rig_unit":
            rows, column_totals, grand_total = _build_rig_unit(qs, year_ids, mode, sub)
        elif dimension == "incident_type":
            rows, column_totals, grand_total = _build_incident_type(qs, year_ids)
        elif dimension == "incident_cause":
            rows, column_totals, grand_total = _build_incident_cause(qs, year_ids, sub or "immediate")
        elif dimension == "near_miss":
            rows, column_totals, grand_total = _build_near_miss(qs, year_ids)
        elif dimension == "rig_operation":
            rows, column_totals, grand_total = _build_rig_operation(qs, year_ids)
        elif dimension == "work_location":
            rows, column_totals, grand_total = _build_work_location(qs, year_ids)
        elif dimension == "positions_injured":
            rows, column_totals, grand_total = _build_positions_injured(qs, year_ids)
        elif dimension == "contact_exposure":
            rows, column_totals, grand_total = _build_contact_exposure(qs, year_ids)
        elif dimension == "part_of_body":
            rows, column_totals, grand_total = _build_part_of_body(qs, year_ids)
        elif dimension == "incident_actions":
            rows, column_totals, grand_total = _build_incident_actions(qs, year_ids)
        else:
            return None

    year_labels = {y["financial_year_id"]: y["fin_year_text"] for y in all_years}
    years = [{"id": fy, "label": year_labels.get(fy, str(fy))} for fy in year_ids]

    summary_lines = [f"Dimension: {dimension_label}"]
    if dimension == "incident_cause":
        summary_lines.append(f"Cause Type: {'Root Cause' if sub == 'root' else 'Immediate Cause'}")
    elif dimension == "rig_unit" and sub and sub != "all" and sub.isdigit():
        rig_type_name = MstRigType.objects.filter(pk=sub).values_list("rig_type_name", flat=True).first()
        if rig_type_name:
            summary_lines.append(f"Rig Type: {rig_type_name}")
    summary_lines.append(population_line)
    summary_lines.append(
        f"Financial Years: {', '.join(y['label'] for y in years)}" if len(years) <= 6 else f"Financial Years: {len(years)} selected"
    )

    return {
        "dimension": dimension,
        "dimension_label": dimension_label,
        "years": years,
        "all_years": [{"id": y["financial_year_id"], "label": y["fin_year_text"]} for y in all_years],
        "rows": rows,
        "column_totals": column_totals,
        "grand_total": grand_total,
        "filter_summary": summary_lines,
    }


class IncidentDashboardView(APIView):
    permission_classes = [HasMenuPermission]
    entity_key = "dashboards.incident_dashboard"

    def get(self, request):
        result = _resolve_pivot(request)
        if result is None:
            return Response({"error": f"Unknown dimension '{request.query_params.get('dimension')}'"}, status=400)
        return Response(result)


class IncidentDashboardExportView(APIView):
    """Export Excel for the pivot table exactly as shown on screen — same
    rows/years/totals, same descending-by-total order, optionally excluding
    zero-total rows via ?hide_empty=1 (matching the page's own "Hide rows
    with no incidents" checkbox) — with the active filters stated in the
    sheet header, same reasoning as Incident Register's own export."""

    permission_classes = [HasMenuPermission]
    entity_key = "dashboards.incident_dashboard"
    # HasMenuPermission reads view.action to look up the required flag in
    # _ACTION_PERM (view/add/edit/.../export) — a plain APIView has no
    # DRF-router-assigned .action, so it's set explicitly here to require
    # the Export permission rather than falling back to the default "view".
    action = "export"

    def get(self, request):
        result = _resolve_pivot(request)
        if result is None:
            return Response({"error": f"Unknown dimension '{request.query_params.get('dimension')}'"}, status=400)

        rows = result["rows"]
        if request.query_params.get("hide_empty") == "1":
            rows = [r for r in rows if r["total"] > 0]
        rows = sorted(rows, key=lambda r: -r["total"])

        years = result["years"]
        columns = [result["dimension_label"], *[y["label"] for y in years], "Total"]
        data_rows = [[r["label"], *[r["counts"].get(str(y["id"]), 0) for y in years], r["total"]] for r in rows]
        data_rows.append(
            ["Total", *[result["column_totals"].get(str(y["id"]), 0) for y in years], result["grand_total"]]
        )

        _audit_export(request, f"{result['dimension_label']} pivot export", len(data_rows))

        filename = f"incident-dashboard-{result['dimension']}-{timezone.now().date().isoformat()}.xlsx"
        return build_xlsx_response(
            filename,
            result["dimension_label"].replace("/", "-"),  # Excel forbids "/" in a sheet name
            [result["dimension_label"], *result["filter_summary"]],
            columns,
            data_rows,
            bold_last_row=True,
        )

class IncidentDashboardMetaView(APIView):
    permission_classes = [HasMenuPermission]
    entity_key = "dashboards.incident_dashboard"

    def get(self, request):
        all_years = _financial_years()
        rig_types = list(
            MstRigType.objects.order_by("rig_type_name").values("rig_type_id", "rig_type_name")
        )
        rigs = list(MstRig.objects.order_by("rig_name").values("rig_id", "rig_name", "rig_type_id"))
        units = sorted(
            Incident.objects.exclude(marked_as_deleted="Y")
            .filter(rig__isnull=True)
            .exclude(unit_name__isnull=True)
            .exclude(unit_name="")
            .values_list("unit_name", flat=True)
            .distinct()
        )
        return Response(
            {
                "dimensions": [{"key": k, "label": v} for k, v in DIMENSION_LABELS.items()],
                "years": [{"id": y["financial_year_id"], "label": y["fin_year_text"]} for y in all_years],
                "rig_types": [{"id": r["rig_type_id"], "name": r["rig_type_name"]} for r in rig_types],
                "rigs": [{"id": r["rig_id"], "name": r["rig_name"], "rig_type_id": r["rig_type_id"]} for r in rigs],
                "units": units,
            }
        )


def _incident_row_dict(i):
    return {
        "incident_id": i.incident_id,
        "rig_name": i.rig.rig_name if i.rig_id else (i.unit_name or "Unknown"),
        "rig_incident_no": i.rig_incident_no or "",
        "incident_date": i.incident_date,
        "incident_type_abrv": i.incident_type.incident_abrv if i.incident_type_id else "",
        "incident_descr": i.incident_descr,
    }


def _mode_description(dimension, mode, rig_ids, unit_names, meta_lookup):
    """Human-readable population description for the print header — e.g.
    "Rigs: Axom Rhino, SR01" or "All rigs" — so the printed page states
    exactly which slice of the population it covers, not just the pivot
    cell's row/year."""
    if dimension == "other_qhse_actions":
        if rig_ids:
            names = [meta_lookup.get(("rig", r), str(r)) for r in rig_ids]
            return f"Rigs: {', '.join(names)}"
        return "All rigs"
    if mode == "units":
        if unit_names:
            return f"Units: {', '.join(unit_names)}"
        return "All units"
    if rig_ids:
        names = [meta_lookup.get(("rig", r), str(r)) for r in rig_ids]
        return f"Rigs: {', '.join(names)}"
    return "All rigs"


def _resolve_drilldown(request):
    """Shared by the JSON endpoint and the Print PDF endpoint — resolves
    the request's params into (kind, rows, filter_summary_lines). Takes the
    same filters as the main pivot (mode/rig_ids/unit_names/sub) plus `row`
    (the clicked row's key) and `year` (financial_year_id) — structured,
    ID-based params resolved server-side, rather than the legacy page's own
    mechanism of encrypting a raw SQL WHERE fragment built from formatted
    display text (see module docstring)."""
    params = request.query_params
    dimension = params.get("dimension", "rig_unit")
    mode = params.get("mode", "rigs")
    sub = params.get("sub", "")
    row = params.get("row", "")
    year_raw = params.get("year")
    rig_ids = _parse_ids(params.get("rig_ids"))
    unit_names = _parse_strs(params.get("unit_names"))

    if not year_raw or not year_raw.isdigit():
        return None, None, ["year is required"]
    year = int(year_raw)

    all_years = _financial_years()
    year_meta = next((y for y in all_years if y["financial_year_id"] == year), None)
    year_label = year_meta["fin_year_text"] if year_meta else str(year)

    rig_names = {r["rig_id"]: r["rig_name"] for r in MstRig.objects.values("rig_id", "rig_name")}
    meta_lookup = {("rig", rid): name for rid, name in rig_names.items()}
    dimension_label = DIMENSION_LABELS.get(dimension, dimension)
    population_line = f"Population: {_mode_description(dimension, mode, rig_ids, unit_names, meta_lookup)}"

    if dimension == "other_qhse_actions":
        qs = OtherQhseAction.objects.filter(action_status=row)
        if rig_ids:
            qs = qs.filter(rig_id__in=rig_ids)
        if year_meta:
            qs = qs.filter(
                other_qhse_action_dt__gte=year_meta["fin_year_from"], other_qhse_action_dt__lte=year_meta["fin_year_to"]
            )
        summary_lines = [
            f"Dimension: {dimension_label}",
            f"{dimension_label}: {ACTION_STATUS_LABELS.get(row, row)}",
            population_line,
            f"Financial Year: {year_label}",
        ]
        rows = [
            {
                "icr_no": a.icr_no,
                "rig_name": a.rig.rig_name,
                "qhse_category": a.qhse_category.qhse_category_name,
                "action_recommended": a.action_recommended,
                "action_taken": a.action_taken,
                "action_party": a.action_party,
                "target_date": a.target_date,
                "completion_dt": a.completion_dt,
                "status": ACTION_STATUS_LABELS.get(a.action_status, a.action_status),
            }
            for a in qs.select_related("rig", "qhse_category").order_by("-other_qhse_action_dt")
        ]
        return "other_qhse_actions", rows, summary_lines

    qs = Incident.objects.exclude(marked_as_deleted="Y").filter(financial_year_id=year)
    qs = _apply_population_filter(qs, mode, rig_ids, unit_names)

    row_label = row
    if dimension == "rig_unit":
        row_label = row if mode == "units" else rig_names.get(int(row), row) if row.isdigit() else row
        qs = qs.filter(unit_name=row) if mode == "units" else qs.filter(rig_id=row)
    elif dimension == "incident_type":
        row_label = MstIncidentType.objects.filter(pk=row).values_list("incident_type", flat=True).first() or row
        qs = qs.filter(incident_type_id=row)
    elif dimension == "incident_cause":
        row_label = MstIncidentCause.objects.filter(pk=row).values_list("incident_cause_desc", flat=True).first() or row
        cause_type_line = f"Cause Type: {'Root Cause' if sub == 'root' else 'Immediate Cause'}"
        if sub == "root":
            incident_ids = IncidentRootCause.objects.filter(
                incident__in=qs, root_cause_id=row
            ).exclude(marked_as_deleted="Y").values_list("incident_id", flat=True)
            qs = qs.filter(incident_id__in=incident_ids)
        else:
            qs = qs.exclude(incident_type_id=NEAR_MISS_TYPE_ID).filter(immediate_incident_cause_id=row)
    elif dimension == "near_miss":
        row_label = rig_names.get(int(row), row) if row.isdigit() else row
        qs = qs.filter(incident_type_id=NEAR_MISS_TYPE_ID, rig_id=row)
    elif dimension == "rig_operation":
        row_label = MstRigOperation.objects.filter(pk=row).values_list("rig_operation_name", flat=True).first() or row
        qs = qs.filter(rig_operation_id=row)
    elif dimension == "work_location":
        row_label = MstWorkLocation.objects.filter(pk=row).values_list("work_location", flat=True).first() or row
        qs = qs.filter(work_location_id=row)
    elif dimension == "positions_injured":
        row_label = MstRank.objects.filter(pk=row).values_list("rank_name", flat=True).first() or row
        qs = qs.filter(person_injured="Y", rank_id=row)
    elif dimension == "contact_exposure":
        row_label = (
            MstContactExposureType.objects.filter(pk=row).values_list("contact_expo_type_name", flat=True).first() or row
        )
        qs = qs.filter(contact_expo_type_id=row)
    elif dimension == "part_of_body":
        row_label = MstPartsOfBody.objects.filter(pk=row).values_list("part_of_body_name", flat=True).first() or row
        qs = qs.filter(
            Q(part_of_body_1_id=row) | Q(part_of_body_2_id=row) | Q(part_of_body_3_id=row) | Q(part_of_body_4_id=row)
        )
    elif dimension == "incident_actions":
        row_label = ACTION_STATUS_LABELS.get(row, row)
        actions = (
            IncidentAction.objects.filter(incident__in=qs, action_status=row)
            .exclude(marked_as_deleted="Y")
            .select_related("incident", "incident__rig")
            .order_by("-incident__incident_date")
        )
        rows = [
            {
                "rig_incident_no": a.incident.rig_incident_no or "",
                "rig_name": a.incident.rig.rig_name if a.incident.rig_id else (a.incident.unit_name or "Unknown"),
                "incident_date": a.incident.incident_date,
                "action_recommended": a.action_recommended,
                "action_taken": a.action_taken,
                "action_party": a.action_party,
                "target_date": a.target_date,
                "completion_dt": a.completion_dt,
                "status": ACTION_STATUS_LABELS.get(a.action_status, a.action_status),
            }
            for a in actions
        ]
        summary_lines = [
            f"Dimension: {dimension_label}",
            f"{dimension_label}: {row_label}",
            population_line,
            f"Financial Year: {year_label}",
        ]
        return "incident_actions", rows, summary_lines
    else:
        return None, None, [f"Unknown dimension '{dimension}'"]

    summary_lines = [f"Dimension: {dimension_label}", f"{dimension_label}: {row_label}"]
    if dimension == "incident_cause":
        summary_lines.append(cause_type_line)
    summary_lines += [population_line, f"Financial Year: {year_label}"]
    rows = [_incident_row_dict(i) for i in qs.select_related("rig", "incident_type").order_by("-incident_date")]
    return "incidents", rows, summary_lines


class IncidentDashboardDrilldownView(APIView):
    """The underlying records behind one clicked pivot cell (one dimension
    value x one financial year). See _resolve_drilldown for the actual
    filter logic, shared with the Print PDF endpoint below."""

    permission_classes = [HasMenuPermission]
    entity_key = "dashboards.incident_dashboard"

    def get(self, request):
        kind, rows, summary_lines = _resolve_drilldown(request)
        if kind is None:
            return Response({"error": "; ".join(summary_lines)}, status=400)
        return Response({"kind": kind, "rows": rows, "filter_summary": summary_lines})


DRILLDOWN_PDF_COLUMNS = {
    "incidents": [
        ("rig_name", "Rig/Unit"),
        ("rig_incident_no", "Incident No."),
        ("incident_date", "Date"),
        ("incident_type_abrv", "Type"),
        ("incident_descr", "Description"),
    ],
    "incident_actions": [
        ("rig_incident_no", "Incident No."),
        ("rig_name", "Rig/Unit"),
        ("incident_date", "Date"),
        ("action_recommended", "Action Recommended"),
        ("action_taken", "Action Taken"),
        ("action_party", "Action Party"),
        ("target_date", "Target Date"),
        ("completion_dt", "Completion Date"),
        ("status", "Status"),
    ],
    "other_qhse_actions": [
        ("icr_no", "ICR No."),
        ("rig_name", "Rig"),
        ("qhse_category", "Category"),
        ("action_recommended", "Action Recommended"),
        ("action_taken", "Action Taken"),
        ("action_party", "Action Party"),
        ("target_date", "Target Date"),
        ("completion_dt", "Completion Date"),
        ("status", "Status"),
    ],
}


class IncidentDashboardDrilldownPrintView(APIView):
    """PDF version of one drill-down's record list — drawn with ReportLab, like
    pipeline as the Incident Register's own Print (incident_register_report.py)
    — with the exact filter combination (dimension, row, year, population)
    stated in the header so the printed page is self-describing rather than
    a bare table someone has to guess the context of later."""

    permission_classes = [HasMenuPermission]
    entity_key = "dashboards.incident_dashboard"
    # Same reasoning as IncidentDashboardExportView.action above — a printed
    # PDF is a export of the underlying records, not a "view", so it's
    # gated (and audited) as one.
    action = "export"

    def get(self, request):
        from .incident_dashboard_report import render_drilldown_pdf

        kind, rows, summary_lines = _resolve_drilldown(request)
        if kind is None:
            return Response({"error": "; ".join(summary_lines)}, status=400)

        columns = DRILLDOWN_PDF_COLUMNS[kind]
        pdf_bytes = render_drilldown_pdf(
            title=DIMENSION_LABELS.get(request.query_params.get("dimension", ""), "Incident Dashboard"),
            summary_lines=summary_lines,
            columns=[label for _, label in columns],
            rows=[[r.get(key) for key, _ in columns] for r in rows],
        )

        _audit_export(request, f"{DIMENSION_LABELS.get(request.query_params.get('dimension', ''), 'Incident Dashboard')} drilldown PDF", len(rows))

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = 'inline; filename="Incident Dashboard Drilldown.pdf"'
        return response
