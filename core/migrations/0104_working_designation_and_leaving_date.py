from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


def fix_data(apps, schema_editor):
    """Before the designation becomes a real link: any designation number a user carries that the new table does not have yet gets a stub row
    (a re-import of the legacy table replaces the names), so nothing is lost and the link can be added. Then a user's date of leaving moves
    into To (user_to) where To is empty."""
    User = apps.get_model("core", "MstUser")
    Designation = apps.get_model("core", "MstWorkingDesignation")
    have = set(Designation.objects.values_list("pk", flat=True))
    for did in sorted(set(User.objects.exclude(work_designation_id__isnull=True).values_list("work_designation_id", flat=True)) - have):
        Designation.objects.create(pk=did, working_designation=f"Designation {did}", working_designation_active="N", cr_user_id=0, cr_dt=timezone.now())
    for u in User.objects.filter(user_to__isnull=True, date_of_leaving__isnull=False):
        u.user_to = u.date_of_leaving
        u.save(update_fields=["user_to"])


class Migration(migrations.Migration):
    dependencies = [("core", "0103_employee_independence_step2")]

    operations = [
        migrations.CreateModel(
            name="MstWorkingDesignation",
            fields=[
                ("working_designation_id", models.AutoField(primary_key=True, serialize=False)),
                ("working_designation", models.CharField(max_length=40)),
                ("critical_flag", models.CharField(default="N", max_length=1)),
                ("usage_filter", models.CharField(blank=True, max_length=3, null=True)),
                ("working_designation_active", models.CharField(default="Y", max_length=1)),
                ("cr_user_id", models.IntegerField(default=0)),
                ("cr_dt", models.DateTimeField(blank=True, null=True)),
                ("mod_user_id", models.IntegerField(blank=True, null=True)),
                ("mod_dt", models.DateTimeField(blank=True, null=True)),
            ],
            options={"db_table": "mst_working_designation"},
        ),
        migrations.AlterField("mstuser", "work_designation_id", models.IntegerField(db_column="work_designation_id", null=True, blank=True)),
        migrations.RunPython(fix_data, migrations.RunPython.noop),
        migrations.RenameField("mstuser", "work_designation_id", "work_designation"),
        migrations.AlterField(
            "mstuser",
            "work_designation",
            models.ForeignKey(
                blank=True, db_column="work_designation_id", null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="users", to="core.mstworkingdesignation",
            ),
        ),
        migrations.RemoveField("mstuser", "date_of_leaving"),
    ]
