"""The "Drilling Info Status" mail (legacy alert 244, procedure Prc_Qry_Drilling_Info_Status): one mail per COMPANY, every day, with a table of the company's rigs
that are on a project: the rig, its project, the project's start, the first anchor-down of its current well, the date of its latest daily report and how many
days old that is. It is a status mail, not an alarm: it goes out every day whether or not something is late (the days are red when more than 1).

Which rigs: every rig of sub-type 2 or 3 on a project line that is still open (the project has no end date and the rig no end date), taken to the company that
owns the rig's cost centre (Cost Centre To Company Mapping, the mapping with no end date). A rig appears under every such company (normally one). All of them, every
day, including a rig that has never reported (its Last Update and Days Diff. are blank).
Columns: Company (its abbreviation) · Rig Name ("EE01 (LR 3)": the name and the old name) · Contract No. (spaces removed) · Prj Start Date · First Anchor Down Date (of
the rig's well that is not completed; the latest if there are several) · Last Update on (the rig's latest daily report, any project) · Days Diff. (today less that
date; blank when 0; red when more than 1).
Who gets a company's mail: the people set for that COMPANY and alert 244 in Masters > Rig Alert Recipients (active: To blank or not yet passed) plus the alert's own
recipients (Alert To Users), each address once, the strongest type winning (core/drilling_info_not_entered.py). A company with no To address is reported as a failure
after the other companies' mails have gone. Mails are made in the alert's cycle (core/report_job.py): Next Mail, Start Time and Frequency (1 = every day) are set on the alert;
a retry does not mail a company twice in a day. Wording: "Seros-IT Auto Alert" where the legacy mail said "S.I.S."; the subject is the alert's Mail Subject plus " - <company>" (added 7 Nov 2026, as the Drilling Info Not Entered mail does with the rig)."""

import datetime
import html as _html

from . import mailer
from .drilling_info_not_entered import recipients_for_company
from .models import CostCentreToCompanyMapping, DrillingDtl, DrillingHdr, EmailLog, MstCostCentre, MstRig, ProjectContractDtl, RigToEmailMapping
from .notification_triggers import resolve_alert_recipients_detailed
from .report_job import ReportMail, ScheduledReportJob
from django.db.models import Max

JOB_KEY = "drilling_info_status"
ENTITY_KEY = "automation"
ACTION = "send_drilling_info_status_mail"
TRIGGER_CODE = "auto.drilling_info_status"
ALERT_NAME = "Drilling Info Status"
SUBTYPES = (2, 3)
HEADERS = ["Company", "Rig Name", "Contract No.", "Prj Start Date", "First Anchor Down Date", "Last Update on", "Days Diff."]
KIND = {"T": "to", "C": "cc", "B": "bcc"}


def status_rows(today):
    """[{company_id, company, rig_id, rig, contract_no, prj_start, anchor, last, days}] for every rig on an open project line, in company then rig order."""
    out = []
    for ln in ProjectContractDtl.objects.filter(contract__prj_end_dt__isnull=True, rig_active_to__isnull=True, rig__rig_subtype_id__in=SUBTYPES).select_related("contract", "rig"):
        rig = ln.rig
        last = DrillingDtl.objects.filter(rig_id=rig.rig_id).aggregate(m=Max("drilling_dtl_dt"))["m"]
        anchor = DrillingHdr.objects.filter(rig_id=rig.rig_id, drilling_completion_dt__isnull=True, first_anchor_down_dt__isnull=False).order_by("-first_anchor_down_dt").values_list("first_anchor_down_dt", flat=True).first()
        for cc in MstCostCentre.objects.filter(rig_id=rig.rig_id):
            for mp in CostCentreToCompanyMapping.objects.filter(cost_centre=cc, mapping_to__isnull=True).select_related("company"):
                out.append({
                    "company_id": mp.company_id, "company": mp.company.company_abrv or mp.company.company_name, "rig_id": rig.rig_id,
                    "rig": f"{rig.rig_name} ({rig.old_rig_name})" if rig.old_rig_name else rig.rig_name,
                    "contract_no": (ln.contract.prj_contract_no or "").replace(" ", ""), "prj_start": ln.contract.prj_start_dt, "anchor": anchor.date() if anchor else None,
                    "last": last, "days": (today - last).days if last else 0,
                })
    out.sort(key=lambda r: (r["company"] or "", r["company_id"], r["rig_id"]))
    return out


