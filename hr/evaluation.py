"""Candidate Competencies Details: the interviewers' ratings of a candidate, and the printed "Rig Candidate Interview Evaluation Form".

Rules (from the legacy page and its stored procedure Prc_Candidate_Interview_Competency):
  * A department takes part when it has active competencies in the Competency master (the legacy page hardcoded HSE 35, Technical 14 and HR 3; those are
    the only three that have any today, so the screen is the same, and a department added to the master appears by itself). Panels run in department
    id order, highest first (HSE, Technical, HR), which is the legacy screen and Excel order.
  * Only a user who is an ACTIVE interviewer of a department (Masters > Interviewer Mapping) may rate it; every other panel is read only.
  * A department's ratings are saved together: every competency of it needs a rating of 1 to 3 (remarks up to 75 characters). A department that has no
    ratings yet and none typed is simply left out. On an update only rating and remarks change: the interviewer of a saved row never changes.
  * Scores: a department's is the sum of its ratings out of 3 times its competencies (3/9); the overall is the sum of all rated departments (A+B+C) out of
    3 times their competencies (14/33); the status is the candidate's hiring status. A department with no rating yet has no score.
"""

import os
from io import BytesIO

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.models import MstCompetency, MstInterviewer
from hr.models import CandidateInterviewCompetency

MAX_RATING = 3
REMARK_LENGTH = 75
HIRING_STATUS = {"N": "New", "R": "Rejected", "S": "Selected", "O": "On Hold"}
# Panel captions the legacy page used; any other department shows its own name.
TITLES = {35: "HSE", 14: "Technical", 3: "HR"}


class RatingError(Exception):
    """A refused save. `errors` is {department id: message}; `status` the HTTP status."""

    def __init__(self, errors, status=400):
        super().__init__(errors)
        self.errors, self.status = errors, status


def department_ids():
    """Departments with at least one active competency, highest id first."""
    ids = MstCompetency.objects.filter(active="Y").values_list("department_id", flat=True).distinct()
    return sorted(set(ids), reverse=True)


def interviewer_ids_of(user_id):
    """{department id: interviewer id} for the active interviewer rows of a user (the first one when a department has several)."""
    out = {}
    if user_id is None:
        return out
    for row in MstInterviewer.objects.filter(user_id=user_id, active="Y").order_by("interviewer_id"):
        out.setdefault(row.department_id, row.interviewer_id)
    return out


def _title(dept):
    return TITLES.get(dept.pk) or dept.dept_dispname


def build_sheet(hdr, user_id):
    """Everything the page and the printout need for one candidate."""
    mine = interviewer_ids_of(user_id)
    rated = {}
    for r in CandidateInterviewCompetency.objects.filter(hdr=hdr).select_related("competency", "department", "interviewer", "interviewer__user"):
        rated.setdefault(r.department_id, {})[r.competency_id] = r
    panels, sum_all, max_all = [], 0, 0
    from core.models import MstDepartment

    depts = {d.pk: d for d in MstDepartment.objects.filter(pk__in=department_ids())}
    for dept_id in department_ids():
        dept = depts[dept_id]
        comps = list(MstCompetency.objects.filter(department_id=dept_id, active="Y").order_by("competency_id"))
        existing = rated.get(dept_id, {})
        rows = [{"competency": c.pk, "name": c.competency_name.strip(), "rating": existing[c.pk].rating if c.pk in existing else None,
                 "remarks": (existing[c.pk].remarks or "") if c.pk in existing else ""} for c in comps]
        # a rating saved for a competency that is inactive now still belongs on the sheet
        active_ids = {c.pk for c in comps}
        for cid, r in sorted(existing.items()):
            if cid not in active_ids:
                rows.append({"competency": cid, "name": r.competency.competency_name.strip(), "rating": r.rating, "remarks": r.remarks or ""})
        given = [x["rating"] for x in rows if x["rating"] is not None]
        score = sum(given) if given else None
        top = MAX_RATING * len(rows)
        who = next((r.interviewer for r in existing.values()), None)
        panels.append({
            "dept": dept_id, "title": _title(dept), "can_edit": dept_id in mine, "rows": rows, "score": score, "max": top,
            "interviewer": (who.user.user_name or who.user.user_login_id).strip() if who else "",
            "interviewer_id": who.pk if who else None,
            "sign_path": who.sign_path if who and who.sign_path else "",
        })
        if given:
            sum_all += score
            max_all += top
    return {
        "candidate": candidate_card(hdr),
        "panels": panels,
        "overall": {"score": sum_all if max_all else None, "max": max_all, "status": HIRING_STATUS.get(hdr.hiring_status, "")},
        "can_rate": bool(mine) and any(p["can_edit"] for p in panels),
    }


