from django.db import migrations, models
import django.db.models.deletion


def days_to_moves(apps, schema_editor):
    """Each plan row that had ILM days becomes one planned ILM move of days x 24 hours."""
    Plan, Move = apps.get_model("core", "RigMonthPlan"), apps.get_model("core", "RigPlannedMove")
    for p in Plan.objects.filter(ilm_days__gt=0):
        Move.objects.create(plan=p, move_rate_id=6, planned_hours=p.ilm_days * 24, note="from the ILM days entered before")


class Migration(migrations.Migration):
    dependencies = [("core", "0126_drilling_rate_class")]
    operations = [
        migrations.CreateModel(
            name="RigPlannedMove",
            fields=[
                ("move_id", models.AutoField(primary_key=True, serialize=False)),
                ("plan", models.ForeignKey(db_column="plan_id", on_delete=django.db.models.deletion.CASCADE, related_name="planned_moves", to="core.rigmonthplan")),
                ("move_rate_id", models.IntegerField()),
                ("planned_hours", models.DecimalField(decimal_places=2, max_digits=7)),
                ("planned_km", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ("note", models.CharField(blank=True, default="", max_length=200)),
            ],
            options={"db_table": "rig_planned_move", "ordering": ["move_id"]},
        ),
        migrations.RunPython(days_to_moves, migrations.RunPython.noop),
        migrations.RemoveField(model_name="rigmonthplan", name="ilm_days"),
    ]
