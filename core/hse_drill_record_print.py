"""QHSE → HSE Drills / Exercises — the printable "Emergency Response Drill
Report" PDF, built to match the legacy sample (HSE Drill Details/
HSE_Drill_Record_Print.pdf) and rendered with WeasyPrint from a Django
template, same approach as incident_flash_report.py.

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
from django.template.loader import render_to_string
from django.utils import timezone

from .company_branding import resolve_rig_company_branding

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


def render_hse_drill_record_pdf(hdr):
    from weasyprint import HTML

    ctx = build_report_context(hdr)
    html = render_to_string("core/hse_drill_record_print.html", ctx)
    return HTML(string=html, base_url=str(settings.MEDIA_ROOT)).write_pdf()
