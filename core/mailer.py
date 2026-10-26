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


def _send_via(subject, body, to, cc, bcc, from_email, auth_user, auth_password, is_html, attachments):
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
    for filename, content, mimetype in attachments or []:
        message.attach(filename, content, mimetype)
    if settings.EMAIL_USE_CONSOLE:
        # Bcc is deliberately never a header on the real message (that's
        # correct SMTP behaviour, not a bug) — the console backend's own dump
        # of the message therefore never shows it, and Cc can be easy to miss
        # among a long header block. Print the actual envelope explicitly so
        # console-mode testing shows the full picture.
        print(f"--- Envelope: To={to or []} Cc={cc or []} Bcc={bcc or []} ---")
        if attachments:
            print(f"--- Attachments: {[a[0] for a in attachments]} ---")
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
    attachments=None,
):
    """Best-effort: a failed send is logged, never raised — a notification
    that doesn't go out shouldn't break the action (finalize/approve/etc.)
    that triggered it.

    attachments, if given, is a list of (filename, content_bytes,
    mimetype) tuples — plain values, same as everything else this function
    takes, so a caller building one (e.g. a rendered PDF) must do so before
    handing off to queue_notification_email's background thread.

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
                _send_via(subject, body, to, cc, bcc, from_email, auth_user, auth_password, is_html, attachments)
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
                    attachments,
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
            attachment_names=", ".join(a[0] for a in (attachments or [])),
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


# ── Scheduled (automatic) mail ───────────────────────────────────────────────────────────────────────────────────────────────

_sched_log = logging.getLogger("seros.scheduler")


def designated_smtp():
    """The sending account set up for the birthday mail in the environment (BIRTHDAY_EMAIL_*), or None when it is not set."""
    if not settings.BIRTHDAY_EMAIL_HOST:
        return None
    user = settings.BIRTHDAY_EMAIL_USER
    return {
        "host": settings.BIRTHDAY_EMAIL_HOST, "port": settings.BIRTHDAY_EMAIL_PORT, "user": user or None,
        "password": settings.BIRTHDAY_EMAIL_PASSWORD or None, "use_tls": settings.BIRTHDAY_EMAIL_USE_TLS,
        "use_ssl": settings.BIRTHDAY_EMAIL_USE_SSL,
        "from_address": settings.BIRTHDAY_EMAIL_FROM or (user if user and "@" in user else settings.DEFAULT_FROM_EMAIL),
    }


def default_smtp():
    """The default account (EMAIL_HOST...), the one the rest of the application falls back to."""
    return {
        "host": settings.EMAIL_HOST, "port": settings.EMAIL_PORT, "user": settings.EMAIL_HOST_USER or None,
        "password": settings.EMAIL_HOST_PASSWORD or None, "use_tls": settings.EMAIL_USE_TLS, "use_ssl": settings.EMAIL_USE_SSL,
        "from_address": settings.DEFAULT_FROM_EMAIL,
    }


def _build_scheduled_message(subject, html, text, to, cc, bcc, from_name, from_address, inline_images, connection):
    from email.mime.image import MIMEImage
    from email.utils import formataddr

    from django.core.mail import EmailMultiAlternatives

    msg = EmailMultiAlternatives(
        subject=subject, body=text, from_email=formataddr((from_name, from_address)) if from_name else from_address,
        to=to or None, cc=cc or None, bcc=bcc or None, connection=connection,
    )
    msg.attach_alternative(html, "text/html")
    if inline_images:
        msg.mixed_subtype = "related"  # the picture belongs to the page, not a separate attachment
        for cid, data, subtype in inline_images:
            img = MIMEImage(data, _subtype=subtype)
            img.add_header("Content-ID", f"<{cid}>")
            img.add_header("Content-Disposition", "inline", filename=f"{cid}.{subtype}")
            msg.attach(img)
    return msg


def _deliver(subject, html, text, to, cc, bcc, from_name, smtp, inline_images):
    """One send through one account. Raises on any failure."""
    connection = get_connection(
        host=smtp["host"], port=smtp["port"], username=smtp["user"], password=smtp["password"],
        use_tls=smtp["use_tls"], use_ssl=smtp["use_ssl"], fail_silently=False,
    )
    msg = _build_scheduled_message(subject, html, text, to, cc, bcc, from_name, smtp["from_address"], inline_images, connection)
    if settings.EMAIL_USE_CONSOLE:
        print(f"--- Envelope: To={to or []} Cc={cc or []} Bcc={bcc or []} ---")
    msg.send()


def _html_for_log(html, inline_images):
    """The mail's HTML as kept in the Email Log. A picture sent inside the mail (src="cid:...") cannot be shown by the log page, so it is replaced
    by a small copy of the picture (a data address of about 20 KB), which lets the log show what was sent."""
    try:
        import base64
        import io

        from PIL import Image

        for cid, data, _sub in inline_images or []:
            img = Image.open(io.BytesIO(data)).convert("RGB")
            img.thumbnail((480, 480))
            out = io.BytesIO()
            img.save(out, "JPEG", quality=70, optimize=True)
            html = html.replace(f"cid:{cid}", "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode("ascii"))
    except Exception:
        _sched_log.warning("could not make a log preview of the inline picture", exc_info=True)
    return html


def send_scheduled_email(subject, html, text, to=None, cc=None, bcc=None, from_name="", inline_images=None, trigger="", trigger_code="", designated=True):
    """Sends one automatic mail: with the designated account first (when one is set and `designated` is true), and straight away with the default
    account if that fails. Always writes ONE EmailLog row for the attempt, success or failure, and logs any failure to the scheduler logs.

    Returns {"ok", "smtp_used" ('designated', 'default' or ''), "error", "email_log_id"}. Never raises."""
    from .models import EmailLog

    to, cc, bcc = ([a for a in (x or []) if a] for x in (to, cc, bcc))
    recipients_display = ", ".join([*to, *(f"cc:{a}" for a in cc), *(f"bcc:{a}" for a in bcc)])
    attempts = []
    if designated and designated_smtp():
        attempts.append(("designated", designated_smtp()))
    attempts.append(("default", default_smtp()))

    ok, used, errors = False, "", []
    if not (to or cc or bcc):
        errors.append("No recipients")
    else:
        for label, smtp in attempts:
            try:
                _deliver(subject, html, text, to, cc, bcc, from_name, smtp, inline_images)
                ok, used = True, label
                break
            except Exception as exc:
                errors.append(f"{label} SMTP ({smtp['host']}:{smtp['port']}) failed: {exc}")
                _sched_log.error("scheduled mail %r: %s", trigger_code or subject, errors[-1], exc_info=True)
    error = "; ".join(errors) if not ok else ""
    if ok and errors:
        _sched_log.warning("scheduled mail %r went out with the %s account after: %s", trigger_code or subject, used, "; ".join(errors))
    if not ok and errors == ["No recipients"]:
        _sched_log.error("scheduled mail %r has no recipients: nothing was sent", trigger_code or subject)

    log_id = None
    try:
        row = EmailLog.objects.create(
            subject=subject[:200], body=_html_for_log(html, inline_images), recipients=recipients_display, trigger=trigger[:200], trigger_code=trigger_code[:100], success=ok,
            error=error or ("; ".join(errors) if errors else ""), used_fallback=bool(ok and used == "default" and designated and designated_smtp()),
            attachment_names=", ".join(f"{cid}.{sub}" for cid, _, sub in (inline_images or [])), sent_by_user_id=None,
        )
        log_id = row.pk
    except Exception:
        _sched_log.exception("EmailLog write failed for scheduled mail %r", subject)
    return {"ok": ok, "smtp_used": used, "error": error, "email_log_id": log_id}
