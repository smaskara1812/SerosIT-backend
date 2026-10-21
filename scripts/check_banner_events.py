"""Checks Admin > Banner Events with real requests as people holding exactly the rights named; everything runs in one
transaction that is rolled back.

    cd backend
    .venv/bin/python scripts/check_banner_events.py
"""
import copy
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.test import APIClient

from core.banner_events import DEFAULT_DESIGN, covers
from core.models import BannerEvent, UserPermission, UserProfile
from core.permissions import invalidate_user_access


class Rollback(Exception):
    pass


fails = []


def ok(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {detail}" if not cond else ""))
    if not cond:
        fails.append(name)


def mk(n, keys=(), flags=("view",), admin=False):
    U = get_user_model()
    u = U.objects.create_user(username=n, password="x")
    uid = (UserProfile.objects.order_by("-user_id").first().user_id or 0) + 1
    UserProfile.objects.create(user_id=uid, user_login_id=n, is_app_admin=admin)
    for k in keys:
        UserPermission.objects.create(user_id=uid, menu_key=k, can_view="view" in flags, can_add="add" in flags, can_edit="edit" in flags, can_delete="delete" in flags, can_export=False)
    invalidate_user_access(n)
    c = APIClient(HTTP_HOST="localhost")
    c.force_authenticate(u)
    return c


try:
    with transaction.atomic():
        today = timezone.now().date()
        d = lambda n: (today + datetime.timedelta(days=n)).isoformat()
        poster = mk("zzbe1", ["admin.banner_events"], ("view", "add", "edit", "delete"))
        viewer = mk("zzbe2", ["admin.banner_events"], ("view",))
        nobody = mk("zzbe3")
        admin = mk("zzbe0", admin=True)
        design = copy.deepcopy(DEFAULT_DESIGN)
        design["text"]["greeting"] = "Happy Safety Day, {name}"
        design["background"] = {"type": "gradient", "colors": ["#f5c400", "#e8a900"], "angle": 90}
        body = {"name": "Safety Day", "starts_on": d(0), "ends_on": d(1), "repeat_yearly": "N", "priority": 0, "is_published": "Y", "design": design}
        r = poster.post("/api/admin/banner-events/", body, format="json")
        ok("a rights-holder can create an event", r.status_code == 201, str(r.content[:240]))
        eid = r.json().get("event_id")
        ok("status is live", r.json().get("status") == "live")
        ok("admin can create", admin.post("/api/admin/banner-events/", {**body, "name": "Admin one", "starts_on": d(30), "ends_on": d(31)}, format="json").status_code == 201)
        ok("view-only cannot create", viewer.post("/api/admin/banner-events/", body, format="json").status_code == 403)
        ok("no rights cannot list", nobody.get("/api/admin/banner-events/").status_code == 403)
        ok("view-only can list", viewer.get("/api/admin/banner-events/").status_code == 200)
        ok("view-only cannot delete", viewer.delete(f"/api/admin/banner-events/{eid}/").status_code == 403)

        bad = lambda **kw: poster.post("/api/admin/banner-events/", {**body, "name": "x" + str(len(fails)), **kw}, format="json")
        n_events = iter(range(100, 1000, 2))
        def with_design(mut):
            k = next(n_events)
            return bad(design=(lambda dd: (mut(dd), dd)[1])(copy.deepcopy(design)), starts_on=d(k), ends_on=d(k + 1))
        ok("end before start refused", bad(starts_on=d(5), ends_on=d(2)).status_code == 400)
        ok("blank name refused", bad(name="  ").status_code == 400)
        ok("unknown design key refused", with_design(lambda dd: dd.update({"script": "x"})).status_code == 400)
        ok("html in the greeting refused", with_design(lambda dd: dd["text"].update({"greeting": "<img src=x onerror=alert(1)>"})).status_code == 400)
        ok("greeting too long refused", with_design(lambda dd: dd["text"].update({"greeting": "x" * 81})).status_code == 400)
        ok("a non-hex colour refused", with_design(lambda dd: dd["background"].update({"colors": ["red"]})).status_code == 400)
        ok("a css injection colour refused", with_design(lambda dd: dd["background"].update({"colors": ["#fff;background:url(x)"]})).status_code == 400)
        ok("too many colours refused", with_design(lambda dd: dd["background"].update({"colors": ["#111111"] * 4})).status_code == 400)
        ok("unknown pattern refused", with_design(lambda dd: dd["pattern"].update({"type": "image"})).status_code == 400)
        ok("opacity out of range refused", with_design(lambda dd: dd["pattern"].update({"opacity": 5})).status_code == 400)
        ok("unknown layout refused", with_design(lambda dd: dd.update({"layout": "free"})).status_code == 400)
        shape = {"id": "a1", "type": "star", "x": 300, "y": 120, "w": 90, "h": 90, "rot": 15, "fill": "#ffd700", "opacity": 0.9, "n": 5, "p": 0.45}
        ok("a valid shape is accepted", with_design(lambda dd: dd.update({"layers": [shape]})).status_code == 201)
        ok("a gradient and outline are accepted", with_design(lambda dd: dd.update({"layers": [{**shape, "fill2": "#ff0000", "grad": 45, "stroke": "#000000", "sw": 6}]})).status_code == 201)
        ok("a bad gradient colour refused", with_design(lambda dd: dd.update({"layers": [{**shape, "fill2": "red"}]})).status_code == 400)
        ok("an outline too thick refused", with_design(lambda dd: dd.update({"layers": [{**shape, "stroke": "#000000", "sw": 999}]})).status_code == 400)
        label = {"id": "t1", "type": "text", "x": 300, "y": 100, "w": 200, "h": 60, "text": "26 JAN", "size": 48, "bold": True, "font": "serif", "spacing": 4, "fill": "#ffffff"}
        ok("a text label is accepted", with_design(lambda dd: dd.update({"layers": [label]})).status_code == 201)
        ok("html in a text label refused", with_design(lambda dd: dd.update({"layers": [{**label, "text": "<b>x</b>"}]})).status_code == 400)
        ok("an empty text label refused", with_design(lambda dd: dd.update({"layers": [{**label, "text": "  "}]})).status_code == 400)
        ok("a text label too long refused", with_design(lambda dd: dd.update({"layers": [{**label, "text": "x" * 41}]})).status_code == 400)
        ok("an unknown font refused", with_design(lambda dd: dd.update({"layers": [{**label, "font": "comic"}]})).status_code == 400)
        ok("text settings on a plain shape refused", with_design(lambda dd: dd.update({"layers": [{**shape, "text": "hi"}]})).status_code == 400)
        ok("every built-in shape is accepted", with_design(lambda dd: dd.update({"layers": [{**shape, "id": f"k{i}", "type": ty} for i, ty in enumerate(["rect","circle","ring","triangle","diamond","star","sparkle","heart","moon","drop","leaf","wave","line","rig","ship","tree","cloud","sun","snowflake","helicopter","hardhat","drillbit","wrench","gear","cone","diya","kite","balloon","flag","spectacles","chakra","indiagate","redfort","tajmahal","qutub","jet","swoosh","book","mosque","lantern","splash","burst","temple","bauble","holly","flame","bananaleaf","ribbon","bow","modak","flower","bird","hand"])]})).status_code == 201)
        ok("an unknown shape type refused", with_design(lambda dd: dd.update({"layers": [{**shape, "type": "image"}]})).status_code == 400)
        ok("an unknown shape setting refused", with_design(lambda dd: dd.update({"layers": [{**shape, "href": "http://x"}]})).status_code == 400)
        ok("a shape colour that is not hex refused", with_design(lambda dd: dd.update({"layers": [{**shape, "fill": "url(#x)"}]})).status_code == 400)
        ok("a shape outside the allowed area refused", with_design(lambda dd: dd.update({"layers": [{**shape, "x": 99999}]})).status_code == 400)
        ok("a shape with a script-like id refused", with_design(lambda dd: dd.update({"layers": [{**shape, "id": "<x>"}]})).status_code == 400)
        ok("more than 120 shapes refused", with_design(lambda dd: dd.update({"layers": [{**shape, "id": f"s{i}"} for i in range(121)]})).status_code == 400)
        strip = {"edge": "top", "type": "garland", "size": 44, "colors": ["#fbbf24", "#f59e0b"], "opacity": 1, "spacing": 1}
        ok("a frame setting is accepted", with_design(lambda dd: dd.update({"frame": {"mode": "on", "color": "#336699"}})).status_code == 201)
        ok("an unknown frame mode refused", with_design(lambda dd: dd.update({"frame": {"mode": "x"}})).status_code == 400)
        ok("a bad frame colour refused", with_design(lambda dd: dd.update({"frame": {"mode": "on", "color": "blue"}})).status_code == 400)
        ok("a greeting and message font are accepted", with_design(lambda dd: dd["text"].update({"titleFont": "cinzel", "bodyFont": "lora"})).status_code == 201)
        ok("an unknown font refused", with_design(lambda dd: dd["text"].update({"titleFont": "comic"})).status_code == 400)
        ok("a text label may use a bundled font", with_design(lambda dd: dd.update({"layers": [{**label, "font": "pacifico"}]})).status_code == 201)
        ok("a border strip is accepted", with_design(lambda dd: dd.update({"edges": [strip]})).status_code == 201)
        ok("every strip kind is accepted", all(with_design(lambda dd, t=t: dd.update({"edges": [{**strip, "type": t}]})).status_code == 201 for t in ("toran", "bunting", "lights", "lanterns", "pearls", "icicles", "zigzag", "scallop", "waves", "stars", "diamonds", "bands")))
        ok("three border strips refused", with_design(lambda dd: dd.update({"edges": [strip, {**strip, "edge": "bottom"}, strip]})).status_code == 400)
        ok("an unknown strip kind refused", with_design(lambda dd: dd.update({"edges": [{**strip, "type": "x"}]})).status_code == 400)
        ok("a strip with no colours refused", with_design(lambda dd: dd.update({"edges": [{**strip, "colors": []}]})).status_code == 400)
        ok("a strip on the side refused", with_design(lambda dd: dd.update({"edges": [{**strip, "edge": "left"}]})).status_code == 400)
        ok("a strip with an unknown setting refused", with_design(lambda dd: dd.update({"edges": [{**strip, "z": 1}]})).status_code == 400)
        ok("exactly 120 shapes accepted", with_design(lambda dd: dd.update({"layers": [{**shape, "id": f"s{i}"} for i in range(120)]})).status_code == 201)
        ok("a soft search tint is accepted", with_design(lambda dd: dd.update({"search": {"tint": "#fff1f2"}})).status_code == 201)
        ok("a dark search tint refused", with_design(lambda dd: dd.update({"search": {"tint": "#1c448a"}})).status_code == 400)
        ok("a search tint that is not hex refused", with_design(lambda dd: dd.update({"search": {"tint": "pink"}})).status_code == 400)
        ok("an unknown search setting refused", with_design(lambda dd: dd.update({"search": {"tint": "#ffffff", "x": 1}})).status_code == 400)
        ok("a notice position is accepted", with_design(lambda dd: dd.update({"notice": {"x": 40, "y": 65}})).status_code == 201)
        ok("the older top / middle / bottom form still opens", with_design(lambda dd: dd.update({"notice": {"at": "middle"}})).status_code == 201)
        ok("a notice position outside the banner refused", with_design(lambda dd: dd.update({"notice": {"x": 140, "y": 0}})).status_code == 400)
        ok("a notice position that is not a number refused", with_design(lambda dd: dd.update({"notice": {"x": "left", "y": 0}})).status_code == 400)
        ok("an unknown notice setting refused", with_design(lambda dd: dd.update({"notice": {"x": 0, "y": 0, "z": 5}})).status_code == 400)
        ok("a good design is accepted", bad(design=design, starts_on=d(60), ends_on=d(61)).status_code == 201)

        # which event shows today
        a = BannerEvent.objects.get(pk=eid)
        live = nobody.get("/api/banner/active/").json()["event"]
        ok("anyone signed in gets today's banner", live and live["event_id"] == eid, str(live))
        ok("the reply is only the design", set(live) == {"event_id", "name", "design", "preview"})
        hi = poster.post("/api/admin/banner-events/", {**body, "name": "Higher", "priority": 5}, format="json").json()["event_id"]
        ok("higher priority wins an overlap", nobody.get("/api/banner/active/").json()["event"]["event_id"] == hi)
        ok("the list flags the overlap", "Higher" in str(poster.get(f"/api/admin/banner-events/{eid}/").json().get("overlaps")))
        poster.patch(f"/api/admin/banner-events/{hi}/", {"is_published": "N"}, format="json")
        ok("a draft never shows", nobody.get("/api/banner/active/").json()["event"]["event_id"] == eid)
        ok("no event today gives the normal banner", (lambda: (BannerEvent.objects.update(is_published="N"), nobody.get("/api/banner/active/").json()["event"])[1])() is None)
        BannerEvent.objects.filter(pk=hi).update(is_published="N")
        ok("preview of a draft for a rights-holder", viewer.get(f"/api/banner/active/?preview={hi}").json()["event"]["event_id"] == hi)
        ok("preview is refused for others", nobody.get(f"/api/banner/active/?preview={hi}").json()["event"] is None)
        BannerEvent.objects.filter(pk=eid).update(is_published="Y")
        # dates
        from types import SimpleNamespace as NS
        Dt = datetime.date
        yearly = NS(repeat_yearly="Y", starts_on=Dt(2020, 12, 28), ends_on=Dt(2021, 1, 3))
        ok("a yearly event wraps over New Year", covers(yearly, Dt(2030, 12, 30)) and covers(yearly, Dt(2031, 1, 2)) and not covers(yearly, Dt(2031, 6, 1)))
        one = NS(repeat_yearly="N", starts_on=Dt(2026, 1, 26), ends_on=Dt(2026, 1, 26))
        ok("a one-day event is inclusive", covers(one, Dt(2026, 1, 26)) and not covers(one, Dt(2026, 1, 27)) and not covers(one, Dt(2027, 1, 26)))
        raise Rollback()
except Rollback:
    pass
if fails:
    print("\nFAILED:", fails)
    sys.exit(1)
print("\nAll banner event checks passed.")
