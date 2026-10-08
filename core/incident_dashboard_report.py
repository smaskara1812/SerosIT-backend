"""Incident Dashboard — Print PDF for one drill-down's record list. Same
ReportLab table report as incident_register_report.py, generic over columns/rows since
the Incident Dashboard's drill-down shape varies by dimension (plain
incidents vs. Incident Actions vs. Other QHSE Actions — see
DRILLDOWN_PDF_COLUMNS in incident_dashboard.py).
"""

from django.utils import timezone

from .company_branding import seros_logo_path
from .pdf_reportlab import auto_columns, render_table_report

PRINT_ROW_LIMIT = 2000


def _fmt_cell(v):
    import datetime

    if isinstance(v, datetime.datetime):
        return v.strftime("%d/%m/%Y %H:%M")
    if isinstance(v, datetime.date):
        return v.strftime("%d/%m/%Y")
    return v if v not in (None, "") else "—"


def render_drilldown_pdf(title, summary_lines, columns, rows):
    total = len(rows)
    shown_rows = [[_fmt_cell(v) for v in row] for row in rows[:PRINT_ROW_LIMIT]]
    return render_table_report(
        title=title,
        subtitle="Incident Dashboard — drill-down record list",
        logo_path=seros_logo_path(),
        header_chips=summary_lines,
        meta=[
            [("Generated ", False), (timezone.now().strftime("%d/%m/%Y %H:%M"), True)],
            [("Total ", False), (str(total), True), (f" record{'' if total == 1 else 's'}", False)],
        ],
        note=f"Showing the first {len(shown_rows)} of {total} matching records." if total > PRINT_ROW_LIMIT else None,
        columns=auto_columns(columns, shown_rows, 841.89 - 24 * 72 / 25.4),
        rows=shown_rows,
        top_margin_mm=30,
    )