def by_company(rows):
    """[(company id, company, [rows])] in company order."""
    groups = {}
    for r in rows:
        groups.setdefault((r["company"], r["company_id"]), []).append(r)
    return [(cid, name, rs) for (name, cid), rs in sorted(groups.items(), key=lambda kv: (kv[0][0] or "", kv[0][1]))]


def _d(v):
    return f"{v:%d/%m/%Y}" if v else ""


def build_company_mail(company, rows):
    """-> (html, text) of one company's mail."""
    th = "padding:3px;border:1px solid #000000;background-color:#00988A;color:#FFFFFF;font-weight:bold;text-align:left"
    td = "padding:3px;border:1px solid #000000"
    head = "".join(f"<td style=\"{th}\">{h}</td>" for h in HEADERS)
    body = []
    for r in rows:
        days = "" if not r["days"] else str(r["days"])
        red = "color:red;" if r["days"] > 1 else ""
        body.append(
            "<tr style=\"font-family:Verdana,Tahoma,Arial;font-size:11px\">"
            f"<td style=\"{td}\">{_html.escape(r['company'] or '')}</td><td style=\"{td}\">{_html.escape(r['rig'])}</td><td style=\"{td}\">{_html.escape(r['contract_no'])}</td>"
            f"<td style=\"{td}\">{_d(r['prj_start'])}</td><td style=\"{td}\">{_d(r['anchor'])}</td><td style=\"{td}\">{_d(r['last'])}</td>"
            f"<td style=\"{td};text-align:center;{red}\">{days}</td></tr>"
        )
    html = (
        "<div style=\"font-family:Verdana,Tahoma,Arial,sans-serif;font-size:13px\">"
        "<p style=\"color:#e00707;margin:0 0 4px\">Seros-IT Auto Alert</p><br/>"
        "<p style=\"color:#0715cd;margin:0 0 14px\">Drilling Info Status</p><br/>"
        "<table style=\"border-collapse:collapse\" cellpadding=\"3\" cellspacing=\"3\" border=\"1\">"
        f"<tr style=\"font-family:Verdana,Tahoma,Arial;font-size:11px\">{head}</tr>{''.join(body)}</table>"
        "<p style=\"margin:40px 0 0\">* This is an automated mail. Please do not reply.</p></div>"
    )
    lines = ["Seros-IT Auto Alert", "", "Drilling Info Status", " | ".join(HEADERS)]
    for r in rows:
        lines.append(" | ".join([r["company"] or "", r["rig"], r["contract_no"], _d(r["prj_start"]), _d(r["anchor"]), _d(r["last"]), "" if not r["days"] else str(r["days"])]))
    lines += ["", "* This is an automated mail. Please do not reply."]
    return html, "\n".join(lines)


