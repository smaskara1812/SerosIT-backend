"""Checks the banner pictures with real uploads and real requests. Pictures go to a temporary folder (never the real media folder) and
everything in the database runs in one transaction that is rolled back.

    cd backend
    .venv/bin/python scripts/check_banner_assets.py
"""
import io, os, sys, shutil, tempfile, django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from PIL import Image
from rest_framework.test import APIClient
from core.models import BannerAsset, BannerEvent, UserPermission, UserProfile
from core.permissions import invalidate_user_access
from core import banner_assets as ba
from core.banner_events import clean_design
from rest_framework import serializers

TMP = tempfile.mkdtemp(prefix="banner_assets_check_")
settings.MEDIA_ROOT = TMP


class Rollback(Exception):
    pass


fails = []


def ok(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {detail}" if not cond else ""))
    if not cond:
        fails.append(name)


def mk(n, flags=("view",), admin=False, key="admin.banner_events"):
    U = get_user_model(); u = U.objects.create_user(username=n, password="x")
    uid = (UserProfile.objects.order_by("-user_id").first().user_id or 0) + 1
    UserProfile.objects.create(user_id=uid, user_login_id=n, is_app_admin=admin)
    if flags:
        UserPermission.objects.create(user_id=uid, menu_key=key, can_view="view" in flags, can_add="add" in flags, can_edit="edit" in flags, can_delete="delete" in flags)
    invalidate_user_access(n)
    c = APIClient(HTTP_HOST="localhost"); c.force_authenticate(u); return c


def png(size=(300, 200), mode="RGBA", color=(200, 30, 30, 255), alpha_hole=False):
    im = Image.new(mode, size, color)
    if alpha_hole:
        for x in range(size[0] // 2):
            for y in range(size[1] // 2):
                im.putpixel((x, y), (0, 0, 0, 0))
    out = io.BytesIO(); im.save(out, "PNG"); return out.getvalue()


def jpg(size=(400, 300), exif_orientation=None):
    im = Image.new("RGB", size, (30, 120, 200))
    out = io.BytesIO()
    if exif_orientation:
        ex = Image.Exif(); ex[0x0112] = exif_orientation; ex[0x010E] = "SECRET CAMERA NOTE"
        im.save(out, "JPEG", exif=ex)
    else:
        im.save(out, "JPEG")
    return out.getvalue()


def upload(c, data, name):
    return c.post("/api/admin/banner-assets/", {"file": SimpleUploadedFile(name, data)}, format="multipart")


try:
    with transaction.atomic():
        admin = mk("zzba0", admin=True)
        editor = mk("zzba1", ("view", "add", "edit", "delete"))
        viewer = mk("zzba2", ("view",))
        nobody = mk("zzba3", ())

        print("A. who may do what")
        ok("view-only cannot upload", upload(viewer, png(), "a.png").status_code == 403)
        ok("no rights cannot list", nobody.get("/api/admin/banner-assets/").status_code == 403)
        ok("view-only can list", viewer.get("/api/admin/banner-assets/").status_code == 200)

        print("B. a transparent PNG keeps its see-through parts")
        r = upload(editor, png(alpha_hole=True), "logo.png"); j = r.json()
        ok("accepted", r.status_code == 201, str(r.content[:200]))
        ok("recorded as see-through", j.get("has_alpha") is True and j.get("kind") == "png")
        stored = Image.open(os.path.join(TMP, BannerAsset.objects.get(pk=j["id"]).file_path))
        ok("the stored file is still RGBA with a see-through corner", stored.mode in ("RGBA", "P") and stored.convert("RGBA").getpixel((2, 2))[3] == 0)
        ok("the thumbnail is extremely small (data address under 6 KB)", j["thumb"].startswith("data:image/png;base64,") and len(j["thumb"]) < 6000, str(len(j.get("thumb", ""))))
        again = upload(editor, png(alpha_hole=True), "same-again.png")
        ok("the same picture sent again is the same row", again.status_code == 200 and again.json()["id"] == j["id"] and again.json()["existing"] is True)

        print("C. JPG and JPEG, metadata removed, turned upright")
        r = upload(editor, jpg(exif_orientation=6), "photo.jpeg"); jj = r.json()
        ok("a .jpeg photo is accepted", r.status_code == 201, str(r.content[:200]))
        f = os.path.join(TMP, BannerAsset.objects.get(pk=jj["id"]).file_path)
        im = Image.open(f)
        ok("the camera note is gone", b"SECRET CAMERA NOTE" not in open(f, "rb").read() and not im.getexif())
        ok("it was turned upright (400x300 sent sideways comes out 300 wide, 400 tall)", im.size == (300, 400), str(im.size))
        ok("an opaque picture is not marked see-through", jj["has_alpha"] is False)

        print("D. size limits")
        big = upload(editor, png((3200, 2400), "RGB", (10, 10, 10)), "big.png")
        ok("a large picture is shrunk to at most 1600 px and 400 KB", big.status_code == 201 and max(big.json()["width"], big.json()["height"]) <= 1600 and big.json()["bytes"] <= 400 * 1024, str(big.content[:160]))
        ok("a file over 5 MB is refused", upload(editor, b"\x89PNG" + os.urandom(6 * 1024 * 1024), "huge.png").status_code == 400)

        print("E. only real JPG and PNG pictures")
        ok("a text file named .png is refused", upload(editor, b"hello world", "x.png").status_code == 400)
        svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><script>alert(1)</script></svg>'
        ok("an SVG is refused by name", upload(editor, svg, "a.svg").status_code == 400)
        ok("an SVG renamed .png is refused", upload(editor, svg, "a.png").status_code == 400)
        gif = io.BytesIO(); Image.new("RGB", (20, 20)).save(gif, "GIF")
        ok("a GIF renamed .jpg is refused", upload(editor, gif.getvalue(), "a.jpg").status_code == 400)
        webp = io.BytesIO(); Image.new("RGB", (20, 20)).save(webp, "WEBP")
        ok("a WebP renamed .png is refused", upload(editor, webp.getvalue(), "a.png").status_code == 400)
        bomb = io.BytesIO(); Image.new("1", (30000, 30000)).save(bomb, "PNG")
        ok("a picture with hundreds of millions of pixels is refused", len(bomb.getvalue()) < 5 * 1024 * 1024 and upload(editor, bomb.getvalue(), "bomb.png").status_code == 400)
        ok("nothing was stored for the refused files", BannerAsset.objects.filter(is_builtin="N").count() == 3, str(BannerAsset.objects.count()))

        print("F. the Seros logos that come with the application")
        lib = editor.get("/api/admin/banner-assets/").json()
        built = [x for x in lib["results"] if x["builtin"]]
        ok("two built-in logos are in the library", len(built) == 2 and {b["name"] for b in built} == {n for _, n in ba.BUILTIN}, str([b["name"] for b in built]))
        ok("they are see-through PNGs", all(b["has_alpha"] and b["kind"] == "png" for b in built))
        ok("a built-in logo cannot be removed", editor.delete(f"/api/admin/banner-assets/{built[0]['id']}/").status_code == 400)

        print("G. everyone signed in can see a picture, nobody else")
        url = f"/api/banner/assets/{j['id']}/file/"
        r = nobody.get(url)
        ok("a signed-in user with no rights gets the picture", r.status_code == 200 and r["Content-Type"] == "image/png" and r["X-Content-Type-Options"] == "nosniff")
        ok("with a cache tag", bool(r["ETag"]) and "private" in r["Cache-Control"])
        ok("asking again with the tag gets 'not changed'", nobody.get(url, HTTP_IF_NONE_MATCH=r["ETag"]).status_code == 304)
        ok("signed out gets nothing", APIClient(HTTP_HOST="localhost").get(url).status_code in (401, 403))
        ok("an unknown picture is 404", nobody.get("/api/banner/assets/999999/file/").status_code == 404)

        print("H. pictures in a design")
        good = {"layers": [{"id": "p1", "type": "picture", "x": 300, "y": 120, "w": 200, "h": 120, "rot": 0, "fill": "#ffffff", "opacity": 1, "asset": j["id"]}]}
        ok("a design with a picture layer is accepted", clean_design(good)["layers"][0]["asset"] == j["id"])

        def bad(layers, what):
            try:
                clean_design({"layers": layers}); ok(what, False, "was accepted")
            except serializers.ValidationError:
                ok(what, True)
        pl = good["layers"][0]
        bad([{**pl, "asset": 987654}], "a picture that does not exist is refused")
        bad([{k: v for k, v in pl.items() if k != "asset"}], "a picture layer with no picture is refused")
        bad([{**pl, "type": "star"}], "a picture id on a shape that is not a picture is refused")
        bad([{**pl, "id": f"p{i}"} for i in range(7)], "more than six pictures in one design is refused")
        ok("six are fine", len(clean_design({"layers": [{**pl, "id": f"p{i}"} for i in range(6)]})["layers"]) == 6)
        ev = BannerEvent.objects.create(name="zz picture event", starts_on="2026-01-01", ends_on="2026-01-02", repeat_yearly="N", priority=0, is_published="N", design=clean_design(good), cr_user_id=0, cr_dt="2026-01-01")
        ok("the library says which event uses the picture", any(x["id"] == j["id"] and x["used_in"] == ["zz picture event"] for x in editor.get("/api/admin/banner-assets/").json()["results"]))
        ok("a picture in use cannot be removed (it names the event)", (lambda r: r.status_code == 409 and "zz picture event" in r.json()["detail"])(editor.delete(f"/api/admin/banner-assets/{j['id']}/")))
        ok("view-only cannot remove one", viewer.delete(f"/api/admin/banner-assets/{jj['id']}/").status_code == 403)
        ok("an unused picture can be removed, with its file", editor.delete(f"/api/admin/banner-assets/{jj['id']}/").status_code == 204 and not os.path.exists(f))
        BannerAsset.objects.filter(pk=j["id"]).delete()
        ok("a saved design whose picture has gone loads without it (the Home page never breaks)", clean_design(ev.design, strict=False)["layers"] == [])
        raise Rollback()
except Rollback:
    pass
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print()
print("FAILED: " + ", ".join(fails) if fails else "all checks passed")
sys.exit(1 if fails else 0)
