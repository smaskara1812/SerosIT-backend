"""Reports > Rig Performance: the Rig Performance workbook shown as tables on the page (what the hand-made Excel file showed each day), for a chosen month and
year, and the rate sheet behind its projection (what the Master Rate Sheet showed). Read-only; the numbers come from core/rig_performance_month.py, the same
code that builds the Excel file mailed every day. Rights are the pages' own (menu keys reports.rig_performance and reports.rig_performance_masters):
View to see, Export (on the report) to download the Excel file. The Masters page is also where the month's inputs are changed (Edit on
reports.rig_performance_masters): the rig's planned moves (in hours), normal days and weights (Rig Month Plans) and its ILM terms (ILM Rate Terms), saved through the same
checks as the Masters pages and recorded in the audit history."""

import calendar
import datetime
from decimal import Decimal

from django.http import HttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import audit as _audit
from . import rig_performance_month as m
from .masters_serializers import IlmRateTermSerializer, RigMonthPlanSerializer
from .models import IlmRateTerm, MstDrillingRate, MstRig, ProjectContract, RigMonthPlan, SysAuditLog, UserProfile
from .permissions import holds_a_right_on

KEY_REPORT = "reports.rig_performance"
KEY_MASTERS = "reports.rig_performance_masters"
MIN_YEAR = 2020


def _f(v, nd=None):
    if v is None:
        return None
    return round(float(v), nd) if nd is not None else float(v)


def _month(request):
    """(first day of the month, last day reported) from ?month=YYYY-MM (default: the month of yesterday), or (None, error)."""
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    raw = (request.query_params.get("month") or "").strip()
    if not raw:
        first = yesterday.replace(day=1)
    else:
        try:
            first = datetime.datetime.strptime(raw + "-01", "%Y-%m-%d").date()
        except ValueError:
            return None, "Choose a month and a year."
    if first.year < MIN_YEAR:
        return None, "Choose a later year."
    last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
    return first, min(last, yesterday)


