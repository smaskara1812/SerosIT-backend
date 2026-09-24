"""Light HTML templates for approval-notification mail.

Built against a real legacy sample mail (a bordered Rig/Date/User table
under a centered heading + status line, with an automated-mail footer) —
kept close to that shape for familiarity, but not a pixel-for-pixel replica:
a per-event status line, and a Revision Note row when one exists, are new.
"""

from html import escape

from .models import MailRecipientMapping

_EVENT_TEXT = {
    MailRecipientMapping.EVENT_FINALIZE: ("Daily report has been submitted", "Pending L1 Approval"),
    MailRecipientMapping.EVENT_APPROVE: ("Daily report has been approved", "Approved"),
    MailRecipientMapping.EVENT_REJECT: ("Daily report has been rejected", "Rejected"),
    MailRecipientMapping.EVENT_REVISE_PREVIOUS: ("Daily report sent back for revision", "Sent for Revision"),
}


def _actor_name(user):
    """Full name via the linked employee record (matches the legacy
    sample's "Ranvir Singh", not a raw login id) — falls back to the login
    id for a user with no employee record linked."""
    if user is None:
        return ""
    if user.emp_id:
        name = " ".join(p for p in (user.emp.emp_fname, user.emp.emp_sname) if p)
        if name:
            return name
    return user.user_login_id


def drilling_report_mail(instance, actor, event_type):
    """Returns (subject, html_body) for one Drilling Report notification."""
    heading, status = _EVENT_TEXT.get(event_type, (event_type.replace("_", " ").title(), ""))
    rig_no_spaces = instance.rig.rig_name.replace(" ", "")
    subject = f"Drilling Daily Report : : {rig_no_spaces}-{instance.drilling_dtl_dt.strftime('%d-%m-%Y')}"

    rows = [
        ("Rig", instance.rig.rig_name),
        ("Drilling Date", instance.drilling_dtl_dt.strftime("%d/%m/%Y")),
        ("Action By", _actor_name(actor)),
    ]
    if event_type == MailRecipientMapping.EVENT_REVISE_PREVIOUS and instance.revision_note:
        rows.append(("Revision Note", instance.revision_note))

    # Rig name and Revision Note both ultimately come from free-text fields
    # someone typed (a rig's own name, an approver's revision note) — escape
    # every row value before it reaches the HTML, or a note containing
    # "<script>..." would inject straight into a real outgoing email.
    rows_html = "".join(
        "<tr>"
        f'<td style="padding:6px 12px;border:1px solid #ccc;font-weight:bold;background:#f5f5f5;white-space:nowrap;">{escape(str(label))}</td>'
        f'<td style="padding:6px 12px;border:1px solid #ccc;">{escape(str(value))}</td>'
        "</tr>"
        for label, value in rows
    )
    status_html = f'<p style="text-align:center;font-weight:bold;font-size:14px;margin:0 0 16px;">{status}</p>' if status else ""

    body = f"""<div style="font-family:Georgia,'Times New Roman',serif;color:#222;">
  <p style="text-align:center;font-weight:bold;font-size:16px;margin:16px 0 4px;">{heading}</p>
  {status_html}
  <table style="border-collapse:collapse;margin:0 auto;">{rows_html}</table>
  <p style="text-align:center;color:#666;font-size:12px;margin-top:24px;">
    * <strong>This is an automated mail. Please do not reply.</strong><br>
    This message was sent automatically by SerosIT.
  </p>
</div>"""
    return subject, body


def incident_created_mail(instance):
    """Returns (subject, html_body) for the QHSE Incident Details 'notify
    on create' mail (NotificationTrigger entity_key
    'qhse.incident_details' / action 'create', pointed at Mail_Alert_Dtl's
    Alert_Id 240 — 'Incident Report Added'). Same bordered-table shape as
    drilling_report_mail, matching the legacy sample mail's own "A New
    Incident has been Recorded" layout rather than a pixel replica."""
    rig_name = instance.rig.rig_name if instance.rig_id else (instance.unit_name or "")
    subject = "Incident Report Added"

    rows = [
        ("Rig Incident No.", instance.rig_incident_no or ""),
        ("Incident Date/Time", instance.incident_date.strftime("%d/%m/%Y %H:%M")),
        ("Nature of Incident", instance.incident_type.incident_type),
        ("Rig", rig_name),
        ("Well No.", instance.well_no or ""),
        ("Reported By", instance.reported_by or ""),
    ]
    rows_html = "".join(
        "<tr>"
        f'<td style="padding:6px 12px;border:1px solid #ccc;font-weight:bold;background:#f5f5f5;white-space:nowrap;">{escape(str(label))}</td>'
        f'<td style="padding:6px 12px;border:1px solid #ccc;">{escape(str(value))}</td>'
        "</tr>"
        for label, value in rows
    )

    body = f"""<div style="font-family:Georgia,'Times New Roman',serif;color:#222;">
  <p style="text-align:center;font-weight:bold;font-size:16px;margin:16px 0 4px;">A New Incident has been Recorded</p>
  <table style="border-collapse:collapse;margin:0 auto;">{rows_html}</table>
  <p style="text-align:center;color:#666;font-size:12px;margin-top:24px;">
    * <strong>This is an automated mail. Please do not reply.</strong><br>
    This message was sent automatically by SerosIT.
  </p>
</div>"""
    return subject, body
