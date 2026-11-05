"""Rig Operations dashboard: one rig-by-rig, month-by-month, day-by-day picture of the daily drilling reports. A re-implementation of the Rig Operations
workbook (Dashboard.xlsx, spec rig-ops-dashboard-spec.md) on the system's own data: the workbook's "paste the export" step is the daily report itself.
Everything is read from DrillingDtl (the day), DrillingDtlOps (the operations) and DrillingHdr (the well); nothing is entered here.

Definitions, chosen so that every page of the system agrees (5 Nov 2026; the two marked * are to be confirmed with Arjun):
  Metres drilled *   the daily report's own figure (DrillingDtl.drilling_meterage = the sum of |depth to - depth from| of the "Drill actual" operations), the
                     same figure Operations Analytics and Drilling Performance use. The workbook clamps a reversed depth to 0; here it counts as the typed
                     difference and the day is flagged as a possible typo.
  Avg ROP            metres drilled / hours of the "Drill actual" operation (not the average of the recorded ROP figures Drilling Performance uses).
  Productive hours * the classes of core/rate_classes.py (every class except Zero Rate); Productivity % = productive hours / all hours; Operating % = R1 hours / all.
  Revenue            hours x the rate per hour of the operation's own project rate row (Project Drilling Rates), for the classes that are billed per hour (not
                     rig moves: ILM/IPM lump sums are not included, as in the workbook), in crore.
  Hours              from the operations (duration), never from the daily buckets, which are only reconciled against them in Things to check.
  Wells completed    wells whose completion date (Drilling Information) falls in the dates.
  Rig-days           the rig's daily reports in the dates (a report with no operation lines counts, and is flagged in Things to check).
  Things to check    days where the operations do not add up to 24 hours, the daily buckets (+ force majeure) differ from the operations, or a Drill actual row has a Depth To below its Depth From; the latest 730
                     days of data, for the chosen rigs, whatever the dates.
Scope per widget as in the spec: tiles, class hours and top operations follow rig + dates; the rig comparison follows the dates only; the monthly trend is the 12
months ending at the To month and the daily trend the 31 days ending at To (both follow the rigs); the status board follows neither; the well table follows the
rigs only (the latest 12 wells)."""

import calendar
import datetime
from collections import defaultdict
from decimal import Decimal

from django.db.models import Case, DecimalField, F, Max, Sum, Value, When
from rest_framework.response import Response
from rest_framework.views import APIView

from . import rate_classes as rc
from .dashboard_access import dashboard_rig_queryset, get_accessible_rig_ids
from .models import DrillingDtl, DrillingDtlOps, DrillingHdr
from .permissions import HasMenuPermission

DRILL_ACTUAL_OPS_ID = 2
CRORE = 10_000_000.0
CHECK_WINDOW_DAYS = 730
RECENT_RIG_DAYS = 400  # the status board lists rigs that reported in the last ~13 months
WELLS_SHOWN = 12
MONTH_FMT = "%Y-%m"
# The kinds of thing the Things to check list can show (a day can have several): the filters of the list
CHECK_KINDS = [("no_ops", "No operation lines"), ("not_24", "Hours not 24"), ("summary", "Summary differs"), ("depth", "Depth reversed")]


def _f(v):
    return float(v) if v is not None else 0.0


def _r(v, nd=2):
    return None if v is None else round(float(v), nd)


def _div(a, b):
    return a / b if b else None


class _Agg:
    """Hours, money and metres of one rig (or one month, one day) as the rows are read."""

    __slots__ = ("hours", "by_class", "productive", "drilling_hrs", "revenue", "by_op")

    def __init__(self):
        self.hours = 0.0
        self.by_class = defaultdict(float)
        self.productive = 0.0
        self.drilling_hrs = 0.0
        self.revenue = 0.0
        self.by_op = defaultdict(float)

    def add(self, hours, cls, ops_id, revenue):
        self.hours += hours
        self.by_class[cls] += hours
        if rc.is_productive(cls):
            self.productive += hours
        if ops_id == DRILL_ACTUAL_OPS_ID:
            self.drilling_hrs += hours
        self.revenue += revenue
        self.by_op[ops_id] += hours


def _month_start(d):
    return d.replace(day=1)


