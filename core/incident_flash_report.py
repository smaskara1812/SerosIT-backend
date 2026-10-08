"""QHSE Incident Flash Report — a 2-page PDF built to match the mentor-
supplied blank template ("Incident flush report blank template.pdf"),
drawn with ReportLab (pdf_forms.py).

Data-wise this mirrors legacy eos.Prc_Qry_Incident_Actions's
'Get_Incident_Details_Reports' record status, with one deliberate
deviation: that proc's own Third_Party_Belongs_To case (Third_Party='N'
-> 'EOSIL' literal, ='Y' -> contractor name) is stale — the live
`third_party` column now holds either a "belongs to" code from
BELONGS_TO_LABELS (mirrors IncidentDetailsFormPage.jsx's own
BELONGS_TO_OPTIONS) or, when that code is a contractor-type code ('0'/
'1' — see CONTRACTOR_REQUIRED_THIRD_PARTY in incident_views.py), the
linked Contractor's name instead. Verified against real imported data
(values 0, 1, 2, 10, 30, 308, 309, 316 all actually occur), not guessed.

The letterhead (company name + logo) is resolved per rig/incident-date
via company_branding.resolve_rig_company_branding — see that module's
own docstring and the project memory qhse_incident_report_dynamic_branding
for why that logic lives separately from this report.
"""

import os

from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Flowable, NextPageTemplate, PageBreak, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfbase.pdfmetrics import stringWidth

from . import pdf_forms as F
from .company_branding import resolve_rig_company_branding
from .pdf_reportlab import FONT, FONT_BOLD, PX, flow_text

SEVERITY_LABELS = {"H": "High", "M": "Medium", "L": "Low"}
# Same palette as SEVERITY_BADGE in IncidentDetailsListPage.jsx, so the
# printed report's severity colors match what the app itself shows.
SEVERITY_COLORS = {
    "H": {"fg": "#dc2626", "bg": "#fef2f2", "border": "#fecaca"},
    "M": {"fg": "#b45309", "bg": "#fffbeb", "border": "#fde68a"},
    "L": {"fg": "#059669", "bg": "#ecfdf5", "border": "#a7f3d0"},
}

# Mirrors frontend/src/routes/qhse/IncidentDetailsFormPage.jsx's own
# BELONGS_TO_OPTIONS — kept in sync manually, same as how severity labels
# are duplicated between the serializer and the frontend elsewhere in
# this app.
BELONGS_TO_LABELS = {
    "0": "TP Contractors",
    "1": "Operator Contractors",
    "2": "Operator",
    "10": "OGDSL",
    "30": "EOSL",
    "308": "StarBit",
    "309": "OGD-EHES JVPL",
    "316": "Seros",
}
CONTRACTOR_REQUIRED_THIRD_PARTY = {"0", "1"}


def _fmt_date(dt):
    return dt.strftime("%d/%m/%Y") if dt else ""


def _fmt_datetime(dt):
    if not dt:
        return ""
    return dt.strftime("%d/%m/%Y %H:%M")


def _belongs_to_display(incident):
    code = incident.third_party
    if not code:
        return ""
    if code in CONTRACTOR_REQUIRED_THIRD_PARTY:
        return incident.contractor.contractor_name if incident.contractor_id else ""
    return BELONGS_TO_LABELS.get(code, code)


def _designation_display(incident):
    if incident.rank_id:
        return incident.rank.rank_name
    return incident.rank_name or ""


def _probable_causes(incident):
    causes = []
    if incident.immediate_incident_cause_id:
        causes.append(incident.immediate_incident_cause.incident_cause_desc)
    if incident.immediate_incident_cause_2_id:
        causes.append(incident.immediate_incident_cause_2.incident_cause_desc)
    return causes


def _part_of_body_display(incident):
    parts = [
        p.part_of_body_name
        for p in [
            incident.part_of_body_1 if incident.part_of_body_1_id else None,
            incident.part_of_body_2 if incident.part_of_body_2_id else None,
            incident.part_of_body_3 if incident.part_of_body_3_id else None,
            incident.part_of_body_4 if incident.part_of_body_4_id else None,
        ]
        if p
    ]
    return ", ".join(parts)


