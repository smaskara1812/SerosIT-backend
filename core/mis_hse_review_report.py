"""PDF render for QHSE → Monthly HSE Review — drawn with ReportLab
(pdf_reportlab.build_letterhead for the header, tables built here)."""

from decimal import ROUND_HALF_UP, Decimal
from io import BytesIO

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle

from .company_branding import seros_logo_path
from .pdf_reportlab import (
    FONT,
    FONT_BOLD,
    FONT_ITALIC,
    MM,
    NAVY,
    PX,
    ROW_LINE,
    TEXT,
    NumberedCanvas,
    build_letterhead,
    flow_text,
    register_fonts,
)

CAPTION_BG, CAPTION_LINE = colors.HexColor("#e8edf7"), colors.HexColor("#c7d2e5")
HEAD_BG, HEAD_LINE = colors.HexColor("#eef2ff"), colors.HexColor("#d1d9ec")
STAT_BG, STAT_TEXT, STAT_LINE = colors.HexColor("#dbeafe"), colors.HexColor("#1e3a8a"), colors.HexColor("#bfdbfe")
INACTIVE = colors.HexColor("#9ca3af")


def _fixed(value, places):
    """Rounds half up, like the template's floatformat did, without thousands separators."""
    q = Decimal(1).scaleb(-places)
    return str(Decimal(str(value if value is not None else 0)).quantize(q, rounding=ROUND_HALF_UP))


def _styles():
    cell = ParagraphStyle("cell", fontName=FONT, fontSize=8, leading=8 * 1.17, textColor=TEXT)
    return {
        "cell": cell,
        "num": ParagraphStyle("num", parent=cell, alignment=2),
        "head": ParagraphStyle("head", parent=cell, fontName=FONT_BOLD, fontSize=7.2, leading=7.2 * 1.17),
        "caption": ParagraphStyle("caption", parent=cell, fontName=FONT_BOLD, fontSize=7.8, leading=7.8 * 1.17, textColor=NAVY),
        "muted": ParagraphStyle("muted", parent=cell, textColor=INACTIVE),
        "grey_i": ParagraphStyle("grey_i", parent=cell, fontName=FONT_ITALIC, textColor=INACTIVE),
        "grey_i_num": ParagraphStyle("grey_i_num", parent=cell, fontName=FONT_ITALIC, textColor=INACTIVE, alignment=2),
        "bold": ParagraphStyle("bold", parent=cell, fontName=FONT_BOLD),
        "stat": ParagraphStyle("stat", parent=cell, fontName=FONT_BOLD, fontSize=7.8, leading=7.8 * 1.17, textColor=STAT_TEXT),
        "period": ParagraphStyle("period", parent=cell, fontName=FONT_BOLD, fontSize=8.4, leading=8.4 * 1.17, textColor=colors.white),
    }


def _table(st, width, caption, widths, rows, header=None):
    """A captioned table. widths: points for every column but the first, which
    takes the rest. Each row is a list of (text, style_name) pairs; a row of one
    pair spans the table."""
    n = len(widths) + 1
    col_w = [width - sum(widths)] + list(widths)
    data = [[Paragraph(flow_text(caption), st["caption"])] + [""] * (n - 1)]
    style = [
        ("SPAN", (0, 0), (-1, 0)),
        ("BACKGROUND", (0, 0), (-1, 0), CAPTION_BG),
        ("BOX", (0, 0), (-1, 0), 0.75 * PX, CAPTION_LINE),
    ]
    first_body = 1
    if header:
        data.append([Paragraph(flow_text(h), st["head"]) for h in header])
        style += [("BACKGROUND", (0, 1), (-1, 1), HEAD_BG), ("GRID", (0, 1), (-1, 1), 0.75 * PX, HEAD_LINE)]
        first_body = 2
    for r in rows:
        if len(r) == 1:
            data.append([Paragraph(flow_text(r[0][0]), st[r[0][1]])] + [""] * (n - 1))
            style.append(("SPAN", (0, len(data) - 1), (-1, len(data) - 1)))
        else:
            data.append([Paragraph(flow_text(t), st[s]) for t, s in r])
    if len(data) > first_body:
        style.append(("GRID", (0, first_body), (-1, -1), 0.75 * PX, ROW_LINE))
    style += [
        ("TOPPADDING", (0, 0), (-1, -1), 3 * PX),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * PX),
        ("LEFTPADDING", (0, 0), (-1, -1), 6 * PX),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6 * PX),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    # Only the column-header row repeats on a following page, not the caption.
    t = Table(data, colWidths=col_w, repeatRows=(1,) if header else 0)
    t.setStyle(TableStyle(style))
    return t


