"""QHSE → HSE Drills / Exercises — the printable "Emergency Response Drill
Report" PDF, built to match the legacy sample (HSE Drill Details/
HSE_Drill_Record_Print.pdf) and drawn with ReportLab (pdf_reportlab.py).

The letterhead (company name + logo) is resolved per rig/drill-date via
company_branding.resolve_rig_company_branding — see that module's own
docstring and the project memory qhse_incident_report_dynamic_branding for
why that logic lives separately from this report, same reasoning as the
Incident Flash Report.

Drill Photos: a migrated row's drill_rec_photo_upload_path is a legacy-
format string (see HseDrillRecordPhotoUpload's own model docstring) that
won't resolve to a real file until the photo library is copied over and
its paths rewritten (scripts/fix_hse_drill_photo_paths.py). Rather than
silently dropping those rows from the printed report — which would make
it look like no photos were ever taken — every active row still gets a
tile; one with no resolvable file gets a placeholder box instead of an
<img>, same "Image not available" treatment as the Photos tab in the
frontend edit form (HseDrillRecordChildPanel.jsx)."""

import os

from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from . import pdf_forms as F
from .company_branding import resolve_rig_company_branding
from .pdf_reportlab import FONT, FONT_BOLD, PX, flow_text

MM_SS_FIELDS = [
    "initial_response_time",
    "fire_team_1_duration",
    "fire_team_2_duration",
    "snr_team_duration",
    "drill_muster",
    "abandon_muster_offshore",
    "total_time_of_drill",
]


def _fmt_mm_ss(value):
    """Decimal(4,2) packed MM.SS -> "M.SS min." display string, matching
    the sample report's own "3.00 min." / "13.00 min." formatting."""
    if value is None:
        return None
    return f"{value:.2f} min."


def _fmt_date(dt):
    return dt.strftime("%d/%m/%Y") if dt else ""


def _fmt_datetime(dt):
    if not dt:
        return ""
    return dt.strftime("%d/%m/%Y %H:%M")


def _type_of_drill_display(hdr):
    names = [hdr.hse_drill_1.hse_drill_name if hdr.hse_drill_1_id else None, hdr.hse_drill_2.hse_drill_name if hdr.hse_drill_2_id else None]
    names = [n for n in names if n]
    return " followed by ".join(names)


def build_report_context(hdr):
    branding = resolve_rig_company_branding(hdr.rig_id, hdr.drill_dt.date())
    media_root = settings.MEDIA_ROOT

    def abs_path(rel_path):
        return os.path.join(media_root, rel_path) if rel_path else None

    logo_path = abs_path(branding["big_logo_path"] or branding["small_logo_path"])

    photos = []
    for p in hdr.photo_uploads.filter(drill_rec_photo_active="Y").order_by("drill_rec_photo_upload_id"):
        candidate = os.path.join(media_root, p.drill_rec_photo_upload_path.lstrip("/")) if p.drill_rec_photo_upload_path else None
        available = bool(candidate and os.path.isfile(candidate))
        photos.append({"path": candidate if available else None, "available": available})

    durations = {field: _fmt_mm_ss(getattr(hdr, field)) for field in MM_SS_FIELDS}

    return {
        "hdr": hdr,
        "company_name": branding["company_name"] or "",
        "logo_path": logo_path,
        "rig_name": hdr.rig.rig_name if hdr.rig_id else "",
        "report_date_time": _fmt_datetime(timezone.now()),
        "drill_date_display": _fmt_date(hdr.drill_dt),
        "drill_time_display": hdr.drill_dt.strftime("%H:%M") if hdr.drill_dt else "",
        "type_of_drill_display": _type_of_drill_display(hdr),
        "initiated_by_display": " / ".join(
            filter(
                None,
                [str(hdr.initiated_by_fs_emp_1) if hdr.initiated_by_fs_emp_1_id else None, str(hdr.initiated_by_fs_emp_2) if hdr.initiated_by_fs_emp_2_id else None],
            )
        ),
        "approved_by_oim_display": str(hdr.approved_by_oim_fs_emp) if hdr.approved_by_oim_fs_emp_id else "",
        "control_room_display": "Yes" if hdr.control_room_on_shore == "Y" else "No",
        "durations": durations,
        "events": list(hdr.events.order_by("drill_rec_event_time")),
        "observations": list(hdr.observations.order_by("drill_rec_observation_id")),
        "improvements": list(hdr.improvements.order_by("drill_rec_improvement_id")),
        "corrective_actions": list(hdr.corrective_actions.order_by("drill_rec_corrective_action_id")),
        "photos": photos,
    }


