"""The Activity Monitor mail: the rig activities and inspections that are not completed and are due within the alert's Window (days) or already
overdue, sent on the alert's cycle (core/report_job.py). The mail body is a small table of COUNTS, a row for each rig with its overdue activities and
those due within the window; the full list, one row per activity, is the attached Excel file. A port of the legacy alert 58 ("Activity Monitor - EOSL",
RigActivityMonitor in the legacy mail service, which put every activity in the mail body), with these differences, all agreed:
  * the body shows counts per rig (overdue, due within the window, total) and the activities are in the Excel, which says for each whether it is overdue
    (by how many days), due today or due in N days, with overdue rows marked;
  * when nothing is due the mail says so once, instead of printing the empty-state line and then "Nil"; an empty Activity Monitor gives the same mail
    (the legacy code sent a mail with no body);
  * the wording says "Seros-IT" where the legacy mail said "S.I.S.";
  * a failure is retried and reported by e-mail to SCHEDULER_ERROR_MAIL_TO (core/error_mail.py).
Which rows: Activity Monitor rows with no completion date and a scheduled date on or before today + Window. There is no lower limit, as before: an
activity that was due long ago and never closed stays in the mail until it is."""

import datetime
import html
import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .models import ActivityMonitor
from .report_job import ReportMail, ScheduledReportJob

JOB_KEY = "activity_monitor"
ENTITY_KEY = "automation"
ACTION = "send_activity_monitor_mail"
TRIGGER_CODE = "auto.activity_monitor"
ALERT_NAME = "Activity Monitor - EOSL"  # what the setup command looks for when it is not told an alert id
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
NATURE = {"M": "Mandatory", "N": "Non Mandatory"}
NO_RIG = "Office / Port"
HEADERS = ["Sr.No.", "Rig", "Activity", "Activity Nature", "Planning Remark", "Due On", "Status"]
WIDTHS = {"Sr.No.": 7, "Rig": 18, "Activity": 40, "Activity Nature": 16, "Planning Remark": 32, "Due On": 12, "Status": 20}
RED = "FDE8E8"


def status_text(due, today):
    days = (due - today).days
    if days < 0:
        return f"Overdue by {-days} day{'s' if days != -1 else ''}"
    if days == 0:
        return "Due today"
    return f"Due in {days} day{'s' if days != 1 else ''}"


def collect(window_days, today):
    """The open monitor rows due within the window or overdue, as dicts, by rig (the rig-less ones last), then oldest first."""
    limit = today + datetime.timedelta(days=max(0, int(window_days or 0)))
    qs = ActivityMonitor.objects.filter(completion_dt__isnull=True, scheduled_dt__lte=limit).select_related("activity", "rig")
    rows = [
        {
            "activity": m.activity.activity_name, "nature": NATURE.get(m.activity.activity_nature, m.activity.activity_nature or ""),
            "rig": m.rig.rig_name if m.rig_id else NO_RIG, "remark": (m.planning_remark or "").strip(), "due": m.scheduled_dt,
            "status": status_text(m.scheduled_dt, today), "overdue": m.scheduled_dt < today, "id": m.activity_monitor_id,
        }
        for m in qs
    ]
    rows.sort(key=lambda r: (r["rig"] == NO_RIG, r["rig"].lower(), r["due"], r["activity"].lower(), r["id"]))
    return rows


def by_rig(rows):
    """[(rig, overdue, upcoming)] in the same order as the rows."""
    out = {}
    for r in rows:
        o = out.setdefault(r["rig"], [0, 0])
        o[0 if r["overdue"] else 1] += 1
    return [(rig, o, u) for rig, (o, u) in out.items()]


def build_workbook(rows, window, today):
    """The Excel bytes: a Summary sheet (the counts per rig, as in the mail) and a Details sheet with one row per activity."""
    wb = Workbook()
    thin = Side(style="thin")
    box = Border(left=thin, right=thin, top=thin, bottom=thin)
    head_fill = PatternFill("solid", fgColor="D3D3D3")

    def header(ws, row, labels):
        for i, h in enumerate(labels, start=1):
            c = ws.cell(row=row, column=i, value=h)
            c.font, c.fill, c.border, c.alignment = Font(bold=True), head_fill, box, Alignment(horizontal="center")

    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = "Activity Monitor"
    ws["A1"].font = Font(name="Arial", size=15)
    ws["A2"] = f"Seros-IT Report Date: {today:%d-%m-%Y}"
    ws["A3"] = f"Not completed, and overdue or due within {window} days."
    labels = ["Rig", "Overdue", f"Due in next {window} days", "Total"]
    header(ws, 5, labels)
    r, tot_o, tot_u = 6, 0, 0
    for rig, o, u in by_rig(rows):
        for i, v in enumerate([rig, o, u, o + u], start=1):
            c = ws.cell(row=r, column=i, value=v)
            c.border = box
            if i > 1:
                c.alignment = Alignment(horizontal="center")
        if o:
            ws.cell(row=r, column=2).fill = PatternFill("solid", fgColor=RED)
        tot_o, tot_u, r = tot_o + o, tot_u + u, r + 1
    for i, v in enumerate(["Total", tot_o, tot_u, tot_o + tot_u], start=1):
        c = ws.cell(row=r, column=i, value=v)
        c.font, c.border = Font(bold=True), box
        if i > 1:
            c.alignment = Alignment(horizontal="center")
    for col, w in zip("ABCD", (24, 12, 24, 10)):
        ws.column_dimensions[col].width = w

    wd = wb.create_sheet("Details")
    header(wd, 1, HEADERS)
    for n, row in enumerate(rows, start=1):
        for i, v in enumerate([n, row["rig"], row["activity"], row["nature"], row["remark"], row["due"], row["status"]], start=1):
            c = wd.cell(row=n + 1, column=i, value=v)
            c.border, c.alignment = box, Alignment(vertical="top", wrap_text=True)
            if i == 6:
                c.number_format = "DD/MM/YYYY"
            if row["overdue"]:
                c.fill = PatternFill("solid", fgColor=RED)
    for i, h in enumerate(HEADERS, start=1):
        wd.column_dimensions[get_column_letter(i)].width = WIDTHS[h]
    wd.freeze_panes = "A2"
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _page(inner):
    return (
        "<div style=\"font-family:Verdana,Tahoma,Arial,sans-serif;font-size:13px\">"
        "<p style=\"color:#e00707;margin:0 0 4px\">Seros-IT Auto Alert</p>"
        f"{inner}"
        "<p style=\"margin:28px 0 0\">This is an automated Mail. Please do not reply.</p></div>"
    )


