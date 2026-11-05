"""The Rig Performance mail: every day at the alert's hour (10:00), the month-to-date "Rig_Performance-<Month>-<Year>" Excel file, built from the daily
drilling reports, mailed to the person named on the alert. It replaces a file that was updated by hand every morning. It is a new report (there is
no legacy alert for it); the layout is the one the hand-made workbook had: a sheet per rig (a row per day, the hours of each rate, Total, Productivity,
Revenue in crore) and a FINAL sheet (the target and projection of each rig, its productivity and revenue per day, the month's totals, actual as a % of
target, and the diesel consumption, cost and closing balance).

What is calculated, and from what:
  * Hours: the activity hours of the day on the rig's daily report, by rate. Columns: R1, R2 (also ILM-R2 and 1/5 R2), R3, R0, FM (FM, FM 2/3, FM 1/3 and Force majeure),
    ILM/IPM (ILM, IPM-Lateral, IPM-Adjacent) and, only when a rig has any, Other (the remaining rates). Total is their sum. A day with no report is a
    blank row (a rig that started mid-month has empty rows before it, a day not yet reported is empty).
  * Productivity = (R1 + R2 + R3 + ILM/IPM + FM) / Total: the productive classes of core/rate_classes.py (every class except R0) over all hours, the same
    rule as the Rig Operations dashboard.
  * Revenue (crore) = hours x the rate per hour of that rate on the rig's contract (Project Drilling Rates) / 10,000,000. ILM/IPM hours earn the rig's
    "MIS per day" (crore, set per rig and month) for each 24 hours, because their rate in the contract is a lump sum, not per hour.
  * Diesel: the litres of the day's report; cost = litres x the price per litre in force that day (Diesel Price) / 10,000,000; closing balance = the
    rig's diesel stock as the Daily Operations Update works it out (received less consumed, added up day by day from the project's start).
  * Target: 96 % for every rig (a constant for now). Productive hours: the one rule of core/rate_classes.py (every class except R0, FM included; to be confirmed).
  * Projection (crore), calculated, never typed: (non-ILM days x the normal day's revenue + the ILM amount when there are ILM days) / 10,000,000. The normal
    day's revenue = 24 x (R1 % x the R1 rate per hour + R2 % x the R2 rate + R3 % x the R3 rate), the rates from Project Drilling Rates and the percentages
    from Rig Month Plans (85 / 15 / 0 unless changed for the rig and month). The days are those the rig is on its project in the month (from the day it
    starts, to the day it ends), or the plan's own numbers; ILM days come from the plan. ILM amount = the flat amount + (km - upto km) x the price per
    km when km is over upto km (ILM Rate Terms; the km are the distance covered of the wells started in the month); MIS per day = that amount / the ILM
    days (the plan's, else the days with ILM/IPM hours so far) and it is the revenue of each ILM/IPM day (hours / 24 of it).
  * IPM is not in the projection yet (to be confirmed).
  * Differences between the old workbook and the system's rates are not copied: the system's rates are used and the known differences are listed on the
    Notes sheet (KNOWN_DIFFERENCES), to be confirmed.
The day reported is yesterday; on the 1st the whole previous month is reported (yesterday is its last day)."""

import calendar
import datetime
import html
import io
from collections import defaultdict
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .models import DieselPrice, DrillingDtl, DrillingDtlOps, DrillingHdr, IlmRateTerm, MstRig, ProjectContractDtl, ProjectDrillingRate, RigMonthPlan
from . import rate_classes
from .daily_operations_update import current_contract, diesel_stock_by_day, project_start
from .report_job import ReportMail, ScheduledReportJob

JOB_KEY = "rig_performance"
ENTITY_KEY = "automation"
ACTION = "send_rig_performance_mail"
TRIGGER_CODE = "auto.rig_performance"
ALERT_NAME = "Rig Performance"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
CRORE = Decimal(10000000)
DEFAULT_TARGET = Decimal("96")
COLUMNS = ["R1", "R2", "R3", "R0", "FM", "ILM/IPM"]
RATE_COLUMN = {rid: rate_classes.COLUMN_OF_CLASS[cls] for rid, cls in rate_classes.CLASS_OF_RATE_ID.items()}  # one column per rate class (core/rate_classes.py)
NO_MONEY_RATES = {6, 7, 8, 15, 13, 14, 19, 20}  # lump sums, metres and kilometres: not hours x a rate
# Where the system and the hand-made workbook disagree; the system's figure is used. Remove an entry once it is confirmed or the rate is corrected.
KNOWN_DIFFERENCES = [
    "EE01, R3: the October 2026 workbook priced R3 at 1,124,630 a day; the system's contract rate is 42,174 an hour (1,012,176 a day). The system's rate is used.",
    "SK02, R2: the workbook has three R2 columns (R2-A 972,000, R2-B 918,000, R2-C 864,000 a day) and counts only R2-A as productive; the system's contract has one R2 rate (972,000 a day, the same as R2-A), so any R2-B or R2-C hours cannot be told apart and all R2 hours are shown in one R2 column. Hours were only ever booked on R2-A in Aug-Oct 2026, so the figures agree.",
    "Productivity: in the workbook FM counts as productive for EE01 and SK02 but not for EE05 (Axom Rhino); the system counts it for every rig (every class except R0 counts), the same rule as the Rig Operations dashboard (to be confirmed).",
]
TARGET_PCT = Decimal("96")  # the productivity target of every rig, for now
FM_PRODUCTIVE = rate_classes.FORCE_MAJEURE in rate_classes.PRODUCTIVE_CLASSES  # the one productive rule of core/rate_classes.py (to be confirmed with Arjun)
RATE_R1, RATE_R2, RATE_R3, RATE_ILM = 1, 2, 3, 6
GREEN, NAVY, GREY, AMBER = "00988A", "1E2656", "D9D9D9", "FFF2CC"


