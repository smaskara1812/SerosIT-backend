"""Recipient resolution for approval-workflow notification mail — Drilling
Report today, the same shape reused by other approval codes (HR, Offer
Letters, ...) later.

Business rule is fixed in code, not admin-configurable (confirmed over
several rounds — only the *extra* addresses are configurable, via
MailRecipientMapping):

    FINALIZE                         actor = creator
        To  = the rig's Level-1 approver(s) (ApproverMappingDtl, receive_mail='Y')
        Cc  = the creator (self) — always, even if the creator also happens
              to land in To for some other reason
    APPROVE / REJECT / REVISE_PREVIOUS   actor = the approver who acted
        To  = the record's creator + every OTHER approver mapped to that
              rig (excluding the actor)
        Cc  = the acting approver (self) — always, even if they also happen
              to be a To recipient (e.g. also mapped as a receive_mail
              approver on the same rig they just acted on)
    REVISE_SELF                      no mail

On top of that, whatever's attached via MailRecipientMapping for that
(approval_code, event_type) is merged in, bucketed by that entry's own
addressee_type (To/Cc/Bcc) — not hardcoded per event like the legacy SQL.
"""

from .models import ApproverMappingDtl, MailRecipientMapping, MstUser

DRILLING_APPROVAL_CODE = "DRILLING_DTL"


def _dedupe(seq):
    return list(dict.fromkeys(a for a in seq if a))


def _approver_emails(approval_code, rig_id, level=1, exclude_user_id=None):
    qs = ApproverMappingDtl.objects.filter(
        approver_mapping__approval_code__approval_code=approval_code,
        approver_mapping__approver_level=level,
        approver_mapping__approver_active="Y",
        rig_id=rig_id,
        receive_mail="Y",
    ).select_related("approver_mapping__approver_user")
    emails = []
    for d in qs:
        user = d.approver_mapping.approver_user
        if exclude_user_id is not None and user.user_id == exclude_user_id:
            continue
        if user.user_email:
            emails.append(user.user_email)
    return emails


def _user_email(user_id):
    if user_id is None:
        return None
    user = MstUser.objects.filter(user_id=user_id).first()
    return user.user_email if user else None


def _apply_mapping_extras(approval_code, event_type, to, cc, bcc):
    mappings = MailRecipientMapping.objects.filter(
        approval_code__approval_code=approval_code, event_type=event_type
    ).select_related("mail_alert_to_user")
    for m in mappings:
        entry = m.mail_alert_to_user
        if not entry.email_addr:
            continue
        {"T": to, "C": cc, "B": bcc}.get(entry.addressee_type, []).append(entry.email_addr)


def resolve_drilling_mail(event_type, rig_id, creator_user_id, actor_user_id):
    """Returns {to, cc, bcc} (each a deduped list of email addresses) for
    one Drilling Report notification. Caller resolves the actor's own
    identity (email/login/cached password) separately — this function only
    decides who receives the mail, not who sends it."""
    to, mapping_cc, bcc = [], [], []
    actor_email = _user_email(actor_user_id)

    if event_type == MailRecipientMapping.EVENT_FINALIZE:
        to = _approver_emails(DRILLING_APPROVAL_CODE, rig_id, level=1)
    else:
        creator_email = _user_email(creator_user_id)
        if creator_email:
            to.append(creator_email)
        to += _approver_emails(DRILLING_APPROVAL_CODE, rig_id, level=1, exclude_user_id=actor_user_id)

    _apply_mapping_extras(DRILLING_APPROVAL_CODE, event_type, to, mapping_cc, bcc)

    to = _dedupe(to)
    # The acting user is always Cc'd on their own action, unconditionally —
    # even when they also happen to land in To (e.g. an approver who's also
    # themself mapped as a receive_mail approver on the rig they just acted
    # on). Only the admin-configured extras get deduped against To; the
    # actor's own self-Cc is never dropped for that reason.
    cc = ([actor_email] if actor_email else []) + [a for a in mapping_cc if a != actor_email and a not in to]
    cc = _dedupe(cc)
    bcc = _dedupe(a for a in bcc if a not in to and a not in cc)
    return {"to": to, "cc": cc, "bcc": bcc}
