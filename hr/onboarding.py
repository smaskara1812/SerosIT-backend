"""Candidate onboarding invites: the rules shared by the HR side (create, resend, cancel, extend) and the public form (code, session, draft, submit).

The public form is the only part of the system a person without an account can reach, so everything it accepts is whitelisted and size-limited here:
  * the link carries a random token; only its SHA-256 is stored (`token_hash`);
  * a code is mailed to the ONE invited address; it lives 10 minutes, may be sent 3 times an hour, tried 5 times, then the invite locks;
  * after the code a signed form session lets the page save a draft; it ends after 60 minutes without use (each save renews it) and never lasts more than
    12 hours; a new code or a resend ends every older session (the nonce changes);
  * the draft is plain JSON in the invite row, never in the candidate tables, and is capped at 64 KB and to the known fields only.
"""

import hashlib
import json
import logging
import secrets
from datetime import date, timedelta

from django.conf import settings
from django.core import signing
from django.utils import timezone

from core.validation_helpers import EMAIL_MESSAGE, is_valid_email, phone_error  # noqa: F401  (EMAIL_MESSAGE re-exported for the views)

log = logging.getLogger("hr.onboarding")

INVITE_DAYS = 7
OTP_MINUTES = 10
OTP_SENDS_PER_HOUR = 3
OTP_TRIES = 5
SESSION_IDLE_SECONDS = 60 * 60
SESSION_MAX_SECONDS = 12 * 60 * 60
DRAFT_MAX_BYTES = 64 * 1024
MAX_ROWS = 20
SESSION_SALT = "hr.onboarding.session"

# draft key -> (candidate column, max length)   (text fields)
TEXT_FIELDS = {
    "fname": 20, "mname": 20, "lname": 20, "father": 40, "nationality": 25, "mobile": 10, "present_addr": 100, "permanent_addr": 100,
    "qualification": 200, "source": 50, "recommendation": 75,
}
DATE_FIELDS = ("dob",)
INT_FIELDS = {"tot_y": 70, "tot_m": 11, "cur_y": 70, "cur_m": 11}
FLAG_FIELDS = ("no_training", "no_experience", "same_addr")
TRAINING_FIELDS = {"type": 50, "agency": 75, "cert_no": 25, "cert_dt": 10, "valid_from": 10, "valid_to": 10}
EXPERIENCE_FIELDS = {"from": 10, "to": 10, "company": 100, "designation": 25}
# What the progress figure counts: the things a candidate must give.
REQUIRED_FOR_PROGRESS = ("fname", "lname", "father", "dob", "nationality", "mobile", "present_addr", "permanent_addr", "qualification")


# ── token, code, session ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def hash_token(token):
    return hashlib.sha256((token or "").encode()).hexdigest()


def new_token():
    return secrets.token_urlsafe(32)


def _otp_hash(invite, code):
    return hashlib.sha256(f"{invite.pk}:{code}:{settings.SECRET_KEY}".encode()).hexdigest()


def _origin_of(value):
    """'https://host:port' out of an Origin header or a full address, else ''."""
    from urllib.parse import urlsplit

    try:
        parts = urlsplit(value or "")
    except ValueError:
        return ""
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme in ("http", "https") and parts.netloc else ""


def base_url(request=None):
    """The web address candidates open their link on. It is the address of the web app itself, taken from the request HR made it from (the browser's
    Origin, else its Referer), so no setting is needed: the link points to wherever HR is using the system. ONBOARDING_BASE_URL (environment) overrides it
    when HR reaches the system on an internal address but candidates must use a public one. With neither, the first CORS origin, then localhost."""
    configured = (getattr(settings, "ONBOARDING_BASE_URL", "") or "").strip().rstrip("/")
    if configured:
        return configured
    if request is not None:
        found = _origin_of(request.META.get("HTTP_ORIGIN")) or _origin_of(request.META.get("HTTP_REFERER"))
        if found:
            return found
    origins = getattr(settings, "CORS_ALLOWED_ORIGINS", None) or []
    return (origins[0] if origins else "http://localhost:5173").rstrip("/")


def link_for(token, request=None):
    return f"{base_url(request)}/join/{token}"


def new_code():
    return f"{secrets.randbelow(1_000_000):06d}"


def set_code(invite, code):
    invite.otp_hash = _otp_hash(invite, code)
    invite.otp_expires_dt = timezone.now() + timedelta(minutes=OTP_MINUTES)


def code_matches(invite, code):
    if not invite.otp_hash or not invite.otp_expires_dt or invite.otp_expires_dt < timezone.now():
        return False
    return secrets.compare_digest(invite.otp_hash, _otp_hash(invite, (code or "").strip()))


def issue_session(invite, first=None):
    """A signed form session for this invite. `first` is when the first one was issued (the 12-hour cap counts from it)."""
    return signing.dumps({"i": invite.pk, "n": invite.session_nonce, "t0": first or int(timezone.now().timestamp())}, salt=SESSION_SALT)


