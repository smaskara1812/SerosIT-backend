"""ReportLab building blocks for the printable reports.

ReportLab is pure Python (`pip install reportlab`): no system libraries, so
nothing extra to install on a server. Reports are moved here from WeasyPrint
one at a time; each keeps its look (same colours, fonts, layout) so the PDF
reads the same as before.

`render_table_report` covers the "letterhead + filter chips + one long table"
shape shared by the Incident Register and the Incident Dashboard drill-down.
The helpers it is built from (fonts, running header, "Page X of Y" footer) are
meant to be reused by the other reports as they move over.
"""

import os
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import BaseDocTemplate, Flowable, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle

FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
FONT, FONT_BOLD, FONT_ITALIC = "LiberationSans", "LiberationSans-Bold", "LiberationSans-Italic"

NAVY = colors.HexColor("#1a3f7a")
TEXT = colors.HexColor("#1f2937")
TEXT_STRONG = colors.HexColor("#374151")
MUTED = colors.HexColor("#6b7280")
FOOTER = colors.HexColor("#9ca3af")
ROW_LINE = colors.HexColor("#e5e7eb")
ROW_ALT = colors.HexColor("#f8fafc")
CHIP_BG = colors.HexColor("#eef2ff")
CHIP_LINE = colors.HexColor("#c7d2fe")
NOTE_BG = colors.HexColor("#fffbeb")
NOTE_LINE = colors.HexColor("#fde68a")
NOTE_TEXT = colors.HexColor("#92400e")

PX = 0.75  # the old templates were written in CSS pixels; 1px = 0.75pt
MM = 72 / 25.4

_fonts_ready = False


