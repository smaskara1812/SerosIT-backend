"""Admin > Birthday Mailer: the people list, the templates (the picture the name is drawn on), the read-only view of how the mail is set up, and a
test send. The rights are the page's own (menu key admin.birthday_mailer): View to see, Add/Edit/Delete to change, Export for the people list CSV.

The mail itself is built and sent by core/birthday_mailer.py, on a schedule by core/scheduler.py."""

import calendar
import datetime
import json
import os

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action, api_view, parser_classes, permission_classes
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import audit as _audit
from . import birthday_excel, birthday_mailer as bm, mailer
from .masters_views import BaseMasterViewSet
from .media_uploads import media_url, next_sequence
from .models import BirthdayPerson, BirthdayTemplate, SchedHeartbeat, SchedItem, UserProfile
from .notice_board import poster_name
from .permissions import holds_a_right_on

MENU_KEY = "admin.birthday_mailer"


def _may(request, *flags):
    return holds_a_right_on(request, [MENU_KEY], flags=flags)


def _deny(what="use the Birthday Mailer"):
    return Response({"detail": f"You do not have the right to {what}."}, status=403)


def _uid(request):
    try:
        return UserProfile.objects.get(user_login_id=request.user.username).user_id
    except UserProfile.DoesNotExist:
        return 0


# ── people ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────