# ── drawing (shared pieces live in pdf_forms.py) ─────────────────────────────

TH = ParagraphStyle("th", fontName=FONT_BOLD, fontSize=7, leading=8.4, textColor=F.LABEL)
EVENT = ParagraphStyle("event", fontName=FONT, fontSize=8.4, leading=10.5, textColor=F.INK)
EVENT_TIME = ParagraphStyle("event_time", parent=EVENT, textColor=F.MUTED)
SIGN_HEAD = ParagraphStyle("sign_head", fontName=FONT_BOLD, fontSize=7.6, leading=9, textColor=F.NAVY)
CAPTION = ParagraphStyle("caption", fontName=FONT, fontSize=7, leading=8.4, textColor=F.LABEL)


def _time(value):
    return value.strftime("%H:%M:%S") if hasattr(value, "strftime") else str(value or "")


def _events_table(events):
    data = [[Paragraph("TIME", TH), Paragraph("EVENT", TH)]]
    for e in events:
        data.append([Paragraph(_time(e.drill_rec_event_time), EVENT_TIME), Paragraph(flow_text(e.drill_rec_event_desc), EVENT)])
    t = Table(data, colWidths=[60 * PX, F.INNER - 60 * PX], repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, 0), 0.75, F.LINE),
                ("LINEBELOW", (0, 1), (-1, -1), 0.75, F.SOFT_LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 3 * PX),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * PX),
                ("LEFTPADDING", (0, 0), (-1, -1), 6 * PX),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6 * PX),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return t


