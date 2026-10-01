"""Shared helper for every feature that saves a user-uploaded file under
MEDIA_ROOT (Rig Certificates, Interviewer signatures, Incident Photos,
HSE Drill Photos, ...).

One media root, one subfolder per feature, one naming convention: every
file is named after the id of the record it belongs to (or that record's
id plus a small disambiguator, e.g. Incident Photos' per-incident sequence
number) — never a random uuid, and never the original uploaded filename.
This mirrors the legacy convention (e.g. Interviewer signatures were
literally named "<user id>.jpg" on disk) and keeps an uploaded file's name
self-explanatory when browsing MEDIA_ROOT directly, not just through the
app. It also happens to be most of what closes off a double-extension
attack (e.g. "shell.php.jpg" or "photo.jpg.exe") — the original name is
discarded outright, only its extension survives, and only after the
checks below pass.

Validated here, in order, before a single byte is written:
  - the final extension (os.path.splitext takes the last one — so
    "shell.php.jpg" reads as ".jpg", not ".php") must be in the caller's
    allow-list;
  - no extension anywhere else in the original filename — the discarded
    part — may be a known dangerous one (_DANGEROUS_EXTENSIONS), since a
    file named that way is a red flag about where it came from even
    though the trailing part would be discarded either way;
  - declared size, checked before reading the body;
  - for the types this app actually accepts, the file's own leading bytes
    (_MAGIC_SIGNATURES) must match what the extension claims — catches a
    renamed script/executable that happens to carry an allowed extension,
    which a name/size check alone can't.
"""

import os

from django.conf import settings

DEFAULT_ALLOWED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".pdf")
DEFAULT_MAX_SIZE_MB = 10

# Extensions that must never appear anywhere in an uploaded filename, even
# in a part that gets discarded — scripts/executables/markup that a
# misconfigured web server could end up executing, or that a browser could
# be tricked into treating as live content if a file ever got served with
# the wrong Content-Type.
_DANGEROUS_EXTENSIONS = {
    ".php", ".php3", ".php4", ".php5", ".phtml", ".pht",
    ".asp", ".aspx", ".jsp", ".jspx",".exe",".ps1",".sql"
    ".exe", ".dll", ".com", ".bat", ".cmd", ".sh", ".bash", ".ps1",
    ".py", ".pyc", ".rb", ".pl", ".cgi",
    ".js", ".mjs", ".html", ".htm", ".svg", ".xml",
}

# Leading bytes for every extension this app actually hands to
# save_media_file (see the three call sites: Rig Certificates/Interviewer
# Signatures default to jpg/jpeg/png/pdf; Incident Photos adds
# bmp/gif/tiff). Checked against the real upload, not the claimed
# extension — a renamed .exe presented as "photo.jpg" fails here even
# though its name and declared size look fine.
_MAGIC_SIGNATURES = {
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".gif": [b"GIF87a", b"GIF89a"],
    ".bmp": [b"BM"],
    ".tiff": [b"II*\x00", b"MM\x00*"],
    ".pdf": [b"%PDF-"],
}


def _has_dangerous_extension(name):
    # Every dot-separated part of the *whole* filename, not just the
    # final suffix — "shell.php.jpg" must be caught here even though
    # os.path.splitext only ever sees the trailing ".jpg".
    parts = name.lower().split(".")
    return any(f".{p}" in _DANGEROUS_EXTENSIONS for p in parts[1:])


def _sniff_mismatch(f, ext):
    signatures = _MAGIC_SIGNATURES.get(ext)
    if not signatures:
        return False
    head = f.read(max(len(sig) for sig in signatures))
    f.seek(0)
    return not any(head.startswith(sig) for sig in signatures)


def save_media_file(f, subfolder, filename, allowed_extensions=DEFAULT_ALLOWED_EXTENSIONS, max_size_mb=DEFAULT_MAX_SIZE_MB):
    """Saves `f` (a Django UploadedFile) under MEDIA_ROOT/<subfolder>/<filename><ext>
    — `filename` should NOT include the extension, which is read off the
    upload itself. Returns (rel_path, error): rel_path is what to store in
    the DB (MEDIA_URL + rel_path is the servable URL), error is a
    user-facing string on failure.
    """
    ext = os.path.splitext(f.name)[1].lower()
    if ext not in allowed_extensions:
        return None, f"Only {', '.join(allowed_extensions)} files are allowed"
    if _has_dangerous_extension(f.name):
        return None, "This file's name isn't allowed."
    if f.size > max_size_mb * 1024 * 1024:
        return None, f"File exceeds {max_size_mb} MB limit"
    if _sniff_mismatch(f, ext):
        return None, "This file's contents don't match its extension."

    abs_dir = os.path.join(settings.MEDIA_ROOT, subfolder)
    os.makedirs(abs_dir, exist_ok=True)
    full_filename = f"{filename}{ext}"
    abs_path = os.path.join(abs_dir, full_filename)
    with open(abs_path, "wb") as out:
        for chunk in f.chunks():
            out.write(chunk)

    return f"{subfolder}/{full_filename}", None


def media_url(request, rel_path):
    if not rel_path:
        return None
    url = settings.MEDIA_URL + rel_path
    return request.build_absolute_uri(url) if request else url