class DrillingInfoStatusJob(ScheduledReportJob):
    key = JOB_KEY
    name = "Drilling Info Status"
    report_name = "Drilling Info Status"
    description = "Every day, one mail per company: its rigs on a project, with the project, the first anchor down and the date of the latest daily report."
    trigger_entity = ENTITY_KEY
    trigger_action = ACTION
    trigger_code = TRIGGER_CODE
    uses_rig_recipients = True  # the preview and the pages also list / link Rig Alert Recipients

    def build(self, alert, now):
        from .drilling_info_not_entered import _workbook, XLSX
        from .drilling_info_not_entered import recipients_for_company as _rc

        today = now.date()
        groups = by_company(status_rows(today))
        names = ", ".join(n for _c, n, _r in groups)
        rows = []
        for cid, company, rs in groups:
            rec = _rc(alert.alert_id, cid, today)
            for r in rs:
                rows.append([r["company"], r["rig"], r["contract_no"], r["prj_start"], r["anchor"], r["last"], r["days"] or None, "; ".join(rec["to"]), "; ".join(rec["cc"]), "; ".join(rec["bcc"])])
        sheet = _workbook("Drilling Info Status", HEADERS + ["To", "Cc", "Bcc"], rows, "No rig is on a project: nothing would be sent.")
        return ReportMail(alert.mail_subject or "Drilling Info Status", "", "", [(f"Drilling_Info_Status_{now:%d_%m_%Y}.xlsx", sheet, XLSX)], not groups, f"{len(groups)} company mail(s): {names}" if groups else "No rig is on a project: nothing sent")

    def preview_mails(self, alert, now):
        """The test: one real mail per company, as the real run sends them."""
        subject = (alert.mail_subject or "Drilling Info Status").strip()
        out = []
        for cid, company, rows in by_company(status_rows(now.date())):
            html, text = build_company_mail(company, rows)
            rec = recipients_for_company(alert.alert_id, cid, now.date())
            out.append(ReportMail(f"{subject} - {company}", html, text, [], False, f"mail for {company}", to=rec["to"], cc=rec["cc"], bcc=rec["bcc"]))
        return out

    def recipients_detailed(self, as_of=None, alert=None, base=None):
        a = alert or self.alert()
        if not a:
            return []
        as_of = as_of or datetime.date.today()
        out = list(base) if base is not None else resolve_alert_recipients_detailed(a.alert_id, as_of)
        for r in RigToEmailMapping.objects.filter(alert_id=a.alert_id, company__isnull=False, addressee_type__in=list(KIND), from_dt__lte=as_of).select_related("user", "company"):
            if (r.to_dt is None or r.to_dt >= as_of) and (r.user.user_email or "").strip():
                out.append({"type": KIND[r.addressee_type], "email": r.user.user_email.strip(), "name": (r.user.user_name or "").strip(), "source": f"Rig Alert Recipients ({r.company.company_abrv or r.company.company_name})", "from": r.from_dt, "to_date": r.to_dt})
        return out

    def _blockers(self, setup, now):
        if not setup["trigger_found"] or not setup["trigger_active"]:
            return f"The trigger for the {self.report_name} is missing or switched off."
        if not setup["alert"]["active"]:
            return f"The alert '{setup['alert']['name']}' is switched off. Tick Active on it in Masters > Alert Details."
        return ""

    def send_report(self, alert, setup, now, designated=True, fresh=False):
        """One mail per company. Returns (error, result, mail) as the base class does; `result` is that of the last mail sent (None when nothing was sent)."""
        error = self._blockers(setup, now)
        if error:
            return error, None, None
        today = now.date()
        subject = (alert.mail_subject or "Drilling Info Status").strip()
        groups = by_company(status_rows(today))
        sent, skipped, problems, last, all_to = [], [], [], None, []
        for company_id, company, rows in groups:
            label = f"Drilling Info Status: {company} · {today:%Y-%m-%d}"[:200]
            if not fresh and EmailLog.objects.filter(trigger=label, success=True, sent_dt__date=today).exists():
                skipped.append(company)
                continue
            rec = recipients_for_company(alert.alert_id, company_id, today)
            if not rec["to"]:
                problems.append(f"{company}: no To address (set one in Masters > Rig Alert Recipients or Alert To Users)")
                continue
            html, text = build_company_mail(company, rows)
            try:
                res = mailer.send_scheduled_email(f"{subject} - {company}", html, text, to=rec["to"], cc=rec["cc"], bcc=rec["bcc"], from_name=setup["from_name"], trigger=label, trigger_code=TRIGGER_CODE, designated=designated, alert_id=alert.alert_id, env_account=False)
            except Exception as exc:
                problems.append(f"{company}: {type(exc).__name__}: {exc}")
                continue
            if res["ok"]:
                sent.append(company)
                last = res
                all_to += rec["to"] + rec["cc"] + [f"bcc:{a}" for a in rec["bcc"]]
            else:
                problems.append(f"{company}: {res['error'] or 'the mail could not be sent'}")
        if last is not None:
            last = {**last, "recipients": ", ".join(dict.fromkeys(all_to))}
        parts = [f"{len(sent)} company mail(s) sent: {', '.join(sent)}" if sent else ("No rig is on a project: nothing sent" if not groups else "No new mail sent")]
        if skipped:
            parts.append(f"already mailed earlier: {', '.join(skipped)}")
        mail = ReportMail(subject, "", "", [], not groups, " · ".join(parts)[:280])
        return ("; ".join(problems), last, mail)


JOB = DrillingInfoStatusJob()


def ensure_setup(alert_id=None, alert_name=ALERT_NAME):
    """Creates the scheduler's job row and, when the alert can be found (by id, else by name), the trigger row that connects the mail to it. Safe to run again."""
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