def read_session(invite, session):
    """The session's first-issue time when it is valid for this invite, else None."""
    try:
        data = signing.loads(session or "", salt=SESSION_SALT, max_age=SESSION_IDLE_SECONDS)
    except signing.BadSignature:
        return None
    if data.get("i") != invite.pk or not invite.session_nonce or data.get("n") != invite.session_nonce:
        return None
    first = int(data.get("t0") or 0)
    if timezone.now().timestamp() - first > SESSION_MAX_SECONDS:
        return None
    return first


def new_nonce():
    return secrets.token_hex(8)


# ── status ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def is_open(invite):
    """Can the public form still be used with this invite?"""
    return not (invite.submitted_dt or invite.cancelled_dt or invite.expires_dt < timezone.now())


def status_of(invite):
    if invite.submitted_dt:
        return "submitted"
    if invite.cancelled_dt:
        return "cancelled"
    if invite.expires_dt < timezone.now():
        return "expired"
    if invite.locked:
        return "locked"
    if invite.draft_saved_dt:
        return "draft"
    if invite.verified_dt:
        return "verified"
    if invite.opened_dt:
        return "opened"
    return "sent"


def mask_email(email):
    name, _, domain = (email or "").partition("@")
    return f"{name[:1]}{'*' * max(2, len(name) - 1)}@{domain}" if domain else "***"


# ── draft ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def _clip(value, limit):
    return str(value if value is not None else "").strip()[:limit]


def _int(value, top):
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        return ""
    return n if 0 <= n <= top else ""


def _date(value):
    text = str(value or "").strip()[:10]
    try:
        date.fromisoformat(text)
        return text
    except ValueError:
        return ""


def clean_draft(raw):
    """Only the known fields, trimmed to their column sizes, rows capped. Anything else is dropped."""
    raw = raw if isinstance(raw, dict) else {}
    out = {k: _clip(raw.get(k), n) for k, n in TEXT_FIELDS.items()}
    out["dob"] = _date(raw.get("dob"))
    out.update({k: _int(raw.get(k), top) for k, top in INT_FIELDS.items()})
    out.update({k: bool(raw.get(k)) for k in FLAG_FIELDS})
    step = raw.get("step")
    out["step"] = step if isinstance(step, int) and 0 <= step <= 20 else 0

    def rows(key, fields):
        result = []
        for row in (raw.get(key) if isinstance(raw.get(key), list) else [])[:MAX_ROWS]:
            if not isinstance(row, dict):
                continue
            clean = {k: _clip(row.get(k), n) for k, n in fields.items()}
            if any(clean.values()):
                for k in ("cert_dt", "valid_from", "valid_to", "from", "to"):
                    if k in clean:
                        clean[k] = _date(clean[k])
                result.append(clean)
        return result

    out["trainings"] = rows("trainings", TRAINING_FIELDS)
    out["experiences"] = rows("experiences", EXPERIENCE_FIELDS)
    return out


def load_draft(invite):
    try:
        return clean_draft(json.loads(invite.draft)) if invite.draft else clean_draft({})
    except ValueError:
        return clean_draft({})


def progress(draft):
    """About how much of the form is done, 0-100 (for HR's list)."""
    got = sum(1 for k in REQUIRED_FOR_PROGRESS if draft.get(k))
    return round(100 * got / len(REQUIRED_FOR_PROGRESS))


# ── mail ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def _send(subject, html, text, to, trigger_code):
    """One automatic mail through the designated sender (same route as the other automatic mails): it is written to the Email Log and follows the
    mail redirect rules like every other automatic mail. Never raises."""
    try:
        from core.mailer import send_scheduled_email

        from . import mail_theme

        result = send_scheduled_email(
            subject, html, text, to=[to], trigger="Rig personnel data request", trigger_code=trigger_code, designated=True, inline_images=mail_theme.logo_image(),
        )
        return bool(result.get("ok"))
    except Exception:
        log.exception("onboarding mail %r failed", trigger_code)
        return False


