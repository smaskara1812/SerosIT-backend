"""Read-only self test: finds code and database errors without using the app.

    python manage.py selftest              # everything
    python manage.py selftest --fast       # skip the extra query variants
    python manage.py selftest --only drilling    # only API routes containing this text
    python manage.py selftest --user jsmith      # run as this login (default: first active app admin)

Run it on the Windows / SQL Server machine after every pull. It never writes
data (GET requests only), and writes a full report with tracebacks to
selftest_report_<time>.txt in the backend folder.

Four parts:
  1. Environment: database, migrations, Django system check, PDF engine (ReportLab),
     Excel engine, media folder, logo file, duplicate token-blacklist rows.
  2. Every table: reads one row of each model, so a missing column or table fails here.
  3. Every API route that answers GET: opened in-process as an admin, with a few
     variants (second page, search, ordering). A crash (500) or Python exception fails.
  4. A summary of failures, grouped by cause.

A 400/404 on a route that needs parameters is not a failure. A 503
is reported as a warning.
"""

import re
import time
import traceback
from collections import Counter, OrderedDict
from datetime import datetime
from io import BytesIO

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.test import APIClient

from core.models import UserProfile

SLOW_SECONDS = 3.0
PLACEHOLDER = re.compile(r"\(\?P<(\w+)>[^)]*\)|<(?:\w+:)?(\w+)>")


class Result:
    def __init__(self, area, name, status, detail="", seconds=0.0, trace=""):
        self.area, self.name, self.status = area, name, status  # status: ok | warn | fail
        self.detail, self.seconds, self.trace = detail, seconds, trace


def _last_project_frame(trace):
    frames = [l.strip() for l in trace.splitlines() if 'File "' in l and ("SerosIT" in l or "backend" in l) and ".venv" not in l and "site-packages" not in l]
    return frames[-1] if frames else ""


def _short_trace(trace):
    """Only the project's own frames plus the error line; the test client and
    framework frames are noise."""
    lines = trace.splitlines()
    keep = []
    for i, l in enumerate(lines):
        if 'File "' in l and "/core/" in l.replace("\\", "/") and "selftest.py" not in l and ".venv" not in l and "site-packages" not in l:
            keep.append(l.strip())
            if i + 1 < len(lines):
                keep.append("    " + lines[i + 1].strip())
    keep.append(_error_line(trace))
    return "\n".join(keep)


def _error_line(trace):
    lines = [l for l in trace.strip().splitlines() if l.strip()]
    return lines[-1][:300] if lines else ""


def _walk(patterns, prefix=""):
    for p in patterns:
        piece = str(p.pattern)
        if isinstance(p, URLResolver):
            yield from _walk(p.url_patterns, prefix + piece)
        elif isinstance(p, URLPattern):
            yield prefix + piece, p.callback


def _clean(route):
    route = route.replace("^", "").replace("$", "").replace("\\Z", "").replace("\\.", ".")
    route = route.replace("/?", "/").replace("?", "")
    return PLACEHOLDER.sub(lambda m: "{" + (m.group(1) or m.group(2)) + "}", route)


def api_routes():
    """Unique (route, callback) pairs under api/ that can answer GET."""
    seen = OrderedDict()
    for raw, cb in _walk(get_resolver().url_patterns):
        route = _clean(raw)
        if not route.startswith("api/") or "format" in route or "(" in route:
            continue
        actions = getattr(cb, "actions", None)
        cls = getattr(cb, "cls", None) or getattr(cb, "view_class", None)
        if actions is not None:
            if "get" not in actions:
                continue
        elif cls is None or not hasattr(cls, "get"):
            continue
        seen.setdefault(route, cb)
    return seen