def _d(v):
    return Decimal(str(v)) if v is not None else Decimal(0)


def month_bounds(end):
    first = end.replace(day=1)
    return first, end.replace(day=calendar.monthrange(end.year, end.month)[1])


def plan_for(rig_id, month):
    return RigMonthPlan.objects.filter(rig_id=rig_id, month=month).first()


def project_days(rig_id, contract_id, first, last):
    """(first day, last day, number of days) the rig is on its project within the month: from the day it starts (not before the 1st) to the day it
    ends (not after the last); (None, None, 0) when it is not on a project at all that month."""
    line = ProjectContractDtl.objects.filter(rig_id=rig_id, contract_id=contract_id).select_related("contract").order_by("-rig_active_from").first()
    if line is None:
        return None, None, 0
    start = max(first, line.rig_active_from)
    stop = line.rig_active_to or line.contract.prj_end_dt or last
    end = min(last, stop)
    return (start, end, (end - start).days + 1) if end >= start else (None, None, 0)


RATE_IPM = (7, 8)  # IPM - Lateral, IPM - Adjacent


def month_moves(rig_id, contract_id, first, last):
    """The rig moves of the month: the wells it started on the project that month and are paid as a move (Rate Type ILM, IPM - Lateral or IPM - Adjacent):
    [{"date", "well", "type": "ILM" or "IPM", "rate_id", "km"}] in date order."""
    out = []
    for h in DrillingHdr.objects.filter(
        rig_id=rig_id, contract_id=contract_id, drilling_rate_id__in=(RATE_ILM,) + RATE_IPM,
        first_anchor_down_dt__gte=datetime.datetime.combine(first, datetime.time.min), first_anchor_down_dt__lte=datetime.datetime.combine(last, datetime.time.max),
    ).order_by("first_anchor_down_dt"):
        out.append({"date": h.first_anchor_down_dt.date(), "well": h.location or "", "type": "IPM" if h.drilling_rate_id in RATE_IPM else "ILM", "rate_id": h.drilling_rate_id, "km": _d(h.distance_covered_kms_knots)})
    return out


def contract_rates(rig_id, contract_id):
    return {r.drilling_rate_id: _d(r.rate) for r in ProjectDrillingRate.objects.filter(rig_id=rig_id, contract_id=contract_id) if r.rate is not None}


def ilm_amount(rig_id, contract_id, km, rates):
    """(amount in rupees or None, source text): the flat amount + (km - upto km) x the price per km. Without ILM Rate Terms the project's own ILM rate is the
    flat amount and there is no per-km price; with neither, None."""
    term = IlmRateTerm.objects.filter(rig_id=rig_id, contract_id=contract_id).first()
    if term is not None:
        flat = _d(term.flat_amount) if term.flat_amount is not None else rates.get(RATE_ILM, Decimal(0))
        if not flat:
            return None, "ILM Rate Terms have no flat amount and the project's ILM rate is 0"
        return flat + max(Decimal(0), km - _d(term.upto_km)) * _d(term.extra_per_km), f"flat {flat:,.0f} up to {float(term.upto_km):g} km, then {float(term.extra_per_km):,.2f} a km"
    flat = rates.get(RATE_ILM, Decimal(0))
    if flat:
        return flat, f"the project's ILM rate {flat:,.0f} (no ILM Rate Terms)"
    return None, "no ILM Rate Terms and the project's ILM rate is 0"