class BirthdayPersonSerializer(serializers.ModelSerializer):
    shown_name = serializers.CharField(read_only=True)
    birthday_label = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    next_birthday = serializers.SerializerMethodField()

    class Meta:
        model = BirthdayPerson
        fields = "__all__"
        read_only_fields = ["source", "upload_batch", "cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def get_birthday_label(self, obj):
        return f"{obj.birth_day} {calendar.month_abbr[obj.birth_month]}" + (f" {obj.birth_year}" if obj.birth_year else "")

    def get_is_active(self, obj):
        return bm.is_active_on(obj, datetime.date.today())

    def get_next_birthday(self, obj):
        today = datetime.date.today()
        d = bm.birthday_on(obj, today.year)
        return (d if d >= today else bm.birthday_on(obj, today.year + 1)).isoformat()

    def validate_full_name(self, v):
        v = " ".join((v or "").split())
        if not v:
            raise serializers.ValidationError("Enter the person's full name.")
        if len(v) > 100:
            raise serializers.ValidationError("The full name can be at most 100 characters.")
        return v

    def validate_display_name(self, v):
        v = " ".join((v or "").split())
        if len(v) > 100:
            raise serializers.ValidationError("The display name can be at most 100 characters.")
        return v or None

    def validate_birth_year(self, v):
        if v is not None and not 1900 <= v <= datetime.date.today().year:
            raise serializers.ValidationError("Enter a real year, or leave it blank.")
        return v

    def validate(self, attrs):
        inst = self.instance
        m = attrs.get("birth_month", inst.birth_month if inst else None)
        d = attrs.get("birth_day", inst.birth_day if inst else None)
        errors = {}
        if m is not None and not 1 <= m <= 12:
            errors["birth_month"] = "The month must be 1 to 12."
        elif m is not None and d is not None and not 1 <= d <= calendar.monthrange(2000, m)[1]:  # 2000 is a leap year: 29 Feb is allowed
            errors["birth_day"] = f"{calendar.month_name[m]} does not have a day {d}."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class BirthdayPersonViewSet(BaseMasterViewSet):
    queryset = BirthdayPerson.objects.all()
    serializer_class = BirthdayPersonSerializer
    entity_key = MENU_KEY
    name_field = "full_name"
    date_active_field = "leaving_date"  # Active = no leaving date, or one that has not passed (it is the last day)
    search_fields = ["full_name", "display_name"]
    lookup = False

    def label_for(self, instance):
        return instance.shown_name

    def list(self, request, *args, **kwargs):
        """The people, in the order the page shows them. ?sort=next (the default: the soonest birthday first) or ?sort=calendar (January to December) or ?sort=name (A to Z). By default the
        people who are still here come first and the ones who have left come after, each group in that order; ?group=0 turns the grouping off and
        sorts everyone together. The next birthday is worked out here (not in the database), so the list is sorted in memory and then paged."""
        today = datetime.date.today()
        sort = request.query_params.get("sort", "next")
        group = request.query_params.get("group", "1") != "0"
        rows = list(self.filter_queryset(self.get_queryset()))

        def days_to_next(p):
            d = bm.birthday_on(p, today.year)
            return ((d if d >= today else bm.birthday_on(p, today.year + 1)) - today).days

        def key(p):
            lead = 0 if (not group or bm.is_active_on(p, today)) else 1
            if sort == "name":
                main = " ".join(p.full_name.split()).casefold()
            elif sort == "calendar":
                main = (p.birth_month, p.birth_day)  # January to December, whatever today is
            else:
                main = days_to_next(p)
            return (lead, main, " ".join(p.full_name.split()).casefold(), p.person_id)

        rows.sort(key=key)
        page = self.paginate_queryset(rows)
        ser = self.get_serializer(page if page is not None else rows, many=True)
        return self.get_paginated_response(ser.data) if page is not None else Response(ser.data)

    @action(detail=False, methods=["get"], url_path="template")
    def download_template(self, request):
        """The blank Excel file to fill in."""
        r = HttpResponse(birthday_excel.build_template(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        r["Content-Disposition"] = 'attachment; filename="Birthday_Mailer_people_template.xlsx"'
        return r

    @action(detail=False, methods=["post"], url_path="upload", parser_classes=[MultiPartParser])
    def upload_people(self, request):
        """Reads an Excel file. dry_run=1 (the default) only reports; dry_run=0 saves the valid rows. skip_duplicates=0 adds every row."""
        f = request.FILES.get("file")
        if not f:
            return Response({"detail": "Choose an Excel file first."}, status=400)
        flag = lambda k, default: str(request.data.get(k, default)).lower() in ("1", "true", "yes", "on")
        dry = flag("dry_run", "1")
        try:
            report = birthday_excel.process(f.read(), dry_run=dry, skip_duplicates=flag("skip_duplicates", "1"), user_id=_uid(request))
        except birthday_excel.UploadError as exc:
            return Response({"detail": str(exc)}, status=400)
        if not dry and report["added"]:
            _audit.record_action(request, "create", MENU_KEY, report["batch"], f"Birthday Mailer: {report['added']} people uploaded from Excel", {"added": {"old": None, "new": report["added"]}})
        return Response(report)


# ── templates ────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def _template_row(request, t):
    if not t.thumb_data and os.path.isfile(bm.template_path(t)):  # a template saved before thumbnails existed: make its thumbnail once
        with open(bm.template_path(t), "rb") as fh:
            t.thumb_data = bm.make_thumb(fh.read())
        BirthdayTemplate.objects.filter(pk=t.pk).update(thumb_data=t.thumb_data)
    return {
        "id": t.template_id, "name": t.name, "url": media_url(request, t.file_path), "thumb": t.thumb_data, "width": t.width, "height": t.height,
        "box": {"x": t.box_x, "y": t.box_y, "w": t.box_w, "h": t.box_h}, "font": t.font, "color": t.color, "size_max": t.size_max, "size_min": t.size_min,
        "align_h": t.align_h, "align_v": t.align_v, "text_case": t.text_case, "active": t.is_active == "Y", "times_used": t.times_used,
        "last_used_at": t.last_used_at, "posted_by": t.posted_by_name or "",
    }


def clean_settings(raw, base=None):
    """Checks the text and box settings of a template. `raw` may be partial (a change); `base` is the current values. Returns a dict of model fields."""
    b = base or {}
    out = {}
    def num(key, lo, hi, default, as_int=False):
        v = raw.get(key, b.get(key, default))
        try:
            v = float(v)
        except (TypeError, ValueError):
            raise serializers.ValidationError({key: "must be a number"})
        if not lo <= v <= hi:
            raise serializers.ValidationError({key: f"must be between {lo} and {hi}"})
        return int(round(v)) if as_int else v
    box = raw.get("box", {}) or {}
    cur = {"x": b.get("box_x", 0.1), "y": b.get("box_y", 0.6), "w": b.get("box_w", 0.8), "h": b.get("box_h", 0.2)}
    for k in ("x", "y", "w", "h"):
        v = box.get(k, cur[k])
        try:
            cur[k] = float(v)
        except (TypeError, ValueError):
            raise serializers.ValidationError({"box": f"{k} must be a number"})
    if not (0 <= cur["x"] <= 1 and 0 <= cur["y"] <= 1 and 0.02 <= cur["w"] <= 1 and 0.02 <= cur["h"] <= 1):
        raise serializers.ValidationError({"box": "The name box must sit inside the picture and not be tiny."})
    if cur["x"] + cur["w"] > 1.0001 or cur["y"] + cur["h"] > 1.0001:
        raise serializers.ValidationError({"box": "The name box goes outside the picture."})
    out.update(box_x=cur["x"], box_y=cur["y"], box_w=cur["w"], box_h=cur["h"])
    out["size_max"] = num("size_max", 8, 800, 96, True)
    out["size_min"] = num("size_min", 8, 800, 28, True)
    if out["size_min"] > out["size_max"]:
        raise serializers.ValidationError({"size_min": "The smallest size cannot be bigger than the biggest."})
    for key, allowed, default in (("font", tuple(bm.FONTS), "poppins"), ("align_h", bm.ALIGN_H, "center"), ("align_v", bm.ALIGN_V, "middle"), ("text_case", bm.CASES, "title")):
        v = raw.get(key, b.get(key, default))
        if v not in allowed:
            raise serializers.ValidationError({key: "must be one of " + ", ".join(allowed)})
        out[key] = v
    color = raw.get("color", b.get("color", "#ffffff"))
    import re
    if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise serializers.ValidationError({"color": "must be a colour such as #ffffff"})
    out["color"] = color.lower()
    if "name" in raw or not base:
        name = " ".join(str(raw.get("name", b.get("name", ""))).split())
        if not name:
            raise serializers.ValidationError({"name": "Give the template a name."})
        out["name"] = name[:80]
    if "active" in raw:
        out["is_active"] = "Y" if raw["active"] in (True, "Y", "true", "1", 1) else "N"
    return out


PREVIEW_WIDTH = 640  # the editor's previews are small and light (a JPEG, about 40 KB); the real card is sent larger, as a PNG


def _as_jpeg(png_bytes, quality=80):
    import io

    from PIL import Image

    out = io.BytesIO()
    Image.open(io.BytesIO(png_bytes)).convert("RGB").save(out, "JPEG", quality=quality, optimize=True)
    return out.getvalue()


def _base_of(t):
    return {"box_x": t.box_x, "box_y": t.box_y, "box_w": t.box_w, "box_h": t.box_h, "font": t.font, "color": t.color, "size_max": t.size_max, "size_min": t.size_min,
            "align_h": t.align_h, "align_v": t.align_v, "text_case": t.text_case, "name": t.name}


def _bad(exc):
    return Response({"detail": "; ".join(f"{k}: {v}" for k, v in exc.detail.items()) if isinstance(exc.detail, dict) else str(exc.detail), "errors": exc.detail}, status=400)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, JSONParser])
def templates_api(request):
    """GET: the templates. POST (multipart: file, name and the settings as plain fields): add one."""
    if request.method == "GET":
        if not _may(request, "view"):
            return _deny()
        return Response({"results": [_template_row(request, t) for t in BirthdayTemplate.objects.order_by("-is_active", "-template_id")], "fonts": [{"key": k, "label": v[0]} for k, v in bm.FONTS.items()]})
    if not _may(request, "add"):
        return _deny("add birthday templates")
    f = request.FILES.get("file")
    if not f:
        return Response({"detail": "Choose a PNG picture first."}, status=400)
    try:
        png, w, h = bm.process_template_upload(f.read(), f.name)
    except bm.TemplateError as exc:
        return Response({"detail": str(exc)}, status=400)
    raw = {k: v for k, v in request.data.items() if k != "file"}
    if "box" not in raw and any(k in raw for k in ("box_x", "box_y", "box_w", "box_h")):
        raw["box"] = {k: raw.get(f"box_{k}") for k in "xywh" if raw.get(f"box_{k}") is not None}
    if isinstance(raw.get("box"), str):
        try:
            raw["box"] = json.loads(raw["box"])
        except ValueError:
            raw["box"] = {}
    raw.setdefault("name", os.path.splitext(os.path.basename(f.name or "Template"))[0])
    try:
        fields = clean_settings(raw)
    except serializers.ValidationError as exc:
        return _bad(exc)
    fields["is_active"] = "N" if str(raw.get("active", "true")).lower() in ("false", "0", "n") else "Y"
    row = BirthdayTemplate.objects.create(file_path="x", width=w, height=h, thumb_data=bm.make_thumb(png), posted_by_name=poster_name(request.user), cr_user_id=_uid(request) or 1, cr_dt=timezone.now(), **fields)
    rel = f"{bm.FOLDER}/{row.template_id}_{next_sequence(bm.FOLDER, str(row.template_id))}.png"
    path = os.path.join(settings.MEDIA_ROOT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(png)
    BirthdayTemplate.objects.filter(pk=row.pk).update(file_path=rel)
    row.refresh_from_db()
    _audit.record_action(request, "create", MENU_KEY, row.pk, f"Birthday template: {row.name}", {"file": {"old": None, "new": rel}})
    return Response(_template_row(request, row), status=201)


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def template_detail_api(request, template_id):
    t = BirthdayTemplate.objects.filter(pk=template_id).first()
    if not t:
        return Response({"detail": "That template no longer exists."}, status=404)
    if request.method == "DELETE":
        if not _may(request, "edit", "delete"):
            return _deny("remove birthday templates")
        label, rel = t.name, t.file_path
        t.delete()
        try:
            os.remove(os.path.join(settings.MEDIA_ROOT, rel))
        except OSError:
            pass
        _audit.record_action(request, "delete", MENU_KEY, template_id, f"Birthday template: {label}", {"file": {"old": rel, "new": None}})
        return Response(status=204)
    if not _may(request, "edit"):
        return _deny("change birthday templates")
    old = _template_row(request, t)
    try:
        fields = clean_settings(request.data, _base_of(t))
    except serializers.ValidationError as exc:
        return _bad(exc)
    fields["mod_user_id"], fields["mod_dt"] = _uid(request), timezone.now()
    BirthdayTemplate.objects.filter(pk=t.pk).update(**fields)
    t.refresh_from_db()
    new = _template_row(request, t)
    changes = {k: {"old": old[k], "new": new[k]} for k in new if k not in ("url", "last_used_at") and old.get(k) != new[k]}
    _audit.record_action(request, "update", MENU_KEY, t.pk, f"Birthday template: {t.name}", changes or None)
    return Response(new)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def template_preview_api(request):
    """The template with a sample name drawn in it (a small JPEG), using the settings as they are in the editor now (not yet saved). Body: {template_id,
    box, font, color, size_max, size_min, align_h, align_v, text_case}. Returns the PNG; X-Card-Meta says how the name was fitted."""
    if not _may(request, "add", "edit"):
        return _deny("preview birthday templates")
    t = BirthdayTemplate.objects.filter(pk=request.data.get("template_id")).first()
    if not t:
        return Response({"detail": "Choose a saved template first."}, status=404)
    try:
        fields = clean_settings(request.data, _base_of(t))
    except serializers.ValidationError as exc:
        return _bad(exc)
    sample = " ".join(str(request.data.get("sample", "Priya Sharma")).split())[:bm.MAX_NAME] or "Priya Sharma"
    for k, v in fields.items():
        setattr(t, k, v)  # in memory only: nothing is saved
    if not os.path.isfile(bm.template_path(t)):
        return Response({"detail": "The template picture is missing from the media folder."}, status=404)
    png, meta = bm.render_card(t, sample, max_width=PREVIEW_WIDTH)
    r = HttpResponse(_as_jpeg(png), content_type="image/jpeg")
    r["X-Card-Meta"] = json.dumps({"size": meta["size"], "lines": len(meta["lines"]), "truncated": meta["truncated"], "below_min": meta["below_min"]})
    r["Cache-Control"] = "no-store"
    return r


# ── the setup the page shows, and the test mail ──────────────────────────────────────────────────────────────────────────────

def scheduler_health(now=None):
    """Whether the scheduler SERVICE is alive: it runs at the top of every hour, so more than 75 minutes since its last run means it has stopped. A run
    started by hand with "Run it now" does not count (it is reported on its own as manual_at), or a click would make a stopped service look alive."""
    now = now or datetime.datetime.now()
    hb = SchedHeartbeat.objects.filter(pk=1).first()
    manual = hb.last_manual_tick_at if hb else None
    manual_minutes = int((now - manual).total_seconds() // 60) if manual else None
    if not hb or not hb.last_service_tick_at:
        return {"state": "never", "last_run": None, "minutes_ago": None, "ok": True, "message": "The scheduler service has not run.", "manual_at": manual, "manual_minutes_ago": manual_minutes}
    minutes = int((now - hb.last_service_tick_at).total_seconds() // 60)
    return {"state": "stale" if minutes > 75 else "running", "last_run": hb.last_service_tick_at, "minutes_ago": minutes, "ok": hb.last_tick_ok, "message": hb.last_message,
            "manual_at": manual, "manual_minutes_ago": manual_minutes}


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def overview_api(request):
    """What the Birthday Mailer page shows in its 'Mail setup' panel, read from the trigger, the alert and the environment."""
    if not _may(request, "view"):
        return _deny()
    today = datetime.date.today()
    setup = bm.get_setup(today)
    people = list(BirthdayPerson.objects.all())
    active = [p for p in people if bm.is_active_on(p, today)]
    coming = sorted(((min((d for d in (bm.birthday_on(p, today.year), bm.birthday_on(p, today.year + 1)) if d >= today)), p) for p in active), key=lambda x: (x[0], x[1].shown_name))[:8]
    return Response({
        "setup": setup, "scheduler": scheduler_health(),
        "counts": {"people": len(people), "active": len(active), "templates": BirthdayTemplate.objects.count(), "templates_active": BirthdayTemplate.objects.filter(is_active="Y").count()},
        "coming": [{"date": d.isoformat(), "name": p.shown_name} for d, p in coming],
        "links": {"trigger": "/masters/notification-triggers", "recipients": f"/masters/mail-alert-to-users?alert={setup['alert']['id']}&alertName={setup['alert']['name']}" if setup.get("alert") else ""},
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def test_send_api(request):
    """Sends ONE sample mail ("Test Person") to the address given, and only to it (not to the alert's recipients), to try the sending account and the
    next picture. Needs Edit."""
    if not _may(request, "edit"):
        return _deny("send a test mail")
    import re
    to = (request.data.get("email") or "").strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", to):
        return Response({"detail": "Enter an e-mail address to send the test to."}, status=400)
    t = bm.pick_template()
    if t is None:
        return Response({"detail": "There is no active template to send."}, status=400)
    if not os.path.isfile(bm.template_path(t)):
        return Response({"detail": f"The template picture '{t.name}' is missing from the media folder."}, status=400)
    setup = bm.get_setup()
    subject, html, text, images, _ = bm.build_mail("Test Person", t, setup)
    res = mailer.send_scheduled_email("[Test] " + subject, html, text, to=[to], from_name=setup["from_name"], inline_images=images, trigger=f"Birthday test to {to}", trigger_code="auto.birthday.test", alert_id=(setup.get("alert") or {}).get("id"))
    _audit.record_action(request, "update", MENU_KEY, "test", f"Birthday test mail to {to}", {"result": {"old": None, "new": "sent" if res["ok"] else "failed"}})
    return Response({"ok": res["ok"], "smtp_used": res["smtp_used"], "fell_back": res.get("fell_back", False), "first_choice": res.get("first_choice", ""), "error": res["error"], "template": t.name, "email_log_id": res["email_log_id"]}, status=200 if res["ok"] else 502)
