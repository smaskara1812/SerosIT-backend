"""The Open Incident Actions mail: every incident action that is not closed, counted per rig or unit in the mail and listed in full in an attached Excel
file, sent on the alert's cycle (core/report_job.py). A port of the legacy alert 141 ("Open Incident Actions", Open_Incident_Actions in the legacy mail
service with Prc_Qry_Incident_Actions 'Alert', which put every action in the mail body), with these differences, all agreed:
  * the body is a table of counts per rig or unit (overdue, not yet due, total) and the actions are in the Excel, with overdue rows marked;
  * the legacy text said "overdue" but listed every open action, and showed the overdue days only for the late ones; the mail now says "open", and the
    Excel gives every action a status: overdue by N days, due today, due in N days, or Immediate when it has no target date;
  * actions and incidents marked as deleted are left out (the legacy procedure had no such column);
  * when nothing is open the mail says so once, instead of printing the empty-state line and then "Nil";
  * the wording says "Seros-IT" where the legacy mail said "S.I.S.";
  * a failure is retried and reported by e-mail to SCHEDULER_ERROR_MAIL_TO (core/error_mail.py).
Which rows: incident actions whose status is not Closed (Open and In Process), on incidents and actions not marked as deleted. The alert's Window is not
used (it is 0 on the alert, as in the legacy data). An action with no target date counts as overdue, measured from the incident date, as before."""

import datetime
import html
import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .models import IncidentAction
from .report_job import ReportMail, ScheduledReportJob

JOB_KEY = "incident_actions"
ENTITY_KEY = "automation"
ACTION = "send_open_incident_actions_mail"
TRIGGER_CODE = "auto.open_incident_actions"
ALERT_NAME = "Open Incident Actions"  # what the setup command looks for when it is not told an alert id
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
STATUS = {"OP": "Open", "IN": "In Process"}
NO_RIG = "(no rig or unit)"
HEADERS = ["Sr.No.", "Rig / Unit", "Incident No.", "Incident Date", "Recommendation", "Action Taken", "Action Party", "Status", "Target Date", "Due"]
WIDTHS = {"Sr.No.": 7, "Rig / Unit": 18, "Incident No.": 16, "Incident Date": 13, "Recommendation": 50, "Action Taken": 30, "Action Party": 20, "Status": 12, "Target Date": 13, "Due": 26}
RED = "FDE8E8"


def due_text(target, incident_day, today):
    """(text, overdue) for an action: against its target date, or, with none, 'Immediate' and measured from the incident date."""
    if target is None:
        days = (today - incident_day).days
        return f"Immediate (open {days} days since the incident)" if days > 0 else "Immediate", True
    days = (target - today).days
    if days < 0:
        return f"Overdue by {-days} day{'s' if days != -1 else ''}", True
    if days == 0:
        return "Due today", False
    return f"Due in {days} day{'s' if days != 1 else ''}", False


def collect(today):
    """The open actions as dicts, by rig or unit, then by target date (none first, they are the most urgent), then incident number."""
    qs = (
        IncidentAction.objects.exclude(action_status="CL").exclude(marked_as_deleted="Y").exclude(incident__marked_as_deleted="Y")
        .select_related("incident", "incident__rig")
    )
    rows = []
    for a in qs:
        inc = a.incident
        rig = (inc.rig.rig_name if inc.rig_id else (inc.unit_name or "").strip()) or NO_RIG
        day = inc.incident_date.date()
        text, overdue = due_text(a.target_date, day, today)
        rows.append({
            "rig": rig, "incident_no": inc.rig_incident_no or "", "incident_date": day, "recommendation": (a.action_recommended or "").strip(),
            "taken": (a.action_taken or "").strip(), "party": (a.action_party or "").strip(), "status": STATUS.get(a.action_status, a.action_status),
            "target": a.target_date, "due_text": text, "overdue": overdue, "id": a.incident_action_id,
        })
    rows.sort(key=lambda r: (r["rig"] == NO_RIG, r["rig"].lower(), r["target"] is not None, r["target"] or datetime.date.min, r["incident_no"], r["id"]))
    return rows


def by_rig(rows):
    """[(rig or unit, overdue, not yet due)] in the same order as the rows."""
    out = {}
    for r in rows:
        o = out.setdefault(r["rig"], [0, 0])
        o[0 if r["overdue"] else 1] += 1
    return [(rig, o, n) for rig, (o, n) in out.items()]


