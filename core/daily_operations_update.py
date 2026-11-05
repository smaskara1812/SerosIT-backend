"""The Daily Operations Update mail: for every working rig, a table of hours per rate (today, week, month, year, project to date) with a chart in the mail
body, and a PDF ("Daily Operations Summary Report", one page per rig) attached; sent on the alert's cycle (core/report_job.py). A port of the legacy
"Daily Operations Update" alert, built as the legacy did, from two stored procedures:
  * Prc_Qry_Rig_Rate_Today_Week_Mnth_Yr_Prj_Wise ('Get_Final_Result'): the table and chart of every rig in the mail body;
  * Prc_Qry_Daily_Operations_Update_Report ('Get_Daily_Operations_Summary_Report'): the PDF.
The day reported is yesterday. How the figures are made (kept exactly as the legacy procedures made them, quirks included):
  Mail body
  * Rigs: the latest active contract line of each rig (no end date on the line or the contract), which has a daily drilling report on that contract in the
    last 30 days; in rig order. The legacy body counted those 30 days back from today, the PDF from yesterday.
  * Period starts: week = the Sunday on or before the day; month = the 1st; year = 1 January; project = the rig's first anchor-down date on its current
    contract. A period that starts before the project is cut at the project start.
  * Hours per rate (rates R1, R2, R3, R0, FM, ILM, IPM-Lateral, IPM-Adjacent) = the activity hours of the period on the rig's current contract, DIVIDED BY THE
    NUMBER OF DAYS OF THE PERIOD, so week, month, year and project show a daily average, not a total. Total = the sum of the rate rows.
  * % = the rate's hours x 100 / the Total (only when both are not 0). Uptime = the % of R1 plus the % of R2. HSD (diesel) = the period's diesel used, also
    divided by its days, whole litres (cut, not rounded). Uptime and HSD are one figure per period.
  * Last Update On = the rig's latest daily report date; Days Diff. = days from then to today ('-' when it is today).
  PDF page of a rig
  * NPT% = (repair service + repair rate + zero rate hours of the day) / 24; Average Tripping Speed = the average of |ROP trip| of the 'Trips' activities
    from the 1st of the month to the rig's last report date (whole number); HSD Consumed = diesel of the rig's last report date; Average HSD = all the
    project's diesel / days since the first anchor down; hazard ID cards of the day (open / closed) and the month's daily average; the two pies are the
    day's hours per activity and per rate; revenue = hours x the project's rate per rate, with metres for the two meterage rates, and the ILM/IPM lump sum
    plus kilometres on the first anchor-down day; UNAPPROVED when the day's report is not approved at level 1.
Differences from the legacy mail, all agreed: the wording says "Seros-IT" where the legacy mail said "S.I.S."; when no rig qualifies the mail still goes,
saying so, with no attachment; a failure is retried and reported by e-mail to SCHEDULER_ERROR_MAIL_TO (core/error_mail.py).

THE LEGACY SQL FUNCTIONS: Gnc_Get_Prj_Drilling_Rate, Fnc_Get_Average_Revenue and Fnc_Get_LastStock_Rig_Diesel are ported from the files given (section "legacy
functions"). Fnc_Get_Days_On_Well was not given: fnc_get_days_on_well is a plain calculation until it is."""

import datetime
import io
import os
from collections import defaultdict
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from xml.sax.saxutils import escape as xml

from PIL import Image, ImageDraw, ImageFont

from .models import DrillingDtl, DrillingDtlOps, DrillingHdr, HazardCard, MstDrillingRate, MstRig, ProjectContractDtl, ProjectDrillingRate
from .report_job import ReportMail, ScheduledReportJob

JOB_KEY = "daily_operations_update"
ENTITY_KEY = "automation"
ACTION = "send_daily_operations_update_mail"
TRIGGER_CODE = "auto.daily_operations_update"
ALERT_NAME = "Daily Operations Update"  # what the setup command looks for when it is not told an alert id
LOOKBACK_DAYS = 30  # a rig is in the report when it has a daily report in the last 30 days (hard-coded in the legacy procedures)
RATE_IDS = (1, 2, 3, 4, 5, 6, 7, 8)
UPTIME_RATES = (1, 2)
OPS_TRIPS = 6
METERAGE_RATES = (13, 14)
ILM_IPM_RATES = (6, 7, 8)
RATE_KMS = 20
PERIODS = ("Today", "Week", "Month", "Year", "Project")
D2 = Decimal("0.01")
SEROS_GREEN, SEROS_NAVY = "#00988A", "#1E2656"
SERIES_COLOURS = ["#4A86E8", "#F4A93B", "#D84315", "#0F6B8F", "#BDBDBD"]  # today, week, month, year, project: as the legacy chart


def _q2(v):
    return None if v is None else Decimal(v).quantize(D2, rounding=ROUND_HALF_UP)


def _date(v):
    return v.date() if isinstance(v, datetime.datetime) else v


# ───────────────────────────── legacy functions ─────────────────────────────
def gnc_get_prj_drilling_rate(drilling_rate_id, contract_id, rig_id):
    """eos.Gnc_Get_Prj_Drilling_Rate: the rate of a drilling rate on a contract for a rig (the row of Project Drilling Rates), or None."""
    if drilling_rate_id is None:
        return None
    r = ProjectDrillingRate.objects.filter(drilling_rate_id=drilling_rate_id, contract_id=contract_id, rig_id=rig_id).order_by("-prj_drilling_rate_id").first()
    return r.rate if r is not None else None


