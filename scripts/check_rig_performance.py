"""Checks the Rig Performance mail: the hardcoded target and productivity rule, the diesel price by date, the calculated projection, ILM/IPM revenue from the
calculated MIS per day, the workbook (a sheet per rig, FINAL, Notes) and the mail. Reads the development data (October 2026); anything written is rolled
back, nothing is sent.

    cd backend
    .venv/bin/python scripts/check_rig_performance.py
"""
import datetime, io, os, sys, django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from decimal import Decimal
from django.db import transaction
from openpyxl import load_workbook
from core import rig_performance_month as m, scheduler
from core.models import DieselPrice, IlmRateTerm, RigMonthPlan

fails = []


def ok(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {detail}" if not cond else ""))
    if not cond:
        fails.append(name)


class Rollback(Exception):
    pass


D = datetime.date
END = D(2026, 10, 13)
FIRST = D(2026, 10, 1)


class A:
    mail_subject = ""


try:
    with transaction.atomic():
        data = m.collect(END)
        names = [r["name"] for r in data["rigs"]]
        ok("rigs with a report in the month are found, in rig order", {"EE01", "SK02"} <= set(names) and [r["rig"].rig_id for r in data["rigs"]] == sorted(r["rig"].rig_id for r in data["rigs"]), str(names))
        ee01 = next(r for r in data["rigs"] if r["name"] == "EE01")
        from core import rate_classes
        ok("target is 96 % and the productive rule is the shared one (FM counts, R0 does not)", ee01["setting"]["target"] == 96 and ee01["setting"]["fm"] is True and rate_classes.ZERO_RATE not in rate_classes.PRODUCTIVE_CLASSES)
        ok("each report day has Total = the sum of the columns", all(abs(r["total"] - sum(r["hours"].values(), Decimal(0))) < Decimal("0.001") for r in ee01["rows"] if r["reported"]))
        ok("revenue uses the system's rate (EE01 R1 a day = 2,249,256 / 10^7)", abs(ee01["rows"][0]["revenue"] - Decimal("0.2249256")) < Decimal("0.0000001"), str(ee01["rows"][0]["revenue"]))
        ok("October 2026 diesel price is the seeded one", m.price_on(D(2026, 10, 5)) == Decimal("90.16"))
        DieselPrice.objects.create(price_per_litre="80.00", valid_from=D(2026, 10, 10), valid_to=D(2026, 10, 12), note="check")
        ok("the price is the one in force on the day", m.price_on(D(2026, 10, 9)) == Decimal("90.16") and m.price_on(D(2026, 10, 11)) == Decimal("80.00") and m.price_on(D(2026, 10, 13)) == Decimal("90.16"))

        # projection is calculated (no row: the whole month, default weights, no ILM)
        RigMonthPlan.objects.filter(rig=ee01["rig"]).delete()
        pj = m.collect(END)
        ee01 = next(r for r in pj["rigs"] if r["name"] == "EE01")
        rates = m.contract_rates(ee01["rig"].rig_id, m.current_contract(ee01["rig"].rig_id, END))
        normal = 24 * (Decimal("0.85") * rates[1] + Decimal("0.15") * rates[2])
        ok("no plan row: 31 days x the normal day, no ILM", ee01["proj"]["days"] == 31 and abs(ee01["projection"] - 31 * normal / m.CRORE) < Decimal("0.00001"), str(ee01["projection"]))
        RigMonthPlan.objects.create(rig=ee01["rig"], month=FIRST, ilm_days=0, non_ilm_days=20, r1_pct=70, r2_pct=30, r3_pct=0)
        ee01 = next(r for r in m.collect(END)["rigs"] if r["name"] == "EE01")
        normal2 = 24 * (Decimal("0.70") * rates[1] + Decimal("0.30") * rates[2])
        ok("the plan's days and weights are used", abs(ee01["projection"] - 20 * normal2 / m.CRORE) < Decimal("0.00001"), str(ee01["projection"]))
        RigMonthPlan.objects.filter(rig=ee01["rig"]).delete()

        # ILM/IPM revenue: MIS per day from the plan's ILM days
        from core.models import DrillingDtlOps
        RigMonthPlan.objects.create(rig=ee01["rig"], month=FIRST, ilm_days=4)
        contract = m.current_contract(ee01["rig"].rig_id, END)
        IlmRateTerm.objects.filter(rig=ee01["rig"], contract_id=contract).delete()
        IlmRateTerm.objects.create(rig=ee01["rig"], contract_id=contract, upto_km=30, flat_amount=4000000, extra_per_km=0)
        e2 = next(r for r in m.collect(END)["rigs"] if r["name"] == "EE01")
        ok("MIS per day = flat amount / the plan's ILM days", abs(e2["proj"]["mis_cr"] - Decimal("4000000") / m.CRORE / 4) < Decimal("0.0000001"), str(e2["proj"]["mis_cr"]))
        ok("the projection adds the ILM amount for the planned days", abs(e2["projection"] - (27 * normal + 4000000) / m.CRORE) < Decimal("0.00001"), str(e2["projection"]))


        # IPM move (EE01, Aug 2026: an IPM - Adjacent move started 28 Aug): priced at the project's IPM rate, counted when ILM days are planned
        a1, a2 = D(2026, 8, 1), D(2026, 8, 31)
        RigMonthPlan.objects.filter(rig=ee01["rig"]).delete()
        c_aug = m.current_contract(ee01["rig"].rig_id, a2)
        rates_aug = m.contract_rates(ee01["rig"].rig_id, c_aug)
        normal_aug = 24 * (Decimal("0.85") * rates_aug[1] + Decimal("0.15") * rates_aug[2])
        p0 = m.projection_for(ee01["rig"].rig_id, c_aug, a1, a2, None, Decimal(0))
        ok("a recorded move with no ILM days planned is flagged, not counted", p0["warnings"] and p0["moves"][0]["type"] == "IPM" and abs(p0["value"] - 31 * normal_aug / m.CRORE) < Decimal("0.00001"), str(p0["warnings"]))
        RigMonthPlan.objects.create(rig=ee01["rig"], month=a1, ilm_days=8)
        p1 = m.projection_for(ee01["rig"].rig_id, c_aug, a1, a2, RigMonthPlan.objects.get(rig=ee01["rig"], month=a1), Decimal(0))
        ok("an IPM move is the project's IPM rate: 23 normal days + 6,627,052 = 5.7587 Cr", abs(p1["value"] - (23 * normal_aug + Decimal("6627052")) / m.CRORE) < Decimal("0.00001") and p1["ilm_amount"] == Decimal("6627052.00"), f"{p1['value']} {p1['ilm_amount']}")
        ok("the ILM terms are not added for an IPM-only month", "ILM terms" not in p1["ilm_note"] and "flat" not in p1["ilm_note"], p1["ilm_note"])
        ok("MIS per day = the IPM amount / 8 days", abs(p1["mis_cr"] - Decimal("6627052") / m.CRORE / 8) < Decimal("0.0000001"))

        # closing a month
        ok("auto-close leaves a rig with ILM/IPM activity and no ILM days open", "SK02" in m.unconfirmed_ilm(a1) and "EE01" not in m.unconfirmed_ilm(a1))
        closed, left = m.close_month(a1, note="check", auto=True)
        ok("close_month closes the others and reports who was left open", closed >= 1 and "SK02" in left and not RigMonthPlan.objects.filter(rig__rig_name="SK02", month=a1, closed_on__isnull=False).exists(), f"{closed} {left}")
        ok("a closed row has its date", RigMonthPlan.objects.get(rig=ee01["rig"], month=a1).closed_on == datetime.date.today())
        closed2, _l = m.close_month(a1, note="again", auto=True)
        ok("closing again changes nothing", closed2 == 0)
        c3, l3 = m.close_month(a1, note="forced", auto=False)
        ok("a forced close takes the unconfirmed rig as 0 ILM days", c3 >= 1 and RigMonthPlan.objects.get(rig__rig_name="SK02", month=a1).ilm_days == 0)

        mail = m.build_mail(A(), datetime.datetime(2026, 10, 14, 10, 0))
        ok("the mail carries the Excel file", len(mail.attachments) == 1 and mail.attachments[0][0] == "Rig_Performance-October-2026.xlsx" and mail.attachments[0][1][:2] == b"PK")
        wb = load_workbook(io.BytesIO(mail.attachments[0][1]))
        ok("sheets: a per rig, FINAL and Notes", wb.sheetnames[-2:] == ["FINAL-OCT-26", "Notes"] and len(wb.sheetnames) == len(names) + 2, str(wb.sheetnames))
        fs = wb["FINAL-OCT-26"]
        ok("FINAL shows 96 % targets and a projection per rig", abs(fs["B1"].value - 0.96) < 1e-9 and fs.cell(row=2, column=2 + len(names) + 1).value is not None)
        notes = [r[0] or "" for r in wb["Notes"].iter_rows(values_only=True)]
        ok("the Notes sheet shows the projection working and the known difference", any("non-ILM days" in t for t in notes) and any("1,124,630" in t for t in notes))
        ok("the mail lists the rigs", "EE01" in mail.html and "Seros-IT" in mail.html)
        empty = m.build_mail(A(), datetime.datetime(2031, 1, 2, 10, 0))
        ok("no rig gives the empty-state mail", empty.empty and not empty.attachments)
        ok("the job is on the scheduler", scheduler.JOBS.get(m.JOB_KEY) is m.JOB)
        raise Rollback
except Rollback:
    pass
print("\nFAILED: " + ", ".join(fails) if fails else "\nall passed")
sys.exit(1 if fails else 0)