def build_workbook(rows, today):
    """The Excel bytes: a Summary sheet (the counts per rig or unit, as in the mail) and a Details sheet with one row per action."""
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
    ws["A1"] = "Open Incident Actions"
    ws["A1"].font = Font(name="Arial", size=15)
    ws["A2"] = f"Seros-IT Report Date: {today:%d-%m-%Y}"
    ws["A3"] = "Incident actions that are not closed."
    header(ws, 5, ["Rig / Unit", "Overdue", "Not yet due", "Total"])
    r, tot_o, tot_n = 6, 0, 0
    for rig, o, n in by_rig(rows):
        for i, v in enumerate([rig, o, n, o + n], start=1):
            c = ws.cell(row=r, column=i, value=v)
            c.border = box
            if i > 1:
                c.alignment = Alignment(horizontal="center")
        if o:
            ws.cell(row=r, column=2).fill = PatternFill("solid", fgColor=RED)
        tot_o, tot_n, r = tot_o + o, tot_n + n, r + 1
    for i, v in enumerate(["Total", tot_o, tot_n, tot_o + tot_n], start=1):
        c = ws.cell(row=r, column=i, value=v)
        c.font, c.border = Font(bold=True), box
        if i > 1:
            c.alignment = Alignment(horizontal="center")
    for col, w in zip("ABCD", (24, 12, 14, 10)):
        ws.column_dimensions[col].width = w

    wd = wb.create_sheet("Details")
    header(wd, 1, HEADERS)
    for n, row in enumerate(rows, start=1):
        values = [n, row["rig"], row["incident_no"], row["incident_date"], row["recommendation"], row["taken"], row["party"], row["status"], row["target"], row["due_text"]]
        for i, v in enumerate(values, start=1):
            c = wd.cell(row=n + 1, column=i, value=v)
            c.border, c.alignment = box, Alignment(vertical="top", wrap_text=True)
            if i in (4, 9):
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


def _counts_table(groups):
    th = "padding:5px 10px;border:1px solid #104a7b;background:#0715cd;color:#ffffff"
    head = f"<td style=\"{th};text-align:left\">Rig / Unit</td>" + "".join(f"<td style=\"{th};text-align:center\">{h}</td>" for h in ("Overdue", "Not yet due", "Total"))
    body, tot_o, tot_n = [], 0, 0
    for rig, o, n in groups:
        cell = "padding:4px 10px;border:1px solid #104a7b;text-align:center;background:#F7F8E0"
        red = f"{cell};background:#fde8e8;color:#b00020;font-weight:bold" if o else cell
        body.append(f"<tr><td style=\"padding:4px 10px;border:1px solid #104a7b;background:#F7F8E0\">{html.escape(rig)}</td><td style=\"{red}\">{o}</td><td style=\"{cell}\">{n}</td><td style=\"{cell}\">{o + n}</td></tr>")
        tot_o, tot_n = tot_o + o, tot_n + n
    tot = "padding:4px 10px;border:1px solid #104a7b;text-align:center;font-weight:bold"
    body.append(f"<tr><td style=\"{tot};text-align:left\">Total</td><td style=\"{tot}\">{tot_o}</td><td style=\"{tot}\">{tot_n}</td><td style=\"{tot}\">{tot_o + tot_n}</td></tr>")
    return f"<table cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse:collapse\"><tr>{head}</tr>{''.join(body)}</table>"


def build_mail(alert, now):
    """-> ReportMail for the alert (its Mail Subject gives the subject; the Window is not used)."""
    today = now.date()
    rows = collect(today)
    subject = (alert.mail_subject or "Seros-IT Auto Report - Open Incident Actions").strip()
    if not rows:
        line = "There are no open incident actions."
        return ReportMail(subject, _page(f"<p style=\"color:#0715cd;margin:0 0 14px\">{line}</p>"), line, [], True, "Nothing open")
    groups = by_rig(rows)
    overdue = sum(g[1] for g in groups)
    counts = f"{overdue} overdue, {len(rows) - overdue} not yet due"
    inner = (
        "<p style=\"color:#0715cd;margin:0 0 14px\">Open Incident Actions</p>"
        "<p>You are requested to review and close the open recommendations/actions, the overdue ones first. The full list is in the attached Excel file.</p>"
        f"{_counts_table(groups)}"
    )
    text = f"Open incident actions ({counts}). The full list is in the attached Excel file.\n" + "\n".join(f"{rig}: {o} overdue, {n} not yet due" for rig, o, n in groups)
    name = f"Open_Incident_Actions_{now:%d_%m_%Y_%H%M%S}.xlsx"
    return ReportMail(subject, _page(inner), text, [(name, build_workbook(rows, today), XLSX)], False, f"{len(rows)} open actions in {len(groups)} rigs or units: {counts}")


class OpenIncidentActionsJob(ScheduledReportJob):
    key = JOB_KEY
    name = "Open Incident Actions"
    report_name = "Open Incident Actions"
    description = "Every incident action that is not closed: counts per rig or unit in the mail, the full list as an Excel file."
    trigger_entity = ENTITY_KEY
    trigger_action = ACTION
    trigger_code = TRIGGER_CODE

    def build(self, alert, now):
        return build_mail(alert, now)


JOB = OpenIncidentActionsJob()


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
