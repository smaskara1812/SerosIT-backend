"""One-time fix-up for HseDrillRecordPhotoUpload.drill_rec_photo_upload_path
once the legacy photo files have been copied into
backend/media/HSE_Drills_photos/.

The 187 migrated rows still carry the legacy path format
("/Images/HSE_Drills_Photos/<file>"), which doesn't match this app's own
convention (core/media_uploads.py: a path relative to MEDIA_ROOT, no
leading slash, served as MEDIA_URL + path). This rewrites each row to
"HSE_Drills_photos/<file>" — but only for rows whose file actually exists
on disk at that new location, so a partial/incomplete copy doesn't leave
rows pointing at files that aren't there.

One known data glitch: id 65's legacy path is "N/Images/HSE_Drills_Photos/65.jpg"
(a stray "N" baked into the path string itself, unrelated to its Active
flag, which is "Y") — handled below by matching on the filename at the end
of the path, not the prefix.

Run with:
    .venv/bin/python manage.py shell < scripts/fix_hse_drill_photo_paths.py

Defaults to a dry run (prints what it would change, touches nothing).
Set DRY_RUN = False below once the printed plan looks right.
"""

import os

from django.conf import settings

from core.models import HseDrillRecordPhotoUpload

DRY_RUN = True
SUBFOLDER = "HSE_Drills_photos"

rows = HseDrillRecordPhotoUpload.objects.all().order_by("drill_rec_photo_upload_id")
target_dir = os.path.join(settings.MEDIA_ROOT, SUBFOLDER)

updated, missing, already_ok = [], [], []

for row in rows:
    old_path = row.drill_rec_photo_upload_path or ""
    filename = old_path.rsplit("/", 1)[-1]
    if not filename:
        continue
    new_path = f"{SUBFOLDER}/{filename}"
    if old_path == new_path:
        already_ok.append(row.drill_rec_photo_upload_id)
        continue
    if not os.path.isfile(os.path.join(target_dir, filename)):
        missing.append((row.drill_rec_photo_upload_id, filename))
        continue
    updated.append((row.drill_rec_photo_upload_id, old_path, new_path))
    if not DRY_RUN:
        row.drill_rec_photo_upload_path = new_path
        row.save(update_fields=["drill_rec_photo_upload_path"])

print(f"{'Would update' if DRY_RUN else 'Updated'}: {len(updated)}")
for pk, old, new in updated[:10]:
    print(f"  {pk}: {old!r} -> {new!r}")
if len(updated) > 10:
    print(f"  ... and {len(updated) - 10} more")

print(f"\nAlready correct: {len(already_ok)}")

print(f"\nMissing on disk (skipped, not touched): {len(missing)}")
for pk, filename in missing[:20]:
    print(f"  id {pk}: expected {target_dir}/{filename}")
if len(missing) > 20:
    print(f"  ... and {len(missing) - 20} more")

if DRY_RUN:
    print("\nDRY_RUN is True — nothing was changed. Set DRY_RUN = False at the top of this script and re-run to apply.")
