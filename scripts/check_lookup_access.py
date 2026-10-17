"""Checks who can read the lists that dropdowns are filled from.

    cd backend
    .venv/bin/python scripts/check_lookup_access.py

The rule: a person may read a list as a dropdown source only if they hold View, Add or Edit on a page that picks
from it (the pages are generated from the frontend into core/lookup_consumers.py), and then only its lookup columns.
Being signed in is not enough, and rights on the list's own page are not needed. This script checks, with real
requests as people with exactly the rights named:

  1. every list a page picks from opens for someone who holds ONLY that page (so the page works for them),
     and returns the columns the dropdown asked for;
  2. every list that can serve lookups answers 403 for someone with no rights at all (typing the address is not
     enough) and for someone who holds only a page that does not pick from it;
  3. a lookup read returns only lookup columns, never audit columns or private ones, and does not allow writes or
     exports; private lists (mail recipients, job descriptions, ...) stay closed even to the pages around them;
  4. no page quietly depends on another page's rights for data that is not a lookup list;
  5. core/lookup_consumers.py matches what the frontend uses right now (run scripts/build_lookup_consumers.py if not).

Everything runs inside one transaction that is rolled back, so nothing is saved. Exits with status 1 on a failure.
"""

import importlib.util
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import get_resolver, resolve
from rest_framework.test import APIClient

from core.models import UserPermission, UserProfile
from core.permissions import invalidate_user_access

