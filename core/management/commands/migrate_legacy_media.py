"""Moves the legacy system's media files into MEDIA_ROOT and rewrites the paths stored in the database to match.

Only what the rebuilt pages use is migrated (Incident Photos, HSE Drill Photos, Interviewer signatures, Doc To Sign signatures, FS employee
photos). Folder names stay as the app already uses them (core/media_uploads.py). For every row:

  - the legacy path is reduced to its file name (the stored text comes in several shapes: "/Images/X/1.jpg", "N/Images/X/1.jpg",
    "NE:\\EBS_Projects\\...\\X\\1.jpg"), the file is looked up in the legacy folder ignoring letter case;
  - the file is checked with the same guard the upload endpoints use (core.media_uploads.check_existing_file);
  - only when the file was found, passed the check and is now in MEDIA_ROOT does the row's path change to "<subfolder>/<file>". A row
    whose file is missing or rejected keeps its old text untouched (nothing is cleared), and is listed in the report.

Dry run by default; nothing is copied or changed without --apply. Safe to run again: files already in place with the same size are left
alone, and rows already holding a new-style path are skipped. A file that exists at the destination with a different size is never
overwritten (reported as a conflict).

    python manage.py migrate_legacy_media                      # dry run
    python manage.py migrate_legacy_media --apply
    python manage.py migrate_legacy_media --source D:\\legacy\\Images --report D:\\out\\media_report.csv
"""

import csv
import os
import re
import shutil

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from core.media_uploads import IMAGE_EXTENSIONS, check_existing_file, detect_extension
from core.models import (
    DocToSignMapping,
    HseDrillRecordPhotoUpload,
    IncidentPhoto,
    MstFsEmployee,
    MstInterviewer,
)

IMAGE_EXTS = INCIDENT_EXTS = IMAGE_EXTENSIONS


def _file_name(stored):
    """The last path part of a stored legacy path, whatever slash or drive style it was written in."""
    return re.split(r"[\\/]", (stored or "").strip())[-1]


class Target:
    """One kind of file: which legacy folder it comes from, where it goes, which rows point at it."""

    def __init__(self, label, source_dir, subfolder, model, field, pk, exts, name_for=None):
        self.label, self.source_dir, self.subfolder = label, source_dir, subfolder
        self.model, self.field, self.pk, self.exts = model, field, pk, exts
        self.name_for = name_for  # (row, legacy file name) -> destination file name; default keeps the legacy name


def _fs_name(row, legacy):
    return f"{row.fs_emp_id}{os.path.splitext(legacy)[1].lower()}"


TARGETS = [
    Target("Incident photos", "Incident_Photos", "incident_photos", IncidentPhoto, "incident_photo_path", "incident_photo_id", INCIDENT_EXTS),
    Target("HSE drill photos", "HSE_Drills_Photos", "HSE_Drills_photos", HseDrillRecordPhotoUpload, "drill_rec_photo_upload_path",
           "drill_rec_photo_upload_id", INCIDENT_EXTS),
    Target("Doc To Sign signatures", "Signatures", "signatures", DocToSignMapping, "sign_path", "doc_to_sign_id", IMAGE_EXTS),
    Target("FS employee photos", "Fs_Emp_Photos", "fs_emp_photos", MstFsEmployee, "fs_emp_photo_path", "fs_emp_id", IMAGE_EXTS, _fs_name),
]


