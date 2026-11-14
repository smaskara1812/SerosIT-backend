"""Checks Print Offer Letter (the approved letters as PDF) through the real API, and the letter text rules of hr/offer_letter_pdf.py.

    cd backend
    .venv/bin/python scripts/check_offer_letter_print.py

Runs inside one transaction that is rolled back at the end, so nothing is saved. The PDF text checks need `pdftotext` (poppler); they are skipped when it is missing.
Exits with status 1 if any check fails.
"""

import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

import datetime

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import MstUser, MstUserFsCatgMapping, UserPermission, UserProfile
from core.permissions import invalidate_user_access
from hr import offer_letter_pdf as op
from hr.models import FsNewApplDtl, FsOfferLetter, FsOfferLetterComponent

URL = "/api/hr/fs-offer-letter-print/"
FAILED = []
PDFTOTEXT = shutil.which("pdftotext")


def check(name, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


def make_user(login, admin=False, view=False):
    mst = MstUser.objects.create(user_name=login, user_login_id=login, user_active="Y", user_type_id="N", user_from=datetime.date(2020, 1, 1), cr_user_id=1, cr_dt=timezone.now())
    UserProfile.objects.create(user_id=mst.user_id, user_login_id=login, is_app_admin=admin)
    if view:
        UserPermission.objects.create(user_id=mst.user_id, menu_key="hr.fs_offer_letter_print", can_view=True, can_add=False, can_edit=False, can_delete=False, can_export=False)
    invalidate_user_access(login)
    c = APIClient(HTTP_HOST="localhost")
    c.force_authenticate(get_user_model().objects.create_user(username=login, password="x"))
    return c


def pdf_text(data):
    if not PDFTOTEXT:
        return None
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(data)
    try:
        return subprocess.run([PDFTOTEXT, "-layout", f.name, "-"], capture_output=True, text=True).stdout
    finally:
        os.unlink(f.name)


def run():
    admin = make_user("zz_pr_admin", admin=True)
    viewer = make_user("zz_pr_viewer", view=True)
    nobody = make_user("zz_pr_nobody")

    print("Numbers in words")
    check("21,418 in Indian words", op.words_indian(21418) == "Twenty One Thousand Four Hundred Eighteen")
    check("12,50,000 in lakhs", op.words_indian(1250000) == "Twelve Lakh Fifty Thousand" and op.group_indian(1250000) == "12,50,000")
    check("60,000 and 1,670", op.words_indian(60000) == "Sixty Thousand" and op.words_indian(1670) == "One Thousand Six Hundred Seventy")
    check("western words and grouping", op.words_western(1250000) == "One Million Two Hundred Fifty Thousand" and op.group_western(1250000) == "1,250,000")

    print("The list")
    r = admin.get(URL, {"page_size": 5}).json()
    check("lists approved letters only", r["count"] > 0 and all(x["workflow"] == "approved" for x in r["results"]))
    first = r["results"][0]
    check("a row carries the letter, the template and the mail status", first["template_label"] in ("Fixed term", "Per day rate") and first["mail_status"] in ("Not sent", "Sent", "Resent") and "can_print" in first)
    check("filter by template works", admin.get(URL, {"template": "per_day", "page_size": 1}).json()["count"] > 0 and admin.get(URL, {"template": "fixed_term", "page_size": 1}).json()["count"] > 0)
    check("meta answers", admin.get(URL + "meta/").status_code == 200)
    check("a letter that is not approved is not here", FsOfferLetter.objects.exclude(cr_status="F", l1_approval_status="A").exists() is False or admin.get(f"{URL}{FsOfferLetter.objects.exclude(cr_status='F', l1_approval_status='A').first().pk}/").status_code == 404)
    check("nothing can be created, edited or deleted here", admin.post(URL, {}, format="json").status_code in (405, 404) and admin.patch(f"{URL}{first['fs_new_appl']}/", {}, format="json").status_code == 405
          and admin.delete(f"{URL}{first['fs_new_appl']}/").status_code == 405)

    print("The PDF")
    ready = [x for x in FsOfferLetter.objects.filter(cr_status="F", l1_approval_status="A", fs_new_appl__appl_fs_category_id=4).select_related("fs_new_appl").order_by("-fs_offer_letter_dt")[:600] if not op.problems_for(x)]
    fixed = next(x for x in ready if op.template_for(x) == op.FIXED_TERM)
    per_day = next(x for x in ready if op.template_for(x) == op.PER_DAY)
    for label, letter in (("fixed-term", fixed), ("per-day", per_day)):
        res = admin.get(f"{URL}{letter.pk}/pdf/")
        check(f"the {label} letter opens as a PDF", res.status_code == 200 and res["Content-Type"] == "application/pdf" and res.content[:4] == b"%PDF", res.content[:150])
    with_head = admin.get(f"{URL}{fixed.pk}/pdf/").content
    without = admin.get(f"{URL}{fixed.pk}/pdf/", {"letterhead": "0"}).content
    check("the letterhead can be left out (the file is smaller)", len(without) < len(with_head))
    check("view-only without an FS category sees nothing (the category rule)", viewer.get(f"{URL}{fixed.pk}/pdf/").status_code == 404)
    vmst = MstUser.objects.get(user_login_id="zz_pr_viewer")
    MstUserFsCatgMapping.objects.create(user=vmst, fs_category_id=4, mapping_from=datetime.date(2020, 1, 1), cr_user_id=1, cr_dt=timezone.now())
    invalidate_user_access("zz_pr_viewer")
    check("view-only with the category can open it", viewer.get(f"{URL}{fixed.pk}/pdf/").status_code == 200)
    check("no rights: closed", nobody.get(URL).status_code == 403 and nobody.get(f"{URL}{fixed.pk}/pdf/").status_code == 403)
    check("signed out: refused", APIClient(HTTP_HOST="localhost").get(URL).status_code in (401, 403))
    res = admin.post(f"{URL}{fixed.pk}/send-mail/")
    check("Send mail answers 'not configured'", res.status_code == 501 and "not configured" in res.json()["error"])

    print("What the letter says")
    FsOfferLetterComponent.objects.filter(offer_letter=fixed, component_id__in=[4, 34]).delete()
    FsOfferLetter.objects.filter(pk=fixed.pk).update(travel_class=None, on_off_desc=None, on_days=21, off_days=14, rig_location="Field X")
    fixed = FsOfferLetter.objects.get(pk=fixed.pk)
    text = pdf_text(op.render_offer_letter_pdf(fixed))
    if text is None:
        print("  skip  pdftotext is not installed: the text checks are skipped")
    else:
        check("no camp sentence without a Camp Allowance row", "Camp Allowance, applicable" not in text)
        check("travel says Not Applicable with no allowance and no eligibility text", "Not Applicable" in text)
        check("on/off days come from the letter", "21 Days ON followed by 14 Days OFF" in text and "Field X" in text)
        FsOfferLetterComponent.objects.create(offer_letter=fixed, component_id=34, amount=4500, counts_in_total="N", show_in_letter="Y", sort_order=12)
        FsOfferLetterComponent.objects.create(offer_letter=fixed, component_id=4, amount=5000, counts_in_total="N", show_in_letter="Y", sort_order=11)
        FsOfferLetter.objects.filter(pk=fixed.pk).update(travel_class="Economy class air ticket", on_off_desc="Custom rotation text")
        text = pdf_text(op.render_offer_letter_pdf(FsOfferLetter.objects.get(pk=fixed.pk)))
        check("the camp amount comes from the Camp Allowance row", "Rs. 4500/- as Camp Allowance" in text)
        check("travel shows the allowance, then the eligibility text", "Rs.5000/- as Travelling Allowance" in text and "Economy class air ticket" in text)
        check("a typed description replaces the on/off sentence", "Custom rotation text" in text and "Days ON followed" not in text)
        FsOfferLetter.objects.filter(pk=fixed.pk).update(travel_class="You are entitled to receive Rs.5000/- as Travelling Allowance")
        text = pdf_text(op.render_offer_letter_pdf(FsOfferLetter.objects.get(pk=fixed.pk)))
        check("the same travel sentence typed in the eligibility text is printed once", text.count("as Travelling Allowance") == 1)
        FsOfferLetter.objects.filter(pk=fixed.pk).update(travel_class="Economy class air ticket")
        FsOfferLetterComponent.objects.filter(offer_letter=fixed, component_id=34).update(show_in_letter="N")
        text = pdf_text(op.render_offer_letter_pdf(FsOfferLetter.objects.get(pk=fixed.pk)))
        check("camp allowance not marked 'show in letter' is left out", "Camp Allowance, applicable" not in text)
        day = pdf_text(op.render_offer_letter_pdf(FsOfferLetter.objects.get(pk=per_day.pk)))
        check("the per-day letter states the day rate and has no salary table", "consolidated day rate of INR" in day and "Monthly Salary Component" not in day and "Appointment as Retainer" in day)

    print("Bulk send")
    FsNewApplDtl.objects.filter(pk=fixed.pk).update(fs_emp_email_pers="a@example.com")
    FsNewApplDtl.objects.filter(pk=per_day.pk).update(fs_emp_email_pers="b@example.com")
    FsOfferLetterComponent.objects.filter(offer_letter=fixed, component_id=1).update(amount=18305)  # put the Basic back, then break another letter below
    res = admin.post(URL + "send-mail-bulk/", {"ids": [per_day.pk, per_day.pk]}, format="json")
    check("selected letters are checked one by one; mail is not configured", res.status_code == 501 and "not configured" in res.json()["error"] and res.json()["ready"] == 1 and len(res.json()["results"]) == 1, res.content[:300])
    noemail = FsOfferLetter.objects.filter(cr_status="F", l1_approval_status="A", fs_new_appl__appl_fs_category_id=4).exclude(pk__in=[fixed.pk, per_day.pk]).order_by("-fs_offer_letter_dt").first()
    FsNewApplDtl.objects.filter(pk=noemail.pk).update(fs_emp_email_pers="")
    res = admin.post(URL + "send-mail-bulk/", {"ids": [per_day.pk, noemail.pk, 99999999]}, format="json").json()
    by_id = {r["id"]: r for r in res["results"]}
    check("each selected letter gets its own result", len(res["results"]) == 3 and res["ready"] == 1 and res["blocked"] == 2)
    check("a letter without an e-mail address is reported, not sent", by_id[noemail.pk]["ready"] is False and ("e-mail" in by_id[noemail.pk]["message"] or "add up" in by_id[noemail.pk]["message"]))
    check("an unknown letter is reported", by_id[99999999]["ready"] is False)
    check("nothing selected is refused", admin.post(URL + "send-mail-bulk/", {"ids": []}, format="json").status_code == 400 and admin.post(URL + "send-mail-bulk/", {}, format="json").status_code == 400)
    check("too many at once is refused", admin.post(URL + "send-mail-bulk/", {"ids": list(range(1, 302))}, format="json").status_code == 400)
    check("no rights: closed", nobody.post(URL + "send-mail-bulk/", {"ids": [per_day.pk]}, format="json").status_code == 403)
    check("the list says why a letter cannot be mailed", "mail_problems" in admin.get(URL, {"page_size": 1}).json()["results"][0])

    print("When a letter cannot be printed")
    FsOfferLetterComponent.objects.filter(offer_letter=fixed, component_id=1).update(amount=1)
    res = admin.get(f"{URL}{fixed.pk}/pdf/")
    check("pay that does not add up is refused with the reason", res.status_code == 400 and "add up" in res.json()["error"], res.content[:200])
    check("and the page says so", not admin.get(f"{URL}{fixed.pk}/").json()["can_print"])
    offshore = FsOfferLetter.objects.filter(cr_status="F", l1_approval_status="A", fs_new_appl__appl_fs_category_id=5).first()
    if offshore:
        res = admin.get(f"{URL}{offshore.pk}/pdf/")
        check("an offshore letter is refused for now", res.status_code == 400 and "offshore" in res.json()["error"].lower(), res.content[:200])


if __name__ == "__main__":
    with transaction.atomic():
        run()
        transaction.set_rollback(True)
    if FAILED:
        print(f"\n{len(FAILED)} FAILED: " + "; ".join(FAILED))
        sys.exit(1)
    print("\nAll checks passed.")
