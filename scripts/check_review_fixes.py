"""Checks the fixes from the mentor's form review (October 2026): date years, emails, telephone, latitude/longitude, a company that is its own parent,
the Document To Sign list, the Alert Details / Alert To Users rules, and the Leaving Reason Details form, through the real API.

    cd backend
    .venv/bin/python scripts/check_review_fixes.py

Runs every request inside one transaction that is rolled back at the end, so nothing is saved. Needs the normal dev data.
Exits with status 1 if any check fails.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

import datetime
import re

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.test import APIClient

from core.models import MstBusinessGrp, MstCompany, MstCompanyLocation, MstLeavingReason, MstLocation, MstCountry, MailAlertDtl, MstBusinessSystem, MstCertInstitute, MstUser
from core.validation_helpers import dms_error, is_valid_email, phone_error

FAILED = []
M_PK = MstBusinessSystem._meta.pk.name


def check(name, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  {str(detail)[:260]}" if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


def keys(resp):
    try:
        return set(resp.json().keys())
    except Exception:
        return set()


class Rollback(Exception):
    pass


def run():
    client = APIClient(HTTP_HOST="localhost")
    client.force_authenticate(get_user_model().objects.filter(is_superuser=True).first())
    base = "/api/masters/"

    print("shared helpers")
    for good in ("a@b.co", "vinita.singh@essar.com", "x_y+z@sub.domain.in"):
        check(f"email ok: {good}", is_valid_email(good))
    for bad in ("test@inco", "vin#in.c", "sad", "a@b", "a@b.c", "a @b.com", "@b.com", "a@.com"):
        check(f"email refused: {bad}", not is_valid_email(bad))
    check("phone ok", phone_error("+91 22 2654 1234") == "")
    check("phone letters refused", phone_error("asdsa") != "")
    check("phone too short refused", phone_error("12345") != "")
    for good in ("18°58'00.00\"", "072°49'00.00\"E", "7°07'00.00\"S", "84°21'00.00\"W", "21°05'50.47\""):
        axis = "lon" if good[-1] in "EW" or good.startswith(("072", "84", "0")) else "lat"
        check(f"dms ok: {good}", dms_error(good, "lat" if good[-1] in 'S"' and not good.startswith(("072", "84")) else axis) == "")
    for bad in ("dsfakdE", "wdkfsh;kj", "18.5", "91°00'00.00\"", "18°61'00.00\"", "18°58'00.00\"E"):
        check(f"dms refused as a latitude: {bad}", dms_error(bad, "lat") != "")
    check("dms: E is not a latitude letter, N is fine", dms_error("18°58'00.00\"N", "lat") == "" and dms_error("18°58'00.00\"E", "lat") != "")
    check("dms: 181 degrees refused as a longitude", dms_error("181°00'00.00\"E", "lon") != "")

    print("date years (a date typed as 12-01-12 arrives as 0012)")
    loc = MstLocation.objects.first()
    country = MstCountry.objects.first()
    for year in ("0012-12-12", "0027-01-01", "1899-12-31", "2101-01-01", "20260-01-01"):
        r = client.post(f"{base}business-grps/", {"business_grp_name": "zz year test", "business_grp_abrv": "zzy", "business_grp_from": year, "business_grp_order": 1, "business_grp_active": "Y"}, format="json")
        check(f"a Business Group From of {year} is refused", r.status_code == 400 and "business_grp_from" in keys(r), r.content.decode())
    r = client.post(f"{base}business-grps/", {"business_grp_name": "zz year ok", "business_grp_abrv": "zzo", "business_grp_from": "2012-12-12", "business_grp_order": 1, "business_grp_active": "Y"}, format="json")
    check("a Business Group From of 2012-12-12 is accepted", r.status_code == 201, r.content.decode())
    bg_id = r.json().get("business_grp_id")
    r = client.patch(f"{base}business-grps/{bg_id}/", {"parent_business_grp": bg_id}, format="json")
    check("a business group can't be its own parent", r.status_code == 400 and "parent_business_grp" in keys(r), r.content.decode())

    # an old record with a date outside the range can still be edited for something else (judged only when it is new or changed)
    MstBusinessGrp.objects.filter(pk=bg_id).update(business_grp_from=datetime.date(1853, 1, 1))
    r = client.patch(f"{base}business-grps/{bg_id}/", {"business_grp_abrv": "zzp", "business_grp_from": "1853-01-01"}, format="json")
    check("an old record keeping an old date can still be edited", r.status_code == 200, r.content.decode())
    r = client.patch(f"{base}business-grps/{bg_id}/", {"business_grp_from": "0012-01-01"}, format="json")
    check("but changing it to 0012 is refused", r.status_code == 400, r.content.decode())

    print("company: not its own parent")
    comp = MstCompany.objects.exclude(company_active="N").first()
    r = client.patch(f"{base}companies/{comp.pk}/", {"parent_company": comp.pk}, format="json")
    check("a company can't be its own parent", r.status_code == 400 and "parent_company" in keys(r), r.content.decode())

    print("cert institutes: telephone")
    body = {"cert_institute_name": "zz test institute", "cert_institute_shortname": "zzt", "location": loc.pk}
    for bad in ("asdsa", "123"):
        r = client.post(f"{base}cert-institutes/", {**body, "tel_no": bad}, format="json")
        check(f"telephone {bad!r} is refused", r.status_code == 400 and "tel_no" in keys(r), r.content.decode())
    r = client.post(f"{base}cert-institutes/", {**body, "tel_no": "+912226541234"}, format="json")
    check("a real telephone is accepted", r.status_code == 201, r.content.decode())

    print("company locations: latitude and longitude")
    ctype = MstCompanyLocation.objects.exclude(company_loc_type=None).first()
    cl = {"company_loc_name": "zz loc", "company_loc_abrv": "zzl", "company_loc_order": 1, "company_loc_active": "Y", "country": country.pk, "location": loc.pk,
          "company_loc_type": ctype.company_loc_type, "company_loc_ownership": ctype.company_loc_ownership}
    r = client.post(f"{base}company-locations/", {**cl, "latitude": "dsfakdE", "longitude": "wdkfsh;kj"}, format="json")
    check("junk latitude and longitude are refused", r.status_code == 400 and {"latitude", "longitude"} <= keys(r), r.content.decode())
    r = client.post(f"{base}company-locations/", {**cl, "latitude": "18°58'00.00\"", "longitude": "072°49'00.00\"E"}, format="json")
    check("DMS latitude and longitude are accepted", r.status_code == 201, r.content.decode())

    print("emails")
    r = client.get(f"{base}business-systems/?page_size=1")
    bs = (r.json().get("results") or [None])[0]
    if bs:
        r = client.patch(f"{base}business-systems/{bs[M_PK]}/", {"mail_from_address": "test@inco"}, format="json")
        check("Business System: Mail From Address test@inco is refused", r.status_code == 400 and "mail_from_address" in keys(r), r.content.decode())
        r = client.patch(f"{base}business-systems/{bs[M_PK]}/", {"mail_from_address": "alerts@seros.in"}, format="json")
        check("Business System: a real address is accepted", r.status_code == 200, r.content.decode())

    print("mail alerts")
    alert = MailAlertDtl.objects.filter(next_mail_dt__isnull=False).first()
    old_null = MailAlertDtl.objects.filter(next_mail_dt__isnull=True).first()
    new = {"alert_type": "S", "alert_category": "A", "alert_name": "zz alert", "alert_window": 1, "alert_freq": 1, "mail_subject": "s", "particulars": "p", "start_time": 9}
    r = client.post(f"{base}mail-alerts/", new, format="json")
    check("a new alert without Next Mail is refused", r.status_code == 400 and "next_mail_dt" in keys(r), r.content.decode())
    r = client.post(f"{base}mail-alerts/", {**new, "next_mail_dt": "0012-12-12T00:00:00"}, format="json")
    check("a Next Mail in year 12 is refused", r.status_code == 400, r.content.decode())
    r = client.post(f"{base}mail-alerts/", {**new, "next_mail_dt": "2026-12-12T00:00:00"}, format="json")
    check("a good Next Mail is accepted", r.status_code == 201, r.content.decode())
    if alert:
        r = client.patch(f"{base}mail-alerts/{alert.pk}/", {"next_mail_dt": None}, format="json")
        check("Next Mail can't be cleared on an alert that has one", r.status_code == 400, r.content.decode())
    if old_null:
        r = client.patch(f"{base}mail-alerts/{old_null.pk}/", {"alert_freq": old_null.alert_freq}, format="json")
        check("an old alert with no Next Mail can still be edited", r.status_code == 200, r.content.decode())
    alert_id = r.json().get("alert_id") if r.status_code == 201 else (alert.pk if alert else None)
    some = MailAlertDtl.objects.filter(pk__gt=0).first()
    r = client.post(f"{base}mail-alert-to-users/", {"alert": some.pk, "email_addr": "vin#in.c", "addressee_type": "T", "mail_alert_order": 1, "mail_alert_from": "2026-01-01"}, format="json")
    check("Alert To Users: vin#in.c is refused", r.status_code == 400 and "email_addr" in keys(r), r.content.decode())
    r = client.post(f"{base}mail-alert-to-users/", {"alert": some.pk, "email_addr": "x@seros.in", "addressee_type": "T", "mail_alert_order": 1, "mail_alert_from": "0012-12-12"}, format="json")
    check("Alert To Users: From in year 12 is refused", r.status_code == 400 and "mail_alert_from" in keys(r), r.content.decode())
    r = client.post(f"{base}mail-alert-to-users/", {"alert": some.pk, "email_addr": "x@seros.in", "addressee_type": "T", "mail_alert_order": 1, "mail_alert_from": "2026-01-01"}, format="json")
    check("Alert To Users: a good row is accepted", r.status_code == 201, r.content.decode())

    print("employee email for Alert To Users")
    u = MstUser.objects.exclude(user_email__isnull=True).exclude(user_email="").exclude(emp_id=None).first()
    r = client.get(f"{base}mail-alert-to-users/employee-email/?emp={u.emp_id}")
    check("the employee's login email comes back", r.status_code == 200 and r.json().get("email"), r.content.decode())
    r = client.get(f"{base}mail-alert-to-users/employee-email/?emp=abc")
    check("a bad id gives an empty email", r.status_code == 200 and r.json().get("email") == "", r.content.decode())
    r = client.get(f"{base}mail-alert-to-users/employee-email/?emp=-1")
    check("an unknown employee gives an empty email", r.status_code == 200 and r.json().get("email") == "", r.content.decode())

    print("signable documents (the list Document To Sign picks from) and Document To Sign")
    from core.models import DocToSignMapping, MstSignableDoc
    sd = f"{base}signable-docs/"
    check("the 28 starting names are in the table", MstSignableDoc.objects.count() >= 28 and MstSignableDoc.objects.filter(signable_doc_name="Offer_Ltr_Onshore").exists())
    names = set(DocToSignMapping.objects.values_list("doc_name", flat=True).distinct())
    check("every document name already on a mapping is in the table", names <= set(MstSignableDoc.objects.values_list("signable_doc_name", flat=True)), sorted(names))
    r = client.post(sd, {"signable_doc_name": "Zz_New_Letter_Onshore", "signable_doc_active": "Y"}, format="json")
    check("a new document name can be added", r.status_code == 201, r.content.decode())
    new_id = r.json().get("signable_doc_id")
    r = client.post(sd, {"signable_doc_name": "zz_new_letter_onshore", "signable_doc_active": "Y"}, format="json")
    check("the same name in other capitals is refused", r.status_code == 400 and "signable_doc_name" in keys(r), r.content.decode())
    r = client.post(sd, {"signable_doc_name": "Has Spaces", "signable_doc_active": "Y"}, format="json")
    check("a name with spaces is refused", r.status_code == 400 and "signable_doc_name" in keys(r), r.content.decode())
    r = client.post(sd, {"signable_doc_name": "Zz_Other", "signable_doc_active": "X"}, format="json")
    check("an Active value other than Y or N is refused", r.status_code == 400 and "signable_doc_active" in keys(r), r.content.decode())
    listed = [d["signable_doc_name"] for d in client.get(sd + "?active=Y&page_size=100").json()["results"]]
    check("the active list offers the new name", "Zz_New_Letter_Onshore" in listed)
    emp = MstUser.objects.exclude(emp_id=None).first().emp_id
    d = {"employee": emp, "sign_from": "2026-01-01"}
    r = client.post(f"{base}doc-to-sign-mapping/", {**d, "doc_name": "My own document"}, format="json")
    check("a document name that is not in the table is refused", r.status_code == 400 and "doc_name" in keys(r), r.content.decode())
    r = client.post(f"{base}doc-to-sign-mapping/", {**d, "doc_name": "Zz_New_Letter_Onshore"}, format="json")
    check("a name added to the table is accepted on a mapping", r.status_code == 201, r.content.decode())
    map_id = r.json().get("doc_to_sign_id")
    check("a name still used by a mapping can't be deleted", client.delete(f"{sd}{new_id}/").status_code == 400)
    check("it can be switched off instead", client.patch(f"{sd}{new_id}/", {"signable_doc_active": "N"}, format="json").status_code == 200)
    r = client.post(f"{base}doc-to-sign-mapping/", {**d, "sign_from": "2026-01-03", "doc_name": "Zz_New_Letter_Onshore"}, format="json")
    check("a switched-off name is no longer accepted on a new mapping", r.status_code == 400 and "doc_name" in keys(r), r.content.decode())
    r = client.patch(f"{base}doc-to-sign-mapping/{map_id}/", {"sign_from": "2026-01-01", "doc_name": "Zz_New_Letter_Onshore"}, format="json")
    check("an old mapping keeping its (now switched-off) name can still be edited", r.status_code == 200, r.content.decode())
    client.delete(f"{base}doc-to-sign-mapping/{map_id}/")
    check("once no mapping uses it, the name can be deleted", client.delete(f"{sd}{new_id}/").status_code == 204)

    print("user management (its own views, not a serializer)")
    um = "/api/admin/user-management/create/"
    r = client.post(um, {"login_id": "zzrv1", "name": "zz review", "email": "vin#in.c"}, format="json")
    check("a new user with email vin#in.c is refused", r.status_code == 400 and "email" in r.content.decode().lower(), r.content.decode())
    r = client.post(um, {"login_id": "zzrv1", "name": "zz review", "email": "zz@seros.in", "user_from": "0012-12-12"}, format="json")
    check("a new user with a From in year 12 is refused", r.status_code == 400 and "year" in r.content.decode().lower(), r.content.decode())
    r = client.post(um, {"login_id": "zzrv1", "name": "zz review", "email": "zz@seros.in", "user_from": "2026-01-01"}, format="json")
    check("a good new user is created", r.status_code in (200, 201), r.content.decode())
    uid = r.json().get("user_id")
    r = client.post(f"/api/admin/user-management/{uid}/update/", {"name": "zz review", "email": "test@inco"}, format="json")
    check("changing a user's email to test@inco is refused", r.status_code == 400, r.content.decode())
    r = client.post(f"/api/admin/user-management/{uid}/update/", {"name": "zz review", "email": "zz@seros.in", "user_to": "0027-01-01"}, format="json")
    check("changing a user's To to year 27 is refused", r.status_code == 400, r.content.decode())

    print("document to sign: signature upload")
    import io
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.conf import settings
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 60
    up = "/api/masters/doc-to-sign-mapping/upload-sign/"
    r = client.post(up, {"emp_id": str(emp), "file": SimpleUploadedFile("sig.png", png, content_type="image/png")}, format="multipart")
    check("a PNG signature is saved under signatures/", r.status_code == 200 and r.json().get("path", "").startswith(f"signatures/{emp}_"), r.content.decode())
    first = r.json().get("path")
    r = client.post(up, {"emp_id": str(emp), "file": SimpleUploadedFile("sig.png", png, content_type="image/png")}, format="multipart")
    check("a second upload gets its own number, so the first is kept", r.status_code == 200 and r.json().get("path") != first and os.path.isfile(os.path.join(settings.MEDIA_ROOT, first)), r.content.decode())
    second = r.json().get("path")
    r = client.post(up, {"emp_id": str(emp), "file": SimpleUploadedFile("sig.gif", b"GIF89a" + b"0" * 20, content_type="image/gif")}, format="multipart")
    check("a GIF is refused", r.status_code == 400, r.content.decode())
    r = client.post(up, {"emp_id": str(emp), "file": SimpleUploadedFile("sig.png", b"not really a png", content_type="image/png")}, format="multipart")
    check("a file that is not really a PNG is refused", r.status_code == 400, r.content.decode())
    r = client.post(up, {"file": SimpleUploadedFile("sig.png", png, content_type="image/png")}, format="multipart")
    check("an upload with no employee is refused", r.status_code == 400, r.content.decode())
    d2 = {"employee": emp, "sign_from": "2026-01-02", "doc_name": "Offer_Ltr_Onshore"}
    r = client.post(f"{base}doc-to-sign-mapping/", {**d2, "sign_path": "../../etc/passwd"}, format="json")
    check("a made-up signature path is refused", r.status_code == 400 and "sign_path" in keys(r), r.content.decode())
    r = client.post(f"{base}doc-to-sign-mapping/", {**d2, "sign_path": second}, format="json")
    check("the uploaded path is accepted and comes back with a link", r.status_code == 201 and (r.json().get("sign_url") or "").split("?")[0].endswith(second), r.content.decode())
    for p in (first, second):
        try:
            os.remove(os.path.join(settings.MEDIA_ROOT, p))
        except OSError:
            pass
    old = DocToSignMapping.objects.exclude(sign_path__startswith="signatures/").exclude(sign_path=None).first()
    r = client.patch(f"{base}doc-to-sign-mapping/{old.pk}/", {"sign_from": str(old.sign_from), "sign_path": old.sign_path}, format="json")
    check("an old record with a legacy path can still be edited", r.status_code == 200, r.content.decode())

    print("leaving reason details")
    reason = MstLeavingReason.objects.get(leaving_reason="Non Reporting")
    r = client.post(f"{base}leaving-reason-details/", {"leaving_reason_dtl": "zz new job details", "leaving_reason": reason.pk}, format="json")
    check("creating a detail under 'Non Reporting' works", r.status_code == 201, r.content.decode())
    r = client.post(f"{base}leaving-reason-details/", {"leaving_reason_dtl": "zz again", "leaving_reason": "Non Reporting"}, format="json")
    print("       (sending the NAME instead of the id gives:", r.status_code, r.content.decode()[:120], ")")

    raise Rollback()


try:
    with transaction.atomic():
        run()
except Rollback:
    pass

print()
print("FAILED:" if FAILED else "all checks passed", *FAILED, sep="\n  " if FAILED else " ")
sys.exit(1 if FAILED else 0)
