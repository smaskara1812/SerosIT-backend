"""Admin > Home Page > Customise Sero: the outfits Sero the mascot can wear, and which one he wears when.

An outfit is a small `look` document built from a fixed dress-up kit (head, top with a print and a trim, neck, face, extra) and colours. It is validated strictly (known
keys only, kit parts from the lists below, hex colours) and drawn by the frontend, so an outfit can never carry markup or a shape of its own.

Which outfit he wears, first match wins:
  1. the live banner names an outfit (design.sero.outfit is an outfit id);
  2. otherwise the day's outfit: weekdays and weekends each have a mode, set on the page: plain (his usual look), fixed (one chosen outfit) or daily (one outfit a day drawn
     from the single pool, the same for every user). The daily pick is a function of the date alone (no job, nothing remembered), shuffled fairly so every outfit in the
     pool is worn once before any repeats, and never the same outfit two days running within weekdays or within weekends.

Who may use the page is its own User Rights (admin.sero_look): App Admins always, anyone else when an admin grants View / Add / Edit / Delete. Someone who can edit banner
events may also READ the outfits, to choose one in the banner editor's Sero section.
"""

import random
import re

from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import audit as _audit
from .models import BannerEvent, SeroOutfit, SeroSetting
from .notice_board import poster_name
from .permissions import holds_a_right_on

MENU_KEY = "admin.sero_look"
BANNER_KEY = "admin.banner_events"
ENTITY = "sero_outfit"
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
MODES = ("plain", "fixed", "daily")
MAX_OUTFITS = 60

# The dress-up kit. frontend/src/lib/seroOutfit.js holds the same lists (and the drawings): keep them in step.
PARTS = {
    "head": ("hardhat", "cap", "beanie", "turban", "headphones", "santa", "party", "cowboy", "chef", "none"),  # hardhat = his usual Seros safety hat, any colour
    "top": ("none", "tee", "kurta", "jacket", "hoodie", "shirt"),  # none = his own white shell
    "neck": ("none", "scarf", "bandana", "dupatta", "idcard"),  # idcard = an ID card on a lanyard
    "face": ("none", "shades", "specs"),
    "extra": ("none", "garland", "bowtie", "necktie", "medal"),
}
PRINTS = ("none", "stripes", "dots", "checks", "zigzag", "stars", "chevrons")
LENGTHS = ("short", "regular", "long")  # how far a kurta hangs: to the hip, to the thigh, over the knees
TRIMS = ("none", "hem", "collar", "cuffs", "all")  # a contrasting border on the hem, the neckline, the cuffs or all three

DEFAULT_LOOK = {
    "head": {"style": "hardhat", "color": "#f58220"},  # the default look is Sero as he always is
    "top": {"style": "none", "color": "#2563eb", "print": "none", "printColor": "#ffffff", "trim": "none", "trimColor": "#ffffff", "length": "regular"},
    "neck": {"style": "none", "color": "#dc2626", "stripe": None},
    "face": {"style": "none", "color": "#111827"},
    "extra": {"style": "none", "color": "#f59e0b"},
    "shoes": {"color": "#1f6fb5"},  # the upper of his shoes; the default is his own blue
}


class LookError(ValueError):
    pass


def _hex(value, what, allow_none=False):
    if value is None and allow_none:
        return None
    if not isinstance(value, str) or not HEX.match(value):
        raise LookError(f"{what} must be a colour like #1c448a")
    return value.lower()


def _only(obj, allowed, what):
    if not isinstance(obj, dict):
        raise LookError(f"{what} must be an object")
    extra = set(obj) - set(allowed)
    if extra:
        raise LookError(f"{what}: unknown setting {sorted(extra)[0]!r}")


def _style(obj, part):
    s = obj.get("style", DEFAULT_LOOK[part]["style"])
    if s not in PARTS[part]:
        raise LookError(f"{part} must be one of " + ", ".join(PARTS[part]))
    return s


