"""Admin > Holiday Mailer: the festival and holiday pictures, the dates each goes out, the read-only view of how the mail is set up, and a test send.
The rights are the page's own (menu key admin.holiday_mailer): View to see, Add / Edit / Delete to change.

The mail itself is built and sent by core/holiday_mailer.py, on a schedule by core/scheduler.py."""

import datetime
import os

from django.conf import settings
from django.utils import timezone
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import audit as _audit
from . import holiday_mailer as hm, mailer
from .birthday_views import _uid, scheduler_health
from .media_uploads import media_url, next_sequence
from .models import HolidayEvent, SchedItem
from .notice_board import poster_name
from .permissions import holds_a_right_on

MENU_KEY = "admin.holiday_mailer"
TRUE = ("1", "true", "yes", "on", "y")


def _may(request, *flags):
    return holds_a_right_on(request, [MENU_KEY], flags=flags)


def _deny(what="use the Holiday Mailer"):
    return Response({"detail": f"You do not have the right to {what}."}, status=403)


def _row(request, ev, today=None):
    today = today or datetime.date.today()
    nxt = hm.next_send(ev, today)
    n = max(1, min(hm.MAX_DAYS, ev.send_days or 1))
    first = nxt
    if nxt and n > 1:  # the first day of the run that is going on now or comes next
        starts = [ev.send_on] if ev.repeat_yearly != "Y" else [hm._on(y, ev.send_on.month, ev.send_on.day) for y in (nxt.year - 1, nxt.year)]
        for st in starts:
            if st <= nxt < st + datetime.timedelta(days=n):
                first = st
    last = first + datetime.timedelta(days=n - 1) if first else None
    return {
        "id": ev.event_id, "name": ev.name, "subject": ev.subject, "send_on": ev.send_on, "send_days": n, "repeat_yearly": ev.repeat_yearly == "Y",
        "active": ev.is_active == "Y", "note": ev.note, "url": media_url(request, ev.file_path), "thumb": ev.thumb_data, "width": ev.width, "height": ev.height,
        "next_send": nxt, "run_from": first, "run_to": last, "over": nxt is None, "posted_by": ev.posted_by_name or "",
    }


def _clean(raw, base=None):
    """Checks the fields of an event. `raw` may be partial (a change); `base` is the current values. Returns (fields, errors)."""
    b = base or {}
    out, err = {}, {}
    name = " ".join(str(raw.get("name", b.get("name", ""))).split())
    if not name:
        err["name"] = "Give the event a name, for example Diwali."
    elif len(name) > 80:
        err["name"] = "The name can be at most 80 characters."
    out["name"] = name
    subject = " ".join(str(raw.get("subject", b.get("subject", ""))).split())
    if len(subject) > 200:
        err["subject"] = "The subject can be at most 200 characters."
    out["subject"] = subject
    send_on = raw.get("send_on", b.get("send_on"))
    try:
        out["send_on"] = send_on if isinstance(send_on, datetime.date) else datetime.date.fromisoformat(str(send_on)[:10])
    except ValueError:
        err["send_on"] = "Choose the date the mail goes out."
    try:
        days = int(raw.get("send_days", b.get("send_days", 1)))
        if not 1 <= days <= hm.MAX_DAYS:
            raise ValueError
        out["send_days"] = days
    except (TypeError, ValueError):
        err["send_days"] = f"Days must be a whole number from 1 to {hm.MAX_DAYS}."
    flag = lambda k, default: str(raw.get(k, b.get(k, default))).lower() in TRUE
    out["repeat_yearly"] = "Y" if flag("repeat_yearly", False) else "N"
    out["is_active"] = "Y" if flag("active", True) else "N"
    note = " ".join(str(raw.get("note", b.get("note", ""))).split())
    if len(note) > 200:
        err["note"] = "The note can be at most 200 characters."
    out["note"] = note
    return out, err