def register_fonts():
    """Liberation Sans ships with the app (core/fonts), metric-compatible with
    Arial, so every server renders the same without relying on system fonts."""
    global _fonts_ready
    if _fonts_ready:
        return
    pdfmetrics.registerFont(TTFont(FONT, os.path.join(FONT_DIR, "LiberationSans-Regular.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, os.path.join(FONT_DIR, "LiberationSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_ITALIC, os.path.join(FONT_DIR, "LiberationSans-Italic.ttf")))
    pdfmetrics.registerFontFamily(FONT, normal=FONT, bold=FONT_BOLD, italic=FONT_ITALIC, boldItalic=FONT_BOLD)
    _fonts_ready = True


def flow_text(value):
    """Table cell text: runs of whitespace and line breaks collapse to one space,
    as they did when these reports were HTML."""
    return text(" ".join(str(value).split()) if value is not None else "")


def text(value):
    """Escapes user text for a Paragraph and keeps its line breaks."""
    return escape("" if value is None else str(value)).replace("\r\n", "\n").replace("\n", "<br/>")


class NumberedCanvas(rl_canvas.Canvas):
    """Draws "Page X of Y" bottom right; Y is only known once every page exists."""

    right_margin = 12 * MM
    bottom_margin = 13 * MM

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            self.setFont(FONT, 7.5)
            self.setFillColor(FOOTER)
            self.drawRightString(self._pagesize[0] - self.right_margin, self.bottom_margin - 8, f"Page {self._pageNumber} of {total}")
            super().showPage()
        super().save()


def numbered_canvas(right_mm, bottom_mm=13):
    """NumberedCanvas for a page whose right/bottom margins differ from the default."""
    return type("NumberedCanvasCustom", (NumberedCanvas,), {"right_margin": right_mm * MM, "bottom_margin": bottom_mm * MM})


class Spaced(Flowable):
    """One line of letter-spaced text (CSS letter-spacing), which Paragraph can't do."""

    def __init__(self, label, font, size, color, spacing_em=0.0, align="left", leading=None):
        super().__init__()
        self.label, self.font, self.size, self.color = label, font, size, color
        self.spacing = spacing_em * size
        self.align = align
        self.leading = leading or size * 1.25

    def wrap(self, avail_w, avail_h):
        self.avail = avail_w
        return avail_w, self.leading

    def draw(self):
        c = self.canv
        width = stringWidth(self.label, self.font, self.size) + self.spacing * len(self.label)
        x = {"left": 0, "right": self.avail - width, "center": (self.avail - width) / 2}[self.align]
        t = c.beginText(x, (self.leading - self.size) / 2 + self.size * 0.22)
        t.setFont(self.font, self.size)
        t.setFillColor(self.color)
        t.setCharSpace(self.spacing)
        t.textOut(self.label)
        c.drawText(t)


def _chip_layout(chips, max_width, size, pad_x, pad_y, gap_x, gap_y):
    """Wraps chips into rows. Returns (rows of (label, width), row height, total height)."""
    row_h = size + pad_y * 2
    rows, current, used = [], [], 0.0
    for label in chips:
        w = stringWidth(label, FONT, size) + pad_x * 2
        if current and used + gap_x + w > max_width:
            rows.append(current)
            current, used = [], 0.0
        used += (gap_x if current else 0) + w
        current.append((label, w))
    if current:
        rows.append(current)
    total = len(rows) * row_h + max(len(rows) - 1, 0) * gap_y
    return rows, row_h, total


def _draw_chips(c, x, y_top, rows, row_h, size, radius, pad_x, gap_x, gap_y):
    c.saveState()
    c.setLineWidth(0.75)
    for r_i, row in enumerate(rows):
        y = y_top - (r_i + 1) * row_h - r_i * gap_y
        cx = x
        for label, w in row:
            c.setFillColor(CHIP_BG)
            c.setStrokeColor(CHIP_LINE)
            c.roundRect(cx, y, w, row_h, min(radius, row_h / 2), fill=1, stroke=1)
            c.setFillColor(TEXT_STRONG)
            c.setFont(FONT, size)
            c.drawString(cx + pad_x, y + (row_h - size) / 2 + size * 0.22, label)
            cx += w + gap_x
    c.restoreState()


class Chips(Flowable):
    """A wrapped row of filter chips in the body (not repeated on every page)."""

    def __init__(self, chips, size=7.2, pill=True):
        super().__init__()
        self.chips, self.size = chips, size
        self.radius = 99 if pill else 4
        self.pad_x, self.pad_y, self.gap_x, self.gap_y = 8 * PX, 2 * PX, 6, 4

    def wrap(self, avail_w, avail_h):
        self.rows, self.row_h, h = _chip_layout(self.chips, avail_w, self.size, self.pad_x, self.pad_y, self.gap_x, self.gap_y)
        self.width, self.height = avail_w, h
        return avail_w, h

    def draw(self):
        _draw_chips(self.canv, 0, self.height, self.rows, self.row_h, self.size, self.radius, self.pad_x, self.gap_x, self.gap_y)


def auto_columns(labels, rows, avail_pt, cap_pt=130, sample=200):
    """Column specs sized to their content: short columns take what their widest
    cell needs (up to cap_pt), the single widest column takes the remaining width
    and wraps."""
    register_fonts()
    natural = []
    for i, label in enumerate(labels):
        w = stringWidth(str(label).upper(), FONT_BOLD, 7.4)
        for row in rows[:sample]:
            w = max(w, stringWidth(str(row[i] if row[i] is not None else ""), FONT, 8.4))
        natural.append(w + 12 * PX)
    widest = max(range(len(labels)), key=lambda i: natural[i])
    cols = []
    for i, label in enumerate(labels):
        width = None if i == widest else min(natural[i], cap_pt) / PX
        cols.append({"label": label, "width": width})
    return cols


def build_letterhead(page_w, page_h, *, title, meta, logo_path=None, subtitle=None, header_chips=(), top_margin_mm=26, side_mm=12, title_size=15, logo_px=30, meta_size=7.6, header_offset=0):
    """The running header (logo, title, optional subtitle and chips, right-hand
    meta lines, closing rule). Returns (draw_header for PageTemplate.onPage, top
    margin, left, right, bottom) so the body frame starts below it."""
    register_fonts()
    left = right = side_mm * MM
    bottom = 13 * MM
    chip_args = (7.8, 8 * PX, 2 * PX, 6, 4)
    logo_h = logo_px * PX
    title_x = left
    logo_w = 0
    if logo_path:
        iw, ih = ImageReader(logo_path).getSize()
        logo_w = iw * logo_h / ih
        title_x = left + logo_w + 10 * PX

    # Top-down layout of the letterhead: title, optional subtitle, optional chips;
    # the logo is centred against that block and the rule closes it.
    header_top = page_h - 16 - header_offset
    y = header_top - title_size * 1.25
    title_base = header_top - title_size
    sub_base = None
    if subtitle:
        sub_base = y - 8
        y -= 8 * 1.3 + 2
    chips_top = None
    if header_chips:
        chips_layout = _chip_layout(list(header_chips), page_w - right - title_x - 170, *chip_args)
        chips_top = y - 6
        y = chips_top - chips_layout[2]
    block_h = max(header_top - y, logo_h)
    rule_y = header_top - block_h - 8 * PX
    top = max(top_margin_mm * MM, page_h - rule_y + 20)

    def draw_header(c, doc):
        c.saveState()
        if logo_path:
            c.drawImage(logo_path, left, header_top - block_h / 2 - logo_h / 2, width=logo_w, height=logo_h, mask="auto")
        c.setFont(FONT_BOLD, title_size)
        c.setFillColor(NAVY)
        c.drawString(title_x, title_base, title)
        if sub_base is not None:
            c.setFont(FONT, 8)
            c.setFillColor(MUTED)
            c.drawString(title_x, sub_base, subtitle)
        if chips_top is not None:
            chip_rows_, row_h, _ = chips_layout
            _draw_chips(c, title_x, chips_top, chip_rows_, row_h, chip_args[0], 4, chip_args[1], chip_args[3], chip_args[4])
        my = header_top - 8
        for segments in meta:
            width = sum(stringWidth(t, FONT_BOLD if b else FONT, meta_size) for t, b in segments)
            x = page_w - right - width
            for t, b in segments:
                c.setFont(FONT_BOLD if b else FONT, meta_size)
                c.setFillColor(TEXT_STRONG if b else MUTED)
                c.drawString(x, my, t)
                x += stringWidth(t, FONT_BOLD if b else FONT, meta_size)
            my -= meta_size * 1.45
        c.setStrokeColor(NAVY)
        c.setLineWidth(1.5 * PX)
        c.line(left, rule_y, page_w - right, rule_y)
        c.restoreState()

    return draw_header, top, left, right, bottom


def note_flowable(note, width):
    """The yellow 'showing the first N of M' strip."""
    n = Table([[Paragraph(text(note), ParagraphStyle("note", fontName=FONT, fontSize=7.8, leading=10, textColor=NOTE_TEXT))]], colWidths=[width])
    n.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NOTE_BG), ("BOX", (0, 0), (-1, -1), 1 * PX, NOTE_LINE), ("TOPPADDING", (0, 0), (-1, -1), 5 * PX), ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * PX), ("LEFTPADDING", (0, 0), (-1, -1), 10 * PX)]))
    return n


