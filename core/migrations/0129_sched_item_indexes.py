# The Scheduled Mails and Report Mails pages count and list sched_item on every tab. On SQL Server the table is clustered on item_id, so a count
# that cannot use an index reads the error text and the recipient snapshot of every row. These indexes cover the tab counts, the Earlier ordering,
# one report's latest runs, the per-automation counts, and the overdue check.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0128_rig_to_email_mapping"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="scheditem",
            index=models.Index(fields=["send_date", "status"], name="sched_day_status"),
        ),
        migrations.AddIndex(
            model_name="scheditem",
            index=models.Index(fields=["-send_date", "-due_at", "-item_id"], name="sched_day_due"),
        ),
        migrations.AddIndex(
            model_name="scheditem",
            index=models.Index(fields=["job_key", "-send_date", "-item_id"], name="sched_job_day"),
        ),
        migrations.AddIndex(
            model_name="scheditem",
            index=models.Index(fields=["job_key", "status", "send_date"], name="sched_job_stat_day"),
        ),
        migrations.AddIndex(
            model_name="scheditem",
            index=models.Index(fields=["status", "due_at"], name="sched_status_due"),
        ),
    ]
