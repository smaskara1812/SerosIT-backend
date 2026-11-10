"""Proves that the batched Rig Performance Masters page (the rate sheet) gives exactly the same answer as working the rigs one by one, also for the cases the real
data barely holds: plans with and without weights (carried over from an earlier month), planned moves (ILM with and without km, IPM), closed months (by a person
and by the system), ILM terms, long audit histories. Everything runs in one transaction that is rolled back.

    cd backend
    .venv/bin/python scripts/check_rig_performance_batching.py
"""
import datetime, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django; django.setup()
from decimal import Decimal
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from core import rig_performance_month as m
from core import rig_performance_views as v
from core.models import IlmRateTerm, ProjectContractDtl, RigMonthPlan, RigPlannedMove, SysAuditLog, UserProfile

class Rollback(Exception): pass
fails = []
def ok(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {detail}" if not cond else ""))
    if not cond: fails.append(name)

def norm(d): return json.loads(json.dumps(d, sort_keys=True, default=str))

def first_diff(a, b, path=""):
    if type(a) != type(b): return f"{path}: {a!r} vs {b!r}"
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b: return f"{path}/{k}: missing on one side"
            r = first_diff(a[k], b[k], f"{path}/{k}")
            if r: return r
    elif isinstance(a, list):
        if len(a) != len(b): return f"{path}: {len(a)} vs {len(b)} items"
        for i, (x, y) in enumerate(zip(a, b)):
            r = first_diff(x, y, f"{path}[{i}]")
            if r: return r
    elif a != b: return f"{path}: {a!r} vs {b!r}"

try:
    with transaction.atomic():
        now = timezone.now()
        rigs = sorted({ln.rig_id for ln in ProjectContractDtl.objects.all()})[:14]
        pairs = sorted({(ln.rig_id, ln.contract_id) for ln in ProjectContractDtl.objects.filter(rig_id__in=rigs)})
        user = UserProfile.objects.order_by("user_id").first()
        months = [datetime.date(2026, mo, 1) for mo in range(1, 12)]
        n = 0
        for i, rid in enumerate(rigs):
            for j, mo in enumerate(months):
                kind = (i + j) % 4
                if kind == 3 or RigMonthPlan.objects.filter(rig_id=rid, month=mo).exists():
                    continue  # no plan this month (or the real data already has one)
                plan = RigMonthPlan.objects.create(
                    rig_id=rid, month=mo, cr_dt=now, note="" if kind == 0 else "note",
                    r1_pct=Decimal(70 + i % 5) if kind == 1 else None, r2_pct=Decimal(20) if kind == 1 else None, r3_pct=Decimal(10 - i % 5) if kind == 1 else None,
                    non_ilm_days=Decimal(20 + j) if kind == 2 and j % 2 else None,
                    closed_on=mo + datetime.timedelta(days=40) if (i + j) % 5 == 0 else None, closed_by=(user.user_id if user and i % 2 else None), closed_note="closed",
                )
                n += 1
                if (i + j) % 3 == 0:
                    RigPlannedMove.objects.create(plan=plan, move_rate_id=6, planned_hours=Decimal(18 + j), planned_km=Decimal(35 + i) if i % 2 else None)
                    RigPlannedMove.objects.create(plan=plan, move_rate_id=7 + (j % 2), planned_hours=Decimal(6))
                if (i + j) % 4 == 0:
                    for k in range(15):  # more than the 12 shown
                        SysAuditLog.objects.create(username="zzu", action="update", entity="x", target_table="rig_month_plan", target_pk=str(plan.pk), kind="change", changes={"note": {"old": str(k), "new": str(k + 1)}}, note=f"n{k}")
                    SysAuditLog.objects.create(username="zzu", action="event", entity="x", target_table="rig_month_plan", target_pk=str(plan.pk), kind="event")
        for i, (rid, cid) in enumerate(pairs):
            if i % 3 == 0 and not IlmRateTerm.objects.filter(rig_id=rid, contract_id=cid).exists():
                IlmRateTerm.objects.create(rig_id=rid, contract_id=cid, upto_km=Decimal(30), flat_amount=Decimal(5000000) if i % 2 else None, extra_per_km=Decimal(50000), cr_dt=now)
        print(f"made {n} plans for {len(rigs)} rigs over {len(months)} months")

        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        import calendar
        same = qa = qb = 0
        for first in [datetime.date(2025, 6, 1), datetime.date(2025, 12, 1), *months]:
            last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
            end = min(last, yesterday)
            with CaptureQueriesContext(connection) as q1:
                one_by_one = norm(v._rate_sheet_payload(first, end))  # no cache, no batching: each rig asks for itself
            with CaptureQueriesContext(connection) as q2:
                batched = norm(v.rate_sheet_payload(first, end))
            d = first_diff(one_by_one, batched, str(first))
            qa += len(q1); qb += len(q2)
            same += d is None
            if d: print("   DIFF", d)
        total = 2 + len(months)
        ok(f"every month is identical, batched or one by one ({same} of {total})", same == total)
        ok("the batched way asks the database far less", qb * 3 < qa, f"{qa} -> {qb}")
        print(f"   queries over {total} months: {qa} one by one -> {qb} batched")
        allrows = [r for mo in months for r in norm(v.rate_sheet_payload(mo, min(mo.replace(day=28), yesterday)))["rigs"]]
        ok("plans were really exercised", any(r["plan"]["exists"] for r in allrows), f"{len(allrows)} rig-months")
        ok("planned moves were really exercised", any(r["planned_moves"] for r in allrows))
        ok("closed months were really exercised", any(r["closed"] for r in allrows))
        ok("long histories were really exercised", any(len(r["history"]) == 12 for r in allrows))
        sample = {"rigs": allrows}
        ok("history shows at most 12 changes", all(len(r["history"]) <= 12 for r in sample["rigs"]))
        ok("a weight carried over from an earlier month shows up", any("carried over" in r["weights_source"] for r in allrows))
        raise Rollback()
except Rollback:
    pass
print("\n" + ("ALL OK" if not fails else f"{len(fails)} FAILED: {fails}"))
sys.exit(1 if fails else 0)
