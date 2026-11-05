"""The "Drilling Info : Daily Not Entered" mail (legacy alert 231, procedure Prc_Qry_Job_Drilling_Info_Daily_Not_Entered): one short mail per rig that has not
entered YESTERDAY's daily drilling report, sent on the alert's cycle (core/report_job.py, normally every day).

Which rigs are checked (as the legacy procedure did): the rig's latest project line is still open (no rig end date, no project end date) AND the rig has a daily
report in the last N days (N = the alert's Window; the legacy procedure had 30 written into it) on a well that is not completed. Every day within an active
project is a working day: there is no holiday rule. A checked rig with no daily report dated yesterday is flagged.

Who gets a rig's mail (the legacy Prc_Rig_To_Email_Mapping_Email_Config): the people set for that rig and this alert in Masters > Rig Alert Recipients
(active: To is blank or not yet passed), plus the alert's own recipients (Alert To Users). An address is listed once; if it is set more than once the
strongest type wins (To, then Cc, then Bcc). The Bcc is the alert's own Bcc rows (the legacy job had one address written into it; now it is the data). A rig
with no To address at all is reported as a failure (the legacy procedure refused to send it), after the other rigs' mails have gone.

The mail: subject = the alert's Mail Subject plus " - <rig>" (added 5 Nov 2026); body = "Seros-IT Auto Alert" (the legacy said "S.I.S."), "Drilling Information has not been updated for Rig : <rig>"
and, added, the date that is missing. Nothing is sent when no rig is missing. A failure is retried at the next hourly runs (a rig already mailed that day is
not mailed again) and, after the last try, reported by e-mail to SCHEDULER_ERROR_MAIL_TO (core/error_mail.py), which may hold several addresses separated by commas."""

import datetime
import html as _html

from . import mailer
from .models import DrillingDtl, EmailLog, MstRig, ProjectContractDtl, RigToEmailMapping
from .notification_triggers import resolve_alert_recipients_detailed
from .report_job import ReportMail, ScheduledReportJob

JOB_KEY = "drilling_info_not_entered"
ENTITY_KEY = "automation"
ACTION = "send_drilling_info_not_entered_mail"
TRIGGER_CODE = "auto.drilling_info_not_entered"
ALERT_NAME = "Drilling Info : Daily Not Entered"
DEFAULT_WINDOW = 30
RANK = {"to": 0, "cc": 1, "bcc": 2}
KIND = {"T": "to", "C": "cc", "B": "bcc"}


def window_days(alert):
    w = alert.alert_window if alert is not None else None
    return w if w and w >= 1 else DEFAULT_WINDOW


def active_rigs(today):
    """[rig id] whose latest project line is open (no rig end, no project end)."""
    latest = {}
    for ln in ProjectContractDtl.objects.filter(rig_active_to__isnull=True, contract__prj_end_dt__isnull=True):
        cur = latest.get(ln.rig_id)
        if cur is None or (ln.rig_active_from, ln.pk) > (cur.rig_active_from, cur.pk):
            latest[ln.rig_id] = ln
    return sorted(latest)


def missing_rigs(today, window):
    """[(rig id, rig name)] checked and without a daily report dated yesterday, in rig order."""
    yesterday = today - datetime.timedelta(days=1)
    back = today - datetime.timedelta(days=window)
    out = []
    for rid in active_rigs(today):
        worked = DrillingDtl.objects.filter(rig_id=rid, drilling_dtl_dt__gte=back, drilling_dtl_dt__lte=yesterday, drilling_hdr__rig_id=rid, drilling_hdr__drilling_completion_dt__isnull=True).exists()
        if worked and not DrillingDtl.objects.filter(rig_id=rid, drilling_dtl_dt=yesterday).exists():
            out.append((rid, MstRig.objects.get(pk=rid).rig_name))
    return out


