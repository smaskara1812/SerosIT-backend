from django.db import migrations, models

# (old entity_key, old action) -> (new entity_key, new action). Rows are rewritten in place, so a database that already has them converts itself.
RENAMES = [
    (("automation.birthday", "send"), ("automation", "send_birthday_mail")),
    (("automation.holiday", "send"), ("automation", "send_holiday_mail")),
]


def forwards(apps, schema_editor):
    T = apps.get_model("core", "NotificationTrigger")
    for (oe, oa), (ne, na) in RENAMES:
        T.objects.filter(entity_key=oe, action=oa).update(entity_key=ne, action=na)


def backwards(apps, schema_editor):
    T = apps.get_model("core", "NotificationTrigger")
    for (oe, oa), (ne, na) in RENAMES:
        T.objects.filter(entity_key=ne, action=na).update(entity_key=oe, action=oa)


class Migration(migrations.Migration):
    """Notification Triggers: one trigger point "Automation" with an action per automatic mail (send_birthday_mail, send_holiday_mail,
    send_haz_id_register_mail), instead of one trigger point per mail. The action column is widened to hold the longer names."""

    dependencies = [("core", "0116_alert_sender_display_name")]

    operations = [
        migrations.AlterField(model_name="notificationtrigger", name="action", field=models.CharField(max_length=40)),
        migrations.RunPython(forwards, backwards),
    ]