def projection_for(rig_id, contract_id, first, last, plan, actual_ilm_days):
    """The calculated projection of the rig for the month and the working behind it (see the module notes). The moves of the month are priced as:
      * ILM moves: the ILM terms applied to the kilometres of the ILM moves together (flat amount + km beyond the flat limit x the price per km);
        [to be confirmed with Arjun: per move instead of the month's total];
      * IPM moves: the project's IPM rate of the move's rate type, each;
      * no move recorded yet but ILM days planned: the ILM flat amount (a move that has not started).
    The moves count in the projection only when ILM days are planned (the ILM days are the days those moves take)."""
    out = {
        "value": None, "days": 0, "ilm_days": Decimal(0), "non_ilm_days": Decimal(0), "normal_day": None, "weights": None, "km": Decimal(0), "ilm_amount": None, "ilm_note": "",
        "mis_cr": None, "start": None, "end": None, "problem": "", "warnings": [], "moves": [],
    }
    if contract_id is None:
        out["problem"] = "no active project with rates"
        return out
    rates = contract_rates(rig_id, contract_id)
    start, end, days = project_days(rig_id, contract_id, first, last)
    pct = (_d(plan.r1_pct), _d(plan.r2_pct), _d(plan.r3_pct)) if plan else (Decimal(85), Decimal(15), Decimal(0))
    normal = Decimal(24) * (pct[0] * rates.get(RATE_R1, Decimal(0)) + pct[1] * rates.get(RATE_R2, Decimal(0)) + pct[2] * rates.get(RATE_R3, Decimal(0))) / 100
    ilm_days = _d(plan.ilm_days) if plan else Decimal(0)
    non = _d(plan.non_ilm_days) if plan and plan.non_ilm_days is not None else max(Decimal(0), Decimal(days) - ilm_days)

    moves = month_moves(rig_id, contract_id, first, last)
    ilm_moves = [mv for mv in moves if mv["type"] == "ILM"]
    ipm_moves = [mv for mv in moves if mv["type"] == "IPM"]
    ilm_km = sum((mv["km"] for mv in ilm_moves), Decimal(0))
    parts, notes = [], []
    if ilm_moves or (not moves and ilm_days > 0):
        amount, note = ilm_amount(rig_id, contract_id, ilm_km, rates)
        if amount is None:
            notes.append(note)
        else:
            parts.append(amount)
            notes.append(note if ilm_moves else note + " (no move recorded yet)")
    for mv in ipm_moves:
        rate = rates.get(mv["rate_id"], Decimal(0))
        mv["amount"] = rate
        if rate:
            parts.append(rate)
            notes.append(f"IPM move {mv['date']:%d %b}: the project's IPM rate {rate:,.0f}")
        else:
            notes.append(f"IPM move {mv['date']:%d %b}: the project's IPM rate is 0")
    for mv in ilm_moves:
        mv["amount"] = None  # an ILM move's amount comes from the terms over the month's ILM km (shown as the total)
    amount_total = sum(parts, Decimal(0)) if parts else None
    basis = ilm_days if ilm_days > 0 else actual_ilm_days
    out.update({"days": days, "ilm_days": ilm_days, "non_ilm_days": non, "normal_day": normal, "weights": pct, "km": ilm_km, "ilm_amount": amount_total, "ilm_note": "; ".join(notes), "start": start, "end": end, "moves": moves})
    if amount_total is not None and basis > 0:
        out["mis_cr"] = amount_total / CRORE / basis
    total = non * normal
    if ilm_days > 0:
        if amount_total is None:
            out["problem"] = "ILM days are planned but the amount of the move is not known (" + "; ".join(notes) + ")"
        else:
            total += amount_total
    elif moves:
        out["warnings"].append("a move is recorded this month (" + ", ".join(f"{mv['type']} {mv['date']:%d %b}" for mv in moves) + ") but no ILM days are planned, so it is not in the projection")
    out["value"] = total / CRORE
    return out


def ilm_activity(rig_id, first, last):
    """True when the rig recorded ILM/IPM hours or started a move in the month (so a month with no ILM days entered is probably 'not entered yet')."""
    hours = DrillingDtlOps.objects.filter(
        drilling_dtl__rig_id=rig_id, drilling_dtl__drilling_dtl_dt__gte=first, drilling_dtl__drilling_dtl_dt__lte=last, prj_drilling_rate__drilling_rate_id__in=(RATE_ILM,) + RATE_IPM
    ).exists()
    moved = DrillingHdr.objects.filter(
        rig_id=rig_id, drilling_rate_id__in=(RATE_ILM,) + RATE_IPM, first_anchor_down_dt__gte=datetime.datetime.combine(first, datetime.time.min), first_anchor_down_dt__lte=datetime.datetime.combine(last, datetime.time.max)
    ).exists()
    return hours or moved


def unconfirmed_ilm(first):
    """[rig name] whose month `first` is not closed, has ILM/IPM activity and no ILM days entered: the ILM days still have to be entered or confirmed as 0."""
    last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
    out = []
    for rid in sorted(set(DrillingDtl.objects.filter(drilling_dtl_dt__gte=first, drilling_dtl_dt__lte=last).values_list("rig_id", flat=True))):
        plan = RigMonthPlan.objects.filter(rig_id=rid, month=first).first()
        if (plan is None or (plan.closed_on is None and not plan.ilm_days)) and ilm_activity(rid, first, last):
            out.append(MstRig.objects.get(pk=rid).rig_name)
    return out


def close_month(first, note="", user_id=None, rig_ids=None, auto=False):
    """Closes the month: makes sure every rig that reported in it has its Rig Month Plan row (ILM days 0 when nobody entered any) and marks the row closed, so the
    month's ILM day count is final. A row that is already closed is left alone (safe to run again). With auto=True (the daily report's own run) a rig that
    had ILM/IPM activity but has no ILM days entered is NOT closed: it is left open for someone to enter or confirm the days. Returns (closed now, [rig names
    left open])."""
    from django.utils import timezone

    from . import audit as _audit

    last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
    ids = set(DrillingDtl.objects.filter(drilling_dtl_dt__gte=first, drilling_dtl_dt__lte=last).values_list("rig_id", flat=True))
    if rig_ids is not None:
        ids &= set(rig_ids)
    closed, left = 0, []
    for rid in sorted(ids):
        plan = RigMonthPlan.objects.filter(rig_id=rid, month=first).first()
        if plan is not None and plan.closed_on is not None:
            continue
        if auto and (plan is None or not plan.ilm_days) and ilm_activity(rid, first, last):
            left.append(MstRig.objects.get(pk=rid).rig_name)
            continue
        if plan is None:
            plan = RigMonthPlan.objects.create(rig_id=rid, month=first, ilm_days=0, cr_user_id=user_id or 0, cr_dt=timezone.now())
        plan.closed_on, plan.closed_by, plan.closed_note = datetime.date.today(), user_id, (note or "")[:200]
        plan.save(update_fields=["closed_on", "closed_by", "closed_note"])
        _audit._create(user_id, "system" if user_id is None else "", "close", "reports.rig_performance_masters", _audit.entity_label("reports.rig_performance_masters"), plan.pk, f"{plan.rig.rig_name} {first:%b %Y}", {"closed_on": {"old": None, "new": str(plan.closed_on)}, "ilm_days": {"old": None, "new": str(plan.ilm_days)}}, None, target=plan, note=note or "closed")
        closed += 1
    return closed, left