class Command(BaseCommand):
    help = "Copy legacy media into MEDIA_ROOT and rewrite the stored paths (dry run unless --apply)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="really copy files and change the database")
        parser.add_argument("--source", default=None, help="the legacy Images folder (default: <project>/Images)")
        parser.add_argument("--report", default=None, help="CSV report path (default: <project>/documents/media_migration/report.csv)")

    def handle(self, *args, **opts):
        apply = opts["apply"]
        project = os.path.dirname(os.path.abspath(settings.BASE_DIR))
        source = opts["source"] or os.path.join(project, "Images")
        report = opts["report"] or os.path.join(project, "documents", "media_migration", "report.csv")
        if not os.path.isdir(source):
            self.stderr.write(f"Legacy folder not found: {source}")
            return
        self.stdout.write(f"{'APPLY' if apply else 'DRY RUN'} - source {source}, target {settings.MEDIA_ROOT}\n")
        lines = []
        for t in TARGETS:
            lines += self._run_target(t, source, apply)
        lines += self._run_interviewers(source, apply)
        os.makedirs(os.path.dirname(report), exist_ok=True)
        with open(report, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["target", "row id", "old path", "new path", "result"])
            w.writerows(lines)
        self.stdout.write(f"\nReport: {report}")
        if not apply:
            self.stdout.write("Nothing was changed (dry run). Re-run with --apply to do it.")

    # -- helpers ----------------------------------------------------------------------------------------------------

    def _index(self, folder):
        """lower-cased file name -> real file name for one legacy folder."""
        if not os.path.isdir(folder):
            return {}
        return {n.lower(): n for n in os.listdir(folder) if os.path.isfile(os.path.join(folder, n))}

    def _place(self, src, subfolder, dest_name, exts, apply):
        """Check and copy one file. Returns (ok, why, final file name). A genuine image saved under the wrong extension (a PNG named
        .jpg, common for pasted screenshots) is kept under its true extension; anything else the guard refuses stays behind."""
        err = check_existing_file(src, allowed_extensions=exts)
        if err:
            # the content check is the last one the guard makes, so the name and size were fine; the bytes say what the file really is
            true_ext = detect_extension(src) if "contents do not match" in err else None
            if true_ext not in exts:
                return False, f"rejected: {err}", dest_name
            dest_name = os.path.splitext(dest_name)[0] + true_ext
        dest_dir = os.path.join(str(settings.MEDIA_ROOT), subfolder)
        dest = os.path.join(dest_dir, dest_name)
        if os.path.exists(dest):
            if os.path.getsize(dest) != os.path.getsize(src):
                return False, "conflict: a different file is already there", dest_name
            return True, "already in place", dest_name
        if apply:
            os.makedirs(dest_dir, exist_ok=True)
            shutil.copy2(src, dest)
        return True, "copied" if apply else "would copy", dest_name

    def _run_target(self, t, source, apply):
        folder = os.path.join(source, t.source_dir)
        index = self._index(folder)
        out, counts = [], {}
        updates = []
        for row in t.model.objects.all().order_by(t.pk):
            old = getattr(row, t.field) or ""
            pk = getattr(row, t.pk)
            if not old or old.startswith(t.subfolder + "/"):
                continue
            legacy = _file_name(old)
            real = index.get(legacy.lower())
            if not real:
                result, new = "file missing, old text kept", ""
            else:
                dest_name = t.name_for(row, real) if t.name_for else legacy
                ok, why, dest_name = self._place(os.path.join(folder, real), t.subfolder, dest_name, t.exts, apply)
                result, new = why, f"{t.subfolder}/{dest_name}" if ok else ""
                if ok:
                    updates.append((row, new))
            counts[result.split(":")[0]] = counts.get(result.split(":")[0], 0) + 1
            out.append((t.label, pk, old, new, result))
        if apply and updates:
            with transaction.atomic():
                for row, new in updates:
                    t.model.objects.filter(**{t.pk: getattr(row, t.pk)}).update(**{t.field: new})
        self._summary(t.label, counts, len(updates), apply)
        return out

    def _run_interviewers(self, source, apply):
        folder = os.path.join(source, "Crew_Interviewer")
        files = {}
        for n in self._index(folder).values():
            stem, ext = os.path.splitext(n)
            if ext.lower() in IMAGE_EXTS:
                files.setdefault(stem, n)
        out, counts, updates = [], {}, []
        for row in MstInterviewer.objects.all().order_by("interviewer_id"):
            if row.sign_path:
                continue
            real = files.get(str(row.user_id))
            if not real:
                result, new = "no file for this user, left empty", ""
            else:
                dest_name = f"{row.user_id}{os.path.splitext(real)[1].lower()}"
                ok, why, dest_name = self._place(os.path.join(folder, real), "interviewer_signatures", dest_name, IMAGE_EXTS, apply)
                result, new = why, f"interviewer_signatures/{dest_name}" if ok else ""
                if ok:
                    updates.append((row, new))
            counts[result.split(":")[0]] = counts.get(result.split(":")[0], 0) + 1
            out.append(("Interviewer signatures", row.interviewer_id, row.sign_path or "", new, result))
        if apply and updates:
            with transaction.atomic():
                for row, new in updates:
                    MstInterviewer.objects.filter(interviewer_id=row.interviewer_id).update(sign_path=new)
        self._summary("Interviewer signatures", counts, len(updates), apply)
        return out

    def _summary(self, label, counts, rows_changed, apply):
        parts = ", ".join(f"{n} {k}" for k, n in sorted(counts.items())) or "nothing to do"
        self.stdout.write(f"{label}: {parts}; rows {'changed' if apply else 'that would change'}: {rows_changed}")
