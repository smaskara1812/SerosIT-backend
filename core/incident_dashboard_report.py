"""Incident Dashboard — Print PDF for one drill-down's record list. Same
WeasyPrint pipeline as incident_register_report.py (render_to_string ->
weasyprint.HTML(string=...).write_pdf()), generic over columns/rows since
the Incident Dashboard's drill-down shape varies by dimension (plain
incidents vs. Incident Actions vs. Other QHSE Actions — see
DRILLDOWN_PDF_COLUMNS in incident_dashboard.py).
"""

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

PRINT_ROW_LIMIT = 2000


def _fmt_cell(v):
    import datetime

    if isinstance(v, datetime.datetime):
        return v.strftime("%d/%m/%Y %H:%M")
    if isinstance(v, datetime.date):
        return v.strftime("%d/%m/%Y")
    return v if v not in (None, "") else "—"


def render_drilldown_pdf(title, summary_lines, columns, rows):
    from weasyprint import HTML

    total = len(rows)
    shown_rows = rows[:PRINT_ROW_LIMIT]
    context = {
        "title": title,
        "summary_lines": summary_lines,
        "columns": columns,
        "rows": [[_fmt_cell(v) for v in row] for row in shown_rows],
        "generated_at": timezone.now().strftime("%d/%m/%Y %H:%M"),
        "total": total,
        "shown": len(shown_rows),
        "truncated": total > PRINT_ROW_LIMIT,
    }
    html = render_to_string("core/incident_dashboard_drilldown_report.html", context)
    return HTML(string=html, base_url=str(settings.MEDIA_ROOT)).write_pdf()
