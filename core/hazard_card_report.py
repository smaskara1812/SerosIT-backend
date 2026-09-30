"""QHSE → Hazard ID Card → Print Report: a filter-driven PDF with four pie
charts plus a rig-grouped detail table, rendered with WeasyPrint (same
pipeline as incident_register_report.py).

No legacy code exists for this report at all — no .aspx/.cs and no
stored-procedure body (the requirements docx only names
[eos].[Prc_Qry_Hazard_ID_Card_Report]) — so this is a reconstruction from
that docx, a sample legacy PDF, and the user's own confirmation of the
fourth chart's scope, not a verified port. Four groupings, each over
whatever the current filter bar matches:
  1. Hazards recorded on various Rigs      — count by rig
  2. Types of Hazards Identified           — count by haz_type
  3. Party wise Hazards Reported           — count by reported_by_party
  4. Hazards reported by EOSIL departments — count by resp_dept, but only
     rows where reported_by_party == 'EOSIL' (confirmed with the user:
     the title names EOSIL specifically, and the sample PDF showed this
     chart with no data — consistent with few/no EOSIL-reported cards in
     that filtered set)

No charting library exists anywhere in this codebase — rather than adding
one (e.g. matplotlib) for four pie charts, each is a small hand-built
inline SVG (a handful of arc-path slices computed from percentages),
matching the WeasyPrint + Django-template + CSS-only pattern every other
PDF in this app already uses.

event_dt/close_out_dt are naive IST wall-clock values straight from the
DB (TIME_ZONE="Asia/Kolkata", USE_TZ=False) — no conversion needed here.
"""

import math
from collections import Counter

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

from .company_branding import seros_logo_path

PRINT_ROW_LIMIT = 2000

PIE_COLORS = ["#1a3f7a", "#2563eb", "#f59e0b", "#059669", "#dc2626", "#7c3aed", "#0891b2", "#db2777", "#65a30d"]


def _fmt_naive(dt):
    """event_dt/close_out_dt only — no timezone conversion, see module docstring."""
    return dt.strftime("%d/%m/%Y %H:%M") if dt else ""


def _emp_name(emp):
    return " ".join(p for p in [emp.emp_fname, emp.emp_mname, emp.emp_sname] if p)


def _pie_chart(title, counts, size=132):
    """counts: list of (label, count), already sorted by caller. Returns
    None-svg (rendered as "No Data Available", matching the sample PDF)
    when the filtered set has nothing in this grouping."""
    total = sum(c for _, c in counts)
    if not total:
        return {"title": title, "svg": None, "legend": []}

    cx = cy = r = size / 2
    cursor = -90.0
    paths = []
    legend = []
    for i, (label, count) in enumerate(counts):
        color = PIE_COLORS[i % len(PIE_COLORS)]
        angle = count / total * 360
        if len(counts) == 1:
            paths.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}" />')
        else:
            x1 = cx + r * math.cos(math.radians(cursor))
            y1 = cy + r * math.sin(math.radians(cursor))
            cursor += angle
            x2 = cx + r * math.cos(math.radians(cursor))
            y2 = cy + r * math.sin(math.radians(cursor))
            large_arc = 1 if angle > 180 else 0
            paths.append(
                f'<path d="M{cx},{cy} L{x1:.2f},{y1:.2f} '
                f'A{r},{r} 0 {large_arc} 1 {x2:.2f},{y2:.2f} Z" fill="{color}" />'
            )
        legend.append({"label": label, "count": count, "pct": round(count / total * 100, 1), "color": color})

    svg = (
        f'<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}" '
        f'xmlns="http://www.w3.org/2000/svg">{"".join(paths)}</svg>'
    )
    return {"title": title, "svg": svg, "legend": legend}


def render_hazard_card_report_pdf(queryset, filter_summary):
    from weasyprint import HTML

    total = queryset.count()
    rows = list(queryset[:PRINT_ROW_LIMIT])

    rig_counts = Counter(r.rig.rig_name if r.rig_id else "Unknown" for r in rows)
    type_counts = Counter(r.haz_type.haz_type_name if r.haz_type_id else "Unknown" for r in rows)
    party_counts = Counter(r.reported_by_party or "Unknown" for r in rows)
    eosil_dept_counts = Counter(
        r.resp_dept.vessel_dept_name if r.resp_dept_id else "Unknown"
        for r in rows
        if r.reported_by_party == "EOSIL"
    )

    charts = [
        _pie_chart("Hazards recorded on various Rigs", rig_counts.most_common()),
        _pie_chart("Types of Hazards Identified", type_counts.most_common()),
        _pie_chart("Party wise Hazards Reported", party_counts.most_common()),
        _pie_chart("Hazards reported by EOSIL departments", eosil_dept_counts.most_common()),
    ]

    # Grouped by rig, matching the sample report's own layout — Sr No
    # restarts at 1 within each rig's section.
    groups = {}
    order = []
    for r in rows:
        name = r.rig.rig_name if r.rig_id else "Unknown"
        if name not in groups:
            groups[name] = []
            order.append(name)
        groups[name].append(r)

    grouped_rows = [
        {
            "rig_name": name,
            "rows": [
                {
                    "sr_no": i + 1,
                    "haz_id_card_no": r.haz_id_card_no,
                    "operator_name": r.contract.operator.operator_name if r.contract_id else "",
                    "work_location_name": r.work_location.work_location if r.work_location_id else "",
                    "event_dt": _fmt_naive(r.event_dt),
                    "reported_by": r.reported_by_name
                    or (_emp_name(r.reported_by_fs_emp) if r.reported_by_fs_emp_id else ""),
                    "haz_type_name": r.haz_type.haz_type_name if r.haz_type_id else "",
                    "tfs": "Y" if r.timeout_for_safety == "Y" else "N",
                    "hazard_desc": r.hazard_desc,
                    "action_taken": r.action_taken or "",
                    "resp_dept_name": r.resp_dept.vessel_dept_name if r.resp_dept_id else "",
                    "resp_rank_name": r.resp_rank.rank_name if r.resp_rank_id else "",
                    "close_out_dt": _fmt_naive(r.close_out_dt),
                    "status_label": "Closed" if r.haz_id_card_status == "C" else "Open",
                }
                for i, r in enumerate(groups[name])
            ],
        }
        for name in order
    ]

    context = {
        "logo_path": seros_logo_path(),
        "charts": charts,
        "groups": grouped_rows,
        "filter_summary": filter_summary,
        "generated_at": timezone.now().strftime("%d/%m/%Y %H:%M"),
        "total": total,
        "shown": len(rows),
        "truncated": total > PRINT_ROW_LIMIT,
    }
    html = render_to_string("core/hazard_card_report.html", context)
    return HTML(string=html, base_url=str(settings.MEDIA_ROOT)).write_pdf()
