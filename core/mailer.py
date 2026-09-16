"""Outgoing email — one call site for every notification this app sends.

Callers never branch on console-vs-real: that's entirely decided by
EMAIL_USE_CONSOLE (settings.py), which swaps Django's EMAIL_BACKEND between
the console backend (prints to the terminal running the backend) and the
real SMTP backend. This module just wraps django.core.mail so a future
caller (e.g. the Drilling Report approval-notification resolver) has one
place to call rather than importing Django's mail module directly."""

import logging

from django.core.mail import send_mail as _django_send_mail

logger = logging.getLogger(__name__)


def send_notification_email(subject, body, recipient_list, from_email=None, trigger="", sent_by_user_id=None):
    """Best-effort: a failed send is logged, never raised — a notification
    that doesn't go out shouldn't break the action (finalize/revise/etc.)
    that triggered it, same reasoning as audit.record_action's own
    swallow-and-log pattern.

    Every attempt — success or failure — writes an EmailLog row (the Admin
    "Email Log" page reads straight off this table), so a silently-failed
    send is still visible somewhere even though the caller never sees it."""
    from .models import EmailLog

    recipient_list = [r for r in recipient_list if r]
    error = ""
    success = False
    if not recipient_list:
        error = "No recipients"
    else:
        try:
            _django_send_mail(
                subject=subject,
                message=body,
                from_email=from_email,
                recipient_list=recipient_list,
                fail_silently=False,
            )
            success = True
        except Exception as exc:
            logger.exception("send_notification_email failed: subject=%r to=%r", subject, recipient_list)
            error = str(exc)

    try:
        EmailLog.objects.create(
            subject=subject,
            body=body,
            recipients=", ".join(recipient_list),
            trigger=trigger,
            success=success,
            error=error,
            sent_by_user_id=sent_by_user_id,
        )
    except Exception:
        logger.exception("EmailLog write failed for subject=%r", subject)

    return success
