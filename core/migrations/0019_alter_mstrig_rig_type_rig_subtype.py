import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Converts MstRig.rig_type_id/rig_subtype_id from raw IntegerFields to
    real ForeignKeys, now that mst_rig_type/mst_rig_subtype exist and are
    populated (see import_rig_type_subtype.sql, run between 0018 and this
    migration). The underlying columns keep their name and type — only a DB
    FK constraint is added — so this is state-only at the Django level."""

    dependencies = [
        ("core", "0018_mstrigtype_mstrigsubtype"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveField(model_name="mstrig", name="rig_type_id"),
                migrations.RemoveField(model_name="mstrig", name="rig_subtype_id"),
                migrations.AddField(
                    model_name="mstrig",
                    name="rig_type",
                    field=models.ForeignKey(
                        db_column="rig_type_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="rigs",
                        to="core.mstrigtype",
                        default=1,
                    ),
                    preserve_default=False,
                ),
                migrations.AddField(
                    model_name="mstrig",
                    name="rig_subtype",
                    field=models.ForeignKey(
                        db_column="rig_subtype_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="rigs",
                        to="core.mstrigsubtype",
                        default=1,
                    ),
                    preserve_default=False,
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE mst_rig ADD CONSTRAINT fk_mst_rig_rig_type FOREIGN KEY (rig_type_id) REFERENCES mst_rig_type (rig_type_id)",
                    reverse_sql="ALTER TABLE mst_rig DROP FOREIGN KEY fk_mst_rig_rig_type",
                ),
                migrations.RunSQL(
                    sql="ALTER TABLE mst_rig ADD CONSTRAINT fk_mst_rig_rig_subtype FOREIGN KEY (rig_subtype_id) REFERENCES mst_rig_subtype (rig_subtype_id)",
                    reverse_sql="ALTER TABLE mst_rig DROP FOREIGN KEY fk_mst_rig_rig_subtype",
                ),
            ],
        ),
    ]
