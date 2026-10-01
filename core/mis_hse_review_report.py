"""PDF render for QHSE → Monthly HSE Review — same WeasyPrint pipeline as
every other report in this app (see incident_register_report.py)."""

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

from .company_branding import seros_logo_path


def render_mis_hse_review_pdf(report):
    from weasyprint import HTML

    context = {
        "logo_path": seros_logo_path(),
        "generated_at": timezone.now().strftime("%d/%m/%Y %H:%M"),
        "report": report,
        "scope_label": report["project_label"] if report["filter_type"] == "PROJECT" else "SEROS (All Rigs)",
    }
    html = render_to_string("core/mis_hse_review_report.html", context)
    return HTML(string=html, base_url=str(settings.MEDIA_ROOT)).write_pdf()
