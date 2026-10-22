from django.db import migrations, models

# Step 2 of retiring mst_employee: every link to it stops being a foreign key (the constraints are dropped; the columns and their values
# stay, as plain legacy employee ids). The table itself is NOT dropped here.
CHANGES = [
    # (model, old name, new name, db column)
    ("mstbusinesssystem", "owner_emp", "legacy_owner_emp_id", "owner_emp_id"),
    ("mailalerttouser", "emp", "legacy_emp_id", "emp_id"),
    ("mstuser", "emp", "emp_id", "emp_id"),
    ("doctosignmapping", "employee", "legacy_emp_id", "emp_id"),
    ("mstitasset", "emp", "legacy_emp_id", "emp_id"),
    ("itassetholder", "emp", "legacy_emp_id", "emp_id"),
    ("itaccessoryholder", "emp", "legacy_emp_id", "emp_id"),
]


def build():
    ops = []
    for model, old, new, column in CHANGES:
        ops.append(migrations.AlterField(model, old, models.IntegerField(db_column=column, null=True, blank=True)))
        ops.append(migrations.RenameField(model, old, new))
    return ops


class Migration(migrations.Migration):
    dependencies = [("core", "0102_employee_independence_step1")]
    operations = build()
