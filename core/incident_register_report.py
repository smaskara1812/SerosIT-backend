"""QHSE Incident Register — printable PDF, rendered with WeasyPrint from a
Django template (same pipeline as incident_flash_report.py's per-incident
Flash Report — see that module for the established pattern this mirrors:
render_to_string -> weasyprint.HTML(string=...).write_pdf()).

Unlike the Flash Report (one incident, full detail, per-rig letterhead),
this is a plain listing report — whatever rows the current filter bar
matches, landscape, one row per incident — so it carries no dynamic
company branding of its own.
"""

from zoneinfo import ZoneInfo

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

# Same reasoning as incident_flash_report.py: storage is UTC, but every
# rig/incident in this data is India-based, so the printed report always
# shows IST regardless of the server's own configured timezone.
IST = ZoneInfo("Asia/Kolkata")

# A PDF this deep would be slow to render and unwieldy to print — the
# on-screen list already paginates, so Print is meant for "this filtered
# slice", not "dump the whole table". Rows beyond this are silently
# dropped with a note on the report itself, matching how a very large
# result set already isn't a realistic printing use case.
PRINT_ROW_LIMIT = 2000


def _fmt_dt(dt):
    if not dt:
        return ""
    if timezone.is_aware(dt):
        dt = dt.astimezone(IST)
    return dt.strftime("%d/%m/%Y %H:%M")


def render_incident_register_pdf(queryset, filter_summary):
    from weasyprint import HTML

    total = queryset.count()
    incidents = list(queryset[:PRINT_ROW_LIMIT])

    context = {
        "rows": [
            {
                "sr_no": i + 1,
                "rig_name": r.rig.rig_name if r.rig_id else "Unknown",
                "rig_incident_no": r.rig_incident_no or "",
                "incident_date": _fmt_dt(r.incident_date),
                "incident_type_abrv": r.incident_type.incident_abrv if r.incident_type_id else "",
                "incident_descr": r.incident_descr,
            }
            for i, r in enumerate(incidents)
        ],
        "filter_summary": filter_summary,
        "generated_at": _fmt_dt(timezone.now()),
        "total": total,
        "shown": len(incidents),
        "truncated": total > PRINT_ROW_LIMIT,
    }
    html = render_to_string("core/incident_register_report.html", context)
    return HTML(string=html, base_url=str(settings.MEDIA_ROOT)).write_pdf()