def _counts_table(groups, window):
    th = "padding:5px 10px;border:1px solid #104a7b;background:#0715cd;color:#ffffff"
    head = f"<td style=\"{th};text-align:left\">Rig</td>" + "".join(f"<td style=\"{th};text-align:center\">{h}</td>" for h in ("Overdue", f"Due in next {window} days", "Total"))
    body, tot_o, tot_u = [], 0, 0
    for rig, o, u in groups:
        cell = "padding:4px 10px;border:1px solid #104a7b;text-align:center;background:#F7F8E0"
        red = f"{cell};background:#fde8e8;color:#b00020;font-weight:bold" if o else cell
        body.append(f"<tr><td style=\"padding:4px 10px;border:1px solid #104a7b;background:#F7F8E0\">{html.escape(rig)}</td><td style=\"{red}\">{o}</td><td style=\"{cell}\">{u}</td><td style=\"{cell}\">{o + u}</td></tr>")
        tot_o, tot_u = tot_o + o, tot_u + u
    tot = "padding:4px 10px;border:1px solid #104a7b;text-align:center;font-weight:bold"
    body.append(f"<tr><td style=\"{tot};text-align:left\">Total</td><td style=\"{tot}\">{tot_o}</td><td style=\"{tot}\">{tot_u}</td><td style=\"{tot}\">{tot_o + tot_u}</td></tr>")
    return f"<table cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse:collapse\"><tr>{head}</tr>{''.join(body)}</table>"


def build_mail(alert, now):
    """-> ReportMail for the alert (its Window gives how many days ahead to look, its Mail Subject the subject)."""
    window = max(0, int(alert.alert_window or 0))
    today = now.date()
    rows = collect(window, today)
    subject = (alert.mail_subject or "Seros-IT Auto Report - Activity Monitor").strip()
    if not rows:
        line = f"There are no rig activities due in the next {window} days, and none overdue."
        return ReportMail(subject, _page(f"<p style=\"color:#0715cd;margin:0 0 14px\">{line}</p>"), line, [], True, "Nothing due")
    groups = by_rig(rows)
    overdue = sum(g[1] for g in groups)
    upcoming = len(rows) - overdue
    counts = f"{overdue} overdue, {upcoming} due in the next {window} days"
    inner = (
        f"<p style=\"color:#0715cd;margin:0 0 14px\">Rig activities that are overdue or due in the next {window} days.</p>"
        "<p>Please ensure that all upcoming Inspections/Activities have been accounted for. The full list is in the attached Excel file.</p>"
        f"{_counts_table(groups, window)}"
    )
    text = f"Rig activities that are overdue or due in the next {window} days ({counts}). The full list is in the attached Excel file.\n" + "\n".join(
        f"{rig}: {o} overdue, {u} due in the next {window} days" for rig, o, u in groups
    )
    name = f"Activity_Monitor_{now:%d_%m_%Y_%H%M%S}.xlsx"
    return ReportMail(subject, _page(inner), text, [(name, build_workbook(rows, window, today), XLSX)], False, f"{len(rows)} activities in {len(groups)} rigs: {counts}")


class ActivityMonitorJob(ScheduledReportJob):
    key = JOB_KEY
    name = "Activity Monitor"
    report_name = "Activity Monitor"
    description = "The rig activities and inspections that are not completed and are due within the alert's Window, or already overdue: counts per rig in the mail, the full list as an Excel file."
    trigger_entity = ENTITY_KEY
    trigger_action = ACTION
    trigger_code = TRIGGER_CODE

    def build(self, alert, now):
        return build_mail(alert, now)


JOB = ActivityMonitorJob()


def ensure_setup(alert_id=None, alert_name=ALERT_NAME):
    """Creates the scheduler's job row and, when the alert can be found (by id, else by name), the trigger row that connects the mail to it. Safe to run
    again. Returns what it did, as a list of words."""
    from django.utils import timezone

    from .models import MailAlertDtl, NotificationTrigger, SchedJob

    did = []
    SchedJob.objects.get_or_create(job_key=JOB_KEY, defaults={"name": JOB.name, "enabled": "Y"})
    if NotificationTrigger.objects.filter(entity_key=ENTITY_KEY, action=ACTION).exists():
        return did
    alert = MailAlertDtl.objects.filter(pk=alert_id).first() if alert_id else MailAlertDtl.objects.filter(alert_name__iexact=alert_name).order_by("alert_id").first()
    if alert is None:
        return did
    NotificationTrigger.objects.create(entity_key=ENTITY_KEY, action=ACTION, alert=alert, notification_trigger_active="Y", cr_user_id=0, cr_dt=timezone.now())
    did.append(f"trigger row created for alert {alert.alert_id} ({alert.alert_name})")
    return did
