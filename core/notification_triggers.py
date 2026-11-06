"""Generic (entity_key, action) -> notification dispatch.

Legacy hardcoded a raw Alert_Id literal at every single call site that
needed to fire a mail on some action — confirmed across 40+ 'U'-type rows
in Mail_Alert_Dtl (Offer Letter creation, Material Requisition creation,
Incident creation via Alert_Id 240, etc.), never a shared resolver. This
module is that resolver: a call site just does

    notification_triggers.trigger("qhse.incident_details", "create", ...)

and whether that fires at all, and who it goes to, comes from data
(NotificationTrigger + the MailAlertToUser rows already scoped to its
alert_id) — not from a number written into this feature's own code. A new
"notify on X" feature later is a NotificationTrigger row, not a new
hardcoded id and a bespoke resolver.

Deliberately separate from mail_recipients.py's Drilling Report approval
logic — that resolver computes recipients from a business rule (creator +
mapped approvers) with MailRecipientMapping only layering "extras" on
top. Here there's no computed base case: the entire recipient list for a
given trigger comes from data, exactly like MailRecipientMapping's own
extras do (same MailAlertToUser table, just not layered on anything)."""

from datetime import date as date_cls

from django.db.models import Q

from . import mailer
from .models import MailAlertToUser, NotificationTrigger


# Every trigger point and action the application knows, with the words the form shows. This is the one list: the Notification Triggers form offers
# exactly these, and a row for any other pair is refused (a typo would otherwise be a mail that silently never goes out). Adding a "notify on X" feature
# means adding it here AND to the schema in frontend/src/config/mastersSchemas.js ('notification-triggers'); scripts/check_trigger_registry.py fails
# when the two differ. {entity_key: (label, {action: label})}
TRIGGER_POINTS = {
    "qhse.incident_details": ("QHSE → Incident Details", {"create": "Create"}),
    "automation": (
        "Automation",
        {
            "send_birthday_mail": "Send birthday mail",
            "send_holiday_mail": "Send holiday mail",
            "send_haz_id_register_mail": "Send HAZ ID register mail",
            "send_rig_rate_breakup_mail": "Send Rig Rate Break-Up mail",
            "send_activity_monitor_mail": "Send Activity Monitor mail",
            "send_open_incident_actions_mail": "Send Open Incident Actions mail",
            "send_daily_operations_update_mail": "Send Daily Operations Update mail",
            "send_rig_performance_mail": "Send Rig Performance mail",
            "send_drilling_info_not_entered_mail": "Send Drilling Info: Daily Not Entered mail",
            "send_drilling_info_status_mail": "Send Drilling Info Status mail",
        },
    ),
}


def is_registered(entity_key, action):
    return action in TRIGGER_POINTS.get(entity_key, ("", {}))[1]


def _dedupe(seq):
    return list(dict.fromkeys(a for a in seq if a))


def _alert_rows(alert_id, as_of):
    return (
        MailAlertToUser.objects.filter(alert_id=alert_id, mail_alert_from__lte=as_of)
        .filter(Q(mail_alert_to__isnull=True) | Q(mail_alert_to__gte=as_of))
        .select_related("user")
    )


def _detailed_from_rows(rows):
    kind = {"T": "to", "C": "cc", "B": "bcc"}
    out = []
    for r in rows:
        if r.addressee_type not in kind or not r.email_addr:
            continue
        name = (r.user.user_name.strip() if r.user_id and r.user.user_name else "") or (r.recipient_name or "")
        out.append({
            "type": kind[r.addressee_type], "email": r.email_addr, "name": name,
            "source": f"Alert To Users (alert {r.alert_id}, row {r.mail_alert_to_user_id})",
            "from": r.mail_alert_from, "to_date": r.mail_alert_to,
        })
    return out


def resolve_alert_recipients_detailed(alert_id, as_of=None):
    """The recipients of one alert, each with where it comes from: [{"type": "to"|"cc"|"bcc", "email", "name", "source"}, ...], from the
    MailAlertToUser rows whose From/To window covers as_of (default today). This is the one place that decides who a mail goes to: sending uses
    it (through resolve_alert_recipients), and so does the recipients preview on the Scheduled Mails and Report Mails pages, so the preview is
    exactly what is sent. More sources (for example the rig-wise recipients of some report) are added here, each with its own `source` text."""
    as_of = as_of or date_cls.today()
    return _detailed_from_rows(_alert_rows(alert_id, as_of))


def resolve_many_recipients_detailed(alert_ids, as_of=None):
    """The same as resolve_alert_recipients_detailed, for several alerts in one query. {alert_id: [entries]}. An alert with nobody is an empty list."""
    as_of = as_of or date_cls.today()
    ids = [i for i in dict.fromkeys(alert_ids) if i]
    if not ids:
        return {}
    grouped = {}
    rows = (
        MailAlertToUser.objects.filter(alert_id__in=ids, mail_alert_from__lte=as_of)
        .filter(Q(mail_alert_to__isnull=True) | Q(mail_alert_to__gte=as_of))
        .select_related("user")
    )
    for r in rows:
        grouped.setdefault(r.alert_id, []).append(r)
    return {i: _detailed_from_rows(grouped.get(i, [])) for i in ids}


def lists_from_detailed(entries):
    """{to, cc, bcc} email lists from the detailed entries, deduped, in the same order."""
    lists = {"to": [], "cc": [], "bcc": []}
    for e in entries:
        lists[e["type"]].append(e["email"])
    return {k: _dedupe(v) for k, v in lists.items()}


def resolve_alert_recipients(alert_id, as_of=None):
    """Returns {to, cc, bcc} (deduped email lists) for one alert_id, from
    MailAlertToUser rows whose mail_alert_from/mail_alert_to window covers
    as_of (defaults to today) — same date-scoping shape used elsewhere in
    this app for time-bounded config (e.g. company_branding.py). Built from
    resolve_alert_recipients_detailed, so the list and the preview agree."""
    return lists_from_detailed(resolve_alert_recipients_detailed(alert_id, as_of))


def trigger(entity_key, action, subject, body, sent_by_user_id=None, is_html=True, attachments=None):
    """Looks up the active NotificationTrigger for (entity_key, action).
    A missing rule, or a rule with no configured recipients, is a silent
    no-op — same as every other notification call site in this app (a
    notification that isn't configured, or has nowhere to go, shouldn't
    raise from inside the request that triggered it).

    attachments (list of (filename, content_bytes, mimetype) tuples) is
    passed straight through to mailer.queue_notification_email — build it
    before calling trigger(), since the actual send happens on a
    background thread with no access back to the request/DB."""
    rule = (
        NotificationTrigger.objects.filter(entity_key=entity_key, action=action, notification_trigger_active="Y")
        .select_related("alert")
        .first()
    )
    if not rule:
        return

    recipients = resolve_alert_recipients(rule.alert_id)
    if not (recipients["to"] or recipients["cc"] or recipients["bcc"]):
        return

    mailer.queue_notification_email(
        subject=subject,
        body=body,
        is_html=is_html,
        attachments=attachments,
        to=recipients["to"],
        cc=recipients["cc"],
        bcc=recipients["bcc"],
        trigger=rule.alert.alert_name,
        trigger_code=f"{entity_key}.{action}",
        sent_by_user_id=sent_by_user_id,
    )