def _add_months(first, n):
    y, m = divmod(first.year * 12 + first.month - 1 + n, 12)
    return datetime.date(y, m + 1, 1)


def check_rows_for(accessible_ids, data_max, rigs):
    """Everything that is to be checked in the latest CHECK_WINDOW_DAYS of data, for every accessible rig: (rows, per-rig counts). One row per rig-day:
    {rig_id, rig, date, ops_hours, summary_hours, problems [texts], kinds [keys of CHECK_KINDS], dtl_id}. Used by the dashboard's tile (the count) and by the Things to
    check page (the list, paged)."""
    check_from = data_max - datetime.timedelta(days=CHECK_WINDOW_DAYS)
    day_ops_hours = {}
    for row in (
        DrillingDtlOps.objects.filter(drilling_dtl__rig_id__in=accessible_ids, drilling_dtl__drilling_dtl_dt__gte=check_from)
        .values("drilling_dtl_id")
        .annotate(
            h=Sum("duration"),
            fm=Sum(Case(When(prj_drilling_rate__drilling_rate_id__in=rc.rate_ids_of(rc.FORCE_MAJEURE), then=F("duration")), default=Value(0), output_field=DecimalField(max_digits=12, decimal_places=2))),
        )
    ):
        day_ops_hours[row["drilling_dtl_id"]] = (_f(row["h"]), _f(row["fm"]))
    # Drill actual rows whose Depth To is below the Depth From (a typo, or a hole drilled back): they count as negative metres, so the day is to be checked
    reversed_rows = defaultdict(list)  # drilling_dtl_id -> ["18:00-06:00: Depth From 2,114.00 m, Depth To 2,050.00 m"]
    for dtl_id, t_from, t_to, d_from_v, d_to_v in DrillingDtlOps.objects.filter(
        drilling_dtl__rig_id__in=accessible_ids, drilling_dtl__drilling_dtl_dt__gte=check_from, drilling_ops_id=DRILL_ACTUAL_OPS_ID, depth_from__isnull=False, depth_to__isnull=False, depth_to__lt=F("depth_from")
    ).values_list("drilling_dtl_id", "time_from", "time_to", "depth_from", "depth_to"):
        when = f"{t_from:%H:%M}-{t_to:%H:%M}" if t_from and t_to else "a row"
        reversed_rows[dtl_id].append(f"Drill actual {when}: Depth To {d_to_v:,.2f} m is below Depth From {d_from_v:,.2f} m")
    check_rows = []
    check_days = defaultdict(int)
    for d in DrillingDtl.objects.filter(rig_id__in=accessible_ids, drilling_dtl_dt__gte=check_from).values(
        "drilling_dtl_id", "rig_id", "drilling_dtl_dt", "operating_hrs", "standby_hrs", "repair_service_hrs", "repair_rate_hrs", "zero_rate_hrs", "rig_move_hrs"
    ):
        h, fm = day_ops_hours.get(d["drilling_dtl_id"], (0.0, 0.0))
        buckets = sum(_f(d[k]) for k in ("operating_hrs", "standby_hrs", "repair_service_hrs", "repair_rate_hrs", "zero_rate_hrs", "rig_move_hrs"))
        flags, kinds = [], []
        if h == 0:
            flags.append("no operation lines")
            kinds.append("no_ops")
        else:
            if abs(h - 24) > 0.005:
                flags.append("operations add up to %s h, not 24" % round(h, 2))
                kinds.append("not_24")
            if abs(buckets + fm - h) > 0.005:
                flags.append("daily summary %s h differs from the operations %s h" % (round(buckets + fm, 2), round(h, 2)))
                kinds.append("summary")
        if reversed_rows.get(d["drilling_dtl_id"]):
            flags.extend(reversed_rows[d["drilling_dtl_id"]])
            kinds.append("depth")
        if flags:
            check_days[d["rig_id"]] += 1
            check_rows.append({"rig_id": d["rig_id"], "rig": rigs.get(d["rig_id"], ""), "date": d["drilling_dtl_dt"].isoformat(), "ops_hours": round(h, 2), "summary_hours": round(buckets + fm, 2), "problems": flags, "kinds": kinds, "dtl_id": d["drilling_dtl_id"]})
    return check_rows, check_days


