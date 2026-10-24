"""System checks about the project layout itself (run on every manage.py command)."""

import os

from django.conf import settings
from django.core import checks


def unregistered_app_folders(base_dir, registered, installed):
    """Folders next to manage.py that look like a Django app with models (they have apps.py and a models module or package) but are not in
    PROJECT_APPS: an export, an import, History and revert or the admin would silently skip every table in them."""
    found = []
    for name in sorted(os.listdir(base_dir)):
        path = os.path.join(base_dir, name)
        if name.startswith((".", "_")) or not os.path.isdir(path) or name in ("config", "scripts", "media", "docs"):
            continue
        has_models = os.path.isfile(os.path.join(path, "models.py")) or os.path.isdir(os.path.join(path, "models"))
        if os.path.isfile(os.path.join(path, "apps.py")) and has_models and name not in registered:
            found.append(name)
    return found


@checks.register()
def check_project_apps(app_configs=None, **kwargs):
    problems = []
    registered = list(getattr(settings, "PROJECT_APPS", []))
    for name in unregistered_app_folders(str(settings.BASE_DIR), registered, settings.INSTALLED_APPS):
        problems.append(checks.Error(
            f"The app folder {name!r} has models but is not in PROJECT_APPS (config/settings.py). Add it there, once, and nowhere else: "
            "exports, imports, History and revert and the admin read that list.", id="core.E010"))
    for label in registered:
        if label not in [a.split(".")[0] for a in settings.INSTALLED_APPS]:
            problems.append(checks.Error(f"PROJECT_APPS lists {label!r} but INSTALLED_APPS does not include it.", id="core.E011"))
        if not os.path.isdir(os.path.join(str(settings.BASE_DIR), label, "migrations")):
            problems.append(checks.Error(f"App {label!r} has no migrations folder (with an __init__.py): its tables could not be created.", id="core.E012"))
    return problems