def rig_rows(alert_id, rig_id, as_of, company_id=None):
    """The Rig Alert Recipients rows of the alert for a rig (or, for a mail that goes out per company, for a company) that are active on `as_of`."""
    qs = RigToEmailMapping.objects.filter(alert_id=alert_id, addressee_type__in=list(KIND), from_dt__lte=as_of).select_related("user")
    qs = qs.filter(company_id=company_id) if company_id is not None else qs.filter(rig_id=rig_id)
    return [r for r in qs if (r.to_dt is None or r.to_dt >= as_of) and (r.user.user_email or "").strip()]


def recipients_for_rig(alert_id, rig_id, as_of, company_id=None):
    """{to, cc, bcc}: the rig's (or company's) own recipients plus the alert's, each address once, in the strongest type it was given."""
    best = {}
    entries = [(KIND[r.addressee_type], r.user.user_email.strip()) for r in rig_rows(alert_id, rig_id, as_of, company_id)]
    entries += [(e["type"], e["email"].strip()) for e in resolve_alert_recipients_detailed(alert_id, as_of)]
    for kind, email in entries:
        key = email.lower()
        if key not in best or RANK[kind] < RANK[best[key][0]]:
            best[key] = (kind, email)
    out = {"to": [], "cc": [], "bcc": []}
    for kind, email in best.values():
        out[kind].append(email)
    return out


def recipients_for_company(alert_id, company_id, as_of):
    return recipients_for_rig(alert_id, None, as_of, company_id)


def _page(rig, day):
    return (
        "<div style=\"font-family:Verdana,Tahoma,Arial,sans-serif;font-size:13px\">"
        "<p style=\"color:#e00707;margin:0 0 4px\">Seros-IT Auto Alert</p><br/>"
        f"<p style=\"color:#0715cd;margin:0 0 14px\">Drilling Information has not been updated for Rig : {_html.escape(rig)}</p>"
        f"<p style=\"margin:0 0 14px\">No daily drilling report is entered for {day:%d %b %Y}.</p>"
        "<p style=\"margin:28px 0 0\">* This is an automated mail. Please do not reply.</p></div>"
    )


def _text(rig, day):
    return f"Seros-IT Auto Alert\n\nDrilling Information has not been updated for Rig : {rig}\nNo daily drilling report is entered for {day:%d %b %Y}.\n\n* This is an automated mail. Please do not reply."


