from django.db import migrations


class Migration(migrations.Migration):
    """The sender table keeps its legacy name, like the other legacy copies (mail_alert_dtl for Mail_Alert_Dtl): table alert_sender_dtl, model
    AlertSenderDtl, key alert_sender_dtl_id."""

    dependencies = [("core", "0114_alert_sender")]

    operations = [
        migrations.RenameModel(old_name="AlertSender", new_name="AlertSenderDtl"),
        migrations.RenameField(model_name="alertsenderdtl", old_name="alert_sender_id", new_name="alert_sender_dtl_id"),
        migrations.AlterModelTable(name="alertsenderdtl", table="alert_sender_dtl"),
    ]
