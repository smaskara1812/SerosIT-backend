"""Guard rails against silly mistakes in the project layout and the HR conventions.

    cd backend
    .venv/bin/python scripts/check_project_structure.py

It checks that:
  1. every app folder with models is in PROJECT_APPS, has migrations, and the model changes have their migration (makemigrations --check);
  2. nothing hard-codes one app where "all our models" is meant (exports, imports, History and revert, admin, self-test);
  3. the HR rules really bite: made-up HR models and viewsets that break a rule are refused (so the safeguards themselves are tested);
  4. every HR route refuses someone who is not signed in;
  5. every HR viewset's page name (entity_key) exists in the menu table, so the page can be given rights.
Read-only. Exits 1 on any failure.
"""
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.db import models
from django.test import Client
from django.test.utils import isolate_apps
from django.urls import URLPattern, URLResolver, get_resolver

from core.project_apps import project_app_labels, project_models
from core.structure_checks import unregistered_app_folders
from hr.checks import hr_model_problems
from hr.views import HrMasterViewSet

FAILED = []
BASE = str(settings.BASE_DIR)


def check(name, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  {str(detail)[:300]}" if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


print("1. layout")
check("PROJECT_APPS are all installed", all(a in [x.split('.')[0] for x in settings.INSTALLED_APPS] for a in project_app_labels()))
check("every project app has a migrations folder", all(os.path.isfile(os.path.join(BASE, a, "migrations", "__init__.py")) for a in project_app_labels()))
check("no app folder with models is missing from PROJECT_APPS", not unregistered_app_folders(BASE, settings.PROJECT_APPS, settings.INSTALLED_APPS), unregistered_app_folders(BASE, settings.PROJECT_APPS, settings.INSTALLED_APPS))
with tempfile.TemporaryDirectory() as tmp:
    os.makedirs(os.path.join(tmp, "newapp"))
    open(os.path.join(tmp, "newapp", "apps.py"), "w").close()
    open(os.path.join(tmp, "newapp", "models.py"), "w").close()
    check("a new app folder left out of PROJECT_APPS is caught", unregistered_app_folders(tmp, ["core", "hr"], []) == ["newapp"])
try:
    call_command("makemigrations", check=True, dry_run=True, verbosity=0, stdout=io.StringIO(), stderr=io.StringIO())
    ok = True
except SystemExit:
    ok = False
check("every model change has its migration (makemigrations --check)", ok, "run: python manage.py makemigrations")
union = {m for label in project_app_labels() for m in apps.get_app_config(label).get_models() if not m._meta.abstract and not m._meta.proxy}
check("project_models() returns the models of every project app", set(project_models()) == union)

print("2. nothing hard-codes one app")
bad = []
for root, dirs, files in os.walk(BASE):
    dirs[:] = [d for d in dirs if d not in (".venv", "node_modules", "migrations", "__pycache__", "media")]
    for f in files:
        if f.endswith(".py") and f not in ("project_apps.py", "check_project_structure.py"):
            text = open(os.path.join(root, f), encoding="utf-8", errors="ignore").read()
            if 'get_app_config("core")' in text or "get_app_config('core')" in text or 'app_label == "core"' in text:
                bad.append(os.path.relpath(os.path.join(root, f), BASE))
check("no file asks for the core app alone where all our models are meant", not bad, bad)

print("3. the HR rules bite")
with isolate_apps("hr"):
    class Good(models.Model):
        class Meta:
            app_label = "hr"
            db_table = "hr_good"

    class NoTable(models.Model):
        class Meta:
            app_label = "hr"

    class WrongPrefix(models.Model):
        class Meta:
            app_label = "hr"
            db_table = "candidates"

    class Upper(models.Model):
        class Meta:
            app_label = "hr"
            db_table = "hr_Upper"

    check("a correct HR model passes", not hr_model_problems([Good]), hr_model_problems([Good]))
    check("an HR model with no db_table is refused", len(hr_model_problems([NoTable])) == 1)
    check("an HR table that does not start with hr_ is refused", len(hr_model_problems([WrongPrefix])) == 1)
    check("an HR table with capitals is refused", len(hr_model_problems([Upper])) == 1)

    def refused(**attrs):
        try:
            type("Bad", (HrMasterViewSet,), {"__module__": "x", **attrs})
            return False
        except ImproperlyConfigured:
            return True

    base = {"queryset": Good.objects.all(), "serializer_class": object, "name_field": "id"}
    check("a correct HR viewset is accepted", not refused(**base, entity_key="hr.good"))
    check("an HR viewset with no entity_key is refused", refused(**base))
    check("an HR viewset whose entity_key does not start with hr. is refused", refused(**base, entity_key="masters.good"))
    check("an HR viewset with capitals in its entity_key is refused", refused(**base, entity_key="hr.Good"))
    check("an HR viewset with no queryset is refused", refused(serializer_class=object, name_field="id", entity_key="hr.good"))
    check("an HR viewset with no name_field is refused", refused(queryset=Good.objects.all(), serializer_class=object, entity_key="hr.good"))
    from core.models import MstRig
    check("an HR viewset on a core model is refused", refused(queryset=MstRig.objects.all(), serializer_class=object, name_field="id", entity_key="hr.rigs"))

print("4. HR routes need a signed-in user")


def walk(patterns, prefix=""):
    for p in patterns:
        if isinstance(p, URLResolver):
            yield from walk(p.url_patterns, prefix + str(p.pattern))
        elif isinstance(p, URLPattern):
            yield prefix + str(p.pattern)


hr_routes = [r for r in walk(get_resolver().url_patterns) if r.startswith("api/hr/")]
anon = Client(HTTP_HOST="localhost")
open_routes = []
for route in hr_routes:
    if "<" in route or "(?P" in route:  # routes with a parameter need a real id; the ones without cover the list pages
        continue
    path = "/" + route.replace("^", "").replace("\\.", ".").replace("$", "")
    r = anon.get(path)
    if r.status_code not in (401, 403, 404, 405):
        open_routes.append((path, r.status_code))
check(f"every HR route refuses an anonymous request ({len(hr_routes)} routes)", not open_routes, open_routes)

print("5. HR pages have a menu row")
from django.db import connection

if "sys_menu" in connection.introspection.table_names():
    from core.models import SysMenu

    keys = set(SysMenu.objects.values_list("menu_key", flat=True))
    from core.audit_revert import viewsets_by_entity

    hr_entities = [k for k, v in viewsets_by_entity().items() if any(c.__module__.startswith("hr.") for c in v)]
    missing = [k for k in hr_entities if k not in keys]
    check(f"every HR page name exists in sys_menu ({len(hr_entities)} pages)", not missing, missing)

print()
print("FAILED:" if FAILED else "all checks passed", *FAILED, sep="\n  " if FAILED else " ")
sys.exit(1 if FAILED else 0)