def build_payload(rig_ids, accessible_ids, d_from, d_to):
    """The dashboard as data. rig_ids = the chosen rigs (a subset of accessible_ids); d_from / d_to may be None (all the data)."""
    accessible_ids = set(accessible_ids)
    rig_ids = set(rig_ids) & accessible_ids
    rigs = {r.rig_id: r.rig_name for r in dashboard_rig_queryset().filter(rig_id__in=accessible_ids)}
    data_max = DrillingDtl.objects.filter(rig_id__in=accessible_ids).aggregate(m=Max("drilling_dtl_dt"))["m"]
    data_min = DrillingDtl.objects.filter(rig_id__in=accessible_ids).order_by("drilling_dtl_dt").values_list("drilling_dtl_dt", flat=True).first()
    if data_max is None:
        return {"data_through": None, "empty": True, "rigs": [{"rig_id": i, "rig_name": n} for i, n in sorted(rigs.items(), key=lambda x: x[1])]}
    d_from = d_from or data_min
    d_to = d_to or data_max
    if d_from > d_to:
        d_from, d_to = d_to, d_from

    month_end_first = _month_start(d_to)
    month_first = _add_months(month_end_first, -11)  # the 12 months ending at the month of To
    daily_first = d_to - datetime.timedelta(days=30)
    fetch_from = min(d_from, month_first, daily_first)

    # ── operations: one pass over the rows of every accessible rig ──
    per_rig = defaultdict(_Agg)  # in the dates, every accessible rig (the comparison)
    monthly = defaultdict(_Agg)  # month -> chosen rigs
    daily_ops = defaultdict(float)  # day -> operating hours, chosen rigs
    all_ops = _Agg()  # in the dates, chosen rigs
    depth_errors = 0
    depth_error_days = set()
    depth_error_rows = {}  # (rig id, day) -> ["07:00-09:30: 1,200 m to 1,150 m", ...]
    ops = DrillingDtlOps.objects.filter(
        drilling_dtl__rig_id__in=accessible_ids, drilling_dtl__drilling_dtl_dt__gte=fetch_from, drilling_dtl__drilling_dtl_dt__lte=d_to
    ).values_list("drilling_dtl__rig_id", "drilling_dtl__drilling_dtl_dt", "prj_drilling_rate__drilling_rate_id", "prj_drilling_rate__rate", "drilling_ops_id", "duration", "depth_from", "depth_to", "drilling_dtl_id", "time_from", "time_to")
    for rig_id, day, rate_id, rate, ops_id, duration, depth_from, depth_to, dtl_id, t_from, t_to in ops.iterator(chunk_size=5000):
        hours = _f(duration)
        cls = rc.class_of(rate_id)
        revenue = hours * _f(rate) if (cls in rc.PRICED_CLASSES and rate is not None) else 0.0
        in_dates = d_from <= day <= d_to
        chosen = rig_id in rig_ids
        if in_dates:
            per_rig[rig_id].add(hours, cls, ops_id, revenue)
            if chosen:
                all_ops.add(hours, cls, ops_id, revenue)
                if ops_id == DRILL_ACTUAL_OPS_ID and depth_to is not None and depth_from is not None and depth_to < depth_from:
                    depth_errors += 1
                    depth_error_days.add((rig_id, day, dtl_id))
                    when = f"{t_from:%H:%M}-{t_to:%H:%M}" if t_from and t_to else "a row"
                    depth_error_rows.setdefault((rig_id, day), []).append(f"{when}, Drill actual: Depth From {depth_from:,.2f} m, Depth To {depth_to:,.2f} m")
        if chosen:
            if month_first <= day < _add_months(month_end_first, 1):
                monthly[_month_start(day)].add(hours, cls, ops_id, revenue)
            if daily_first <= day <= d_to and cls == rc.OPERATING:
                daily_ops[day] += hours

    # ── days: diesel, metres, rig-days, the daily series ──
    dtl_rows = DrillingDtl.objects.filter(rig_id__in=accessible_ids, drilling_dtl_dt__gte=fetch_from, drilling_dtl_dt__lte=d_to).values_list(
        "rig_id", "drilling_dtl_dt", "consumption_diesel", "drilling_meterage"
    )
    rig_days = defaultdict(int)
    diesel = defaultdict(float)
    metres = defaultdict(float)
    m_metres, m_diesel = defaultdict(float), defaultdict(float)
    daily_metres, daily_diesel = defaultdict(float), defaultdict(float)
    for rig_id, day, dsl, mtr in dtl_rows.iterator(chunk_size=5000):
        chosen = rig_id in rig_ids
        if d_from <= day <= d_to:
            rig_days[rig_id] += 1
            diesel[rig_id] += _f(dsl)
            metres[rig_id] += _f(mtr)
        if chosen:
            if month_first <= day < _add_months(month_end_first, 1):
                m_metres[_month_start(day)] += _f(mtr)
            if daily_first <= day <= d_to:
                daily_metres[day] += _f(mtr)
                daily_diesel[day] += _f(dsl)

    # ── wells completed in the dates ──
    done = defaultdict(int)
    for rid, _ in DrillingHdr.objects.filter(
        rig_id__in=accessible_ids, drilling_completion_dt__isnull=False, drilling_completion_dt__date__gte=d_from, drilling_completion_dt__date__lte=d_to
    ).values_list("rig_id", "drilling_hdr_id"):
        done[rid] += 1

    # ── things to check: the count here, the list on its own page (things_to_check_page) ──
    check_rows, check_days = check_rows_for(accessible_ids, data_max, rigs)
    # the list shows the chosen rigs' flagged days, newest first (the comparison's per-rig counts cover every rig)
    chosen_check = sorted((r for r in check_rows if r["rig_id"] in rig_ids), key=lambda r: (r["date"], r["rig"]), reverse=True)

    # ── the tiles ──
    def tiles(agg, rig_set):
        drilled = sum(metres[r] for r in rig_set)
        dsl = sum(diesel[r] for r in rig_set)
        return {
            "total_hrs": _r(agg.hours), "operating_hrs": _r(agg.by_class[rc.OPERATING]), "operating_pct": _r(_div(agg.by_class[rc.OPERATING], agg.hours) * 100 if agg.hours else None),
            "productive_hrs": _r(agg.productive), "productivity_pct": _r(_div(agg.productive, agg.hours) * 100 if agg.hours else None),
            "drilled_m": _r(drilled, 1), "drilling_hrs": _r(agg.drilling_hrs), "avg_rop": _r(_div(drilled, agg.drilling_hrs)), "diesel_l": int(round(dsl)),
            "diesel_per_m": _r(_div(dsl, drilled)), "revenue_cr": _r(agg.revenue / CRORE, 4), "rig_days": sum(rig_days[r] for r in rig_set),
            "wells_completed": sum(done[r] for r in rig_set), "days_to_check": sum(check_days[r] for r in rig_set),
        }

    kpis = tiles(all_ops, rig_ids)

    # ── warnings ──
    warnings = []
    unmapped = all_ops.by_class.get(rc.UNMAPPED, 0.0)
    if unmapped:
        warnings.append(f"{unmapped:,.2f} hrs have a rate type that is not a time class (Other, meterage, MOB, KMS): they count in the total hours but are not productive.")
    no_rev = [rigs.get(r, str(r)) for r in sorted(rig_ids, key=lambda x: rigs.get(x, "")) if per_rig[r].hours and not per_rig[r].revenue]
    if no_rev:
        warnings.append("Revenue is 0 for: " + ", ".join(no_rev) + " - no rate per hour in Project Drilling Rates.")
    no_ops = [(rigs.get(r["rig_id"]), r["date"]) for r in check_rows if "no operation lines" in r["problems"] and r["rig_id"] in rig_ids and d_from.isoformat() <= r["date"] <= d_to.isoformat()]
    if no_ops:
        warnings.append(f"{len(no_ops)} daily report(s) in these dates have no operation lines, so their hours are missing (see Things to check).")

    # ── status board (a fixed number of queries, however many rigs there are) ──
    recent_from = data_max - datetime.timedelta(days=RECENT_RIG_DAYS)
    last_day = {r["rig_id"]: r["m"] for r in DrillingDtl.objects.filter(rig_id__in=rigs.keys()).values("rig_id").annotate(m=Max("drilling_dtl_dt")) if r["m"] >= recent_from}
    last_dtl = {}
    for d in DrillingDtl.objects.filter(rig_id__in=last_day.keys(), drilling_dtl_dt__in=set(last_day.values())).select_related("drilling_hdr").order_by("drilling_dtl_id"):
        if d.drilling_dtl_dt == last_day.get(d.rig_id):
            last_dtl[d.rig_id] = d  # the latest report of each rig (the highest id when a day has two)
    last_ops = {}
    for op in DrillingDtlOps.objects.filter(drilling_dtl_id__in=[d.drilling_dtl_id for d in last_dtl.values()]).select_related("drilling_ops", "drilling_section", "prj_drilling_rate__drilling_rate").order_by("time_from", "drilling_dtl_ops_id"):
        last_ops[op.drilling_dtl_id] = op  # the later row replaces the earlier: the day's last operation
    hdr_ids = {d.drilling_hdr_id for d in last_dtl.values() if d.drilling_hdr_id}
    depth_of = {r["drilling_dtl__drilling_hdr_id"]: r["m"] for r in DrillingDtlOps.objects.filter(drilling_dtl__drilling_hdr_id__in=hdr_ids).values("drilling_dtl__drilling_hdr_id").annotate(m=Max("depth_to"))}
    board = []
    for rid in sorted(last_dtl, key=lambda x: rigs[x]):
        last = last_dtl[rid]
        op = last_ops.get(last.drilling_dtl_id)
        board.append({
            "rig_id": rid, "rig": rigs[rid], "last_report": last.drilling_dtl_dt.isoformat(), "dtl_id": last.drilling_dtl_id, "hdr_id": last.drilling_hdr_id,
            "location": last.drilling_hdr.location if last.drilling_hdr_id else "", "depth_m": _r(depth_of.get(last.drilling_hdr_id), 0),
            "section": op.drilling_section.drilling_section_name if op is not None and op.drilling_section_id else "",
            "last_operation": f"{op.drilling_ops.drilling_ops_code_no}: {op.drilling_ops.drilling_ops_name}" if op is not None else "",
            "rate": op.prj_drilling_rate.drilling_rate.rate_code if op is not None and op.prj_drilling_rate_id else "",
        })

    # ── comparison (dates only, every accessible rig that has data in the dates) ──
    comparison = []
    for rid in sorted(rigs, key=lambda x: rigs[x]):
        agg = per_rig.get(rid)
        if agg is None and not rig_days.get(rid):
            continue
        agg = agg or _Agg()
        row = tiles(agg, {rid})
        row.update({"rig_id": rid, "rig": rigs[rid], "check_days": check_days[rid]})
        comparison.append(row)
    total_agg = _Agg()
    for rid in rigs:
        a = per_rig.get(rid)
        if a:
            total_agg.hours += a.hours
            total_agg.productive += a.productive
            total_agg.drilling_hrs += a.drilling_hrs
            total_agg.revenue += a.revenue
            for k, v in a.by_class.items():
                total_agg.by_class[k] += v
    shown = {r["rig_id"] for r in comparison}
    total = tiles(total_agg, shown)
    total.update({"rig_id": None, "rig": "Total", "check_days": sum(r["check_days"] for r in comparison)})
    comparison.append(total)

    # ── trends ──
    months = []
    for i in range(12):
        first = _add_months(month_first, i)
        a = monthly.get(first, _Agg())
        months.append({
            "month": first.strftime(MONTH_FMT), "total_hrs": _r(a.hours), "productive_hrs": _r(a.productive), "productivity_pct": _r(_div(a.productive, a.hours) * 100 if a.hours else None),
            "revenue_cr": _r(a.revenue / CRORE, 4), "drilled_m": _r(m_metres[first], 1),
        })
    days = []
    for i in range(31):
        d = daily_first + datetime.timedelta(days=i)
        days.append({"date": d.isoformat(), "drilled_m": _r(daily_metres[d], 1), "diesel_l": int(round(daily_diesel[d])), "operating_hrs": _r(daily_ops[d])})

    # ── where the time goes ──
    classes = [{"class": c, "hours": _r(all_ops.by_class.get(c, 0.0))} for c in rc.CLASSES]
    classes.append({"class": rc.UNMAPPED, "hours": _r(all_ops.by_class.get(rc.UNMAPPED, 0.0))})
    from .models import MstDrillingOperation

    names = {o.drilling_ops_id: f"{o.drilling_ops_code_no}: {o.drilling_ops_name}" for o in MstDrillingOperation.objects.all()}
    top = sorted(((oid, h) for oid, h in all_ops.by_op.items() if h > 0), key=lambda x: (-x[1], x[0]))[:10]
    top_ops = [{"operation": names.get(oid, str(oid)), "hours": _r(h)} for oid, h in top]

    # ── wells (the latest 12 of the chosen rigs, any date; two queries for all of them) ──
    hdrs = list(DrillingHdr.objects.filter(rig_id__in=rig_ids).order_by("-first_anchor_down_dt", "-drilling_hdr_id")[:WELLS_SHOWN])[::-1]
    hdr_ids = [h.drilling_hdr_id for h in hdrs]
    dtls_of = defaultdict(list)
    hdr_of_dtl = {}
    for dtl_id, hdr_id, day, dsl, mtr in DrillingDtl.objects.filter(drilling_hdr_id__in=hdr_ids).values_list("drilling_dtl_id", "drilling_hdr_id", "drilling_dtl_dt", "consumption_diesel", "drilling_meterage"):
        dtls_of[hdr_id].append((day, _f(dsl), _f(mtr)))
        hdr_of_dtl[dtl_id] = hdr_id
    well_agg = defaultdict(_Agg)
    well_depth = {}
    for dtl_id, rate_id, rate, ops_id, duration, dto in DrillingDtlOps.objects.filter(drilling_dtl_id__in=list(hdr_of_dtl)).values_list(
        "drilling_dtl_id", "prj_drilling_rate__drilling_rate_id", "prj_drilling_rate__rate", "drilling_ops_id", "duration", "depth_to"
    ).iterator(chunk_size=5000):
        hid = hdr_of_dtl[dtl_id]
        cls = rc.class_of(rate_id)
        well_agg[hid].add(_f(duration), cls, ops_id, _f(duration) * _f(rate) if cls in rc.PRICED_CLASSES and rate is not None else 0.0)
        if dto is not None and (well_depth.get(hid) is None or dto > well_depth[hid]):
            well_depth[hid] = dto
    well_rows = []
    for h in hdrs:
        a = well_agg.get(h.drilling_hdr_id, _Agg())
        days_rows = dtls_of.get(h.drilling_hdr_id, [])
        first_day = min((x[0] for x in days_rows), default=h.first_anchor_down_dt.date())
        last_day = max((x[0] for x in days_rows), default=first_day)
        drilled = sum(x[2] for x in days_rows)
        dsl = sum(x[1] for x in days_rows)
        well_rows.append({
            "rig": rigs.get(h.rig_id, ""), "location": h.location or "", "status": "Completed" if h.drilling_completion_dt else "In progress", "days": (last_day - first_day).days + 1,
            "depth_m": _r(well_depth.get(h.drilling_hdr_id), 0), "drilled_m": _r(drilled, 1), "rop": _r(_div(drilled, a.drilling_hrs)), "productivity_pct": _r(_div(a.productive, a.hours) * 100 if a.hours else None),
            "revenue_cr": _r(a.revenue / CRORE, 4), "diesel_l": int(round(dsl)), "diesel_per_m": _r(_div(dsl, drilled)), "hdr_id": h.drilling_hdr_id, "first_report": first_day.isoformat(),
        })

    return {
        "data_through": data_max.isoformat(), "from": d_from.isoformat(), "to": d_to.isoformat(), "rigs": [{"rig_id": i, "rig_name": n} for i, n in sorted(rigs.items(), key=lambda x: x[1])],
        "selected_rig_ids": sorted(rig_ids), "kpis": kpis, "warnings": warnings, "status_board": board, "comparison": comparison, "monthly": months, "daily": days,
        "hours_by_class": classes, "top_operations": top_ops, "wells": well_rows, "days_to_check_total": len(chosen_check),
        "check_kinds": [{"key": k, "label": lab, "count": sum(1 for r in chosen_check if k in r["kinds"])} for k, lab in CHECK_KINDS],
        "productive_rule": rc.rule_text(),
        "depth_error_days": [{"rig_id": r, "rig": rigs.get(r, ""), "date": d.isoformat(), "dtl_id": i} for r, d, i in sorted(depth_error_days, key=lambda x: (str(rigs.get(x[0])), x[1]))[:20]],
    }