def send_invite_mail(invite, link):
    from html import escape

    from . import mail_theme as t

    name = invite.candidate_name
    days = max(1, (invite.expires_dt - timezone.now()).days)
    body = (
        f'<p style="margin:0 0 16px 0;font-size:16px;color:{t.NAVY_800};">Dear <b>{escape(name)}</b>,</p>'
        "<p style=\"margin:0 0 6px 0;\">As part of your application, our HR team needs a few details from you. Please share them using the button below. "
        "It takes about 10 minutes, and you can stop and come back whenever you like.</p>"
        + t.button(link, "Fill in my details")
        + f'<p style="margin:26px 0 8px 0;font-size:12px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:{t.OCEAN};">What to expect</p>'
        + t.steps([
            "Open the link and confirm it is you with a code we email to this address.",
            "Answer a few short steps. Your answers are saved as you go.",
            "Send when you are done. Our HR team records your details.",
        ])
        + f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:10px;"><tr><td bgcolor="{t.NAVY_50}" '
        f'style="border:1px solid {t.NAVY_100};border-radius:12px;padding:14px 16px;font-size:13px;line-height:20px;color:{t.GRAPHITE_500};">'
        f"This link works for <b>{days} {'day' if days == 1 else 'days'}</b> and only for this email address. Please do not forward it.<br>"
        f'If the button does not work, copy this address into your browser:<br><a href="{escape(link, quote=True)}" style="color:{t.NAVY_600};word-break:break-all;">{escape(link)}</a>'
        "</td></tr></table>"
        f'<p style="margin:22px 0 0 0;">Regards,<br><b style="color:{t.NAVY_700};">HR team, Seros</b></p>'
    )
    html = t.render("Please share your details", body, preheader="Our HR team needs a few details from you. It takes about 10 minutes.")
    text = (
        f"Dear {name},\n\nAs part of your application, our HR team needs a few details from you. Please share them here: {link}\n\n"
        f"It takes about 10 minutes and you can stop and come back. You will confirm it is you with a code we email to this address.\n"
        f"The link works for {days} {'day' if days == 1 else 'days'}, only for this email address. Do not forward it.\n\nRegards,\nHR team, Seros"
    )
    ok = _send("Seros HR: please share your details", html, text, invite.email_id, "hr.candidate_invite")
    if ok:
        invite.last_mail_dt = timezone.now()
    return ok


def send_code_mail(invite, code):
    from html import escape

    from . import mail_theme as t

    body = (
        f'<p style="margin:0 0 6px 0;font-size:16px;color:{t.NAVY_800};">Dear <b>{escape(invite.candidate_name)}</b>,</p>'
        "<p style=\"margin:0;\">Use this code to confirm it is you and open your form.</p>"
        + t.code_box(code)
        + f'<p style="margin:0;text-align:center;font-size:13px;color:{t.GRAPHITE_500};">The code works for <b>{OTP_MINUTES} minutes</b>.</p>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:24px;"><tr><td bgcolor="{t.NAVY_50}" '
        f'style="border:1px solid {t.NAVY_100};border-radius:12px;padding:14px 16px;font-size:13px;line-height:20px;color:{t.GRAPHITE_500};">'
        "<b>Keep it to yourself.</b> Seros will never ask you for this code. If you did not ask for it, you can ignore this mail."
        "</td></tr></table>"
    )
    html = t.render("Your verification code", body, preheader=f"Your code is {code}. It works for {OTP_MINUTES} minutes.")
    text = f"Dear {invite.candidate_name},\n\nYour code is {code}. It works for {OTP_MINUTES} minutes.\nKeep it to yourself. If you did not ask for it, ignore this mail."
    return _send("Your verification code", html, text, invite.email_id, "hr.candidate_code")


def send_submitted_mail(invite, hdr):
    """The confirmation to the candidate once his details are in: same route as the other onboarding mails (Email Log, mail redirect)."""
    from html import escape

    from . import mail_theme as t

    moment = invite.submitted_dt or timezone.now()
    if timezone.is_aware(moment):  # the project may run with or without time zones; show the server's local time either way
        moment = timezone.localtime(moment)
    when = moment.strftime("%d %b %Y, %H:%M")
    body = (
        f'<p style="margin:0 0 16px 0;font-size:16px;color:{t.NAVY_800};">Dear <b>{escape(invite.candidate_name)}</b>,</p>'
        '<p style="margin:0 0 6px 0;">Thank you. We have received your details, and they are now with our HR team.</p>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:22px 0 4px 0;"><tr>'
        f'<td bgcolor="#ebfaf9" style="border:1px solid #a2e2dc;border-radius:12px;padding:16px 18px;font-size:14px;line-height:22px;color:{t.NAVY_800};">'
        f'<b style="color:#008077;">&#10003; Details received</b><br>Received on {escape(when)}'
        "</td></tr></table>"
        f'<p style="margin:26px 0 8px 0;font-size:12px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:{t.OCEAN};">What happens next</p>'
        + t.steps([
            "Our HR team records and reviews your details and your resume.",
            "We contact you on the mobile number or email you gave if we need anything more.",
            "If your application goes ahead, we will be in touch about the next steps.",
        ])
        + f'<p style="margin:12px 0 0 0;font-size:13px;color:{t.GRAPHITE_500};">You do not need to do anything else, and the link you used no longer works.</p>'
        f'<p style="margin:22px 0 0 0;">Regards,<br><b style="color:{t.NAVY_700};">HR team, Seros</b></p>'
    )
    html = t.render("We have received your details", body, preheader=f"Your details were received on {when}.")
    text = (
        f"Dear {invite.candidate_name},\n\nThank you. We have received your details (received on {when}). "
        "They are now with our HR team, who will get in touch with you.\n\nRegards,\nHR team, Seros"
    )
    return _send("We have received your details", html, text, invite.email_id, "hr.candidate_submitted")
