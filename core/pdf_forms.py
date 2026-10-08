"""ReportLab kit for the one-record "form" reports (HSE Drill Record, Incident
Flash Report): letterhead with report number strip, rounded titled sections,
label/value grids, metric cards, photos.

Everything is portrait A4 with 14mm side margins, matching the layout these
reports had as HTML. See pdf_reportlab.py for the table-style reports.
"""

import os
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import BaseDocTemplate, Frame, Image, KeepTogether, PageTemplate, Paragraph, Spacer, Table, TableStyle

from .pdf_reportlab import FONT, FONT_BOLD, MM, NAVY, PX, Spaced, flow_text, numbered_canvas, register_fonts

LINE = colors.HexColor("#e5e7eb")
SOFT_LINE = colors.HexColor("#f1f5f9")
CARD_BG = colors.HexColor("#f8fafc")
LABEL = colors.HexColor("#374151")
LABEL_LIGHT = colors.HexColor("#9ca3af")
INK = colors.HexColor("#111827")
MUTED = colors.HexColor("#6b7280")
EMPTY = colors.HexColor("#c1c7d0")
GREY = colors.HexColor("#9ca3af")
ACCENT = colors.HexColor("#2563eb")

PAGE_W, PAGE_H = A4
SIDE = 14 * MM
WIDTH = PAGE_W - 2 * SIDE
INNER = WIDTH - 28 * PX  # inside a section's padding
PHOTO_PX = 900  # photos are scaled down before embedding


def dash(v):
    return v if v else "—"


def plain():
    return [("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]


def base_styles():
    register_fonts()
    value = ParagraphStyle("value", fontName=FONT, fontSize=8.8, leading=8.8 * 1.32, textColor=INK)
    return {
        "value": value,
        "empty": ParagraphStyle("empty", parent=value, textColor=EMPTY),
        "company": ParagraphStyle("company", fontName=FONT_BOLD, fontSize=15, leading=15 * 1.15, textColor=NAVY),
        "bullet": ParagraphStyle("bullet", fontName=FONT, fontSize=8.6, leading=8.6 * 1.35, textColor=INK, leftIndent=14 * PX, bulletIndent=2, bulletFontName=FONT, spaceAfter=3 * PX),
        "metric_label": ParagraphStyle("metric_label", fontName=FONT_BOLD, fontSize=6.6, leading=7.9, textColor=LABEL, alignment=1),
        "na": ParagraphStyle("na", fontName=FONT, fontSize=7, leading=8.4, textColor=GREY, alignment=1),
    }


def label(text, color=LABEL, align="left"):
    return Spaced(text.upper(), FONT_BOLD, 7, color, 0.04, align=align, leading=8.1)


def field(st, text, value, label_color=LABEL, grey_empty=False, align="left"):
    """A small caps label above its value. With grey_empty, a blank value shows a grey dash."""
    blank = value in (None, "")
    style = st["empty"] if (blank and grey_empty) else st["value"]
    if align == "right":
        style = ParagraphStyle("vr", parent=style, alignment=2)
    return [label(text, label_color, align), Spacer(1, 0.75), Paragraph(flow_text("—" if blank else value), style)]


def grid(cells, cols, width, gap_x=18 * PX, gap_y=6 * PX, spans=()):
    """CSS-grid-like layout: equal columns with gaps. cells are flowable lists (or '').
    spans: (row, col, n) to let a cell cover n columns; the cells it covers must be ''."""
    cw = (width - gap_x * (cols - 1)) / cols
    rows = [cells[i : i + cols] for i in range(0, len(cells), cols)]
    rows = [r + [""] * (cols - len(r)) for r in rows]
    t = Table(rows, colWidths=[cw + gap_x] * (cols - 1) + [cw])
    style = plain() + [("VALIGN", (0, 0), (-1, -1), "TOP")]
    style += [("RIGHTPADDING", (c, 0), (c, -1), gap_x) for c in range(cols - 1)]
    style += [("BOTTOMPADDING", (0, r), (-1, r), gap_y) for r in range(len(rows) - 1)]
    style += [("SPAN", (c, r), (c + n - 1, r)) for r, c, n in spans]
    t.setStyle(TableStyle(style))
    return t


def section(title, flowables, title_color=NAVY, bar_color=ACCENT, background=None, border=LINE):
    """Rounded box with a barred title; its content flows across pages if long."""
    heading = Table([["", Spaced(title.upper(), FONT_BOLD, 7.6, title_color, 0.06, leading=8.8)]], colWidths=[3 * PX, WIDTH - 21 - 3 * PX])
    heading.setStyle(TableStyle(plain() + [("BACKGROUND", (0, 0), (0, 0), bar_color), ("LEFTPADDING", (1, 0), (1, 0), 8 * PX)]))
    return box([heading, Spacer(1, 5 * PX)] + list(flowables), background, border)


def box(flowables, background=None, border=LINE):
    t = Table([[list(flowables)]], colWidths=[WIDTH], splitInRow=1)
    style = [
        ("BOX", (0, 0), (-1, -1), 0.75, border),
        ("ROUNDEDCORNERS", [6 * PX] * 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 14 * PX),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14 * PX),
        ("TOPPADDING", (0, 0), (-1, -1), 8 * PX),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8 * PX),
    ]
    if background:
        style.append(("BACKGROUND", (0, 0), (-1, -1), background))
    t.setStyle(TableStyle(style))
    return t


