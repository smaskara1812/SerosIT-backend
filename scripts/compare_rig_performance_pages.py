"""Records, or compares against, the exact output of the two Rig Performance pages (the report and the rate sheet) for every month, so a speed-up can be proved
not to change any number. `record <file>` writes the output; `compare <file>` runs again and lists every difference (and the query counts, before and after).

    cd backend
    .venv/bin/python scripts/compare_rig_performance_pages.py record /path/baseline.json
    .venv/bin/python scripts/compare_rig_performance_pages.py compare /path/baseline.json
"""
import calendar, datetime, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django; django.setup()
from django.db import connection
from django.test.utils import CaptureQueriesContext
from core import rig_performance_views as v


def months():
    today = datetime.date.today()
    y, mo = 2023, 1
    while (y, mo) <= (today.year, today.month + 1 if today.month < 12 else 12):
        yield datetime.date(y, mo, 1)
        mo += 1
        if mo == 13:
            y, mo = y + 1, 1


def run():
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    out, stats = {}, {}
    for first in months():
        last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
        end = min(last, yesterday)
        for name, fn in (("sheet", v.rate_sheet_payload), ("report", v.report_payload)):
            with CaptureQueriesContext(connection) as q:
                t = time.perf_counter()
                data = fn(first, end)
                ms = (time.perf_counter() - t) * 1000
            out[f"{name} {first:%Y-%m}"] = json.loads(json.dumps(data, sort_keys=True, default=str))
            stats[f"{name} {first:%Y-%m}"] = (len(q), round(ms))
    return out, stats


def diff(a, b, path=""):
    if type(a) != type(b):
        yield f"{path}: {a!r} -> {b!r}"
    elif isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                yield f"{path}/{k}: only in {'new' if k in b else 'old'}"
            else:
                yield from diff(a[k], b[k], f"{path}/{k}")
    elif isinstance(a, list):
        if len(a) != len(b):
            yield f"{path}: {len(a)} items -> {len(b)} items"
        for i, (x, y) in enumerate(zip(a, b)):
            yield from diff(x, y, f"{path}[{i}]")
    elif a != b:
        yield f"{path}: {a!r} -> {b!r}"


if __name__ == "__main__":
    mode, path = sys.argv[1], sys.argv[2]
    out, stats = run()
    if mode == "record":
        json.dump({"out": out, "stats": stats}, open(path, "w"))
        print(f"recorded {len(out)} pages; queries: sheet {sum(c for k, (c, _) in stats.items() if k.startswith('sheet'))}, report {sum(c for k, (c, _) in stats.items() if k.startswith('report'))}")
    else:
        old = json.load(open(path))
        bad = 0
        for k in out:
            for d in diff(old["out"][k], out[k], k):
                bad += 1
                if bad <= 40:
                    print("DIFF", d)
        for kind in ("sheet", "report"):
            before = sum(c for k, (c, _) in old["stats"].items() if k.startswith(kind))
            after = sum(c for k, (c, _) in stats.items() if k.startswith(kind))
            t0 = sum(m for k, (_, m) in old["stats"].items() if k.startswith(kind))
            t1 = sum(m for k, (_, m) in stats.items() if k.startswith(kind))
            print(f"{kind:7} queries {before} -> {after}   time {t0} ms -> {t1} ms")
        print("IDENTICAL" if not bad else f"{bad} DIFFERENCES")
        sys.exit(1 if bad else 0)
