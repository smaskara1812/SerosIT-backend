import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0017_alter_projectdrillingrate_drilling_rate"),
    ]

    operations = [
        migrations.CreateModel(
            name="MstRigType",
            fields=[
                ("rig_type_id", models.AutoField(primary_key=True, serialize=False)),
                ("rig_type_name", models.CharField(max_length=15)),
                ("cr_user_id", models.IntegerField()),
                ("cr_dt", models.DateTimeField()),
                ("mod_user_id", models.IntegerField(blank=True, null=True)),
                ("mod_dt", models.DateTimeField(blank=True, null=True)),
            ],
            options={"db_table": "mst_rig_type"},
        ),
        migrations.CreateModel(
            name="MstRigSubtype",
            fields=[
                ("rig_subtype_id", models.AutoField(primary_key=True, serialize=False)),
                ("rig_subtype_name", models.CharField(max_length=20)),
                ("cr_user_id", models.IntegerField()),
                ("cr_dt", models.DateTimeField()),
                ("mod_user_id", models.IntegerField(blank=True, null=True)),
                ("mod_dt", models.DateTimeField(blank=True, null=True)),
                (
                    "rig_type",
                    models.ForeignKey(
                        db_column="rig_type_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subtypes",
                        to="core.mstrigtype",
                    ),
                ),
            ],
            options={"db_table": "mst_rig_subtype"},
        ),
    ]