HOST = "localhost"  # the self-test sets this to the host its other checks use
FAILED = []
_users = {}


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_lookup_consumers", os.path.join(ROOT, "scripts", "build_lookup_consumers.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check(name, ok, detail=""):
    print(("  ok    " if ok else "  FAIL  ") + name + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


def client_for(*keys):
    """A signed-in person who holds View on exactly these menu keys (none at all, for no keys)."""
    held = tuple(sorted(keys))
    if held not in _users:
        name = f"zzlk{len(_users)}"  # short: the login column is narrow
        user = get_user_model().objects.create_user(username=name, password="x")
        next_id = (UserProfile.objects.order_by("-user_id").first().user_id or 0) + 1
        UserProfile.objects.create(user_id=next_id, user_login_id=name, is_app_admin=False)
        for k in held:
            UserPermission.objects.create(user_id=next_id, menu_key=k, can_view=True, can_add=False, can_edit=False, can_delete=False, can_export=False)
        invalidate_user_access(name)
        c = APIClient(HTTP_HOST=HOST)
        c.force_authenticate(user)
        _users[held] = c
    return _users[held]


def lookup_routes():
    """{entity key: list url} for every list in the URL conf that can serve lookups."""
    found = {}

    def walk(patterns, prefix=""):
        for p in patterns:
            if hasattr(p, "url_patterns"):
                walk(p.url_patterns, prefix + str(p.pattern))
                continue
            cls = getattr(getattr(p, "callback", None), "cls", None)
            route = (prefix + str(p.pattern)).replace("^", "").replace("$", "")
            if cls and re.fullmatch(r"api/[a-z0-9\-/]+/", route) and "(?P" not in route and "<" not in route:
                capable = getattr(cls, "is_lookup_capable", None)
                key = getattr(cls, "lookup_entity", None) or getattr(cls, "entity_key", None)
                if capable and capable() and key and key not in found:
                    found[key] = "/" + route

    walk(get_resolver().url_patterns)
    return found


def asked_for(url):
    m = re.search(r"[?&]fields=([^&]+)", url)
    return [f for f in m.group(1).replace("%2C", ",").split(",") if f] if m else []


def rows_of(response):
    data = response.json()
    return data.get("results", data) if isinstance(data, dict) else data


def run():
    builder = _load_builder()
    refs = builder.references()
    routes = lookup_routes()
    registry = builder.build()

    print(f"\n== 1. Every list a page picks from opens for someone who holds only that page ({len(refs)} calls scanned) ==")
    opened = 0
    for where, keys, url in refs:
        entity = builder.entity_of(url.split("?")[0])
        if not entity:
            continue
        who = client_for(*keys)
        r = who.get(url)
        opened += 1
        check(f"{where} opens {url}", r.status_code in (200, 405), f"status {r.status_code}")  # 405: a POST-only action, so rights passed
        want = asked_for(url)
        if r.status_code == 200 and want:
            rows = rows_of(r)
            missing = [f for f in want if rows and f not in rows[0]]
            check(f"  and returns the columns it asked for: {url}", not missing, f"missing {missing}")
    print(f"   ({opened} calls opened)")

    print(f"\n== 2. {len(routes)} lists that can serve lookups: closed to someone with no rights, and to a page that does not pick from them ==")
    nobody = client_for()
    for entity, url in sorted(routes.items()):
        r = nobody.get(url)
        check(f"closed for someone with no rights: {url}", r.status_code == 403, f"status {r.status_code}")
        owners = set(registry.get(entity, ())) | {entity}
        wrong = next((k for k in ("qhse.hazard_id_card", "dashboards.fuel_water", "it_asset.it_assets", "drilling.drilling_report", "qhse.training_log") if k not in owners), None)
        if wrong:
            r = client_for(wrong).get(url)
            check(f"closed for a page that does not pick from it ({wrong}): {url}", r.status_code == 403, f"status {r.status_code}")

    print("\n== 3. What a lookup read may return, and what stays closed ==")
    picker = client_for("qhse.incident_details")  # holds a page that picks from Rigs
    r = picker.get("/api/masters/rigs/?page_size=5&fields=rig_id,rig_name,cr_user_id,mod_dt,cr_dt")
    row = (rows_of(r) or [{}])[0] if r.status_code == 200 else {}
    check("rigs: audit columns are never returned, even when asked for", r.status_code == 200 and not ({"cr_user_id", "mod_dt", "cr_dt"} & set(row)), str(sorted(row)))
    r = picker.get("/api/masters/rigs/?page_size=5")
    row = (rows_of(r) or [{}])[0] if r.status_code == 200 else {}
    check("rigs: with no ?fields= only lookup columns come back", r.status_code == 200 and "rig_name" in row and "cr_user_id" not in row, str(sorted(row)))
    r = client_for("drilling.drilling_report").get("/api/masters/project-drilling-rates/?page_size=5")
    row = (rows_of(r) or [{}])[0] if r.status_code == 200 else {}
    check("drilling rates: the rate code is offered, the amounts are not", r.status_code == 200 and not ({"rate", "rate_amount", "amount"} & set(row)), str(sorted(row)))
    r = client_for("qhse.incident_root_cause").get("/api/qhse/incidents/?page_size=3")
    row = (rows_of(r) or [{}])[0] if r.status_code == 200 else {}
    check("incidents, for the Root Cause page: only the declared columns come back", r.status_code == 200 and set(row) <= {"incident_id", "rig_incident_no", "rig_name", "incident_date"}, str(sorted(row)))
    r = client_for("qhse.incident_details").get("/api/masters/users/?page_size=3")
    check("users: not readable by a page that does not pick from them", r.status_code == 403, f"status {r.status_code}")
    r = client_for("masters.mail_alert_to_users").get("/api/masters/users/?page_size=3")
    row = (rows_of(r) or [{}])[0] if r.status_code == 200 else {}
    check("users: an email address is never returned", "user_email" not in row, str(sorted(row)))
    for url in ("/api/masters/job-description-headers/", "/api/masters/user-rig-mapping/", "/api/masters/mail-alerts/export/"):
        r = picker.get(url)
        check(f"stays closed to a page around it: {url}", r.status_code == 403, f"status {r.status_code}")
    r = picker.post("/api/masters/rigs/", {"rig_name": "ZZ Probe Rig"}, format="json")
    check("a lookup read does not allow adding a rig", r.status_code == 403, f"status {r.status_code}")
    r = picker.get("/api/masters/rigs/export/")
    check("a lookup read does not allow the export", r.status_code == 403, f"status {r.status_code}")

    print("\n== 4. Pages that call into another page's data, made by someone who holds only the calling page ==")
    broken = 0
    seen = set()
    for where, keys, url in refs:
        path = url.split("?")[0]
        if (where, path) in seen:
            continue
        seen.add((where, path))
        try:
            owner = getattr(resolve(path).func.cls, "entity_key", None)
        except Exception:
            continue
        if owner is None or owner in keys or builder.entity_of(path):
            continue  # the page's own data, or a lookup list (checked above)
        r = client_for(*keys).get(url)
        if r.status_code == 403:
            broken += 1
            check(f"{where} -> {url} (belongs to {owner})", False, "403: the page cannot read it without rights on the other page")
    if not broken:
        check(f"no page depends on another page's rights for non-lookup data ({len(seen)} calls checked)", True)

    print("\n== 5. The list of which page picks from what is up to date ==")
    check("core/lookup_consumers.py matches the frontend (run scripts/build_lookup_consumers.py if not)", builder.render(registry) == open(builder.OUT, encoding="utf-8").read())


class Rollback(Exception):
    pass


def main():
    try:
        with transaction.atomic():
            run()
            raise Rollback()
    except Rollback:
        pass
    print()
    if FAILED:
        print(f"FAILED: {len(FAILED)} check(s):")
        for n in FAILED:
            print("  -", n)
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