def fnc_get_average_revenue(rig_id, contract_id, from_date, to_date, first_entry_hdr_id):
    """eos.Fnc_Get_Average_Revenue: the TOTAL revenue of the rig on the contract between two dates (the caller divides it by the number of days), or None
    when there is nothing to add up. Two parts, as in the legacy function: (1) every activity of the rig's daily reports between the dates, except ILM and
    IPM, as hours x the rate (metres x the rate for the two meterage rates); (2) for every well of the contract that overlaps the dates and is paid as ILM or
    IPM (its Rate Type is 6, 7 or 8), other than the project's first well: the ILM/IPM rate plus the distance covered x the KMS rate. A well with no such
    rate, or no distance, adds nothing."""
    if from_date is None or to_date is None:
        return None
    parts = []
    rows = DrillingDtlOps.objects.filter(
        drilling_dtl__rig_id=rig_id, drilling_dtl__drilling_hdr__contract_id=contract_id, drilling_dtl__drilling_dtl_dt__gte=from_date, drilling_dtl__drilling_dtl_dt__lte=to_date
    ).exclude(prj_drilling_rate__drilling_rate_id__in=ILM_IPM_RATES).values("prj_drilling_rate__drilling_rate_id", "drilling_ops_id", "duration", "depth_from", "depth_to")
    for r in rows:
        rid = r["prj_drilling_rate__drilling_rate_id"]
        qty = (r["depth_to"] or 0) - (r["depth_from"] or 0) if r["drilling_ops_id"] == 2 and rid in METERAGE_RATES else r["duration"]
        rate = gnc_get_prj_drilling_rate(rid, contract_id, rig_id)
        parts.append((rate or 0) * (qty or 0) if qty is not None else None)
    kms = gnc_get_prj_drilling_rate(RATE_KMS, contract_id, rig_id)
    for h in DrillingHdr.objects.filter(rig_id=rig_id, contract_id=contract_id, drilling_rate_id__in=ILM_IPM_RATES).exclude(pk=first_entry_hdr_id):
        if _date(h.first_anchor_down_dt) <= to_date and (_date(h.drilling_completion_dt) if h.drilling_completion_dt else to_date) >= from_date:
            lump = gnc_get_prj_drilling_rate(h.drilling_rate_id, contract_id, rig_id)
            parts.append(lump + h.distance_covered_kms_knots * kms if lump is not None and kms is not None and h.distance_covered_kms_knots is not None else None)
    parts = [p for p in parts if p is not None]
    return sum(parts, Decimal(0)) if parts else None


def diesel_stock_by_day(rig_id, project_from_date):
    """The diesel stock of the rig day by day from the project's start: [(day, opening, received, consumed, closing)] in date order. As the legacy function:
    the stock is only what the daily reports show (received less consumed, added up from the start date), with no starting stock."""
    if project_from_date is None:
        return []
    out, run = [], Decimal(0)
    for d in DrillingDtl.objects.filter(rig_id=rig_id, drilling_dtl_dt__gte=project_from_date).order_by("drilling_dtl_dt", "pk"):
        rec, con = _q2(d.received_diesel or 0), _q2(d.consumption_diesel or 0)
        opening = run
        run = run + rec - con
        out.append((d.drilling_dtl_dt, opening, rec, con, run))
    return out


def fnc_get_last_stock_rig_diesel(rig_id, project_from_date):
    """eos.Fnc_Get_LastStock_Rig_Diesel: (opening, received, consumed, closing) of the rig's latest daily report on or after the project's start; Nones when
    there is none."""
    series = diesel_stock_by_day(rig_id, project_from_date)
    if not series:
        return None, None, None, None
    _day, opening, rec, con, closing = series[-1]
    return opening, rec, con, closing


def fnc_get_days_on_well(at, first_anchor):
    """eos.Fnc_Get_Days_On_Well: '2 Months 8 Days 1:00 Hrs' from the first anchor down to `at`.
    NOT YET PORTED: the legacy function was not provided; this is a plain calculation (months of 30 days)."""
    if first_anchor is None:
        return "-"
    secs = max(0, int((at - first_anchor).total_seconds()))
    days, rest = divmod(secs, 86400)
    hours, rest = divmod(rest, 3600)
    months, days = divmod(days, 30)
    parts = []
    if months:
        parts.append(f"{months} Month{'s' if months != 1 else ''}")
    parts.append(f"{days} Day{'s' if days != 1 else ''}")
    parts.append(f"{hours}:{rest // 60:02d} Hrs")
    return " ".join(parts)


# ───────────────────────────── which rigs, which contract ─────────────────────────────
def working_rigs(back_from, to, same_contract):
    """[(rig_id, contract_id)] in rig order: the rig's latest active contract line, with a daily report between the two dates (on that contract for the
    mail body, on any contract for the PDF)."""
    latest = {}
    for ln in ProjectContractDtl.objects.filter(rig_active_to__isnull=True, contract__prj_end_dt__isnull=True):
        cur = latest.get(ln.rig_id)
        if cur is None or (ln.rig_active_from, ln.pk) > (cur.rig_active_from, cur.pk):
            latest[ln.rig_id] = ln
    out = []
    for rig_id, ln in sorted(latest.items()):
        q = DrillingDtl.objects.filter(rig_id=rig_id, drilling_dtl_dt__gte=back_from, drilling_dtl_dt__lte=to)
        if same_contract:
            q = q.filter(drilling_hdr__contract_id=ln.contract_id)
        if q.exists():
            out.append((rig_id, ln.contract_id))
    return out


