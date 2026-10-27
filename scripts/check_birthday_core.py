"""Checks the Birthday Mailer's core with real code and a fake mail server: who has a birthday (29 February, the leaving date), the picture the
name is drawn on, the recipients read from the trigger and the alert, planning, sending, rotation of templates, failover from the designated to
the default account, retries, missed mails, skip / resend, pausing, and the lock that stops two copies. Pictures go to a temporary folder, log
files to another, and everything in the database is rolled back.

    cd backend
    .venv/bin/python scripts/check_birthday_core.py
"""
import datetime, io, os, shutil, sys, tempfile, django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TMP = tempfile.mkdtemp(prefix="birthday_core_check_")
os.environ["LOG_DIR"] = os.path.join(TMP, "logs")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from django.conf import settings
from django.db import transaction
from PIL import Image
from core import birthday_mailer as bm, mailer, scheduler
from core.models import AlertSenderDtl, BirthdayPerson, BirthdayTemplate, EmailLog, MailAlertDtl, MailAlertToUser, NotificationTrigger, SchedHeartbeat, SchedItem, SchedJob

settings.MEDIA_ROOT = os.path.join(TMP, "media")
os.makedirs(os.path.join(settings.MEDIA_ROOT, "birthday_templates"))


class Rollback(Exception):
    pass


fails = []


