from django.db import migrations, models
from django.utils import timezone

# The 28 document names the old system kept as a fixed list (they are also the names already on Document To Sign Mapping rows).
NAMES = [
    "Appreciation_Ltr_Offshore", "Appreciation_Ltr_Onshore", "Conformation_Ltr_Offshore", "Conformation_Ltr_Onshore",
    "Contract_Extension_Ltr_Offshore", "Contract_Extension_Ltr_Onshore", "Experience_Ltr_Offshore", "Experience_Ltr_Onshore",
    "Increment_Ltr_Offshore", "Increment_Ltr_Onshore", "Joining_Contracts_Offshore", "Joining_Contracts_Onshore",
    "Material_Requisition", "Material_Requisition_Onshore", "Offer_Ltr_Offshore", "Offer_Ltr_Onshore",
    "Promotion_Ltr_Offshore", "Promotion_Ltr_Onshore", "Salary_Correction_Ltr_Offshore", "Salary_Correction_Ltr_Onshore",
    "Service_Requisition_Offshore", "Service_Requisition_Onshore", "Termination_Ltr_Offshore", "Termination_Ltr_Onshore",
    "User_Defined_Resume_Offshore", "User_Defined_Resume_Onshore", "Warning_Ltr_Offshore", "Warning_Ltr_Onshore",
]


def seed(apps, schema_editor):
    Doc = apps.get_model("core", "MstSignableDoc")
    now = timezone.now()
    for name in NAMES:
        if not Doc.objects.filter(signable_doc_name=name).exists():
            Doc.objects.create(signable_doc_name=name, signable_doc_active="Y", cr_user_id=1, cr_dt=now)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0099_banner_event"),
    ]

    operations = [
        migrations.CreateModel(
            name="MstSignableDoc",
            fields=[
                ("signable_doc_id", models.AutoField(primary_key=True, serialize=False)),
                ("signable_doc_name", models.CharField(max_length=50)),
                ("signable_doc_active", models.CharField(default="Y", max_length=1)),
                ("cr_user_id", models.IntegerField()),
                ("cr_dt", models.DateTimeField()),
                ("mod_user_id", models.IntegerField(blank=True, null=True)),
                ("mod_dt", models.DateTimeField(blank=True, null=True)),
            ],
            options={"db_table": "mst_signable_doc"},
        ),
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