def _base_of(ev):
    return {"name": ev.name, "subject": ev.subject, "send_on": ev.send_on, "send_days": ev.send_days, "repeat_yearly": ev.repeat_yearly == "Y", "active": ev.is_active == "Y", "note": ev.note}


def _bad(errors):
    return Response({"detail": "; ".join(errors.values()), "errors": errors}, status=400)


def _save_picture(ev, data):
    """Writes the processed picture for `ev` and returns the new relative path. The old file is removed by the caller after the row is updated."""
    rel = f"{hm.FOLDER}/{ev.event_id}_{next_sequence(hm.FOLDER, str(ev.event_id))}.png"
    path = os.path.join(settings.MEDIA_ROOT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)
    return rel


def _process(f):
    try:
        return hm.process_template_upload(f.read(), f.name)
    except hm.TemplateError as exc:
        raise ValueError(str(exc).replace("A template", "A picture").replace("template", "picture"))


def _remove(rel):
    try:
        os.remove(os.path.join(settings.MEDIA_ROOT, rel))
    except OSError:
        pass


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, JSONParser])
def events_api(request):
    """GET ?when=upcoming|over|all &q=<text>: the events. POST (multipart: file, name, subject, send_on, send_days, repeat_yearly, active, note): add one."""
    if request.method == "GET":
        if not _may(request, "view"):
            return _deny()
        today = datetime.date.today()
        rows = [_row(request, ev, today) for ev in HolidayEvent.objects.all()]
        q = request.query_params.get("q", "").strip().lower()
        if q:
            rows = [r for r in rows if q in r["name"].lower() or q in r["subject"].lower()]
        when = request.query_params.get("when", "upcoming")
        counts = {"upcoming": sum(1 for r in rows if not r["over"]), "over": sum(1 for r in rows if r["over"]), "all": len(rows)}
        if when == "upcoming":
            rows = sorted((r for r in rows if not r["over"]), key=lambda r: (r["next_send"], r["name"].lower()))
        elif when == "over":
            rows = sorted((r for r in rows if r["over"]), key=lambda r: (r["send_on"], r["name"].lower()), reverse=True)
        else:
            rows = sorted(rows, key=lambda r: (r["over"], r["next_send"] or datetime.date.max, r["name"].lower()))
        return Response({"results": rows, "counts": counts, "when": when})
    if not _may(request, "add"):
        return _deny("add holiday events")
    f = request.FILES.get("file")
    if not f:
        return Response({"detail": "Choose the finished PNG picture first."}, status=400)
    fields, err = _clean(request.data)
    if err:
        return _bad(err)
    try:
        png, w, h = _process(f)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=400)
    ev = HolidayEvent.objects.create(file_path="x", width=w, height=h, thumb_data=hm.make_thumb(png), posted_by_name=poster_name(request.user), cr_user_id=_uid(request) or 1, cr_dt=timezone.now(), **fields)
    rel = _save_picture(ev, png)
    HolidayEvent.objects.filter(pk=ev.pk).update(file_path=rel)
    ev.refresh_from_db()
    _audit.record_action(request, "create", MENU_KEY, ev.pk, f"Holiday event: {ev.name}", {"send_on": {"old": None, "new": str(ev.send_on)}, "file": {"old": None, "new": rel}})
    return Response(_row(request, ev), status=201)


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser, MultiPartParser])
def event_detail_api(request, event_id):
    """PATCH: change the fields (JSON), and/or replace the picture (multipart with a `file`). DELETE: remove the event and its picture."""
    ev = HolidayEvent.objects.filter(pk=event_id).first()
    if not ev:
        return Response({"detail": "That event no longer exists."}, status=404)
    if request.method == "DELETE":
        if not _may(request, "delete", "edit"):
            return _deny("remove holiday events")
        label, rel = ev.name, ev.file_path
        ev.delete()
        SchedItem.objects.filter(job_key=hm.JOB_KEY, subject_key=str(event_id), status="planned").update(status="cancelled", note="The event was removed.", mod_dt=timezone.now())
        _remove(rel)
        _audit.record_action(request, "delete", MENU_KEY, event_id, f"Holiday event: {label}", {"file": {"old": rel, "new": None}})
        return Response(status=204)
    if not _may(request, "edit"):
        return _deny("change holiday events")
    old = _row(request, ev)
    fields, err = _clean(request.data, _base_of(ev))
    if err:
        return _bad(err)
    f = request.FILES.get("file")
    old_rel = None
    if f:
        try:
            png, w, h = _process(f)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        old_rel = ev.file_path
        fields.update(file_path=_save_picture(ev, png), width=w, height=h, thumb_data=hm.make_thumb(png))
    fields["mod_user_id"], fields["mod_dt"] = _uid(request), timezone.now()
    HolidayEvent.objects.filter(pk=ev.pk).update(**fields)
    if old_rel:
        _remove(old_rel)
    ev.refresh_from_db()
    new = _row(request, ev)
    changes = {k: {"old": old[k], "new": new[k]} for k in new if k not in ("url", "thumb", "next_send", "run_from", "run_to", "over", "posted_by") and old.get(k) != new[k]}
    if f:
        changes["picture"] = {"old": old["url"], "new": "replaced"}
    _audit.record_action(request, "update", MENU_KEY, ev.pk, f"Holiday event: {ev.name}", changes or None)
    return Response(new)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def overview_api(request):
    """What the Holiday Mailer page shows in its 'Mail setup' panel, read from the trigger, the alert and the environment."""
    if not _may(request, "view"):
        return _deny()
    today = datetime.date.today()
    setup = hm.get_setup(today)
    events = list(HolidayEvent.objects.all())
    coming = sorted(((hm.next_send(e, today), e) for e in events if e.is_active == "Y"), key=lambda x: (x[0] or datetime.date.max, x[1].name))
    coming = [(d, e) for d, e in coming if d][:8]
    return Response({
        "setup": setup, "scheduler": scheduler_health(),
        "counts": {"events": len(events), "active": sum(1 for e in events if e.is_active == "Y")},
        "coming": [{"date": d.isoformat(), "name": e.name} for d, e in coming],
        "links": {"trigger": "/masters/notification-triggers", "recipients": f"/masters/mail-alert-to-users?alert={setup['alert']['id']}&alertName={setup['alert']['name']}" if setup.get("alert") else ""},
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def test_send_api(request):
    """Sends ONE event's mail to the address given, and only to it (not to the alert's recipients), to try the picture and the sending account. Needs Edit."""
    if not _may(request, "edit"):
        return _deny("send a test mail")
    import re
    to = (request.data.get("email") or "").strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", to):
        return Response({"detail": "Enter an e-mail address to send the test to."}, status=400)
    ev = HolidayEvent.objects.filter(pk=request.data.get("event_id")).first()
    if ev is None:
        return Response({"detail": "Choose an event to send."}, status=400)
    if not os.path.isfile(hm.picture_path(ev)):
        return Response({"detail": f"The picture for '{ev.name}' is missing from the media folder."}, status=400)
    setup = hm.get_setup()
    subject, html, text, images = hm.build_mail(ev, setup, hm.next_send(ev, datetime.date.today()) or datetime.date.today())
    res = mailer.send_scheduled_email("[Test] " + subject, html, text, to=[to], from_name=setup["from_name"], inline_images=images, trigger=f"Holiday test to {to}", trigger_code="auto.holiday.test", alert_id=(setup.get("alert") or {}).get("id"))
    _audit.record_action(request, "update", MENU_KEY, "test", f"Holiday test mail to {to}", {"result": {"old": None, "new": "sent" if res["ok"] else "failed"}})
    return Response({"ok": res["ok"], "smtp_used": res["smtp_used"], "fell_back": res.get("fell_back", False), "first_choice": res.get("first_choice", ""), "error": res["error"], "event": ev.name, "email_log_id": res["email_log_id"]}, status=200 if res["ok"] else 502)
