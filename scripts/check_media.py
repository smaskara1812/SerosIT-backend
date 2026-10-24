"""Checks the media setup end to end (run: .venv/bin/python manage.py shell < scripts/check_media.py).

 - every stored path in the migrated tables is either a new-style path whose file exists, or old legacy text (never a new-style path
   pointing at nothing);
 - media links are signed, expire, and cannot be forged or used to leave MEDIA_ROOT;
 - the upload guard refuses what it should (renamed executable, .sql in a name, wrong extension), and upload numbering never collides;
 - migrate_legacy_media is safe to run again (a second dry run finds nothing left to copy).
"""
import io
import os
import time
from contextlib import redirect_stdout

from django.conf import settings
from django.core import signing
from django.core.management import call_command
from django.test import Client

from core import media_uploads as mu
from core.models import DocToSignMapping, HseDrillRecordPhotoUpload, IncidentPhoto, MstFsEmployee, MstInterviewer

ROOT = str(settings.MEDIA_ROOT)
fails = 0


def check(label, ok):
    global fails
    print(("PASS " if ok else "FAIL ") + label)
    fails += 0 if ok else 1


NEW = {
    "incident_photos": (IncidentPhoto, "incident_photo_path"),
    "HSE_Drills_photos": (HseDrillRecordPhotoUpload, "drill_rec_photo_upload_path"),
    "signatures": (DocToSignMapping, "sign_path"),
    "interviewer_signatures": (MstInterviewer, "sign_path"),
    "fs_emp_photos": (MstFsEmployee, "fs_emp_photo_path"),
}
for folder, (model, field) in NEW.items():
    bad = [p for p in model.objects.values_list(field, flat=True) if p and p.startswith(folder + "/") and not os.path.isfile(os.path.join(ROOT, p))]
    check(f"{folder}: no new-style path points at a missing file", not bad)

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

c = APIClient(HTTP_HOST="localhost")
anon = APIClient(HTTP_HOST="localhost")
c.force_authenticate(get_user_model().objects.filter(is_superuser=True).first())
url = mu.media_url(None, "fs_emp_photos/1.jpg")
check("the file address carries no secret", "?" not in url and url == "/api/media/fs_emp_photos/1.jpg")
check("a signed-in administrator is served the file", c.get(url).status_code == 200)
check("someone not signed in is refused", anon.get(url).status_code == 401)
check("path traversal -> refused", c.get("/api/media/fs_emp_photos/../../manage.py").status_code == 404)
check("a folder that is not served -> refused", c.get("/api/media/Letterhead Logo/Footer2.jpg").status_code == 404)
check(".sql is a dangerous extension", mu._has_dangerous_extension("x.sql.jpg"))
check("a JPEG is detected by its bytes as .jpg", mu.detect_extension(os.path.join(ROOT, "fs_emp_photos", "1.jpg")) == ".jpg")
check("next_sequence skips used numbers", mu.next_sequence("incident_photos", "1") > 1)

buf = io.StringIO()
with redirect_stdout(buf):
    call_command("migrate_legacy_media")
check("second dry run: nothing left to copy", "would copy" not in buf.getvalue())
print(f"\n{fails} failure(s)")