def report_payload(first, end):
    """The report page as data: a table per rig, the FINAL table, the notes."""
    if end < first:
        return {"month": f"{first:%Y-%m}", "label": f"{first:%B %Y}", "end": None, "rigs": [], "final": None, "notes": [], "message": f"{first:%B %Y} has not started: there is nothing to show yet."}
    data = m.collect(end)
    if not data["rigs"]:
        return {"month": f"{first:%Y-%m}", "label": f"{first:%B %Y}", "end": end.isoformat(), "rigs": [], "final": None, "notes": [], "message": f"There is no daily drilling report for any rig in {first:%B %Y}."}
    rigs = []
    for rg in data["rigs"]:
        totals = {c: Decimal(0) for c in rg["cols"]}
        rows = []
        grand = Decimal(0)
        for r in rg["rows"]:
            if not r["reported"]:
                rows.append({"date": r["day"].isoformat(), "reported": False})
                continue
            for c in rg["cols"]:
                totals[c] += r["hours"][c]
            grand += r["total"]
            rows.append({
                "date": r["day"].isoformat(), "reported": True, "hours": [_f(r["hours"][c]) if r["hours"][c] else None for c in rg["cols"]], "total": _f(r["total"]),
                "productivity": _f(r["prod"], 4), "revenue": _f(r["revenue"], 4), "ilm_missing": bool(r.get("ilm_missing")),
            })
        rigs.append({"name": rg["name"], "cols": rg["cols"], "rows": rows, "totals": [_f(totals[c]) if totals[c] else None for c in rg["cols"]], "total": _f(grand), "avg_productivity": _f(rg["avg_prod"], 4), "revenue": _f(rg["revenue"], 4)})
    # FINAL: a row per day, as the FINAL sheet
    n = len(data["rigs"])
    days = []
    for idx, day in enumerate(data["days"]):
        prods, revs, hsd = [], [], []
        total_rev = Decimal(0)
        any_prod = []
        for rg in data["rigs"]:
            r = rg["rows"][idx]
            if not r["reported"]:
                prods.append(None), revs.append(None), hsd.append(None)
                continue
            prods.append(_f(r["prod"], 4))
            revs.append(_f(r["revenue"], 4))
            total_rev += r["revenue"]
            if r["prod"] is not None:
                any_prod.append(r["prod"])
            hsd.append({"litres": r["litres"], "cost": _f(r.get("cost"), 4), "closing": _f(r.get("closing"))})
        days.append({"date": day.isoformat(), "productivity": prods, "avg": _f(sum(any_prod, Decimal(0)) / len(any_prod), 4) if any_prod else None, "revenue": revs, "total": _f(total_rev, 4) if any_prod else None, "hsd": hsd})
    targets = [_f(r["setting"]["target"] / 100, 4) for r in data["rigs"]]
    avgs = [r["avg_prod"] for r in data["rigs"] if r["avg_prod"] is not None]
    overall = sum(avgs, Decimal(0)) / len(avgs) if avgs else None
    avg_target = sum((r["setting"]["target"] for r in data["rigs"]), Decimal(0)) / n / 100
    projections = [_f(r["projection"], 4) for r in data["rigs"]]
    proj_total = sum((r["projection"] for r in data["rigs"] if r["projection"] is not None), Decimal(0))
    total_rev = sum((r["revenue"] for r in data["rigs"]), Decimal(0))
    final = {
        "rigs": [r["name"] for r in data["rigs"]], "targets": targets, "avg_target": _f(avg_target, 4), "projections": projections, "projection_total": _f(proj_total, 4) if proj_total else None,
        "days": days,
        "totals": {
            "productivity": [_f(r["avg_prod"], 4) for r in data["rigs"]], "avg": _f(overall, 4), "revenue": [_f(r["revenue"], 4) for r in data["rigs"]], "total": _f(total_rev, 4),
            "hsd": [{"litres": int(r["litres"]), "cost": _f(r["cost"], 4)} for r in data["rigs"]],
        },
        "actual_vs_target": [_f(r["avg_prod"] / (r["setting"]["target"] / 100), 4) if r["avg_prod"] is not None else None for r in data["rigs"]],
        "actual_vs_target_avg": _f(overall / avg_target, 4) if overall is not None and avg_target else None,
        "revenue_vs_projection": [_f(r["revenue"] / r["projection"], 4) if r["projection"] else None for r in data["rigs"]],
        "revenue_vs_projection_total": _f(total_rev / proj_total, 4) if proj_total else None,
    }
    return {
        "month": f"{first:%Y-%m}", "label": f"{first:%B %Y}", "end": end.isoformat(), "rigs": rigs, "final": final,
        "notes": [{"text": t, "heading": b} for t, b in m.notes_lines(data) if t],
    }


RECENT_REPORT_DAYS = 60  # a rig that reported within this many days before the month is still working
NEW_LINE_DAYS = 45  # a rig whose project line started within this many days before the month's end is starting (it may not have reported yet)


def rate_sheet_rigs(first, last, ref):
    """The rigs of the rate sheet for a month: the drilling rigs that are on a project line overlapping the month AND are working (reported in the month or in the
    60 days before it) or are just starting (the line began within 45 days of the month's end), plus every rig that reported in the month even when its project
    line does not cover it. Rigs with an old open-ended line and no recent report are left out (they would only be noise). Returns ([(rig id, name)] in rig
    order, ids of the rigs that reported in the month)."""
    from django.db.models import Max

    from .dashboard_access import dashboard_rig_queryset
    from .models import DrillingDtl, ProjectContractDtl

    reported = set(DrillingDtl.objects.filter(drilling_dtl_dt__gte=first, drilling_dtl_dt__lte=ref).values_list("rig_id", flat=True)) if ref >= first else set()
    drilling_rigs = set(dashboard_rig_queryset().values_list("rig_id", flat=True))
    lines = {}
    for ln in ProjectContractDtl.objects.filter(rig_active_from__lte=last, rig_id__in=drilling_rigs).select_related("contract"):
        ends = ln.rig_active_to or ln.contract.prj_end_dt
        if ends is None or ends >= first:
            cur = lines.get(ln.rig_id)
            if cur is None or ln.rig_active_from > cur:
                lines[ln.rig_id] = ln.rig_active_from  # the latest start of its lines in the month
    recent_from = first - datetime.timedelta(days=RECENT_REPORT_DAYS)
    last_report = {r["rig_id"]: r["m"] for r in DrillingDtl.objects.filter(rig_id__in=lines.keys(), drilling_dtl_dt__lte=max(ref, first)).values("rig_id").annotate(m=Max("drilling_dtl_dt"))}
    starting_from = last - datetime.timedelta(days=NEW_LINE_DAYS)
    working = {rid for rid, started in lines.items() if rid in reported or (last_report.get(rid) and last_report[rid] >= recent_from) or started >= starting_from}
    return [(r.rig_id, r.rig_name) for r in MstRig.objects.filter(pk__in=reported | working).order_by("rig_id")], reported


