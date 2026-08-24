import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0019_alter_mstrig_rig_type_rig_subtype"),
    ]

    operations = [
        migrations.CreateModel(
            name="MstContinent",
            fields=[
                ("continent_id", models.AutoField(primary_key=True, serialize=False)),
                ("continent_name", models.CharField(max_length=15)),
                ("cr_user_id", models.IntegerField()),
                ("cr_dt", models.DateTimeField()),
                ("mod_user_id", models.IntegerField(blank=True, null=True)),
                ("mod_dt", models.DateTimeField(blank=True, null=True)),
            ],
            options={"db_table": "mst_continent"},
        ),
        migrations.CreateModel(
            name="MstCountry",
            fields=[
                ("country_id", models.AutoField(primary_key=True, serialize=False)),
                ("country_name", models.CharField(max_length=40)),
                ("country_known_name", models.CharField(max_length=25)),
                ("country_iso_cd", models.CharField(max_length=2)),
                ("country_active", models.CharField(default="Y", max_length=1)),
                ("cr_user_id", models.IntegerField()),
                ("cr_dt", models.DateTimeField()),
                ("mod_user_id", models.IntegerField(blank=True, null=True)),
                ("mod_dt", models.DateTimeField(blank=True, null=True)),
                (
                    "continent",
                    models.ForeignKey(
                        blank=True,
                        db_column="continent_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="countries",
                        to="core.mstcontinent",
                    ),
                ),
            ],
            options={"db_table": "mst_country"},
        ),
        migrations.CreateModel(
            name="MstCountryState",
            fields=[
                ("country_state_id", models.AutoField(primary_key=True, serialize=False)),
                ("country_state_name", models.CharField(max_length=25)),
                ("country_state_abrv", models.CharField(max_length=2)),
                ("country_state_active", models.CharField(default="Y", max_length=1)),
                ("cr_user_id", models.IntegerField()),
                ("cr_dt", models.DateTimeField()),
                ("mod_user_id", models.IntegerField(blank=True, null=True)),
                ("mod_dt", models.DateTimeField(blank=True, null=True)),
                (
                    "country",
                    models.ForeignKey(
                        db_column="country_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="states",
                        to="core.mstcountry",
                    ),
                ),
            ],
            options={"db_table": "mst_country_state"},
        ),
        migrations.CreateModel(
            name="MstVesselDept",
            fields=[
                ("vessel_dept_id", models.AutoField(primary_key=True, serialize=False)),
                ("vessel_dept_name", models.CharField(max_length=25)),
                ("vessel_dept_order", models.IntegerField(default=0)),
                ("cr_user_id", models.IntegerField()),
                ("cr_dt", models.DateTimeField()),
                ("mod_user_id", models.IntegerField(blank=True, null=True)),
                ("mod_dt", models.DateTimeField(blank=True, null=True)),
            ],
            options={"db_table": "mst_vessel_dept"},
        ),
    ]