def ok(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {detail}" if not cond else ""))
    if not cond:
        fails.append(name)


D = datetime.date
NOW = datetime.datetime(2026, 3, 10, 7, 0, 5)  # a Tuesday, five seconds past 07:00


def person(full, m, d, display=None, leaving=None, year=None):
    return BirthdayPerson.objects.create(full_name=full, display_name=display, birth_month=m, birth_day=d, birth_year=year, leaving_date=leaving, cr_user_id=0, cr_dt=NOW)


def make_template(name, w=1200, h=800, **kw):
    rel = f"birthday_templates/{name}.png"
    Image.new("RGB", (w, h), (20, 70, 140)).save(os.path.join(settings.MEDIA_ROOT, rel))
    base = dict(name=name, file_path=rel, width=w, height=h, box_x=0.1, box_y=0.6, box_w=0.8, box_h=0.2, font="poppins", color="#ffffff", size_max=90, size_min=30,
                align_h="center", align_v="middle", text_case="title", is_active="Y", cr_user_id=0, cr_dt=NOW)
    base.update(kw)
    return BirthdayTemplate.objects.create(**base)


sent = []        # what the fake mail server received
fail_hosts = set()  # hosts that refuse mail


def fake_deliver(subject, html, text, to, cc, bcc, from_name, smtp, inline_images):
    if smtp["host"] in fail_hosts:
        raise ConnectionError(f"{smtp['host']} refused the connection")
    sent.append({"subject": subject, "to": to, "cc": cc, "bcc": bcc, "from_name": from_name, "host": smtp["host"], "images": inline_images, "html": html})


mailer._deliver = fake_deliver
settings.BIRTHDAY_EMAIL_HOST = ""

try:
    with transaction.atomic():
        # the checks must not depend on real data: inside this rolled-back transaction the lists start empty
        for m in (SchedItem, BirthdayTemplate, BirthdayPerson, AlertSenderDtl):
            m.objects.all().delete()
        print("A. who has a birthday")
        leap = person("Leap Lara", 2, 29)
        ok("29 February is kept on 28 February in a year with no 29th", bm.birthday_on(leap, 2027) == D(2027, 2, 28) and bm.birthday_on(leap, 2028) == D(2028, 2, 29))
        ok("she is found on 28 Feb 2027 and not on 1 Mar", leap in bm.people_with_birthday(D(2027, 2, 28)) and leap not in bm.people_with_birthday(D(2027, 3, 1)))
        ok("and on 29 Feb 2028 but not on 28 Feb 2028", leap in bm.people_with_birthday(D(2028, 2, 29)) and leap not in bm.people_with_birthday(D(2028, 2, 28)))
        gone = person("Leaving Leo", 3, 10, leaving=D(2026, 3, 9))
        last = person("Last Day Lena", 3, 10, leaving=D(2026, 3, 10))
        ok("someone who left yesterday is not active", not bm.is_active_on(gone, D(2026, 3, 10)))
        ok("the leaving date is the last day (still active on it)", bm.is_active_on(last, D(2026, 3, 10)))
        BirthdayPerson.objects.filter(pk__in=[leap.pk, gone.pk, last.pk]).delete()
        a = person("Priya Sharma", 3, 10); b = person("Priya Sharma", 3, 10)
        ok("there is no uniqueness rule: two identical rows are two people", BirthdayPerson.objects.filter(full_name="Priya Sharma").count() == 2)
        ok("display name is used when given, else the full name", person("Venkata Rao", 7, 1, display="Venky").shown_name == "Venky" and a.shown_name == "Priya Sharma")
        BirthdayPerson.objects.all().delete()

        print("B. the picture")
        t = make_template("fitcheck")
        png, meta = bm.render_card(t, "Raj")
        im = Image.open(io.BytesIO(png))
        ok("the card is sent at 900 px wide, in proportion", im.size == (900, 600) and meta["width"] == 900, str(im.size))
        ok("a short name takes the biggest size", meta["size"] == 90 and meta["lines"] == ["Raj"])
        _, m2 = bm.render_card(t, "Priya Sharma"); _, m3 = bm.render_card(t, "Venkata Subrahmanyam Chandrasekharan Iyer")
        ok("a longer name is shrunk to fit", m2["size"] <= 90 and m3["size"] < m2["size"] or m3["lines"] != m3["lines"][:1], str((m2["size"], m3["size"], m3["lines"])))
        ok("a long name is wrapped onto two lines at a bigger size when the box is tall enough, rather than squeezed small on one line", len(m3["lines"]) == 2 and not m3["truncated"] and m3["size"] >= 50, str(m3))
        narrow = make_template("narrow", box_x=0.3, box_w=0.4)
        _, m5 = bm.render_card(narrow, "Venkata Subrahmanyam Chandrasekharan Iyer")
        ok("in a narrow box a long name goes onto several lines instead of being cut", len(m5["lines"]) >= 3 and not m5["truncated"] and all(l for l in m5["lines"]), str(m5))
        narrow.delete()
        tiny = make_template("tiny", box_x=0.45, box_w=0.1, box_y=0.5, box_h=0.1)
        _, m4 = bm.render_card(tiny, "A" * 59)
        ok("a name that cannot fit even at half the smallest size is cut with an ellipsis and flagged", m4["truncated"] and m4["lines"][-1].endswith("…"), str(m4))
        tiny.delete()
        tall = make_template("tall", box_x=0.35, box_w=0.3, box_y=0.4, box_h=0.4, size_min=28)
        _, m6 = bm.render_card(tall, "Venkata Subrahmanyam Chandrasekharan Iyer")
        ok("in a narrow, tall box a long name wraps onto as many lines as it needs, and is not cut", len(m6["lines"]) >= 3 and not m6["truncated"], str(m6))
        _, m7 = bm.render_card(tall, "Pushpak Khandelwal")
        ok("a usual name in the same box goes on two lines at a bigger size than the long one", len(m7["lines"]) == 2 and m7["size"] > m6["size"], str((m6["size"], m7["size"], m7["lines"])))
        thin = make_template("thin", box_x=0.4, box_w=0.2, box_y=0.5, box_h=0.12, size_min=40)
        _, m8 = bm.render_card(thin, "Venkata Subrahmanyam")
        ok("a name wider than the box at the smallest size is made smaller, not cut", m8["size"] < 40 and m8["below_min"] and not m8["truncated"], str(m8))
        for tt in (tall, thin):
            tt.delete()
        ok("capitals: title case, upper case and as typed", bm.display_text("priya  sharma", "title") == "Priya Sharma" and bm.display_text("priya", "upper") == "PRIYA" and bm.display_text("pRiya", "asis") == "pRiya")
        left = make_template("left", align_h="left", box_x=0.1, box_w=0.5); right = make_template("right", align_h="right", box_x=0.1, box_w=0.5)
        def ink_x(template):
            im = Image.open(io.BytesIO(bm.render_card(template, "Raj")[0])).convert("RGB")
            xs = [x for x in range(im.size[0]) for y in range(int(im.size[1] * 0.6), int(im.size[1] * 0.8)) if im.getpixel((x, y))[0] > 200]
            return min(xs), max(xs)
        lx, rx = ink_x(left), ink_x(right)
        ok("left and right alignment put the name at opposite ends of the box", lx[0] < 150 and rx[1] > 400 and lx[1] < rx[1], f"{lx} {rx}")
        ok("all three bundled fonts load", all(os.path.isfile(os.path.join(bm.FONT_DIR, f)) and bm._font(k, 40) for k, (_, f) in bm.FONTS.items()))
        for tt in (left, right):
            tt.delete()

        print("C. the setup is read from the trigger and the alert")
        did = bm.ensure_setup()
        trig = NotificationTrigger.objects.get(entity_key=bm.ENTITY_KEY, action=bm.ACTION)
        alert = trig.alert
        ok("the trigger row points at alert 247", alert.alert_id == 247)
        ok("the alert's subject carries the {name} marker", "{name}" in MailAlertDtl.objects.get(pk=247).mail_subject)
        setup = bm.get_setup(NOW.date())
        ok("the setup shows the alert and the send hour, and no name when the alert has no sender (only the From address is shown)", setup["alert"]["id"] == 247 and setup["from_name"] == "" and setup["send_hour"] == 7)
        snd = AlertSenderDtl.objects.create(alert=alert, mail_host="named.example.test", mail_port=25, mail_security="N", from_address="hr@example.test", display_name="Human Resource – Seros", is_active="Y", cr_user_id=0, cr_dt=NOW)
        ok("the sender name comes from the alert's sender account", bm.get_setup(NOW.date())["from_name"] == "Human Resource – Seros" and mailer.sender_info(247)["display_name"] == "Human Resource – Seros")
        snd.delete()  # the rest of the checks use the default account, as they always did
        ok("recipients are the alert's active To, Cc and Bcc rows", setup["recipients"] == __import__("core.notification_triggers", fromlist=["x"]).resolve_alert_recipients(247, as_of=NOW.date()) and any(setup["recipients"].values()), str(setup["recipients"]))
        MailAlertToUser.objects.create(alert=alert, recipient_name="Cc Person", email_addr="zz-cc@example.com", addressee_type="C", mail_alert_from=D(2026, 1, 1), mail_alert_to=None, mail_alert_order=9, cr_user_id=0, cr_dt=NOW)
        MailAlertToUser.objects.create(alert=alert, recipient_name="Old Person", email_addr="zz-old@example.com", addressee_type="T", mail_alert_from=D(2025, 1, 1), mail_alert_to=D(2026, 1, 1), mail_alert_order=9, cr_user_id=0, cr_dt=NOW)
        r = bm.get_setup(NOW.date())["recipients"]
        ok("a Cc row added to the alert is picked up, and an ended row is left out", "zz-cc@example.com" in r["cc"] and "zz-old@example.com" not in r["to"])
        NotificationTrigger.objects.filter(pk=trig.pk).update(notification_trigger_active="N")
        ok("switching the trigger off shows a warning", any("switched off" in w for w in bm.get_setup(NOW.date())["warnings"]))
        NotificationTrigger.objects.filter(pk=trig.pk).update(notification_trigger_active="Y")

        print("D. planning the next 7 days")
        t1, t2 = make_template("card_one"), make_template("card_two")
        p1 = person("Priya Sharma", 3, 10); p2 = person("Raj Kumar", 3, 10); p3 = person("Anita Rao", 3, 14); p4 = person("Far Away", 3, 20)
        res = bm.JOB.plan(NOW)
        items = SchedItem.objects.filter(job_key="birthday")
        ok("a mail is planned for each birthday in the next 7 days (not beyond)", items.count() == 3 and not items.filter(label="Far Away").exists(), str(list(items.values_list("label", flat=True))))
        ok("two people with the same birthday are two separate items", items.filter(send_date=D(2026, 3, 10)).count() == 2)
        ok("each is due at the alert's hour", all(i.due_at.hour == 7 and i.due_at.minute == 0 for i in items))
        bm.JOB.plan(NOW)
        ok("planning again adds nothing (never planned twice)", SchedItem.objects.filter(job_key="birthday").count() == 3)
        p3.leaving_date = D(2026, 3, 12); p3.save(); bm.JOB.plan(NOW)
        ok("someone who leaves before the day is cancelled", SchedItem.objects.get(label="Anita Rao").status == "cancelled")
        p2.display_name = "Raj"; p2.save(); bm.JOB.plan(NOW)
        ok("a changed display name updates the planned item", SchedItem.objects.filter(label="Raj", send_date=D(2026, 3, 10)).exists())

        print("E. sending")
        before = bm.JOB.process(datetime.datetime(2026, 3, 10, 6, 59, 0))
        ok("nothing goes out before the hour", not sent and before["sent"] == 0)
        res = bm.JOB.process(NOW)
        ok("both birthdays go out at 07:00, as two separate mails", res["sent"] == 2 and len(sent) == 2, str((res, len(sent))))
        m = sent[0]
        ok("each goes to the alert's To, Cc and Bcc", m["to"] == setup["recipients"]["to"] and "zz-cc@example.com" in m["cc"] and m["bcc"] == setup["recipients"]["bcc"], str(m))
        ok("the celebrant is not a recipient", all("priya" not in a.lower() and "raj" not in a.lower() for s in sent for a in s["to"] + s["cc"] + s["bcc"]))
        pat = setup["subject"]  # the alert's own subject (an administrator may have added words around {name}); {name} becomes the person's name
        ok("the subject is the alert's subject with the name in it", "{name}" in pat and {s["subject"] for s in sent} == {pat.replace("{name}", "Priya Sharma"), pat.replace("{name}", "Raj")}, str([s["subject"] for s in sent]))
        ok("the mail carries the sender name that was set up (none here: no sender account)", m["from_name"] == setup["from_name"] == "")
        ok("the card is sent inline as a PNG", m["images"][0][0] == "birthday" and m["images"][0][2] == "png" and m["images"][0][1][:4] == b"\x89PNG" and 'cid:birthday' in m["html"])
        ok("the two cards use different templates (they take turns)", len({i.template_id for i in SchedItem.objects.filter(send_date=NOW.date(), status="sent")}) == 2)
        ok("both are in the Email Log, tagged auto.birthday", EmailLog.objects.filter(trigger_code="auto.birthday", success=True).count() == 2)
        ok("the items are marked sent with the log id and the account used", all(i.status == "sent" and i.email_log_id and i.smtp_used == "default" and i.attempts == 1 for i in SchedItem.objects.filter(send_date=NOW.date())))
        n_before = len(sent); bm.JOB.process(NOW + datetime.timedelta(hours=1))
        ok("the next hour sends nothing again", len(sent) == n_before)
        MailAlertDtl.objects.filter(pk=247).update(alert_active=None)
        err_off, res_off, _t = bm.JOB._compose_and_send(p1, NOW)
        ok("an alert that is not ticked Active sends nothing, and says why", res_off is None and "switched off" in err_off and "Alert Details" in err_off and len(sent) == n_before, err_off)
        MailAlertDtl.objects.filter(pk=247).update(alert_active="Y")
        SchedItem.objects.filter(send_date=NOW.date()).delete(); sent.clear()

        print("F. the designated account, then the default; retries")
        settings.BIRTHDAY_EMAIL_HOST = "smtp.designated.test"
        bm.JOB.plan(NOW); SchedItem.objects.exclude(send_date=NOW.date()).delete()
        fail_hosts.add("smtp.designated.test")
        res = bm.JOB.process(NOW)
        ok("when the designated account fails, the default is used straight away", res["sent"] == 2 and all(s["host"] == settings.EMAIL_HOST for s in sent), str([s["host"] for s in sent]))
        ok("the item records that the default account was used", all(i.smtp_used == "default" for i in SchedItem.objects.filter(send_date=NOW.date())))
        ok("the Email Log marks the fallback", EmailLog.objects.filter(trigger_code="auto.birthday", used_fallback=True, success=True).count() == 2)
        SchedItem.objects.filter(send_date=NOW.date()).delete(); sent.clear(); EmailLog.objects.all().delete()
        bm.JOB.plan(NOW); SchedItem.objects.exclude(send_date=NOW.date()).delete()
        fail_hosts.add(settings.EMAIL_HOST)
        res = bm.JOB.process(NOW)
        ok("when both fail the mail is marked failed with the reason", res["failed"] == 2 and all(i.status == "failed" and i.attempts == 1 and "refused" in i.last_error for i in SchedItem.objects.filter(send_date=NOW.date())), str(list(SchedItem.objects.values_list("status", "last_error"))))
        ok("each failure is in the Email Log with the error", EmailLog.objects.filter(trigger_code="auto.birthday", success=False).count() == 2)
        res = bm.JOB.process(NOW + datetime.timedelta(minutes=30))
        ok("it is not retried within the same hour", res["failed"] == 0 and SchedItem.objects.filter(attempts=1).count() == 2)
        res = bm.JOB.process(NOW + datetime.timedelta(hours=1))
        ok("the next hour is the first retry", res["retried"] == 2 and SchedItem.objects.filter(attempts=2, status="failed").count() == 2)
        res = bm.JOB.process(NOW + datetime.timedelta(hours=2))
        ok("the hour after is the second retry (the third try in all)", res["retried"] == 2 and SchedItem.objects.filter(attempts=3, status="failed").count() == 2)
        res = bm.JOB.process(NOW + datetime.timedelta(hours=3))
        ok("then it stops: at most 2 retries", res["retried"] == 0 and SchedItem.objects.filter(attempts=3).count() == 2)
        fail_hosts.discard(settings.EMAIL_HOST)
        res = bm.JOB.process(NOW + datetime.timedelta(hours=4))
        ok("a mail that gave up stays failed until someone resends it", res["sent"] == 0)
        ok("send now works on a failed mail", scheduler.send_now(SchedItem.objects.filter(status="failed").first().pk, "tester", NOW + datetime.timedelta(hours=4))[0] is True)
        fail_hosts.discard("smtp.designated.test")
        SchedItem.objects.filter(send_date=NOW.date()).delete(); sent.clear()

        print("G. missed, skip, send now, resend, pause")
        bm.JOB.plan(NOW); SchedItem.objects.exclude(send_date=NOW.date()).delete()
        res = bm.JOB.process(NOW + datetime.timedelta(days=1, hours=1))
        ok("a mail whose day passed unsent is Missed, not sent late next day", res["missed"] == 2 and not sent and SchedItem.objects.filter(status="missed").count() == 2)
        SchedItem.objects.all().delete()
        bm.JOB.plan(NOW); SchedItem.objects.exclude(send_date=NOW.date()).delete()
        one, two = list(SchedItem.objects.filter(send_date=NOW.date()))
        scheduler.skip_item(one.pk, "tester", NOW)
        res = bm.JOB.process(NOW)
        ok("a skipped mail is not sent, the other is", res["sent"] == 1 and SchedItem.objects.get(pk=one.pk).status == "skipped" and SchedItem.objects.get(pk=two.pk).status == "sent")
        scheduler.unskip_item(one.pk, "tester", NOW)
        ok("un-skip puts it back to planned", SchedItem.objects.get(pk=one.pk).status == "planned")
        res = bm.JOB.process(NOW + datetime.timedelta(hours=1))
        ok("and it goes out at the next run", SchedItem.objects.get(pk=one.pk).status == "sent")
        n = len(sent); okr, err = scheduler.resend(two.pk, "tester", NOW + datetime.timedelta(hours=2))
        ok("resend sends a new mail, keeps the item sent and counts it", okr and len(sent) == n + 1 and SchedItem.objects.get(pk=two.pk).resend_count == 1 and SchedItem.objects.get(pk=two.pk).status == "sent")
        ok("resend makes a new Email Log row", EmailLog.objects.filter(trigger_code="auto.birthday", success=True).count() >= 3)
        try:
            scheduler.skip_item(two.pk, "tester"); ok("a sent mail cannot be skipped", False)
        except scheduler.ActionError:
            ok("a sent mail cannot be skipped", True)
        SchedItem.objects.all().delete(); sent.clear()
        SchedJob.objects.filter(job_key="birthday").update(enabled="N")
        out = scheduler.tick(NOW, owner="check-a")
        ok("a paused job plans and sends nothing", out["jobs"]["birthday"].get("paused") and not SchedItem.objects.exists() and not sent)
        SchedJob.objects.filter(job_key="birthday").update(enabled="Y")

        print("H. the whole hourly run and the lock")
        out = scheduler.tick(NOW, owner="check-a")
        ok("a tick plans and sends in one go", out["ran"] and out["jobs"]["birthday"]["sent"] == 2 and not out["errors"], str(out))
        hb = SchedHeartbeat.objects.get(pk=1)
        ok("it records the heartbeat", hb.last_tick_at == NOW and hb.last_tick_ok and hb.last_message == "OK" and hb.locked_by == "")
        SchedHeartbeat.objects.filter(pk=1).update(locked_by="other-copy", locked_until=NOW + datetime.timedelta(minutes=30))
        ok("a second copy cannot run while the first holds the lock", scheduler.tick(NOW, owner="check-b")["ran"] is False)
        SchedHeartbeat.objects.filter(pk=1).update(locked_until=NOW - datetime.timedelta(minutes=1))
        ok("a lock left behind by a dead copy expires", scheduler.tick(NOW, owner="check-b")["ran"] is True)
        raise Rollback()
except Rollback:
    pass
finally:
    log_files = sorted(os.listdir(os.environ["LOG_DIR"])) if os.path.isdir(os.environ["LOG_DIR"]) else []
    err_txt = "".join(open(os.path.join(os.environ["LOG_DIR"], f), encoding="utf-8").read() for f in log_files if f.startswith("automation_errors"))
    ok("errors went to the automation_errors log with the reason", "refused the connection" in err_txt, str(log_files))
    ok("the scheduler log shows the hourly runs", any(f.startswith("scheduler") for f in log_files))
    ok("no password or key is in the logs", "password" not in err_txt.lower().replace("passwords", ""))
    shutil.rmtree(TMP, ignore_errors=True)

print()
print("FAILED: " + ", ".join(fails) if fails else "all checks passed")
sys.exit(1 if fails else 0)