def current_contract(rig_id, day):
    """The contract of the rig's latest contract line that started on or before `day` (and has rates for the rig), else None."""
    best = None
    for ln in ProjectContractDtl.objects.filter(rig_id=rig_id, rig_active_from__lte=day):
        if best is None or (ln.rig_active_from, ln.pk) > (best.rig_active_from, best.pk):
            best = ln
    if best is None or not ProjectDrillingRate.objects.filter(rig_id=rig_id, contract_id=best.contract_id).exists():
        return None
    return best.contract_id


def project_start(rig_id, contract_id, day):
    """The rig's first anchor-down date on the contract (on or before `day`), else None."""
    first = DrillingHdr.objects.filter(rig_id=rig_id, contract_id=contract_id, first_anchor_down_dt__lte=datetime.datetime.combine(day, datetime.time.max)).order_by("first_anchor_down_dt").first()
    return _date(first.first_anchor_down_dt) if first else None


# ───────────────────────────── the mail body ─────────────────────────────
def _hours(rig_id, contract_id, start, end):
    """{rate id: average hours per day or None} and the diesel per day (whole litres or None), for rates 1 to 8."""
    days = Decimal((end - start).days + 1)
    sums = defaultdict(lambda: None)
    rows = (
        DrillingDtlOps.objects.filter(drilling_dtl__rig_id=rig_id, drilling_dtl__drilling_hdr__contract_id=contract_id, drilling_dtl__drilling_dtl_dt__gte=start, drilling_dtl__drilling_dtl_dt__lte=end)
        .values("prj_drilling_rate__drilling_rate_id", "duration")
    )
    for r in rows:
        rid = r["prj_drilling_rate__drilling_rate_id"]
        if rid in RATE_IDS and r["duration"] is not None:
            sums[rid] = (sums[rid] or Decimal(0)) + r["duration"]
    hours = {rid: _q2(sums[rid] / days) if sums[rid] is not None else None for rid in RATE_IDS}
    diesel = [d for d in DrillingDtl.objects.filter(rig_id=rig_id, drilling_hdr__contract_id=contract_id, drilling_dtl_dt__gte=start, drilling_dtl_dt__lte=end).values_list("consumption_diesel", flat=True) if d is not None]
    hsd = int((Decimal(sum(diesel)) / days).quantize(Decimal(1), rounding=ROUND_DOWN)) if diesel else None
    return hours, hsd


def period_starts(day, project_from):
    week = day - datetime.timedelta(days=(day.weekday() + 1) % 7)  # Sunday on or before
    month, year = day.replace(day=1), day.replace(month=1, day=1)
    starts = {"Today": day, "Week": week, "Month": month, "Year": year, "Project": project_from or day}
    for k in ("Week", "Month", "Year"):
        if project_from and project_from > starts[k]:
            starts[k] = project_from
    return starts


def rig_table(rig_id, contract_id, day):
    """The mail block of one rig: {"rates": [{"id","code","Today": {"hrs","pct"}, ...}], "total": {...}, "uptime": {...}, "hsd": {...}} per period."""
    codes = {r.drilling_rate_id: (r.rate_code or "").strip() for r in MstDrillingRate.objects.filter(drilling_rate_id__in=RATE_IDS)}
    starts = period_starts(day, project_start(rig_id, contract_id, day))
    per, hsd, total, uptime = {}, {}, {}, {}
    for p in PERIODS:
        hours, hsd[p] = _hours(rig_id, contract_id, starts[p], day)
        total[p] = _q2(sum((v for v in hours.values() if v is not None), Decimal(0))) if any(v is not None for v in hours.values()) else None
        pct = {}
        for rid, v in hours.items():
            pct[rid] = _q2(v * 100 / total[p]) if v and total[p] else None
        up = [pct[r] for r in UPTIME_RATES if pct.get(r) is not None]
        uptime[p] = _q2(sum(up, Decimal(0))) if up else None
        per[p] = {"hours": hours, "pct": pct}
    rates = [{"id": rid, "code": codes.get(rid, str(rid)), **{p: {"hrs": per[p]["hours"][rid], "pct": per[p]["pct"][rid]} for p in PERIODS}} for rid in RATE_IDS]
    return {"rates": rates, "total": total, "uptime": uptime, "hsd": hsd, "starts": starts}


def rig_header(rig_id, project_from, today):
    last = DrillingDtl.objects.filter(rig_id=rig_id).order_by("-drilling_dtl_dt").values_list("drilling_dtl_dt", flat=True).first()
    diff = (today - last).days if last else 0
    opening, received, consumed, closing = fnc_get_last_stock_rig_diesel(rig_id, project_from)
    return {"last": last, "diff": "-" if diff == 0 else str(diff), "opening": opening, "received": received, "consumed": consumed, "closing": closing}


def collect_body(today):
    """[{"rig","table","header"}] for the mail body: yesterday's figures, rigs with a report in the last 30 days up to today."""
    day = today - datetime.timedelta(days=1)
    out = []
    for rig_id, _latest in working_rigs(today - datetime.timedelta(days=LOOKBACK_DAYS), today, same_contract=True):
        contract = current_contract(rig_id, day)
        if contract is None:
            continue
        table = rig_table(rig_id, contract, day)
        rig = MstRig.objects.get(pk=rig_id)
        out.append({"rig": rig.rig_name, "rig_id": rig_id, "table": table, "header": rig_header(rig_id, project_start(rig_id, contract, day), today)})
    return out


