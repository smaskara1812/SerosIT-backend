"""Checks that the list of notification trigger points and actions is the same everywhere it is written down:
  * the registry in core/notification_triggers.py (TRIGGER_POINTS) and the Notification Triggers form (frontend/src/config/mastersSchemas.js);
  * every row already in the notification_trigger table, and every trigger the code uses (the automatic mailers' ENTITY_KEY / ACTION, and every
    notification_triggers.trigger("x", "y", ...) call site);
  * the form's save check: an unknown trigger point or action is refused, a known pair is accepted.

    cd backend
    .venv/bin/python scripts/check_trigger_registry.py
"""
import os, re, sys, django
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.test import APIClient
from core import notification_triggers as nt
from core.models import MailAlertDtl, NotificationTrigger, UserPermission, UserProfile
from core.permissions import invalidate_user_access

fails = []


def ok(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {detail}" if not cond else ""))
    if not cond:
        fails.append(name)


schema = open(os.path.join(os.path.dirname(ROOT), "frontend", "src", "config", "mastersSchemas.js"), encoding="utf-8").read()
i = schema.index("'notification-triggers': {")
blk = schema[i: schema.index("\n  },\n", i)]
opts = blk[blk.index("options: ["): blk.index("required: true")]
form_points = dict(re.findall(r"value: '([^']+)', label: '([^']+)'", opts))
by = blk[blk.index("optionsByValue: {"):]
form_actions = {}
for m in re.finditer(r"(?:'([\w.]+)'|(\w+)): \[(.*?)\]", by, re.S):
    form_actions[m.group(1) or m.group(2)] = dict(re.findall(r"value: '([^']+)', label: '([^']+)'", m.group(3)))

print("A. the form and the registry say the same")
ok("same trigger points", set(form_points) == set(nt.TRIGGER_POINTS), f"form {sorted(form_points)} registry {sorted(nt.TRIGGER_POINTS)}")
ok("same labels for the trigger points", all(form_points.get(k) == v[0] for k, v in nt.TRIGGER_POINTS.items()))
ok("same actions for each trigger point", all(set(form_actions.get(k, {})) == set(v[1]) for k, v in nt.TRIGGER_POINTS.items()), str(form_actions))
ok("same labels for the actions", all(form_actions.get(k, {}).get(a) == lbl for k, v in nt.TRIGGER_POINTS.items() for a, lbl in v[1].items()))

print("B. everything in use is in the registry")
ok("every row in the table", all(nt.is_registered(e, a) for e, a in NotificationTrigger.objects.values_list("entity_key", "action")), str(list(NotificationTrigger.objects.values_list("entity_key", "action"))))
from core import birthday_mailer, holiday_mailer
mods = [birthday_mailer, holiday_mailer]
for name in ("haz_id_register", "rig_rate_breakup"):
    try:
        mods.append(__import__(f"core.{name}", fromlist=["x"]))
    except ImportError:
        pass
ok("the automatic mailers' own trigger and action", all(nt.is_registered(m.ENTITY_KEY, m.ACTION) for m in mods), str([(m.__name__, m.ENTITY_KEY, m.ACTION) for m in mods]))
calls = []
for f in os.listdir(os.path.join(ROOT, "core")):
    if f.endswith(".py") and f != "notification_triggers.py":
        calls += re.findall(r"notification_triggers\.trigger\(\s*[\"']([\w.]+)[\"']\s*,\s*[\"'](\w+)[\"']", open(os.path.join(ROOT, "core", f), encoding="utf-8").read())
ok("every notification_triggers.trigger(...) call site", all(nt.is_registered(e, a) for e, a in calls), str(calls))
ok("the Automation trigger point has the four mails", set(nt.TRIGGER_POINTS["automation"][1]) == {"send_birthday_mail", "send_holiday_mail", "send_haz_id_register_mail", "send_rig_rate_breakup_mail"})
ok("the column is wide enough for the longest action", NotificationTrigger._meta.get_field("action").max_length >= max(len(a) for v in nt.TRIGGER_POINTS.values() for a in v[1]))


class Rollback(Exception):
    pass


print("C. the save check")
try:
    with transaction.atomic():
        U = get_user_model(); u = U.objects.create_user(username="zztr1", password="x")
        uid = (UserProfile.objects.order_by("-user_id").first().user_id or 0) + 1
        UserProfile.objects.create(user_id=uid, user_login_id="zztr1", is_app_admin=False)
        UserPermission.objects.create(user_id=uid, menu_key="masters.notification_triggers", can_view=True, can_add=True, can_edit=True, can_delete=True, can_export=False)
        UserPermission.objects.create(user_id=uid, menu_key="masters.mail_alerts", can_view=True)
        invalidate_user_access("zztr1")
        c = APIClient(HTTP_HOST="localhost"); c.force_authenticate(u)
        a = MailAlertDtl.objects.filter(alert_id__gt=0).order_by("-alert_id").first()
        NotificationTrigger.objects.filter(entity_key="automation", action="send_haz_id_register_mail").delete()
        r = c.post("/api/masters/notification-triggers/", {"entity_key": "automation", "action": "send_haz_id_register_mail", "alert": a.pk, "notification_trigger_active": "Y"}, format="json")
        ok("a known pair is saved, with the words the form shows", r.status_code == 201 and r.json()["trigger_label"] == "Automation" and r.json()["action_label"] == "Send HAZ ID register mail", str(r.content[:200]))
        ok("an unknown trigger point is refused", c.post("/api/masters/notification-triggers/", {"entity_key": "automaton", "action": "send_haz_id_register_mail", "alert": a.pk}, format="json").status_code == 400)
        ok("an unknown action is refused (a typo would never fire)", c.post("/api/masters/notification-triggers/", {"entity_key": "automation", "action": "send_birthday", "alert": a.pk}, format="json").status_code == 400)
        ok("an action from another trigger point is refused", c.post("/api/masters/notification-triggers/", {"entity_key": "qhse.incident_details", "action": "send_holiday_mail", "alert": a.pk}, format="json").status_code == 400)
        ok("the same pair twice is refused (one alert per trigger)", c.post("/api/masters/notification-triggers/", {"entity_key": "automation", "action": "send_haz_id_register_mail", "alert": a.pk}, format="json").status_code == 400)
        raise Rollback()
except Rollback:
    pass

print()
print("FAILED: " + ", ".join(fails) if fails else "all checks passed")
sys.exit(1 if fails else 0)
