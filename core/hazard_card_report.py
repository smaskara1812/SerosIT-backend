"""QHSE → Hazard ID Card → Print Report: a filter-driven PDF with four pie
charts plus a rig-grouped detail table, drawn with ReportLab (same table
builder as incident_register_report.py).

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

No charting library is needed: each pie is a handful of ReportLab wedges
computed from the counts (see _pie_drawing).

event_dt/close_out_dt are naive IST wall-clock values straight from the
DB (TIME_ZONE="Asia/Kolkata", USE_TZ=False) — no conversion needed here.
"""

from collections import Counter

from django.utils import timezone
from reportlab.graphics.shapes import Circle, Drawing, Wedge
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import CondPageBreak, KeepTogether, Paragraph, Spacer, Table, TableStyle

from .company_branding import seros_logo_path
from .pdf_reportlab import FONT, FONT_BOLD, MM, NAVY, PX, Chips, data_table, flow_text, note_flowable, register_fonts, render_story_report

PRINT_ROW_LIMIT = 2000

PIE_COLORS = ["#1a3f7a", "#2563eb", "#f59e0b", "#059669", "#dc2626", "#7c3aed", "#0891b2", "#db2777", "#65a30d"]


def _fmt_naive(dt):
    """event_dt/close_out_dt only — no timezone conversion, see module docstring."""
    return dt.strftime("%d/%m/%Y %H:%M") if dt else ""


def _emp_name(emp):
    return " ".join(p for p in [emp.emp_fname, emp.emp_mname, emp.emp_sname] if p)


def _pie_chart(title, counts):
    """counts: list of (label, count), already sorted by caller. No slices
    (rendered as "No Data Available", matching the sample PDF) when the
    filtered set has nothing in this grouping."""
    total = sum(c for _, c in counts)
    slices = [
        {"label": label, "count": count, "pct": round(count / total * 100, 1), "color": PIE_COLORS[i % len(PIE_COLORS)]}
        for i, (label, count) in enumerate(counts)
    ]
    return {"title": title, "slices": slices if total else []}


PIE_SIZE = 100 * PX


def _pie_drawing(slices):
    """Wedges clockwise from 12 o'clock, like the old SVG."""
    d = Drawing(PIE_SIZE, PIE_SIZE)
    r = PIE_SIZE / 2
    total = sum(sl["count"] for sl in slices)
    if len(slices) == 1:
        d.add(Circle(r, r, r, fillColor=colors.HexColor(slices[0]["color"]), strokeColor=None))
        return d
    cursor = 0.0
    for sl in slices:
        angle = sl["count"] / total * 360
        d.add(Wedge(r, r, r, 90 - cursor - angle, 90 - cursor, fillColor=colors.HexColor(sl["color"]), strokeColor=None, strokeWidth=0))
        cursor += angle
    return d


def _legend(slices, width):
    size = 6.8
    label_style = ParagraphStyle("lg", fontName=FONT, fontSize=size, leading=size * 1.2, textColor=colors.HexColor("#374151"))
    value_style = ParagraphStyle("lv", fontName=FONT, fontSize=size, leading=size * 1.2, textColor=colors.HexColor("#6b7280"))
    dot_w = 6 * PX + 3 * PX
    values = [f"{sl['count']} ({sl['pct']}%)" for sl in slices]
    value_w = max(stringWidth(v, FONT, size) for v in values) + 2 * PX
    rows = []
    for sl, v in zip(slices, values):
        dot = Drawing(6 * PX, 6 * PX)
        dot.add(Circle(3 * PX, 3 * PX, 3 * PX, fillColor=colors.HexColor(sl["color"]), strokeColor=None))
        rows.append([dot, Paragraph(flow_text(sl["label"]), label_style), Paragraph(v, value_style)])
    t = Table(rows, colWidths=[dot_w, max(width - dot_w - value_w, 20), value_w])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (0, -1), 3 * PX),
                ("RIGHTPADDING", (1, 0), (1, -1), 2 * PX),
                ("RIGHTPADDING", (2, 0), (2, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * PX),
            ]
        )
    )
    return t