def _n(v, fmt="{:.2f}"):
    return "" if v is None else fmt.format(v)


def _pct(v):
    """The % cell: a float in the legacy table, so 88.00 shows as 88 and 12.50 as 12.5."""
    if v is None:
        return ""
    s = f"{float(v):.2f}".rstrip("0").rstrip(".")
    return s


def _stock(v):
    return "-" if v is None else f"{v:.2f}"


def body_table_html(block):
    t, rig = block["table"], block["rig"]
    font = "font-family:Verdana,Tahoma,Arial;"
    th1 = f"{font}font-size:11px;background-color:{SEROS_GREEN};color:#ffffff;"
    th2 = f"{font}font-size:12px;background-color:{SEROS_NAVY};color:#ffffff;"
    h = block["header"]
    last = h["last"].strftime("%d/%m/%Y") if h["last"] else ""
    top = (
        f"<div style=\"{font}font-size:12px\"><b>Rig : </b>{xml(rig)} , <b>Last Update On : </b>{last} , <b>Days Diff. : </b>{h['diff']}</div>"
        f"<div style=\"{font}font-size:12px\"><b>HSD: Opening Stock : </b>{_stock(h['opening'])} , <b>Consumed : </b>{_stock(h['consumed'])} , <b>Received : </b>{_stock(h['received'])} , <b>Closing : </b>{_stock(h['closing'])}</div><br>"
    )
    rows = [f"<tr style=\"{th1}\"><td><b>Rig : {xml(rig)}</b></td>" + "".join(f"<td colspan=\"4\" align=\"center\"><b>{p} TD</b></td>" if p != "Today" else "<td colspan=\"4\" align=\"center\"><b>Today</b></td>" for p in PERIODS) + "</tr>"]
    rows.append(f"<tr style=\"{th2}\"><td><b>Rate</b></td>" + "<td align=\"center\">Hrs</td><td align=\"center\">%</td><td align=\"center\">Uptime</td><td align=\"center\">HSD</td>" * 5 + "</tr>")
    n = len(t["rates"]) + 1
    for i, r in enumerate(t["rates"] + [None]):
        cells = [f"<td align=\"center\" style=\"background-color:#46BEA9\"><b>{r['code'] if r else 'Total'}</b></td>"]
        for p in PERIODS:
            if r:
                cells.append(f"<td align=\"right\">{_n(r[p]['hrs'])}</td><td align=\"right\">{_pct(r[p]['pct'])}</td>")
            else:
                cells.append(f"<td align=\"right\">{_n(t['total'][p])}</td><td></td>")
            if i == 0:
                cells.append(f"<td align=\"right\" rowspan=\"{n - 1}\">{_n(t['uptime'][p])}</td><td align=\"right\" rowspan=\"{n - 1}\">{'' if t['hsd'][p] is None else t['hsd'][p]}</td>")
            elif r is None:
                cells.append("<td></td><td></td>")
        rows.append(f"<tr style=\"{font}font-size:12px\">{''.join(cells)}</tr>")
    table = f"<table style=\"border-collapse:collapse\" cellpadding=\"3\" cellspacing=\"3\" border=\"1\" bordercolor=\"#000000\" width=\"100%\">{''.join(rows)}</table>"
    return top + table


# ── the chart: drawn with Pillow (reportlab has no PNG output without a system library, and mail programs do not show svg) ──
def _font(size, bold=False):
    f = os.path.join(os.path.dirname(__file__), "fonts", "LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf")
    return ImageFont.truetype(f, size)