def render_mis_hse_review_pdf(report):
    register_fonts()
    st = _styles()
    page_w, page_h = A4
    scope = report["project_label"] if report["filter_type"] == "PROJECT" else "SEROS (All Rigs)"
    draw_header, top, left, right, bottom = build_letterhead(
        page_w,
        page_h,
        title=report["report_title"],
        logo_path=seros_logo_path(),
        meta=[
            [("Generated ", False), (timezone.now().strftime("%d/%m/%Y %H:%M"), True)],
            [("Scope ", False), (scope, True)],
        ],
        top_margin_mm=30,
        side_mm=10,
        title_size=14,
        logo_px=28,
        meta_size=7.4,
        header_offset=12,
    )
    width = page_w - left - right
    gap = 10 * PX
    col_w = (width - gap) / 2
    gap_after = Spacer(1, 8 * PX)

    # ── left column ──
    mh = report["manhours"]
    mh_rows = [[(r["label"], "cell"), (_fixed(r["total_man_hours"], 0), "num")] for r in mh["rows"]]
    if mh["third_party_rows"]:
        mh_rows.append([("Third Party", "bold")])
        mh_rows += [[(r["label"], "cell"), (_fixed(r["total_man_hours"], 0), "num")] for r in mh["third_party_rows"]]
    if not mh["rows"] and not mh["third_party_rows"]:
        mh_rows = [[("No data for this period.", "muted")]]
    hz = report["hazard_card"]
    hz_rows = [
        [(label, "cell"), (str(hz[key]["total"]), "num"), (str(hz[key]["seros"]), "num"), (str(hz[key]["others"]), "num")]
        for label, key in (("Hazard ID Card", "total"), ("Open", "open"), ("Close", "close"))
    ]
    left_col = [
        _table(st, col_w, "Manhours (Total Man Hours)", [90], mh_rows) if len(mh_rows) != 1 or len(mh_rows[0]) != 1 else _table(st, col_w, "Manhours (Total Man Hours)", [], mh_rows),
        gap_after,
        _table(st, col_w, "Meetings", [30], [[("TOTAL HSE MEETINGS HELD", "cell"), (str(report["meetings_total"]), "num")]]),
        gap_after,
        _table(
            st, col_w, "Incidents", [32, 42, 62],
            [[(r["incident_type"], "cell"), (str(r["total"]), "num"), (str(r["seros"]), "num"), (str(r["contractor"]), "num")] for r in report["incidents"]],
            header=["Incident Type", "Total", "SEROS", "Contractor"],
        ),
        gap_after,
        _table(st, col_w, "Hazard ID Card", [52, 54, 54], hz_rows, header=["", "Total", "SEROS", "Others"]),
    ]

    # ── right column ──
    lti_rows = []
    for r in report["lti"]:
        if r["active"]:
            lti_rows.append([(r["rig_name"], "cell"), (str(r["lti_free_days"]), "num")])
        else:
            lti_rows.append([(r["rig_name"], "grey_i"), ("Not in operation", "grey_i_num")])
    right_col = [
        _table(st, col_w, "Rig Name — LTI Free Days", [128], lti_rows),
        gap_after,
        _table(
            st, col_w, "HSE Inspections/Drills/Audits", [92],
            [[(r["activity_name"], "cell"), (str(r["total_number"]), "num")] for r in report["activities"]],
            header=["Activity", "Total Number"],
        ),
    ]

    columns = Table([[left_col, "", right_col]], colWidths=[col_w, gap, col_w], splitInRow=1)
    columns.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))

    period = Table(
        [[Paragraph(flow_text(f"HSE Return ({report['period_label']}) ({report['date_from']:%d/%m/%Y} - {report['date_to']:%d/%m/%Y})"), st["period"])]],
        colWidths=[width],
    )
    period.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY), ("TOPPADDING", (0, 0), (-1, -1), 4 * PX), ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * PX), ("LEFTPADDING", (0, 0), (-1, -1), 8 * PX)]))

    stats = report["statistics"]
    stat_title = Table([[Paragraph(flow_text(f"HSE Statistics ({stats['statistic_from']:%d/%m/%Y} - {stats['statistic_to']:%d/%m/%Y})"), st["stat"])]], colWidths=[width])
    stat_title.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), STAT_BG), ("BOX", (0, 0), (-1, -1), 0.75 * PX, STAT_LINE), ("TOPPADDING", (0, 0), (-1, -1), 3 * PX), ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * PX), ("LEFTPADDING", (0, 0), (-1, -1), 6 * PX)]))
    stat_rows = Table(
        [
            [Paragraph(flow_text("LTIF — Lost Time Injury Frequency (per 1,000,000 exposure hours)"), st["cell"]), Paragraph(_fixed(stats["ltif"], 3), st["num"])],
            [Paragraph(flow_text("TRIR — Total Recordable Incident Rate (per 200,000 exposure hours)"), st["cell"]), Paragraph(_fixed(stats["trir"], 3), st["num"])],
        ],
        colWidths=[width - 55, 55],
    )
    stat_rows.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.75 * PX, ROW_LINE), ("TOPPADDING", (0, 0), (-1, -1), 3 * PX), ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * PX), ("LEFTPADDING", (0, 0), (-1, -1), 6 * PX), ("RIGHTPADDING", (0, 0), (-1, -1), 6 * PX)]))

    env = _table(
        st, width, "Environment Reporting", [88, 65],
        [[(r["consumable_name"], "cell"), (r["unit"] or "", "cell"), (_fixed(r["total_quantity"], 2), "num")] for r in report["environment"]],
        header=["Consumable", "Unit", "Total Qty."],
    )

    story = [period, Spacer(1, 6 * PX), columns, Spacer(1, 6 * PX), stat_title, stat_rows, Spacer(1, 8 * PX), env]
    buf = BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4, leftMargin=left, rightMargin=right, topMargin=top, bottomMargin=bottom, title=report["report_title"])
    frame = Frame(left, bottom, width, page_h - top - bottom, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=draw_header)])
    doc.build(story, canvasmaker=NumberedCanvas)
    return buf.getvalue()
