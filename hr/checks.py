"""System checks for the HR app. Django runs these on every manage.py command (runserver, migrate, makemigrations, test, check), so a
mistake against the HR conventions stops the command with a message that names the model."""

from django.apps import apps
from django.core import checks

PREFIX = "hr_"


def hr_model_problems(models):
    """Messages for HR models that break the rules. A function of the model list so it can be tested with made-up models."""
    problems = []
    for m in models:
        name = f"{m.__module__}.{m.__name__}"
        table = getattr(m._meta, "db_table", "") or ""
        explicit = getattr(m._meta, "original_attrs", {}).get("db_table")
        if not explicit:
            problems.append((name, "has no explicit Meta.db_table. Set db_table = 'hr_<name>' so the table name is never guessed."))
        elif not table.startswith(PREFIX) or table != table.lower() or " " in table:
            problems.append((name, f"db_table {table!r} must be lower case and start with {PREFIX!r} (so it cannot clash with a core table)."))
    return problems


@checks.register("models")
def check_hr_models(app_configs=None, **kwargs):
    try:
        models = [m for m in apps.get_app_config("hr").get_models() if not m._meta.abstract and not m._meta.proxy]
    except LookupError:
        return []
    return [checks.Error(f"{name}: {text}", id="hr.E001") for name, text in hr_model_problems(models)]