def chart_png(block):
    """The clustered bar chart of one rig: a cluster per rate, a bar per period (hours), as the legacy chart. Returns PNG bytes."""
    w, h = 700, 380
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    rates = block["table"]["rates"]
    left, right, top, bottom = 52, w - 18, 40, h - 92
    vals = [float(r[p]["hrs"] or 0) for r in rates for p in PERIODS]
    top_val = max(vals + [1])
    step = 5 if top_val > 12 else 2 if top_val > 6 else 1
    axis_max = (int(top_val // step) + 1) * step
    d.text((w / 2, 16), f"Rig Information : {block['rig']}", fill="#222222", font=_font(13), anchor="mm")
    for k in range(0, axis_max + 1, step):
        y = bottom - (bottom - top) * k / axis_max
        d.line([(left, y), (right, y)], fill="#d9d9d9" if k else "#555555")
        d.text((left - 8, y), str(k), fill="#444444", font=_font(11), anchor="rm")
    d.line([(left, top), (left, bottom)], fill="#555555")
    cluster = (right - left) / len(rates)
    bar = cluster * 0.72 / len(PERIODS)
    for i, r in enumerate(rates):
        x0 = left + i * cluster + cluster * 0.14
        for j, p in enumerate(PERIODS):
            v = float(r[p]["hrs"] or 0)
            if v <= 0:
                continue
            x, y = x0 + j * bar, bottom - (bottom - top) * v / axis_max
            d.rectangle([x, y, x + bar - 1, bottom], fill=SERIES_COLOURS[j])
            d.text((x + bar / 2, y - 3), f"{v:g}", fill="#222222", font=_font(9), anchor="md")
        d.text((left + (i + 0.5) * cluster, bottom + 6), r["code"], fill="#333333", font=_font(10), anchor="ma")
    d.text(((left + right) / 2, bottom + 40), "Rates", fill="#333333", font=_font(11), anchor="mm")
    d.text((left, top - 16), "Hours", fill="#333333", font=_font(11), anchor="ls")
    lx = left
    for j, p in enumerate(PERIODS):
        d.rectangle([lx, h - 24, lx + 8, h - 16], fill=SERIES_COLOURS[j])
        label = f"{p}_TD_Hrs"
        d.text((lx + 13, h - 20), label, fill="#333333", font=_font(10), anchor="lm")
        lx += 13 + int(d.textlength(label, font=_font(10))) + 18
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()


# ───────────────────────────── the PDF ─────────────────────────────
def _money(symbol, v):
    """'~ ₹21,95,367.00': the Indian grouping of the legacy FORMAT(.., 'N', 'en-in')."""
    if v is None:
        return "-"
    neg = v < 0
    whole, frac = f"{abs(Decimal(v)).quantize(D2, rounding=ROUND_HALF_UP):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])
    return f"~ {'-' if neg else ''}{symbol}{whole}.{frac}"


def _symbol(contract_id, rig_id):
    row = ProjectDrillingRate.objects.filter(rig_id=rig_id, contract_id=contract_id).select_related("currency").first()
    if row is None or row.currency_id is None:
        return ""
    if row.currency_id == 1:
        return "Rs. "  # the bundled font (Liberation Sans) has no rupee sign; the legacy PDF printed it
    if row.currency_id == 2:
        return "$"
    return (row.currency.currency_abrv or "").strip()


def _revenue_of_day(rig_id, contract_id, day, first_entry_hdr_id):
    """Revenue today: hours x the project rate per rate (metres for the two meterage rates, ILM and IPM not counted), plus the ILM/IPM lump sum and
    kilometres on the first anchor-down day of a project that has already begun."""
    total = Decimal(0)
    rows = DrillingDtlOps.objects.filter(
        drilling_dtl__rig_id=rig_id, drilling_dtl__drilling_hdr__contract_id=contract_id, drilling_dtl__drilling_dtl_dt=day
    ).values("prj_drilling_rate__drilling_rate_id", "drilling_ops_id", "duration", "depth_from", "depth_to")
    for r in rows:
        rid = r["prj_drilling_rate__drilling_rate_id"]
        if rid in ILM_IPM_RATES:
            continue
        qty = r["duration"]
        if r["drilling_ops_id"] == 2 and rid in METERAGE_RATES:
            qty = (r["depth_to"] or 0) - (r["depth_from"] or 0)
        rate = gnc_get_prj_drilling_rate(rid, contract_id, rig_id)
        total += (rate or 0) * (qty or 0)
    hdrs = [h for h in DrillingHdr.objects.filter(rig_id=rig_id, contract_id=contract_id) if _date(h.first_anchor_down_dt) == day]
    is_first_entry = any(h.pk == first_entry_hdr_id for h in hdrs)
    if not is_first_entry and len(hdrs) == 1:
        h = hdrs[0]
        lump = gnc_get_prj_drilling_rate(h.drilling_rate_id, contract_id, rig_id)
        kms = gnc_get_prj_drilling_rate(RATE_KMS, contract_id, rig_id)
        total += (lump or 0) + (h.distance_covered_kms_knots or 0) * (kms or 0)
    return total


def rig_page(rig_id, contract_id, day, now):
    """Everything one PDF page shows (the figures of Prc_Qry_Daily_Operations_Update_Report for one rig)."""
    rig = MstRig.objects.get(pk=rig_id)
    month_start = day.replace(day=1)
    hdrs = list(DrillingHdr.objects.filter(rig_id=rig_id).order_by("first_anchor_down_dt", "pk"))
    hdr = next((h for h in hdrs if _date(h.first_anchor_down_dt) <= day and (h.drilling_completion_dt is None or _date(h.drilling_completion_dt) >= day)), None)
    proj_hdrs = [h for h in hdrs if h.contract_id == contract_id]
    last_date = DrillingDtl.objects.filter(drilling_hdr_id__in=[h.pk for h in proj_hdrs]).order_by("-drilling_dtl_dt").values_list("drilling_dtl_dt", flat=True).first() if proj_hdrs else None
    first_anchor_rig = _date(proj_hdrs[0].first_anchor_down_dt) if proj_hdrs else None
    cards = HazardCard.objects.filter(rig_id=rig_id, contract_id=contract_id)
    on_day = [c for c in cards.filter(event_dt__date=day)]
    open_n = sum(1 for c in on_day if c.haz_id_card_status == "O")
    closed_n = sum(1 for c in on_day if c.haz_id_card_status == "C")
    in_month = cards.filter(event_dt__date__gte=month_start, event_dt__date__lte=day).count()
    avg_cards = _q2(Decimal(in_month) / ((day - month_start).days + 1))
    haz = defaultdict(int)
    for c in cards.filter(marked_as_deleted="N", event_dt__date=day).select_related("haz_type"):
        haz[(c.haz_type.haz_type_name or "").strip() if c.haz_type_id else "-"] += 1

    dtl_day = DrillingDtl.objects.filter(rig_id=rig_id, drilling_dtl_dt=day)
    remark = next(iter(dtl_day.values_list("remark", flat=True)), "") or ""
    hsd = None
    if last_date is not None:
        v = DrillingDtl.objects.filter(rig_id=rig_id, drilling_hdr__contract_id=contract_id, drilling_dtl_dt=last_date).values_list("consumption_diesel", flat=True).first()
        hsd = v
    trips = list(
        DrillingDtlOps.objects.filter(drilling_ops_id=OPS_TRIPS, drilling_dtl__rig_id=rig_id, drilling_dtl__drilling_hdr__contract_id=contract_id, drilling_dtl__drilling_dtl_dt__gte=month_start, drilling_dtl__drilling_dtl_dt__lte=last_date or day)
        .values_list("rop_trip_mh", flat=True)
    )
    speed = Decimal(int(sum(abs(t or 0) for t in trips) / len(trips))) if trips else Decimal(0)  # whole numbers (integer division), 0 when no trips

    npt = Decimal(0)
    d = DrillingDtl.objects.filter(rig_id=rig_id, drilling_hdr__contract_id=contract_id, drilling_dtl_dt=day).first()
    if d is not None and DrillingDtlOps.objects.filter(drilling_dtl=d).exists():
        npt = _q2(((d.repair_service_hrs or 0) + (d.repair_rate_hrs or 0) + (d.zero_rate_hrs or 0)) / 24 * 100)

    pie_ops, pie_rates = defaultdict(Decimal), defaultdict(Decimal)
    codes = {r.drilling_rate_id: (r.rate_code or "").strip() for r in MstDrillingRate.objects.all()}
    ops = DrillingDtlOps.objects.filter(drilling_dtl__rig_id=rig_id, drilling_dtl__drilling_dtl_dt=day).select_related("drilling_ops", "prj_drilling_rate").order_by("drilling_ops_id")
    for o in ops:
        pie_ops[(o.drilling_ops.drilling_ops_name or "").strip()] += o.duration or 0
        pie_rates[codes.get(o.prj_drilling_rate.drilling_rate_id, "") if o.prj_drilling_rate_id else ""] += o.duration or 0

    first_entry = proj_hdrs[0].pk if proj_hdrs else None
    symbol = _symbol(contract_id, rig_id)
    revenue = _revenue_of_day(rig_id, contract_id, day, first_entry)
    month_total = fnc_get_average_revenue(rig_id, contract_id, month_start, last_date, first_entry) if last_date else None
    proj_total = fnc_get_average_revenue(rig_id, contract_id, first_anchor_rig, last_date, first_entry) if last_date and first_anchor_rig else None
    month_days = ((last_date - month_start).days + 1) if last_date else 0
    proj_days = ((last_date - first_anchor_rig).days + 1) if last_date and first_anchor_rig else 0
    all_diesel = sum(v or 0 for v in DrillingDtl.objects.filter(rig_id=rig_id, drilling_dtl_dt__gte=first_anchor_rig or day, drilling_dtl_dt__lte=last_date or day).values_list("consumption_diesel", flat=True))
    avg_hsd = _q2(Decimal(all_diesel) / proj_days) if proj_days else Decimal(0)

    approved = DrillingDtl.objects.filter(rig_id=rig_id, drilling_hdr__contract_id=contract_id, drilling_dtl_dt=day).values_list("l1_approval_status", flat=True).first()
    anchor = hdr.first_anchor_down_dt if hdr else None
    return {
        "rig": rig.rig_name, "rig_id": rig_id, "location": (hdr.location if hdr else None) or "Rig Move", "npt": npt,
        "anchor": anchor.strftime("%d/%m/%Y %H:%M") if anchor else "-",
        "days_on_well": fnc_get_days_on_well(datetime.datetime.combine(day + datetime.timedelta(days=1), datetime.time(6)), anchor) if anchor else "-",
        "unapproved": (approved or "N") == "N", "hz_open": open_n, "hz_closed": closed_n, "hz_avg": avg_cards, "hazards": dict(haz),
        "ops": dict(pie_ops), "rates": dict(pie_rates), "speed": speed, "hsd": hsd, "avg_hsd": avg_hsd, "remark": (remark or "")[:500],
        "revenue": _money(symbol, revenue),
        # as the legacy procedure: a total that is NULL, or no days, is shown as 0.00 (FORMAT(isnull(x, 0)))
        "rev_month": _money(symbol, (Decimal(month_total) / month_days) if month_total is not None and month_days else Decimal(0)),
        "rev_project": _money(symbol, (Decimal(proj_total) / proj_days) if proj_total is not None and proj_days else Decimal(0)),
        "now": now,
    }


def collect_pdf(today):
    day = today - datetime.timedelta(days=1)
    pages = []
    for rig_id, _c in working_rigs(day - datetime.timedelta(days=LOOKBACK_DAYS), day, same_contract=False):
        contract = current_contract(rig_id, day)
        if contract is not None:
            pages.append((rig_id, contract))
    return pages


def build_pdf(today, now):
    """The PDF bytes of the Daily Operations Summary Report (one page per rig), or None when there is no rig."""
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import ParagraphStyle

    from . import pdf_reportlab as P
    from .company_branding import seros_logo_path

    day = today - datetime.timedelta(days=1)
    pages = [rig_page(rid, cid, day, now) for rid, cid in collect_pdf(today)]
    if not pages:
        return None
    P.register_fonts()
    W, H = A4
    m = 14 * P.MM
    buf = io.BytesIO()
    logo = seros_logo_path()
    base = ParagraphStyle("b", fontName=P.FONT, fontSize=9, leading=12, textColor=colors.black)
    bold = ParagraphStyle("bb", parent=base, fontName=P.FONT_BOLD)
    title = ParagraphStyle("t", parent=bold, fontSize=17, leading=20, alignment=1)
    pie_colours = [colors.HexColor(c) for c in ("#3A639B", "#EEA24E", "#14946F", "#DC5A21", "#B5307B", "#FBD460", "#7A5EA8", "#64B5CD", "#8C8C8C", "#C9A227")]

    def pie_block(heading, data, width):
        out = [Paragraph(f"<b>{xml(heading)}</b>", ParagraphStyle("h", parent=base, fontSize=12, alignment=1, spaceAfter=4))]
        items = [(k, v) for k, v in data.items() if v]
        if not items:
            out.append(Spacer(1, 6))
            return out + [Paragraph(f"No data for {heading}", base), Spacer(1, 60)]
        d = Drawing(width * 0.5, 130)
        pie = Pie()
        pie.x, pie.y, pie.width, pie.height = 40, 10, 110, 110
        pie.data = [float(v) for _k, v in items]
        pie.labels = [f"{float(v):.2f}" for _k, v in items]
        pie.sideLabels = 1
        pie.simpleLabels = 0
        pie.slices.strokeWidth, pie.slices.strokeColor = 0.5, colors.white
        pie.slices.fontName, pie.slices.fontSize = P.FONT, 7
        for i in range(len(items)):
            pie.slices[i].fillColor = pie_colours[i % len(pie_colours)]
        d.add(pie)
        legend = [[ "", Paragraph(xml(k), ParagraphStyle("l", parent=base, fontSize=7, leading=8.5)), f"{float(v):.2f}"] for k, v in items]
        legend.append(["", Paragraph("Total:", ParagraphStyle("l", parent=base, fontSize=7, leading=8.5)), f"{float(sum(v for _k, v in items)):.2f}"])
        lt = Table(legend, colWidths=[8, 100, 28])
        style = [("FONT", (0, 0), (-1, -1), P.FONT, 7), ("ALIGN", (2, 0), (2, -1), "RIGHT"), ("BOX", (0, 0), (-1, -1), 0.5, colors.black), ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]
        for i in range(len(items)):
            style.append(("BACKGROUND", (0, i), (0, i), pie_colours[i % len(pie_colours)]))
        lt.setStyle(TableStyle(style))
        row = Table([[d, lt]], colWidths=[width * 0.52, width * 0.45])
        row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        return out + [row]

    def on_page(c, doc):
        c.saveState()
        c.setLineWidth(0.7)
        c.rect(m / 2, m / 2, W - m, H - m)
        c.setLineWidth(1)
        c.line(m / 2, H - m - 46, W - m / 2, H - m - 46)  # the rule under the header, as in the legacy report
        c.setLineWidth(0.7)
        if logo:
            try:
                c.drawImage(logo, m, H - m - 34, height=34, width=34 * 3.2, preserveAspectRatio=True, mask="auto")
            except Exception:
                pass
        c.setFont(P.FONT_BOLD, 14)
        c.drawCentredString(W / 2 - 22, H - m - 14, "Daily Operations Summary Report")
        pg = doc.page_data[doc.page - 1] if doc.page - 1 < len(doc.page_data) else None
        if pg and pg["unapproved"]:
            c.setFillColor(colors.HexColor("#e00707"))
            c.setFont(P.FONT_BOLD, 13)
            c.drawCentredString(W / 2, H - m - 32, "UNAPPROVED")
            c.setFillColor(colors.black)
        c.setFont(P.FONT, 8)
        c.drawRightString(W - m, H - m - 8, f"Seros-IT Report Date: {now:%d/%m/%Y %H:%M}")
        c.drawRightString(W - m, H - m - 22, f"DPR date: {day:%d-%m-%Y}")
        c.drawRightString(W - m - 6, m / 2 + 8, f"Page {doc.page} of {len(doc.page_data)}")
        c.restoreState()

    doc = BaseDocTemplate(buf, pagesize=A4, leftMargin=m, rightMargin=m, topMargin=m + 46, bottomMargin=m)
    doc.page_data = pages
    fw = W - 2 * m
    doc.addPageTemplates([PageTemplate(frames=[Frame(m, m, fw, H - 2 * m - 46, leftPadding=0, rightPadding=0, topPadding=6, bottomPadding=0)], onPage=on_page)])
    rule, soft = colors.HexColor("#1a3f7a"), colors.HexColor("#d5dbe5")
    label = ParagraphStyle("lab", parent=base, fontName=P.FONT_BOLD, fontSize=8, leading=10, textColor=colors.HexColor("#5b6472"))
    value = ParagraphStyle("val", parent=base, fontSize=10.5, leading=13)
    big = ParagraphStyle("big", parent=base, fontName=P.FONT_BOLD, fontSize=14, leading=17)
    section = ParagraphStyle("sec", parent=base, fontName=P.FONT_BOLD, fontSize=10, leading=12, textColor=rule)
    note = ParagraphStyle("note", parent=base, fontSize=9.5, leading=12.5, textColor=colors.HexColor("#6b7280"))

    def cell(name, val, style=value):
        return [Paragraph(name.upper(), label), Paragraph(val, style)]

    def grid(rows, widths, bg=None):
        t = Table(rows, colWidths=widths)
        st = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("LINEBELOW", (0, 0), (-1, -1), 0.5, soft)]
        if bg:
            st.append(("BACKGROUND", (0, 0), (-1, -1), bg))
        t.setStyle(TableStyle(st))
        return t

    def heading(text):
        t = Table([[Paragraph(xml(text), section)]], colWidths=[fw])
        t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.8, rule), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        return t

    def empty(text):
        return [Spacer(1, 10), Paragraph(xml(text), note), Spacer(1, 18)]

    story = []
    for i, pg in enumerate(pages):
        if i:
            story.append(PageBreak())
        w3 = [fw * 0.34, fw * 0.36, fw * 0.30]
        story.append(grid([[cell("Rig", xml(pg["rig"]), big), cell("Location", xml(pg["location"])), cell("NPT %", f"{pg['npt']:.2f}%")]], w3, colors.HexColor("#f3f6fb")))
        story.append(grid([[cell("First anchor down / spud date", pg["anchor"]), cell("Days on well", xml(pg["days_on_well"])), ""]], w3))
        story.append(heading("Types of Hazards identified"))
        story += pie_block("", pg["hazards"], fw)[1:] if pg["hazards"] else empty("No data for Types of Hazards identified")
        story.append(grid([[cell("Hazard ID cards (open / closed)", f"{pg['hz_open']} / {pg['hz_closed']}"), cell("Average hazard ID cards per day", f"{pg['hz_avg']:.2f}"), ""]], w3, colors.HexColor("#f3f6fb")))
        story.append(heading("Operations Classification"))
        story += pie_block("", pg["ops"], fw)[1:] if pg["ops"] else empty("No data for Code No. Operations")
        story.append(heading("Rates"))
        story += pie_block("", pg["rates"], fw)[1:] if pg["rates"] else empty("No data for Rates")
        story.append(Spacer(1, 4))
        story.append(grid([[cell("Average tripping speed", f"{pg['speed']:.2f}"), cell("HSD consumed", f"{pg['hsd'] if pg['hsd'] is not None else 0:.2f}"), cell("Average HSD consumption this project", f"{pg['avg_hsd']:.2f}")]], w3, colors.HexColor("#f3f6fb")))
        story.append(heading("Operations Summary"))
        story.append(Spacer(1, 4))
        story.append(Paragraph(xml(pg["remark"]).replace("\n", "<br/>") or "-", ParagraphStyle("o", parent=base, fontSize=9.5, leading=13, alignment=4, leftIndent=8, rightIndent=6)))
        story.append(Spacer(1, 8))
        story.append(grid([[cell("Rig", xml(pg["rig"])), cell("Revenue today", xml(pg["revenue"]), ParagraphStyle("rv", parent=value, fontName=P.FONT_BOLD)), ""]], w3))
        story.append(grid([[cell("Average daily revenue this month", xml(pg["rev_month"])), cell("Average daily revenue this project", xml(pg["rev_project"])), ""]], w3))
    doc.build(story)
    return buf.getvalue()


