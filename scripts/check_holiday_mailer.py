"""Checks the Holiday Mailer: the dates (one day, several days, yearly, 29 February, across New Year), planning, sending with a fake mail server
(subject, picture, recipients from the alert, failover, retries), the scheduler running it beside the birthday job, and every endpoint with people
holding exactly the rights named. Pictures go to a temporary folder, mail to a fake server, and the database changes are rolled back.

    cd backend
    .venv/bin/python scripts/check_holiday_mailer.py
"""
import datetime, io, os, shutil, sys, tempfile, django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TMP = tempfile.mkdtemp(prefix="holiday_check_")
os.environ["LOG_DIR"] = os.path.join(TMP, "logs")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from PIL import Image
from rest_framework.test import APIClient
from core import holiday_mailer as hm, mailer, scheduler
from core.models import AlertSenderDtl, EmailLog, HolidayEvent, MailAlertDtl, MailAlertToUser, NotificationTrigger, SchedItem, SchedJob, UserPermission, UserProfile
from core.permissions import invalidate_user_access

settings.MEDIA_ROOT = os.path.join(TMP, "media")
os.makedirs(os.path.join(settings.MEDIA_ROOT, hm.FOLDER))
settings.BIRTHDAY_EMAIL_HOST = ""
sent, fail_hosts = [], set()


def fake_deliver(subject, html, text, to, cc, bcc, from_name, smtp, inline_images):
    if smtp["host"] in fail_hosts:
        raise ConnectionError(f"{smtp['host']} refused the connection")
    sent.append({"subject": subject, "to": to, "cc": cc, "bcc": bcc, "from_name": from_name, "host": smtp["host"], "images": inline_images, "html": html})


mailer._deliver = fake_deliver


class Rollback(Exception):
    pass


fails = []