def price_on(day):
    p = DieselPrice.objects.filter(valid_from__lte=day).exclude(valid_to__lt=day).order_by("-valid_from", "-price_id").first()
    return _d(p.price_per_litre) if p else None


def collect(end):
    """Everything the workbook and the mail show for the month ending at `end` (yesterday)."""
    first, last = month_bounds(end)
    days = [first + datetime.timedelta(days=i) for i in range((end - first).days + 1)]
    rig_ids = sorted(set(DrillingDtl.objects.filter(drilling_dtl_dt__gte=first, drilling_dtl_dt__lte=end).values_list("rig_id", flat=True)))
    prices = {d: price_on(d) for d in days}
    rigs = []
    for rid in rig_ids:
        rig = MstRig.objects.get(pk=rid)
        plan = plan_for(rid, first)
        contract = current_contract(rid, end)
        actual_ilm_days = Decimal(0)
        reports = {r.drilling_dtl_dt: r for r in DrillingDtl.objects.filter(rig_id=rid, drilling_dtl_dt__gte=first, drilling_dtl_dt__lte=end)}
        hours = defaultdict(lambda: defaultdict(Decimal))
        money = defaultdict(Decimal)
        rates_used = {}
        ops = DrillingDtlOps.objects.filter(drilling_dtl__rig_id=rid, drilling_dtl__drilling_dtl_dt__gte=first, drilling_dtl__drilling_dtl_dt__lte=end).select_related("drilling_dtl", "prj_drilling_rate", "prj_drilling_rate__drilling_rate")
        for o in ops:
            day, dur = o.drilling_dtl.drilling_dtl_dt, _d(o.duration)
            pr = o.prj_drilling_rate
            rate_id = pr.drilling_rate_id if pr is not None else None
            col = RATE_COLUMN.get(rate_id, "Other")
            hours[day][col] += dur
            if pr is not None and rate_id not in NO_MONEY_RATES and pr.rate is not None:
                money[day] += dur * _d(pr.rate)
                rates_used[pr.drilling_rate.rate_code] = _d(pr.rate)
        has_other = any(h.get("Other") for h in hours.values())
        actual_ilm_days = sum((h.get("ILM/IPM", Decimal(0)) for h in hours.values()), Decimal(0)) / 24
        proj = projection_for(rid, contract, first, last, plan, actual_ilm_days)
        stock = {d: closing for d, _o, _r, _c, closing in diesel_stock_by_day(rid, project_start(rid, contract, end) if contract else None)}
        st = {"target": TARGET_PCT, "fm": FM_PRODUCTIVE}
        cols = COLUMNS + (["Other"] if has_other else [])
        rows = []
        for day in days:
            if day not in reports:
                rows.append({"day": day, "reported": False})
                continue
            h = {c: hours[day].get(c, Decimal(0)) for c in cols}
            total = sum(h.values(), Decimal(0))
            prod_hours = h["R1"] + h["R2"] + h["R3"] + h["ILM/IPM"] + (h["FM"] if st["fm"] else Decimal(0))
            rev = money[day] / CRORE
            ilm_missing = False
            if h["ILM/IPM"]:
                if proj["mis_cr"] is None:
                    ilm_missing = True
                else:
                    rev += proj["mis_cr"] * h["ILM/IPM"] / 24
            litres = reports[day].consumption_diesel
            rows.append({
                "day": day, "reported": True, "hours": h, "total": total, "prod": (prod_hours / total) if total else None, "revenue": rev,
                "litres": litres, "closing": stock.get(day), "cost": (_d(litres) * prices[day] / CRORE) if litres is not None and prices[day] is not None else None, "ilm_missing": ilm_missing,
            })
        done = [r for r in rows if r["reported"] and r["prod"] is not None]
        rigs.append({
            "rig": rig, "name": rig.rig_name, "cols": cols, "rows": rows, "setting": st, "plan": plan, "proj": proj, "rates_used": rates_used,
            "avg_prod": (sum((r["prod"] for r in done), Decimal(0)) / len(done)) if done else None,
            "revenue": sum((r["revenue"] for r in rows if r["reported"]), Decimal(0)),
            "projection": proj["value"], "yesterday": next((r for r in rows if r["day"] == end), None),
            "litres": sum((_d(r["litres"]) for r in rows if r["reported"] and r.get("litres") is not None), Decimal(0)),
            "cost": sum((r["cost"] for r in rows if r["reported"] and r.get("cost") is not None), Decimal(0)),
        })
    rigs.sort(key=lambda r: r["rig"].rig_id)
    return {"first": first, "end": end, "days": days, "rigs": rigs, "prices": prices}


