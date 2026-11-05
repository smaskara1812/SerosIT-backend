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
        RigMonthPlan.objects.create(rig=ee01["rig"], month=FIRST, non_ilm_days=20, r1_pct=70, r2_pct=30, r3_pct=0)
        ee01 = next(r for r in m.collect(END)["rigs"] if r["name"] == "EE01")
        normal2 = 24 * (Decimal("0.70") * rates[1] + Decimal("0.30") * rates[2])
        ok("the plan's days and weights are used", abs(ee01["projection"] - 20 * normal2 / m.CRORE) < Decimal("0.00001"), str(ee01["projection"]))
        RigMonthPlan.objects.filter(rig=ee01["rig"]).delete()

        # a planned ILM move (hours): its amount / its hours is the planned MIS per hour
        from core.models import DrillingDtlOps
        from core.models import RigPlannedMove
        plan4 = RigMonthPlan.objects.create(rig=ee01["rig"], month=FIRST)
        RigPlannedMove.objects.create(plan=plan4, move_rate_id=6, planned_hours=96, planned_km=0)  # 96 hours = 4 days
        contract = m.current_contract(ee01["rig"].rig_id, END)
        IlmRateTerm.objects.filter(rig=ee01["rig"], contract_id=contract).delete()
        IlmRateTerm.objects.create(rig=ee01["rig"], contract_id=contract, upto_km=30, flat_amount=4000000, extra_per_km=0)
        e2 = next(r for r in m.collect(END)["rigs"] if r["name"] == "EE01")
        ok("planned MIS per hour = the move's amount / its planned hours", abs(e2["proj"]["planned"][0]["mis_hour"] - Decimal("4000000") / 96) < Decimal("0.0001"), str(e2["proj"]["planned"]))
        ok("the projection adds the ILM amount and takes the move's 4 days out of the normal days", abs(e2["projection"] - (27 * normal + 4000000) / m.CRORE) < Decimal("0.00001"), str(e2["projection"]))


        # IPM move (EE01, Aug 2026: an IPM - Adjacent move started 28 Aug): priced at the project's IPM rate, counted when the move is planned
        a1, a2 = D(2026, 8, 1), D(2026, 8, 31)
        RigMonthPlan.objects.filter(rig=ee01["rig"]).delete()
        c_aug = m.current_contract(ee01["rig"].rig_id, a2)
        rates_aug = m.contract_rates(ee01["rig"].rig_id, c_aug)
        normal_aug = 24 * (Decimal("0.85") * rates_aug[1] + Decimal("0.15") * rates_aug[2])
        p0 = m.projection_for(ee01["rig"].rig_id, c_aug, a1, a2, None)
        ok("a recorded move with nothing planned is flagged, not counted", p0["warnings"] and p0["moves"][0]["type"] == "IPM" and abs(p0["value"] - 31 * normal_aug / m.CRORE) < Decimal("0.00001"), str(p0["warnings"]))
        plan8 = RigMonthPlan.objects.create(rig=ee01["rig"], month=a1)
        RigPlannedMove.objects.create(plan=plan8, move_rate_id=8, planned_hours=192)  # 8 days
        p1 = m.projection_for(ee01["rig"].rig_id, c_aug, a1, a2, RigMonthPlan.objects.get(rig=ee01["rig"], month=a1))
        ok("an IPM move is the project's IPM rate: 23 normal days + 6,627,052 = 5.7587 Cr", abs(p1["value"] - (23 * normal_aug + Decimal("6627052")) / m.CRORE) < Decimal("0.00001") and p1["ilm_amount"] == Decimal("6627052.00"), f"{p1['value']} {p1['ilm_amount']}")
        ok("the ILM terms are not added for an IPM-only month", "ILM terms" not in p1["ilm_note"] and "flat" not in p1["ilm_note"], p1["ilm_note"])
        ok("planned MIS per hour = the IPM amount / 192 hours", abs(p1["planned"][0]["mis_hour"] - Decimal("6627052") / 192) < Decimal("0.0001"))

        # actual revenue of move hours = hours x the move's amount / all hours logged on it; it adds back to the amount
        aug = next(r for r in m.collect(a2)["rigs"] if r["name"] == "EE01")
        mv_aug = aug["proj"]["moves"]
        ok("the August IPM is one move of the hours logged (20-27 Aug), priced once", len(mv_aug) == 1 and mv_aug[0]["type"] == "IPM" and mv_aug[0]["hours"] > 150 and mv_aug[0]["amount"] == Decimal("6627052.00"), str(mv_aug and (mv_aug[0]["type"], mv_aug[0]["hours"])))
        ok("its hourly figure x its hours adds back to the amount", abs(sum(h * mv_aug[0]["mis_hour"] for h in mv_aug[0]["by_day"].values()) - Decimal("6627052")) < Decimal("0.01"))
        full_day = next(r for r in aug["rows"] if r["reported"] and r["day"] == D(2026, 8, 22))
        ok("a full move day earns 24 hours of it (and nothing at the normal rates)", abs(full_day["revenue"] - 24 * mv_aug[0]["mis_hour"] / m.CRORE) < Decimal("0.0000001"), str(full_day["revenue"]))
        ok("a move still running is earned over the hours logged so far: later hours lower the hourly figure", mv_aug[0]["mis_hour"] == mv_aug[0]["amount"] / mv_aug[0]["hours"])

        # a Standby rate added later (R2-A) gets its own column, productive like R2
        from core.models import MstDrillingRate, ProjectDrillingRate
        from core import rate_classes as rcl
        base = next(r for r in m.collect(END)["rigs"] if r["name"] == "EE01")
        r2_hours = sum((x["hours"]["R2"] for x in base["rows"] if x["reported"]), Decimal(0))
        newr = MstDrillingRate.objects.create(rate_code="R2-A", rate_description="check", rate_active="Y", rate_class="Standby", cr_user_id=0, cr_dt=datetime.datetime.now())
        rcl.clear_cache()
        ok("a new Standby rate is classed Standby and gets its own column named by its code", rcl.class_of(newr.drilling_rate_id) == rcl.STANDBY and rcl.column_of(newr.drilling_rate_id) == "R2-A")
        ok("the old standby rates keep the R2 column", rcl.column_of(2) == "R2" and rcl.column_of(15) == "R2" and rcl.column_of(18) == "R2")
        pdr = ProjectDrillingRate.objects.filter(rig=base["rig"], contract_id=m.current_contract(base["rig"].rig_id, END), drilling_rate_id=2).first()
        if pdr is not None and r2_hours > 0:
            ProjectDrillingRate.objects.filter(pk=pdr.pk).update(drilling_rate=newr)
            after = next(r for r in m.collect(END)["rigs"] if r["name"] == "EE01")
            ok("R2-A hours are shown in their own column, after R2", after["cols"][:3] == ["R1", "R2", "R2-A"] and sum((x["hours"]["R2-A"] for x in after["rows"] if x["reported"]), Decimal(0)) == r2_hours, str(after["cols"]))
            ok("they count as productive and earn at their own rate", after["avg_prod"] == base["avg_prod"] and abs(after["revenue"] - base["revenue"]) < Decimal("0.0000001"))
            ProjectDrillingRate.objects.filter(pk=pdr.pk).update(drilling_rate_id=2)
        newr.delete()
        rcl.clear_cache()

        # closing a month
        ok("auto-close leaves a rig with ILM/IPM activity and no ILM days open", "SK02" in m.unconfirmed_ilm(a1) and "EE01" not in m.unconfirmed_ilm(a1))
        closed, left = m.close_month(a1, note="check", auto=True)
        ok("close_month closes the others and reports who was left open", closed >= 1 and "SK02" in left and not RigMonthPlan.objects.filter(rig__rig_name="SK02", month=a1, closed_on__isnull=False).exists(), f"{closed} {left}")
        ok("a closed row has its date", RigMonthPlan.objects.get(rig=ee01["rig"], month=a1).closed_on == datetime.date.today())
        closed2, _l = m.close_month(a1, note="again", auto=True)
        ok("closing again changes nothing", closed2 == 0)
        c3, l3 = m.close_month(a1, note="forced", auto=False)
        ok("a forced close takes the unconfirmed rig as no planned moves", c3 >= 1 and not m.planned_moves_of(RigMonthPlan.objects.get(rig__rig_name="SK02", month=a1)))


        # weights are optional: carried over from the latest earlier month that set them (same project), else 85 / 15 / 0
        RigMonthPlan.objects.filter(rig=ee01["rig"]).delete()
        rid2 = ee01["rig"].rig_id
        c_now = m.current_contract(rid2, D(2026, 10, 31))
        w, src = m.weights_for(rid2, D(2026, 10, 1), c_now)
        ok("no plan row at all: the default 85 / 15 / 0", w == m.DEFAULT_WEIGHTS and src.startswith("default"), str((w, src)))
        RigMonthPlan.objects.create(rig=ee01["rig"], month=D(2026, 9, 1), r1_pct=75, r2_pct=25, r3_pct=0)
        w, src = m.weights_for(rid2, D(2026, 10, 1), c_now)
        ok("a month with no row carries over the earlier month's weights", w == (Decimal(75), Decimal(25), Decimal(0)) and src == "carried over from Sep 2026", str((w, src)))
        RigMonthPlan.objects.create(rig=ee01["rig"], month=D(2026, 10, 1))  # a plan row with no weights typed
        w, src = m.weights_for(rid2, D(2026, 10, 1), c_now)
        ok("a plan row with the weights left blank still carries them over", w == (Decimal(75), Decimal(25), Decimal(0)) and "carried over" in src)
        w, src = m.weights_for(rid2, D(2026, 11, 1), c_now)
        ok("and so does every later month", w == (Decimal(75), Decimal(25), Decimal(0)) and src == "carried over from Sep 2026")
        RigMonthPlan.objects.filter(rig=ee01["rig"], month=D(2026, 10, 1)).update(r1_pct=60, r2_pct=40, r3_pct=0)
        w, src = m.weights_for(rid2, D(2026, 10, 1), c_now)
        w_nov, src_nov = m.weights_for(rid2, D(2026, 11, 1), c_now)
        ok("a month that differs sets its own, and the months after carry THAT one", w == (Decimal(60), Decimal(40), Decimal(0)) and src == "set for this month" and w_nov[0] == 60 and src_nov == "carried over from Oct 2026", str((src, src_nov)))
        w, src = m.weights_for(rid2, D(2026, 11, 1), c_now + 9999)
        ok("on another project the weights start again from the default", w == m.DEFAULT_WEIGHTS, str((w, src)))
        RigMonthPlan.objects.filter(rig=ee01["rig"]).delete()


        # a row for a rig with no ILM changes nothing: the same projection with and without it
        RigMonthPlan.objects.filter(rig=ee01["rig"]).delete()
        c_o = m.current_contract(ee01["rig"].rig_id, D(2026, 10, 31))
        none_row = m.projection_for(ee01["rig"].rig_id, c_o, FIRST, D(2026, 10, 31), None)
        RigMonthPlan.objects.create(rig=ee01["rig"], month=FIRST)  # ILM days 0, nothing else typed
        with_row = m.projection_for(ee01["rig"].rig_id, c_o, FIRST, D(2026, 10, 31), RigMonthPlan.objects.get(rig=ee01["rig"], month=FIRST))
        ok("a plan row with no ILM and nothing else typed gives the same projection as no row", none_row["value"] == with_row["value"] and none_row["days"] == with_row["days"] == 31 and with_row["ilm_hours"] == 0 and with_row["non_ilm_days"] == 31, f"{none_row['value']} {with_row['value']}")
        RigMonthPlan.objects.filter(rig=ee01["rig"]).delete()

        mail = m.build_mail(A(), datetime.datetime(2026, 10, 14, 10, 0))
        ok("the mail carries the Excel file", len(mail.attachments) == 1 and mail.attachments[0][0] == "Rig_Performance-October-2026.xlsx" and mail.attachments[0][1][:2] == b"PK")
        wb = load_workbook(io.BytesIO(mail.attachments[0][1]))
        ok("sheets: a per rig, FINAL and Notes", wb.sheetnames[-2:] == ["FINAL-OCT-26", "Notes"] and len(wb.sheetnames) == len(names) + 2, str(wb.sheetnames))
        fs = wb["FINAL-OCT-26"]
        ok("FINAL shows 96 % targets and a projection per rig", abs(fs["B1"].value - 0.96) < 1e-9 and fs.cell(row=2, column=2 + len(names) + 1).value is not None)
        notes = [r[0] or "" for r in wb["Notes"].iter_rows(values_only=True)]
        ok("the Notes sheet shows the projection working and the productivity rule", any("normal days" in t for t in notes) and any("Productivity" in t for t in notes))
        ok("the mail lists the rigs", "EE01" in mail.html and "Seros-IT" in mail.html)
        empty = m.build_mail(A(), datetime.datetime(2031, 1, 2, 10, 0))
        ok("no rig gives the empty-state mail", empty.empty and not empty.attachments)
        ok("the job is on the scheduler", scheduler.JOBS.get(m.JOB_KEY) is m.JOB)
        raise Rollback
except Rollback:
    pass
print("\nFAILED: " + ", ".join(fails) if fails else "\nall passed")
sys.exit(1 if fails else 0)
