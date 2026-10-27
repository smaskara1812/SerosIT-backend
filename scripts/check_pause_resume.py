"""Checks what pausing an automation and resuming it later really does, so the confirmation dialogs on Scheduled Mails say the truth:
  * dates-based automations (Birthday, Holiday): while paused nothing is planned or sent; on resume, mails already planned for days that have passed show as
    Missed (not sent; they can be sent by hand), mails never planned for those days simply do not exist, today's mail goes out at the next run (late if its
    hour has passed), later days carry on; an event that spans several days loses only the days that went by.
  * cycle-based automations (the report mails): while paused Next Mail keeps its place; when it has passed, the report is sent ONCE on resume (not once per
    missed cycle) and Next Mail moves on; a Next Mail set in the future before resuming means nothing is sent on resume.
A fake mail server is used and everything in the database is rolled back.

    cd backend
    .venv/bin/python scripts/check_pause_resume.py
"""
import datetime, os, shutil, sys, tempfile, django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TMP = tempfile.mkdtemp(prefix="pause_resume_check_")
os.environ["LOG_DIR"] = os.path.join(TMP, "logs")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from django.conf import settings
from django.db import transaction
from PIL import Image
from core import birthday_mailer as bm, haz_id_register as hz, holiday_mailer as hm, mailer, scheduler
from core.models import BirthdayPerson, BirthdayTemplate, HolidayEvent, MailAlertDtl, NotificationTrigger, SchedItem, SchedJob

sent = []
mailer._deliver = lambda subject, html, text, to, cc, bcc, from_name, smtp, inline_images, attachments=None: sent.append({"subject": subject, "to": to})
settings.MEDIA_ROOT = os.path.join(TMP, "media")
os.makedirs(os.path.join(settings.MEDIA_ROOT, "birthday_templates")); os.makedirs(os.path.join(settings.MEDIA_ROOT, "holiday_images"))
settings.SCHEDULER_ERROR_MAIL_TO = []


class Rollback(Exception):
    pass


fails = []