def bullets(st, items):
    if not items:
        return [Paragraph("—", st["empty"])]
    return [Paragraph(flow_text(t), st["bullet"], bulletText="•") for t in items]


def header(st, company_name, logo_path, title, meta_items):
    """Logo + company + report title over a navy rule, then a right-aligned strip
    of (label, value, emphasis) items."""
    logo = None
    left_w = 0
    if logo_path and os.path.isfile(logo_path):
        iw, ih = ImageReader(logo_path).getSize()
        h = 52 * PX
        logo = Image(logo_path, width=iw * h / ih, height=h, mask="auto")
        left_w = iw * h / ih + 16 * PX
    texts = []
    if company_name:
        texts.append(Paragraph(flow_text(company_name), st["company"]))
    texts += [Spacer(1, 3 * PX), Spaced(title.upper(), FONT_BOLD, 8, MUTED, 0.09, leading=10)]
    t = Table([[logo or "", texts]], colWidths=[left_w, WIDTH - left_w] if logo else [0.01, WIDTH - 0.01])
    t.setStyle(TableStyle(plain() + [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOTTOMPADDING", (0, 0), (-1, -1), 10 * PX), ("LINEBELOW", (0, 0), (-1, -1), 1.5 * PX, NAVY)]))
    cells, widths = [], []
    for text, value, emphasis in meta_items:
        w = max(stringWidth(text.upper(), FONT_BOLD, 7) + 0.04 * 7 * len(text), stringWidth(str(value or ""), FONT_BOLD, 8.6)) + 1
        widths.append(w + 22 * PX)
        vstyle = ParagraphStyle("mv", fontName=FONT_BOLD, fontSize=8.6, leading=10.8, textColor=NAVY if emphasis else LABEL, alignment=2)
        cells.append([Spaced(text.upper(), FONT_BOLD, 7, LABEL, 0.04, align="right", leading=8.6), Spacer(1, 1 * PX), Paragraph(flow_text(value), vstyle)])
    widths[-1] -= 22 * PX
    strip = Table([cells], colWidths=widths)
    strip.setStyle(TableStyle(plain() + [("RIGHTPADDING", (0, 0), (-2, -1), 22 * PX)]))
    meta = Table([["", strip]], colWidths=[WIDTH - sum(widths), sum(widths)])
    meta.setStyle(TableStyle(plain() + [("BOTTOMPADDING", (0, 0), (-1, -1), 8 * PX), ("LINEBELOW", (0, 0), (-1, -1), 0.75, LINE)]))
    return [t, Spacer(1, 6 * PX), meta, Spacer(1, 8 * PX)]


def card(st, value, text, width, value_size=11.5, label_color=LABEL):
    value_style = ParagraphStyle("metric", fontName=FONT_BOLD, fontSize=value_size, leading=value_size * 1.22, textColor=NAVY, alignment=1)
    label_style = ParagraphStyle("metric_l", parent=st["metric_label"], textColor=label_color)
    t = Table([[Paragraph(flow_text(value), value_style)], [Paragraph(flow_text(text.upper()), label_style)]], colWidths=[width])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), CARD_BG),
                ("BOX", (0, 0), (-1, -1), 0.75, LINE),
                ("ROUNDEDCORNERS", [5 * PX] * 4),
                ("TOPPADDING", (0, 0), (-1, 0), 6 * PX),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 0),
                ("TOPPADDING", (0, 1), (-1, 1), 1 * PX),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 6 * PX),
                ("LEFTPADDING", (0, 0), (-1, -1), 6 * PX),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6 * PX),
            ]
        )
    )
    return t


