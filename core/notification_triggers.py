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


def _dedupe(seq):
    return list(dict.fromkeys(a for a in seq if a))


def resolve_alert_recipients(alert_id, as_of=None):
    """Returns {to, cc, bcc} (deduped email lists) for one alert_id, from
    MailAlertToUser rows whose mail_alert_from/mail_alert_to window covers
    as_of (defaults to today) — same date-scoping shape used elsewhere in
    this app for time-bounded config (e.g. company_branding.py)."""
    as_of = as_of or date_cls.today()
    to, cc, bcc = [], [], []
    rows = MailAlertToUser.objects.filter(alert_id=alert_id, mail_alert_from__lte=as_of).filter(
        Q(mail_alert_to__isnull=True) | Q(mail_alert_to__gte=as_of)
    )
    for r in rows:
        {"T": to, "C": cc, "B": bcc}.get(r.addressee_type, []).append(r.email_addr)
    return {"to": _dedupe(to), "cc": _dedupe(cc), "bcc": _dedupe(bcc)}


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
