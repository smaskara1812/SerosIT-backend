"""QHSE Incident Flash Report — a 2-page PDF built to match the mentor-
supplied blank template ("Incident flush report blank template.pdf"),
rendered with WeasyPrint from a Django template.

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
from zoneinfo import ZoneInfo

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

from .company_branding import resolve_rig_company_branding

# The app's TIME_ZONE setting is UTC (for storage consistency), but every
# rig/incident in this data is India-based, so the printed report always
# converts to IST regardless of the server's own configured timezone.
IST = ZoneInfo("Asia/Kolkata")

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
    # incident_date/incident_reported_dt are stored timezone-aware (UTC) —
    # convert to IST before formatting so the report doesn't print UTC
    # times (see IST comment above; Django's own TIME_ZONE is UTC, so
    # timezone.localtime() alone would be a no-op here).
    if not dt:
        return ""
    if timezone.is_aware(dt):
        dt = dt.astimezone(IST)
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


def render_flash_report_pdf(incident):
    from weasyprint import HTML

    ctx = build_report_context(incident)
    html = render_to_string("core/incident_flash_report.html", ctx)
    return HTML(string=html, base_url=str(settings.MEDIA_ROOT)).write_pdf()