def rate_sheet_payload(first, end):
    with m.read_cache():  # the same plan, rates and terms are asked for again and again while the rigs are worked out: ask the database once
        return _rate_sheet_payload(first, end)


def _rate_sheet_payload(first, end):
    """The rate sheet behind the projection: per rig the rates per day, the weights, the normal day, the days, the ILM block and the projection. A rig is
    listed when it is on a project in the month (even before its first report) or has reported in it, so the month can be planned from its first day."""
    today = datetime.date.today()
    if first > today.replace(day=1):
        return {"month": f"{first:%Y-%m}", "label": f"{first:%B %Y}", "rigs": [], "message": f"{first:%B %Y} has not started: there is nothing to show yet."}
    last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
    ref = max(first, end)  # the day the project and its rates are looked up for: the last day reported, or the 1st when nothing is reported yet
    codes = {r.drilling_rate_id: (r.rate_code or "").strip() for r in MstDrillingRate.objects.all()}
    rigs, reported_ids = rate_sheet_rigs(first, last, ref)
    m.prefetch_rigs([rid for rid, _n in rigs], first)  # everything per rig below is read for all the rigs together, a few queries in all
    contracts = {rid: m.current_contract(rid, ref) for rid, _n in rigs}
    numbers = dict(ProjectContract.objects.filter(pk__in={c for c in contracts.values() if c}).values_list("pk", "prj_contract_no"))
    plans = {rid: m.plan_for(rid, first) for rid, _n in rigs}
    histories = _histories([pl for pl in plans.values() if pl is not None])
    closers = dict(UserProfile.objects.filter(user_id__in={pl.closed_by for pl in plans.values() if pl is not None and pl.closed_on is not None and pl.closed_by}).values_list("user_id", "user_login_id"))
    out = []
    for rig_id, name in rigs:
        # Only the rig's plan and its projection are needed here. They used to be taken from m.collect(), which also works out every day's hours, revenue and diesel for
        # every rig (the whole Rig Performance report); the projection it holds is the very call made below (same rig, project, month, plan and moves), so the numbers are the same.
        contract = contracts[rig_id]
        plan = plans[rig_id]
        pj = m.projection_for(rig_id, contract, first, last, plan)
        rates = m.contract_rates(rig_id, contract) if contract else {}
        weights = pj["weights"] or (Decimal(85), Decimal(15), Decimal(0))
        weighted = {m.RATE_R1: weights[0], m.RATE_R2: weights[1], m.RATE_R3: weights[2]}
        lines = []
        for rid in (m.RATE_R1, m.RATE_R2, m.RATE_R3):
            per_day = rates.get(rid, Decimal(0)) * 24
            lines.append({"code": codes.get(rid, str(rid)), "per_day": _f(per_day), "weight": _f(weighted[rid]), "for_revenue": _f(per_day * weighted[rid] / 100)})
        others = [{"code": codes.get(rid, str(rid)), "per_day": _f(rate * 24)} for rid, rate in sorted(rates.items()) if rid not in (m.RATE_R1, m.RATE_R2, m.RATE_R3) and rid not in m.NO_MONEY_RATES and rate]
        contract_no = numbers.get(contract) if contract else None
        term = rg_term(rig_id, contract)
        reported = rig_id in reported_ids
        out.append({
            "name": name, "contract": contract_no, "problem": pj["problem"], "weights_source": pj["weights_source"], "rates": lines, "other_rates": others, "normal_day": _f(pj["normal_day"]), "reported": reported,
            "days_on_project": pj["days"], "from": pj["start"].isoformat() if pj["start"] else None, "to": pj["end"].isoformat() if pj["end"] else None,
            "ilm_hours": _f(pj["ilm_hours"]), "ilm_days": _f(pj["ilm_days"], 2), "non_ilm_days": _f(pj["non_ilm_days"]), "normal_total": _f(pj["non_ilm_days"] * pj["normal_day"]) if pj["normal_day"] is not None else None,
            "normal_total_cr": _f(pj["non_ilm_days"] * pj["normal_day"] / m.CRORE, 4) if pj["normal_day"] is not None else None,
            "rig_id": rig_id, "contract_id": contract,
            "moves": [
                {"date": mv["date"].isoformat(), "well": mv["well"], "type": mv["type"], "km": _f(mv["km"]), "amount": _f(mv["amount"]), "hours": _f(mv["hours"]), "hours_month": _f(mv["hours_month"]),
                 "mis_hour": _f(mv["mis_hour"]), "note": mv["note"]} for mv in pj["moves"]
            ],
            "planned_moves": [
                {"rate_id": p["rate_id"], "type": p["type"], "hours": _f(p["hours"]), "km": _f(p["km"]), "km_source": p["km_source"], "amount": _f(p["amount"]), "mis_hour": _f(p["mis_hour"]), "note": p["note"], "text": p["text"]}
                for p in pj["planned"]
            ],
            "warnings": pj["warnings"],
            "closed": _closed_info(plan, closers),
            "can_close": reported and end >= last and not (plan and plan.closed_on),
            "history": histories.get(plan.pk, []) if plan is not None else [],
            "plan": {
                "exists": plan is not None, "moves": [{"rate_id": pm.move_rate_id, "hours": _f(pm.planned_hours), "km": _f(pm.planned_km), "note": pm.note} for pm in m.planned_moves_of(plan)], "non_ilm_days": _f(plan.non_ilm_days) if plan else None,
                "r1_pct": _f(plan.r1_pct) if plan else None, "r2_pct": _f(plan.r2_pct) if plan else None, "r3_pct": _f(plan.r3_pct) if plan else None,
                "weights_source": pj["weights_source"], "weights": [_f(w) for w in pj["weights"]] if pj["weights"] else None,
                "note": plan.note if plan else "",
            },
            "auto_days": max(0, rg_days(pj)),
            "ilm": {
                "term": term, "km": _f(pj["km"]), "amount": _f(pj["ilm_amount"]), "amount_cr": _f(pj["ilm_amount"] / m.CRORE, 4) if pj["ilm_amount"] is not None else None,
                "note": pj["ilm_note"],
            },
            "projection_cr": _f(pj["value"], 4),
        })
    return {"month": f"{first:%Y-%m}", "label": f"{first:%B %Y}", "rigs": out, "message": "" if out else f"No rig is on a project in {first:%B %Y}, and none has reported."}