def build_report_context(incident):
    branding = resolve_rig_company_branding(incident.rig_id, incident.incident_date.date())
    media_root = settings.MEDIA_ROOT

    def abs_path(rel_path):
        return os.path.join(media_root, rel_path) if rel_path else None

    # Prefer the bigger logo asset for a more prominent header; fall back
    # to the small one when a company's folder only has that.
    logo_path = abs_path(branding["big_logo_path"] or branding["small_logo_path"])

    return {
        "incident": incident,
        "rig_name": incident.rig.rig_name if incident.rig_id else (incident.unit_name or ""),
        "company_name": branding["company_name"] or "",
        "logo_path": logo_path,
        "incident_date_time": _fmt_datetime(incident.incident_date),
        "reported_date_time": _fmt_datetime(incident.incident_reported_dt),
        "report_date_time": _fmt_datetime(timezone.now()),
        "severity_label": SEVERITY_LABELS.get(incident.incident_severity, ""),
        "severity_potential_label": SEVERITY_LABELS.get(incident.incident_severity_potential, ""),
        "severity_colors": SEVERITY_COLORS.get(incident.incident_severity, SEVERITY_COLORS["L"]),
        "severity_potential_colors": SEVERITY_COLORS.get(incident.incident_severity_potential, SEVERITY_COLORS["L"]),
        "person_injured": incident.person_injured == "Y",
        "belongs_to_display": _belongs_to_display(incident),
        "designation_display": _designation_display(incident),
        "part_of_body_display": _part_of_body_display(incident),
        "probable_causes": _probable_causes(incident),
        "photos": [
            os.path.join(media_root, p.incident_photo_path)
            for p in incident.photos.all()
            if p.incident_photo_path
        ],
    }


# ── drawing (shared pieces live in pdf_forms.py) ─────────────────────────────

AMBER_TITLE, AMBER_BAR = colors.HexColor("#b45309"), colors.HexColor("#d97706")
AMBER_BG, AMBER_LINE = colors.HexColor("#fffbeb"), colors.HexColor("#fde68a")


class SeverityChip(Flowable):
    """Coloured pill for Actual / Potential severity."""

    def __init__(self, label, palette):
        super().__init__()
        self.label, self.palette = label, palette
        self.width = stringWidth(label, FONT_BOLD, 8.3) + 20 * PX
        self.height = 8.3 * 1.2 + 4 * PX

    def wrap(self, avail_w, avail_h):
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.setLineWidth(0.75)
        c.setStrokeColor(colors.HexColor(self.palette["border"]))
        c.setFillColor(colors.HexColor(self.palette["bg"]))
        c.roundRect(0.4, 0.4, self.width - 0.8, self.height - 0.8, 4 * PX, fill=1, stroke=1)
        c.setFillColor(colors.HexColor(self.palette["fg"]))
        c.setFont(FONT_BOLD, 8.3)
        c.drawString(10 * PX, (self.height - 8.3) / 2 + 8.3 * 0.22, self.label)


