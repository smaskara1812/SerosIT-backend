"""The project's own apps, in one place. Never write `apps.get_app_config("core")` (or an app name) to mean "our models": that silently
skips every other app, so an export, an import, History and revert or the admin would miss all of its tables. Use these helpers; the
list of apps is `PROJECT_APPS` in config/settings.py."""

from django.apps import apps
from django.conf import settings


def project_app_labels():
    return list(settings.PROJECT_APPS)


def project_models(include_unmanaged=True):
    """Every concrete (non-abstract, non-proxy) model of every project app."""
    found = []
    for label in project_app_labels():
        for m in apps.get_app_config(label).get_models():
            if m._meta.abstract or m._meta.proxy:
                continue
            if include_unmanaged or m._meta.managed:
                found.append(m)
    return found


def project_modules():
    """Every importable module of every project app (sub-packages included, so a viewset in hr/views/recruitment.py is found), as
    (app label, dotted module name). Used to find viewsets and so on wherever they live, without a hand-kept list. Modules that fail to
    import are skipped here; the structure check reports them."""
    import importlib
    import pkgutil

    out = []
    for label in project_app_labels():
        pkg = importlib.import_module(label)
        for mod in pkgutil.walk_packages(pkg.__path__, prefix=f"{label}.", onerror=lambda name: None):
            parts = mod.name.split(".")
            if any(p in ("migrations", "management", "tests") for p in parts):
                continue
            out.append((label, mod.name))
    return out