def sheet_name(rig_name, first, taken):
    base = "".join(ch for ch in f"{rig_name}-{first:%b}-{first:%y}".upper() if ch not in "[]:*?/\\")[:31]
    name, n = base, 2
    while name in taken:
        name = f"{base[:28]}-{n}"
        n += 1
    taken.add(name)
    return name


def notes_lines(data):
    """[(text, is heading)] of the Notes sheet / the Notes box of the report page: how the file is made, rates used, the projection working, the diesel price and
    the differences still to be confirmed."""
    end = data["end"]
    lines = [("How this file is made", True), (f"Month to date up to {end:%d-%m-%Y}, from the daily drilling reports in Seros-IT. Rates, hours and diesel are the system's.", False), ("", False)]
    lines += [("Rates used (per day: the rate per hour x 24)", True)]
    for rg in data["rigs"]:
        lines.append((f"{rg['name']}: " + ", ".join(f"{code} {float(rate) * 24:,.0f}" for code, rate in rg["rates_used"].items()), False))
    lines += [("", False), ("Productivity: target 96% for every rig; " + rate_classes.rule_text() + " (the same rule as the Rig Operations dashboard; to be confirmed with Arjun)", True), ("", False), ("Projection working (calculated, not typed)", True)]
    for rg in data["rigs"]:
        pj = rg["proj"]
        if pj["value"] is None:
            lines.append((f"{rg['name']}: no projection ({pj['problem']})", False))
            continue
        if not pj["days"] or pj["start"] is None:
            # it reported this month but its project line does not cover any day of it (a line that ended earlier, or one that starts later)
            lines.append((f"{rg['name']}: reported this month but has no days on a project line in it, so there is no projection", False))
            continue
        w = pj["weights"]
        lines.append((
            f"{rg['name']}: {float(pj['non_ilm_days']):g} non-ILM days x {float(pj['normal_day']):,.0f} a day (R1 {float(w[0]):g}%, R2 {float(w[1]):g}%, R3 {float(w[2]):g}%) + "
            + (f"moves {float(pj['ilm_amount']):,.0f} ({pj['ilm_note']}; {float(pj['km']):g} ILM km, {float(pj['ilm_days']):g} ILM/IPM days)" if pj["ilm_days"] > 0 and pj["ilm_amount"] is not None else "no ILM days")
            + f" = {float(pj['value']):.4f} Cr; on the project {pj['start']:%d %b} to {pj['end']:%d %b} ({pj['days']} days)" + ("; plan: " + (rg["plan"].note or "set in Rig Month Plans") if rg["plan"] else "; no Rig Month Plan row (defaults)"), False))
    for rg in data["rigs"]:
        for w in rg["proj"]["warnings"]:
            lines.append((f"{rg['name']}: {w}", False))
    lines += [("", False), ("Diesel price per litre", True)]
    for day in (data["first"], data["end"]):
        p = data["prices"].get(day)
        lines.append((f"{day:%d-%m-%Y}: " + (f"{float(p):g}" if p is not None else "no price set"), False))
    lines += [("", False), ("Differences to confirm (the system's figure is used)", True)] + [(t, False) for t in KNOWN_DIFFERENCES]
    return lines