def photo_card(st, photo_path, width, caption=None, max_height=520):
    """A bordered tile with the photo (EXIF rotation applied, scaled down), or an
    'Image not available' tile when the file is missing or unreadable."""
    inner = []
    if photo_path and os.path.isfile(photo_path):
        try:
            from PIL import Image as PILImage
            from PIL import ImageOps

            with PILImage.open(photo_path) as im:
                im = ImageOps.exif_transpose(im).convert("RGB")
                im.thumbnail((PHOTO_PX, PHOTO_PX * 2))
                buf = BytesIO()
                im.save(buf, "JPEG", quality=85)
                w, h = im.size
            buf.seek(0)
            iw = width - 1.5
            ih = iw * h / w
            if ih > max_height:
                iw, ih = iw * max_height / ih, max_height
            inner.append(Image(buf, width=iw, height=ih))
        except Exception:
            inner = []
    if not inner:
        inner.append(Paragraph("Image not available", st["na"]))
        unavailable = True
    else:
        unavailable = False
    rows = [[inner[0]]]
    if caption:
        rows.append([Spaced(caption.upper(), FONT_BOLD, 7.5, MUTED, 0.04, leading=9)])
    t = Table(rows, colWidths=[width])
    style = plain() + [("BOX", (0, 0), (-1, -1), 0.75, LINE), ("ROUNDEDCORNERS", [6 * PX] * 4), ("ALIGN", (0, 0), (-1, 0), "CENTER")]
    if unavailable:
        style += [("BACKGROUND", (0, 0), (-1, 0), CARD_BG), ("TOPPADDING", (0, 0), (-1, 0), 6 * PX), ("BOTTOMPADDING", (0, 0), (-1, 0), 6 * PX)]
    else:
        style += [("LEFTPADDING", (0, 0), (-1, 0), 0.75), ("TOPPADDING", (0, 0), (-1, 0), 0.75)]
    if caption:
        style += [("LEFTPADDING", (0, 1), (-1, 1), 10 * PX), ("TOPPADDING", (0, 1), (-1, 1), 6 * PX), ("BOTTOMPADDING", (0, 1), (-1, 1), 6 * PX)]
    t.setStyle(TableStyle(style))
    return t


MAX_KEEP = PAGE_H - 26 * MM - 130  # roughly one page's body, under the running header


def keep(*flowables, after=6 * PX):
    """Keeps these together on one page: if they don't fit in what is left, they
    all move to the next page, so a section is never cut off mid-way. One taller
    than a page can't move whole, so it is let through to flow and split instead
    of leaving a blank band behind. The gap after is inside the group, so it never
    leaves a blank strip at the top of a page."""
    height = sum(f.wrap(WIDTH, PAGE_H * 10)[1] for f in flowables)
    items = list(flowables) + [Spacer(1, after)]
    return KeepTogether(items) if height <= MAX_KEEP else items


def build(story, title, headers):
    """Builds the PDF with a running header on every page.

    headers: {template name: header flowables from header()}. The first is the
    default; switch with NextPageTemplate(name) before a PageBreak."""
    register_fonts()
    buf = BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4, leftMargin=SIDE, rightMargin=SIDE, topMargin=13 * MM, bottomMargin=13 * MM, title=title)
    top = PAGE_H - 13 * MM
    templates = []
    for name, flowables in headers.items():
        sizes = [f.wrap(WIDTH, PAGE_H)[1] for f in flowables]
        used = sum(sizes)

        def draw(canvas, _doc, flowables=flowables, sizes=sizes):
            y = top
            for f, h in zip(flowables, sizes):
                f.wrap(WIDTH, PAGE_H)
                f.drawOn(canvas, SIDE, y - h)
                y -= h

        frame = Frame(SIDE, 13 * MM, WIDTH, top - used - 13 * MM, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        templates.append(PageTemplate(id=name, frames=[frame], onPage=draw))
    doc.addPageTemplates(templates)
    story = [x for item in story for x in (item if isinstance(item, list) else [item])]  # keep() may return a list
    doc.build(story, canvasmaker=numbered_canvas(14))
    return buf.getvalue()
