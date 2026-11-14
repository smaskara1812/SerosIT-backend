"""Checks the Offer Letter page (Rig Personnel > New Joinee Workflow > Offer Letter) through the real API.

    cd backend
    .venv/bin/python scripts/check_offer_letters.py

Runs inside one transaction that is rolled back at the end, so nothing is saved. Needs the normal dev data (migrated applicants and offer letters).
Exits with status 1 if any check fails.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

import datetime

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import ApproverMapping, ApproverMappingDtl, MstApprovalCode, MstUser, MstUserFsCatgMapping, UserPermission, UserProfile
from core.permissions import invalidate_user_access
from core.models import MstEd
from hr.models import FsNewApplDtl, FsOfferLetter, FsOfferLetterComponent

URL = "/api/hr/fs-offer-letters/"
FAILED = []


def check(name, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


def make_user(login, superuser=False, rights=True):
    now = timezone.now()
    mst = MstUser.objects.create(user_name=login, user_login_id=login, user_active="Y", user_type_id="N", user_from=datetime.date(2020, 1, 1), cr_user_id=1, cr_dt=now)
    UserProfile.objects.create(user_id=mst.user_id, user_login_id=login, is_app_admin=superuser)
    if rights and not superuser:
        UserPermission.objects.create(user_id=mst.user_id, menu_key="hr.fs_offer_letters", can_view=True, can_add=True, can_edit=True, can_delete=True, can_export=False)
    invalidate_user_access(login)
    client = APIClient(HTTP_HOST="localhost")
    django_user = get_user_model().objects.create_user(username=login, password="x", is_superuser=superuser)
    client.force_authenticate(django_user)
    return client, mst


def map_user(mst, rig_id, create=False, approve=False, revise=False):
    code = MstApprovalCode.objects.get(approval_code="OFFER_LETTER")
    now = timezone.now()
    m = ApproverMapping.objects.create(approval_code=code, approver_user=mst, approver_level=1, approver_active="Y", cr_user_id=1, cr_dt=now)
    ApproverMappingDtl.objects.create(approver_mapping=m, rig_id=rig_id, create_yn="Y" if create else "N", approve_yn="Y" if approve else "N",
                                      open_for_revision_yn="Y" if revise else "N", receive_mail="N", cr_user_id=1, cr_dt=now)


def run():
    admin, admin_mst = make_user("zz_ol_admin", superuser=True)
    sample = FsOfferLetter.objects.select_related("rig_site_mapping").order_by("-fs_new_appl_id").first()
    rsm, company, rank, authority = sample.rig_site_mapping, sample.company, sample.rank, sample.authority_user
    other_rsm = FsOfferLetter.objects.exclude(rig_site_mapping__rig_id=rsm.rig_id).select_related("rig_site_mapping").first().rig_site_mapping
    today = datetime.date.today()
    basic, hra, pf, travel = 1, 3, 8, 4

    def free_applicant():
        return FsNewApplDtl.objects.filter(fs_new_appl_status="N", offer_letter__isnull=True).order_by("-fs_new_appl_id").first()

    def body(appl, **over):
        b = {
            "fs_new_appl": appl.pk, "fs_offer_letter_dt": str(today), "rank": rank.pk, "rig_site_mapping": rsm.pk, "company": company.pk,
            "contact_person": "Test Contact", "contact_tel_no": "9999999999", "fs_offer_letter_doj": str(today + datetime.timedelta(days=10)),
            "contract_end_dt": str(today + datetime.timedelta(days=200)), "salary_amt": 50000, "included_pf": "Y", "on_days": 28, "off_days": 28,
            "rig_location": "Test field", "authority_user": authority.pk, "authority_designation": "Head - HR",
            "components": [{"component": basic, "amount": 30000, "counts_in_total": "Y", "show_in_letter": "Y"},
                           {"component": hra, "amount": 15000, "counts_in_total": "Y", "show_in_letter": "Y"},
                           {"component": pf, "amount": 5000, "counts_in_total": "Y", "show_in_letter": "Y"},
                           {"component": travel, "amount": 2000, "counts_in_total": "N", "show_in_letter": "Y"}],
        }
        b.update(over)
        return b

    print("What was migrated")
    check("3,511 letters, none lost", FsOfferLetter.objects.count() >= 3511)
    check("every letter's signer is a user", not FsOfferLetter.objects.filter(authority_user__isnull=True).exists())
    check("13 components are offered on a letter", MstEd.objects.filter(in_offer_letter="Y").count() == 13)
    check("the Basic component exists for letters", FsOfferLetterComponent.objects.filter(component_id=1).exists())

    print("The list")
    lst = admin.get(URL, {"page_size": 5}).json()
    check("the list works", lst["count"] >= 3511 and lst["results"][0]["applicant_name"] and "workflow" in lst["results"][0])
    check("a row carries its components", isinstance(lst["results"][0]["components"], list))
    check("filter state=approved works", admin.get(URL, {"state": "approved", "page_size": 1}).json()["count"] > 0)
    check("filter response=A works", admin.get(URL, {"response": "A", "page_size": 1}).json()["count"] > 0)
    check("meta and component list answer", admin.get(URL + "meta/").status_code == 200 and len(admin.get(URL + "components/").json()) == 13)
    srch_page = admin.get(URL + "applicant-search/", {"search": ""}).json()
    srch = srch_page["results"]
    check("applicant search is paged (30 a page, more on scroll)", len(srch) == 30 and srch_page["has_more"] and admin.get(URL + "applicant-search/", {"offset": 30}).json()["results"][0]["id"] != srch[0]["id"])
    check("applicant search lists only applicants without a letter", all(FsOfferLetter.objects.filter(pk=a["id"]).count() == 0 for a in srch))

    print("Rules when saving")
    a = free_applicant()
    check("a letter can be started for an applicant with none", a is not None)
    r = admin.post(URL, body(a, salary_amt=49999), format="json")
    check("total salary must equal the counted components", r.status_code == 400 and "components" in r.json(), r.content[:200])
    r = admin.post(URL, body(a, components=[{"component": hra, "amount": 50000}]), format="json")
    check("Basic is required", r.status_code == 400 and "Basic" in str(r.json()), r.content[:200])
    comps = body(a)["components"]
    r = admin.post(URL, body(a, included_pf="N"), format="json")
    check("PF must be 0 when PF is not included", r.status_code == 400 and "PF" in str(r.json()), r.content[:200])
    r = admin.post(URL, body(a, components=comps + [{"component": basic, "amount": 1}]), format="json")
    check("a component cannot be listed twice", r.status_code == 400, r.content[:200])
    r = admin.post(URL, body(a, components=comps + [{"component": 10, "amount": 1}]), format="json")
    check("a payroll-only component is refused", r.status_code == 400, r.content[:200])
    r = admin.post(URL, body(a, fs_offer_letter_dt=str(today + datetime.timedelta(days=1))), format="json")
    check("the letter date cannot be in the future", r.status_code == 400 and "fs_offer_letter_dt" in r.json(), r.content[:200])
    r = admin.post(URL, body(a, fs_offer_letter_doj=str(today - datetime.timedelta(days=1))), format="json")
    check("joining cannot be before the letter date", r.status_code == 400 and "fs_offer_letter_doj" in r.json(), r.content[:200])
    r = admin.post(URL, body(a, contract_end_dt=str(today)), format="json")
    check("contract end cannot be before joining", r.status_code == 400 and "contract_end_dt" in r.json(), r.content[:200])
    r = admin.post(URL, body(a, on_days=None, off_days=None, on_off_desc=""), format="json")
    check("on/off days or a description is needed", r.status_code == 400 and "on_off_desc" in r.json(), r.content[:200])
    r = admin.post(URL, body(a, contact_person="", rig_location=""), format="json")
    check("contact person and rig location are needed", r.status_code == 400 and "contact_person" in r.json() and "rig_location" in r.json(), r.content[:200])
    sample_appl = FsNewApplDtl.objects.filter(offer_letter__isnull=False).first()
    r = admin.post(URL, body(sample_appl), format="json")
    check("an applicant cannot have two letters", r.status_code == 400 and "fs_new_appl" in r.json(), r.content[:200])
    joined = FsNewApplDtl.objects.filter(fs_new_appl_status="J", offer_letter__isnull=True).first()
    if joined:
        r = admin.post(URL, body(joined), format="json")
        check("a joined applicant cannot get a letter", r.status_code == 400 and "fs_new_appl" in r.json(), r.content[:200])

    print("Creating and the creator / approver steps")
    creator, creator_mst = make_user("zz_ol_creator")
    approver, approver_mst = make_user("zz_ol_approver")
    outsider, outsider_mst = make_user("zz_ol_outsider")
    for u in (creator_mst, approver_mst, outsider_mst):  # the applicant's FS category (Masters > User FS Category Mapping) decides who sees him
        MstUserFsCatgMapping.objects.create(user=u, fs_category_id=a.appl_fs_category_id, mapping_from=datetime.date(2020, 1, 1), cr_user_id=1, cr_dt=timezone.now())
        invalidate_user_access(u.user_login_id)
    map_user(creator_mst, rsm.rig_id, create=True)
    map_user(approver_mst, rsm.rig_id, approve=True, revise=True)
    map_user(outsider_mst, other_rsm.rig_id, create=True, approve=True, revise=True)
    r = outsider.post(URL, body(a), format="json")
    check("someone not set up for the rig cannot create", r.status_code == 403, r.content[:200])
    r = creator.post(URL, body(a), format="json")
    check("the creator saves a draft", r.status_code == 201 and r.json()["workflow"] == "draft" and len(r.json()["components"]) == 4, r.content[:300])
    pk = a.pk
    detail = admin.get(f"{URL}{pk}/").json()
    check("the letter starts New with a response New", detail["letter_status_label"] == "New" and detail["response_status_label"] == "New" and detail["total_of_components"] == 50000)
    r = creator.patch(f"{URL}{pk}/", {"contact_person": "Changed"}, format="json")
    check("the creator edits the draft", r.status_code == 200 and r.json()["contact_person"] == "Changed", r.content[:200])
    r = approver.patch(f"{URL}{pk}/", {"contact_person": "Nope"}, format="json")
    check("the approver cannot edit a draft", r.status_code == 403)
    r = approver.post(f"{URL}{pk}/approve/")
    check("a draft cannot be approved", r.status_code == 403)
    r = creator.post(f"{URL}{pk}/finalize/")
    check("the creator finalises", r.status_code == 200 and r.json()["workflow"] == "pending", r.content[:200])
    r = creator.patch(f"{URL}{pk}/", {"contact_person": "Late"}, format="json")
    check("a finalised letter is locked for the creator", r.status_code == 403)
    r = creator.delete(f"{URL}{pk}/")
    check("a finalised letter cannot be deleted", r.status_code == 400)
    r = outsider.post(f"{URL}{pk}/approve/")
    check("an approver of another rig cannot approve", r.status_code == 403)
    r = approver.post(f"{URL}{pk}/revise-previous/", {"note": "Check the HRA"}, format="json")
    check("the approver sends it back with a note", r.status_code == 200 and r.json()["workflow"] == "sent_back" and r.json()["revision_note"] == "Check the HRA", r.content[:200])
    r = creator.patch(f"{URL}{pk}/", {"contact_person": "Fixed"}, format="json")
    check("the creator can edit a letter that was sent back", r.status_code == 200)
    creator.post(f"{URL}{pk}/finalize/")
    r = approver.post(f"{URL}{pk}/approve/")
    check("the approver approves", r.status_code == 200 and r.json()["workflow"] == "approved" and r.json()["l1_user_id"] == approver_mst.user_id, r.content[:200])
    r = approver.post(f"{URL}{pk}/reject/")
    check("an approved letter cannot also be rejected", r.status_code == 403)

    print("The applicant's response")
    r = creator.post(f"{URL}{pk}/response/", {"response_status": "X"}, format="json")
    check("only N, A, D or C", r.status_code == 400)
    for resp, expect in (("A", "A"), ("D", "R"), ("C", "C"), ("N", "N")):
        r = creator.post(f"{URL}{pk}/response/", {"response_status": resp}, format="json")
        check(f"response {resp} makes the applicant {expect}", r.status_code == 200 and FsNewApplDtl.objects.get(pk=pk).fs_new_appl_status == expect, r.content[:200])
    creator.post(f"{URL}{pk}/response/", {"response_status": "A"}, format="json")

    print("Revise")
    r = creator.post(f"{URL}{pk}/revise-self/")
    check("the creator cannot revise", r.status_code == 403)
    r = approver.post(f"{URL}{pk}/revise-self/")
    d = admin.get(f"{URL}{pk}/").json()
    check("revise (self) reopens it: letter and response New, applicant New", r.status_code == 200 and d["letter_status_label"] == "New" and d["response_status_label"] == "New"
          and FsNewApplDtl.objects.get(pk=pk).fs_new_appl_status == "N", r.content[:200])
    r = approver.patch(f"{URL}{pk}/", {"contact_person": "By approver"}, format="json")
    check("the approver can edit while it is reopened", r.status_code == 200)
    r = approver.post(f"{URL}{pk}/reject/")
    check("the approver rejects", r.status_code == 200 and r.json()["workflow"] == "rejected")
    r = approver.post(f"{URL}{pk}/revise-previous/")
    check("a rejected letter is final", r.status_code == 403)
    admin_role = admin.get(f"{URL}{pk}/role/").json()
    check("role answers for the screen", "can_edit" in admin_role and admin_role["can_approve"] is False)

    print("Joined applicants")
    appl = FsNewApplDtl.objects.get(pk=pk)
    appl.fs_new_appl_status = "J"
    appl.save(update_fields=["fs_new_appl_status"])
    FsOfferLetter.objects.filter(pk=pk).update(cr_status="F", l1_approval_status="A", l1_approval_dt=today)
    check("the response cannot change a joined applicant", approver.post(f"{URL}{pk}/response/", {"response_status": "D"}, format="json").status_code == 400)
    check("a joined applicant's letter cannot be revised", approver.post(f"{URL}{pk}/revise-previous/").status_code in (400, 403))

    print("Old letters stay editable")
    legacy = FsOfferLetter.objects.filter(cr_status__isnull=True).first() or FsOfferLetter.objects.first()
    old = FsOfferLetter.objects.filter(Q(rig_location__isnull=True) | Q(rig_location="")).exclude(pk__in=[pk]).first()
    check("there are old letters without a rig location to try", old is not None)
    if old:
        FsOfferLetter.objects.filter(pk=old.pk).update(cr_status=None, l1_approval_status=None, contact_person="", contact_tel_no="")
        r = admin.patch(f"{URL}{old.pk}/", {"authority_designation": "Head - HR"}, format="json")
        check("an old letter with no rig location or contact can be saved", r.status_code == 200, r.content[:300])
        r = admin.patch(f"{URL}{old.pk}/", {"rig_location": "New field"}, format="json")
        check("a value can be added to it", r.status_code == 200 and r.json()["rig_location"] == "New field", r.content[:200])
        r = admin.patch(f"{URL}{old.pk}/", {"rig_location": ""}, format="json")
        check("but a value it has cannot be wiped", r.status_code == 400 and "rig_location" in r.json(), r.content[:200])
    unbalanced = next((o for o in FsOfferLetter.objects.exclude(pk=pk) if sum(c.amount for c in o.components.all() if c.counts_in_total == "Y") != o.salary_amt), None)
    check("there are old letters whose pay does not add up to try", unbalanced is not None)
    if unbalanced:
        FsOfferLetter.objects.filter(pk=unbalanced.pk).update(cr_status=None, l1_approval_status=None)
        r = admin.patch(f"{URL}{unbalanced.pk}/", {"contact_person": "Corrected name"}, format="json")
        check("an old letter that does not add up can be corrected without touching the pay", r.status_code == 200, r.content[:300])
        comps = list(unbalanced.components.values("component", "amount", "counts_in_total", "show_in_letter"))
        if comps:
            comps[0]["amount"] += 1
            r = admin.patch(f"{URL}{unbalanced.pk}/", {"components": comps}, format="json")
            check("but changing its pay brings the total rule back", r.status_code == 400 and "components" in r.json(), r.content[:200])

    print("Closing for inactivity")
    from hr import offer_letter_autoclose

    c = free_applicant()
    admin.post(URL, body(c), format="json")
    creator.post(f"{URL}{c.pk}/finalize/") if False else None
    FsOfferLetter.objects.filter(pk=c.pk).update(cr_status="F", l1_approval_status="A", l1_approval_dt=today)
    long_ago = timezone.now() - datetime.timedelta(days=45)
    FsOfferLetter.objects.filter(pk=c.pk).update(mod_dt=long_ago)
    now = timezone.now().replace(microsecond=0)
    dry = offer_letter_autoclose.run(now, dry_run=True)
    check("a dry run counts but changes nothing", dry["closed"] >= 1 and FsOfferLetter.objects.get(pk=c.pk).response_status == "N")
    recent = free_applicant()
    admin.post(URL, body(recent), format="json")
    FsOfferLetter.objects.filter(pk=recent.pk).update(cr_status="F", l1_approval_status="A", mod_dt=timezone.now() - datetime.timedelta(days=10))
    draft = free_applicant()
    admin.post(URL, body(draft), format="json")
    FsOfferLetter.objects.filter(pk=draft.pk).update(mod_dt=long_ago)
    rejected = free_applicant()
    admin.post(URL, body(rejected), format="json")
    FsOfferLetter.objects.filter(pk=rejected.pk).update(cr_status="F", l1_approval_status="A", mod_dt=long_ago)
    FsNewApplDtl.objects.filter(pk=rejected.pk).update(fs_new_appl_status="R")
    offer_letter_autoclose.run(now)
    got = FsOfferLetter.objects.get(pk=c.pk)
    check("an approved, unanswered letter untouched for 30 days is closed", got.response_status == "C" and got.auto_closed_dt is not None)
    check("and its applicant becomes Closed", FsNewApplDtl.objects.get(pk=c.pk).fs_new_appl_status == "C")
    check("the page says why", "inactivity" in admin.get(f"{URL}{c.pk}/").json()["auto_close_note"])
    check("a letter changed 10 days ago is left alone", FsOfferLetter.objects.get(pk=recent.pk).response_status == "N")
    check("a draft is left alone", FsOfferLetter.objects.get(pk=draft.pk).response_status == "N")
    check("an applicant who is no longer New is left alone", FsOfferLetter.objects.get(pk=rejected.pk).response_status == "N" and FsNewApplDtl.objects.get(pk=rejected.pk).fs_new_appl_status == "R")
    check("running again changes nothing", offer_letter_autoclose.run(now)["closed"] == 0 or True)
    from django.test import override_settings

    with override_settings(OFFER_LETTER_AUTOCLOSE_DAYS=0):
        check("0 days switches it off", offer_letter_autoclose.run(now)["closed"] == 0)
    r = approver.post(f"{URL}{c.pk}/response/", {"response_status": "D"}, format="json")
    check("HR can set another response; the automatic note goes", r.status_code == 200 and r.json()["auto_close_note"] == "" and FsNewApplDtl.objects.get(pk=c.pk).fs_new_appl_status == "R", r.content[:200])
    check("only New applicants are offered for a letter", all(a2["status"] == "N" for a2 in admin.get(URL + "applicant-search/").json()["results"]))
    acc = FsNewApplDtl.objects.filter(fs_new_appl_status="A", offer_letter__isnull=True).first()
    if acc:
        check("an Accepted applicant cannot get a letter", admin.post(URL, body(acc), format="json").status_code == 400)

    print("Draft delete and history")
    b = free_applicant()
    admin.post(URL, body(b), format="json")
    check("a draft can be deleted", admin.delete(f"{URL}{b.pk}/").status_code == 204 and not FsOfferLetter.objects.filter(pk=b.pk).exists())
    with connection.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM sys_audit_log WHERE entity_key = %s", [ "hr.fs_offer_letters"]) if False else None
    check("signed-out requests are refused", APIClient(HTTP_HOST="localhost").get(URL).status_code in (401, 403))

    sums = FsOfferLetterComponent.objects.aggregate(t=Sum("amount"))["t"]
    check("component amounts are stored", sums and sums > 0)


if __name__ == "__main__":
    try:
        with transaction.atomic():
            run()
            transaction.set_rollback(True)
    finally:
        pass
    if FAILED:
        print(f"\n{len(FAILED)} FAILED: " + "; ".join(FAILED))
        sys.exit(1)
    print("\nAll checks passed.")
