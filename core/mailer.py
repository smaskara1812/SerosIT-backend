"""Outgoing email — one call site for every notification this app sends.

Callers never branch on console-vs-real: that's entirely decided by
EMAIL_USE_CONSOLE (settings.py), which swaps Django's EMAIL_BACKEND between
the console backend (prints to the terminal running the backend) and the
real SMTP backend.

Two entry points:
    send_notification_email()  — synchronous, does the actual send + retry
                                  + EmailLog write. Use directly only from
                                  somewhere that's already off the request
                                  thread (e.g. a management command).
    queue_notification_email() — what everything else should call: fires
                                  send_notification_email() on a background
                                  thread so a slow/unreachable SMTP server
                                  never makes a Finalize/Approve/etc request
                                  hang waiting on it.
"""

import logging
import threading

from django.conf import settings
from django.core.mail import EmailMessage, get_connection

logger = logging.getLogger(__name__)


def _send_via(subject, body, to, cc, bcc, from_email, auth_user, auth_password, is_html):
    connection = get_connection(username=auth_user, password=auth_password, fail_silently=False)
    message = EmailMessage(
        subject=subject,
        body=body,
        from_email=from_email,
        to=to or None,
        cc=cc or None,
        bcc=bcc or None,
        connection=connection,
    )
    if is_html:
        message.content_subtype = "html"
    if settings.EMAIL_USE_CONSOLE:
        # Bcc is deliberately never a header on the real message (that's
        # correct SMTP behaviour, not a bug) — the console backend's own dump
        # of the message therefore never shows it, and Cc can be easy to miss
        # among a long header block. Print the actual envelope explicitly so
        # console-mode testing shows the full picture.
        print(f"--- Envelope: To={to or []} Cc={cc or []} Bcc={bcc or []} ---")
    message.send()


def send_notification_email(
    subject,
    body,
    to=None,
    cc=None,
    bcc=None,
    from_email=None,
    auth_user=None,
    auth_password=None,
    trigger="",
    trigger_code="",
    sent_by_user_id=None,
    is_html=False,
):
    """Best-effort: a failed send is logged, never raised — a notification
    that doesn't go out shouldn't break the action (finalize/approve/etc.)
    that triggered it.

    Tries (auth_user, auth_password, from_email) first — normally the
    acting user's own cached AD credential and address. If that's missing
    or the send fails for any reason, retries once through the shared
    Oilfield Services fallback account (settings.EMAIL_HOST_USER/PASSWORD),
    with From switched to that account's own address — the relay only
    allows sending From an address that matches whoever it authenticated,
    confirmed against the real server, so the fallback can't keep the
    original From.

    Every attempt — success or failure — writes an EmailLog row (the Admin
    "Email Log" page reads straight off this table, including whether the
    fallback identity ended up being used)."""
    from .models import EmailLog

    to = [a for a in (to or []) if a]
    cc = [a for a in (cc or []) if a]
    bcc = [a for a in (bcc or []) if a]
    recipients_display = ", ".join([*to, *(f"cc:{a}" for a in cc), *(f"bcc:{a}" for a in bcc)])

    success = False
    used_fallback = False
    error = ""

    if not (to or cc or bcc):
        error = "No recipients"
    else:
        if auth_user and auth_password:
            try:
                _send_via(subject, body, to, cc, bcc, from_email, auth_user, auth_password, is_html)
                success = True
            except Exception as exc:
                logger.warning("send_notification_email primary send failed, retrying via fallback SMTP: %s", exc)
                error = f"Primary send failed: {exc}"
        else:
            error = "No cached mail credential for sender"

        if not success:
            try:
                _send_via(
                    subject,
                    body,
                    to,
                    cc,
                    bcc,
                    settings.DEFAULT_FROM_EMAIL,
                    settings.EMAIL_HOST_USER or None,
                    settings.EMAIL_HOST_PASSWORD or None,
                    is_html,
                )
                success = True
                used_fallback = True
                error = ""
            except Exception as exc2:
                logger.exception("send_notification_email failed on both primary and fallback sends")
                error = f"{error + '; ' if error else ''}Fallback send failed: {exc2}"

    try:
        EmailLog.objects.create(
            subject=subject,
            body=body,
            recipients=recipients_display,
            trigger=trigger,
            trigger_code=trigger_code,
            success=success,
            error=error,
            used_fallback=used_fallback,
            sent_by_user_id=sent_by_user_id,
        )
    except Exception:
        logger.exception("EmailLog write failed for subject=%r", subject)

    return success


def queue_notification_email(**kwargs):
    """Fire-and-forget. Every kwarg must already be a plain value (email
    addresses, strings, ids) — never a request/session/queryset — since the
    background thread runs after this function returns, by which point the
    request that triggered it may already be torn down."""
    from django.db import close_old_connections

    def _run():
        try:
            send_notification_email(**kwargs)
        finally:
            close_old_connections()

    threading.Thread(target=_run, daemon=True).start()
