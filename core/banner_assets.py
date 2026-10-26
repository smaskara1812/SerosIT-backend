"""Admin > Banner Events: pictures for the home banner (JPG, JPEG and PNG, with see-through backgrounds kept).

Who may do what is the Banner Events page's own User Rights (menu key admin.banner_events): View to see the library, Add or Edit
to upload, Edit or Delete to remove one. Every signed-in person may FETCH a picture, because the banner is shown to everyone on the
Home page; the pictures are banner art and carry nothing private.

Nothing a person uploads is stored as it was sent. The file must really be a JPG or a PNG (its content is checked, not its name or
type), it is opened and re-encoded, and so loses any hidden data (location, camera, comments); it is turned upright, reduced to at
most MAX_SIDE pixels on its longest side and to at most MAX_BYTES. A picture with see-through parts stays a PNG. The result is named
by its own checksum, so the same picture is one row however often it is sent. A very small preview is made at the same time, as a
data address, for the editor's library.

SVG is not accepted (a decision for now): it is code, not just a picture.
"""

import hashlib
import io
import os
import base64

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import audit as _audit
from .models import BannerAsset, BannerEvent
from .notice_board import poster_name
from .permissions import holds_a_right_on

MENU_KEY = "admin.banner_events"
FOLDER = "banner_assets"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_BYTES = 400 * 1024
MAX_SIDE = 1600
MAX_PIXELS = 40_000_000  # refuse a picture that would need more memory than this to open (a "decompression bomb")
SIDE_STEPS = (1600, 1200, 900, 640, 480, 320)
THUMB_SIDE = 72
ALLOWED_EXTENSIONS = (".jpg", ".jpeg", ".png")
BUILTIN_DIR = os.path.join(os.path.dirname(__file__), "banner_logos")
BUILTIN = (  # (file in banner_logos, name shown in the library)
    ("seros-logo.png", "Seros logo (with text)"),
    ("seros-mark.png", "Seros mark"),
)


class PictureError(Exception):
    """A problem with the picture, worded for the person who sent it."""


def _pil():
    from PIL import Image, ImageOps

    return Image, ImageOps


def _has_alpha(img):
    """True when some part of the picture is actually see-through (an alpha channel that is fully opaque does not count)."""
    if img.mode in ("RGBA", "LA"):
        low, _ = img.getchannel("A").getextrema()
        return low < 255
    if img.mode == "P" and "transparency" in img.info:
        return True
    return False


def _png(img):
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()


def _jpeg(img, quality=85):
    out = io.BytesIO()
    img.save(out, "JPEG", quality=quality, optimize=True, progressive=True)
    return out.getvalue()


def _fit(img, side):
    w, h = img.size
    if max(w, h) <= side:
        return img
    scale = side / max(w, h)
    return img.resize((max(1, round(w * scale)), max(1, round(h * scale))), _pil()[0].LANCZOS)


