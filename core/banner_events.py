"""Admin > Banner Events: a custom look for the home page banner on chosen days.

Who may manage events is the page's own User Rights (admin.banner_events): App Admins always, anyone else when an admin
grants them View / Add / Edit / Delete. There is no approval step: anyone with Add or Edit can publish.

Everyone signed in reads today's banner through /api/banner/active/, which returns only the design. A person holding
View on the page may also pass ?preview=<event id> to see a draft or an event that is not on today.

The design is a small JSON document, never HTML. It is validated strictly (known keys only, hex colours, numbers inside
fixed ranges, short plain text) so a bad design can never break the home page or put markup in front of other people.
"""

import re
from datetime import date, timedelta

from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .masters_views import BaseMasterViewSet
from .models import BannerEvent
from .notice_board import poster_name
from .permissions import holds_a_right_on

MENU_KEY = "admin.banner_events"
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
LAYOUTS = ("standard", "mirrored", "centred")
BACKGROUNDS = ("solid", "gradient")
PATTERNS = ("none", "dots", "stripes", "waves", "grid", "chevrons", "sunburst", "topo")
MAX_LAYERS = 60
SHAPES = (
    "rect", "circle", "ring", "triangle", "diamond", "star", "sparkle", "heart", "moon", "drop", "leaf", "wave", "line", "rig", "ship",
    "tree", "cloud", "sun", "snowflake", "helicopter", "hardhat", "drillbit", "wrench", "gear", "cone", "diya", "kite", "balloon", "flag", "spectacles",
    "chakra", "indiagate", "redfort", "tajmahal", "qutub", "jet", "swoosh", "book", "mosque", "lantern", "splash", "burst", "temple", "bauble", "holly", "flame", "bananaleaf", "ribbon", "bow", "modak", "flower", "bird", "hand",
    "text",
)
TEXT_KEYS = ("text", "size", "bold", "font", "spacing")  # only on a text layer
LAYER_KEYS = ("id", "type", "x", "y", "w", "h", "rot", "fill", "opacity", "n", "p", "fill2", "grad", "stroke", "sw") + TEXT_KEYS
FONTS = ("sans", "serif")

DEFAULT_DESIGN = {
    "v": 1,
    "layout": "standard",
    "text": {"greeting": "", "message": "", "caption": "", "color": None},
    "background": {"type": "gradient", "colors": ["#1c448a", "#17356f", "#0f2650"], "angle": 118},
    "pattern": {"type": "none", "color": "#ffffff", "opacity": 0.12, "scale": 1.0},
    "contours": {"on": True, "color": "#ffffff", "opacity": 0.13, "density": 2},
    "showLastSignIn": True,
    "search": {"tint": "#ffffff"},
    "layers": [],
}


def _err(path, msg):
    raise serializers.ValidationError({"design": f"{path}: {msg}"})


def _only_keys(obj, allowed, path):
    if not isinstance(obj, dict):
        _err(path, "must be an object")
    extra = set(obj) - set(allowed)
    if extra:
        _err(path, f"unknown setting {sorted(extra)[0]!r}")


def _text(value, path, limit):
    if value is None:
        return ""
    if not isinstance(value, str):
        _err(path, "must be text")
    value = value.strip()
    if len(value) > limit:
        _err(path, f"is longer than {limit} characters")
    if re.search(r"[\x00-\x08\x0b-\x1f\x7f<>]", value):
        _err(path, "contains characters that are not allowed")
    return value


def _hex(value, path, allow_none=False):
    if value is None and allow_none:
        return None
    if not isinstance(value, str) or not HEX.match(value):
        _err(path, "must be a colour like #1c448a")
    return value.lower()


def _luminance(hex_colour):
    channels = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _light_tint(value, path):
    """The search box's tint: any colour that is still light and soft (the search words are dark), white by default."""
    value = _hex(value, path)
    if _luminance(value) < 0.7:
        _err(path, "must be a light, soft colour")
    return value


def _num(value, path, lo, hi):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not lo <= value <= hi:
        _err(path, f"must be a number from {lo} to {hi}")
    return value


