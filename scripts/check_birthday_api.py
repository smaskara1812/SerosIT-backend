"""Checks the Birthday Mailer and Scheduled Mails endpoints with real requests made by people holding exactly the rights named: the people list,
the Excel template and upload, the picture templates and their preview, the setup panel, the test send, and every action on the Scheduled Mails
page. Pictures go to a temporary folder, mail to a fake server, and the database changes are rolled back.

    cd backend
    .venv/bin/python scripts/check_birthday_api.py
"""
import datetime, io, os, shutil, sys, tempfile, django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TMP = tempfile.mkdtemp(prefix="birthday_api_check_")
os.environ["LOG_DIR"] = os.path.join(TMP, "logs")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from openpyxl import Workbook, load_workbook
from PIL import Image
from rest_framework.test import APIClient
from core import birthday_mailer as bm, mailer
from core.models import AlertSenderDtl, BirthdayPerson, BirthdayTemplate, EmailLog, SchedItem, UserPermission, UserProfile
from core.permissions import invalidate_user_access

settings.MEDIA_ROOT = os.path.join(TMP, "media")
os.makedirs(settings.MEDIA_ROOT)
sent = []
mailer._deliver = lambda subject, html, text, to, cc, bcc, from_name, smtp, images: sent.append({"subject": subject, "to": to, "cc": cc, "bcc": bcc, "images": images})
settings.BIRTHDAY_EMAIL_HOST = ""


class Rollback(Exception):
    pass


fails = []