def process_upload(data, filename=""):
    """The bytes of a sent file -> (stored bytes, kind 'png'|'jpg', has_alpha, width, height, thumb data address).
    Raises PictureError, with a message for the person, when the file cannot be used."""
    Image, ImageOps = _pil()
    if len(data) > MAX_UPLOAD_BYTES:
        raise PictureError(f"That file is {len(data) / 1048576:.1f} MB. A picture can be at most {MAX_UPLOAD_BYTES // 1048576} MB.")
    ext = os.path.splitext(filename or "")[1].lower()
    if ext and ext not in ALLOWED_EXTENSIONS:
        raise PictureError("Only JPG, JPEG and PNG pictures can be used here.")
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        probe = Image.open(io.BytesIO(data))
        fmt = probe.format
        probe.verify()
        img = Image.open(io.BytesIO(data))
        if img.size[0] * img.size[1] > MAX_PIXELS:
            raise PictureError("That picture has too many pixels. Reduce its size and try again.")
        img.load()
    except PictureError:
        raise
    except Image.DecompressionBombError:
        raise PictureError("That picture has too many pixels. Reduce its size and try again.")
    except Exception:
        raise PictureError("That file is not a picture that can be read. Use a JPG, JPEG or PNG.")
    if fmt not in ("JPEG", "PNG"):
        raise PictureError("Only JPG, JPEG and PNG pictures can be used here.")
    img = ImageOps.exif_transpose(img)  # upright, as the camera meant it
    if img.size[0] < 4 or img.size[1] < 4:
        raise PictureError("That picture is too small to use.")
    alpha = _has_alpha(img)
    img = img.convert("RGBA") if alpha else img.convert("RGB")
    img = _fit(img, MAX_SIDE)

    body, kind = None, None
    for side in SIDE_STEPS:
        cand = _fit(img, side)
        if alpha:
            body, kind = _png(cand), "png"
            if len(body) > MAX_BYTES:  # fewer colours, same see-through edges
                q = cand.quantize(256, method=Image.Quantize.FASTOCTREE)
                body = _png(q)
        else:
            j, p = _jpeg(cand), _png(cand)
            body, kind = (p, "png") if len(p) <= len(j) else (j, "jpg")  # flat artwork is smaller as PNG, photographs as JPG
        if len(body) <= MAX_BYTES:
            img = cand
            break
    else:
        raise PictureError("That picture is still too large after shrinking it. Try a simpler picture.")
    final = Image.open(io.BytesIO(body))
    return body, kind, alpha, final.size[0], final.size[1], _thumb(img, alpha)


def _thumb(img, alpha):
    """An extremely small preview, as a data address: a few kilobytes at most."""
    Image, _ = _pil()
    t = _fit(img.copy(), THUMB_SIDE)
    if alpha:
        out = io.BytesIO()
        t.quantize(16, method=Image.Quantize.FASTOCTREE).save(out, "PNG", optimize=True)
        mime = "image/png"
    else:
        out = io.BytesIO()
        t.convert("RGB").save(out, "JPEG", quality=28, optimize=True)
        mime = "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(out.getvalue()).decode("ascii")


def _store(data, kind, name, request=None, builtin=False, alpha=False, width=0, height=0, thumb="", user=None):
    sha = hashlib.sha256(data).hexdigest()
    existing = BannerAsset.objects.filter(sha256=sha).first()
    if existing:
        return existing, False
    rel = f"{FOLDER}/{sha[:24]}.{kind}"
    path = os.path.join(settings.MEDIA_ROOT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):  # named by checksum: an existing file is already these exact bytes
        tmp = path + ".part"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    row = BannerAsset.objects.create(
        name=(name or "Picture")[:80], file_path=rel, kind=kind, has_alpha="Y" if alpha else "N", width=width, height=height,
        size_bytes=len(data), sha256=sha, thumb_data=thumb, is_builtin="Y" if builtin else "N",
        posted_by_name=poster_name(user) if user else "Seros", cr_user_id=0, cr_dt=timezone.now(),
    )
    return row, True


def ensure_builtin_assets():
    """The Seros logos that come with the application. Safe to call at any time: it adds only what is missing."""
    for fname, label in BUILTIN:
        src = os.path.join(BUILTIN_DIR, fname)
        if not os.path.exists(src) or BannerAsset.objects.filter(is_builtin="Y", name=label).exists():
            continue
        with open(src, "rb") as f:
            body, kind, alpha, w, h, thumb = process_upload(f.read(), fname)
        row, created = _store(body, kind, label, builtin=True, alpha=alpha, width=w, height=h, thumb=thumb)
        if not created and row.is_builtin != "Y":
            BannerAsset.objects.filter(pk=row.pk).update(is_builtin="Y", name=label)


def pictures_in(design):
    """The asset ids a design's picture layers use."""
    return [l.get("asset") for l in (design or {}).get("layers", []) if isinstance(l, dict) and l.get("type") == "picture" and l.get("asset") is not None]


def usage():
    """{asset id: [names of the events that use it]}"""
    out = {}
    for ev in BannerEvent.objects.all():
        for aid in set(pictures_in(ev.design)):
            out.setdefault(aid, []).append(ev.name)
    return out