# ───────────────────────────── the mail ─────────────────────────────
def _page(inner):
    return (
        "<div style=\"font-family:Verdana,Tahoma,Arial,sans-serif;font-size:13px\">"
        "<p style=\"color:#e00707;margin:0 0 4px\">Seros-IT Auto Alert</p>"
        f"{inner}"
        "<p style=\"margin:28px 0 0\">This is an automated Mail. Please do not reply.</p></div>"
    )


def build_mail(alert, now):
    """-> ReportMail for the alert (its Mail Subject gives the subject; the Window is not used: the legacy report hard-coded its 30 days)."""
    today = now.date()
    day = today - datetime.timedelta(days=1)
    subject = (alert.mail_subject or "Daily Operations Update").strip()
    blocks = collect_body(today)
    pdf = build_pdf(today, now) if blocks else None
    if not blocks:
        line = f"There is no daily operations report for any rig for {day:%d/%m/%Y}."
        return ReportMail(subject, _page(f"<p style=\"color:#0715cd;margin:0 0 14px\">{line}</p>"), line, [], True, "No rig reported")
    inner = [f"<p>Dear Sir,</p><p>Please find attached the Daily Operations Update dated {day:%d/%m/%Y}</p>"]
    images = []
    for i, b in enumerate(blocks):
        cid = f"rigchart{i}"
        images.append((cid, chart_png(b), "png"))
        inner.append(body_table_html(b) + f"<br><hr><img src=\"cid:{cid}\" alt=\"Rig Information : {xml(b['rig'])}\"><br><br>")
    text = f"Daily Operations Update dated {day:%d/%m/%Y}: {len(blocks)} rigs. The report is attached as a PDF.\n" + "\n".join(f"{b['rig']}: today {_n(b['table']['total']['Today'])} hrs" for b in blocks)
    attachments = [(f"Daily_Operations_Summary_{now:%d_%m_%Y_%H%M%S}.pdf", pdf, "application/pdf")] if pdf else []
    return ReportMail(subject, _page("".join(inner)), text, attachments, False, f"{len(blocks)} rigs for {day:%d/%m/%Y}", images)


class DailyOperationsUpdateJob(ScheduledReportJob):
    key = JOB_KEY
    name = "Daily Operations Update"
    report_name = "Daily Operations Update"
    description = "Hours per rate for every rig (today, week, month, year, project) with a chart in the mail, and the Daily Operations Summary Report as a PDF."
    trigger_entity = ENTITY_KEY
    trigger_action = ACTION
    trigger_code = TRIGGER_CODE

    def build(self, alert, now):
        return build_mail(alert, now)


JOB = DailyOperationsUpdateJob()


def ensure_setup(alert_id=None, alert_name=ALERT_NAME):
    """Creates the scheduler's job row and, when the alert can be found (by id, else by name), the trigger row that connects the mail to it. Safe to run
    again. Returns what it did, as a list of words."""
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