class Command(BaseCommand):
    help = "Read-only self test of the environment, every table and every GET API route."

    def add_arguments(self, parser):
        parser.add_argument("--fast", action="store_true", help="Skip the extra query variants")
        parser.add_argument("--only", default="", help="Only API routes containing this text")
        parser.add_argument("--user", default="", help="Login to run as (default: first active app admin)")
        parser.add_argument("--no-tables", action="store_true", help="Skip the table sweep")

    # ── output helpers ──────────────────────────────────────────────────────
    def say(self, text="", style=None):
        self.stdout.write(style(text) if style else text)

    def record(self, res):
        self.results.append(res)
        mark = {"ok": self.style.SUCCESS("  ok  "), "warn": self.style.WARNING(" WARN "), "fail": self.style.ERROR(" FAIL ")}[res.status]
        if res.status != "ok" or self.verbose_all:
            self.say(f"{mark} [{res.area}] {res.name}  {res.detail}".rstrip())

    # ── part 1 ──────────────────────────────────────────────────────────────
    def environment(self):
        def run(name, fn):
            t0 = time.time()
            try:
                out = fn()
                status, detail = (out if isinstance(out, tuple) else ("ok", out or ""))
                self.record(Result("env", name, status, detail, time.time() - t0))
            except Exception:
                tb = traceback.format_exc()
                self.record(Result("env", name, "fail", _error_line(tb), time.time() - t0, tb))

        def database():
            with connection.cursor() as c:
                if connection.vendor == "microsoft":
                    c.execute("SELECT @@VERSION")
                    ver = c.fetchone()[0].splitlines()[0]
                else:
                    c.execute("SELECT VERSION()")
                    ver = c.fetchone()[0]
            self.say(f"Database: {connection.vendor} {connection.settings_dict['NAME']} - {ver}")
            return f"{connection.vendor}"

        def migrations():
            ex = MigrationExecutor(connection)
            plan = ex.migration_plan(ex.loader.graph.leaf_nodes())
            if plan:
                return "fail", f"{len(plan)} migration(s) not applied: " + ", ".join(f"{m.app_label}.{m.name}" for m, _ in plan[:5])
            return "all applied"

        def system_check():
            call_command("check", verbosity=0)

        def pdf_engine():
            from core.pdf_reportlab import render_table_report

            pdf = render_table_report(title="Self test", meta=[[("ok", False)]], columns=[{"label": "A", "width": None}], rows=[["1"]])
            return "PDF engine works" if pdf.startswith(b"%PDF") else ("fail", "ReportLab did not produce a PDF")

        def excel():
            from openpyxl import Workbook

            wb = Workbook()
            wb.active["A1"] = "ok"
            buf = BytesIO()
            wb.save(buf)
            return "Excel engine works"

        def media():
            import tempfile

            settings.MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=settings.MEDIA_ROOT, delete=True):
                pass
            return f"{settings.MEDIA_ROOT} is writable"

        def logo():
            from core.company_branding import seros_logo_path

            import os

            p = seros_logo_path()
            return ("ok", "logo found") if p and os.path.exists(str(p).replace("file://", "")) else ("warn", f"SEROS logo not found at {p}")

        def blacklist():
            from django.db.models import Count
            from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

            dups = list(BlacklistedToken.objects.values("token_id").annotate(c=Count("id")).filter(c__gt=1)[:5])
            if dups:
                return "fail", f"{len(dups)}+ token(s) blacklisted more than once; refresh will return 500 for them (delete the extra rows)"
            return "no duplicate rows"

        def admin_exists():
            return "ok", f"running as {self.user.username}" if self.user else ("fail", "no active app admin found")

        run("Database connection", database)
        run("Migrations", migrations)
        run("Django system check", system_check)
        run("PDF engine (ReportLab)", pdf_engine)
        run("Excel engine (openpyxl)", excel)
        run("Media folder", media)
        run("SEROS logo", logo)
        run("Token blacklist rows", blacklist)
        run("Test user", admin_exists)

    # ── part 2 ──────────────────────────────────────────────────────────────
    def tables(self):
        models = [m for m in apps.get_models() if m._meta.app_label == "core" and m._meta.managed and not m._meta.abstract and not m._meta.proxy]
        self.say(f"Reading one row from each of {len(models)} tables...")
        bad = 0
        for m in models:
            t0 = time.time()
            try:
                list(m._default_manager.all()[:1])
                m._default_manager.count()
                if self.verbose_all:
                    self.record(Result("table", m._meta.db_table, "ok", "", time.time() - t0))
                else:
                    self.results.append(Result("table", m._meta.db_table, "ok", "", time.time() - t0))
            except Exception:
                bad += 1
                tb = traceback.format_exc()
                self.record(Result("table", m._meta.db_table, "fail", _error_line(tb), time.time() - t0, tb))
        self.say(f"  tables: {len(models) - bad} ok, {bad} failed")

    # ── part 3 ──────────────────────────────────────────────────────────────
    def get(self, url, label_route):
        t0 = time.time()
        try:
            resp = self.client.get(url)
        except Exception:
            tb = traceback.format_exc()
            return Result("api", url, "fail", _error_line(tb), time.time() - t0, tb), None
        secs = time.time() - t0
        code = resp.status_code
        self.codes[code] += 1
        if 400 <= code < 500 and code not in (401, 403):
            self.client_errors.append(f"{code}  {url}")
        if code == 503:
            detail = ""
            try:
                detail = str(resp.json().get("detail", ""))[:140]
            except Exception:
                pass
            return Result("api", url, "warn", f"503 {detail}", secs), resp
        if code >= 500:
            return Result("api", url, "fail", f"HTTP {code}", secs, resp.content[:600].decode("utf-8", "replace")), resp
        if code in (401, 403):
            return Result("api", url, "warn", f"HTTP {code} (permission)", secs), resp
        if secs > SLOW_SECONDS:
            return Result("api", url, "warn", f"slow: {secs:.1f}s", secs), resp
        return Result("api", url, "ok", f"HTTP {code}", secs), resp

    def sample_id(self, prefix, cb):
        if prefix in self.id_cache:
            return self.id_cache[prefix]
        value = None
        try:
            resp = self.client.get("/" + prefix + "?page_size=1")
            if resp.status_code == 200:
                data = resp.json()
                rows = data.get("results") if isinstance(data, dict) else data
                if rows:
                    row = rows[0]
                    cls = getattr(cb, "cls", None)
                    pk_name = None
                    model = getattr(getattr(cls, "queryset", None), "model", None) if cls else None
                    if model is not None:
                        pk_name = model._meta.pk.name
                    if pk_name and pk_name in row:
                        value = row[pk_name]
                    else:
                        value = next((v for k, v in row.items() if k.endswith("_id") and isinstance(v, int)), None)
                        if value is None:
                            value = next((v for v in row.values() if isinstance(v, int)), None)
        except Exception:
            value = None
        self.id_cache[prefix] = value
        return value

    def api(self, only, fast):
        routes = api_routes()
        if only:
            routes = OrderedDict((r, c) for r, c in routes.items() if only in r)
        self.say(f"Opening {len(routes)} API routes as {self.user.username}...")
        skipped = []
        for route, cb in routes.items():
            if "{" in route:
                head, _, _ = route.partition("{")
                if route.count("{") != 1:
                    skipped.append(route)
                    continue
                sid = self.sample_id(head, cb)
                if sid is None:
                    skipped.append(route + "  (no sample record)")
                    continue
                url = "/" + re.sub(r"\{\w+\}", str(sid), route)
                res, _ = self.get(url, route)
                self.record(res)
                continue
            url = "/" + route
            res, resp = self.get(url, route)
            self.record(res)
            if fast or res.status == "fail" or resp is None or resp.status_code != 200:
                continue
            body = None
            try:
                body = resp.json()
            except Exception:
                pass
            if isinstance(body, dict) and "results" in body:
                variants = ["?search=a", "?page_size=200"]
                if (body.get("count") or 0) > 5:
                    variants.insert(0, "?page_size=5&page=2")
                for v in variants:
                    r2, _ = self.get(url + v, route)
                    if r2.status == "fail":
                        self.record(r2)
                    else:
                        self.results.append(r2)
        self.skipped = skipped

    # ── part 4: routes that need filters ─────────────────────────────────────
    def scenarios(self):
        """Routes that answer 400 without filters hold the heaviest queries and the
        report builders (the Performance Dashboard crash on SQL Server was in one).
        Fill their filters from real data and run them, exports and prints included."""
        from core.models import DrillingDtl, MstFinancialYear, MstFsCategory, MstRig, ProjectContract

        rig = MstRig.objects.order_by("rig_id").first()
        dtl = DrillingDtl.objects.order_by("-drilling_dtl_dt").first()
        fy_ids = ",".join(str(i) for i in MstFinancialYear.objects.values_list("pk", flat=True)[:5])
        cat = MstFsCategory.objects.order_by("pk").first()
        project = ProjectContract.objects.order_by("-prj_start_dt").first()
        if not (rig and dtl):
            self.say("  no drilling data to build scenarios from; skipped")
            return
        rid = rig.rig_id
        to_dt = dtl.drilling_dtl_dt
        to_s = to_dt.date().isoformat() if hasattr(to_dt, "date") else str(to_dt)
        from_s = f"{int(to_s[:4]) - 1}{to_s[4:]}"
        month = to_s[:7]
        year = to_s[:4]
        urls = []
        for status in ("monthly", "daily"):
            pd = f"record_status={status}"
            for suffix in ("", "export/"):
                urls.append(f"/api/drilling/performance-dashboard/{suffix}?{pd}&dates_entered=financial_yr&rig_ids={rid}&financial_years={fy_ids}&page=1")
                urls.append(f"/api/drilling/performance-dashboard/{suffix}?{pd}&dates_entered=dates&rig_ids={rid}&from_dt={from_s}&to_dt={to_s}&page=1")
            urls.append(f"/api/drilling/performance-dashboard/?{pd}&dates_entered=financial_yr&rig_ids={rid}&financial_years={fy_ids}&page=2")
        for base in ("operations-analytics", "drilling-tripping-analysis"):
            for rt in ("daily", "monthly"):
                for suffix in ("", "export/"):
                    urls.append(f"/api/drilling/{base}/{suffix}?rig={rid}&from_dt={from_s}&to_dt={to_s}&report_type={rt}")
        for suffix in ("", "export/"):
            urls.append(f"/api/drilling/drilling-daily-data/{suffix}?rig={rid}&from_dt={from_s}&to_dt={to_s}&page=1")
        if cat:
            for rt in ("Training_Matrix", "Employees_Matrix"):
                for suffix in ("preview/", "export/"):
                    urls.append(f"/api/qhse/training-report/{suffix}?report_type={rt}&category={cat.pk}&rig={rid}&from_date={from_s}&to_date={to_s}")
        for ptype, extra in (("MONTHLY", f"&month={month}"), ("QUARTERLY", f"&year={year}&quarter=JAN_MAR"), ("ANNUAL", f"&year={year}"), ("DATE_RANGE", f"&from_month={from_s[:7]}&to_month={month}")):
            for suffix in ("", "print/"):
                urls.append(f"/api/qhse/mis-hse-review/{suffix}?period_type={ptype}&filter_type=SEROS{extra}")
                if project:
                    urls.append(f"/api/qhse/mis-hse-review/{suffix}?period_type={ptype}&filter_type=PROJECT&project={project.pk}{extra}")
        self.say(f"Running {len(urls)} filtered report/dashboard requests...")
        for url in urls:
            res, resp = self.get(url, url)
            if res.status == "ok" and resp is not None and resp.status_code != 200:
                res = Result("api", url, "warn", f"HTTP {resp.status_code}: scenario filters were not accepted - update selftest.py", res.seconds)
            if res.status != "ok":
                self.record(res)
            else:
                self.results.append(res)

    # ── entry point ─────────────────────────────────────────────────────────
    def handle(self, *args, **opts):
        self.results, self.id_cache, self.skipped = [], {}, []
        self.verbose_all = False
        started = datetime.now()
        User = get_user_model()
        self.user = None
        if opts["user"]:
            self.user = User.objects.filter(username=opts["user"]).first()
        else:
            for p in UserProfile.objects.filter(is_app_admin=True).order_by("user_id"):
                self.user = User.objects.filter(username=p.user_login_id, is_active=True).first()
                if self.user:
                    break
            self.user = self.user or User.objects.filter(is_superuser=True, is_active=True).first()
        host = next((h for h in settings.ALLOWED_HOSTS if h and h not in ("*",) and not h.startswith(".")), "localhost")
        self.client = APIClient(HTTP_HOST=host)
        self.codes = Counter()
        self.client_errors = []
        if self.user:
            self.client.force_authenticate(self.user)

        self.say("== 1. Environment ==")
        self.environment()
        if not opts["no_tables"]:
            self.say("\n== 2. Tables ==")
            self.tables()
        if self.user:
            self.say("\n== 3. API routes ==")
            self.api(opts["only"], opts["fast"])
            if not opts["only"]:
                self.say("\n== 4. Reports and dashboards with filters ==")
                self.scenarios()

        # ── summary + report ──
        fails = [r for r in self.results if r.status == "fail"]
        warns = [r for r in self.results if r.status == "warn"]
        api = [r for r in self.results if r.area == "api"]
        self.say("\n== Summary ==")
        if self.codes:
            self.say("HTTP answers: " + ", ".join(f"{c} x{n}" for c, n in sorted(self.codes.items())))
        self.say(f"Checked: {len(self.results)}   ok: {len(self.results) - len(fails) - len(warns)}   warnings: {len(warns)}   failures: {len(fails)}")
        if self.skipped:
            self.say(f"Skipped {len(self.skipped)} routes (several ids needed or no sample record).")
        slow = sorted((r for r in api), key=lambda r: -r.seconds)[:5]
        self.say("Slowest: " + "; ".join(f"{r.name} {r.seconds:.1f}s" for r in slow))

        causes = Counter()
        for r in fails:
            causes[_error_line(r.trace) or r.detail] += 1
        if causes:
            self.say("\nFailures by cause:")
            for cause, n in causes.most_common():
                self.say(self.style.ERROR(f"  {n}x  {cause}"))

        path = f"selftest_report_{started:%Y%m%d_%H%M%S}.txt"
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"SerosIT self test - {started:%Y-%m-%d %H:%M:%S}\nDatabase: {connection.vendor} / {connection.settings_dict['NAME']}\n")
            f.write(f"Checked {len(self.results)}; warnings {len(warns)}; failures {len(fails)}\n\n")
            for title, items in (("FAILURES", fails), ("WARNINGS", warns)):
                f.write(f"===== {title} =====\n")
                for r in items:
                    f.write(f"\n[{r.area}] {r.name}\n  {r.detail}\n")
                    where = _last_project_frame(r.trace)
                    if where:
                        f.write(f"  at {where}\n")
                    if r.trace:
                        f.write("  " + _short_trace(r.trace).replace("\n", "\n  ") + "\n")
                f.write("\n")
            if self.client_errors:
                f.write("===== ROUTES THAT ANSWERED 400/404 (usually need filters; check any that should open on their own) =====\n" + "\n".join(self.client_errors) + "\n\n")
            if self.skipped:
                f.write("===== SKIPPED =====\n" + "\n".join(self.skipped) + "\n")
        self.say(f"\nFull report with tracebacks: {path}")
        if fails:
            raise SystemExit(1)