def rating_summary(hdr_ids):
    """For the list: {candidate id: {"panels": [{dept, title, rated}], "score": n or None, "max": n}} for these candidates, in a few queries (the same
    scores as the sheet: a department counts once any of its rows is rated, out of 3 times its competencies)."""
    from core.models import MstDepartment

    ids = department_ids()
    depts = {d.pk: d for d in MstDepartment.objects.filter(pk__in=ids)}
    active = {}
    active_ids = {}
    for c in MstCompetency.objects.filter(active="Y", department_id__in=ids):
        active.setdefault(c.department_id, 0)
        active[c.department_id] += 1
        active_ids.setdefault(c.department_id, set()).add(c.pk)
    got = {}
    for hdr_id, dept_id, comp_id, rating in CandidateInterviewCompetency.objects.filter(hdr_id__in=hdr_ids).values_list("hdr_id", "department_id", "competency_id", "rating"):
        slot = got.setdefault(hdr_id, {}).setdefault(dept_id, {"sum": 0, "rows": 0, "extra": 0})
        slot["sum"] += rating
        slot["rows"] += 1
        if comp_id not in active_ids.get(dept_id, ()):
            slot["extra"] += 1  # a rating on a competency that is inactive now still counts
    out = {}
    for hdr_id in hdr_ids:
        mine = got.get(hdr_id, {})
        panels, score, top = [], 0, 0
        for dept_id in ids:
            slot = mine.get(dept_id)
            panels.append({"dept": dept_id, "title": _title(depts[dept_id]), "rated": bool(slot)})
            if slot:
                score += slot["sum"]
                top += MAX_RATING * (active.get(dept_id, 0) + slot["extra"])
        out[hdr_id] = {"panels": panels, "score": score if top else None, "max": top}
    return out


def candidate_card(hdr):
    return {
        "id": hdr.pk, "full_name": str(hdr), "mobile_no": hdr.mobile_no, "email_id": hdr.email_id, "rank_name": hdr.rank.rank_name if hdr.rank_id else "",
        "rig_name": hdr.rig.rig_name if hdr.rig_id else "", "interview_dt": hdr.interview_dt, "edu_qualification": hdr.edu_qualification or "",
        "tot_experience_yrs": hdr.tot_experience_yrs, "tot_experience_mths": hdr.tot_experience_mths,
        "exp_in_curr_pos_yrs": hdr.exp_in_curr_pos_yrs, "exp_in_curr_pos_mths": hdr.exp_in_curr_pos_mths,
        "recruitment_source": hdr.recruitment_source or "", "hiring_reccomendation": hdr.hiring_reccomendation or "", "additional_notes": hdr.additional_notes or "",
    }


def save_ratings(hdr, user_id, panels):
    """Saves what an interviewer sent. `panels` is [{"dept": id, "rows": [{"competency": id, "rating": n, "remarks": text}]}].
    Returns {competency id: (old rating, old remarks, new rating, new remarks)} for the rows that changed (for the audit log). Raises RatingError."""
    mine = interviewer_ids_of(user_id)
    if not mine:
        raise RatingError({"": "You are not set up as an interviewer, so you cannot rate candidates."}, status=403)
    known = set(department_ids())
    errors, plan = {}, []
    for panel in panels if isinstance(panels, list) else []:
        try:
            dept_id = int(panel.get("dept"))
        except (TypeError, ValueError, AttributeError):
            errors[""] = "A department is missing."
            continue
        if dept_id not in known:
            errors[dept_id] = "This department has no competencies to rate."
            continue
        if dept_id not in mine:
            errors[dept_id] = "You are not an interviewer of this department."
            continue
        wanted = {c.pk: c for c in MstCompetency.objects.filter(department_id=dept_id, active="Y")}
        sent = {}
        for row in panel.get("rows") or []:
            try:
                cid = int(row.get("competency"))
            except (TypeError, ValueError, AttributeError):
                continue
            if cid in wanted:
                sent[cid] = row
        existing = {r.competency_id: r for r in CandidateInterviewCompetency.objects.filter(hdr=hdr, department_id=dept_id)}
        typed = [r for r in sent.values() if r.get("rating") not in (None, "")]
        if not typed and not existing:
            continue  # nothing rated here and nothing saved before: left out
        bad = False
        for cid, comp in wanted.items():
            row = sent.get(cid)
            rating = row.get("rating") if row else None
            if rating in (None, ""):
                if cid in existing and not row:
                    continue  # an untouched saved row stays as it is
                errors[dept_id] = "Ratings cannot be blanks."
                bad = True
                break
            try:
                value = int(rating)
            except (TypeError, ValueError):
                value = 0
            if not 1 <= value <= MAX_RATING:
                errors[dept_id] = f"Rating must be between 1 and {MAX_RATING}."
                bad = True
                break
            remarks = str((row or {}).get("remarks") or "").strip()
            if len(remarks) > REMARK_LENGTH:
                errors[dept_id] = f"A remark can be {REMARK_LENGTH} characters at most."
                bad = True
                break
            plan.append((dept_id, comp, value, remarks or None, existing.get(cid)))
        if bad:
            continue
    if errors:
        raise RatingError(errors)
    changed = {}
    now = timezone.now()
    with transaction.atomic():
        for dept_id, comp, value, remarks, row in plan:
            if row is None:
                CandidateInterviewCompetency.objects.create(
                    hdr=hdr, department_id=dept_id, interviewer_id=mine[dept_id], competency=comp, rating=value, remarks=remarks, cr_user_id=user_id, cr_dt=now,
                )
                changed[comp.pk] = (None, None, value, remarks)
            elif row.rating != value or (row.remarks or None) != remarks:
                changed[comp.pk] = (row.rating, row.remarks, value, remarks)
                row.rating, row.remarks, row.mod_user_id, row.mod_dt = value, remarks, user_id, now  # the interviewer of a saved row is kept
                row.save(update_fields=["rating", "remarks", "mod_user_id", "mod_dt"])
    return changed