def _row(a, used):
    return {
        "id": a.asset_id, "name": a.name, "kind": a.kind, "has_alpha": a.has_alpha == "Y", "width": a.width, "height": a.height,
        "bytes": a.size_bytes, "thumb": a.thumb_data, "builtin": a.is_builtin == "Y", "used_in": used.get(a.asset_id, []),
        "posted_by": a.posted_by_name or "", "posted_at": a.cr_dt,
    }


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def assets_api(request):
    """GET: the library. POST (multipart, field `file`, optional `name`): add a picture, or get back the one already stored."""
    if request.method == "GET":
        if not holds_a_right_on(request, [MENU_KEY], flags=("view",)):
            return Response({"detail": "You do not have access to the banner pictures."}, status=403)
        ensure_builtin_assets()
        used = usage()
        rows = BannerAsset.objects.order_by("-is_builtin", "-asset_id")
        return Response({"results": [_row(a, used) for a in rows], "limits": {"max_upload_mb": MAX_UPLOAD_BYTES // 1048576, "max_kb": MAX_BYTES // 1024, "max_side": MAX_SIDE}})
    if not holds_a_right_on(request, [MENU_KEY], flags=("add", "edit")):
        return Response({"detail": "You do not have the right to add banner pictures."}, status=403)
    f = request.FILES.get("file")
    if not f:
        return Response({"detail": "Choose a picture first."}, status=400)
    try:
        body, kind, alpha, w, h, thumb = process_upload(f.read(), f.name)
    except PictureError as exc:
        return Response({"detail": str(exc)}, status=400)
    stem = os.path.splitext(os.path.basename(f.name or "Picture"))[0].strip() or "Picture"
    name = (request.data.get("name") or stem).strip()[:80]
    row, created = _store(body, kind, name, request, alpha=alpha, width=w, height=h, thumb=thumb, user=request.user)
    if created:
        _audit.record_action(request, "create", MENU_KEY, row.asset_id, f"Banner picture: {row.name}", {"file": {"old": None, "new": row.file_path}, "size_bytes": {"old": None, "new": row.size_bytes}})
    return Response({**_row(row, usage()), "existing": not created}, status=201 if created else 200)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def asset_detail_api(request, asset_id):
    if not holds_a_right_on(request, [MENU_KEY], flags=("edit", "delete")):
        return Response({"detail": "You do not have the right to remove banner pictures."}, status=403)
    a = BannerAsset.objects.filter(pk=asset_id).first()
    if not a:
        return Response({"detail": "That picture no longer exists."}, status=404)
    if a.is_builtin == "Y":
        return Response({"detail": "The Seros logos come with the application and cannot be removed."}, status=400)
    used = usage().get(a.asset_id, [])
    if used:
        return Response({"detail": "This picture is used by " + ", ".join(sorted(set(used))[:5]) + ". Remove it from there first."}, status=409)
    path = os.path.join(settings.MEDIA_ROOT, a.file_path)
    label, rel = a.name, a.file_path
    a.delete()
    try:
        os.remove(path)
    except OSError:
        pass
    _audit.record_action(request, "delete", MENU_KEY, asset_id, f"Banner picture: {label}", {"file": {"old": rel, "new": None}})
    return Response(status=204)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def asset_file_api(request, asset_id):
    """The picture itself, for any signed-in user: the Home banner needs it. Sent with the checksum as ETag so a browser asks only 'has it changed?'."""
    a = BannerAsset.objects.filter(pk=asset_id).first()
    if not a:
        raise Http404
    etag = f'"{a.sha256[:32]}"'
    if request.META.get("HTTP_IF_NONE_MATCH") == etag:
        r = HttpResponse(status=304)
        r["ETag"] = etag
        r["Cache-Control"] = "private, max-age=86400"
        return r
    path = os.path.join(settings.MEDIA_ROOT, a.file_path)
    if not os.path.isfile(path):
        raise Http404
    resp = FileResponse(open(path, "rb"), content_type="image/png" if a.kind == "png" else "image/jpeg")
    resp["ETag"] = etag
    resp["Cache-Control"] = "private, max-age=86400"
    resp["X-Content-Type-Options"] = "nosniff"
    resp["Content-Disposition"] = "inline"
    return resp