def _closed_info(plan, users=None):
    """`users` = {user id: login id} when the people of several plans were looked up together."""
    if plan is None or plan.closed_on is None:
        return None
    if not plan.closed_by:
        who = "the system"
    elif users is not None:
        who = users.get(plan.closed_by)
    else:
        who = UserProfile.objects.filter(user_id=plan.closed_by).values_list("user_login_id", flat=True).first()
    return {"on": plan.closed_on.isoformat(), "by": who or "", "note": plan.closed_note}


def _history(plan):
    """The recent changes of the plan row (who, when, what), from the audit history."""
    if plan is None:
        return []
    return _history_rows(SysAuditLog.objects.filter(target_table="rig_month_plan", target_pk=str(plan.pk), kind="change").order_by("-ts")[:12])


def _history_rows(rows):
    out = []
    for r in rows:
        ch = {k: v for k, v in (r.changes or {}).items() if k in ("planned_moves", "non_ilm_days", "r1_pct", "r2_pct", "r3_pct", "closed_on", "note")}
        out.append({"when": r.ts.isoformat(timespec="minutes"), "who": r.username or "", "action": r.action, "changes": ch, "note": r.note})
    return out


def _histories(plans):
    """{plan id: the plan's recent changes} for several plans, read together (the same as _history for each)."""
    if not plans:
        return {}
    by_plan = {}
    for r in SysAuditLog.objects.filter(target_table="rig_month_plan", target_pk__in=[str(pl.pk) for pl in plans], kind="change").order_by("-ts"):
        by_plan.setdefault(r.target_pk, []).append(r)
    return {pl.pk: _history_rows(by_plan.get(str(pl.pk), [])[:12]) for pl in plans}