def data_table(columns, rows, avail, empty_text="Nothing matches the current filters.", head_size=7.4, cell_size=8.4, pad_x=6, pad_y=5, center=()):
    """Navy header row (repeats on each page), zebra rows, thin row lines.

    columns: [{"label": str, "width": px or None (the rest), "align": "left"|"right"}]
    center:  indexes of columns whose cells are centred."""
    register_fonts()
    cell = ParagraphStyle("cell", fontName=FONT, fontSize=cell_size, leading=cell_size * 1.17, textColor=TEXT)
    cell_r = ParagraphStyle("cell_r", parent=cell, alignment=2)
    cell_c = ParagraphStyle("cell_c", parent=cell, alignment=1)
    head = ParagraphStyle("head", fontName=FONT_BOLD, fontSize=head_size, leading=head_size * 1.25, textColor=colors.white)
    head_r = ParagraphStyle("head_r", parent=head, alignment=2)
    head_c = ParagraphStyle("head_c", parent=head, alignment=1)

    def pick(i, right, centred):
        return right if columns[i].get("align") == "right" else centred if i in center else None

    fixed = sum((c["width"] or 0) * PX for c in columns)
    flexible = [c for c in columns if not c.get("width")]
    widths = [(c["width"] * PX) if c.get("width") else (avail - fixed) / max(len(flexible), 1) for c in columns]

    data = [[Paragraph(text(c["label"]).upper(), pick(i, head_r, head_c) or head) for i, c in enumerate(columns)]]
    for row in rows:
        data.append([Paragraph(flow_text(v), pick(i, cell_r, cell_c) or cell) for i, v in enumerate(row)])
    if not rows:
        data.append([Paragraph(text(empty_text), ParagraphStyle("empty", parent=cell, alignment=1, textColor=FOOTER))] + [""] * (len(columns) - 1))

    t = Table(data, colWidths=widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), pad_y * PX),
        ("BOTTOMPADDING", (0, 0), (-1, -1), pad_y * PX),
        ("LEFTPADDING", (0, 0), (-1, -1), pad_x * PX),
        ("RIGHTPADDING", (0, 0), (-1, -1), pad_x * PX),
        ("LINEBELOW", (0, 1), (-1, -1), 0.75 * PX, ROW_LINE),
    ]
    for r in range(2, len(data), 2):
        style.append(("BACKGROUND", (0, r), (-1, r), ROW_ALT))
    if not rows:
        style += [("SPAN", (0, 1), (-1, 1)), ("TOPPADDING", (0, 1), (-1, 1), 20 * PX), ("BOTTOMPADDING", (0, 1), (-1, 1), 20 * PX)]
    t.setStyle(TableStyle(style))
    return t