def clean_design(raw):
    """Return the design with every value checked and normalised, or raise a validation error."""
    if raw in (None, {}):
        return DEFAULT_DESIGN | {}
    _only_keys(raw, DEFAULT_DESIGN, "design")
    d = {}
    if raw.get("v", 1) != 1:
        _err("v", "is not a version this system knows")
    d["v"] = 1
    layout = raw.get("layout", "standard")
    if layout not in LAYOUTS:
        _err("layout", "must be one of " + ", ".join(LAYOUTS))
    d["layout"] = layout

    t = raw.get("text", {})
    _only_keys(t, ("greeting", "message", "caption", "color"), "text")
    d["text"] = {
        "greeting": _text(t.get("greeting"), "greeting", 80),
        "message": _text(t.get("message"), "message", 200),
        "caption": _text(t.get("caption"), "caption", 40),
        "color": _hex(t.get("color"), "text colour", allow_none=True),
    }

    b = raw.get("background", DEFAULT_DESIGN["background"])
    _only_keys(b, ("type", "colors", "angle"), "background")
    if b.get("type") not in BACKGROUNDS:
        _err("background", "type must be solid or gradient")
    colors = b.get("colors")
    if not isinstance(colors, list) or not 1 <= len(colors) <= 3:
        _err("background", "needs one to three colours")
    d["background"] = {"type": b["type"], "colors": [_hex(c, "background colour") for c in colors], "angle": _num(b.get("angle", 118), "angle", 0, 360)}

    p = raw.get("pattern", DEFAULT_DESIGN["pattern"])
    _only_keys(p, ("type", "color", "opacity", "scale"), "pattern")
    if p.get("type") not in PATTERNS:
        _err("pattern", "is not one of the built-in patterns")
    d["pattern"] = {"type": p["type"], "color": _hex(p.get("color", "#ffffff"), "pattern colour"), "opacity": _num(p.get("opacity", 0.12), "pattern strength", 0, 1), "scale": _num(p.get("scale", 1), "pattern size", 0.5, 3)}

    c = raw.get("contours", DEFAULT_DESIGN["contours"])
    _only_keys(c, ("on", "color", "opacity", "density"), "contours")
    if not isinstance(c.get("on", True), bool):
        _err("contours", "on must be true or false")
    d["contours"] = {"on": c.get("on", True), "color": _hex(c.get("color", "#ffffff"), "contour colour"), "opacity": _num(c.get("opacity", 0.13), "contour strength", 0, 0.6), "density": int(_num(c.get("density", 2), "contour spacing", 1, 3))}

    sr = raw.get("search", DEFAULT_DESIGN["search"])
    _only_keys(sr, ("tint",), "search")
    d["search"] = {"tint": _light_tint(sr.get("tint", "#ffffff"), "search box tint")}

    show = raw.get("showLastSignIn", True)
    if not isinstance(show, bool):
        _err("showLastSignIn", "must be true or false")
    d["showLastSignIn"] = show

    layers = raw.get("layers", [])
    if not isinstance(layers, list) or len(layers) > MAX_LAYERS:
        _err("layers", f"must be a list of at most {MAX_LAYERS} shapes")
    d["layers"] = [_layer(l, i) for i, l in enumerate(layers)]
    return d


def _layer(l, i):
    path = f"shape {i + 1}"
    _only_keys(l, LAYER_KEYS, path)
    if l.get("type") not in SHAPES:
        _err(path, "is not one of the built-in shapes")
    ident = l.get("id", f"s{i}")
    if not isinstance(ident, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,16}", ident):
        _err(path, "has an invalid id")
    out = {
        "id": ident,
        "type": l["type"],
        "x": _num(l.get("x", 600), f"{path} position", -200, 1400),
        "y": _num(l.get("y", 180), f"{path} position", -200, 560),
        "w": _num(l.get("w", 100), f"{path} width", 2, 1600),
        "h": _num(l.get("h", 100), f"{path} height", 2, 900),
        "rot": _num(l.get("rot", 0), f"{path} rotation", -360, 360),
        "fill": _hex(l.get("fill", "#ffffff"), f"{path} colour"),
        "opacity": _num(l.get("opacity", 1), f"{path} opacity", 0, 1),
    }
    if "n" in l:
        out["n"] = int(_num(l["n"], f"{path} points", 2, 12))
    if "p" in l:
        out["p"] = _num(l["p"], f"{path} setting", 0, 1)
    if l.get("fill2") is not None:  # a second colour: the shape is a blend from `fill` to `fill2`
        out["fill2"] = _hex(l["fill2"], f"{path} second colour")
        out["grad"] = _num(l.get("grad", 90), f"{path} blend direction", 0, 360)
    if l.get("stroke") is not None:  # an outline
        out["stroke"] = _hex(l["stroke"], f"{path} outline colour")
        out["sw"] = _num(l.get("sw", 4), f"{path} outline thickness", 0, 40)
    if l["type"] == "text":
        out["text"] = _text(l.get("text"), f"{path} words", 40)
        if not out["text"]:
            _err(path, "needs some words")
        out["size"] = int(_num(l.get("size", 48), f"{path} text size", 8, 240))
        if not isinstance(l.get("bold", True), bool):
            _err(path, "bold must be true or false")
        out["bold"] = l.get("bold", True)
        if l.get("font", "sans") not in FONTS:
            _err(path, "font must be sans or serif")
        out["font"] = l.get("font", "sans")
        out["spacing"] = _num(l.get("spacing", 0), f"{path} letter spacing", 0, 30)
    elif any(k in l for k in TEXT_KEYS):
        _err(path, "has text settings but is not a text shape")
    return out


