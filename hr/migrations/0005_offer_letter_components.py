"""Offer letter: pay components as rows instead of columns.

  * new tables hr_salary_component (the component master) and hr_fs_offer_letter_component (one row per component of a letter);
  * the header's links become real foreign keys (rank, rig site mapping, company, travel eligibility) and the signer a user (authority_user);
  * the existing letters' money columns are turned into component rows, the signer's employee id into the user that has it, then the money
    columns (and authority_emp_id) are dropped.
"""

import django.db.models.deletion
from django.db import migrations, models

# (component id = legacy ED_Id, name, abbreviation, display order, counts toward the total by default) for the components a letter uses.
COMPONENTS = [
    (1, "Basic", "Basic", 1, "Y"),
    (3, "House Rent Allowance", "HRA", 2, "Y"),
    (29, "Personal Allowance", "Per. Allow", 3, "Y"),
    (6, "Special Allowance", "Sp. Allow", 4, "Y"),
    (30, "Statutory Bonus", "STATUBONUS", 5, "Y"),
    (20, "Washing Allowance", "Wash-Allw", 6, "Y"),
    (31, "Conveyance", "Conveyance", 7, "Y"),
    (32, "Other Allowance", "OTHERALLOW", 8, "Y"),
    (8, "Provident Fund (Employer)", "PF-Emplr", 9, "Y"),
    (35, "ESIC", "ESIC_EMYR", 10, "Y"),
    (4, "Travel Allowance", "Tr Allow", 11, "N"),
    (34, "Camp Allowance", "CAMPALLO", 12, "N"),
    (33, "Day Rate Amount", "DAY_RT_AMT", 13, "N"),
]

# old column -> (component id, flag column or None, what the flag meant in legacy)
#   counts: the flag said "include in CTC", so it is whether the amount counts toward the total (always Y for the plain components)
#   show:   the flag said "display in the offer letter"
OLD_COLUMNS = [
    ("basic_salary", 1, None, None),
    ("hra", 3, None, None),
    ("per_allow", 29, None, None),
    ("sp_allow", 6, None, None),
    ("statutory_bonus", 30, None, None),
    ("washing_allow", 20, None, None),
    ("conveyance", 31, None, None),
    ("other_allowance", 32, None, None),
    ("pf_emplr", 8, None, None),
    ("esic", 35, None, None),
    ("travel_allowance", 4, "include_in_ctc_travel_allow", "counts"),
    ("camp_allow", 34, "include_in_ctc_camp_allow", "show"),
    ("day_rate_amt", 33, "include_in_ctc_day_rate_amt", "show"),
]
MONEY_FIELDS = [c[0] for c in OLD_COLUMNS] + ["include_in_ctc_camp_allow", "include_in_ctc_travel_allow", "include_in_ctc_day_rate_amt", "authority_emp_id"]