PAGE_SIZE = 25


def things_to_check_page(rig_ids, accessible_ids, kind=None, page=1, page_size=PAGE_SIZE):
    """One page of the Things to check list for the chosen rigs, newest first, optionally of one kind: {count, results, kinds (with counts, for the chosen rigs), page, page_size, next}."""
    accessible_ids = set(accessible_ids)
    rig_ids = set(rig_ids) & accessible_ids
    rigs = {r.rig_id: r.rig_name for r in dashboard_rig_queryset().filter(rig_id__in=accessible_ids)}
    data_max = DrillingDtl.objects.filter(rig_id__in=accessible_ids).aggregate(m=Max("drilling_dtl_dt"))["m"]
    if data_max is None:
        return {"count": 0, "results": [], "kinds": [{"key": k, "label": lab, "count": 0} for k, lab in CHECK_KINDS], "page": 1, "page_size": page_size, "next": None, "window_days": CHECK_WINDOW_DAYS}
    rows, _days = check_rows_for(accessible_ids, data_max, rigs)
    mine = sorted((r for r in rows if r["rig_id"] in rig_ids), key=lambda r: (r["date"], r["rig"]), reverse=True)
    kinds = [{"key": k, "label": lab, "count": sum(1 for r in mine if k in r["kinds"])} for k, lab in CHECK_KINDS]
    if kind in {k for k, _ in CHECK_KINDS}:
        mine = [r for r in mine if kind in r["kinds"]]
    page_size = max(1, min(int(page_size or PAGE_SIZE), 100))
    page = max(1, int(page or 1))
    chunk = mine[(page - 1) * page_size: page * page_size]
    return {"count": len(mine), "results": chunk, "kinds": kinds, "page": page, "page_size": page_size, "next": page + 1 if page * page_size < len(mine) else None, "window_days": CHECK_WINDOW_DAYS}