def rg_days(pj):
    return int(pj["days"] - pj["ilm_days"])


def rg_term(rig_id, contract):
    t = m.ilm_term_of(rig_id, contract) if contract else None
    return None if t is None else {"id": t.term_id, "upto_km": _f(t.upto_km), "flat_amount": _f(t.flat_amount), "extra_per_km": _f(t.extra_per_km), "note": t.note}


def _deny(request, key, flag="view"):
    return None if holds_a_right_on(request, [key], flags=(flag,)) else Response({"detail": "You do not have the right to open this page."}, status=403)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def report_api(request):
    denied = _deny(request, KEY_REPORT)
    if denied:
        return denied
    first, end = _month(request)
    if first is None:
        return Response({"detail": end}, status=400)
    return Response(report_payload(first, end))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def report_download_api(request):
    """The month's Excel file, as the daily mail attaches it (Export)."""
    denied = _deny(request, KEY_REPORT, "export")
    if denied:
        return denied
    first, end = _month(request)
    if first is None:
        return Response({"detail": end}, status=400)
    if end < first:
        return Response({"detail": f"{first:%B %Y} has not started."}, status=404)
    data = m.collect(end)
    if not data["rigs"]:
        return Response({"detail": f"There is no daily drilling report for any rig in {first:%B %Y}."}, status=404)
    _audit.record_action(request, "export", KEY_REPORT, f"{first:%Y-%m}", f"Rig Performance {first:%B %Y} downloaded", None)
    r = HttpResponse(m.build_workbook(data), content_type=m.XLSX)
    r["Content-Disposition"] = f'attachment; filename="Rig_Performance-{first:%B}-{first:%Y}.xlsx"'
    r["Cache-Control"] = "no-store"
    return r


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def rate_sheet_api(request):
    denied = _deny(request, KEY_MASTERS)
    if denied:
        return denied
    first, end = _month(request)
    if first is None:
        return Response({"detail": end}, status=400)
    return Response(rate_sheet_payload(first, end))


def _user_id(request):
    p = UserProfile.objects.filter(user_login_id=request.user.username).first()
    return p.user_id if p else None


def _blank(v):
    return None if v is None or str(v).strip() == "" else v


def _save(request, serializer_class, model, lookup, payload, label):
    """Creates or updates the row found by `lookup`, through the serializer (the same checks as the Masters pages), stamps who and when, records the audit entry.
    Returns a Response."""
    existing = model.objects.filter(**lookup).first()
    ser = serializer_class(existing, data=payload)
    if not ser.is_valid():
        return Response({"errors": ser.errors, "detail": next(iter(next(iter(ser.errors.values()))), "Please check the values.") if ser.errors else "Please check the values."}, status=400)
    old = _audit.snapshot(existing) if existing is not None else {}
    uid = _user_id(request)
    if existing is None:
        inst = ser.save(cr_user_id=uid or 1, cr_dt=timezone.now())
    else:
        inst = ser.save(mod_user_id=uid, mod_dt=timezone.now())
    new = _audit.snapshot(inst)
    changes = {k: {"old": old.get(k), "new": v} for k, v in new.items() if old.get(k) != v and not (existing is None and v in (None, ""))}
    if existing is None or changes:
        _audit.record_action(request, "create" if existing is None else "update", KEY_MASTERS, inst.pk, label, changes or None, target=inst)
    return Response({"ok": True, "created": existing is None})


