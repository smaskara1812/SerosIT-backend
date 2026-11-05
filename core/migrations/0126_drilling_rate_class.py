from django.db import migrations, models

# Adds the Rate Class column only. NO data is filled here: the Drilling Rates rows come from the legacy data transfer. While a row's class is blank the code falls
# back to the built-in classes of the old rate ids (core/rate_classes.py _BUILT_IN_ORIGINAL), so nothing changes until someone sets a class.


class Migration(migrations.Migration):
    dependencies = [("core", "0125_rig_month_plan_weights_optional")]
    operations = [
        migrations.AddField(model_name="mstdrillingrate", name="rate_class", field=models.CharField(blank=True, max_length=20, null=True)),
    ]
