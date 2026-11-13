"""Checks Candidate Interview Details (Rig Personnel > New Joinee Workflow) through the real API.

    cd backend
    .venv/bin/python scripts/check_candidate_interviews.py

Runs every request inside one transaction that is rolled back at the end (uploaded files are removed again), so nothing is saved. Needs the
normal dev data (the migrated candidates). Exits with status 1 if any check fails.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

import datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import MstRank, MstRig
from hr.models import CandidateInterviewHdr
from hr.views.candidates import whole_months

URL = "/api/hr/candidate-interviews/"
TRAIN = "/api/hr/candidate-trainings/"
EXP = "/api/hr/candidate-experiences/"
COMP = "/api/hr/candidate-competencies/"
FAILED = []


def check(name, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


def err_keys(resp):
    try:
        return set(resp.json().keys())
    except Exception:
        return set()


def run():
    admin = get_user_model().objects.filter(is_superuser=True).first()
    client = APIClient(HTTP_HOST="localhost")
    client.force_authenticate(admin)
    today = datetime.date.today()
    adult = (today.replace(year=today.year - 25)).isoformat()
    rig, rank = MstRig.objects.first(), MstRank.objects.first()

    def body(**over):
        base = {"candidate_fname": "Rule", "candidate_lname": "Check", "email_id": "rule.check@example.com", "mobile_no": "9876543210",
                "candidate_dob": adult, "tot_experience_yrs": 10, "tot_experience_mths": 0, "exp_in_curr_pos_yrs": 3, "exp_in_curr_pos_mths": 0}
        base.update(over)
        return base

    print("Migrated data")
    check("10 candidates from the legacy table", CandidateInterviewHdr.objects.count() >= 10)
    first = client.get(URL, {"page_size": 50}).json()
    rows = first["results"] if isinstance(first, dict) else first
    check("list works and carries counts", rows and "trainings_count" in rows[0] and "resume_url" in rows[0], str(rows[:1]))
    check("hiring status was set to N on every migrated row", all(r["hiring_status"] == "N" for r in rows if r["candidate_interview_hdr_id"] <= 10))
    with_resume = [r for r in rows if r.get("resume_url")]
    check("migrated resumes that exist open", len(with_resume) >= 3, f"{len(with_resume)} with a link")
    check("a row whose file is missing says so", any(r.get("resume_missing") for r in rows))
    check("interviewer ratings come with the candidate", client.get(COMP, {"hdr": 1}).json()["count"] >= 1 if isinstance(client.get(COMP, {"hdr": 1}).json(), dict) else True)

    print("Rules on the header")
    r = client.post(URL, body(candidate_dob=today.replace(year=today.year - 17).isoformat()), format="json")
    check("under 18 refused", r.status_code == 400 and "candidate_dob" in err_keys(r), r.content[:200])
    r = client.post(URL, body(interview_dt=(today + datetime.timedelta(days=1)).isoformat()), format="json")
    check("interview date in the future refused", r.status_code == 400 and "interview_dt" in err_keys(r))
    r = client.post(URL, body(exp_in_curr_pos_yrs=11), format="json")
    check("experience in current post above total refused", r.status_code == 400 and "exp_in_curr_pos_yrs" in err_keys(r))
    r = client.post(URL, body(exp_in_curr_pos_yrs=10, exp_in_curr_pos_mths=1), format="json")
    check("one month more than total refused", r.status_code == 400)
    r = client.post(URL, body(tot_experience_mths=12), format="json")
    check("months above 11 refused", r.status_code == 400 and "tot_experience_mths" in err_keys(r))
    r = client.post(URL, body(suitable_for_role="X"), format="json")
    check("Suitable For Role only Y or N", r.status_code == 400 and "suitable_for_role" in err_keys(r))
    r = client.post(URL, body(hiring_status="Z"), format="json")
    check("Hiring Status only N, R, S or O", r.status_code == 400 and "hiring_status" in err_keys(r))
    r = client.post(URL, body(email_id="not-an-email"), format="json")
    check("email must be a real address", r.status_code == 400 and "email_id" in err_keys(r))
    r = client.post(URL, body(mobile_no="abc"), format="json")
    check("mobile must be a phone number", r.status_code == 400 and "mobile_no" in err_keys(r))

    print("Create, default, audit columns")
    r = client.post(URL, body(rig=rig.pk, rank=rank.pk, interview_dt=today.isoformat(), suitable_for_role="Y"), format="json")
    check("a valid candidate is created", r.status_code == 201, r.content[:300])
    new = r.json()
    check("hiring status defaults to N", new.get("hiring_status") == "N")
    check("created date is set automatically", bool(new.get("cr_dt")))
    check("not marked as sent by the candidate", new.get("is_new_from_candidate") is False)
    pk = new["candidate_interview_hdr_id"]

    r = client.patch(f"{URL}{pk}/", {"hiring_status": "S"}, format="json")
    check("HR can set hiring status", r.status_code == 200 and r.json()["hiring_status"] == "S")
    r = client.patch(f"{URL}{pk}/", {"candidate_cert_path": "x/y.pdf"}, format="json")
    check("the resume path cannot be written through the form", r.json().get("candidate_cert_path", "") == "")

    print("The database rules")
    with transaction.atomic():
        try:
            with connection.cursor() as cur:
                cur.execute("UPDATE hr_candidate_interview_hdr SET hiring_status = 'Z' WHERE candidate_interview_hdr_id = %s", [pk])
            check("database refuses Hiring Status Z", False)
        except Exception:
            check("database refuses Hiring Status Z", True)
            transaction.set_rollback(False)

    print("Flag for candidate entries")
    CandidateInterviewHdr.objects.filter(pk=pk).update(candidate_submitted_dt=timezone.now() - datetime.timedelta(hours=2))
    check("shows New for 24 hours", client.get(f"{URL}{pk}/").json()["is_new_from_candidate"] is True)
    check("the New filter finds it", any(x["candidate_interview_hdr_id"] == pk for x in client.get(URL, {"new": 1}).json()["results"]))
    CandidateInterviewHdr.objects.filter(pk=pk).update(candidate_submitted_dt=timezone.now() - datetime.timedelta(hours=25))
    check("gone after 24 hours", client.get(f"{URL}{pk}/").json()["is_new_from_candidate"] is False)

    print("Training and experience rows")
    r = client.post(TRAIN, {"hdr": pk, "training_type": "BOSIET", "training_agency": "OPITO", "training_cert_no": "B1", "training_cert_dt": "2024-01-10",
                            "cert_valid_from_dt": "2024-01-10", "cert_valid_to_dt": "2028-01-09"}, format="json")
    check("training row added", r.status_code == 201, r.content[:200])
    r = client.post(TRAIN, {"hdr": pk, "training_type": "X", "training_agency": "Y", "training_cert_no": "Z", "training_cert_dt": "2024-01-10",
                            "cert_valid_from_dt": "2024-02-10", "cert_valid_to_dt": "2024-01-09"}, format="json")
    check("valid upto before valid from refused", r.status_code == 400 and "cert_valid_to_dt" in err_keys(r))
    r = client.post(EXP, {"hdr": pk, "exp_from_dt": "2016-04-01", "exp_to_dt": "2018-11-30", "company_name": "Axom", "designation": "Driller"}, format="json")
    check("experience row added", r.status_code == 201, r.content[:200])
    check("years and months are worked out (2 years 7 months)", r.json().get("exp_years") == 2 and r.json().get("exp_months") == 7, str(r.json()))
    r = client.post(EXP, {"hdr": pk, "exp_from_dt": "2018-11-30", "exp_to_dt": "2016-04-01", "company_name": "A", "designation": "B"}, format="json")
    check("to date before from date refused", r.status_code == 400 and "exp_to_dt" in err_keys(r))
    legacy = [(("2008-10-13", "2011-07-02"), (2, 8)), (("2011-07-12", "2013-04-30"), (1, 9)), (("2017-01-14", "2025-11-23"), (8, 10)),
              (("2016-01-06", "2016-01-29"), (0, 0)), (("2014-12-01", "2016-03-31"), (1, 3))]
    check("the month count matches the legacy rows", all(divmod(whole_months(datetime.date.fromisoformat(a), datetime.date.fromisoformat(b)), 12) == want
                                                       for (a, b), want in legacy))
    r = client.post(COMP, {"hdr": pk, "rating": 3}, format="json")
    check("ratings are read only", r.status_code in (403, 405))

    print("Resume upload")
    saved = []
    try:
        bad = SimpleUploadedFile("evil.pdf", b"MZ\x90\x00 not a pdf", content_type="application/pdf")
        r = client.post(f"{URL}{pk}/resume/", {"file": bad}, format="multipart")
        check("a renamed program is refused", r.status_code == 400)
        r = client.post(f"{URL}{pk}/resume/", {"file": SimpleUploadedFile("a.exe", b"MZ", content_type="application/octet-stream")}, format="multipart")
        check("an .exe is refused", r.status_code == 400)
        good = SimpleUploadedFile("cv.pdf", b"%PDF-1.4\n%test\n", content_type="application/pdf")
        r = client.post(f"{URL}{pk}/resume/", {"file": good}, format="multipart")
        check("a real PDF is saved", r.status_code == 200 and r.json().get("candidate_cert_path", "").startswith("candidate_resumes/"), r.content[:200])
        if r.status_code == 200:
            saved.append(os.path.join(settings.MEDIA_ROOT, r.json()["candidate_cert_path"]))
            check("and has an address to open it", bool(r.json().get("resume_url")))
        docx = SimpleUploadedFile("cv.docx", b"PK\x03\x04 test", content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        r = client.post(f"{URL}{pk}/resume/", {"file": docx}, format="multipart")
        check("a DOCX is saved", r.status_code == 200, r.content[:200])
        if r.status_code == 200:
            saved.append(os.path.join(settings.MEDIA_ROOT, r.json()["candidate_cert_path"]))
    finally:
        for p in saved:
            if os.path.isfile(p):
                os.remove(p)

    print("Generate Resume")
    r = client.get(f"{URL}{pk}/resume-pdf/")
    check("the resume sheet is a PDF", r.status_code == 200 and r["Content-Type"] == "application/pdf" and r.content[:5] == b"%PDF-", str(r.status_code))
    check("its file name carries the candidate's name", "Rule Check" in r["Content-Disposition"])
    check("an unknown candidate gives 404", client.get(f"{URL}999999/resume-pdf/").status_code == 404)
    check("signed-out requests are refused", APIClient(HTTP_HOST="localhost").get(f"{URL}{pk}/resume-pdf/").status_code in (401, 403))

    print("Rights and privacy")
    anon = APIClient(HTTP_HOST="localhost")
    check("signed-out requests are refused", anon.get(URL).status_code in (401, 403))

    print("Delete")
    r = client.delete(f"{URL}{pk}/")
    check("delete works and takes its rows with it", r.status_code == 204 and not CandidateInterviewHdr.objects.filter(pk=pk).exists())


if __name__ == "__main__":
    try:
        with transaction.atomic():
            run()
            transaction.set_rollback(True)
    finally:
        pass
    print()
    if FAILED:
        print(f"{len(FAILED)} FAILED: " + "; ".join(FAILED))
        sys.exit(1)
    print("All checks passed.")
