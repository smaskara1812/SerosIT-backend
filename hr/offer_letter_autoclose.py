"""Closes an offer letter that nobody has touched for a while.

An approved offer letter whose response is still New (the applicant has not answered, and HR has not recorded one) and that has not been changed for
INACTIVE_DAYS days is closed by the system: its response becomes Closed and, as for any response, the applicant's status becomes Closed. Only an applicant who is still New is touched. "Last change" is the letter's last modification (a save, finalise, approval or response), or its creation date if it was never changed.
The letter carries auto_closed_dt, so the page can say it was closed automatically because of inactivity; HR can still set another response afterwards, which
clears that note. Drafts, letters awaiting approval and letters sent back are left alone: nobody has offered anything to the applicant yet.

Runs from the scheduler at every tick (core/scheduler.py, after the mail jobs; it does nothing when there is nothing to close) and by hand:

    python manage.py close_stale_offer_letters --dry-run
    python manage.py close_stale_offer_letters --days 30

Switch off with OFFER_LETTER_AUTOCLOSE_DAYS=0 in .env; change the period with another number.
"""

import datetime
import logging

from django.conf import settings
from django.db import transaction
from django.db.models import Q

from core import audit as _audit
from hr.models import FsNewApplDtl, FsOfferLetter

log = logging.getLogger("seros.scheduler")
INACTIVE_DAYS = 30  # the default; settings.OFFER_LETTER_AUTOCLOSE_DAYS (.env) overrides it, 0 switches the job off
ENTITY_KEY = "hr.fs_offer_letters"


def note_text(days=INACTIVE_DAYS):
    return f"Closed automatically due to inactivity: no change for {days} days."


def configured_days():
    return getattr(settings, "OFFER_LETTER_AUTOCLOSE_DAYS", INACTIVE_DAYS)


def stale_letters(now, days=INACTIVE_DAYS):
    cutoff = now - datetime.timedelta(days=days)
    # the applicant must still be New: one already moved on (Rejected, Closed, Joined) is left exactly as it is
    return (FsOfferLetter.objects.filter(cr_status="F", l1_approval_status="A", auto_closed_dt__isnull=True, fs_new_appl__fs_new_appl_status="N")
            .filter(Q(response_status="N") | Q(response_status=""))
            .filter(Q(mod_dt__lt=cutoff) | Q(mod_dt__isnull=True, cr_dt__lt=cutoff))
            .select_related("fs_new_appl"))


def run(now=None, days=None, dry_run=False):
    """Closes every stale letter. Returns {"closed": n, "skipped_joined": n}. days=None reads the setting; 0 does nothing."""
    now = now or datetime.datetime.now().replace(microsecond=0)
    days = configured_days() if days is None else days
    out = {"closed": 0, "skipped_joined": 0}
    if not days:
        return out
    for letter in list(stale_letters(now, days)):
        applicant = letter.fs_new_appl
        if applicant.fs_new_appl_status == "J":
            out["skipped_joined"] += 1
            continue
        if dry_run:
            out["closed"] += 1
            continue
        old_applicant_status = applicant.fs_new_appl_status
        with transaction.atomic():
            FsOfferLetter.objects.filter(pk=letter.pk).update(response_status="C", auto_closed_dt=now, mod_dt=now)
            FsNewApplDtl.objects.filter(pk=applicant.pk).update(fs_new_appl_status="C", mod_dt=now)
        out["closed"] += 1
        _audit.record_action(None, "update", ENTITY_KEY, letter.pk, f"{applicant} — offer letter {letter.fs_offer_letter_dt}",
                             {"response_status": {"old": letter.response_status or "N", "new": "C"}, "applicant_status": {"old": old_applicant_status, "new": "C"}},
                             target=letter, note=note_text(days))
    if out["closed"] and not dry_run:
        log.info("offer letters: %s closed automatically due to inactivity (%s days)", out["closed"], days)
    return out