class DrillingInfoNotEnteredJob(ScheduledReportJob):
    key = JOB_KEY
    name = "Drilling Info: Daily Not Entered"
    report_name = "Drilling Info: Daily Not Entered"
    description = "One mail per rig that has not entered yesterday's daily drilling report, to the rig's own recipients and the alert's."
    trigger_entity = ENTITY_KEY
    trigger_action = ACTION
    trigger_code = TRIGGER_CODE
    uses_rig_recipients = True  # the preview and the pages also list / link Rig Alert Recipients

    def build(self, alert, now):
        """The summary of what a run would send (used by the preview and the tests); the mails themselves are made in send_report."""
        today = now.date()
        rigs = missing_rigs(today, window_days(alert))
        names = ", ".join(n for _i, n in rigs)
        return ReportMail(alert.mail_subject or "Drilling Info Not Updated.", "", "", [], not rigs, f"{len(rigs)} rig(s) without yesterday's report: {names}" if rigs else "Every rig has yesterday's report: nothing sent")

    def preview_mails(self, alert, now):
        """The test: one real mail per rig that is missing yesterday's report. When no rig is missing, one EXAMPLE mail for the first checked rig, so the mail can still be seen."""
        today = now.date()
        yesterday = today - datetime.timedelta(days=1)
        base = (alert.mail_subject or "Drilling Info Not Updated.").strip()
        rigs = missing_rigs(today, window_days(alert))
        example = False
        if not rigs:
            ids = active_rigs(today)
            rigs = [(i, MstRig.objects.get(pk=i).rig_name) for i in ids[:1]]
            example = True
        out = []
        for _i, rig in rigs:
            subject = f"{base} - {rig}" + (" (example: no rig is missing right now)" if example else "")
            out.append(ReportMail(subject, _page(rig, yesterday), _text(rig, yesterday), [], False, f"mail for {rig}"))
        return out

    def recipients_detailed(self, as_of=None):
        a = self.alert()
        if not a:
            return []
        as_of = as_of or datetime.date.today()
        out = resolve_alert_recipients_detailed(a.alert_id, as_of)
        names = dict(MstRig.objects.values_list("rig_id", "rig_name"))
        for r in RigToEmailMapping.objects.filter(alert_id=a.alert_id, addressee_type__in=list(KIND), from_dt__lte=as_of).select_related("user"):
            if (r.to_dt is None or r.to_dt >= as_of) and (r.user.user_email or "").strip():
                out.append({"type": KIND[r.addressee_type], "email": r.user.user_email.strip(), "name": (r.user.user_name or "").strip(), "source": f"Rig Alert Recipients ({names.get(r.rig_id, 'any rig')})", "from": r.from_dt, "to_date": r.to_dt})
        return out

    def _blockers(self, setup, now):
        if not setup["trigger_found"] or not setup["trigger_active"]:
            return f"The trigger for the {self.report_name} is missing or switched off."
        if not setup["alert"]["active"]:
            return f"The alert '{setup['alert']['name']}' is switched off. Tick Active on it in Masters > Alert Details."
        return ""

    def send_report(self, alert, setup, now, designated=True):
        """Sends one mail per missing rig. Returns (error, result, mail) as the base class does; `result` is that of the last mail sent (None when nothing was sent)."""
        error = self._blockers(setup, now)
        if error:
            return error, None, None
        today = now.date()
        yesterday = today - datetime.timedelta(days=1)
        rigs = missing_rigs(today, window_days(alert))
        base_subject = (alert.mail_subject or "Drilling Info Not Updated.").strip()
        sent, skipped, problems, last, all_to = [], [], [], None, []
        for rig_id, rig in rigs:
            label = f"Drilling Info Not Entered: {rig} · {yesterday:%Y-%m-%d}"[:200]
            if EmailLog.objects.filter(trigger=label, success=True, sent_dt__date=today).exists():
                skipped.append(rig)  # mailed by an earlier try of this run: not again
                continue
            subject = f"{base_subject} - {rig}"  # the rig is in the subject too, so the mails of different rigs are told apart in the inbox
            rec = recipients_for_rig(alert.alert_id, rig_id, today)
            if not rec["to"]:
                problems.append(f"{rig}: no To address (set one in Masters > Rig Alert Recipients or Alert To Users)")
                continue
            try:
                res = mailer.send_scheduled_email(
                    subject, _page(rig, yesterday), _text(rig, yesterday), to=rec["to"], cc=rec["cc"], bcc=rec["bcc"], from_name=setup["from_name"], trigger=label,
                    trigger_code=TRIGGER_CODE, designated=designated, alert_id=alert.alert_id, env_account=False,
                )
            except Exception as exc:  # the mailer never raises, but a mail that cannot be built must not stop the other rigs
                problems.append(f"{rig}: {type(exc).__name__}: {exc}")
                continue
            if res["ok"]:
                sent.append(rig)
                last = res
                all_to += rec["to"] + rec["cc"] + [f"bcc:{a}" for a in rec["bcc"]]
            else:
                problems.append(f"{rig}: {res['error'] or 'the mail could not be sent'}")
        if last is not None:
            last = {**last, "recipients": ", ".join(dict.fromkeys(all_to))}
        parts = []
        if rigs:
            parts.append(f"{len(rigs)} rig(s) without {yesterday:%d %b} report: {', '.join(n for _i, n in rigs)}")
        else:
            parts.append("Every checked rig has yesterday's report: nothing sent")
        if skipped:
            parts.append(f"already mailed earlier: {', '.join(skipped)}")
        mail = ReportMail(base_subject, "", "", [], not rigs, " · ".join(parts)[:280])
        if problems:
            return "; ".join(problems), last, mail
        return "", last, mail


JOB = DrillingInfoNotEnteredJob()


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