def clean_look(raw):
    """The look with every value checked and filled in, or LookError."""
    if raw in (None, {}):
        return {k: dict(v) for k, v in DEFAULT_LOOK.items()}
    _only(raw, DEFAULT_LOOK, "look")
    d = {}
    for part in ("head", "face", "extra"):
        o = raw.get(part, DEFAULT_LOOK[part])
        _only(o, ("style", "color"), part)
        d[part] = {"style": _style(o, part), "color": _hex(o.get("color", DEFAULT_LOOK[part]["color"]), f"{part} colour")}
    o = raw.get("top", DEFAULT_LOOK["top"])
    _only(o, ("style", "color", "print", "printColor", "trim", "trimColor", "length"), "top")
    pr, tr = o.get("print", "none"), o.get("trim", "none")
    if pr not in PRINTS:
        raise LookError("the print must be one of " + ", ".join(PRINTS))
    if tr not in TRIMS:
        raise LookError("the trim must be one of " + ", ".join(TRIMS))
    ln = o.get("length", "regular")
    if ln not in LENGTHS:
        raise LookError("the length must be one of " + ", ".join(LENGTHS))
    d["top"] = {"style": _style(o, "top"), "length": ln, "color": _hex(o.get("color", "#2563eb"), "top colour"), "print": pr, "printColor": _hex(o.get("printColor", "#ffffff"), "print colour"),
                "trim": tr, "trimColor": _hex(o.get("trimColor", "#ffffff"), "trim colour")}
    o = raw.get("neck", DEFAULT_LOOK["neck"])
    _only(o, ("style", "color", "stripe"), "neck")
    d["neck"] = {"style": _style(o, "neck"), "color": _hex(o.get("color", "#dc2626"), "neck colour"), "stripe": _hex(o.get("stripe"), "stripe colour", allow_none=True)}
    o = raw.get("shoes", DEFAULT_LOOK["shoes"])
    _only(o, ("color",), "shoes")
    d["shoes"] = {"color": _hex(o.get("color", "#1f6fb5"), "shoe colour")}
    return d


def _name(value):
    value = (value or "").strip() if isinstance(value, str) or value is None else None
    if not value:
        raise LookError("Give the outfit a name.")
    if len(value) > 60:
        raise LookError("The name can be at most 60 characters.")
    if re.search(r"[\x00-\x08\x0b-\x1f\x7f<>]", value):
        raise LookError("The name contains characters that are not allowed.")
    return value


# ── ready-made outfits ───────────────────────────────────────────────────────────────────────────

def _look(head=("hardhat", "#f58220"), top=("none", "#2563eb"), print_=("none", "#ffffff"), trim=("none", "#ffffff"), neck=("none", "#dc2626", None), face=("none", "#111827"), extra=("none", "#f59e0b"), length="regular", shoes="#1f6fb5"):
    return {"head": {"style": head[0], "color": head[1]}, "top": {"style": top[0], "color": top[1], "print": print_[0], "printColor": print_[1], "trim": trim[0], "trimColor": trim[1], "length": length},
            "neck": {"style": neck[0], "color": neck[1], "stripe": neck[2]}, "face": {"style": face[0], "color": face[1]}, "extra": {"style": extra[0], "color": extra[1]}, "shoes": {"color": shoes}}


STARTERS = [  # (name, look, in the pool)
    ("Safety hat", _look(head=("hardhat", "#facc15"), top=("shirt", "#0f766e"), trim=("collar", "#ffffff")), False),
    ("Diwali kurta", _look(head=("turban", "#c2410c"), top=("kurta", "#f59e0b"), print_=("dots", "#fde68a"), trim=("all", "#9a3412"), extra=("garland", "#f97316")), False),
    ("New Year swag", _look(head=("cap", "#111827"), top=("jacket", "#111827"), print_=("stars", "#fbbf24"), trim=("hem", "#fbbf24"), face=("shades", "#111827"), extra=("bowtie", "#fbbf24")), False),
    ("Winter scarf", _look(head=("beanie", "#b91c1c"), top=("hoodie", "#475569"), neck=("scarf", "#b91c1c", "#ffffff")), False),
    ("Teal stripes", _look(top=("tee", "#0d9488"), print_=("stripes", "#ccfbf1")), True),
    ("Coral dots", _look(top=("tee", "#f97316"), print_=("dots", "#ffedd5")), True),
    ("Violet checks", _look(top=("shirt", "#7c3aed"), print_=("checks", "#ddd6fe"), trim=("collar", "#ffffff")), True),
    ("Green zigzag", _look(head=("cap", "#15803d"), top=("tee", "#16a34a"), print_=("zigzag", "#bbf7d0")), True),
    ("Navy hoodie", _look(top=("hoodie", "#1e3a8a"), trim=("cuffs", "#60a5fa"), neck=("bandana", "#60a5fa", None)), True),
]


def settings_row():
    row, _ = SeroSetting.objects.get_or_create(pk=1)
    return row


def ensure_starters(request=None):
    """Adds the ready-made outfits the first time anyone looks. Deleted ones stay deleted."""
    row = settings_row()
    if row.starters_made:
        return
    now = timezone.now()
    uid = getattr(getattr(request, "user", None), "pk", None) or 0
    with transaction.atomic():
        for name, look, pool in STARTERS:
            SeroOutfit.objects.create(name=name, look=clean_look(look), in_pool=pool, posted_by_name="Seros", cr_user_id=uid, cr_dt=now)
        row.starters_made = True
        row.save(update_fields=["starters_made"])


# ── which outfit, when ───────────────────────────────────────────────────────────────────────────