def _rig_month(request):
    """(rig id, first of month) from the body, or (None, error text)."""
    try:
        rig = int(request.data.get("rig"))
        first = datetime.datetime.strptime(str(request.data.get("month", "")) + "-01", "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None, "Choose a rig and a month."
    return (rig, first), None


def _clean_moves(raw, first, rig):
    """[(rate id, hours, km or None, note)] from the request, or (None, error text). Hours are more than 0 and, together, within the hours the rig has in the month."""
    if raw in (None, ""):
        return [], None
    if not isinstance(raw, list) or len(raw) > 20:
        return None, "The planned moves must be a list of at most 20."
    ids = m.move_rate_ids()
    out = []
    for i, row in enumerate(raw, start=1):
        try:
            rate = int(row.get("rate_id"))
            hours = Decimal(str(row.get("hours")))
            km = None if _blank(row.get("km")) is None else Decimal(str(row.get("km")))
        except (TypeError, ValueError, ArithmeticError, AttributeError):
            return None, f"Planned move {i}: enter the type, the hours and (for an ILM) the km as numbers."
        if rate not in ids:
            return None, f"Planned move {i}: choose ILM or IPM."
        if hours <= 0 or hours > 24 * 31:
            return None, f"Planned move {i}: the hours must be more than 0 and within the month."
        if km is not None and km < 0:
            return None, f"Planned move {i}: the km cannot be negative."
        out.append((rate, hours, km, str(row.get("note") or "")[:200]))
    last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
    total = sum((h for _r, h, _k, _n in out), Decimal(0))
    if total > 24 * last.day:
        return None, f"The planned moves together take {total:g} hours; the month has {24 * last.day}."
    return out, None


def _moves_text(rows):
    names = {6: "ILM", 7: "IPM - Lateral", 8: "IPM - Adjacent"}
    return "; ".join(f"{names.get(r, r)} {h:g} h" + (f" {k:g} km" if k is not None else "") for r, h, k, _n in rows) or "none"


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def plan_api(request):
    """Sets the rig's plan for the month (the planned moves in hours, normal days, weights), creating the row when the rig had none."""
    denied = _deny(request, KEY_MASTERS, "edit")
    if denied:
        return denied
    rm, error = _rig_month(request)
    if error:
        return Response({"detail": error}, status=400)
    rig, first = rm
    d = request.data
    payload = {
        "rig": rig, "month": first.isoformat(), "non_ilm_days": _blank(d.get("non_ilm_days")),
        "r1_pct": _blank(d.get("r1_pct")), "r2_pct": _blank(d.get("r2_pct")), "r3_pct": _blank(d.get("r3_pct")), "note": (d.get("note") or "")[:200],
    }
    from django.db import transaction

    from .models import MstRig, RigPlannedMove

    name = MstRig.objects.filter(pk=rig).values_list("rig_name", flat=True).first()
    if name is None:
        return Response({"detail": "Unknown rig."}, status=404)
    moves, error = _clean_moves(d.get("moves"), first, rig)
    if error:
        return Response({"detail": error}, status=400)
    if moves:
        
        last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
        contract = m.current_contract(rig, last)
        on_project = m.project_days(rig, contract, first, last)[2] if contract else 0
        total = sum((h for _r, h, _k, _n in moves), Decimal(0))
        if contract and total > 24 * on_project:
            return Response({"detail": f"The planned moves take {total:g} hours but the rig is on its project for only {on_project} days ({24 * on_project} hours) in {first:%B %Y}."}, status=400)
    with transaction.atomic():
        res = _save(request, RigMonthPlanSerializer, RigMonthPlan, {"rig_id": rig, "month": first}, payload, f"{name} {first:%b %Y}")
        if res.status_code != 200 or d.get("moves") is None:
            return res
        plan = RigMonthPlan.objects.get(rig_id=rig, month=first)
        old = [(pm.move_rate_id, pm.planned_hours, pm.planned_km, pm.note) for pm in plan.planned_moves.all()]
        if [(a, b, c) for a, b, c, _n in old] != [(a, b, c) for a, b, c, _n in moves]:
            plan.planned_moves.all().delete()
            for rate, hours, km, note in moves:
                RigPlannedMove.objects.create(plan=plan, move_rate_id=rate, planned_hours=hours, planned_km=km, note=note)
            _audit.record_action(request, "update", KEY_MASTERS, plan.pk, f"{name} {first:%b %Y}", {"planned_moves": {"old": _moves_text(old), "new": _moves_text(moves)}}, target=plan)
    return res


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def ilm_terms_api(request):
    """Sets the ILM terms of the rig on a project, creating them when it had none."""
    denied = _deny(request, KEY_MASTERS, "edit")
    if denied:
        return denied
    d = request.data
    try:
        rig, contract = int(d.get("rig")), int(d.get("contract"))
    except (TypeError, ValueError):
        return Response({"detail": "Choose a rig and a project."}, status=400)
    payload = {"rig": rig, "contract": contract, "upto_km": d.get("upto_km"), "flat_amount": _blank(d.get("flat_amount")), "extra_per_km": _blank(d.get("extra_per_km")) if _blank(d.get("extra_per_km")) is not None else 0, "note": (d.get("note") or "")[:200]}
    from .models import MstRig

    name = MstRig.objects.filter(pk=rig).values_list("rig_name", flat=True).first()
    no = ProjectContract.objects.filter(pk=contract).values_list("prj_contract_no", flat=True).first()
    if name is None or no is None:
        return Response({"detail": "Unknown rig or project."}, status=404)
    return _save(request, IlmRateTermSerializer, IlmRateTerm, {"rig_id": rig, "contract_id": contract}, payload, f"{name} {no}")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def reopen_api(request):
    """Reopens a closed month for a rig (its plan can be changed again). A reason is required and goes to the audit history."""
    denied = _deny(request, KEY_MASTERS, "edit")
    if denied:
        return denied
    rm, error = _rig_month(request)
    if error:
        return Response({"detail": error}, status=400)
    rig, first = rm
    reason = (request.data.get("reason") or "").strip()
    if not reason:
        return Response({"detail": "Give the reason for reopening this month."}, status=400)
    plan = RigMonthPlan.objects.filter(rig_id=rig, month=first).select_related("rig").first()
    if plan is None or plan.closed_on is None:
        return Response({"detail": "This month is not closed."}, status=409)
    old = plan.closed_on
    plan.closed_on, plan.closed_by, plan.closed_note = None, None, ""
    plan.mod_user_id, plan.mod_dt = _user_id(request), timezone.now()
    plan.save(update_fields=["closed_on", "closed_by", "closed_note", "mod_user_id", "mod_dt"])
    _audit.record_action(request, "reopen", KEY_MASTERS, plan.pk, f"{plan.rig.rig_name} {first:%b %Y}", {"closed_on": {"old": str(old), "new": None}}, target=plan, note=reason[:255])
    return Response({"ok": True})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def close_api(request):
    """Closes a month that has ended for one rig, with its plan as it stands."""
    denied = _deny(request, KEY_MASTERS, "edit")
    if denied:
        return denied
    rm, error = _rig_month(request)
    if error:
        return Response({"detail": error}, status=400)
    rig, first = rm
    last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
    if last >= datetime.date.today():
        return Response({"detail": f"{first:%B %Y} has not ended yet: it can be closed after its last day."}, status=409)
    closed, _left = m.close_month(first, note=(request.data.get("note") or "closed by hand")[:200], user_id=_user_id(request), rig_ids=[rig])
    if not closed:
        return Response({"detail": "This month is already closed, or the rig has no report in it."}, status=409)
    return Response({"ok": True})
