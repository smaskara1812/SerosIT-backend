"""Read-only load test of QHSE page-open and report endpoints.

Authenticates in-process with Django's test client. No tokens are printed.
"""
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model
from django.db import close_old_connections
from rest_framework.test import APIClient

from core.models import UserProfile

CONCURRENCY = 8
REQUESTS = 32
HEAVY_CONCURRENCY = 4
HEAVY_REQUESTS = 8


def admin_user():
    User = get_user_model()
    for profile in UserProfile.objects.filter(is_app_admin=True).order_by("user_id"):
        user = User.objects.filter(username=profile.user_login_id, is_active=True).first()
        if user:
            return user
    return None


def percentile(values, pct):
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * pct
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def hit(user, path):
    close_old_connections()
    client = APIClient(HTTP_HOST="localhost")
    client.force_authenticate(user=user)
    started = time.perf_counter()
    try:
        response = client.get(path)
        elapsed_ms = (time.perf_counter() - started) * 1000
        size = len(response.content or b"")
        return response.status_code, elapsed_ms, size
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        return f"ERR:{type(exc).__name__}", elapsed_ms, 0
    finally:
        close_old_connections()


def run_load(user, name, path, concurrency, requests_n):
    # One warmup so the first measured call is not a cold import/query-plan hit.
    hit(user, path)
    samples = []
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(hit, user, path) for _ in range(requests_n)]
        for future in as_completed(futures):
            samples.append(future.result())
    wall = time.perf_counter() - started
    times = [s[1] for s in samples]
    statuses = {}
    for code, _, _ in samples:
        statuses[str(code)] = statuses.get(str(code), 0) + 1
    ok = sum(1 for code, _, _ in samples if code == 200)
    sizes = [s[2] for s in samples if s[0] == 200]
    return {
        "name": name,
        "path": path,
        "n": requests_n,
        "concurrency": concurrency,
        "ok": ok,
        "statuses": statuses,
        "wall": wall,
        "rps": requests_n / wall if wall else 0,
        "min": min(times),
        "p50": percentile(times, 0.50),
        "p95": percentile(times, 0.95),
        "p99": percentile(times, 0.99),
        "max": max(times),
        "mean": statistics.fmean(times),
        "bytes": int(statistics.fmean(sizes)) if sizes else 0,
    }


def fmt_ms(value):
    return f"{value:8.0f}" if value is not None else "     n/a"


def print_row(row):
    status = ",".join(f"{k}:{v}" for k, v in sorted(row["statuses"].items()))
    print(
        f"{row['name']:<32} {row['ok']:>3}/{row['n']:<3} "
        f"{fmt_ms(row['p50'])} {fmt_ms(row['p95'])} {fmt_ms(row['max'])} "
        f"{row['rps']:6.1f} {row['bytes']/1024:8.1f}  {status}  {row['path']}"
    )


def discover(user):
    client = APIClient(HTTP_HOST="localhost")
    client.force_authenticate(user=user)
    extra = []

    incidents = client.get("/api/qhse/incidents/?page=1")
    incident_id = None
    if incidents.status_code == 200:
        results = incidents.data.get("results") if isinstance(incidents.data, dict) else None
        if results:
            incident_id = results[0].get("incident_id")
    if incident_id:
        extra.append(("Incident Root Cause", f"/api/qhse/incident-root-causes/?incident={incident_id}"))
        extra.append(("Incident Actions", f"/api/qhse/incident-actions/?incident={incident_id}"))

    meta = client.get("/api/qhse/mis-hse-review/meta/")
    if meta.status_code == 200 and isinstance(meta.data, dict):
        data_range = meta.data.get("data_range") or {}
        month = data_range.get("max_month") or data_range.get("latest") or data_range.get("to")
        # Fall back to any YYYY-MM-looking value in the payload.
        if not month:
            import json
            blob = json.dumps(meta.data)
            import re
            found = re.findall(r"20\d{2}-\d{2}", blob)
            month = found[-1] if found else None
        if month and len(str(month)) >= 7:
            month = str(month)[:7]
            extra.append((
                "Monthly HSE Review report",
                f"/api/qhse/mis-hse-review/?period_type=MONTHLY&month={month}&filter_type=SEROS",
            ))

    categories = client.get("/api/qhse/training-report/categories/")
    if categories.status_code == 200 and isinstance(categories.data, list) and categories.data:
        first = categories.data[0]
        category = first.get("id") or first.get("value") or first.get("qhse_category_id") or first.get("category")
        if category:
            extra.append((
                "Training Report preview",
                f"/api/qhse/training-report/preview/?report_type=Training_Matrix&category={category}",
            ))

    rigs = client.get("/api/masters/rigs/?page_size=5&fields=rig_id,rig_name")
    rig_id = None
    if rigs.status_code == 200:
        rows = rigs.data.get("results") if isinstance(rigs.data, dict) else rigs.data
        if rows:
            rig_id = rows[0].get("rig_id")
    if rig_id:
        extra.append((
            "HSE Drill Report export",
            f"/api/qhse/hse-drill-report/export/?period=ANNUAL&year=2025&rigs={rig_id}",
        ))
    return extra


