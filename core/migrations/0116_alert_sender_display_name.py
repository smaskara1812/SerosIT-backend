from django.db import migrations, models


def copy_names(apps, schema_editor):
    """Rows that already exist take the name the alert had in its legacy Display Name column, so nothing changes for them."""
    Sender = apps.get_model("core", "AlertSenderDtl")
    for row in Sender.objects.filter(display_name=""):
        name = (row.alert.alert_display_name or "").strip()
        if name:
            Sender.objects.filter(pk=row.pk).update(display_name=name[:125])


class Migration(migrations.Migration):
    dependencies = [("core", "0115_alert_sender_dtl_name")]

    operations = [
        migrations.AddField(model_name="alertsenderdtl", name="display_name", field=models.CharField(blank=True, default="", max_length=125)),
        migrations.RunPython(copy_names, migrations.RunPython.noop),
    ]