def _chart_cards(charts, avail):
    """Four equal-height bordered cards in a row."""
    gap = 10 * PX
    cw = (avail - gap * 3) / 4
    inner = cw - 16 * PX
    title_style = ParagraphStyle("ct", fontName=FONT_BOLD, fontSize=7.6, leading=7.6 * 1.2, textColor=NAVY, alignment=1)
    empty_style = ParagraphStyle("ce", fontName=FONT, fontSize=7.6, leading=9.1, textColor=colors.HexColor("#9ca3af"), alignment=1)
    contents = []
    for ch in charts:
        parts = [Paragraph(flow_text(ch["title"].upper()), title_style), Spacer(1, 6 * PX)]
        if ch["slices"]:
            legend_w = inner - PIE_SIZE - 6 * PX
            body = Table([[_pie_drawing(ch["slices"]), _legend(ch["slices"], legend_w)]], colWidths=[PIE_SIZE + 6 * PX, legend_w])
            body.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (0, -1), 6 * PX), ("RIGHTPADDING", (1, 0), (1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
            parts.append(body)
        else:
            parts += [Spacer(1, 30 * PX), Paragraph("No Data Available", empty_style), Spacer(1, 30 * PX)]
        contents.append(parts)
    height = 0
    for parts in contents:
        height = max(height, sum(p.wrap(inner, 10000)[1] for p in parts) + 16 * PX)
    cards = []
    for parts in contents:
        c = Table([[parts]], colWidths=[cw], rowHeights=[height])
        c.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#e5e7eb")), ("ROUNDEDCORNERS", [6 * PX] * 4), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 8 * PX), ("RIGHTPADDING", (0, 0), (-1, -1), 8 * PX), ("TOPPADDING", (0, 0), (-1, -1), 8 * PX), ("BOTTOMPADDING", (0, 0), (-1, -1), 8 * PX)]))
        cards.append(c)
    row = Table([[cards[0], "", cards[1], "", cards[2], "", cards[3]]], colWidths=[cw, gap, cw, gap, cw, gap, cw])
    row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return row


COLUMNS = [
    {"label": "Sr", "width": 24, "align": "right"},
    {"label": "Card No.", "width": 44},
    {"label": "Operator", "width": 70},
    {"label": "Location", "width": 80},
    {"label": "Date of Event", "width": 72},
    {"label": "Reported By", "width": 64},
    {"label": "Type", "width": 64},
    {"label": "TOFS", "width": 38},
    {"label": "Hazard Description", "width": None},
    {"label": "Action Taken", "width": None},
    {"label": "Resp Dept", "width": 68},
    {"label": "Resp Rank", "width": 62},
    {"label": "Close Out Date", "width": 72},
    {"label": "Status", "width": 52},
]


def render_hazard_card_report_pdf(queryset, filter_summary, period_label=None):
    register_fonts()
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

    avail = landscape(A4)[0] - 24 * MM
    story = []
    if filter_summary:
        story += [Chips(list(filter_summary)), Spacer(1, 10 * PX)]
    if total > PRINT_ROW_LIMIT:
        story += [note_flowable(f"Showing the first {len(rows)} of {total} matching hazard cards — narrow the filters to print the rest.", avail), Spacer(1, 8 * PX)]
    story += [KeepTogether([_chart_cards(charts, avail)]), Spacer(1, 14 * PX)]
    group_title = ParagraphStyle("gt", fontName=FONT_BOLD, fontSize=9, leading=10.8, textColor=NAVY)
    for g in grouped_rows:
        table_rows = [
            [
                r["sr_no"], r["haz_id_card_no"], r["operator_name"] or "—", r["work_location_name"] or "—", r["event_dt"], r["reported_by"] or "—",
                r["haz_type_name"] or "—", r["tfs"], r["hazard_desc"], r["action_taken"] or "—", r["resp_dept_name"] or "—",
                r["resp_rank_name"] or "—", r["close_out_dt"] or "—", r["status_label"],
            ]
            for r in g["rows"]
        ]
        # a heading never sits alone at the bottom of a page
        story += [CondPageBreak(70), Spacer(1, 10 * PX), Paragraph(flow_text(g["rig_name"]), group_title), Spacer(1, 4 * PX)]
        story += [data_table(COLUMNS, table_rows, avail, head_size=7.2, cell_size=7.4, pad_x=5, pad_y=4, center=(7,)), Spacer(1, 8 * PX)]
    if not grouped_rows:
        story.append(Paragraph("No hazard cards match the current filters.", ParagraphStyle("none", fontName=FONT, fontSize=8.4, textColor=colors.HexColor("#9ca3af"), alignment=1, spaceBefore=20)))
    title = "Hazard ID Card Report" + (f" ({period_label})" if period_label else "")
    return render_story_report(
        story,
        title=title,
        logo_path=seros_logo_path(),
        meta=[
            [("Generated ", False), (timezone.now().strftime("%d/%m/%Y %H:%M"), True)],
            [("Total ", False), (str(total), True), (f" hazard{'' if total == 1 else 's'}", False)],
        ],
    )
