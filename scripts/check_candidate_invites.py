"""Checks the candidate invites (HR side) and the public candidate form, end to end through the real API.

    cd backend
    .venv/bin/python scripts/check_candidate_invites.py

Runs inside one transaction that is rolled back at the end (uploaded files are removed again). No mail is sent: the two mail functions are replaced with
ones that keep what would have been sent. Exits with status 1 if any check fails.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

import datetime
import json
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.utils import timezone
from rest_framework.test import APIClient

from hr import onboarding as ob
from hr.models import CandidateExperienceDtl, CandidateInterviewHdr, CandidateInvite, CandidateTrainingDtl

HR = "/api/hr/candidate-invites/"
PUB = "/api/public/onboarding/"
FAILED = []
_REAL_SUBMITTED = ob.send_submitted_mail  # the real one, kept before the checks replace it
SENT = []  # what the fake mailer was asked to send


def check(name, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


def fake_invite_mail(invite, link):
    SENT.append(("invite", invite.email_id, link))
    return True


def fake_submitted_mail(invite, hdr):
    SENT.append(("submitted", invite.email_id, hdr.pk))
    return True


def fake_code_mail(invite, code):
    SENT.append(("code", invite.email_id, code))
    return True


def run():
    admin = get_user_model().objects.filter(is_superuser=True).first()
    hr = APIClient(HTTP_HOST="localhost")
    hr.force_authenticate(admin)
    anon = APIClient(HTTP_HOST="localhost")
    cache.clear()

    def post(endpoint, **body):
        return anon.post(PUB + endpoint + "/", body, format="json")

    print("HR creates an invite")
    r = hr.post(HR, {"candidate_name": "Rule Check", "email_id": "bad"}, format="json")
    check("a bad email is refused", r.status_code == 400 and "email_id" in r.json())
    r = hr.post(HR, {"candidate_name": "", "email_id": "a@example.com"}, format="json")
    check("a missing name is refused", r.status_code == 400 and "candidate_name" in r.json())
    r = hr.post(HR, {"candidate_name": "Rule Check", "email_id": "rule.check@example.com", "expires_days": 99}, format="json")
    check("the days must be 1 to 30", r.status_code == 400)
    r = hr.post(HR, {"candidate_name": "Rule Check", "email_id": "rule.check@example.com"}, format="json")
    check("a valid invite is created, with the link shown once", r.status_code == 201 and r.json().get("link", "").startswith("http://localhost:5173/join/"), r.content[:200])
    body = r.json()
    check("the mail was asked for", SENT and SENT[-1][0] == "invite")
    check("status starts as sent", body["status"] == "sent")
    check("the response shows no token hash, code or draft", not ({"token_hash", "otp_hash", "draft"} & set(body)))
    token = body["link"].rsplit("/", 1)[1]
    pk = body["candidate_invite_id"]
    check("only a hash of the token is stored", CandidateInvite.objects.get(pk=pk).token_hash == ob.hash_token(token) and token not in CandidateInvite.objects.get(pk=pk).token_hash)

    print("Where the link points")
    with mock.patch.object(settings, "ONBOARDING_BASE_URL", ""):
        r = hr.post(HR, {"candidate_name": "Origin Check", "email_id": "origin.check@example.com"}, format="json", HTTP_ORIGIN="https://hr.example.org")
        check("the link uses the address HR is on (the request's Origin)", r.json()["link"].startswith("https://hr.example.org/join/"), r.content[:200])
        r = hr.post(HR, {"candidate_name": "Origin Check", "email_id": "origin.check@example.com"}, format="json", HTTP_ORIGIN="javascript:alert(1)")
        check("a strange Origin is ignored", r.json()["link"].startswith("http://localhost:5173/join/"), r.content[:200])
    with mock.patch.object(settings, "ONBOARDING_BASE_URL", "https://public.example.net/"):
        r = hr.post(HR, {"candidate_name": "Origin Check", "email_id": "origin.check@example.com"}, format="json", HTTP_ORIGIN="https://hr.example.org")
        check("the setting, when given, wins", r.json()["link"].startswith("https://public.example.net/join/"), r.content[:200])

    print("The link")
    bad = post("start", token="x" * 43)
    check("an unknown link and a made-up one answer the same", bad.status_code == 404 and bad.json() == post("start", token="short").json())
    r = post("start", token=token)
    check("the real link opens, showing only a masked address", r.status_code == 200 and r.json()["email_masked"] != "rule.check@example.com" and "@example.com" in r.json()["email_masked"])
    check("opened is recorded", CandidateInvite.objects.get(pk=pk).opened_dt is not None)
    check("the form calls need a session", post("load", token=token).status_code == 401)

    print("The code")
    r = post("verify", token=token, code="123456")
    check("verifying before asking for a code is refused", r.status_code == 400 and r.json()["error"] == "no_code")
    r = post("send-code", token=token)
    check("a code is sent to the invited address only", r.status_code == 200 and SENT[-1][:2] == ("code", "rule.check@example.com"))
    code = SENT[-1][2]
    check("the code is 6 digits", len(code) == 6 and code.isdigit())
    check("only a hash of the code is stored", code not in (CandidateInvite.objects.get(pk=pk).otp_hash or ""))
    wrong = "000000" if code != "000000" else "111111"
    r = post("verify", token=token, code=wrong)
    check("a wrong code is refused and counts the tries left", r.status_code == 400 and "4 tries" in r.json()["message"], r.content[:200])
    r = post("verify", token=token, code=code)
    check("the right code gives a form session", r.status_code == 200 and r.json().get("session"), r.content[:200])
    session = r.json()["session"]
    check("the code cannot be used twice", post("verify", token=token, code=code).status_code == 400)

    print("Resending the code, and the limits")
    for _ in range(2):
        post("send-code", token=token)
    r = post("send-code", token=token)
    check("a 4th code within an hour is refused", r.status_code == 429, r.content[:200])

    print("Locking after wrong codes")
    inv2 = hr.post(HR, {"candidate_name": "Lock Check", "email_id": "lock.check@example.com"}, format="json").json()
    t2 = inv2["link"].rsplit("/", 1)[1]
    post("send-code", token=t2)
    real2 = SENT[-1][2]
    last = None
    for _ in range(5):
        last = post("verify", token=t2, code="000000" if real2 != "000000" else "111111")
    check("the 5th wrong code locks the invite", last.status_code == 403 and last.json()["error"] == "locked")
    check("a locked invite cannot ask for or check codes", post("send-code", token=t2).status_code == 403 and post("verify", token=t2, code=real2).status_code == 403)
    check("HR sees it as locked", hr.get(f"{HR}{inv2['candidate_invite_id']}/").json()["status"] == "locked")
    r = hr.post(f"{HR}{inv2['candidate_invite_id']}/resend/")
    check("a resend unlocks it with a new link", r.status_code == 200 and r.json()["locked"] is False and r.json()["link"] != inv2["link"])
    check("the old link stops working", post("start", token=t2).status_code == 404)

    print("Sessions")
    r = post("load", token=token, session=session)
    check("the session loads the form", r.status_code == 200 and r.json()["email"] == "rule.check@example.com", r.content[:200])
    check("a tampered session is refused", post("load", token=token, session=session[:-3] + "xyz").status_code == 401)
    check("another invite's session is refused", post("load", token=t2, session=session).status_code == 404)
    old_cap = ob.SESSION_MAX_SECONDS
    ob.SESSION_MAX_SECONDS = -1
    check("a session older than 12 hours is refused", post("load", token=token, session=session).status_code == 401)
    ob.SESSION_MAX_SECONDS = old_cap

    print("Saving a draft")
    draft = {"fname": "Rule", "lname": "Check", "dob": "1990-05-05", "mobile": "9876543210", "evil": "<script>", "rank": 5, "rig": 3, "hiring_status": "S",
             "trainings": [{"type": "BOSIET", "agency": "OPITO", "cert_no": "B1", "cert_dt": "2024-01-01", "valid_from": "2024-01-01", "valid_to": "2028-01-01", "extra": "x"}]}
    r = post("save", token=token, session=session, version=0, draft=draft)
    check("a draft is saved", r.status_code == 200 and r.json()["version"] == 1, r.content[:200])
    stored = json.loads(CandidateInvite.objects.get(pk=pk).draft)
    check("unknown fields (evil, rank, rig, hiring_status) are dropped", not ({"evil", "rank", "rig", "hiring_status"} & set(stored)))
    check("the draft is not in the candidate tables", not CandidateInterviewHdr.objects.filter(email_id="rule.check@example.com").exists())
    r = post("save", token=token, session=session, version=0, draft=draft)
    check("saving from a stale copy is refused", r.status_code == 409)
    r = post("save", token=token, session=session, version=1, draft={"fname": "R" * 500})
    check("long values are cut to the column size", r.status_code == 200 and len(json.loads(CandidateInvite.objects.get(pk=pk).draft)["fname"]) == 20)
    big = {"trainings": [{"type": "x" * 50, "agency": "y" * 75, "cert_no": "z" * 25}] * 20, "present_addr": "a" * 100}
    check("many rows stay within the size cap", post("save", token=token, session=session, version=2, draft=big).status_code in (200, 413))
    r = hr.get(f"{HR}{pk}/")
    check("HR sees a draft in progress, without its content", r.json()["status"] == "draft" and "draft" not in r.json() and r.json()["progress"] is not None)

    print("The resume")
    saved = []
    try:
        r = anon.post(PUB + "resume/", {"token": token, "session": session, "file": SimpleUploadedFile("cv.pdf", b"MZ not a pdf")}, format="multipart")
        check("a renamed program is refused", r.status_code == 400)
        r = anon.post(PUB + "resume/", {"token": token, "session": session, "file": SimpleUploadedFile("cv.exe", b"MZ")}, format="multipart")
        check("an .exe is refused", r.status_code == 400)
        r = anon.post(PUB + "resume/", {"token": token, "session": session, "file": SimpleUploadedFile("cv.pdf", b"%PDF-1.4 ok")}, format="multipart")
        check("a PDF is accepted", r.status_code == 200 and r.json()["has_resume"], r.content[:200])
        path1 = CandidateInvite.objects.get(pk=pk).resume_path
        saved.append(os.path.join(settings.MEDIA_ROOT, path1))
        check("it is stored under candidate_resumes, named by the invite", path1.startswith("candidate_resumes/i%d_" % pk))
        anon.post(PUB + "resume/", {"token": token, "session": session, "file": SimpleUploadedFile("cv2.pdf", b"%PDF-1.4 two")}, format="multipart")
        path2 = CandidateInvite.objects.get(pk=pk).resume_path
        saved.append(os.path.join(settings.MEDIA_ROOT, path2))
        check("a replacement removes the earlier file", path1 != path2 and not os.path.exists(os.path.join(settings.MEDIA_ROOT, path1)))

        print("Submitting")
        full = {
            "fname": "Rule", "mname": "", "lname": "Check", "father": "Test Father", "dob": "1990-05-05", "nationality": "Indian", "mobile": "9876543210",
            "present_addr": "1 Test Road", "same_addr": True, "qualification": "Diploma", "tot_y": 10, "tot_m": 0, "cur_y": 3, "cur_m": 0, "source": "Friend",
            "recommendation": "Good",
            "trainings": [{"type": "BOSIET", "agency": "OPITO", "cert_no": "B1", "cert_dt": "2024-01-01", "valid_from": "2024-01-01", "valid_to": "2028-01-01"}],
            "experiences": [{"from": "2016-04-01", "to": "2018-11-30", "company": "Axom", "designation": "Driller"}],
            # things a candidate must not be able to set
            "rig": 1, "rank": 1, "hiring_status": "S", "suitable_for_role": "Y", "additional_notes": "hired",
        }
        r = post("submit", token=token, session=session, draft={**full, "dob": "2015-01-01"})
        check("a child's date of birth is refused, naming the field", r.status_code == 400 and "dob" in r.json().get("fields", {}), r.content[:300])
        r = post("submit", token=token, session=session, draft={**full, "fname": ""})
        check("a missing required answer is named", r.status_code == 400 and "fname" in r.json()["fields"])
        r = post("submit", token=token, session=session, draft={**full, "cur_y": 11})
        check("current experience above total is refused", r.status_code == 400 and r.json()["fields"], r.content[:300])
        r = post("submit", token=token, session=session, draft={**full, "trainings": [{**full["trainings"][0], "valid_to": "2020-01-01"}]})
        check("a bad training row is named by its number", r.status_code == 400 and "0" in r.json().get("trainings", {}), r.content[:300])
        check("a refused submit leaves no candidate behind", not CandidateInterviewHdr.objects.filter(email_id="rule.check@example.com").exists())
        n_before = len([m for m in SENT if m[0] == "submitted"])
        check("no confirmation was mailed for the refused submits", n_before == 0)
        r = post("submit", token=token, session=session, draft=full)
        check("a complete form is submitted", r.status_code == 200 and r.json().get("submitted"), r.content[:300])
        check("a confirmation is mailed to the invited address, once", [m[:2] for m in SENT if m[0] == "submitted"] == [("submitted", "rule.check@example.com")])
        check("the answer tells the page the confirmation went", r.json().get("confirmation_sent") is True)
        hdr = CandidateInterviewHdr.objects.filter(email_id="rule.check@example.com").first()
        check("the candidate row exists", hdr is not None)
        if hdr:
            check("the email is the invited one", hdr.email_id == "rule.check@example.com")
            check("permanent address copied from present", hdr.permanent_addr == "1 Test Road")
            check("it is marked as entered by the candidate (New for 24 hours)", hdr.candidate_submitted_dt is not None)
            check("HR-only columns were not accepted", hdr.rig_id is None and hdr.rank_id is None and hdr.hiring_status == "N" and hdr.suitable_for_role is None and not hdr.additional_notes)
            check("the resume is attached", hdr.candidate_cert_path == path2)
            check("training and experience rows were created", CandidateTrainingDtl.objects.filter(hdr=hdr).count() == 1 and CandidateExperienceDtl.objects.filter(hdr=hdr).count() == 1)
            exp = CandidateExperienceDtl.objects.get(hdr=hdr)
            check("the earlier job's duration is worked out", (exp.exp_years, exp.exp_months) == (2, 7))
            check("the HR list shows it as New", hr.get(f"/api/hr/candidate-interviews/{hdr.pk}/").json()["is_new_from_candidate"] is True)
        inv = CandidateInvite.objects.get(pk=pk)
        check("the invite is submitted, linked, and its draft cleared", inv.submitted_dt and inv.hdr_id == (hdr.pk if hdr else None) and inv.draft == "")
        check("HR sees it as submitted", hr.get(f"{HR}{pk}/").json()["status"] == "submitted")
        check("the link cannot be used again", post("start", token=token).status_code == 404 and post("submit", token=token, session=session, draft=full).status_code == 404)
        check("the session no longer works", post("load", token=token, session=session).status_code == 404)
    finally:
        for p in saved:
            if os.path.isfile(p):
                os.remove(p)

    print("The confirmation mail itself (the mail program replaced)")
    from hr.models import CandidateInvite as _Inv
    real = {}
    with mock.patch("hr.onboarding.send_submitted_mail", ob.send_submitted_mail.__wrapped__ if hasattr(ob.send_submitted_mail, "__wrapped__") else _REAL_SUBMITTED), \
         mock.patch("core.mailer._deliver", lambda subject, html, text, to, cc, bcc, *a, **k: real.update(subject=subject, to=to, html=html)):
        probe = _Inv.objects.get(pk=pk)
        ok = ob.send_submitted_mail(probe, probe.hdr)
    check("it is built and sent without error, to the invited address", ok and real.get("to") == ["rule.check@example.com"], str(real.get("to")))
    check("it gives no internal reference number", "CI-" not in real.get("html", "") and "Reference" not in real.get("html", ""))

    print("HR actions")
    inv3 = hr.post(HR, {"candidate_name": "Act Check", "email_id": "act.check@example.com"}, format="json").json()
    t3 = inv3["link"].rsplit("/", 1)[1]
    before = CandidateInvite.objects.get(pk=inv3["candidate_invite_id"]).expires_dt
    r = hr.post(f"{HR}{inv3['candidate_invite_id']}/extend/", {"days": 3}, format="json")
    check("extend moves the date on", r.status_code == 200 and CandidateInvite.objects.get(pk=inv3["candidate_invite_id"]).expires_dt > before)
    r = hr.post(f"{HR}{inv3['candidate_invite_id']}/extend/", {"days": 60}, format="json")
    check("extend by more than 30 days is refused", r.status_code == 400)
    CandidateInvite.objects.filter(pk=inv3["candidate_invite_id"]).update(expires_dt=timezone.now() - datetime.timedelta(minutes=1))
    check("an expired link is refused like any other", post("start", token=t3).status_code == 404)
    check("HR sees it as expired", hr.get(f"{HR}{inv3['candidate_invite_id']}/").json()["status"] == "expired")
    r = hr.post(f"{HR}{inv3['candidate_invite_id']}/extend/", {"days": 2}, format="json")
    check("extending an expired invite reopens it", post("start", token=t3).status_code == 200 and r.status_code == 200)
    r = hr.post(f"{HR}{inv3['candidate_invite_id']}/cancel/")
    check("cancel works", r.status_code == 200 and r.json()["status"] == "cancelled")
    check("a cancelled link is refused", post("start", token=t3).status_code == 404)
    check("a submitted invite cannot be cancelled or resent", hr.post(f"{HR}{pk}/cancel/").status_code == 400 and hr.post(f"{HR}{pk}/resend/").status_code == 400)
    lst = hr.get(HR, {"status": "submitted"}).json()
    check("the list can be filtered by status", any(x["candidate_invite_id"] == pk for x in lst["results"]) and all(x["status"] == "submitted" for x in lst["results"]))

    print("Rights")
    check("HR calls need a sign-in", anon.get(HR).status_code in (401, 403) and anon.post(HR, {}, format="json").status_code in (401, 403))
    check("the public form cannot reach HR data", anon.get("/api/hr/candidate-interviews/").status_code in (401, 403))


if __name__ == "__main__":
    with mock.patch("hr.onboarding.send_invite_mail", fake_invite_mail), mock.patch("hr.onboarding.send_code_mail", fake_code_mail), mock.patch("hr.onboarding.send_submitted_mail", fake_submitted_mail):
        with transaction.atomic():
            run()
            transaction.set_rollback(True)
    print()
    if FAILED:
        print(f"{len(FAILED)} FAILED: " + "; ".join(FAILED))
        sys.exit(1)
    print("All checks passed.")