def explode_money_columns(apps, schema_editor):
    Component = apps.get_model("hr", "SalaryComponent")
    Letter = apps.get_model("hr", "FsOfferLetter")
    Row = apps.get_model("hr", "FsOfferLetterComponent")
    MstUser = apps.get_model("core", "MstUser")
    for cid, name, abbrv, order, counts in COMPONENTS:
        Component.objects.update_or_create(component_id=cid, defaults=dict(component_name=name, component_abbrv=abbrv, display_order=order, counts_in_total=counts,
                                                                           in_offer_letter="Y", component_type="E", active="Y"))
    order_of = {c[0]: c[3] for c in COMPONENTS}
    for letter in Letter.objects.all().iterator():
        rows = []
        for old, cid, flag, meaning in OLD_COLUMNS:
            amount = getattr(letter, old)
            if not amount:
                continue
            flag_y = flag is not None and getattr(letter, flag) == "Y"
            counts = "Y" if meaning is None else ("Y" if flag_y else "N") if meaning == "counts" else "N"
            show = "Y" if meaning != "show" else ("Y" if flag_y else "N")
            rows.append(Row(offer_letter_id=letter.pk, component_id=cid, amount=amount, counts_in_total=counts, show_in_letter=show, sort_order=order_of[cid]))
        Row.objects.bulk_create(rows)
        if letter.authority_emp_id:
            user = MstUser.objects.filter(emp_id=letter.authority_emp_id).order_by("-user_id").first()
            if user:
                letter.authority_user_id = user.pk
                letter.save(update_fields=["authority_user"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0132_sero_outfits"),
        ("hr", "0004_fs_applicants"),
    ]

    operations = [
        migrations.CreateModel(
            name="SalaryComponent",
            fields=[
                ("component_id", models.IntegerField(primary_key=True, serialize=False)),
                ("component_name", models.CharField(max_length=50, unique=True)),
                ("component_abbrv", models.CharField(blank=True, default="", max_length=15)),
                ("component_type", models.CharField(default="E", max_length=1)),
                ("display_order", models.SmallIntegerField(default=0)),
                ("in_offer_letter", models.CharField(default="Y", max_length=1)),
                ("counts_in_total", models.CharField(default="Y", max_length=1)),
                ("active", models.CharField(default="Y", max_length=1)),
                ("cr_user_id", models.IntegerField(blank=True, null=True)),
                ("cr_dt", models.DateTimeField(blank=True, null=True)),
                ("mod_user_id", models.IntegerField(blank=True, null=True)),
                ("mod_dt", models.DateTimeField(blank=True, null=True)),
            ],
            options={"db_table": "hr_salary_component"},
        ),
        migrations.AddConstraint(model_name="salarycomponent", constraint=models.CheckConstraint(condition=models.Q(("component_type__in", ["E", "D"])), name="hr_salary_comp_type_e_d")),
        migrations.AddConstraint(model_name="salarycomponent", constraint=models.CheckConstraint(condition=models.Q(("in_offer_letter__in", ["Y", "N"])), name="hr_salary_comp_in_letter_y_n")),
        migrations.AddConstraint(model_name="salarycomponent", constraint=models.CheckConstraint(condition=models.Q(("counts_in_total__in", ["Y", "N"])), name="hr_salary_comp_counts_y_n")),
        migrations.AddConstraint(model_name="salarycomponent", constraint=models.CheckConstraint(condition=models.Q(("active__in", ["Y", "N"])), name="hr_salary_comp_active_y_n")),
        migrations.CreateModel(
            name="FsOfferLetterComponent",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("amount", models.IntegerField(default=0)),
                ("counts_in_total", models.CharField(default="Y", max_length=1)),
                ("show_in_letter", models.CharField(default="Y", max_length=1)),
                ("sort_order", models.SmallIntegerField(default=0)),
                ("component", models.ForeignKey(db_column="component_id", on_delete=django.db.models.deletion.PROTECT, related_name="+", to="hr.salarycomponent")),
                ("offer_letter", models.ForeignKey(db_column="fs_new_appl_id", on_delete=django.db.models.deletion.CASCADE, related_name="components", to="hr.fsofferletter")),
            ],
            options={"db_table": "hr_fs_offer_letter_component"},
        ),
        migrations.AddConstraint(model_name="fsofferlettercomponent", constraint=models.UniqueConstraint(fields=("offer_letter", "component"), name="hr_offer_comp_unique")),
        migrations.AddConstraint(model_name="fsofferlettercomponent", constraint=models.CheckConstraint(condition=models.Q(("counts_in_total__in", ["Y", "N"])), name="hr_offer_comp_counts_y_n")),
        migrations.AddConstraint(model_name="fsofferlettercomponent", constraint=models.CheckConstraint(condition=models.Q(("show_in_letter__in", ["Y", "N"])), name="hr_offer_comp_show_y_n")),
        migrations.AddField(
            model_name="fsofferletter",
            name="authority_user",
            field=models.ForeignKey(blank=True, db_column="authority_user_id", null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="core.mstuser"),
        ),
        # the plain id columns become real foreign keys (same column names, data kept)
        migrations.RenameField("fsofferletter", "rank_id", "rank"),
        migrations.AlterField("fsofferletter", "rank", models.ForeignKey(db_column="rank_id", on_delete=django.db.models.deletion.PROTECT, related_name="+", to="core.mstrank")),
        migrations.RenameField("fsofferletter", "rig_site_mapping_id", "rig_site_mapping"),
        migrations.AlterField("fsofferletter", "rig_site_mapping", models.ForeignKey(db_column="rig_site_mapping_id", on_delete=django.db.models.deletion.PROTECT, related_name="+", to="core.rigsitemapping")),
        migrations.RenameField("fsofferletter", "company_id", "company"),
        migrations.AlterField("fsofferletter", "company", models.ForeignKey(db_column="company_id", on_delete=django.db.models.deletion.PROTECT, related_name="+", to="core.mstcompany")),
        migrations.RenameField("fsofferletter", "travel_eligibility_id", "travel_eligibility"),
        migrations.AlterField("fsofferletter", "travel_eligibility", models.ForeignKey(blank=True, db_column="travel_eligibility_id", null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="core.traveleligibility")),
        migrations.RunPython(explode_money_columns, migrations.RunPython.noop),
        *[migrations.RemoveField("fsofferletter", f) for f in MONEY_FIELDS],
    ]