def _sign_block(st, title, cells):
    """cells: three (value, caption); the Signature and Stamp cells are blank."""
    cw = F.WIDTH / 3
    row = []
    for value, caption in cells:
        para = Paragraph(flow_text(value) if value else "&nbsp;", st["value"])
        h = para.wrap(cw - 20 * PX, 1000)[1]
        cap = Table([[Paragraph(flow_text(caption.upper()), CAPTION)]], colWidths=[cw - 20 * PX])
        cap.setStyle(TableStyle(F.plain() + [("LINEABOVE", (0, 0), (-1, 0), 0.75, F.LINE), ("TOPPADDING", (0, 0), (-1, -1), 3 * PX)]))
        row.append([para, Spacer(1, max(0, 24 * PX - h) + 10 * PX), cap])
    data = ([[Paragraph(flow_text(title.upper()), SIGN_HEAD), "", ""]] if title else []) + [row]
    t = Table(data, colWidths=[cw] * 3)
    r = len(data) - 1
    style = [
        ("BOX", (0, 0), (-1, -1), 0.75, F.LINE),
        ("ROUNDEDCORNERS", [6 * PX] * 4),
        ("LEFTPADDING", (0, r), (-1, r), 10 * PX),
        ("RIGHTPADDING", (0, r), (-1, r), 10 * PX),
        ("TOPPADDING", (0, r), (-1, r), 10 * PX),
        ("BOTTOMPADDING", (0, r), (-1, r), 10 * PX),
        ("LINEBEFORE", (1, r), (2, r), 0.75, F.LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    if title:
        style += [("SPAN", (0, 0), (2, 0)), ("BACKGROUND", (0, 0), (2, 0), F.CARD_BG), ("LINEBELOW", (0, 0), (2, 0), 0.75, F.LINE), ("TOPPADDING", (0, 0), (-1, 0), 6 * PX), ("BOTTOMPADDING", (0, 0), (-1, 0), 6 * PX), ("LEFTPADDING", (0, 0), (-1, 0), 10 * PX)]
    t.setStyle(TableStyle(style))
    return t


def render_hse_drill_record_pdf(hdr):
    ctx = build_report_context(hdr)
    st = F.base_styles()
    f = lambda label, value: F.field(st, label, value)
    d = ctx["durations"]
    meta = [("Report No.", hdr.drill_record_no, True), ("Rig", ctx["rig_name"], False), ("Report Date", ctx["report_date_time"], False)]
    header = F.header(st, ctx["company_name"], ctx["logo_path"], "Emergency Response Drill Report", meta)
    cw4 = (F.INNER - 18 * PX * 3) / 4
    metric = lambda key, label: F.card(st, F.dash(d[key]), label, cw4)

    # Every section is kept whole: one that doesn't fit in the space left moves to
    # the next page (under the same header) instead of being cut off, and the next
    # section follows straight on, with no forced page break and no blank gap.
    story = [
        F.keep(
            F.section(
                "Drill / Exercise Record",
                [
                    F.grid(
                        [
                            f("Date & Location", f"{ctx['drill_date_display']} — {F.dash(hdr.drill_location)}"),
                            f("Time", ctx["drill_time_display"]),
                            f("Type of Drilling, Training", ctx["type_of_drill_display"] or "—"),
                            f("Head Count", F.dash(hdr.head_count)),
                        ],
                        2,
                        F.INNER,
                    )
                ],
            )
        ),
        F.keep(F.section("Chronological Order of Events during the Drill", [_events_table(ctx["events"]) if ctx["events"] else Paragraph("No events recorded.", st["empty"])])),
        F.keep(F.section("Observation during the Drill / Exercise", F.bullets(st, [o.drill_rec_observation_desc for o in ctx["observations"]]))),
        F.keep(F.section("Areas of Improvement & Lessons Learnt", F.bullets(st, [i.drill_rec_improvement_desc for i in ctx["improvements"]]))),
        F.keep(F.section("Corrective Action Taken", F.bullets(st, [c.drill_rec_corrective_action_desc for c in ctx["corrective_actions"]]))),
        F.keep(
            F.section(
                "Drill Summary",
                [
                    F.grid(
                        [
                            f("Initiated By", ctx["initiated_by_display"]),
                            f("Initial Response Time", d["initial_response_time"]),
                            f("No. of Participants", F.dash(hdr.no_of_participants)),
                            f("Control Room (Offshore)", ctx["control_room_display"]),
                            f("Fire Team #1 Size", F.dash(hdr.fire_team_1_size)),
                            f("Fire Team #2 Size", F.dash(hdr.fire_team_2_size)),
                            f("Stretcher Team Size", F.dash(hdr.stretcher_team_size)),
                            f("Maintenance Team Size", F.dash(hdr.maintenance_team_size)),
                            f("S&R Team Size", F.dash(hdr.snr_team_size)),
                        ],
                        3,
                        F.INNER,
                    ),
                    Spacer(1, 8 * PX),
                    F.grid(
                        [
                            metric("fire_team_1_duration", "Fire Team #1 Duration"),
                            metric("fire_team_2_duration", "Fire Team #2 Duration"),
                            metric("snr_team_duration", "S&R Duration"),
                            metric("drill_muster", "Drill Muster"),
                            metric("abandon_muster_offshore", "Abandon Muster (Offshore)"),
                            metric("total_time_of_drill", "Total Time of Drill"),
                        ],
                        4,
                        F.INNER,
                    ),
                ],
            )
        ),
        F.keep(
            _sign_block(st, "Approved By", [(ctx["approved_by_oim_display"], "PIC / OIM — Name"), ("", "Signature"), ("", "Stamp")]),
            Spacer(1, 8 * PX),
            _sign_block(st, None, [(hdr.approved_by_companyman, "Company Man — Name"), ("", "Signature"), ("", "Stamp")]),
            after=8 * PX,
        ),
    ]
    if ctx["photos"]:
        pw = (F.INNER - 10 * PX * 2) / 3
        story.append(F.keep(F.section("Drill Photos", [Spacer(1, 5 * PX), F.grid([[F.photo_card(st, p["path"], pw)] for p in ctx["photos"]], 3, F.INNER, gap_x=10 * PX, gap_y=10 * PX)])))
    return F.build(story, f"Drill Report {hdr.drill_record_no}", {"main": header})
