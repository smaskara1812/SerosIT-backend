"""Candidate Interview Details > Generate Resume: the "Bio Data of Key Personnel" sheet, in the format of the sample resume HR supplied (Seros logo top
right, a titled list of ten numbered particulars, a trainings table, then the experience pro forma). Built from the saved record, so the page offers it
for a saved candidate only. Drawn with ReportLab like the other printable reports (core/pdf_reportlab.py).

Two things follow the sample on purpose: the experience rows run oldest first (the sample does, although the line says "reverse order"), and the
experience line of the list says "As per attached pro forma sheet". The sample's spelling "ADRESS" is corrected.
"""

import os
from io import BytesIO

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from core.pdf_reportlab import FONT, FONT_BOLD, register_fonts, text

INK = colors.black
LINE = colors.black


def _logo():
    """The full Seros logo as a flowable, about 55 mm wide, or None if the file is missing."""
    for path in (
        os.path.join(os.path.dirname(settings.BASE_DIR), "frontend", "public", "branding", "seros-logo.png"),
        os.path.join(settings.BASE_DIR, "core", "banner_logos", "seros-logo.png"),
    ):
        if os.path.isfile(path):
            width = 55 * mm
            w, h = ImageReader(path).getSize()
            img = Image(path, width=width, height=width * h / w, mask="auto")
            img.hAlign = "RIGHT"
            return img
    return None


def _dmy(d):
    return d.strftime("%d/%m/%Y") if d else ""


def _day(d):
    return d.strftime("%d %b %Y") if d else ""


def _month(d):
    return d.strftime("%b %Y") if d else ""


def full_name(hdr):
    return " ".join(p for p in (hdr.candidate_fname, hdr.candidate_mname, hdr.candidate_lname) if p and p.strip())


def render_resume_pdf(hdr):
    """The resume as PDF bytes for one CandidateInterviewHdr."""
    register_fonts()
    body = ParagraphStyle("body", fontName=FONT, fontSize=9, leading=12, textColor=INK)
    label = ParagraphStyle("label", fontName=FONT_BOLD, fontSize=9, leading=12, textColor=INK)
    head = ParagraphStyle("head", fontName=FONT_BOLD, fontSize=9, leading=12, textColor=INK)
    title = ParagraphStyle("title", fontName=FONT_BOLD, fontSize=9.5, leading=13, alignment=1, textColor=INK)
    cell = ParagraphStyle("cell", fontName=FONT, fontSize=8.6, leading=11, textColor=INK)
    cell_head = ParagraphStyle("cell_head", fontName=FONT_BOLD, fontSize=8.6, leading=11, textColor=INK)

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=12 * mm, bottomMargin=15 * mm,
                            title=f"Bio data - {full_name(hdr)}", author="Seros")
    story = []
    logo = _logo()
    if logo:
        story.append(logo)
    story += [Spacer(1, 6 * mm), Paragraph("BIO DATA OF KEY PERSONNEL", title), Spacer(1, 7 * mm)]

    rows = [
        ("1. NAME", full_name(hdr)),
        ("2. PRESENT ADDRESS", hdr.present_addr),
        ("3. PERMANENT ADDRESS", hdr.permanent_addr),
        ("4. FATHER’S NAME", hdr.father_name),
        ("5. NATIONALITY", hdr.nationality),
        ("6. DESIGNATED POST", hdr.designated_post),
        ("7. EDUCATIONAL QUALIFICATIONS", hdr.edu_qualification),
        ("8. DATE OF BIRTH", _dmy(hdr.candidate_dob)),
        ("9. EXPERIENCE IN REVERSE ORDER", "As per attached pro forma sheet"),
        ("10. TRAININGS", ""),
    ]
    particulars = Table(
        [[Paragraph(text(k), label), Paragraph(":", label), Paragraph(text(v), body)] for k, v in rows],
        colWidths=[62 * mm, 6 * mm, None],
    )
    particulars.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 3.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2),
                                     ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 2)]))
    story += [particulars, Spacer(1, 3 * mm)]

    def grid(header, data, widths):
        t = Table([[Paragraph(text(h), cell_head) for h in header]] + [[Paragraph(text(c), cell) for c in r] for r in data], colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.6, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 2),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 2), ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]))
        return t

    width = A4[0] - 36 * mm
    quarter = [width * 0.235, width * 0.235, width * 0.265, width * 0.265]
    trainings = hdr.trainings.order_by("cert_valid_from_dt", "candidate_train_dtl_id")
    story.append(grid(
        ["Name", "Period", "Name of Agency", "Certificate No & Date"],
        [(t.training_type, f"{_day(t.cert_valid_from_dt)}  - {_day(t.cert_valid_to_dt)}", t.training_agency, f"{t.training_cert_no} - {_dmy(t.training_cert_dt)}")
         for t in trainings] or [("", "", "", "")],
        quarter,
    ))
    story += [Spacer(1, 4 * mm), Paragraph("PRO FORMA FOR EXPERIENCE CONTRACTORS PERSONNEL:", head), Spacer(1, 2 * mm)]
    experiences = hdr.experiences.order_by("exp_from_dt", "candidate_exp_dtl_id")
    story.append(grid(
        ["Period", "Years/Months", "Company", "Designation"],
        [(f"{_month(e.exp_from_dt)} - {_month(e.exp_to_dt)}", f"{e.exp_years}Yr {e.exp_months} Mnths", e.company_name, e.designation) for e in experiences] or [("", "", "", "")],
        quarter,
    ))
    doc.build(story)
    return buf.getvalue()