class NumberBox(Flowable):
    def __init__(self, n):
        super().__init__()
        self.n = str(n)
        self.size = 14 * PX

    def wrap(self, avail_w, avail_h):
        return self.size, self.size

    def draw(self):
        c = self.canv
        c.setFillColor(F.NAVY)
        c.roundRect(0, 0, self.size, self.size, 3 * PX, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont(FONT_BOLD, 7)
        c.drawCentredString(self.size / 2, self.size / 2 - 7 * 0.35, self.n)


def _chain(obj, *attrs):
    """Follows attributes, giving "" if any link is empty (like a template's silent lookup)."""
    for a in attrs:
        obj = getattr(obj, a, None) if obj is not None else None
    return obj or ""


def _number(value, empty):
    return str(value) if value else empty


def render_flash_report_pdf(incident):
    ctx = build_report_context(incident)
    st = F.base_styles()
    L = F.LABEL_LIGHT
    f = lambda label, value: F.field(st, label, value, L, grey_empty=True)
    number = incident.rig_incident_no or incident.incident_no
    meta = [("Incident No.", number, True), ("Rig / Unit", ctx["rig_name"], False), ("Report Date", ctx["report_date_time"], False)]

    def head(title):
        return F.header(st, ctx["company_name"], ctx["logo_path"], title, meta)

    keep = F.keep  # a section that doesn't fit in the space left moves whole to the next page

    # severity
    chips = []
    for text, label_, palette in (("Actual", ctx["severity_label"], ctx["severity_colors"]), ("Potential", ctx["severity_potential_label"], ctx["severity_potential_colors"])):
        chips.append(([F.label(text, L), Spacer(1, 3 * PX), SeverityChip(label_ or "—", palette)], stringWidth(label_ or "—", FONT_BOLD, 8.3) + 20 * PX))
    severity = Table([[c[0] for c in chips]], colWidths=[chips[0][1] + 28 * PX, chips[1][1]], hAlign="LEFT")
    severity.setStyle(TableStyle(F.plain() + [("VALIGN", (0, 0), (-1, -1), "TOP")]))

    # injury
    belongs = ctx["belongs_to_display"]
    if ctx["person_injured"]:
        injury = F.section(
            "Injury Details",
            [
                F.grid(
                    [
                        F.field(st, "Name", F.dash(incident.emp_name), L),
                        F.field(st, "Designation", F.dash(ctx["designation_display"]), L),
                        F.field(st, "Total Experience (Mths)", F.dash(incident.total_rig_exp_months), L),
                        F.field(st, "Belongs To", F.dash(belongs), L),
                        F.field(st, "Part(s) of Body Injured", F.dash(ctx["part_of_body_display"]), L),
                        "",
                    ],
                    3,
                    F.INNER,
                    spans=[(1, 1, 2)],
                )
            ],
            title_color=AMBER_TITLE,
            bar_color=AMBER_BAR,
            background=AMBER_BG,
            border=AMBER_LINE,
        )
    else:
        line = ParagraphStyle("noinj", fontName=FONT, fontSize=9, leading=11.5, textColor=F.MUTED)
        injury = F.section("Injury Details", [Paragraph(f"No person injured in this incident. Belongs To: <font name='{FONT_BOLD}' color='#111827'>{flow_text(F.dash(belongs))}</font>", line)])

    # causes
    cause_style = ParagraphStyle("cause", fontName=FONT, fontSize=8.8, leading=8.8 * 1.3, textColor=F.INK)
    causes = []
    for n, text in enumerate(ctx["probable_causes"], 1):
        row = Table([[NumberBox(n), Paragraph(flow_text(text), cause_style)]], colWidths=[14 * PX + 7 * PX, F.INNER - 21 * PX])
        row.setStyle(TableStyle(F.plain() + [("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * PX)]))
        causes.append(row)
    if not causes:
        causes.append(Paragraph("—", st["empty"]))
    if incident.immediate_cause_descr:
        causes += [Spacer(1, 8 * PX), F.label("Cause Description", L), Spacer(1, 0.75), Paragraph(flow_text(incident.immediate_cause_descr), st["value"])]

    cw3 = (F.INNER - 18 * PX * 2) / 3
    impact = lambda value, text: F.card(st, value, text, cw3, value_size=13, label_color=L)

    sections = [
        F.section(
            "Incident Overview",
            [
                F.grid(
                    [
                        f("Incident Dt/Time", ctx["incident_date_time"]),
                        f("Reported Dt/Time", ctx["reported_date_time"]),
                        f("Well No.", incident.well_no),
                        f("Country", _chain(incident, "country", "country_name")),
                        f("Operator", _chain(incident, "operator", "operator_name")),
                        f("Nature of Incident", _chain(incident, "incident_type", "incident_type")),
                    ],
                    3,
                    F.INNER,
                )
            ],
        ),
        F.section("Severity", [severity]),
        injury,
        F.section("Description of Incident", [Paragraph(flow_text(incident.incident_descr), st["value"])]),
        F.section("Probable Causes of Occurrence", causes),
        F.section(
            "Incident Context",
            [
                F.grid(
                    [
                        f("Operation at Time of Incident", _chain(incident, "rig_operation", "rig_operation_name")),
                        f("Location of Incident", _chain(incident, "work_location", "work_location")),
                        f("Type of Contact/Exposure", _chain(incident, "contact_expo_type", "contact_expo_type_name")),
                    ],
                    3,
                    F.INNER,
                )
            ],
        ),
        F.section(
            "Corrective & Preventive Action",
            [F.grid([f("Immediate Corrective Action", incident.corrective_action), f("Action Suggested to Prevent Recurrence", incident.preventive_action)], 2, F.INNER)],
        ),
        F.section(
            "Impact",
            [
                F.grid(
                    [
                        impact(_number(incident.npt_hrs_loss, "0.00"), "NPT Hours"),
                        impact(_number(incident.manhours_loss, "0.00"), "Manhours"),
                        impact("$" + _number(incident.financial_loss_amt, "0"), "Property Loss"),
                    ],
                    3,
                    F.INNER,
                )
            ],
        ),
    ]
    if incident.comments:
        sections.append(F.section("Comments", [Paragraph(flow_text(incident.comments), st["value"])]))
    reported = Table(
        [[F.field(st, "Reported By", F.dash(incident.reported_by), L), F.field(st, "Designation", F.dash(_chain(incident, "rptd_by_rank", "rank_name")), L, align="right")]],
        colWidths=[F.INNER / 2, F.INNER / 2],
    )
    reported.setStyle(TableStyle(F.plain() + [("TOPPADDING", (0, 0), (-1, -1), 4 * PX), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    sections.append(F.box([reported]))
    story = [keep(x) for x in sections]

    if ctx["photos"]:
        pw = (F.INNER + 28 * PX - 14 * PX) / 2
        story += [NextPageTemplate("photos"), PageBreak()]
        story.append(F.grid([[F.photo_card(st, p, pw, caption=f"Photo {n}")] for n, p in enumerate(ctx["photos"], 1)], 2, F.WIDTH, gap_x=14 * PX, gap_y=14 * PX))
    headers = {"main": head("Incident Flash Report")}
    if ctx["photos"]:
        headers["photos"] = head("Incident Photos")
    return F.build(story, f"Incident Flash Report {number}", headers)