def render_story_report(
    story,
    *,
    title,
    meta,
    logo_path=None,
    subtitle=None,
    header_chips=(),
    page_size=None,
    top_margin_mm=26,
):
    """Letterhead on every page, then the given flowables, with 'Page X of Y'.
    meta: right-hand header lines, each a list of (text, bold) segments."""
    register_fonts()
    page_w, page_h = page_size or landscape(A4)
    draw_header, top, left, right, bottom = build_letterhead(
        page_w, page_h, title=title, meta=meta, logo_path=logo_path, subtitle=subtitle, header_chips=header_chips, top_margin_mm=top_margin_mm
    )
    buf = BytesIO()
    doc = BaseDocTemplate(buf, pagesize=(page_w, page_h), leftMargin=left, rightMargin=right, topMargin=top, bottomMargin=bottom, title=title)
    frame = Frame(left, bottom, page_w - left - right, page_h - top - bottom, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=draw_header)])
    doc.build(story, canvasmaker=NumberedCanvas)
    return buf.getvalue()


def render_table_report(
    *,
    title,
    columns,
    rows,
    meta,
    logo_path=None,
    subtitle=None,
    header_chips=(),
    body_chips=(),
    note=None,
    empty_text="Nothing matches the current filters.",
    page_size=None,
    top_margin_mm=26,
):
    """Letterhead on every page, optional chips and note, then one table whose
    header row repeats on each page.

    rows:  list of lists of cell values (already formatted for display)
    meta:  right-hand header lines, each a list of (text, bold) segments
    """
    page_w, _ = page_size or landscape(A4)
    avail = page_w - 24 * MM
    story = []
    if body_chips:
        story += [Chips(list(body_chips)), Spacer(1, 8)]
    if note:
        story += [note_flowable(note, avail), Spacer(1, 8)]
    story.append(data_table(columns, rows, avail, empty_text))
    return render_story_report(
        story, title=title, meta=meta, logo_path=logo_path, subtitle=subtitle, header_chips=header_chips, page_size=page_size, top_margin_mm=top_margin_mm
    )
