"""Shared helper for every feature that saves a user-uploaded file under
MEDIA_ROOT (Rig Certificates, Interviewer signatures, Incident Photos, ...).

One media root, one subfolder per feature, one naming convention: every
file is named after the id of the record it belongs to (or that record's
id plus a small disambiguator, e.g. Incident Photos' per-incident sequence
number) — never a random uuid. This mirrors the legacy convention (e.g.
Interviewer signatures were literally named "<user id>.jpg" on disk) and
keeps an uploaded file's name self-explanatory when browsing MEDIA_ROOT
directly, not just through the app.
"""

import os

from django.conf import settings

DEFAULT_ALLOWED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".pdf")
DEFAULT_MAX_SIZE_MB = 10


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
    if f.size > max_size_mb * 1024 * 1024:
        return None, f"File exceeds {max_size_mb} MB limit"

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
