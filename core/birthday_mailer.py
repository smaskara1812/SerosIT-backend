"""The Birthday Mailer: who has a birthday, the picture the name is drawn on, and the mail that goes out.

What decides what, so nothing here is hardcoded:
  * Which alert the mail belongs to, and whether it is on: ONE row of the Notification Triggers table, (entity_key "automation.birthday",
    action "send"), pointing at an alert (alert 247, "Happy Birthday !!!"). Switching that row off stops the mail.
  * Who receives it: the alert's active rows in Alert To Users (To, Cc, Bcc), exactly as for every other alert. The celebrant is not a recipient.
  * When it goes: the alert's start hour (07:00), every day, by the hourly scheduler (core/scheduler.py).
  * The From name and the subject: the alert's display name and subject. A {name} in the subject becomes the person's name.
  * The sending account: BIRTHDAY_EMAIL_* in the environment, then the default account (core/mailer.py).
The people and the pictures are kept on the Birthday Mailer page itself: no link to the users table.
"""

import calendar
import datetime
import io
import logging
import os
import random

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from . import mailer
from .sched_base import JobBase
from .models import BirthdayPerson, BirthdayTemplate, MailAlertDtl, NotificationTrigger, SchedItem, SchedJob
from .notification_triggers import resolve_alert_recipients

log = logging.getLogger("seros.scheduler")

JOB_KEY = "birthday"
ENTITY_KEY = "automation.birthday"
ACTION = "send"
TRIGGER_CODE = "auto.birthday"
DEFAULT_ALERT_ID = 247
FONT_DIR = os.path.join(os.path.dirname(__file__), "birthday_fonts")
FONTS = {  # key -> (label, file)
    "poppins": ("Poppins Bold (clean, modern)", "poppins.ttf"),
    "playfair": ("Playfair Display Bold (elegant serif)", "playfair.ttf"),
    "pacifico": ("Pacifico (friendly script)", "pacifico.ttf"),
}
CASES = ("asis", "upper", "title")
ALIGN_H = ("left", "center", "right")
ALIGN_V = ("top", "middle", "bottom")
FOLDER = "birthday_templates"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_SIDE = 2400  # a larger picture is shrunk to this on upload
MAIL_WIDTH = 900  # the picture is sent at this width: big enough to look good, small enough for e-mail
MAX_PIXELS = 40_000_000
MAX_NAME = 60  # characters of a name shown on a card


# ── people ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def birthday_on(person, year):
    """The day this person's birthday falls on in `year`. 29 February is kept on 28 February in a year that has none."""
    m, d = person.birth_month, person.birth_day
    if m == 2 and d == 29 and not calendar.isleap(year):
        d = 28
    return datetime.date(year, m, d)


def is_active_on(person, day):
    """Active until the leaving date, which is the last day (blank = still here)."""
    return person.leaving_date is None or day <= person.leaving_date


def people_with_birthday(day):
    """The active people whose birthday is `day`."""
    out = []
    for p in BirthdayPerson.objects.filter(Q(birth_month=day.month, birth_day=day.day) | Q(birth_month=2, birth_day=29)):
        if birthday_on(p, day.year) == day and is_active_on(p, day):
            out.append(p)
    return out


# ── the picture ──────────────────────────────────────────────────────────────────────────────────────────────────────────────

class TemplateError(Exception):
    """A problem with an uploaded picture, worded for the person who sent it."""