def _date(v):
    try:
        return datetime.date.fromisoformat(v) if v else None
    except ValueError:
        return None


class RigOperationsDashboardView(APIView):
    permission_classes = [HasMenuPermission]
    entity_key = "dashboards.rig_operations"

    def get(self, request):
        accessible = get_accessible_rig_ids(request)  # None = every rig
        rig_qs = dashboard_rig_queryset()
        if accessible is not None:
            rig_qs = rig_qs.filter(rig_id__in=accessible)
        accessible_ids = {r.rig_id for r in rig_qs}
        requested = request.query_params.get("rigs")
        chosen = {int(x) for x in requested.split(",") if x.strip().isdigit()} & accessible_ids if requested else set(accessible_ids)
        return Response(build_payload(chosen or accessible_ids, accessible_ids, _date(request.query_params.get("from")), _date(request.query_params.get("to"))))


class RigOperationsThingsToCheckView(APIView):
    """The Things to check list on its own page: GET ?rigs=1,2&kind=depth&page=1&page_size=25. Same right and the same rigs as the dashboard."""

    permission_classes = [HasMenuPermission]
    entity_key = "dashboards.rig_operations"

    def get(self, request):
        accessible = get_accessible_rig_ids(request)
        rig_qs = dashboard_rig_queryset()
        if accessible is not None:
            rig_qs = rig_qs.filter(rig_id__in=accessible)
        accessible_ids = {r.rig_id for r in rig_qs}
        requested = request.query_params.get("rigs")
        chosen = {int(x) for x in requested.split(",") if x.strip().isdigit()} & accessible_ids if requested else set(accessible_ids)
        qp = request.query_params
        page = qp.get("page") if (qp.get("page") or "").isdigit() else 1
        size = qp.get("page_size") if (qp.get("page_size") or "").isdigit() else PAGE_SIZE
        return Response(things_to_check_page(chosen or accessible_ids, accessible_ids, qp.get("kind"), page, size))