# ── dates ────────────────────────────────────────────────────────────────────────────────────────

def covers(ev, today):
    """Is `today` inside the event's days? A yearly event compares month and day only and may wrap over New Year."""
    if ev.repeat_yearly != "Y":
        return ev.starts_on <= today <= ev.ends_on
    s, e, t = (ev.starts_on.month, ev.starts_on.day), (ev.ends_on.month, ev.ends_on.day), (today.month, today.day)
    return s <= t <= e if s <= e else (t >= s or t <= e)


def _spans(ev):
    """Every stretch of days the event occupies, for checking overlaps (a yearly one is checked over the next years)."""
    if ev.repeat_yearly != "Y":
        return [(ev.starts_on, ev.ends_on)]
    out = []
    for y in range(date.today().year - 1, date.today().year + 3):
        try:
            s = ev.starts_on.replace(year=y)
        except ValueError:
            s = date(y, 2, 28)
        length = (ev.ends_on - ev.starts_on).days
        out.append((s, s + timedelta(days=length)))
    return out


def overlapping(ev, others):
    mine = _spans(ev)
    hit = []
    for o in others:
        if o.pk == ev.pk or o.is_published != "Y" or ev.is_published != "Y":
            continue
        if any(a1 <= b2 and b1 <= a2 for a1, a2 in mine for b1, b2 in _spans(o)):
            hit.append(o.name)
    return hit


def status_of(ev, today=None):
    today = today or timezone.now().date()
    if ev.is_published != "Y":
        return "draft"
    if covers(ev, today):
        return "live"
    if ev.repeat_yearly == "Y" or ev.starts_on > today:
        return "upcoming"
    return "past"


def pick_for(today, events):
    live = [e for e in events if e.is_published == "Y" and covers(e, today)]
    live.sort(key=lambda e: (e.priority, e.starts_on, e.event_id), reverse=True)
    return live[0] if live else None


# ── API ──────────────────────────────────────────────────────────────────────────────────────────

class BannerEventSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    overlaps = serializers.SerializerMethodField()
    posted_by = serializers.SerializerMethodField()
    design = serializers.JSONField()

    class Meta:
        model = BannerEvent
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt", "posted_by_name"]

    def get_status(self, obj):
        return status_of(obj)

    def get_posted_by(self, obj):
        return obj.posted_by_name or ""

    def get_overlaps(self, obj):
        cache = self.context.setdefault("_all_events", list(BannerEvent.objects.all()))
        return overlapping(obj, cache)

    def validate_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Give the event a name.")
        return value

    def validate_design(self, value):
        return clean_design(value)

    def validate_priority(self, value):
        if not -100 <= value <= 100:
            raise serializers.ValidationError("Priority must be from -100 to 100.")
        return value

    def validate(self, attrs):
        inst = self.instance
        s = attrs.get("starts_on", inst.starts_on if inst else None)
        e = attrs.get("ends_on", inst.ends_on if inst else None)
        yearly = attrs.get("repeat_yearly", inst.repeat_yearly if inst else "N")
        errors = {}
        if s and e:
            if e < s:
                errors["ends_on"] = "The last day cannot be before the first day."
            elif (e - s).days > 366:
                errors["ends_on"] = "An event can last at most a year."
            elif yearly == "Y" and (e - s).days > 364:
                errors["ends_on"] = "A yearly event must be shorter than a year."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def create(self, validated_data):
        validated_data["posted_by_name"] = poster_name(self.context["request"].user)
        return super().create(validated_data)


class BannerEventViewSet(BaseMasterViewSet):
    queryset = BannerEvent.objects.all()
    serializer_class = BannerEventSerializer
    entity_key = MENU_KEY
    name_field = "name"
    search_fields = ["name"]
    lookup = False

    def get_queryset(self):
        qs = super().get_queryset().order_by("-starts_on", "-event_id")
        status = self.request.query_params.get("status")
        if status:
            ids = [e.pk for e in qs if status_of(e) == status]
            qs = qs.filter(pk__in=ids)
        return qs


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def active_banner_api(request):
    """{"event": today's banner design} or {"event": null} for the normal banner. `?preview=<id>` shows that event whatever its dates and
    draft state, but only to someone holding View on the Banner Events page."""
    preview = request.query_params.get("preview")
    if preview:
        if not holds_a_right_on(request, [MENU_KEY], flags=("view",)):
            return Response({"event": None})
        ev = BannerEvent.objects.filter(pk=preview).first()
        return Response({"event": _shape(ev, preview=True) if ev else None})
    today = timezone.now().date()
    ev = pick_for(today, list(BannerEvent.objects.filter(is_published="Y")))
    return Response({"event": _shape(ev) if ev else None})


def _shape(ev, preview=False):
    return {"event_id": ev.event_id, "name": ev.name, "design": clean_design(ev.design), "preview": preview}