def build_workbook(data):
    first, end = data["first"], data["end"]
    wb = Workbook()
    thin = Side(style="thin")
    box = Border(left=thin, right=thin, top=thin, bottom=thin)
    head = PatternFill("solid", fgColor=GREEN)
    sub = PatternFill("solid", fgColor=GREY)
    white = Font(bold=True, color="FFFFFF")
    names, taken = {}, set()
    first_sheet = True
    for rg in data["rigs"]:
        ws = wb.active if first_sheet else wb.create_sheet()
        first_sheet = False
        ws.title = names[rg["rig"].rig_id] = sheet_name(rg["name"], first, taken)
        cols = rg["cols"]
        n_cols = 1 + len(cols) + 3
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n_cols)
        ws["A1"] = f"RIG PERFORMANCE FOR {rg['name']}"
        ws["A1"].font = Font(bold=True, size=13)
        heads = ["Date", *cols, "Total", "Productivity", "Revenue (INR Cr)"]
        for i, h in enumerate(heads, start=1):
            c = ws.cell(row=2, column=i, value=h)
            c.font, c.fill, c.border, c.alignment = white, head, box, Alignment(horizontal="center", wrap_text=True)
        r = 3
        sums = defaultdict(Decimal)
        for row in rg["rows"]:
            ws.cell(row=r, column=1, value=row["day"]).number_format = "DD-MMM-YY"
            if row["reported"]:
                for i, c in enumerate(cols, start=2):
                    v = row["hours"][c]
                    ws.cell(row=r, column=i, value=float(v) if v else None).number_format = "0.00"
                    sums[c] += v
                ws.cell(row=r, column=len(cols) + 2, value=float(row["total"])).number_format = "0.00"
                p = ws.cell(row=r, column=len(cols) + 3, value=float(row["prod"]) if row["prod"] is not None else None)
                p.number_format = "0.0%"
                rv = ws.cell(row=r, column=len(cols) + 4, value=float(row["revenue"]))
                rv.number_format = "0.0000"
                if row["ilm_missing"]:
                    rv.fill = PatternFill("solid", fgColor=AMBER)
                sums["Total"] += row["total"]
                sums["Revenue"] += row["revenue"]
            for i in range(1, n_cols + 1):
                ws.cell(row=r, column=i).border = box
            r += 1
        ws.cell(row=r, column=1, value="TOTAL/AVG")
        for i, c in enumerate(cols, start=2):
            ws.cell(row=r, column=i, value=float(sums[c]) if sums[c] else None).number_format = "0.00"
        ws.cell(row=r, column=len(cols) + 2, value=float(sums["Total"])).number_format = "0.00"
        pa = ws.cell(row=r, column=len(cols) + 3, value=float(rg["avg_prod"]) if rg["avg_prod"] is not None else None)
        pa.number_format = "0.0%"
        ws.cell(row=r, column=len(cols) + 4, value=float(sums["Revenue"])).number_format = "0.0000"
        for i in range(1, n_cols + 1):
            c = ws.cell(row=r, column=i)
            c.font, c.fill, c.border = Font(bold=True), sub, box
        ws.column_dimensions["A"].width = 12
        for i in range(2, n_cols + 1):
            ws.column_dimensions[get_column_letter(i)].width = 11 if i < n_cols else 16
        ws.freeze_panes = "B3"

    # ── FINAL sheet ──
    fs = wb.create_sheet(f"FINAL-{first:%b}-{first:%y}".upper())
    n = len(data["rigs"])
    c_prod, c_avg = 2, 2 + n
    c_rev, c_tot = c_avg + 1, c_avg + 1 + n
    c_hsd = c_tot + 1
    last_col = c_hsd + 3 * n - 1
    fs.cell(row=1, column=1, value="Months Target").font = Font(bold=True)
    fs.cell(row=2, column=1, value="Projection (Cr)").font = Font(bold=True)
    fs.cell(row=3, column=1, value=first).number_format = "MMM-YY"
    fs.merge_cells(start_row=3, start_column=c_prod, end_row=3, end_column=c_avg)
    fs.cell(row=3, column=c_prod, value="Productivity")
    fs.merge_cells(start_row=3, start_column=c_rev, end_row=3, end_column=c_tot)
    fs.cell(row=3, column=c_rev, value="Revenue (INR Cr)")
    if n:
        fs.merge_cells(start_row=3, start_column=c_hsd, end_row=3, end_column=last_col)
        fs.cell(row=3, column=c_hsd, value="HSD Consumption, Cost Analysis and Closing Stock")
    for i in range(1, last_col + 1):
        c = fs.cell(row=3, column=i)
        c.font, c.fill, c.alignment = white, head, Alignment(horizontal="center")
    for k, rg in enumerate(data["rigs"]):
        nm = rg["name"]
        fs.cell(row=4, column=c_prod + k, value=nm)
        fs.cell(row=4, column=c_rev + k, value=nm)
        for j, h in enumerate(("Consumption", "Cost", "Closing B")):
            fs.cell(row=4, column=c_hsd + 3 * k + j, value=f"{nm} {h}")
        t = fs.cell(row=1, column=c_prod + k, value=float(rg["setting"]["target"] / 100))
        t.number_format = "0%"
        pj = fs.cell(row=2, column=c_rev + k, value=float(rg["projection"]) if rg["projection"] is not None else None)
        pj.number_format = "0.00"
    fs.cell(row=4, column=c_avg, value="Avg")
    fs.cell(row=4, column=c_tot, value="Total")
    fs.cell(row=4, column=1, value="Date")
    for i in range(1, last_col + 1):
        c = fs.cell(row=4, column=i)
        c.font, c.fill, c.border, c.alignment = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor=NAVY), box, Alignment(horizontal="center", wrap_text=True)
    avg_target = (sum((r["setting"]["target"] for r in data["rigs"]), Decimal(0)) / n / 100) if n else None
    fs.cell(row=1, column=c_avg, value=float(avg_target) if avg_target is not None else None).number_format = "0%"
    proj_total = sum((r["projection"] for r in data["rigs"] if r["projection"] is not None), Decimal(0))
    fs.cell(row=2, column=c_tot, value=float(proj_total) if any(r["projection"] is not None for r in data["rigs"]) else None).number_format = "0.00"
    row = 5
    for idx, day in enumerate(data["days"]):
        fs.cell(row=row, column=1, value=day).number_format = "DD-MMM-YY"
        prods = []
        rev_sum = Decimal(0)
        for k, rg in enumerate(data["rigs"]):
            dr = rg["rows"][idx]
            if not dr["reported"]:
                continue
            if dr["prod"] is not None:
                fs.cell(row=row, column=c_prod + k, value=float(dr["prod"])).number_format = "0.0%"
                prods.append(dr["prod"])
            fs.cell(row=row, column=c_rev + k, value=float(dr["revenue"])).number_format = "0.0000"
            rev_sum += dr["revenue"]
            if dr["litres"] is not None:
                fs.cell(row=row, column=c_hsd + 3 * k, value=dr["litres"])
            if dr["cost"] is not None:
                fs.cell(row=row, column=c_hsd + 3 * k + 1, value=float(dr["cost"])).number_format = "0.0000"
            if dr.get("closing") is not None:
                fs.cell(row=row, column=c_hsd + 3 * k + 2, value=float(dr["closing"])).number_format = "#,##0"
        if prods:
            fs.cell(row=row, column=c_avg, value=float(sum(prods, Decimal(0)) / len(prods))).number_format = "0.0%"
            fs.cell(row=row, column=c_tot, value=float(rev_sum)).number_format = "0.0000"
        for i in range(1, last_col + 1):
            fs.cell(row=row, column=i).border = box
        row += 1
    tot_row = row
    fs.cell(row=tot_row, column=1, value="TOTAL/AVG")
    for k, rg in enumerate(data["rigs"]):
        fs.cell(row=tot_row, column=c_prod + k, value=float(rg["avg_prod"]) if rg["avg_prod"] is not None else None).number_format = "0.0%"
        fs.cell(row=tot_row, column=c_rev + k, value=float(rg["revenue"])).number_format = "0.0000"
        fs.cell(row=tot_row, column=c_hsd + 3 * k, value=int(rg["litres"]))
        fs.cell(row=tot_row, column=c_hsd + 3 * k + 1, value=float(rg["cost"])).number_format = "0.0000"
    avgs = [r["avg_prod"] for r in data["rigs"] if r["avg_prod"] is not None]
    overall = (sum(avgs, Decimal(0)) / len(avgs)) if avgs else None
    fs.cell(row=tot_row, column=c_avg, value=float(overall) if overall is not None else None).number_format = "0.0%"
    total_rev = sum((r["revenue"] for r in data["rigs"]), Decimal(0))
    fs.cell(row=tot_row, column=c_tot, value=float(total_rev)).number_format = "0.0000"
    for i in range(1, last_col + 1):
        c = fs.cell(row=tot_row, column=i)
        c.font, c.fill, c.border = Font(bold=True), sub, box
    fs.cell(row=tot_row + 2, column=1, value="Actual as a % of Target").font = Font(bold=True)
    fs.cell(row=tot_row + 3, column=1, value="Revenue as a % of Projection").font = Font(bold=True)
    for k, rg in enumerate(data["rigs"]):
        if rg["avg_prod"] is not None and rg["setting"]["target"]:
            fs.cell(row=tot_row + 2, column=c_prod + k, value=float(rg["avg_prod"] / (rg["setting"]["target"] / 100))).number_format = "0.0%"
        if rg["projection"]:
            fs.cell(row=tot_row + 3, column=c_rev + k, value=float(rg["revenue"] / rg["projection"])).number_format = "0.0%"
    if overall is not None and avg_target:
        fs.cell(row=tot_row + 2, column=c_avg, value=float(overall / avg_target)).number_format = "0.0%"
    if proj_total:
        fs.cell(row=tot_row + 3, column=c_tot, value=float(total_rev / proj_total)).number_format = "0.0%"
    fs.cell(row=tot_row + 5, column=1, value="Total Revenue (in CR)").font = Font(bold=True)
    fs.cell(row=tot_row + 5, column=2, value=float(total_rev)).number_format = "0.0000"
    fs.column_dimensions["A"].width = 24
    for i in range(2, last_col + 1):
        fs.column_dimensions[get_column_letter(i)].width = 13
    fs.row_dimensions[4].height = 30
    fs.freeze_panes = "B5"

    # ── Notes sheet ──
    ns = wb.create_sheet("Notes")
    lines = notes_lines(data)
    for i, (t, b) in enumerate(lines, start=1):
        c = ns.cell(row=i, column=1, value=t)
        c.font = Font(bold=b)
    ns.column_dimensions["A"].width = 150
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _p(v):
    return "-" if v is None else f"{float(v) * 100:.1f}%"


