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
from html import escape as html_escape

from django.conf import settings
from django.core.mail import EmailMessage, get_connection

logger = logging.getLogger(__name__)


def _intended(to, cc, bcc):
    parts = []
    if to:
        parts.append("To: " + ", ".join(to))
    if cc:
        parts.append("Cc: " + ", ".join(cc))
    if bcc:
        parts.append("Bcc: " + ", ".join(bcc))
    return "; ".join(parts) or "nobody"


def redirect_mail(subject, to, cc, bcc, html=None, text=None):
    """Mail redirect (settings.MAIL_REDIRECT). Returns (subject, to, cc, bcc, html, text, blocked):
    off: everything unchanged. On: the mail goes only to MAIL_REDIRECT_TO (as To, no Cc or Bcc), the subject starts with [Redirected], and the body begins with a notice
    naming who the mail was meant for. On with no address set: blocked is a sentence saying so and nothing may be sent."""
    if not settings.MAIL_REDIRECT:
        return subject, to, cc, bcc, html, text, ""
    if not settings.MAIL_REDIRECT_TO:
        return subject, to, cc, bcc, html, text, "Mail redirect is on (MAIL_REDIRECT) but MAIL_REDIRECT_TO is empty, so nothing was sent."
    meant = _intended(to, cc, bcc)
    note_text = f"[Redirected mail] This mail was meant for: {meant}. It was sent to you instead because mail redirect is switched on for this server.\n\n"
    note_html = (
        '<div style="border:1px solid #e8900c;background:#fff8e6;color:#7c420d;padding:8px 12px;margin:0 0 14px;font:12px Verdana,Tahoma,Arial,sans-serif">'
        f"<b>Redirected mail.</b> This mail was meant for: {html_escape(meant)}. It was sent to you instead because mail redirect is switched on for this server.</div>"
    )
    if html is not None:
        i = html.lower().find("<body")
        j = html.find(">", i) + 1 if i >= 0 else 0
        html = html[:j] + note_html + html[j:]
    if text is not None:
        text = note_text + text
    return f"[Redirected] {subject}", list(settings.MAIL_REDIRECT_TO), [], [], html, text, ""


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
    blocked = ""
    if to or cc or bcc:
        # Mail redirect: on a test machine every mail goes to the addresses in MAIL_REDIRECT_TO only (see redirect_mail)
        if is_html:
            subject, to, cc, bcc, body, _t, blocked = redirect_mail(subject, to, cc, bcc, html=body)
        else:
            subject, to, cc, bcc, _h, body, blocked = redirect_mail(subject, to, cc, bcc, text=body)
    recipients_display = ", ".join([*to, *(f"cc:{a}" for a in cc), *(f"bcc:{a}" for a in bcc)])

    success = False
    used_fallback = False
    error = ""
    from_used = from_email or auth_user or settings.DEFAULT_FROM_EMAIL or ""

    if blocked:
        error = blocked
    elif not (to or cc or bcc):
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
                from_used = settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER or ""
                error = ""
            except Exception as exc2:
                logger.exception("send_notification_email failed on both primary and fallback sends")
                error = f"{error + '; ' if error else ''}Fallback send failed: {exc2}"

    try:
        EmailLog.objects.create(
            subject=subject,
            body=body,
            recipients=recipients_display,
            from_address=(from_used or "")[:200],
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


def alert_sender(alert_id):
    """The account set for this alert in Masters > Alert Senders (its one active row), as the same kind of dict the other accounts are, or None when
    the alert has none. A stored password that cannot be read (the key it was encrypted with is gone) is marked "broken": that account is not used,
    and the next one is tried."""
    if not alert_id:
        return None
    from . import secret_box
    from .models import AlertSenderDtl

    row = AlertSenderDtl.objects.filter(alert_id=alert_id, is_active="Y").order_by("alert_sender_dtl_id").first()
    if row is None:
        return None
    pw = secret_box.decrypt(row.password) if row.password else None
    smtp = {
        "host": row.mail_host, "port": row.mail_port or 25, "user": row.mail_user_name or None, "password": pw or None,
        "use_tls": row.mail_security == "T", "use_ssl": row.mail_security == "S", "from_address": row.from_address,
        "display_name": (row.display_name or "").strip(),
    }
    if row.password and not pw:
        smtp["broken"] = "the stored password could not be read (is CREDENTIAL_KEY the key it was saved with?)"
    return smtp


_NOT_GIVEN = object()


def sender_identity(alert_id, env_account=True, own=_NOT_GIVEN):
    """Who a mail for this alert is sent as, from the first account that would be tried (the alert's own, else the environment's when `env_account`,
    else the default one): {"address": From address, "account": "alert" | "designated" | "default"}. The name next to it is the alert sender's display name
    (see sender_info); with none, the mail shows the address only."""
    if own is _NOT_GIVEN:
        own = alert_sender(alert_id)
    if own:
        return {"address": own["from_address"], "account": "alert"}
    env = designated_smtp() if env_account else None
    if env:
        return {"address": env["from_address"], "account": "designated"}
    return {"address": default_smtp()["from_address"], "account": "default"}


def alert_links(alert_id, alert_name):
    """Quick links for the pages: the alert's recipients (Alert To Users, filtered to this alert) and the alert itself (Alert Details, opened on it)."""
    from urllib.parse import quote

    if not alert_id:
        return {"recipients": "", "alert": ""}
    q = quote(alert_name or "", safe="")
    return {"recipients": f"/masters/mail-alert-to-users?alert={alert_id}&alertName={q}", "alert": f"/masters/mail-alerts?select={alert_id}&q={q}"}


def sender_info(alert_id, own=_NOT_GIVEN):
    """What the setup panels may show about an alert's own account: server, port, user, From address and sender name. Never the password. `own` is the account
    when the caller has already looked it up (alert_sender), so one page does not ask the database for it again and again."""
    a = alert_sender(alert_id) if own is _NOT_GIVEN else own
    if not a:
        return None
    return {"host": a["host"], "port": a["port"], "user": a["user"] or "", "from_address": a["from_address"], "display_name": a.get("display_name", ""), "broken": a.get("broken", "")}


def _build_scheduled_message(subject, html, text, to, cc, bcc, from_name, from_address, inline_images, connection, attachments=None):
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
    for filename, content, mimetype in attachments or []:
        msg.attach(filename, content, mimetype)
    return msg


def _deliver(subject, html, text, to, cc, bcc, from_name, smtp, inline_images, attachments=None):
    """One send through one account. Raises on any failure."""
    if smtp.get("broken"):
        raise RuntimeError(smtp["broken"])
    connection = get_connection(
        host=smtp["host"], port=smtp["port"], username=smtp["user"], password=smtp["password"],
        use_tls=smtp["use_tls"], use_ssl=smtp["use_ssl"], fail_silently=False,
    )
    msg = _build_scheduled_message(subject, html, text, to, cc, bcc, from_name, smtp["from_address"], inline_images, connection, attachments)
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


def send_scheduled_email(subject, html, text, to=None, cc=None, bcc=None, from_name="", inline_images=None, trigger="", trigger_code="", designated=True, alert_id=None, attachments=None, env_account=True):
    """Sends one automatic mail. The accounts are tried in this order, each straight after the one before it fails: the alert's own account (Masters >
    Alert Senders, when `alert_id` is given and it has an active row), the one set in the environment (BIRTHDAY_EMAIL_*, when set), then the default
    account. `designated` false means the default account only; `env_account` false leaves out the one set in the environment (a report that must go through
    the default account still honours an alert's own account). `attachments` is a list of (file name, bytes, mime type). Always writes ONE EmailLog row for the attempt, success or failure, and logs any
    failure to the scheduler logs.

    Returns {"ok", "smtp_used" ('alert', 'designated', 'default' or ''), "error", "email_log_id", "fell_back"}. Never raises."""
    from .models import EmailLog

    to, cc, bcc = ([a for a in (x or []) if a] for x in (to, cc, bcc))
    blocked = ""
    if to or cc or bcc:
        subject, to, cc, bcc, html, text, blocked = redirect_mail(subject, to, cc, bcc, html=html, text=text)  # mail redirect (MAIL_REDIRECT)
    recipients_display = ", ".join([*to, *(f"cc:{a}" for a in cc), *(f"bcc:{a}" for a in bcc)])
    attempts = []
    if designated:
        own = alert_sender(alert_id)
        if own:
            attempts.append(("alert", own))
        if env_account and designated_smtp():
            attempts.append(("designated", designated_smtp()))
    attempts.append(("default", default_smtp()))

    ok, used, errors = False, "", []
    from_used = attempts[0][1]["from_address"]  # the account tried first; replaced by the one that actually sent it
    if blocked:
        errors.append(blocked)
    elif not (to or cc or bcc):
        errors.append("No recipients")
    else:
        for label, smtp in attempts:
            try:
                if attachments:
                    _deliver(subject, html, text, to, cc, bcc, from_name, smtp, inline_images, attachments=attachments)
                else:
                    _deliver(subject, html, text, to, cc, bcc, from_name, smtp, inline_images)
                ok, used, from_used = True, label, smtp["from_address"]
                break
            except Exception as exc:
                errors.append(f"{label} SMTP ({smtp['host']}:{smtp['port']}) failed: {exc}")
                _sched_log.error("scheduled mail %r: %s", trigger_code or subject, errors[-1], exc_info=True)
    error = "; ".join(errors) if not ok else ""
    if ok and errors:
        _sched_log.warning("scheduled mail %r went out with the %s account after: %s", trigger_code or subject, used, "; ".join(errors))
    if not ok and (errors == ["No recipients"] or (blocked and errors == [blocked])):
        _sched_log.error("scheduled mail %r has no recipients: nothing was sent", trigger_code or subject)

    log_id = None
    try:
        row = EmailLog.objects.create(
            subject=subject[:200], body=_html_for_log(html, inline_images), recipients=recipients_display, from_address=(from_used or "")[:200], trigger=trigger[:200], trigger_code=trigger_code[:100], success=ok,
            error=error or ("; ".join(errors) if errors else ""), used_fallback=bool(ok and used != attempts[0][0]),
            attachment_names=", ".join([f"{cid}.{sub}" for cid, _, sub in (inline_images or [])] + [a[0] for a in (attachments or [])])[:300], sent_by_user_id=None,
        )
        log_id = row.pk
    except Exception:
        _sched_log.exception("EmailLog write failed for scheduled mail %r", subject)
    return {"ok": ok, "smtp_used": used, "error": error, "email_log_id": log_id, "fell_back": bool(ok and used != attempts[0][0]), "first_choice": attempts[0][0]}