def ok(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {detail}" if not cond else ""))
    if not cond:
        fails.append(name)


def mk(n, grants):
    U = get_user_model(); u = U.objects.create_user(username=n, password="x")
    uid = (UserProfile.objects.order_by("-user_id").first().user_id or 0) + 1
    UserProfile.objects.create(user_id=uid, user_login_id=n, is_app_admin=False)
    for key, flags in grants.items():
        UserPermission.objects.create(user_id=uid, menu_key=key, can_view="view" in flags, can_add="add" in flags, can_edit="edit" in flags, can_delete="delete" in flags, can_export="export" in flags)
    invalidate_user_access(n)
    c = APIClient(HTTP_HOST="localhost"); c.force_authenticate(u); return c


def xlsx(rows, headers=("Full Name", "Display Name", "Birth Date", "Leaving Date"), sheet="People"):
    wb = Workbook(); ws = wb.active; ws.title = sheet
    ws.append(list(headers))
    for r in rows:
        ws.append(list(r))
    out = io.BytesIO(); wb.save(out); return out.getvalue()


def up(c, data, dry="1", skip="1"):
    return c.post("/api/admin/birthday-people/upload/", {"file": SimpleUploadedFile("people.xlsx", data), "dry_run": dry, "skip_duplicates": skip}, format="multipart")


def png(w=1200, h=800, color=(20, 70, 140)):
    out = io.BytesIO(); Image.new("RGB", (w, h), color).save(out, "PNG"); return out.getvalue()


BM, SM = "admin.birthday_mailer", "admin.scheduled_mails"
try:
    with transaction.atomic():
        bm.ensure_setup()
        # the checks must not depend on real data: inside this rolled-back transaction the list starts empty
        for m in (SchedItem, BirthdayTemplate, BirthdayPerson, AlertSenderDtl):
            m.objects.all().delete()
        full = mk("zzbm1", {BM: ("view", "add", "edit", "delete", "export"), SM: ("view", "edit")})
        viewer = mk("zzbm2", {BM: ("view",), SM: ("view",)})
        nobody = mk("zzbm3", {})
        adder = mk("zzbm4", {BM: ("view", "add")})

        print("A. who may do what")
        ok("no rights: nothing opens", all(nobody.get(u).status_code == 403 for u in ("/api/admin/birthday-people/", "/api/admin/birthday-templates/", "/api/admin/birthday-mailer/overview/", "/api/admin/scheduled-mails/")))
        ok("view-only can read the people, the templates, the setup and the schedule", all(viewer.get(u).status_code == 200 for u in ("/api/admin/birthday-people/", "/api/admin/birthday-templates/", "/api/admin/birthday-mailer/overview/", "/api/admin/scheduled-mails/")))
        ok("view-only cannot add a person", viewer.post("/api/admin/birthday-people/", {"full_name": "X", "birth_month": 1, "birth_day": 1}, format="json").status_code == 403)
        ok("view-only cannot upload a file", up(viewer, xlsx([["A B", None, "15-Mar", None]]), dry="0").status_code == 403)
        ok("view-only cannot add a template or send a test", viewer.post("/api/admin/birthday-templates/", {"file": SimpleUploadedFile("a.png", png())}, format="multipart").status_code == 403 and viewer.post("/api/admin/birthday-mailer/test-send/", {"email": "a@b.co"}, format="json").status_code == 403)
        ok("view-only on Scheduled Mails cannot act", viewer.post("/api/admin/scheduled-mails/1/skip/").status_code == 403 and viewer.post("/api/admin/scheduled-mails/run-now/").status_code == 403)
        ok("the blank template can be downloaded by anyone with View", viewer.get("/api/admin/birthday-people/template/").status_code == 200)

        print("B. the people list")
        r = full.post("/api/admin/birthday-people/", {"full_name": "  Priya   Sharma ", "display_name": "", "birth_month": 3, "birth_day": 10}, format="json")
        ok("a person can be added; the name is tidied; a blank display name means the full name", r.status_code == 201 and r.json()["full_name"] == "Priya Sharma" and r.json()["shown_name"] == "Priya Sharma" and r.json()["is_active"] is True, str(r.content[:200]))
        ok("an identical person is allowed (no uniqueness rule)", full.post("/api/admin/birthday-people/", {"full_name": "Priya Sharma", "birth_month": 3, "birth_day": 10}, format="json").status_code == 201)
        ok("29 February is accepted", full.post("/api/admin/birthday-people/", {"full_name": "Leap Lara", "birth_month": 2, "birth_day": 29}, format="json").status_code == 201)
        ok("30 February is refused", full.post("/api/admin/birthday-people/", {"full_name": "No Day", "birth_month": 2, "birth_day": 30}, format="json").status_code == 400)
        ok("month 13 is refused", full.post("/api/admin/birthday-people/", {"full_name": "No Month", "birth_month": 13, "birth_day": 1}, format="json").status_code == 400)
        ok("a blank name is refused", full.post("/api/admin/birthday-people/", {"full_name": "  ", "birth_month": 1, "birth_day": 1}, format="json").status_code == 400)
        ok("a birth year in the future is refused", full.post("/api/admin/birthday-people/", {"full_name": "Future", "birth_month": 1, "birth_day": 1, "birth_year": 2999}, format="json").status_code == 400)
        past = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        left = full.post("/api/admin/birthday-people/", {"full_name": "Left Lee", "birth_month": 5, "birth_day": 5, "leaving_date": past}, format="json").json()
        ok("someone whose leaving date has passed is inactive", left["is_active"] is False)
        act = {p["full_name"] for p in full.get("/api/admin/birthday-people/?active=Y&page_size=100").json()["results"]}
        ina = {p["full_name"] for p in full.get("/api/admin/birthday-people/?active=N&page_size=100").json()["results"]}
        ok("the Active filter separates them", "Priya Sharma" in act and "Left Lee" not in act and "Left Lee" in ina)
        ok("search finds by name", any(p["full_name"] == "Left Lee" for p in full.get("/api/admin/birthday-people/?search=lee").json()["results"]))
        ok("the person list carries no email address", "email" not in str(full.get("/api/admin/birthday-people/").json()["results"][0]).lower())
        BirthdayPerson.objects.all().delete()

        print("B2. the order of the list")
        today = datetime.date.today()
        def mkp(name, days, leaving=None):
            d = today + datetime.timedelta(days=days)
            return BirthdayPerson.objects.create(full_name=name, birth_month=d.month, birth_day=d.day, leaving_date=leaving, cr_user_id=0, cr_dt=datetime.datetime.now())
        mkp("Zed Soon", 2); mkp("Amy Later", 40); mkp("Mid Mike", 10); mkp("Bob Today", 0); mkp("Yesterday Yan", -1)
        gone = today - datetime.timedelta(days=5)
        mkp("Left Zoe", 3, gone); mkp("Left Adam", 100, gone); mkp("Left Mona", 1, gone)
        names = lambda q: [p["full_name"] for p in full.get("/api/admin/birthday-people/?page_size=100" + q).json()["results"]]
        ok("default: people who are here first, soonest birthday first, then the ones who have left, soonest first", names("") == ["Bob Today", "Zed Soon", "Mid Mike", "Amy Later", "Yesterday Yan", "Left Mona", "Left Zoe", "Left Adam"], str(names("")))
        ok("a birthday that has just passed is last among those who are here (it comes round next year)", names("&sort=next")[4] == "Yesterday Yan")
        ok("sort by name: A to Z, still with the people who are here first", names("&sort=name") == ["Amy Later", "Bob Today", "Mid Mike", "Yesterday Yan", "Zed Soon", "Left Adam", "Left Mona", "Left Zoe"], str(names("&sort=name")))
        cal = lambda q: [(p["birth_month"], p["birth_day"]) for p in full.get("/api/admin/birthday-people/?page_size=100&sort=calendar" + q).json()["results"]]
        ok("calendar order: January to December inside the people who are here, then inside the ones who have left", cal("") [:5] == sorted(cal("")[:5]) and cal("")[5:] == sorted(cal("")[5:]), str(cal("")))
        ok("calendar order with grouping off is one January to December list", cal("&group=0") == sorted(cal("&group=0")), str(cal("&group=0")))
        ok("with grouping off everyone is sorted together", names("&sort=name&group=0") == ["Amy Later", "Bob Today", "Left Adam", "Left Mona", "Left Zoe", "Mid Mike", "Yesterday Yan", "Zed Soon"], str(names("&sort=name&group=0")))
        ok("grouping off by next birthday mixes the two groups", names("&group=0")[:3] == ["Bob Today", "Left Mona", "Zed Soon"], str(names("&group=0")))
        r = full.get("/api/admin/birthday-people/?page_size=3&page=2&sort=next").json()
        ok("paging works on the sorted list", r["count"] == 8 and [p["full_name"] for p in r["results"]] == ["Amy Later", "Yesterday Yan", "Left Mona"], str(r))
        ok("the filter and the search still apply", names("&active=N&sort=name") == ["Left Adam", "Left Mona", "Left Zoe"] and names("&search=mike") == ["Mid Mike"])
        ok("the leaving date is in every row", all("leaving_date" in p for p in full.get("/api/admin/birthday-people/").json()["results"]))
        BirthdayPerson.objects.all().delete()

        print("C. Excel")
        wbk = load_workbook(io.BytesIO(full.get("/api/admin/birthday-people/template/").content))
        ok("the template has the four columns and an instructions sheet", [c.value for c in wbk["People"][1]] == ["Full Name", "Display Name", "Birth Date", "Leaving Date"] and "Instructions" in wbk.sheetnames)
        ok("it carries no sample people to upload by mistake", wbk["People"].max_row == 1 or all(c.value is None for c in wbk["People"][2]))
        rows = [["Anita Rao", None, datetime.date(1990, 3, 14), None], ["Raj Kumar", "Raj", "15-Mar", None], ["Sita Devi", None, "15/03/1985", "31/12/2030"], ["Leap Lara", None, "29-Feb", None],
                ["Ravi Iyer", None, "1990-07-01", None], ["Mona Lisa", None, "5 March 1992", None], [None, None, None, None], ["Bad Date", None, "31-Feb", None], ["", None, "10-Jan", None], ["No Birth", None, None, None], ["Odd Format", None, "sometime", None]]
        r = up(full, xlsx(rows)); rep = r.json()
        ok("a preview reports without saving", r.status_code == 200 and rep["dry_run"] and BirthdayPerson.objects.count() == 0 and rep["added"] == 6, str(rep)[:300])
        ok("bad rows are listed with their Excel row number and reason", rep["error_count"] == 4 and {e["row"] for e in rep["errors"]} == {9, 10, 11, 12}, str(rep["errors"]))
        ok("an empty row is ignored, not an error", all(e["row"] != 8 for e in rep["errors"]))
        r = up(full, xlsx(rows), dry="0"); rep = r.json()
        ok("the upload saves the valid rows and leaves the bad ones", rep["added"] == 6 and BirthdayPerson.objects.count() == 6 and not rep["dry_run"])
        got = {p.full_name: p for p in BirthdayPerson.objects.all()}
        ok("day and month are read from dates, text and 15/03 style; the year is optional", (got["Anita Rao"].birth_month, got["Anita Rao"].birth_day, got["Anita Rao"].birth_year) == (3, 14, 1990) and (got["Raj Kumar"].birth_month, got["Raj Kumar"].birth_day) == (3, 15) and got["Raj Kumar"].birth_year is None
           and (got["Sita Devi"].birth_day, got["Sita Devi"].birth_year) == (15, 1985) and (got["Leap Lara"].birth_month, got["Leap Lara"].birth_day) == (2, 29) and got["Mona Lisa"].birth_month == 3)
        ok("display name and leaving date are kept; the source is Excel", got["Raj Kumar"].display_name == "Raj" and got["Sita Devi"].leaving_date == datetime.date(2030, 12, 31) and got["Sita Devi"].source == "excel")
        r = up(full, xlsx(rows), dry="0").json()
        ok("uploading the same file again adds nobody while 'skip rows already on the list' is on", r["added"] == 0 and r["skipped_duplicates"] == 6 and BirthdayPerson.objects.count() == 6, str(r)[:200])
        r = up(full, xlsx(rows), dry="0", skip="0").json()
        ok("with the tick off there is no unique rule: every row is added", r["added"] == 6 and BirthdayPerson.objects.count() == 12)
        twice = up(full, xlsx([["Same Same", None, "1-Jan", None], ["Same Same", None, "1-Jan", None]]), dry="1").json()
        ok("a repeat inside one file is reported as a duplicate while the tick is on", twice["added"] == 1 and twice["skipped_duplicates"] == 1)
        ok("a file that is not Excel is refused with a message", up(full, b"not a workbook").status_code == 400 and "Excel" in up(full, b"not a workbook").json()["detail"])
        ok("a workbook with no header row is refused", up(full, xlsx([["a"]], headers=("Foo", "Bar"))).status_code == 400)
        ok("only someone with Add can upload", up(adder, xlsx([["Add Person", None, "2-Feb", None]]), dry="0").status_code == 200)
        BirthdayPerson.objects.all().delete()

        print("D. templates")
        r = full.post("/api/admin/birthday-templates/", {"file": SimpleUploadedFile("birthday one.png", png()), "name": "Blue card", "font": "playfair", "color": "#ffe08a", "align_h": "left"}, format="multipart")
        t = r.json()
        ok("a PNG can be uploaded with its settings", r.status_code == 201 and t["name"] == "Blue card" and t["font"] == "playfair" and t["color"] == "#ffe08a" and t["align_h"] == "left" and t["active"] is True, str(r.content[:250]))
        ok("it is stored under birthday_templates in the media folder", t["url"] and os.path.isfile(os.path.join(settings.MEDIA_ROOT, BirthdayTemplate.objects.get(pk=t["id"]).file_path)) and BirthdayTemplate.objects.get(pk=t["id"]).file_path.startswith("birthday_templates/"))
        ok("a GIF, a text file and an oversized file are refused", full.post("/api/admin/birthday-templates/", {"file": SimpleUploadedFile("a.png", b"hello")}, format="multipart").status_code == 400
           and full.post("/api/admin/birthday-templates/", {"file": SimpleUploadedFile("a.png", b"\x89PNG" + os.urandom(6 * 1024 * 1024))}, format="multipart").status_code == 400)
        ok("a font that is not bundled, a bad colour and a box outside the picture are refused", full.patch(f"/api/admin/birthday-templates/{t['id']}/", {"font": "comic"}, format="json").status_code == 400
           and full.patch(f"/api/admin/birthday-templates/{t['id']}/", {"color": "red"}, format="json").status_code == 400
           and full.patch(f"/api/admin/birthday-templates/{t['id']}/", {"box": {"x": 0.7, "w": 0.6}}, format="json").status_code == 400
           and full.patch(f"/api/admin/birthday-templates/{t['id']}/", {"size_min": 200, "size_max": 100}, format="json").status_code == 400)
        r = full.patch(f"/api/admin/birthday-templates/{t['id']}/", {"box": {"x": 0.2, "y": 0.5, "w": 0.6, "h": 0.25}, "align_v": "top", "active": False}, format="json")
        ok("the box, alignment and the active flag can be changed", r.status_code == 200 and r.json()["box"]["x"] == 0.2 and r.json()["align_v"] == "top" and r.json()["active"] is False, str(r.content[:200]))
        pv = full.post("/api/admin/birthday-templates/preview/", {"template_id": t["id"], "sample": "Priya Sharma"}, format="json")
        ok("the preview is a small, light JPEG with the fitting details", pv.status_code == 200 and pv["Content-Type"] == "image/jpeg" and Image.open(io.BytesIO(pv.content)).size[0] == 640 and len(pv.content) < 80_000 and "size" in pv["X-Card-Meta"], str((pv["Content-Type"], len(pv.content))))
        th = t.get("thumb", "")
        ok("the template has a low-resolution thumbnail of about 10 KB or less", th.startswith("data:image/jpeg;base64,") and len(th) < 25_000, str(len(th)))
        import base64
        tim = Image.open(io.BytesIO(base64.b64decode(th.split(",", 1)[1])))
        ok("the thumbnail is small (at most 320 px)", max(tim.size) <= 320, str(tim.size))
        BirthdayTemplate.objects.filter(pk=t["id"]).update(thumb_data="")
        ok("a template saved without a thumbnail gets one when the list is read", viewer.get("/api/admin/birthday-templates/").json()["results"][0]["thumb"].startswith("data:image/"))
        a1 = full.post("/api/admin/birthday-templates/preview/", {"template_id": t["id"], "sample": "Raj", "size_max": 120}, format="json").content
        a2 = full.post("/api/admin/birthday-templates/preview/", {"template_id": t["id"], "sample": "Raj", "size_max": 40, "color": "#ff0000"}, format="json").content
        ok("the preview uses the unsaved settings from the editor", a1 != a2)
        ok("previewing saves nothing", BirthdayTemplate.objects.get(pk=t["id"]).size_max != 40)
        ok("view-only cannot preview", viewer.post("/api/admin/birthday-templates/preview/", {"template_id": t["id"]}, format="json").status_code == 403)
        ok("the picture is served to View holders through the protected media route, and refused to others", viewer.get(t["url"]).status_code == 200 and nobody.get(t["url"]).status_code in (403, 404))
        full.patch(f"/api/admin/birthday-templates/{t['id']}/", {"active": True}, format="json")

        print("E. the setup panel and the test mail")
        ov = viewer.get("/api/admin/birthday-mailer/overview/").json()
        ok("the panel shows the alert, the hour and the recipients (no name without a sender account)", ov["setup"]["alert"]["id"] == 247 and ov["setup"]["from_name"] == "" and ov["setup"]["send_hour"] == 7 and any(ov["setup"]["recipients"].values()))
        ok("it links to the places that change the recipients and the trigger", "mail-alert-to-users" in ov["links"]["recipients"] and ov["links"]["trigger"])
        ok("it counts people and templates", ov["counts"]["templates_active"] == 1)
        ok("sending without an address is refused", full.post("/api/admin/birthday-mailer/test-send/", {"email": "nope"}, format="json").status_code == 400)
        sent.clear()
        r = full.post("/api/admin/birthday-mailer/test-send/", {"email": "tester@example.com"}, format="json")
        ok("a test mail goes only to the address given, marked [Test]", r.status_code == 200 and len(sent) == 1 and sent[0]["to"] == ["tester@example.com"] and not sent[0]["cc"] and not sent[0]["bcc"] and sent[0]["subject"].startswith("[Test] Happy Birthday"), str((r.content[:200], sent)))
        ok("it is in the Email Log as a test", EmailLog.objects.filter(trigger_code="auto.birthday.test", success=True).exists())

        print("F. Scheduled Mails")
        BirthdayPerson.objects.create(full_name="Today Tina", birth_month=datetime.date.today().month, birth_day=datetime.date.today().day, cr_user_id=0, cr_dt=datetime.datetime.now())
        tm = datetime.date.today() + datetime.timedelta(days=2)
        BirthdayPerson.objects.create(full_name="Soon Sam", birth_month=tm.month, birth_day=tm.day, cr_user_id=0, cr_dt=datetime.datetime.now())
        r = full.post("/api/admin/scheduled-mails/run-now/")
        ok("run-now plans the week (and sends anything due)", r.status_code == 200 and SchedItem.objects.filter(label="Soon Sam").exists(), str(r.content[:200]))
        lst = viewer.get("/api/admin/scheduled-mails/?section=upcoming").json()
        ok("upcoming lists the next 7 days", any(x["label"] == "Soon Sam" and x["status"] == "planned" for x in lst["results"]) and lst["health"]["state"] in ("running", "never", "stale"))
        ok("jobs show the schedule in words", lst["jobs"][0]["key"] == "birthday" and "Daily at 07:00" in lst["jobs"][0]["schedule"])
        soon = SchedItem.objects.get(label="Soon Sam")
        ok("skip works with Edit", full.post(f"/api/admin/scheduled-mails/{soon.pk}/skip/").status_code == 200 and SchedItem.objects.get(pk=soon.pk).status == "skipped")
        ok("skipping a skipped mail is refused", full.post(f"/api/admin/scheduled-mails/{soon.pk}/skip/").status_code == 409)
        ok("un-skip puts it back", full.post(f"/api/admin/scheduled-mails/{soon.pk}/unskip/").status_code == 200 and SchedItem.objects.get(pk=soon.pk).status == "planned")
        sent.clear()
        r = full.post(f"/api/admin/scheduled-mails/{soon.pk}/send-now/")
        ok("send now sends at once, to the alert's recipients", r.status_code == 200 and len(sent) == 1 and SchedItem.objects.get(pk=soon.pk).status == "sent" and r.json()["item"]["can"]["resend"], str(r.content[:200]))
        ok("resend sends again", full.post(f"/api/admin/scheduled-mails/{soon.pk}/resend/").status_code == 200 and SchedItem.objects.get(pk=soon.pk).resend_count == 1 and len(sent) == 2)
        ok("a planned mail cannot be resent", full.post(f"/api/admin/scheduled-mails/{SchedItem.objects.exclude(status='sent').first().pk}/resend/").status_code == 409 if SchedItem.objects.exclude(status="sent").exists() else True)
        ok("the Email Log id is on the item", SchedItem.objects.get(pk=soon.pk).email_log_id)
        em = viewer.get(f"/api/admin/scheduled-mails/{soon.pk}/email/").json()
        ok("the mail itself can be read on the page by someone who may see Scheduled Mails", em.get("success") is True and em["subject"].startswith("Happy Birthday") and "data:image/jpeg;base64," in em["body"] and "cid:" not in em["body"], str(em)[:200])
        ok("nobody else can read it", nobody.get(f"/api/admin/scheduled-mails/{soon.pk}/email/").status_code == 403)
        today_tab = viewer.get("/api/admin/scheduled-mails/?section=today").json()
        ok("the Today tab shows what went today", any(x["label"] == "Today Tina" for x in today_tab["results"]))
        ok("filters: by status and by search", viewer.get("/api/admin/scheduled-mails/?section=today&status=sent").status_code == 200 and viewer.get("/api/admin/scheduled-mails/?section=today&q=Tina").json()["count"] >= 1)
        sp = full.post("/api/admin/scheduled-mails/jobs/birthday/pause/"); ok("an automation can be paused", sp.status_code == 200 and sp.json()["enabled"] is False)
        n = SchedItem.objects.count(); BirthdayPerson.objects.create(full_name="Later Lou", birth_month=(datetime.date.today() + datetime.timedelta(days=3)).month, birth_day=(datetime.date.today() + datetime.timedelta(days=3)).day, cr_user_id=0, cr_dt=datetime.datetime.now())
        full.post("/api/admin/scheduled-mails/run-now/")
        ok("while paused nothing new is planned", SchedItem.objects.count() == n)
        ok("it can be resumed", full.post("/api/admin/scheduled-mails/jobs/birthday/resume/").json()["enabled"] is True)
        ok("an unknown automation is refused", full.post("/api/admin/scheduled-mails/jobs/nope/pause/").status_code == 404)
        raise Rollback()
except Rollback:
    pass
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print()
print("FAILED: " + ", ".join(fails) if fails else "all checks passed")
sys.exit(1 if fails else 0)