def process_template_upload(data, filename=""):
    """The bytes of a sent file -> (PNG bytes, width, height). JPG, JPEG or PNG, up to 5 MB; its content is checked and it is re-encoded, which
    removes hidden data."""
    from PIL import Image, ImageOps

    if len(data) > MAX_UPLOAD_BYTES:
        raise TemplateError(f"That file is {len(data) / 1048576:.1f} MB. A template can be at most {MAX_UPLOAD_BYTES // 1048576} MB.")
    ext = os.path.splitext(filename or "")[1].lower()
    if ext and ext not in (".png", ".jpg", ".jpeg"):
        raise TemplateError("A template must be a PNG (or a JPG or JPEG) picture.")
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        probe = Image.open(io.BytesIO(data))
        fmt = probe.format
        probe.verify()
        img = Image.open(io.BytesIO(data))
        if img.size[0] * img.size[1] > MAX_PIXELS:
            raise TemplateError("That picture has too many pixels. Reduce its size and try again.")
        img.load()
    except TemplateError:
        raise
    except Exception:
        raise TemplateError("That file is not a picture that can be read. Use a PNG, JPG or JPEG.")
    if fmt not in ("PNG", "JPEG"):
        raise TemplateError("A template must be a PNG (or a JPG or JPEG) picture.")
    img = ImageOps.exif_transpose(img)
    if min(img.size) < 100:
        raise TemplateError("That picture is too small to use as a template.")
    has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
    img = img.convert("RGBA" if has_alpha else "RGB")
    if max(img.size) > MAX_SIDE:
        k = MAX_SIDE / max(img.size)
        img = img.resize((round(img.size[0] * k), round(img.size[1] * k)), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue(), img.size[0], img.size[1]


THUMB_SIDE = 320  # the list shows each template at this size: low resolution on purpose, so the page stays light


def make_thumb(png_bytes):
    """A small, low-resolution copy of a template picture as a data address (about 10 KB), for the list of templates."""
    import base64

    from PIL import Image

    img = Image.open(io.BytesIO(png_bytes))
    has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
    img.thumbnail((THUMB_SIDE, THUMB_SIDE))
    out = io.BytesIO()
    if has_alpha:
        img.convert("RGBA").quantize(64, method=Image.Quantize.FASTOCTREE).save(out, "PNG", optimize=True)
        mime = "image/png"
    else:
        img.convert("RGB").save(out, "JPEG", quality=50, optimize=True, progressive=True)
        mime = "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(out.getvalue()).decode("ascii")


def template_path(t):
    return os.path.join(settings.MEDIA_ROOT, t.file_path)


def _font(key, size):
    from PIL import ImageFont

    return ImageFont.truetype(os.path.join(FONT_DIR, FONTS.get(key, FONTS["poppins"])[1]), size)


def display_text(name, case):
    name = " ".join((name or "").split())[:MAX_NAME]
    if case == "upper":
        return name.upper()
    if case == "title":
        return name.title()
    return name


def _line_metrics(font):
    asc, desc = font.getmetrics()
    return asc + desc


LEAD = 0.88  # a second and later line sits this fraction of a full line height below the one before, so wrapped names stay tight


def _block_height(font, n):
    lh = _line_metrics(font)
    return lh + (n - 1) * lh * LEAD


def _balanced(words, n, font, draw, box_w):
    """Splits the words into exactly n lines, none wider than box_w, with the widest line as narrow as it can be (so two lines are of about equal
    length rather than one long and one short). Returns the lines, or None when it cannot be done (a single word is wider than the box)."""
    m = len(words)
    if n > m:
        return None
    width = {}
    for i in range(m):
        for j in range(i + 1, m + 1):
            width[(i, j)] = draw.textlength(" ".join(words[i:j]), font=font)
    inf = float("inf")
    best = [[inf] * (m + 1) for _ in range(n + 1)]
    cut = [[0] * (m + 1) for _ in range(n + 1)]
    best[0][0] = 0
    for k in range(1, n + 1):
        for j in range(k, m + 1):
            for i in range(k - 1, j):
                w = width[(i, j)]
                if w > box_w:
                    continue
                cost = max(best[k - 1][i], w)
                if cost < best[k][j]:
                    best[k][j], cut[k][j] = cost, i
    if best[n][m] == inf:
        return None
    lines, j = [], m
    for k in range(n, 0, -1):
        i = cut[k][j]
        lines.append(" ".join(words[i:j]))
        j = i
    return lines[::-1]


def _ellipsis(text, font, draw, box_w):
    if draw.textlength(text, font=font) <= box_w:
        return text
    while text and draw.textlength(text + "…", font=font) > box_w:
        text = text[:-1]
    return text.rstrip() + "…"


def fit_text(draw, text, font_key, box_w, box_h, size_max, size_min):
    """Finds the biggest size (from size_max down to size_min) at which the name fits the box, on as FEW lines as will fit its width, using as many
    lines as the box is tall enough for. If even size_min is not small enough (a single word wider than the box, or a box too short for the lines
    needed) the size keeps going down to half of size_min rather than cut the name; the caller can see that from the size. Returns (size, lines,
    truncated): only when even that smallest size fails is the name cut with an ellipsis, and truncated is True."""
    words = text.split(" ")
    floor = max(10, size_min // 2)
    for size in range(size_max, floor - 1, -2):
        font = _font(font_key, size)
        lh = _line_metrics(font)
        if lh > box_h:
            continue
        max_lines = 1 + int((box_h - lh) // (lh * LEAD))
        for n in range(1, min(max_lines, len(words)) + 1):
            lines = _balanced(words, n, font, draw, box_w)
            if lines:
                return size, lines, False
    # nothing fits at any size: show as much as fits at the very smallest size, and cut the last line
    font = _font(font_key, floor)
    lh = _line_metrics(font)
    max_lines = max(1, 1 + int((box_h - lh) // (lh * LEAD))) if box_h >= lh else 1
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= box_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    lines.append(cur)
    cut = len(lines) > max_lines or any(draw.textlength(l, font=font) > box_w for l in lines)  # too many lines, or a word wider than the box
    if cut:
        too_many = len(lines) > max_lines
        lines = lines[:max_lines]
        lines = [_ellipsis(l, font, draw, box_w) for l in lines[:-1]] + [_ellipsis(lines[-1] + ("…" if too_many else ""), font, draw, box_w)]
    return floor, lines, cut


def render_card(template, name, max_width=MAIL_WIDTH):
    """The template picture with `name` drawn in the marked box. Returns (PNG bytes, {"size", "lines", "truncated", "width", "height"})."""
    from PIL import Image, ImageDraw

    img = Image.open(template_path(template)).convert("RGBA")
    W, H = img.size
    box_x, box_y, box_w, box_h = (template.box_x * W, template.box_y * H, template.box_w * W, template.box_h * H)
    draw = ImageDraw.Draw(img)
    text = display_text(name, template.text_case)
    size, lines, truncated = fit_text(draw, text, template.font, box_w, box_h, template.size_max, template.size_min)
    font = _font(template.font, size)
    line_h = _line_metrics(font)
    block_h = _block_height(font, len(lines))
    y = box_y + {"top": 0, "middle": (box_h - block_h) / 2, "bottom": box_h - block_h}.get(template.align_v, (box_h - block_h) / 2)
    for line in lines:
        w = draw.textlength(line, font=font)
        x = box_x + {"left": 0, "center": (box_w - w) / 2, "right": box_w - w}.get(template.align_h, (box_w - w) / 2)
        draw.text((x, y), line, font=font, fill=template.color)
        y += line_h * LEAD
    if W > max_width:
        img = img.resize((max_width, round(H * max_width / W)), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue(), {"size": size, "lines": lines, "truncated": truncated, "below_min": size < template.size_min, "width": img.size[0], "height": img.size[1]}


def pick_template():
    """The active template used longest ago (never used first; a tie is settled at random), so the pictures take turns."""
    active = list(BirthdayTemplate.objects.filter(is_active="Y").order_by("last_used_at", "template_id"))
    if not active:
        return None
    oldest = active[0].last_used_at
    return random.choice([t for t in active if t.last_used_at == oldest])


# ── the setup the page shows, and the mail ───────────────────────────────────────────────────────────────────────────────────

def ensure_setup(alert_id=DEFAULT_ALERT_ID, fix_subject=True):
    """Makes sure the trigger row and the job row exist (safe to run again). The trigger points at alert 247; the alert's subject gets a {name}
    marker so the mail says "Happy Birthday <name>". Returns what it did, as a list of words."""
    did = []
    SchedJob.objects.get_or_create(job_key=JOB_KEY, defaults={"name": "Birthday Mailer", "enabled": "Y"})
    alert = MailAlertDtl.objects.filter(pk=alert_id).first()
    if alert is None:
        return did
    if not NotificationTrigger.objects.filter(entity_key=ENTITY_KEY, action=ACTION).exists():
        NotificationTrigger.objects.create(entity_key=ENTITY_KEY, action=ACTION, alert=alert, notification_trigger_active="Y", cr_user_id=0, cr_dt=timezone.now())
        did.append("trigger row created")
    if fix_subject and "{name}" not in (alert.mail_subject or ""):
        MailAlertDtl.objects.filter(pk=alert.pk).update(mail_subject="Happy Birthday {name}")
        did.append("alert subject set to 'Happy Birthday {name}'")
    return did


def get_setup(today=None):
    """Everything the Birthday Mailer page shows about how the mail is set up, read from the trigger, the alert and the environment."""
    today = today or datetime.date.today()
    trig = NotificationTrigger.objects.filter(entity_key=ENTITY_KEY, action=ACTION).select_related("alert").first()
    out = {
        "trigger_found": bool(trig), "trigger_active": bool(trig and trig.notification_trigger_active == "Y"), "alert": None,
        "from_name": "", "subject": "", "send_hour": 7, "recipients": {"to": [], "cc": [], "bcc": []}, "warnings": [],
        "smtp": {"designated": bool(mailer.designated_smtp()), "designated_host": settings.BIRTHDAY_EMAIL_HOST or "", "default_host": settings.EMAIL_HOST, "sender": None},
    }
    if not trig:
        out["warnings"].append("No trigger row connects the Birthday Mailer to an alert. Ask an administrator to add one in Masters > Notification Triggers.")
        return out
    a = trig.alert
    out["alert"] = {"id": a.alert_id, "name": a.alert_name, "active": a.alert_active == "Y"}
    out["subject"] = a.mail_subject or ""
    out["send_hour"] = a.start_time if a.start_time is not None else 7
    out["recipients"] = resolve_alert_recipients(a.alert_id, as_of=today)
    out["smtp"]["sender"] = mailer.sender_info(a.alert_id)
    out["from_name"] = (out["smtp"]["sender"] or {}).get("display_name", "")  # the sender name is kept with the alert's sender account; none = the From address only
    if out["smtp"]["sender"] and out["smtp"]["sender"]["broken"]:
        out["warnings"].append("The sender set for this alert cannot be used: " + out["smtp"]["sender"]["broken"] + ". The next account is used instead.")
    if not out["trigger_active"]:
        out["warnings"].append("The trigger is switched off, so no birthday mail will be sent.")
    if a.alert_active != "Y":
        out["warnings"].append(f"The alert '{a.alert_name}' is switched off.")
    if not any(out["recipients"].values()):
        out["warnings"].append(f"Alert '{a.alert_name}' has no active recipients today, so a birthday mail would have nobody to go to.")
    if not out["smtp"]["sender"] and not out["smtp"]["designated"]:
        out["warnings"].append("No sender is set for this alert (Masters > Alert Senders) and no separate account in the environment, so the default account is used.")
    return out


def _subject(pattern, name):
    pattern = (pattern or "").strip()
    return pattern.replace("{name}", name) if "{name}" in pattern else f"Happy Birthday {name}"


def build_mail(person_name, template, setup, send_date=None):
    """-> (subject, html, text, inline_images, meta) for one person."""
    png, meta = render_card(template, person_name)
    subject = _subject(setup["subject"], display_text(person_name, "asis"))
    alt = f"Happy Birthday {display_text(person_name, 'asis')}"
    html = (
        '<div style="margin:0;padding:0;background:#ffffff;text-align:center">'
        f'<img src="cid:birthday" alt="{alt}" width="{meta["width"]}" style="display:block;margin:0 auto;max-width:100%;height:auto;border:0">'
        "</div>"
    )
    return subject, html, f"{alt}!", [("birthday", png, "png")], meta


def send_for_person(person_name, template, setup, designated=True):
    """Draws the card and sends one mail to the alert's recipients. Returns the mailer's result plus the recipient snapshot."""
    subject, html, text, images, _ = build_mail(person_name, template, setup)
    r = setup["recipients"]
    result = mailer.send_scheduled_email(
        subject, html, text, to=r["to"], cc=r["cc"], bcc=r["bcc"], from_name=setup["from_name"], inline_images=images,
        trigger=f"Birthday: {person_name}"[:200], trigger_code=TRIGGER_CODE, designated=designated,
        alert_id=(setup.get("alert") or {}).get("id"),
    )
    result["recipients"] = ", ".join([*r["to"], *(f"cc:{a}" for a in r["cc"]), *(f"bcc:{a}" for a in r["bcc"])])
    return result


# ── the job the scheduler runs ──────────────────────────────────────────────────────────────────────────────────────────────

class BirthdayJob(JobBase):
    key = JOB_KEY
    name = "Birthday Mailer"

    def plan(self, now, days=7):
        """Makes sure there is an item for every birthday from today to `days` days ahead, and cancels planned ones that no longer apply (the
        person was removed, left, or their birthday changed). Returns {"planned": n, "cancelled": n}."""
        today = now.date()
        setup_hour = get_setup(today)["send_hour"]
        planned = cancelled = 0
        wanted = {}
        for i in range(days + 1):
            day = today + datetime.timedelta(days=i)
            for p in people_with_birthday(day):
                wanted[(str(p.person_id), day)] = p
        for (subject_key, day), p in wanted.items():
            due = datetime.datetime.combine(day, datetime.time(hour=setup_hour))
            item, created = SchedItem.objects.get_or_create(
                job_key=JOB_KEY, subject_key=subject_key, send_date=day,
                defaults={"label": p.shown_name, "due_at": due, "status": "planned", "cr_dt": now},
            )
            if created:
                planned += 1
            elif item.status in ("planned", "failed") and (item.label != p.shown_name or item.due_at != due):
                SchedItem.objects.filter(pk=item.pk).update(label=p.shown_name, due_at=due, mod_dt=now)
        for item in SchedItem.objects.filter(job_key=JOB_KEY, status="planned", send_date__gte=today, send_date__lte=today + datetime.timedelta(days=days)):
            if (item.subject_key, item.send_date) not in wanted:
                SchedItem.objects.filter(pk=item.pk).update(status="cancelled", note="The person was removed, has left, or the birthday changed.", mod_dt=now)
                cancelled += 1
        return {"planned": planned, "cancelled": cancelled}

    def _compose_and_send(self, person, now, designated=True):
        """Builds and sends the mail for one person. Returns (error, result, template); error is "" when the mail went."""
        setup = get_setup(now.date())
        result = template = None
        error = ""
        if not setup["trigger_found"] or not setup["trigger_active"]:
            error = "The trigger for the birthday mail is missing or switched off."
        elif not setup["alert"]["active"]:
            error = f"The alert '{setup['alert']['name']}' is switched off. Tick Active on it in Masters > Alert Details."
        elif not any(setup["recipients"].values()):
            error = f"The alert has no active recipients on {now.date()}."
        else:
            template = pick_template()
            if template is None:
                error = "There is no active template. Add or switch on a template on the Birthday Mailer page."
            elif not os.path.isfile(template_path(template)):
                error = f"The template picture '{template.name}' is missing from the media folder."
        if not error:
            try:
                result = send_for_person(person.shown_name, template, setup, designated=designated)
                if not result["ok"]:
                    error = result["error"] or "The mail could not be sent."
            except Exception as exc:
                log.exception("birthday mail for %s failed while it was being built", person.shown_name)
                error = f"{type(exc).__name__}: {exc}"
        return error, result, template

    def attempt(self, item, now, designated=True):
        """One try at sending one item. Updates the item and returns True when the mail went."""
        person = BirthdayPerson.objects.filter(pk=int(item.subject_key)).first() if item.subject_key.isdigit() else None
        if person is None:
            SchedItem.objects.filter(pk=item.pk).update(status="cancelled", note="The person is no longer on the list.", mod_dt=now)
            return False
        item.attempts += 1
        error, result, template = self._compose_and_send(person, now, designated)
        fields = {"attempts": item.attempts, "last_attempt_at": now, "mod_dt": now}
        if result:
            fields.update(smtp_used=result["smtp_used"], email_log_id=result["email_log_id"], recipients=result["recipients"][:2000])
        if error:
            fields.update(status="failed", last_error=error[:4000])
            log.error("birthday mail for %s (item %s, attempt %s) failed: %s", person.shown_name, item.pk, item.attempts, error)
            SchedItem.objects.filter(pk=item.pk).update(**fields)
            return False
        fields.update(status="sent", sent_at=now, last_error="", template_id=template.template_id)
        SchedItem.objects.filter(pk=item.pk).update(**fields)
        BirthdayTemplate.objects.filter(pk=template.pk).update(last_used_at=now, times_used=template.times_used + 1)
        log.info("birthday mail for %s sent (item %s, %s account, template %s)", person.shown_name, item.pk, result["smtp_used"], template.name)
        return True

    def resend(self, item, now):
        """Sends an already-sent item again (a new mail, a new Email Log row). The item stays 'sent'. Returns (ok, error)."""
        person = BirthdayPerson.objects.filter(pk=int(item.subject_key)).first() if item.subject_key.isdigit() else None
        if person is None:
            return False, "The person is no longer on the list."
        error, result, template = self._compose_and_send(person, now, True)
        fields = {"mod_dt": now}
        if result:
            fields.update(email_log_id=result["email_log_id"], smtp_used=result["smtp_used"], recipients=result["recipients"][:2000])
        if error:
            fields.update(last_error=f"Resend failed: {error}"[:4000])
            log.error("resend of the birthday mail for %s (item %s) failed: %s", person.shown_name, item.pk, error)
            SchedItem.objects.filter(pk=item.pk).update(**fields)
            return False, error
        fields.update(resend_count=item.resend_count + 1, last_error="", template_id=template.template_id, note=f"Resent {now:%d %b %Y %H:%M}")
        SchedItem.objects.filter(pk=item.pk).update(**fields)
        BirthdayTemplate.objects.filter(pk=template.pk).update(last_used_at=now, times_used=template.times_used + 1)
        log.info("birthday mail for %s resent (item %s)", person.shown_name, item.pk)
        return True, ""


JOB = BirthdayJob()
