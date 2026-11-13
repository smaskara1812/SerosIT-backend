"""Checks Candidate Competencies Details (interview ratings and the Excel evaluation form) through the real API.

    cd backend
    .venv/bin/python scripts/check_candidate_evaluations.py

Runs inside one transaction that is rolled back at the end, so nothing is saved. Needs the normal dev data (the migrated candidates and ratings).
Exits with status 1 if any check fails.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

import datetime
from io import BytesIO

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import MstCompetency, MstInterviewer, MstUser, UserProfile
from hr.models import CandidateInterviewCompetency

URL = "/api/hr/candidate-evaluations/"
FAILED = []


def check(name, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


def run():
    User = get_user_model()
    admin = User.objects.filter(is_superuser=True).first()
    unmapped = APIClient(HTTP_HOST="localhost")
    unmapped.force_authenticate(admin)

    print("The candidate list (picker)")
    r = unmapped.get(URL, {"search": "Jagdish"})
    row = r.json()["results"][0] if r.status_code == 200 and r.json().get("results") else {}
    check("search finds the candidate", row.get("full_name", "").startswith("Jagdish"), r.content[:200])
    check("only list fields are returned (no contact details)", set(row) == {"candidate_interview_hdr_id", "full_name", "rank_name", "rig_name", "interview_dt", "hiring_status",
                                                                              "hiring_status_label", "panels", "score", "max"}, str(sorted(row)))
    check("the list shows which departments have rated and the overall score", [p["rated"] for p in row["panels"]] == [True, True, True] and (row["score"], row["max"]) == (14, 33), str(row))
    full = unmapped.get(URL, {"ratings": "full"}).json()
    none_ = unmapped.get(URL, {"ratings": "none"}).json()
    partly = unmapped.get(URL, {"ratings": "partly"}).json()
    check("the rating filters split the candidates (fully, partly, not rated)", full["count"] + partly["count"] + none_["count"] == unmapped.get(URL).json()["count"] and full["count"] > 0 and partly["count"] > 0)
    check("a fully rated candidate has every department rated", all(all(p["rated"] for p in r_["panels"]) for r_ in full["results"]))

    print("One candidate's sheet (the sample: Jagdish Chandra Pandey)")
    pk = row["candidate_interview_hdr_id"]
    sheet = unmapped.get(f"{URL}{pk}/").json()
    check("departments come from the competency master, highest id first (HSE, Technical, HR)", [p["dept"] for p in sheet["panels"]] == [35, 14, 3], str([p["dept"] for p in sheet["panels"]]))
    check("scores match the printed form: 3/9, 6/15, 5/9", [(p["score"], p["max"]) for p in sheet["panels"]] == [(3, 9), (6, 15), (5, 9)])
    check("overall is 14/33 and the status is New", (sheet["overall"]["score"], sheet["overall"]["max"], sheet["overall"]["status"]) == (14, 33, "New"))
    check("a person who is no interviewer sees every panel read only", not sheet["can_rate"] and not any(p["can_edit"] for p in sheet["panels"]))
    r = unmapped.post(f"{URL}{pk}/ratings/", {"panels": [{"dept": 35, "rows": []}]}, format="json")
    check("and cannot save ratings", r.status_code == 403, r.content[:200])

    # a candidate with ratings from technical only, and a user who is the HSE interviewer
    target = 10
    base = unmapped.get(f"{URL}{target}/").json()
    check("a partly rated candidate shows the unrated panels with no score", [p["score"] for p in base["panels"] if p["dept"] in (35, 3)] == [None, None])
    now = timezone.now()
    login = "zz_eval_check"
    mst = MstUser.objects.create(user_name="zz eval check", user_login_id=login, user_active="Y", user_type_id="N", user_from=datetime.date(2020, 1, 1), cr_user_id=1, cr_dt=now)
    UserProfile.objects.create(user_id=mst.user_id, user_login_id=login, is_app_admin=True)
    interviewer = MstInterviewer.objects.create(user=mst, department_id=35, active="Y", cr_user_id=1, cr_dt=now)
    django_user = User.objects.create_user(username=login, password="x")
    hse = APIClient(HTTP_HOST="localhost")
    hse.force_authenticate(django_user)
    comps = list(MstCompetency.objects.filter(department_id=35, active="Y").order_by("competency_id"))
    mine = hse.get(f"{URL}{target}/").json()
    check("the HSE interviewer can edit only the HSE panel", {p["dept"]: p["can_edit"] for p in mine["panels"]} == {35: True, 14: False, 3: False})

    def rows(*ratings, remarks=""):
        return [{"competency": c.pk, "rating": v, "remarks": remarks} for c, v in zip(comps, ratings)]

    def save(*panels):
        return hse.post(f"{URL}{target}/ratings/", {"panels": list(panels)}, format="json")

    print("Rules when saving")
    r = save({"dept": 35, "rows": rows(2, None, 3)})
    check("a blank rating in a department being rated is refused", r.status_code == 400 and "blanks" in r.json()["errors"]["35"], r.content[:200])
    r = save({"dept": 35, "rows": rows(2, 4, 3)})
    check("a rating above 3 is refused", r.status_code == 400 and "between 1 and 3" in r.json()["errors"]["35"])
    r = save({"dept": 35, "rows": rows(0, 1, 1)})
    check("a rating of 0 is refused", r.status_code == 400)
    r = save({"dept": 35, "rows": rows(1, 1, 1, remarks="x" * 76)})
    check("a remark over 75 characters is refused", r.status_code == 400 and "75" in r.json()["errors"]["35"])
    r = save({"dept": 14, "rows": [{"competency": 4, "rating": 3, "remarks": ""}]})
    check("rating a department you are not an interviewer of is refused", r.status_code == 400 and "not an interviewer" in r.json()["errors"]["14"], r.content[:200])
    r = save({"dept": 99, "rows": []})
    check("a department with no competencies is refused", r.status_code == 400)
    check("nothing was saved by the refused requests", not CandidateInterviewCompetency.objects.filter(hdr_id=target, department_id=35).exists())
    r = save({"dept": 35, "rows": []})
    check("a department with nothing rated and nothing saved is just left out", r.status_code == 200 and not CandidateInterviewCompetency.objects.filter(hdr_id=target, department_id=35).exists())

    print("Saving and updating")
    r = save({"dept": 35, "rows": rows(2, 3, 1, remarks="ok")})
    check("a full department is saved", r.status_code == 200, r.content[:300])
    new = r.json()
    hse_panel = next(p for p in new["panels"] if p["dept"] == 35)
    check("with its score 6/9 and the interviewer's name", (hse_panel["score"], hse_panel["max"]) == (6, 9) and hse_panel["interviewer"] == "zz eval check", str(hse_panel))
    check("the overall now counts it with the technical ratings", new["overall"]["max"] == 9 + base["panels"][1]["max"] and new["overall"]["score"] == 6 + base["panels"][1]["score"], str(new["overall"]))
    saved = CandidateInterviewCompetency.objects.filter(hdr_id=target, department_id=35)
    check("the rows carry the interviewer and creator", saved.count() == 3 and all(x.interviewer_id == interviewer.pk and x.cr_user_id == mst.user_id for x in saved))
    r = save({"dept": 35, "rows": rows(3, 3, 1, remarks="ok")})
    check("an update changes the rating", r.status_code == 200 and sorted(x.rating for x in CandidateInterviewCompetency.objects.filter(hdr_id=target, department_id=35)) == [1, 3, 3])
    # a second HSE interviewer changes a rating: the saved row keeps the first interviewer
    login2 = "zz_eval_check2"
    mst2 = MstUser.objects.create(user_name="zz eval two", user_login_id=login2, user_active="Y", user_type_id="N", user_from=datetime.date(2020, 1, 1), cr_user_id=1, cr_dt=now)
    UserProfile.objects.create(user_id=mst2.user_id, user_login_id=login2, is_app_admin=True)
    MstInterviewer.objects.create(user=mst2, department_id=35, active="Y", cr_user_id=1, cr_dt=now)
    second = APIClient(HTTP_HOST="localhost")
    second.force_authenticate(User.objects.create_user(username=login2, password="x"))
    r = second.post(f"{URL}{target}/ratings/", {"panels": [{"dept": 35, "rows": rows(2, 3, 1, remarks="second")}]}, format="json")
    changed_rows = CandidateInterviewCompetency.objects.filter(hdr_id=target, department_id=35)
    check("an update by another interviewer keeps the first interviewer and records who changed it",
          r.status_code == 200 and all(x.interviewer_id == interviewer.pk for x in changed_rows) and all(x.mod_user_id == mst2.user_id for x in changed_rows), r.content[:200])
    before = CandidateInterviewCompetency.objects.filter(hdr_id=target, department_id=35, mod_dt__isnull=False).count()
    save({"dept": 35, "rows": rows(3, 3, 1, remarks="ok")})
    check("saving the same values again changes nothing", CandidateInterviewCompetency.objects.filter(hdr_id=target, department_id=35, mod_dt__isnull=False).count() == before)

    print("The database rule and the Excel form")
    with transaction.atomic():
        try:
            with connection.cursor() as cur:
                cur.execute("UPDATE hr_candidate_interview_competency SET rating = 4 WHERE candidate_interview_comp_id = %s", [saved[0].pk])
            check("the database refuses a rating of 4", False)
        except Exception:
            check("the database refuses a rating of 4", True)
            transaction.set_rollback(False)
    r = unmapped.get(f"{URL}{pk}/evaluation-form/")
    check("the evaluation form is an Excel file", r.status_code == 200 and "spreadsheetml" in r["Content-Type"] and r.content[:2] == b"PK", str(r.status_code))
    import openpyxl

    ws = openpyxl.load_workbook(BytesIO(r.content)).active
    cells = {c.coordinate: c.value for row_ in ws.iter_rows() for c in row_ if c.value not in (None, "")}
    check("it has the title, the candidate and the totals", cells.get("A3") == "Rig Candidate Interview Evaluation Form" and cells.get("B5", "").startswith("Jagdish")
          and cells.get("C12") == "3/9" and cells.get("G14") == "6/15" and cells.get("C20") == "5/9" and cells.get("G17") == "14/33" and cells.get("G18") == "New")
    check("it names the interviewers and departments", cells.get("C22") == "Amit  Katiyar" and cells.get("E22") == "Dany Francis John" and cells.get("G23") == "Human Resource")
    check("it carries the logo and the signatures that exist", len(ws._images) >= 3)

    print("Rights")
    anon = APIClient(HTTP_HOST="localhost")
    check("signed-out requests are refused", anon.get(URL).status_code in (401, 403) and anon.get(f"{URL}{pk}/").status_code in (401, 403))
    check("the list cannot be used to change anything", unmapped.delete(f"{URL}{pk}/").status_code == 405 and unmapped.patch(f"{URL}{pk}/", {}, format="json").status_code == 405)


if __name__ == "__main__":
    with transaction.atomic():
        run()
        transaction.set_rollback(True)
    print()
    if FAILED:
        print(f"{len(FAILED)} FAILED: " + "; ".join(FAILED))
        sys.exit(1)
    print("All checks passed.")