def pool_pick(index, ids):
    """The outfit id for day number `index` (consecutive days of one kind have consecutive numbers). Pure: the same numbers and ids always give the same answer. Every outfit is
    worn once per round of len(ids) days, in a shuffled order that changes each round, and the first of a round is never the last of the round before."""
    ids = sorted(ids)
    if not ids:
        return None
    n = len(ids)
    if n == 1:
        return ids[0]
    if n == 2:
        return ids[index % 2]

    def order(c):
        o = ids[:]
        random.Random(f"sero-outfit:{c}:{n}").shuffle(o)
        return o

    cycle, pos = divmod(index, n)
    cur = order(cycle)
    if pos < 2 and cur[0] == order(cycle - 1)[-1]:
        cur[0], cur[1] = cur[1], cur[0]
    return cur[pos]


def _day_index(day):
    """(is weekend, a number that rises by one from each weekday to the next weekday, or from each weekend day to the next weekend day)."""
    wk, wd = divmod(day.toordinal() - 1, 7)  # 0 = Monday
    return (True, wk * 2 + (wd - 5)) if wd >= 5 else (False, wk * 5 + wd)


def day_outfit(day, setting=None, outfits=None):
    """The outfit row for a day with no banner choice, or None for his usual look."""
    st = setting or settings_row()
    weekend, index = _day_index(day)
    mode, fixed = (st.weekend_mode, st.weekend_outfit) if weekend else (st.weekday_mode, st.weekday_outfit)
    rows = outfits if outfits is not None else list(SeroOutfit.objects.all())
    by_id = {o.outfit_id: o for o in rows}
    if mode == "fixed":
        return by_id.get(fixed)
    if mode == "daily":
        return by_id.get(pool_pick(index, [o.outfit_id for o in rows if o.in_pool]))
    return None


def outfit_for(day, event=None):
    """What he wears today: the live banner's own choice if it has one, else the day's outfit. -> {"id", "name", "look"} or None."""
    rows = list(SeroOutfit.objects.all())
    by_id = {o.outfit_id: o for o in rows}
    chosen = None
    if event is not None:
        wanted = ((event.design or {}).get("sero") or {}).get("outfit")
        chosen = by_id.get(wanted) if isinstance(wanted, int) and not isinstance(wanted, bool) else None
    row = chosen or day_outfit(day, outfits=rows)
    return shape_outfit(row) if row else None


def shape_outfit(o):
    try:
        look = clean_look(o.look)
    except LookError:
        look = clean_look(None)
    return {"id": o.outfit_id, "name": o.name, "look": look}


# ── where outfits are used (for the warning before a delete) ─────────────────────────────────────

def usage(outfit_id):
    banners = [e.name for e in BannerEvent.objects.all() if ((e.design or {}).get("sero") or {}).get("outfit") == outfit_id]
    st = settings_row()
    return {"banners": banners, "weekdays": st.weekday_mode == "fixed" and st.weekday_outfit == outfit_id, "weekends": st.weekend_mode == "fixed" and st.weekend_outfit == outfit_id}


def _used(u):
    return bool(u["banners"] or u["weekdays"] or u["weekends"])


# ── API ──────────────────────────────────────────────────────────────────────────────────────────

def _may(request, flag):
    return holds_a_right_on(request, [MENU_KEY], flags=(flag,))


def _may_read(request):
    return holds_a_right_on(request, [MENU_KEY, BANNER_KEY], flags=("view", "add", "edit"))


def _deny():
    return Response({"detail": "You do not have the right to do that."}, status=403)


def _row_json(o, use=None):
    d = shape_outfit(o)
    d |= {"in_pool": o.in_pool, "posted_by": o.posted_by_name or "", "used_by": use if use is not None else usage(o.outfit_id)}
    return d


def settings_json(st):
    return {"weekday_mode": st.weekday_mode, "weekday_outfit": st.weekday_outfit, "weekend_mode": st.weekend_mode, "weekend_outfit": st.weekend_outfit, "changed_by": st.changed_by,
            "changed_at": st.changed_at.isoformat() if st.changed_at else None}