# ── Excel printout ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def _score(score, top):
    return f"{score}/{top}" if score is not None else ""


def _months(yrs, mths):
    return f"{yrs or 0} Yrs {mths or 0} Mnths" if (yrs is not None or mths is not None) else ""


def build_workbook(hdr, user_id):
    """The Rig Candidate Interview Evaluation Form as an .xlsx (bytes), laid out like the legacy printout."""
    from openpyxl import Workbook
    from openpyxl.drawing.image import Image as XlImage
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    sheet = build_sheet(hdr, user_id)
    c = sheet["candidate"]
    wb = Workbook()
    ws = wb.active
    ws.title = "Evaluation"
    for col, w in zip("ABCDEFGH", (10, 25, 10, 30, 10, 25, 10, 30)):
        ws.column_dimensions[col].width = w
    thin = Side(style="thin")
    box = Border(left=thin, right=thin, top=thin, bottom=thin)
    blue = PatternFill("solid", fgColor="ADD8E6")
    top_left = Alignment(vertical="top", horizontal="left", wrap_text=True)
    center = Alignment(vertical="top", horizontal="center", wrap_text=True)

    def put(ref, value, bold=False, fill=None, align=None, span=None):
        if span:
            ws.merge_cells(f"{ref}:{span}")
        cell = ws[ref]
        cell.value = value
        cell.font = Font(name="Calibri", size=11, bold=bold)
        cell.alignment = align or (center if bold else top_left)
        if fill:
            cell.fill = fill
        # the box goes on every cell of a merged range
        first, last = (ref, span or ref)
        for row in ws[f"{first}:{last}"]:
            for cc in row:
                cc.border = box
                if fill:
                    cc.fill = fill

    logo = None
    for path in (os.path.join(os.path.dirname(settings.BASE_DIR), "frontend", "public", "branding", "seros-logo.png"),
                 os.path.join(settings.BASE_DIR, "core", "banner_logos", "seros-logo.png")):
        if os.path.isfile(path):
            logo = path
            break
    if logo:
        img = XlImage(logo)
        img.width, img.height = 150, 43
        ws.add_image(img, "H1")
    ws.row_dimensions[1].height = 18

    ws.merge_cells("A3:H3")
    ws["A3"] = "Rig Candidate Interview Evaluation Form"
    ws["A3"].font = Font(name="Calibri", size=20, bold=True)
    ws["A3"].alignment = Alignment(horizontal="center", vertical="top")
    dmy = c["interview_dt"].strftime("%d/%m/%Y") if c["interview_dt"] else ""
    put("A4", "Rig / Location", True); put("B4", c["rig_name"], span="C4")
    put("D4", "Interview Date", True); put("E4", dmy)
    put("F4", "Hiring Recommendation", True); put("G4", c["hiring_reccomendation"], span="H4")
    put("A5", "Candidate Name", True); put("B5", c["full_name"], span="C5")
    put("D5", "Position Applied For", True); put("E5", c["rank_name"])
    put("F5", "Source of Recruitment", True); put("G5", c["recruitment_source"], span="H5")
    put("A6", "Education Qualification", True); put("B6", c["edu_qualification"], span="C6")
    put("D6", "Total Experience", True); put("E6", _months(c["tot_experience_yrs"], c["tot_experience_mths"]))
    put("F6", "Experience in current position", True); put("G6", _months(c["exp_in_curr_pos_yrs"], c["exp_in_curr_pos_mths"]), span="H6")

    panels = sheet["panels"]
    letters = [chr(ord("A") + i) for i in range(len(panels))]
    blocks = [("dept", p, letters[i]) for i, p in enumerate(panels)] + [("overall", sheet["overall"], "")]
    row = 7
    for i in range(0, len(blocks), 2):
        pair = blocks[i:i + 2]
        heights = []
        for side, (kind, data, letter) in zip(("A", "E"), pair):
            first = side
            cols = ["A", "B", "C", "D"] if side == "A" else ["E", "F", "G", "H"]
            if kind == "dept":
                put(f"{cols[0]}{row}", f"{data['title']} Competencies:", True, blue, span=f"{cols[3]}{row}")
                for col, label in zip(cols, ("Sl No", "Competency", "Rating(1 to 3)", "Remark")):
                    put(f"{col}{row + 1}", label, True)
                r = row + 2
                for n, item in enumerate(data["rows"], 1):
                    put(f"{cols[0]}{r}", n, align=center)
                    put(f"{cols[1]}{r}", item["name"])
                    put(f"{cols[2]}{r}", item["rating"], align=center)
                    put(f"{cols[3]}{r}", item["remarks"])
                    r += 1
                put(f"{cols[0]}{r}", letter, True)
                put(f"{cols[1]}{r}", "Total Score:", True, align=top_left)
                put(f"{cols[2]}{r}", _score(data["score"], data["max"]), True)
                put(f"{cols[3]}{r}", "")
                heights.append(r - row + 1)
            else:
                put(f"{cols[0]}{row}", "Overall Competencies:", True, blue, span=f"{cols[3]}{row}")
                total_label = "Total Score(" + "+".join(letters) + ")"
                for col, label in zip(cols, ("Sl No", "Competency", total_label, "Remark")):
                    put(f"{col}{row + 1}", label, True)
                put(f"{cols[0]}{row + 2}", "1", True); put(f"{cols[1]}{row + 2}", "Overall Performance:", True)
                put(f"{cols[2]}{row + 2}", _score(data["score"], data["max"]), True); put(f"{cols[3]}{row + 2}", "")
                put(f"{cols[0]}{row + 3}", ""); put(f"{cols[1]}{row + 3}", "Status", True)
                put(f"{cols[2]}{row + 3}", data["status"], True); put(f"{cols[3]}{row + 3}", "")
                heights.append(4)
        row += max(heights)
    put(f"A{row}", f"Additional Notes : {c['additional_notes']}".strip(), True, align=top_left, span=f"H{row}")
    ws.row_dimensions[row].height = 40
    row += 1

    # interviewers: three departments to a block, each over two columns (C:D, E:F, G:H), highest department id first
    sign_rows = []
    for start in range(0, len(panels), 3):
        group = panels[start:start + 3]
        r_name, r_dept, r_sign = row, row + 1, row + 2
        put(f"A{r_name}", "Interviewer Names", True, span=f"B{r_name}")
        put(f"A{r_dept}", "Department", True, span=f"B{r_dept}")
        put(f"A{r_sign}", "Interviewer Signature", True, span=f"B{r_sign}")
        ws.row_dimensions[r_sign].height = 48
        for (left, right), p in zip((("C", "D"), ("E", "F"), ("G", "H")), group):
            put(f"{left}{r_name}", p["interviewer"], align=center, span=f"{right}{r_name}")
            put(f"{left}{r_dept}", p["title"] if p["dept"] not in TITLES else {35: "Health Safety Environment", 14: "Technical Services", 3: "Human Resource"}[p["dept"]],
                align=center, span=f"{right}{r_dept}")
            put(f"{left}{r_sign}", "", align=center, span=f"{right}{r_sign}")
            sign = os.path.join(settings.MEDIA_ROOT, p["sign_path"]) if p["sign_path"] else ""
            if sign and os.path.isfile(sign):
                try:
                    pic = XlImage(sign)
                    ratio = min(150 / pic.width, 55 / pic.height)
                    pic.width, pic.height = int(pic.width * ratio), int(pic.height * ratio)
                    ws.add_image(pic, f"{left}{r_sign}")
                except Exception:  # an unreadable signature file leaves the box empty
                    pass
        row += 3
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    from openpyxl.worksheet.properties import PageSetupProperties

    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    out = BytesIO()
    wb.save(out)
    return out.getvalue()