def ok(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {detail}" if not cond else ""))
    if not cond:
        fails.append(name)


D, DT = datetime.date, datetime.datetime
DAY0 = D(2026, 11, 10)


def at(days, h=8, m=0, s=5):
    return DT.combine(DAY0 + datetime.timedelta(days=days), datetime.time(h, m, s))


def pause(key, on):
    SchedJob.objects.update_or_create(job_key=key, defaults={"enabled": "N" if on else "Y", "name": key})


def tick(when):
    return scheduler.tick(when, owner="check", source="manual")


def status_of(label):
    i = SchedItem.objects.filter(label=label).first()
    return i.status if i else None


try:
    with transaction.atomic():
        for m in (SchedItem, BirthdayPerson, BirthdayTemplate, HolidayEvent):
            m.objects.all().delete()
        NotificationTrigger.objects.filter(entity_key="automation").delete()
        bm.ensure_setup()  # birthday trigger -> alert 247
        alert = MailAlertDtl.objects.get(pk=247)
        NotificationTrigger.objects.create(entity_key=hm.ENTITY_KEY, action=hm.ACTION, alert=alert, notification_trigger_active="Y", cr_user_id=0, cr_dt=at(0))
        NotificationTrigger.objects.create(entity_key=hz.ENTITY_KEY, action=hz.ACTION, alert=alert, notification_trigger_active="Y", cr_user_id=0, cr_dt=at(0))
        MailAlertDtl.objects.filter(pk=247).update(start_time=7, alert_active="Y", alert_freq=15, next_mail_dt=at(1, 7, 0, 0))
        rel = "birthday_templates/t.png"
        Image.new("RGB", (1200, 800), (20, 70, 140)).save(os.path.join(settings.MEDIA_ROOT, rel))
        BirthdayTemplate.objects.create(name="t", file_path=rel, width=1200, height=800, box_x=0.1, box_y=0.6, box_w=0.8, box_h=0.2, font="poppins", color="#ffffff", size_max=90, size_min=30,
                                         align_h="center", align_v="middle", text_case="title", is_active="Y", cr_user_id=0, cr_dt=at(0))
        hrel = "holiday_images/h.png"
        Image.new("RGB", (1200, 600), (200, 80, 30)).save(os.path.join(settings.MEDIA_ROOT, hrel))

        def person(name, days):
            d = DAY0 + datetime.timedelta(days=days)
            return BirthdayPerson.objects.create(full_name=name, birth_month=d.month, birth_day=d.day, cr_user_id=0, cr_dt=at(0))
        for n, d in (("P1 day1", 1), ("P2 day2", 2), ("P3 day3", 3), ("P4 day5", 5)):
            person(n, d)
        HolidayEvent.objects.create(name="Festival", subject="Happy", send_on=DAY0 + datetime.timedelta(days=1), send_days=5, repeat_yearly="N", file_path=hrel, width=1200, height=600, cr_user_id=0, cr_dt=at(0))

        print("A. before the pause")
        tick(at(0))
        ok("the next 7 days are planned: four birthdays and the five days of the festival", SchedItem.objects.filter(job_key="birthday").count() == 4 and SchedItem.objects.filter(job_key="holiday").count() == 5)
        ok("the report mail is not planned yet (its date is a day away: it is, within 7 days)", SchedItem.objects.filter(job_key="haz_id_register", status="planned").count() == 1)

        print("B. paused: three days pass")
        for key in ("birthday", "holiday", "haz_id_register"):
            pause(key, True)
        sent.clear()
        person("P6 never planned", 2)  # added during the pause for a day that passes during it
        r = tick(at(3, 8))
        ok("a paused automation is skipped by the run and sends nothing", all(r["jobs"][k].get("paused") for k in ("birthday", "holiday", "haz_id_register")) and not sent)
        ok("what was planned stays planned (nothing is marked missed while paused)", SchedItem.objects.filter(job_key="birthday", status="planned").count() == 4 and SchedItem.objects.filter(job_key="holiday", status="planned").count() == 5)

        print("C. resumed on day 3 at 08:00")
        for key in ("birthday", "holiday"):
            pause(key, False)
        r = tick(at(3, 8))
        ok("the birthdays of days 1 and 2 are Missed: not sent, and they can be sent by hand", status_of("P1 day1") == "missed" and status_of("P2 day2") == "missed")
        ok("a birthday added during the pause for a day that went by has no item at all", status_of("P6 never planned") is None)
        ok("the birthday of the day it is resumed goes out at once (its 07:00 has passed, so it is late)", status_of("P3 day3") == "sent" and len(sent) >= 1)
        ok("a later birthday carries on as planned", status_of("P4 day5") == "planned")
        hol = {i.send_date: i.status for i in SchedItem.objects.filter(job_key="holiday")}
        ok("the festival that spans five days loses only the days that went by: days 1 and 2 Missed, day 3 sent, days 4 and 5 still to come",
           hol[DAY0 + datetime.timedelta(days=1)] == "missed" and hol[DAY0 + datetime.timedelta(days=2)] == "missed" and hol[DAY0 + datetime.timedelta(days=3)] == "sent"
           and hol[DAY0 + datetime.timedelta(days=4)] == "planned" and hol[DAY0 + datetime.timedelta(days=5)] == "planned", str(hol))
        n = len(sent)
        tick(at(3, 9))
        ok("nothing is sent twice by the next run", len(sent) == n)
        item = SchedItem.objects.get(label="P1 day1")
        ok("a Missed mail can still be sent by hand", scheduler.send_now(item.pk, "tester", at(3, 9))[0] is True and status_of("P1 day1") == "sent")

        print("D. a report mail (cycle): Next Mail passed during the pause")
        pause("haz_id_register", True)
        MailAlertDtl.objects.filter(pk=247).update(next_mail_dt=at(1, 17, 0, 0), alert_freq=15, start_time=7)
        SchedItem.objects.filter(job_key="haz_id_register").delete()
        sent.clear()
        tick(at(4, 8))
        ok("still paused: nothing is planned or sent for the report, and Next Mail keeps its place", not SchedItem.objects.filter(job_key="haz_id_register").exists() and MailAlertDtl.objects.get(pk=247).next_mail_dt == at(1, 17, 0, 0))
        pause("haz_id_register", False)
        MailAlertDtl.objects.filter(pk=247).update(start_time=17)
        tick(at(4, 18))
        items = SchedItem.objects.filter(job_key="haz_id_register")
        ok("on resume the report is sent ONCE (a catch-up), not once for each cycle that went by", items.filter(status="sent").count() == 1 and items.count() == 1, str(list(items.values_list("label", "status"))))
        ok("Next Mail moves to the next date of its cycle after today (day 1 + 15 days)", MailAlertDtl.objects.get(pk=247).next_mail_dt == at(16, 17, 0, 0), str(MailAlertDtl.objects.get(pk=247).next_mail_dt))

        print("E. the same, with Next Mail changed before resuming")
        pause("haz_id_register", True)
        SchedItem.objects.filter(job_key="haz_id_register").delete()
        MailAlertDtl.objects.filter(pk=247).update(next_mail_dt=at(1, 17, 0, 0))
        MailAlertDtl.objects.filter(pk=247).update(next_mail_dt=at(20, 17, 0, 0))  # what Report Mails > Change does
        pause("haz_id_register", False)
        sent.clear()
        tick(at(5, 18))
        ok("nothing is sent on resume, the report waits for its new date", not SchedItem.objects.filter(job_key="haz_id_register", status="sent").exists() and not SchedItem.objects.filter(job_key="haz_id_register").exists())
        raise Rollback()
except Rollback:
    pass
finally:
    shutil.rmtree(TMP, ignore_errors=True)

print()
print("FAILED: " + ", ".join(fails) if fails else "all checks passed")
sys.exit(1 if fails else 0)