def payload(request):
    ensure_starters(request)
    rows = list(SeroOutfit.objects.order_by("name", "outfit_id"))
    st = settings_row()
    today = timezone.now().date()
    banner_names = [(e.name, ((e.design or {}).get("sero") or {}).get("outfit")) for e in BannerEvent.objects.all()]
    out = []
    for o in rows:
        u = {"banners": [n for n, i in banner_names if i == o.outfit_id], "weekdays": st.weekday_mode == "fixed" and st.weekday_outfit == o.outfit_id, "weekends": st.weekend_mode == "fixed" and st.weekend_outfit == o.outfit_id}
        out.append(_row_json(o, u))
    todays = day_outfit(today, st, rows)
    return {"outfits": out, "settings": settings_json(st), "today": shape_outfit(todays) if todays else None, "today_is": "weekend" if _day_index(today)[0] else "weekday",
            "can": {"add": _may(request, "add"), "edit": _may(request, "edit"), "delete": _may(request, "delete")}, "max": MAX_OUTFITS}


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def outfits_api(request):
    if request.method == "GET":
        return Response(payload(request)) if _may_read(request) else _deny()
    if not _may(request, "add"):
        return _deny()
    d = request.data or {}
    try:
        name, look = _name(d.get("name")), clean_look(d.get("look"))
    except LookError as exc:
        return Response({"detail": str(exc)}, status=400)
    ensure_starters(request)
    if SeroOutfit.objects.count() >= MAX_OUTFITS:
        return Response({"detail": f"There can be at most {MAX_OUTFITS} outfits. Delete one first."}, status=400)
    o = SeroOutfit.objects.create(name=name, look=look, in_pool=bool(d.get("in_pool")), posted_by_name=poster_name(request.user)[:60], cr_user_id=request.user.pk, cr_dt=timezone.now())
    _audit.record_action(request, "create", ENTITY, o.pk, name, {"name": {"old": None, "new": name}}, target=o)
    return Response(payload(request), status=201)


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def outfit_detail_api(request, outfit_id):
    o = SeroOutfit.objects.filter(pk=outfit_id).first()
    if not o:
        return Response({"detail": "That outfit no longer exists."}, status=404)
    if request.method == "PATCH":
        if not _may(request, "edit"):
            return _deny()
        d = request.data or {}
        changes = {}
        try:
            if "name" in d:
                new = _name(d["name"])
                if new != o.name:
                    changes["name"] = {"old": o.name, "new": new}
                    o.name = new
            if "look" in d:
                new = clean_look(d["look"])
                if new != clean_look(o.look):
                    changes["look"] = {"old": "changed", "new": "changed"}
                    o.look = new
        except LookError as exc:
            return Response({"detail": str(exc)}, status=400)
        if "in_pool" in d and bool(d["in_pool"]) != o.in_pool:
            changes["in_pool"] = {"old": o.in_pool, "new": bool(d["in_pool"])}
            o.in_pool = bool(d["in_pool"])
        if changes:
            o.mod_user_id, o.mod_dt = request.user.pk, timezone.now()
            o.save()
            _audit.record_action(request, "update", ENTITY, o.pk, o.name, changes, target=o)
        return Response(payload(request))
    if not _may(request, "delete"):
        return _deny()
    use = usage(o.pk)
    if _used(use) and str(request.query_params.get("confirm", "")).lower() not in ("1", "true", "yes"):
        return Response({"detail": "This outfit is in use.", "used_by": use}, status=409)
    with transaction.atomic():
        for e in BannerEvent.objects.all():  # a banner that named it follows the day's outfit again
            sero = (e.design or {}).get("sero") or {}
            if sero.get("outfit") == o.pk:
                e.design = {**e.design, "sero": {**sero, "outfit": None}}
                e.save(update_fields=["design"])
        st = settings_row()
        if st.weekday_mode == "fixed" and st.weekday_outfit == o.pk:
            st.weekday_mode, st.weekday_outfit = "plain", None
        if st.weekend_mode == "fixed" and st.weekend_outfit == o.pk:
            st.weekend_mode, st.weekend_outfit = "plain", None
        st.save()
        label, pk = o.name, o.pk
        _audit.record_action(request, "delete", ENTITY, pk, label, {"name": {"old": label, "new": None}}, target=o)
        o.delete()
    return Response(payload(request))


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def settings_api(request):
    if not _may(request, "edit"):
        return _deny()
    d = request.data or {}
    ids = set(SeroOutfit.objects.values_list("pk", flat=True))
    new = {}
    for part in ("weekday", "weekend"):
        mode, fixed = d.get(f"{part}_mode", "plain"), d.get(f"{part}_outfit")
        if mode not in MODES:
            return Response({"detail": "The mode must be plain, fixed or daily."}, status=400)
        if mode == "fixed" and (isinstance(fixed, bool) or fixed not in ids):
            return Response({"detail": f"Choose which outfit he wears on {part}s."}, status=400)
        if mode == "daily" and not SeroOutfit.objects.filter(in_pool=True).exists():
            return Response({"detail": "The daily outfit needs at least one outfit in the pool."}, status=400)
        new[f"{part}_mode"], new[f"{part}_outfit"] = mode, (fixed if mode == "fixed" else None)
    st = settings_row()
    changes = {k: {"old": getattr(st, k), "new": v} for k, v in new.items() if getattr(st, k) != v}
    for k, v in new.items():
        setattr(st, k, v)
    st.changed_by, st.changed_at = poster_name(request.user)[:100], timezone.now()
    st.save()
    if changes:
        _audit.record_action(request, "update", "sero_setting", 1, "Sero daily outfit", changes)
    return Response(payload(request))