def main():
    import logging
    logging.getLogger("django.db.backends").setLevel(logging.WARNING)
    logging.getLogger("django.request").setLevel(logging.ERROR)
    user = admin_user()
    if user is None:
        print("NO_ACTIVE_ADMIN_USER")
        return

    pages = [
        ("Rig Certificates", "/api/qhse/rig-certificates/?page=1"),
        ("Rig Certificate Schedule", "/api/qhse/rig-certificate-schedule/?page=1"),
        ("Activity Monitor", "/api/qhse/activity-monitor/?page=1"),
        ("Activity Closure Analysis", "/api/qhse/activity-closure-analysis/"),
        ("Incident Details", "/api/qhse/incidents/?page=1"),
        ("Incident Details meta", "/api/qhse/incidents/meta/"),
        ("Incident Register", "/api/qhse/incident-register/?page=1&page_size=50"),
        ("Incident Register meta", "/api/qhse/incident-register/meta/"),
        ("Hazard ID Card", "/api/qhse/hazard-id-card/?page=1"),
        ("Hazard ID Card meta", "/api/qhse/hazard-id-card/meta/"),
        ("MIS Monthly HSE Return", "/api/qhse/mis-hse-return/?page=1"),
        ("Monthly HSE Review meta", "/api/qhse/mis-hse-review/meta/"),
        ("HSE Drills / Exercises", "/api/qhse/hse-drill-record/?page=1"),
        ("HSE Drills meta", "/api/qhse/hse-drill-record/meta/"),
        ("HSE Weekly Drill", "/api/qhse/hse-weekly-drill/?page=1"),
        ("HSE Weekly Drill meta", "/api/qhse/hse-weekly-drill/meta/"),
        ("Leading Indicators", "/api/qhse/leading-indicators/?page=1"),
        ("Lagging Indicators", "/api/qhse/lagging-indicators/?page=1"),
        ("Corrective Actions", "/api/qhse/corrective-actions/?page=1"),
        ("Training Group", "/api/qhse/training-group/?page=1"),
        ("Training Org", "/api/qhse/training-org/?page=1"),
        ("Cert to Rank Mapping", "/api/qhse/cert-to-rank-mapping/?page=1"),
        ("Training Log", "/api/qhse/training-log/?page=1"),
        ("Training Report categories", "/api/qhse/training-report/categories/"),
        ("Shared rig dropdown", "/api/masters/rigs/?page_size=200&fields=rig_id,rig_name"),
    ]

    print(f"PAGE_OPEN concurrency={CONCURRENCY} requests={REQUESTS}")
    print(f"{'page':<32} {'ok':>7} {'p50ms':>8} {'p95ms':>8} {'maxms':>8} {'rps':>6} {'KB':>8}  status")
    rows = []
    for name, path in pages:
        row = run_load(user, name, path, CONCURRENCY, REQUESTS)
        rows.append(row)
        print_row(row)

    heavy = discover(user)
    print()
    print(f"REPORTS concurrency={HEAVY_CONCURRENCY} requests={HEAVY_REQUESTS}")
    print(f"{'page':<32} {'ok':>7} {'p50ms':>8} {'p95ms':>8} {'maxms':>8} {'rps':>6} {'KB':>8}  status")
    heavy_rows = []
    for name, path in heavy:
        row = run_load(user, name, path, HEAVY_CONCURRENCY, HEAVY_REQUESTS)
        heavy_rows.append(row)
        print_row(row)

    # Mixed: every page-open endpoint at once, round-robin, for a fixed request budget.
    mix_n = 80
    mix_paths = [path for _, path in pages]
    print()
    print(f"MIXED page-open concurrency={CONCURRENCY} requests={mix_n}")
    started = time.perf_counter()

    def mixed_hit(i):
        return hit(user, mix_paths[i % len(mix_paths)])

    mix_samples = []
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = [pool.submit(mixed_hit, i) for i in range(mix_n)]
        for future in as_completed(futures):
            mix_samples.append(future.result())
    wall = time.perf_counter() - started
    times = [s[1] for s in mix_samples]
    ok = sum(1 for code, _, _ in mix_samples if code == 200)
    statuses = {}
    for code, _, _ in mix_samples:
        statuses[str(code)] = statuses.get(str(code), 0) + 1
    print(
        f"mixed ok={ok}/{mix_n} p50={percentile(times, 0.50):.0f}ms "
        f"p95={percentile(times, 0.95):.0f}ms max={max(times):.0f}ms "
        f"rps={mix_n / wall:.1f} statuses={statuses}"
    )

    slow = sorted(rows + heavy_rows, key=lambda r: r["p95"], reverse=True)[:8]
    print()
    print("SLOWEST_P95")
    for row in slow:
        print(f"{row['p95']:.0f}ms  {row['name']}  ok={row['ok']}/{row['n']}  {row['statuses']}")


if __name__ == "__main__":
    main()
