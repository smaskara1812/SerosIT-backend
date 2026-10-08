"""QHSE Incident Register — printable PDF, drawn with ReportLab
(pdf_reportlab.render_table_report).

Unlike the Flash Report (one incident, full detail, per-rig letterhead),
this is a plain listing report — whatever rows the current filter bar
matches, landscape, one row per incident — so it carries no dynamic
company branding of its own.
"""

from django.utils import timezone

from .company_branding import seros_logo_path
from .pdf_reportlab import render_table_report

# A PDF this deep would be slow to render and unwieldy to print — the
# on-screen list already paginates, so Print is meant for "this filtered
# slice", not "dump the whole table". Rows beyond this are silently
# dropped with a note on the report itself, matching how a very large
# result set already isn't a realistic printing use case.
PRINT_ROW_LIMIT = 2000


def _fmt_dt(dt):
    if not dt:
        return ""
    return dt.strftime("%d/%m/%Y %H:%M")


def render_incident_register_pdf(queryset, filter_summary):
    total = queryset.count()
    incidents = list(queryset[:PRINT_ROW_LIMIT])
    rows = [
        [
            i + 1,
            r.rig.rig_name if r.rig_id else "Unknown",
            r.rig_incident_no or "—",
            _fmt_dt(r.incident_date),
            (r.incident_type.incident_abrv if r.incident_type_id else "") or "—",
            r.incident_descr,
        ]
        for i, r in enumerate(incidents)
    ]
    return render_table_report(
        title="Incident Register",
        logo_path=seros_logo_path(),
        meta=[
            [("Generated ", False), (_fmt_dt(timezone.now()), True)],
            [("Total ", False), (str(total), True), (f" incident{'' if total == 1 else 's'}", False)],
        ],
        body_chips=[filter_summary],
        note=f"Showing the first {len(incidents)} of {total} matching incidents — narrow the filters to print the rest." if total > PRINT_ROW_LIMIT else None,
        columns=[
            {"label": "Sr.No.", "width": 54, "align": "right"},
            {"label": "Rig", "width": 110},
            {"label": "Incident No.", "width": 80},
            {"label": "Date & Time", "width": 110},
            {"label": "Type", "width": 60},
            {"label": "Brief Description of Incident", "width": None},
        ],
        rows=rows,
        empty_text="No incidents match the current filters.",
    )