def _cr(v):
    return "-" if v is None else f"{float(v):.2f}"


def _page(inner):
    return (
        "<div style=\"font-family:Verdana,Tahoma,Arial,sans-serif;font-size:13px\">"
        "<p style=\"color:#e00707;margin:0 0 4px\">Seros-IT Auto Alert</p>"
        f"{inner}"
        "<p style=\"margin:28px 0 0\">This is an automated Mail. Please do not reply.</p></div>"
    )


def build_mail(alert, now):
    end = now.date() - datetime.timedelta(days=1)
    data = collect(end)
    subject = (alert.mail_subject or "Rig Performance").strip()
    if not data["rigs"]:
        line = f"There is no daily drilling report for any rig in {end:%B %Y} up to {end:%d/%m/%Y}."
        return ReportMail(subject, _page(f"<p style=\"color:#0715cd;margin:0 0 14px\">{line}</p>"), line, [], True, "No rig reported")
    th = "padding:5px 8px;border:1px solid #104a7b;background:#1E2656;color:#ffffff;text-align:center"
    td = "padding:4px 8px;border:1px solid #104a7b;text-align:center;background:#F7F8E0"
    head = "".join(f"<td style=\"{th}\">{h}</td>" for h in ("Rig", f"Productivity {end:%b} (avg)", "Target", "% of target", f"Revenue {end:%b} (Cr)", "Projection (Cr)", "% of projection", f"Productivity {end:%d %b}", f"Diesel {end:%d %b} (L)"))
    body, notes = [], []
    for rg in data["rigs"]:
        y, s = rg["yesterday"], rg["setting"]
        pct_t = (rg["avg_prod"] / (s["target"] / 100)) if rg["avg_prod"] is not None and s["target"] else None
        pct_p = (rg["revenue"] / rg["projection"]) if rg["projection"] else None
        cells = [html.escape(rg["name"]), _p(rg["avg_prod"]), f"{float(s['target']):g}%", _p(pct_t), _cr(rg["revenue"]), _cr(rg["projection"]), _p(pct_p), _p(y["prod"]) if y and y["reported"] else "not reported", (f"{y['litres']:,}" if y and y["reported"] and y.get("litres") is not None else "-")]
        body.append("<tr>" + f"<td style=\"{td};text-align:left\">{cells[0]}</td>" + "".join(f"<td style=\"{td}\">{c}</td>" for c in cells[1:]) + "</tr>")
        if not (y and y["reported"]):
            notes.append(f"{rg['name']} has no daily report for {end:%d/%m/%Y} yet.")
        if rg["projection"] is None:
            notes.append(f"{rg['name']}: no projection for {end:%B %Y} ({rg['proj']['problem']}).")
        elif rg["proj"]["problem"]:
            notes.append(f"{rg['name']}: {rg['proj']['problem']}.")
        for w in rg["proj"]["warnings"]:
            notes.append(f"{rg['name']}: {w}.")
        if any(r.get("ilm_missing") for r in rg["rows"]):
            notes.append(f"{rg['name']}: ILM/IPM hours were reported but the ILM amount is not known (ILM Rate Terms), so their revenue is not counted.")
    previous = (end.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
    for name in unconfirmed_ilm(previous):
        notes.append(f"{name}: ILM/IPM was recorded in {previous:%B %Y} but its ILM days are not entered, so that month is not closed yet.")
    if data["prices"].get(end) is None:
        notes.append("No diesel price is set for this date, so the diesel cost is blank.")
    notes += [t for t in KNOWN_DIFFERENCES if any(t.startswith(rg["name"]) for rg in data["rigs"])]
    inner = (
        f"<p style=\"color:#0715cd;margin:0 0 10px\">Rig Performance, {end:%B %Y}, up to {end:%d/%m/%Y}</p>"
        "<p>The month's file is attached: a sheet per rig with the daily hours, productivity and revenue, and the FINAL sheet.</p>"
        f"<table cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse:collapse\"><tr>{head}</tr>{''.join(body)}</table>"
        + (f"<ul style=\"color:#555\">{''.join(f'<li>{html.escape(t)}</li>' for t in notes)}</ul>" if notes else "")
    )
    text = f"Rig Performance, {end:%B %Y} up to {end:%d/%m/%Y}. The month's Excel file is attached.\n" + "\n".join(f"{r['name']}: productivity {_p(r['avg_prod'])}, revenue {_cr(r['revenue'])} Cr" for r in data["rigs"])
    name = f"Rig_Performance-{end:%B}-{end:%Y}.xlsx"
    return ReportMail(subject, _page(inner), text, [(name, build_workbook(data), XLSX)], False, f"{len(data['rigs'])} rigs, {end:%B %Y} to {end:%d/%m/%Y}")


class RigPerformanceJob(ScheduledReportJob):
    key = JOB_KEY
    name = "Rig Performance"
    report_name = "Rig Performance"
    description = "The month-to-date rig performance file (hours per rate, productivity, revenue, diesel) for every rig, every day."
    trigger_entity = ENTITY_KEY
    trigger_action = ACTION
    trigger_code = TRIGGER_CODE

    def build(self, alert, now):
        return build_mail(alert, now)

    def send_report(self, alert, setup, now, designated=True):
        """As every report job, and then the month that has just ended is closed (its ILM day count becomes final), unless a rig still has to enter its ILM days."""
        out = super().send_report(alert, setup, now, designated)
        try:
            previous = (now.date().replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
            close_month(previous, note="closed automatically at month end", auto=True)
        except Exception:  # closing must never fail the mail that has already gone
            import logging

            logging.getLogger("seros.scheduler").exception("could not close the previous month's Rig Performance plans")
        return out


JOB = RigPerformanceJob()


def ensure_setup(alert_id=None, alert_name=ALERT_NAME):
    """Creates the scheduler's job row and, when the alert can be found (by id, else by name), the trigger row that connects the mail to it."""
    from django.utils import timezone

    from .models import MailAlertDtl, NotificationTrigger, SchedJob

    did = []
    SchedJob.objects.get_or_create(job_key=JOB_KEY, defaults={"name": JOB.name, "enabled": "Y"})
    if NotificationTrigger.objects.filter(entity_key=ENTITY_KEY, action=ACTION).exists():
        return did
    alert = MailAlertDtl.objects.filter(pk=alert_id).first() if alert_id else MailAlertDtl.objects.filter(alert_name__iexact=alert_name).order_by("alert_id").first()
    if alert is None:
        return did
    NotificationTrigger.objects.create(entity_key=ENTITY_KEY, action=ACTION, alert=alert, notification_trigger_active="Y", cr_user_id=0, cr_dt=timezone.now())
    did.append(f"trigger row created for alert {alert.alert_id} ({alert.alert_name})")
    return did
