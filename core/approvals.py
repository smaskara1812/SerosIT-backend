"""Generic creator/approver workflow engine, driven by ApproverMapping /
ApproverMappingDtl. Not Drilling-specific — MstApprovalCode has 10 other
codes in the real legacy data (GRN, Invoice, Contract, Overtime...), so any
future approval-driven form calls into this same module rather than
reimplementing role resolution and state transitions per form.

A "record" here is any model with cr_status/l1_approval_status/l1_user_id/
l1_approval_dt/opened_for_revision_by/opened_for_revision_dt fields —
DrillingDtl today, whatever comes next tomorrow.
"""

from django.utils import timezone

from .models import ApproverMapping, UserProfile


def _profile_user_id(request):
    try:
        return UserProfile.objects.get(user_login_id=request.user.username).user_id
    except UserProfile.DoesNotExist:
        return None


def get_role(approval_code_key, user_id, rig_id):
    """Aggregate capability flags for this user, on this Approval Code, for
    this rig — across every active ApproverMapping row that scopes to it
    (a user can appear more than once, e.g. two levels). Superusers/unmapped
    profiles get no special bypass here; that's a caller decision (the view
    checks request.user.is_superuser itself, same as everywhere else)."""
    caps = {"create": False, "approve": False, "revise": False, "receive_mail": False, "level": None}
    if user_id is None:
        return caps
    mappings = ApproverMapping.objects.filter(
        approval_code__approval_code=approval_code_key,
        approver_user_id=user_id,
        approver_active="Y",
    ).prefetch_related("details")
    for m in mappings:
        for d in m.details.all():
            if d.rig_id != rig_id:
                continue
            if d.create_yn == "Y":
                caps["create"] = True
            if d.approve_yn == "Y":
                caps["approve"] = True
                caps["level"] = m.approver_level if caps["level"] is None else min(caps["level"], m.approver_level)
            if d.open_for_revision_yn == "Y":
                caps["revise"] = True
            if d.receive_mail == "Y":
                caps["receive_mail"] = True
    return caps


def get_role_for_request(approval_code_key, request, rig_id):
    return get_role(approval_code_key, _profile_user_id(request), rig_id)


# ── Gates ────────────────────────────────────────────────────────────────
# Mirrors the legacy doc's own filter strings exactly:
#   Approver's queue:        Cr_Status='F' AND L1_Approval_Status='N'
#   Creator+Approver's queue: (Cr_Status='F' OR Cr_Status='N') AND L1_Approval_Status='N'
# A record with no cr_status yet (NULL/blank) is a plain draft — only its
# creator can touch it, before it ever reaches an approver.


def is_draft(record):
    return record.cr_status not in ("F", "N")


# L1_Approval_Status values that mean "not yet decided" — real historical
# data only ever has NULL/blank here (never literal 'N'), while records our
# own finalize() writes always get literal 'N'. Both mean the same thing.
PENDING_L1 = (None, "", "N")


def can_finalize(record, caps):
    """Creator finalizes a draft, or re-finalizes after being sent back."""
    return caps["create"] and record.cr_status in (None, "", "N")


def can_approve(record, caps):
    return caps["approve"] and record.cr_status == "F" and record.l1_approval_status in PENDING_L1


def can_reject(record, caps):
    """Approver's other decision at the same point Approve is offered —
    same gate, opposite outcome. Rejection is terminal (see can_revise_self/
    can_revise_previous below), matching 'once rejected, no further actions
    required on this'."""
    return caps["approve"] and record.cr_status == "F" and record.l1_approval_status in PENDING_L1


def can_revise_self(record, caps):
    """Approver reopens the record for direct editing (of the underlying
    data, not just their own decision) — a more privileged action than a
    plain approve/reject, so it's gated by the explicit 'Open For Revision'
    flag rather than the base approve capability. Available throughout the
    approval stage except once terminally Rejected."""
    return caps["revise"] and record.cr_status == "F" and record.l1_approval_status != "R"


def can_revise_previous(record, caps):
    """Approver sends the record back to its creator — a basic approver
    action, available to anyone with approve capability regardless of
    whether they also hold 'Open For Revision'. Someone without that flag
    still has this as their only way to push a record back. Unavailable
    once terminally Rejected."""
    return caps["approve"] and record.cr_status == "F" and record.l1_approval_status != "R"


def can_edit_as_approver(record, caps):
    """True while the record is sitting in the window opened by
    revise_self: still pending a fresh decision, and specifically reopened
    (not just freshly finalized) for direct editing. finalize() clears
    opened_for_revision_by, so a freshly (re)submitted record never starts
    in this state — only an explicit Revise (Self) puts it here."""
    return (
        caps["revise"]
        and record.cr_status == "F"
        and record.l1_approval_status in PENDING_L1
        and record.opened_for_revision_by is not None
    )


# ── Transitions ──────────────────────────────────────────────────────────


def finalize(record, user_id):
    record.cr_status = "F"
    record.l1_approval_status = "N"
    record.l1_approval_dt = None
    record.l1_user_id = None
    # A fresh (re)submission is a clean slate — any earlier "reopened for
    # approver editing" state from a prior cycle no longer applies here.
    record.opened_for_revision_by = None
    record.opened_for_revision_dt = None
    record.revision_note = None
    record.mod_user_id = user_id
    record.mod_dt = timezone.now()


def approve(record, user_id):
    record.l1_approval_status = "A"
    record.l1_approval_dt = timezone.localdate()
    record.l1_user_id = user_id
    record.mod_user_id = user_id
    record.mod_dt = timezone.now()


def reject(record, user_id):
    """Terminal — once l1_approval_status is 'R', can_approve/can_reject/
    can_revise_self/can_revise_previous all become false for this record."""
    record.l1_approval_status = "R"
    record.l1_approval_dt = timezone.localdate()
    record.l1_user_id = user_id
    record.mod_user_id = user_id
    record.mod_dt = timezone.now()


def revise_self(record, user_id):
    """Approver undoes their own decision — only L1 fields move, Cr_Status
    is untouched (faithful to the legacy trigger, which never touched it
    here either)."""
    record.l1_approval_status = "N"
    record.l1_approval_dt = None
    record.l1_user_id = None
    record.opened_for_revision_by = user_id
    record.opened_for_revision_dt = timezone.localdate()
    record.mod_user_id = user_id
    record.mod_dt = timezone.now()


def revise_previous(record, user_id, note=None):
    """Approver sends the record back to the creator. Only Cr_Status moves —
    L1_Approval_Status is left as 'N' (its value going into this gate,
    per can_revise_previous), so once the creator refinalizes the record
    reappears in the approver's queue automatically without a separate
    reset. Faithful to the legacy trigger's own field-level behavior.
    revision_note is a new, app-only addition (no legacy column) — a short
    free-text explanation of what needs fixing, cleared on the next
    finalize alongside opened_for_revision_by/dt."""
    record.cr_status = "N"
    record.opened_for_revision_by = user_id
    record.opened_for_revision_dt = timezone.localdate()
    record.revision_note = (note or "").strip()[:500] or None
    record.mod_user_id = user_id
    record.mod_dt = timezone.now()
