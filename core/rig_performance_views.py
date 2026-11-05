"""Reports > Rig Performance: the Rig Performance workbook shown as tables on the page (what the hand-made Excel file showed each day), for a chosen month and
year, and the rate sheet behind its projection (what the Master Rate Sheet showed). Read-only; the numbers come from core/rig_performance_month.py, the same
code that builds the Excel file mailed every day. Rights are the pages' own (menu keys reports.rig_performance and reports.rig_performance_masters):
View to see, Export (on the report) to download the Excel file. The Masters page is also where the month's inputs are changed (Edit on
reports.rig_performance_masters): the rig's ILM days, non-ILM days and weights (Rig Month Plans) and its ILM terms (ILM Rate Terms), saved through the same
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
from .daily_operations_update import current_contract
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


def rate_sheet_payload(first, end):
    """The rate sheet behind the projection: per rig the rates per day, the weights, the normal day, the days, the ILM block and the projection."""
    if end < first:
        return {"month": f"{first:%Y-%m}", "label": f"{first:%B %Y}", "rigs": [], "message": f"{first:%B %Y} has not started: there is nothing to show yet."}
    data = m.collect(end)
    codes = {r.drilling_rate_id: (r.rate_code or "").strip() for r in MstDrillingRate.objects.all()}
    out = []
    for rg in data["rigs"]:
        pj = rg["proj"]
        contract = current_contract(rg["rig"].rig_id, end)
        rates = m.contract_rates(rg["rig"].rig_id, contract) if contract else {}
        weights = pj["weights"] or (Decimal(85), Decimal(15), Decimal(0))
        weighted = {m.RATE_R1: weights[0], m.RATE_R2: weights[1], m.RATE_R3: weights[2]}
        lines = []
        for rid in (m.RATE_R1, m.RATE_R2, m.RATE_R3):
            per_day = rates.get(rid, Decimal(0)) * 24
            lines.append({"code": codes.get(rid, str(rid)), "per_day": _f(per_day), "weight": _f(weighted[rid]), "for_revenue": _f(per_day * weighted[rid] / 100)})
        others = [{"code": codes.get(rid, str(rid)), "per_day": _f(rate * 24)} for rid, rate in sorted(rates.items()) if rid not in (m.RATE_R1, m.RATE_R2, m.RATE_R3) and rid not in m.NO_MONEY_RATES and rate]
        contract_no = ProjectContract.objects.filter(pk=contract).values_list("prj_contract_no", flat=True).first() if contract else None
        term = rg_term(rg["rig"].rig_id, contract)
        out.append({
            "name": rg["name"], "contract": contract_no, "problem": pj["problem"], "rates": lines, "other_rates": others, "normal_day": _f(pj["normal_day"]),
            "days_on_project": pj["days"], "from": pj["start"].isoformat() if pj["start"] else None, "to": pj["end"].isoformat() if pj["end"] else None,
            "ilm_days": _f(pj["ilm_days"]), "non_ilm_days": _f(pj["non_ilm_days"]), "normal_total": _f(pj["non_ilm_days"] * pj["normal_day"]) if pj["normal_day"] is not None else None,
            "normal_total_cr": _f(pj["non_ilm_days"] * pj["normal_day"] / m.CRORE, 4) if pj["normal_day"] is not None else None,
            "rig_id": rg["rig"].rig_id, "contract_id": contract,
            "moves": [{"date": mv["date"].isoformat(), "well": mv["well"], "type": mv["type"], "km": _f(mv["km"]), "amount": _f(mv.get("amount"))} for mv in pj["moves"]],
            "warnings": pj["warnings"],
            "closed": _closed_info(rg["plan"]),
            "can_close": end >= first.replace(day=calendar.monthrange(first.year, first.month)[1]) and not (rg["plan"] and rg["plan"].closed_on),
            "history": _history(rg["plan"]),
            "plan": {
                "exists": rg["plan"] is not None, "ilm_days": _f(rg["plan"].ilm_days) if rg["plan"] else 0, "non_ilm_days": _f(rg["plan"].non_ilm_days) if rg["plan"] else None,
                "r1_pct": _f(rg["plan"].r1_pct) if rg["plan"] else 85, "r2_pct": _f(rg["plan"].r2_pct) if rg["plan"] else 15, "r3_pct": _f(rg["plan"].r3_pct) if rg["plan"] else 0,
                "note": rg["plan"].note if rg["plan"] else "",
            },
            "auto_days": max(0, rg_days(pj)),
            "ilm": {
                "term": term, "km": _f(pj["km"]), "amount": _f(pj["ilm_amount"]), "amount_cr": _f(pj["ilm_amount"] / m.CRORE, 4) if pj["ilm_amount"] is not None else None,
                "note": pj["ilm_note"], "mis_cr": _f(pj["mis_cr"], 4),
            },
            "projection_cr": _f(pj["value"], 4),
        })
    return {"month": f"{first:%Y-%m}", "label": f"{first:%B %Y}", "rigs": out, "message": "" if out else f"There is no daily drilling report for any rig in {first:%B %Y}."}


def _closed_info(plan):
    if plan is None or plan.closed_on is None:
        return None
    who = UserProfile.objects.filter(user_id=plan.closed_by).values_list("user_login_id", flat=True).first() if plan.closed_by else "the system"
    return {"on": plan.closed_on.isoformat(), "by": who or "", "note": plan.closed_note}


def _history(plan):
    """The recent changes of the plan row (who, when, what), from the audit history."""
    if plan is None:
        return []
    rows = SysAuditLog.objects.filter(target_table="rig_month_plan", target_pk=str(plan.pk), kind="change").order_by("-ts")[:12]
    out = []
    for r in rows:
        ch = {k: v for k, v in (r.changes or {}).items() if k in ("ilm_days", "non_ilm_days", "r1_pct", "r2_pct", "r3_pct", "closed_on", "note")}
        out.append({"when": r.ts.isoformat(timespec="minutes"), "who": r.username or "", "action": r.action, "changes": ch, "note": r.note})
    return out


def rg_days(pj):
    return pj["days"] - int(pj["ilm_days"] or 0)


def rg_term(rig_id, contract):
    from .models import IlmRateTerm

    t = IlmRateTerm.objects.filter(rig_id=rig_id, contract_id=contract).first() if contract else None
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


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def plan_api(request):
    """Sets the rig's plan for the month (ILM days, non-ILM days, weights), creating the row when the rig had none."""
    denied = _deny(request, KEY_MASTERS, "edit")
    if denied:
        return denied
    rm, error = _rig_month(request)
    if error:
        return Response({"detail": error}, status=400)
    rig, first = rm
    d = request.data
    payload = {
        "rig": rig, "month": first.isoformat(), "ilm_days": _blank(d.get("ilm_days")) if _blank(d.get("ilm_days")) is not None else 0, "non_ilm_days": _blank(d.get("non_ilm_days")),
        "r1_pct": d.get("r1_pct"), "r2_pct": d.get("r2_pct"), "r3_pct": d.get("r3_pct"), "note": (d.get("note") or "")[:200],
    }
    from .models import MstRig

    name = MstRig.objects.filter(pk=rig).values_list("rig_name", flat=True).first()
    if name is None:
        return Response({"detail": "Unknown rig."}, status=404)
    return _save(request, RigMonthPlanSerializer, RigMonthPlan, {"rig_id": rig, "month": first}, payload, f"{name} {first:%b %Y}")


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
    """Reopens a closed month for a rig (its ILM days can be changed again). A reason is required and goes to the audit history."""
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
    """Closes a month that has ended for one rig, with the ILM days as they stand (0 when none were entered)."""
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
