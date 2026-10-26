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

# The one list of picture types every upload point accepts (the frontend mirrors it in src/lib/mediaTypes.js). Add a type here, add its
# leading bytes to _MAGIC_SIGNATURES below, and add it to the frontend list.
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")
DEFAULT_ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS + (".pdf",)
DEFAULT_MAX_SIZE_MB = 10

# Extensions that must never appear anywhere in an uploaded filename, even
# in a part that gets discarded — scripts/executables/markup that a
# misconfigured web server could end up executing, or that a browser could
# be tricked into treating as live content if a file ever got served with
# the wrong Content-Type.
_DANGEROUS_EXTENSIONS = {
    ".php", ".php3", ".php4", ".php5", ".phtml", ".pht",
    ".asp", ".aspx", ".jsp", ".jspx", ".sql",
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
    ".tif": [b"II*\x00", b"MM\x00*"],
    ".webp": [b"RIFF"],  # plus "WEBP" at byte 8, see _matches
    ".heic": [b""],  # Apple photos: an "ftyp" box with a HEIF brand, see _matches
    ".heif": [b""],
    ".pdf": [b"%PDF-"],
}


def _has_dangerous_extension(name):
    # Every dot-separated part of the *whole* filename, not just the
    # final suffix — "shell.php.jpg" must be caught here even though
    # os.path.splitext only ever sees the trailing ".jpg".
    parts = name.lower().split(".")
    return any(f".{p}" in _DANGEROUS_EXTENSIONS for p in parts[1:])


_HEIF_BRANDS = (b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1")


def _matches(head, ext):
    """Do a file's leading bytes fit what its extension claims?"""
    if not any(head.startswith(sig) for sig in _MAGIC_SIGNATURES[ext]):
        return False
    if ext == ".webp":
        return head[8:12] == b"WEBP"
    if ext in (".heic", ".heif"):
        return head[4:8] == b"ftyp" and head[8:12] in _HEIF_BRANDS
    return True


def _sniff_mismatch(f, ext):
    if ext not in _MAGIC_SIGNATURES:
        return False
    head = f.read(16)
    f.seek(0)
    return not _matches(head, ext)


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


def check_existing_file(abs_path, allowed_extensions=DEFAULT_ALLOWED_EXTENSIONS, max_size_mb=DEFAULT_MAX_SIZE_MB):
    """The same checks as save_media_file, for a file that is already on disk (the legacy media migration): returns an error string, or None
    when the file passes. One set of rules for what may live in the media folder, whether it arrived by upload or by migration."""
    name = os.path.basename(abs_path)
    ext = os.path.splitext(name)[1].lower()
    if ext not in allowed_extensions:
        return f"extension {ext or '(none)'} is not allowed"
    if _has_dangerous_extension(name):
        return "the file name is not allowed"
    if os.path.getsize(abs_path) > max_size_mb * 1024 * 1024:
        return f"larger than {max_size_mb} MB"
    with open(abs_path, "rb") as f:
        if _sniff_mismatch(f, ext):
            return "the contents do not match the extension"
    return None


def next_sequence(subfolder, prefix):
    """The next free number for files named <prefix>_<n>.<ext> in a media subfolder: one more than the highest number already on disk, so a
    new upload can never take the name of an existing file (migrated legacy files are named this way too, with gaps and an empty
    number, e.g. 109_.jpg)."""
    folder = os.path.join(settings.MEDIA_ROOT, subfolder)
    used = [0]
    if os.path.isdir(folder):
        for name in os.listdir(folder):
            stem = os.path.splitext(name)[0]
            head, sep, tail = stem.rpartition("_")
            if sep and head == str(prefix) and tail.isdigit():
                used.append(int(tail))
    return max(used) + 1


def detect_extension(abs_path):
    """The extension a file's own leading bytes say it has (".png" for a PNG saved as "x.jpg"), or None when it matches no known type."""
    with open(abs_path, "rb") as fh:
        head = fh.read(16)
    for ext in (".png", ".jpg", ".pdf"):
        if _matches(head, ext):
            return ext
    return None


# Which page's View right opens the files in each media folder. A folder that is not listed here is never served (for example the letterhead
# logos, which only the server reads). Administrators see every listed folder.
FOLDER_PAGES = {
    "incident_photos": "qhse.incident_details",
    "HSE_Drills_photos": "qhse.hse_drill_record",
    "fs_emp_photos": "masters.fs_employees",
    "signatures": "masters.doc_to_sign_mapping",
    "interviewer_signatures": "masters.interviewer_mapping",
    "rig_certificates": "qhse.rig_certificates",
    "training_cert": "qhse.training_log",
    "mst_employee_images": "admin.user_management",
    "birthday_templates": "admin.birthday_mailer",
}


def media_url(request, rel_path):
    """The address of a stored file. It is NOT a secret link: the file is fetched with the signed-in user's token (see MediaFileView), which checks
    the user's right to the page the file belongs to, so a link that is forwarded or logged opens nothing for anyone else."""
    if not rel_path:
        return None
    url = "/api/media/" + rel_path.lstrip("/")
    return request.build_absolute_uri(url) if request else url
