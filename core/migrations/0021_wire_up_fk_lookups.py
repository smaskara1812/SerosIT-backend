import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Converts a batch of raw *_id IntegerFields (Location, Country,
    Country State, Vessel Dept, Employee references) into real ForeignKeys,
    now that their target tables exist and are populated (see
    import_country_vesseldept_lookups.sql, run between 0020 and this
    migration). Every underlying column keeps its name/type — only a DB FK
    constraint is added — so this is state-only at the Django level."""

    dependencies = [
        ("core", "0020_new_lookup_tables"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                # mst_location.country_id / country_state_id
                migrations.RemoveField(model_name="mstlocation", name="country_id"),
                migrations.RemoveField(model_name="mstlocation", name="country_state_id"),
                migrations.AddField(
                    model_name="mstlocation",
                    name="country",
                    field=models.ForeignKey(
                        db_column="country_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="locations",
                        to="core.mstcountry",
                        default=1,
                    ),
                    preserve_default=False,
                ),
                migrations.AddField(
                    model_name="mstlocation",
                    name="country_state",
                    field=models.ForeignKey(
                        blank=True,
                        db_column="country_state_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="locations",
                        to="core.mstcountrystate",
                    ),
                ),
                # mst_operator.location_id / country_id
                migrations.RemoveField(model_name="mstoperator", name="location_id"),
                migrations.RemoveField(model_name="mstoperator", name="country_id"),
                migrations.AddField(
                    model_name="mstoperator",
                    name="location",
                    field=models.ForeignKey(
                        blank=True,
                        db_column="location_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="operators",
                        to="core.mstlocation",
                    ),
                ),
                migrations.AddField(
                    model_name="mstoperator",
                    name="country",
                    field=models.ForeignKey(
                        blank=True,
                        db_column="country_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="operators",
                        to="core.mstcountry",
                    ),
                ),
                # mst_cert_institute.location_id
                migrations.RemoveField(model_name="mstcertinstitute", name="location_id"),
                migrations.AddField(
                    model_name="mstcertinstitute",
                    name="location",
                    field=models.ForeignKey(
                        db_column="location_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="cert_institutes",
                        to="core.mstlocation",
                        default=1,
                    ),
                    preserve_default=False,
                ),
                # mst_cost_centre.fs_emp_id / location_id
                migrations.RemoveField(model_name="mstcostcentre", name="fs_emp_id"),
                migrations.RemoveField(model_name="mstcostcentre", name="location_id"),
                migrations.AddField(
                    model_name="mstcostcentre",
                    name="fs_emp",
                    field=models.ForeignKey(
                        blank=True,
                        db_column="fs_emp_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="cost_centres",
                        to="core.mstemployee",
                    ),
                ),
                migrations.AddField(
                    model_name="mstcostcentre",
                    name="location",
                    field=models.ForeignKey(
                        blank=True,
                        db_column="location_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="cost_centres",
                        to="core.mstlocation",
                    ),
                ),
                # mst_rank.vessel_dept_id
                migrations.RemoveField(model_name="mstrank", name="vessel_dept_id"),
                migrations.AddField(
                    model_name="mstrank",
                    name="vessel_dept",
                    field=models.ForeignKey(
                        db_column="vessel_dept_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="ranks",
                        to="core.mstvesseldept",
                        default=1,
                    ),
                    preserve_default=False,
                ),
                # mst_user.emp_id
                migrations.RemoveField(model_name="mstuser", name="emp_id"),
                migrations.AddField(
                    model_name="mstuser",
                    name="emp",
                    field=models.ForeignKey(
                        blank=True,
                        db_column="emp_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="users",
                        to="core.mstemployee",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE mst_location ADD CONSTRAINT fk_mst_location_country FOREIGN KEY (country_id) REFERENCES mst_country (country_id)",
                    reverse_sql="ALTER TABLE mst_location DROP FOREIGN KEY fk_mst_location_country",
                ),
                migrations.RunSQL(
                    sql="ALTER TABLE mst_location ADD CONSTRAINT fk_mst_location_country_state FOREIGN KEY (country_state_id) REFERENCES mst_country_state (country_state_id)",
                    reverse_sql="ALTER TABLE mst_location DROP FOREIGN KEY fk_mst_location_country_state",
                ),
                migrations.RunSQL(
                    sql="ALTER TABLE mst_operator ADD CONSTRAINT fk_mst_operator_location FOREIGN KEY (location_id) REFERENCES mst_location (location_id)",
                    reverse_sql="ALTER TABLE mst_operator DROP FOREIGN KEY fk_mst_operator_location",
                ),
                migrations.RunSQL(
                    sql="ALTER TABLE mst_operator ADD CONSTRAINT fk_mst_operator_country FOREIGN KEY (country_id) REFERENCES mst_country (country_id)",
                    reverse_sql="ALTER TABLE mst_operator DROP FOREIGN KEY fk_mst_operator_country",
                ),
                migrations.RunSQL(
                    sql="ALTER TABLE mst_cert_institute ADD CONSTRAINT fk_mst_cert_institute_location FOREIGN KEY (location_id) REFERENCES mst_location (location_id)",
                    reverse_sql="ALTER TABLE mst_cert_institute DROP FOREIGN KEY fk_mst_cert_institute_location",
                ),
                migrations.RunSQL(
                    sql="ALTER TABLE mst_cost_centre ADD CONSTRAINT fk_mst_cost_centre_fs_emp FOREIGN KEY (fs_emp_id) REFERENCES mst_employee (emp_id)",
                    reverse_sql="ALTER TABLE mst_cost_centre DROP FOREIGN KEY fk_mst_cost_centre_fs_emp",
                ),
                migrations.RunSQL(
                    sql="ALTER TABLE mst_cost_centre ADD CONSTRAINT fk_mst_cost_centre_location FOREIGN KEY (location_id) REFERENCES mst_location (location_id)",
                    reverse_sql="ALTER TABLE mst_cost_centre DROP FOREIGN KEY fk_mst_cost_centre_location",
                ),
                migrations.RunSQL(
                    sql="ALTER TABLE mst_rank ADD CONSTRAINT fk_mst_rank_vessel_dept FOREIGN KEY (vessel_dept_id) REFERENCES mst_vessel_dept (vessel_dept_id)",
                    reverse_sql="ALTER TABLE mst_rank DROP FOREIGN KEY fk_mst_rank_vessel_dept",
                ),
                migrations.RunSQL(
                    sql="ALTER TABLE mst_user ADD CONSTRAINT fk_mst_user_emp FOREIGN KEY (emp_id) REFERENCES mst_employee (emp_id)",
                    reverse_sql="ALTER TABLE mst_user DROP FOREIGN KEY fk_mst_user_emp",
                ),
            ],
        ),
    ]
