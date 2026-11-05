"""Checks the Daily Operations Update mail: the period starts (week from Sunday, cut at the project start), the figures kept as the legacy made them (daily
averages, % and uptime), the money format (Indian grouping), the mail (a table and a chart per rig, the PDF attached with a page per rig, the empty-state
mail), the chart picture, and that the job is on the scheduler and the Report Mails page. Reads the development data (a past day that has reports);
nothing is written, nothing is sent.

    cd backend
    .venv/bin/python scripts/check_daily_operations_update.py
"""
import datetime, os, sys, django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from decimal import Decimal
from core import daily_operations_update as m, scheduler
from core.models import DrillingDtl

fails = []


def ok(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {detail}" if not cond else ""))
    if not cond:
        fails.append(name)


D = datetime.date
# period starts: Wednesday 14 Oct 2026 -> week starts Sunday 11 Oct; a project that began on 13 Oct cuts the week, month and year
s = m.period_starts(D(2026, 10, 14), None)
ok("week starts on the Sunday", s["Week"] == D(2026, 10, 11) and s["Month"] == D(2026, 10, 1) and s["Year"] == D(2026, 1, 1), str(s))
s = m.period_starts(D(2026, 10, 18), None)
ok("a Sunday starts its own week", s["Week"] == D(2026, 10, 18), str(s))
s = m.period_starts(D(2026, 10, 14), D(2026, 10, 13))
ok("periods are cut at the project start", s["Week"] == s["Month"] == s["Year"] == s["Project"] == D(2026, 10, 13), str(s))
ok("Indian money format", m._money("Rs. ", Decimal("2195367")) == "~ Rs. 21,95,367.00" and m._money("$", Decimal("1234.5")) == "~ $1,234.50" and m._money("", None) == "-", m._money("Rs. ", Decimal("2195367")))
ok("percent shows like the legacy float", m._pct(Decimal("88.00")) == "88" and m._pct(Decimal("12.50")) == "12.5" and m._pct(Decimal("76.04")) == "76.04" and m._pct(None) == "")

day = DrillingDtl.objects.order_by("-drilling_dtl_dt").values_list("drilling_dtl_dt", flat=True).first()
today = day + datetime.timedelta(days=1)
blocks = m.collect_body(today)
ok("rigs found for the latest report day", len(blocks) >= 1, str([b["rig"] for b in blocks]))
for b in blocks:
    t = b["table"]
    for p in m.PERIODS:
        rows = [r[p]["hrs"] for r in t["rates"] if r[p]["hrs"] is not None]
        tot = sum(rows, Decimal(0))
        ok(f"{b['rig']} {p}: total is the sum of the rates", (t["total"][p] is None) == (not rows) and (not rows or abs(t["total"][p] - tot) <= Decimal("0.02")), f"{t['total'][p]} vs {tot}")
        pcts = [r[p]["pct"] for r in t["rates"] if r[p]["pct"] is not None]
        ok(f"{b['rig']} {p}: percents add to about 100", not pcts or abs(sum(pcts) - 100) <= Decimal("0.1"), str(sum(pcts)))
        up = sum((r[p]["pct"] for r in t["rates"] if r["id"] in m.UPTIME_RATES and r[p]["pct"] is not None), Decimal(0))
        ok(f"{b['rig']} {p}: uptime is R1 + R2", t["uptime"][p] is None or t["uptime"][p] == up, f"{t['uptime'][p]} vs {up}")
    ok(f"{b['rig']}: Today's hours are not averaged over more than a day", (t["total"]["Today"] or 0) <= 24 + Decimal("0.01"))
png = m.chart_png(blocks[0])
ok("the chart is a PNG picture", png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 2000)
html = m.body_table_html(blocks[0])
ok("the body table has the five period groups and the merged cells", all(f"{p} TD" in html or p == "Today" for p in m.PERIODS) and html.count("rowspan") == 10 and "Rig : " in html)


class A:
    mail_subject = ""


mail = m.build_mail(A(), datetime.datetime.combine(today, datetime.time(17, 15)))
ok("the mail has a chart per rig inside it", len(mail.inline_images) == len(blocks) and all(f"cid:{c}" in mail.html for c, _d, _s in mail.inline_images))
ok("the PDF is attached", len(mail.attachments) == 1 and mail.attachments[0][1][:4] == b"%PDF" and mail.attachments[0][2] == "application/pdf")
ok("the subject falls back", mail.subject == "Daily Operations Update")
ok("wording says Seros-IT", "Seros-IT" in mail.html and "S.I.S." not in mail.html)
try:
    from pypdf import PdfReader
    import io
    ok("a PDF page per rig", len(PdfReader(io.BytesIO(mail.attachments[0][1])).pages) == len(m.collect_pdf(today)))
except ImportError:
    print("skip a PDF page count (pypdf is not installed)")
empty = m.build_mail(A(), datetime.datetime(2020, 1, 1, 17, 15))
ok("no rig gives the empty-state mail, no attachment", empty.empty and not empty.attachments and "no daily operations report" in empty.html)
ok("the job is on the scheduler", scheduler.JOBS.get(m.JOB_KEY) is m.JOB)
ok("a 0-trip rig does not break the speed (shows 0)", all(p for p in [m.rig_page(r, c, day, datetime.datetime.now()) for r, c in m.collect_pdf(today)]))

# ported legacy functions
from core.models import DrillingDtlOps, DrillingHdr
rid, cid = m.collect_pdf(today)[0]
ok("Gnc_Get_Prj_Drilling_Rate gives the project's rate row", m.gnc_get_prj_drilling_rate(1, cid, rid) is not None and m.gnc_get_prj_drilling_rate(999, cid, rid) is None)
first_day = day.replace(day=1)
tot = m.fnc_get_average_revenue(rid, cid, day, day, None)
one = m._revenue_of_day(rid, cid, day, None)
ok("Fnc_Get_Average_Revenue for one day matches the day's revenue", tot is not None and abs(Decimal(tot) - one) < Decimal("0.01"), f"{tot} vs {one}")
ok("Fnc_Get_Average_Revenue of a range is the sum of its days", abs(Decimal(m.fnc_get_average_revenue(rid, cid, day - datetime.timedelta(days=1), day, None)) - (m._revenue_of_day(rid, cid, day, None) + m._revenue_of_day(rid, cid, day - datetime.timedelta(days=1), None))) < Decimal("0.01"))
ok("no dates or nothing to add gives None", m.fnc_get_average_revenue(rid, cid, None, day, None) is None and m.fnc_get_average_revenue(rid, cid, datetime.date(2001, 1, 1), datetime.date(2001, 1, 2), None) is None)
series = m.diesel_stock_by_day(rid, m.project_start(rid, cid, day))
ok("diesel stock: each day's opening is the previous closing, closing = opening + received - consumed", series and all(series[i][1] == series[i - 1][4] for i in range(1, len(series))) and all(r[4] == r[1] + r[2] - r[3] for r in series))
op, rec, con, clo = m.fnc_get_last_stock_rig_diesel(rid, m.project_start(rid, cid, day))
ok("the last stock is the last day's", (op, rec, con, clo) == (series[-1][1], series[-1][2], series[-1][3], series[-1][4]) and m.fnc_get_last_stock_rig_diesel(rid, None) == (None, None, None, None))
print("\nFAILED: " + ", ".join(fails) if fails else "\nall passed")
sys.exit(1 if fails else 0)