def ok(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {detail}" if not cond else ""))
    if not cond:
        fails.append(name)


D = datetime.date
NOW = datetime.datetime(2026, 11, 10, 7, 0, 5)  # five seconds past 07:00


def pic(w=1200, h=600, color=(200, 80, 30), mode="RGB"):
    out = io.BytesIO(); Image.new(mode, (w, h), color).save(out, "PNG"); return out.getvalue()


def event(name, on, days=1, yearly="N", active="Y", subject="", w=1200):
    rel = f"{hm.FOLDER}/{name.replace(' ', '_')}.png"
    with open(os.path.join(settings.MEDIA_ROOT, rel), "wb") as fh:
        fh.write(pic(w))
    return HolidayEvent.objects.create(name=name, subject=subject, send_on=on, send_days=days, repeat_yearly=yearly, is_active=active, file_path=rel, width=w, height=600, cr_user_id=0, cr_dt=NOW)


def mk(n, grants):
    U = get_user_model(); u = U.objects.create_user(username=n, password="x")
    uid = (UserProfile.objects.order_by("-user_id").first().user_id or 0) + 1
    UserProfile.objects.create(user_id=uid, user_login_id=n, is_app_admin=False)
    for key, flags in grants.items():
        UserPermission.objects.create(user_id=uid, menu_key=key, can_view="view" in flags, can_add="add" in flags, can_edit="edit" in flags, can_delete="delete" in flags, can_export="export" in flags)
    invalidate_user_access(n)
    c = APIClient(HTTP_HOST="localhost"); c.force_authenticate(u); return c


MK = "admin.holiday_mailer"
try:
    with transaction.atomic():
        # the checks must not depend on real data: inside this rolled-back transaction the lists start empty
        SchedItem.objects.all().delete(); HolidayEvent.objects.all().delete(); AlertSenderDtl.objects.all().delete()
        NotificationTrigger.objects.filter(entity_key=hm.ENTITY_KEY).delete()

        print("A. the dates")
        one = event("Republic Day", D(2026, 1, 26), yearly="Y")
        ok("a fixed date repeats every year", hm.send_dates(one, D(2027, 1, 20), D(2027, 1, 30)) == [D(2027, 1, 26)] and hm.send_dates(one, D(2028, 1, 20), D(2028, 1, 30)) == [D(2028, 1, 26)])
        once = event("Diwali", D(2026, 11, 8), days=3)
        ok("several days in a row start on the date and last that many days", hm.send_dates(once, D(2026, 11, 1), D(2026, 11, 30)) == [D(2026, 11, 8), D(2026, 11, 9), D(2026, 11, 10)])
        ok("a one-off does not come back next year", hm.send_dates(once, D(2027, 11, 1), D(2027, 11, 30)) == [])
        ok("only that day by default", hm.send_dates(event("One day", D(2026, 12, 25)), D(2026, 12, 1), D(2026, 12, 31)) == [D(2026, 12, 25)])
        ny = event("New Year", D(2026, 12, 31), days=3, yearly="Y")
        ok("a run that crosses New Year is found from either side", hm.send_dates(ny, D(2027, 1, 1), D(2027, 1, 5)) == [D(2027, 1, 1), D(2027, 1, 2)] and hm.send_dates(ny, D(2026, 12, 29), D(2026, 12, 31)) == [D(2026, 12, 31)])
        leap = event("Leap Day", D(2028, 2, 29), yearly="Y")
        ok("29 February that repeats is kept on 28 February in a year with no 29th", hm.send_dates(leap, D(2027, 2, 20), D(2027, 3, 2)) == [D(2027, 2, 28)] and hm.send_dates(leap, D(2032, 2, 20), D(2032, 3, 2)) == [D(2032, 2, 29)])
        ok("the next send of a one-off in the past is none, a repeating one is always found", hm.next_send(HolidayEvent(send_on=D(2020, 1, 1), send_days=1, repeat_yearly="N"), D(2026, 11, 10)) is None and hm.next_send(one, D(2026, 11, 10)) == D(2027, 1, 26))
        ok("the next send inside a run is today", hm.next_send(once, D(2026, 11, 9)) == D(2026, 11, 9))
        ok("'Day 2 of 3' is said for a run, nothing for one day", hm.day_text(once, D(2026, 11, 9)) == "Day 2 of 3" and hm.day_text(one, D(2026, 1, 26)) == "")
        HolidayEvent.objects.all().delete()

        print("B. the setup is read from the trigger and the alert")
        alert = MailAlertDtl.objects.filter(alert_active="Y").order_by("alert_id").first()
        orig = {k: getattr(alert, k) for k in ("alert_name", "alert_display_name", "mail_subject", "start_time")}
        MailAlertDtl.objects.filter(pk=alert.pk).update(alert_name="Holiday Events", mail_subject="Season's greetings", start_time=8)
        AlertSenderDtl.objects.create(alert=alert, mail_host="down.example.test", mail_port=25, mail_security="N", from_address="hr@example.test", display_name="Human Resource – Seros", is_active="Y", cr_user_id=0, cr_dt=NOW)
        s0 = hm.get_setup(NOW.date())
        ok("with no trigger the page is told what to do", not s0["trigger_found"] and s0["warnings"])
        did = hm.ensure_setup(alert_name="Holiday Events")
        trig = NotificationTrigger.objects.get(entity_key=hm.ENTITY_KEY, action=hm.ACTION)
        ok("the setup command finds the alert by its name and creates the trigger row", trig.alert_id == alert.pk and did)
        ok("it is safe to run again", hm.ensure_setup(alert_name="Holiday Events") == [])
        MailAlertToUser.objects.filter(alert_id=alert.pk).delete()
        s1 = hm.get_setup(NOW.date())
        ok("no recipients is a warning, the hour comes from the alert and the From name from its sender account", s1["send_hour"] == 8 and s1["from_name"] == "Human Resource – Seros" and any("nobody" in w.lower() for w in s1["warnings"]))
        MailAlertToUser.objects.create(alert=alert, recipient_name="Everyone", email_addr="all-staff@example.test", addressee_type="T", mail_alert_from=D(2026, 1, 1), mail_alert_to=None, mail_alert_order=1, cr_user_id=0, cr_dt=NOW)
        MailAlertToUser.objects.create(alert=alert, recipient_name="Records", email_addr="records@example.test", addressee_type="B", mail_alert_from=D(2026, 1, 1), mail_alert_to=None, mail_alert_order=2, cr_user_id=0, cr_dt=NOW)
        setup = hm.get_setup(NOW.date())
        ok("recipients are the alert's active To and Bcc rows", setup["recipients"]["to"] == ["all-staff@example.test"] and setup["recipients"]["bcc"] == ["records@example.test"], str(setup["recipients"]))
        ok("nothing is wrong now", not [w for w in setup["warnings"] if "trigger" in w.lower() or "recipients" in w.lower()])

        print("C. planning the next 7 days")
        diwali = event("Diwali", D(2026, 11, 10), days=3, subject="Happy Diwali {year} from Seros")
        fixed = event("Children's Day", D(2026, 11, 14), yearly="Y")
        far = event("Far Away", D(2026, 11, 25))
        off = event("Switched Off", D(2026, 11, 11), active="N")
        hm.JOB.plan(NOW)
        items = SchedItem.objects.filter(job_key="holiday")
        ok("a mail is planned for each day an active event goes out in the next 7 days, not beyond and not for a switched-off one", sorted(i.label for i in items) == ["Children's Day", "Diwali · day 1 of 3", "Diwali · day 2 of 3", "Diwali · day 3 of 3"], str(sorted(i.label for i in items)))
        ok("each is due at the alert's hour (08:00)", all(i.due_at.hour == 8 for i in items))
        hm.JOB.plan(NOW)
        ok("planning again adds nothing", SchedItem.objects.filter(job_key="holiday").count() == 4)
        HolidayEvent.objects.filter(pk=fixed.pk).update(send_on=D(2026, 11, 30), repeat_yearly="N")
        hm.JOB.plan(NOW)
        ok("an event whose date moves out of the window is cancelled", SchedItem.objects.get(label="Children's Day").status == "cancelled")
        HolidayEvent.objects.filter(pk=fixed.pk).update(send_on=D(2026, 11, 14))
        HolidayEvent.objects.filter(pk=diwali.pk).update(name="Deepavali")
        hm.JOB.plan(NOW)
        ok("a renamed event updates the planned items", SchedItem.objects.filter(label="Deepavali · day 1 of 3").exists())
        HolidayEvent.objects.filter(pk=diwali.pk).update(name="Diwali")
        hm.JOB.plan(NOW)

        print("D. sending")
        before = hm.JOB.process(datetime.datetime(2026, 11, 10, 7, 59, 0))
        ok("nothing goes out before the hour", not sent and before["sent"] == 0)
        res = hm.JOB.process(NOW + datetime.timedelta(hours=1))
        ok("day 1 of Diwali goes out at 08:00, once", res["sent"] == 1 and len(sent) == 1, str((res, len(sent))))
        m = sent[0]
        ok("it goes to the alert's To and Bcc", m["to"] == ["all-staff@example.test"] and m["bcc"] == ["records@example.test"])
        ok("the subject is the event's own, with the year", m["subject"] == "Happy Diwali 2026 from Seros", m["subject"])
        ok("the From name is the sender account's display name", m["from_name"] == "Human Resource – Seros")
        ok("the picture is sent inline and nothing is drawn on it", m["images"][0][0] == "holiday" and m["images"][0][2] == "png" and "cid:holiday" in m["html"] and Image.open(io.BytesIO(m["images"][0][1])).getpixel((5, 5)) == (200, 80, 30))
        ok("it is shrunk to 900 px wide", Image.open(io.BytesIO(m["images"][0][1])).size[0] == 900)
        ok("it is in the Email Log, tagged auto.holiday", EmailLog.objects.filter(trigger_code="auto.holiday", success=True).count() == 1)
        n = len(sent); hm.JOB.process(NOW + datetime.timedelta(hours=2))
        ok("the next hour sends nothing again", len(sent) == n)
        day2 = datetime.datetime(2026, 11, 11, 8, 0, 5)
        hm.JOB.plan(day2); r2 = hm.JOB.process(day2)
        ok("the next day sends day 2 of the same event", r2["sent"] == 1 and SchedItem.objects.get(label="Diwali · day 2 of 3").status == "sent" and SchedItem.objects.get(label="Diwali · day 1 of 3").status == "sent")
        ev_no_subject = event("No Subject", D(2026, 11, 12))
        ok("an event with no subject uses the alert's subject", hm.subject_for(ev_no_subject, hm.get_setup(NOW.date()), D(2026, 11, 12)) == "Season's greetings")
        MailAlertDtl.objects.filter(pk=alert.pk).update(mail_subject="")
        ok("and 'Happy <name>' when the alert has none", hm.subject_for(ev_no_subject, hm.get_setup(NOW.date()), D(2026, 11, 12)) == "Happy No Subject")
        MailAlertDtl.objects.filter(pk=alert.pk).update(mail_subject="Season's greetings")
        big = event("Big Photo", D(2026, 11, 20), w=1200)
        with open(os.path.join(settings.MEDIA_ROOT, big.file_path), "wb") as fh:
            im = Image.effect_noise((1800, 900), 80).convert("RGB"); im.save(fh, "PNG")
        d, sub, w = hm.mail_picture(big)
        ok("a heavy picture with no see-through parts is sent as a JPEG to keep the mail light", sub == "jpeg" and w == 900 and d[:2] == b"\xff\xd8" and len(d) < 900 * 1024, f"{sub} {len(d)}")
        clear = event("Clear", D(2026, 11, 21))
        Image.new("RGBA", (1000, 500), (255, 0, 0, 0)).save(os.path.join(settings.MEDIA_ROOT, clear.file_path), "PNG")
        ok("a picture with see-through parts stays a PNG", hm.mail_picture(clear)[1] == "png")

        print("E. failures and retries")
        sent.clear()
        HolidayEvent.objects.filter(pk=diwali.pk).update(send_days=3)
        third = datetime.datetime(2026, 11, 12, 8, 0, 5)
        hm.JOB.plan(third)
        settings.EMAIL_HOST = "down.example.test"; fail_hosts.add("down.example.test")
        r3 = hm.JOB.process(third)
        it = SchedItem.objects.get(label="Diwali · day 3 of 3")
        ok("when every account refuses, the item is Failed with the reason", r3["failed"] >= 1 and it.status == "failed" and "refused" in it.last_error and it.attempts == 1, f"{r3} {it.status} {it.last_error[:80]}")
        fail_hosts.clear()
        r4 = hm.JOB.process(third + datetime.timedelta(hours=1))
        ok("at the next hourly run it is tried again and goes out", r4["retried"] >= 1 and SchedItem.objects.get(pk=it.pk).status == "sent" and SchedItem.objects.get(pk=it.pk).attempts == 2)
        os.remove(os.path.join(settings.MEDIA_ROOT, far.file_path))
        far_item = SchedItem.objects.create(job_key="holiday", subject_key=str(far.event_id), label="Far Away", send_date=third.date(), due_at=third, status="planned", cr_dt=third)
        hm.JOB.process(third)
        ok("a missing picture is a clear Failed reason, not a crash", SchedItem.objects.get(pk=far_item.pk).status == "failed" and "missing" in SchedItem.objects.get(pk=far_item.pk).last_error)
        far_item.delete()
        MailAlertDtl.objects.filter(pk=alert.pk).update(alert_active=None)
        off_item = SchedItem.objects.create(job_key="holiday", subject_key=str(event("Off Alert", D(2027, 6, 6)).event_id), label="x", send_date=third.date(), due_at=third, status="planned", cr_dt=third)
        n_sent = len(sent); hm.JOB.process(third)
        ok("an alert that is not ticked Active sends nothing, and the item says why", len(sent) == n_sent and SchedItem.objects.get(pk=off_item.pk).status == "failed" and "switched off" in SchedItem.objects.get(pk=off_item.pk).last_error and "Alert Details" in SchedItem.objects.get(pk=off_item.pk).last_error, SchedItem.objects.get(pk=off_item.pk).last_error)
        MailAlertDtl.objects.filter(pk=alert.pk).update(alert_active="Y")
        hm.JOB.process(third + datetime.timedelta(hours=2))
        ok("ticking Active again lets the retry go out", SchedItem.objects.get(pk=off_item.pk).status == "sent")
        off_item.delete()
        NotificationTrigger.objects.filter(pk=trig.pk).update(notification_trigger_active="N")
        probe = event("Probe", D(2027, 5, 5))
        it2 = SchedItem.objects.create(job_key="holiday", subject_key=str(probe.event_id), label="x", send_date=third.date(), due_at=third, status="planned", cr_dt=third)
        hm.JOB.process(third)
        ok("with the trigger off nothing is sent and the item says why", SchedItem.objects.get(pk=it2.pk).status == "failed" and "switched off" in SchedItem.objects.get(pk=it2.pk).last_error)
        NotificationTrigger.objects.filter(pk=trig.pk).update(notification_trigger_active="Y")
        it2.delete()
        gone = SchedItem.objects.create(job_key="holiday", subject_key="999999", label="Gone", send_date=third.date(), due_at=third, status="planned", cr_dt=third)
        hm.JOB.process(third)
        ok("an item whose event was deleted is cancelled", SchedItem.objects.get(pk=gone.pk).status == "cancelled")

        print("F. the scheduler runs it beside the birthday job")
        ok("the holiday job is registered", "holiday" in scheduler.JOBS and "birthday" in scheduler.JOBS)
        SchedItem.objects.all().delete(); sent.clear()
        res = scheduler.tick(NOW + datetime.timedelta(hours=1), owner="check")
        ok("one hourly run looks after every job", set(res["jobs"]) == {"birthday", "holiday", "haz_id_register", "rig_rate_breakup"} and not res["errors"], str(res))
        ok("the holiday job reports what it did", SchedJob.objects.get(job_key="holiday").last_run_at is not None)
        sj = SchedJob.objects.get(job_key="holiday"); SchedJob.objects.filter(pk=sj.pk).update(enabled="N")
        n = SchedItem.objects.filter(job_key="holiday").count(); HolidayEvent.objects.create(name="Late", send_on=D(2026, 11, 11), file_path="x", cr_user_id=0, cr_dt=NOW)
        scheduler.tick(NOW + datetime.timedelta(hours=2), owner="check")
        ok("paused, the holiday job plans nothing new", SchedItem.objects.filter(job_key="holiday").count() == n)
        SchedJob.objects.filter(pk=sj.pk).update(enabled="Y")
        HolidayEvent.objects.filter(name="Late").delete()
        SchedItem.objects.filter(job_key="holiday").delete()

        print("G. the endpoints")
        full = mk("zzhm1", {MK: ("view", "add", "edit", "delete"), "admin.scheduled_mails": ("view", "edit")})
        viewer = mk("zzhm2", {MK: ("view",)})
        nobody = mk("zzhm3", {})
        today = D.today()
        up = lambda name="x.png", data=None: SimpleUploadedFile(name, data or pic())
        ok("no rights: nothing opens", all(nobody.get(u).status_code == 403 for u in ("/api/admin/holiday-events/", "/api/admin/holiday-mailer/overview/")))
        ok("view-only can read the events and the setup", all(viewer.get(u).status_code == 200 for u in ("/api/admin/holiday-events/", "/api/admin/holiday-mailer/overview/")))
        ok("view-only cannot add, change, delete or test", viewer.post("/api/admin/holiday-events/", {"file": up(), "name": "X", "send_on": "2030-01-01"}, format="multipart").status_code == 403
           and viewer.patch("/api/admin/holiday-events/1/", {"name": "Y"}, format="json").status_code in (403, 404)
           and viewer.post("/api/admin/holiday-mailer/test-send/", {"email": "a@b.co", "event_id": 1}, format="json").status_code == 403)
        HolidayEvent.objects.all().delete()
        r = full.post("/api/admin/holiday-events/", {"file": up("Holi.png"), "name": "  Holi  ", "subject": "Happy Holi!", "send_on": (today + datetime.timedelta(days=30)).isoformat(), "send_days": "2", "repeat_yearly": "0", "active": "1"}, format="multipart")
        j = r.json()
        ok("an event can be added with a picture", r.status_code == 201 and j["name"] == "Holi" and j["send_days"] == 2 and j["repeat_yearly"] is False and j["active"] is True and j["thumb"].startswith("data:image"), str(r.content[:200]))
        eid = j["id"]
        row = HolidayEvent.objects.get(pk=eid)
        ok("the picture is stored in the holiday folder", row.file_path.startswith("holiday_images/") and os.path.isfile(os.path.join(settings.MEDIA_ROOT, row.file_path)))
        ok("a picture is required", full.post("/api/admin/holiday-events/", {"name": "No Pic", "send_on": "2030-01-01"}, format="multipart").status_code == 400)
        ok("the name, the date and the number of days are checked", full.post("/api/admin/holiday-events/", {"file": up(), "name": " ", "send_on": "2030-01-01"}, format="multipart").status_code == 400
           and full.post("/api/admin/holiday-events/", {"file": up(), "name": "A", "send_on": "not a date"}, format="multipart").status_code == 400
           and full.post("/api/admin/holiday-events/", {"file": up(), "name": "A", "send_on": "2030-01-01", "send_days": "99"}, format="multipart").status_code == 400)
        ok("a file that is not a picture is refused", full.post("/api/admin/holiday-events/", {"file": SimpleUploadedFile("x.png", b"not a picture"), "name": "A", "send_on": "2030-01-01"}, format="multipart").status_code == 400)
        ok("a file over 5 MB is refused", full.post("/api/admin/holiday-events/", {"file": SimpleUploadedFile("big.png", b"0" * (5 * 1048576 + 10)), "name": "A", "send_on": "2030-01-01"}, format="multipart").status_code == 400)
        ok("a PDF is refused", full.post("/api/admin/holiday-events/", {"file": SimpleUploadedFile("a.pdf", b"%PDF-1.4"), "name": "A", "send_on": "2030-01-01"}, format="multipart").status_code == 400)
        lst = full.get("/api/admin/holiday-events/").json()
        ok("it shows under Upcoming with its next date", lst["counts"]["upcoming"] == 1 and lst["results"][0]["next_send"] == (today + datetime.timedelta(days=30)).isoformat() and lst["results"][0]["run_to"] == (today + datetime.timedelta(days=31)).isoformat(), str(lst)[:300])
        e2 = full.post("/api/admin/holiday-events/", {"file": up(), "name": "Old Festival", "send_on": "2020-01-01"}, format="multipart").json()
        ok("a one-off in the past shows under Over, not Upcoming", full.get("/api/admin/holiday-events/?when=over").json()["counts"]["over"] == 1 and all(x["name"] != "Old Festival" for x in full.get("/api/admin/holiday-events/").json()["results"]))
        ok("search finds by name or subject", [x["name"] for x in full.get("/api/admin/holiday-events/?when=all&q=holi!").json()["results"]] == ["Holi"] or [x["name"] for x in full.get("/api/admin/holiday-events/?when=all&q=happy holi").json()["results"]] == ["Holi"])
        r = full.patch(f"/api/admin/holiday-events/{eid}/", {"subject": "Holi Hai!", "send_days": 1, "active": False}, format="json")
        ok("an event can be changed (JSON)", r.status_code == 200 and r.json()["subject"] == "Holi Hai!" and r.json()["send_days"] == 1 and r.json()["active"] is False and r.json()["name"] == "Holi", str(r.content[:200]))
        old_path = HolidayEvent.objects.get(pk=eid).file_path
        r = full.patch(f"/api/admin/holiday-events/{eid}/", {"file": up("new.png", pic(800, 400, (1, 2, 3))), "name": "Holi", "send_on": row.send_on.isoformat(), "send_days": "1", "active": "1"}, format="multipart")
        new_path = HolidayEvent.objects.get(pk=eid).file_path
        ok("the picture can be replaced and the old file is removed", r.status_code == 200 and new_path != old_path and os.path.isfile(os.path.join(settings.MEDIA_ROOT, new_path)) and not os.path.isfile(os.path.join(settings.MEDIA_ROOT, old_path)) and r.json()["width"] == 800, str(r.content[:200]))
        ok("a bad change is refused and nothing is saved", full.patch(f"/api/admin/holiday-events/{eid}/", {"send_days": 0}, format="json").status_code == 400 and HolidayEvent.objects.get(pk=eid).send_days == 1)
        ok("the file is served only to people who hold the page", viewer.get(row.file_path and f"/api/media/{new_path}").status_code in (200, 302) and nobody.get(f"/api/media/{new_path}").status_code in (401, 403, 404))
        ov = viewer.get("/api/admin/holiday-mailer/overview/").json()
        ok("the setup panel shows the alert, the recipients and what is coming", ov["setup"]["alert"]["name"] == "Holiday Events" and ov["setup"]["recipients"]["to"] and ov["counts"]["events"] == 2 and ov["coming"], str(ov)[:300])
        sent.clear()
        ok("a test mail needs an address and an event", full.post("/api/admin/holiday-mailer/test-send/", {"email": "nope", "event_id": eid}, format="json").status_code == 400 and full.post("/api/admin/holiday-mailer/test-send/", {"email": "a@b.co", "event_id": 0}, format="json").status_code == 400)
        r = full.post("/api/admin/holiday-mailer/test-send/", {"email": "me@example.test", "event_id": eid}, format="json")
        ok("a test mail goes to that address only, marked [Test]", r.status_code == 200 and len(sent) == 1 and sent[0]["to"] == ["me@example.test"] and not sent[0]["cc"] and not sent[0]["bcc"] and sent[0]["subject"].startswith("[Test] "), str((r.content[:200], sent)))
        sm = full.get("/api/admin/scheduled-mails/").json()
        ok("Scheduled Mails lists the automations", {j["key"] for j in sm["jobs"]} == {"birthday", "holiday", "haz_id_register", "rig_rate_breakup"} and "event's dates" in next(j["schedule"] for j in sm["jobs"] if j["key"] == "holiday"), str(sm["jobs"])[:300])
        ok("deleting needs the Delete right and removes the picture and cancels planned mail", viewer.delete(f"/api/admin/holiday-events/{eid}/").status_code == 403)
        planned = SchedItem.objects.create(job_key="holiday", subject_key=str(eid), label="Holi", send_date=today, due_at=datetime.datetime.now(), status="planned", cr_dt=datetime.datetime.now())
        r = full.delete(f"/api/admin/holiday-events/{eid}/")
        ok("an event can be removed", r.status_code == 204 and not HolidayEvent.objects.filter(pk=eid).exists() and not os.path.isfile(os.path.join(settings.MEDIA_ROOT, new_path)) and SchedItem.objects.get(pk=planned.pk).status == "cancelled")
        from core.models import SysAuditLog
        ok("adding, changing and removing are in the audit trail", {"create", "update", "delete"} <= set(SysAuditLog.objects.filter(entity=MK, username="zzhm1").values_list("action", flat=True)), str(list(SysAuditLog.objects.filter(entity=MK).values_list("action", "username"))[:6]))

        raise Rollback()
except Rollback:
    pass
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print()
print("FAILED: " + ", ".join(fails) if fails else "all checks passed")
sys.exit(1 if fails else 0)
