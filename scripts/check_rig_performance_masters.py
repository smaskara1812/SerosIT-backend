"""Checks the Rig Performance masters (Diesel Prices, Rig Month Plans, ILM Rate Terms): rights, the month kept as the 1st, duplicates, the value checks
(days in the month, weights adding to 100, no negatives), that they are not dropdown sources, and that the report calculates the projection from them (days
from the project's start and end, ILM days, the ILM amount from km and terms, MIS per day). Everything written is rolled back.

    cd backend
    .venv/bin/python scripts/check_rig_performance_masters.py
"""
import datetime, os, sys, django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.test import APIClient
from core import masters_views, rig_performance_month as m
from core.models import DrillingDtl, DrillingHdr, IlmRateTerm, MstRig, ProjectContractDtl, RigMonthPlan, UserPermission, UserProfile
from core.permissions import invalidate_user_access

fails = []


def ok(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {detail}" if not cond else ""))
    if not cond:
        fails.append(name)


class Rollback(Exception):
    pass


KEYS = ["masters.diesel_prices", "masters.rig_month_plans", "masters.ilm_rate_terms"]


def mk(n, grants):
    U = get_user_model(); u = U.objects.create_user(username=n, password="x")
    uid = (UserProfile.objects.order_by("-user_id").first().user_id or 0) + 1
    UserProfile.objects.create(user_id=uid, user_login_id=n, is_app_admin=False)
    for key, flags in grants.items():
        UserPermission.objects.create(user_id=uid, menu_key=key, can_view="view" in flags, can_add="add" in flags, can_edit="edit" in flags, can_delete="delete" in flags, can_export="export" in flags)
    invalidate_user_access(n)
    c = APIClient(HTTP_HOST="localhost"); c.force_authenticate(u); return c


D = datetime.date
try:
    with transaction.atomic():
        full = mk("rpm_full", {k: "view add edit delete export" for k in KEYS})
        nobody = mk("rpm_none", {})
        viewer = mk("rpm_view", {k: "view" for k in KEYS})
        rig = MstRig.objects.get(rig_name="EE01")
        base = "/api/masters/"
        for slug in ("diesel-prices", "rig-month-plans", "ilm-rate-terms"):
            ok(f"{slug}: no rights, no list", nobody.get(f"{base}{slug}/").status_code == 403)
            ok(f"{slug}: a viewer can list but not add", viewer.get(f"{base}{slug}/").status_code == 200 and viewer.post(f"{base}{slug}/", {}, format="json").status_code == 403)

        # diesel prices
        r = full.post(f"{base}diesel-prices/", {"price_per_litre": "95.00", "valid_from": "2026-11-01", "note": "check"}, format="json")
        ok("a diesel price can be added", r.status_code == 201, r.content[:200])
        ok("a price of 0 / an end before the start is refused", full.post(f"{base}diesel-prices/", {"price_per_litre": "0", "valid_from": "2026-11-01"}, format="json").status_code == 400 and full.post(f"{base}diesel-prices/", {"price_per_litre": "90", "valid_from": "2026-11-10", "valid_to": "2026-11-01"}, format="json").status_code == 400)
        ok("the report uses the price in force on the day", m.price_on(D(2026, 11, 2)) == Decimal("95.00") and m.price_on(D(2026, 10, 31)) == Decimal("90.16"))
        ok("a price can be deleted", full.delete(f"{base}diesel-prices/{r.json()['price_id']}/").status_code == 204)

        # month plans
        RigMonthPlan.objects.filter(rig=rig).delete()
        r = full.post(f"{base}rig-month-plans/", {"rig": rig.rig_id, "month": "2026-10-17", "r1_pct": "85", "r2_pct": "15", "r3_pct": "0"}, format="json")
        ok("a month plan can be added", r.status_code == 201, r.content[:200])
        ok("the month is kept as the 1st", r.json()["month"] == "2026-10-01", str(r.json().get("month")))
        pid = r.json()["plan_id"]
        ok("the same rig and month cannot be added twice", full.post(f"{base}rig-month-plans/", {"rig": rig.rig_id, "month": "2026-10-03", "r1_pct": "85", "r2_pct": "15", "r3_pct": "0"}, format="json").status_code == 400)
        ok("weights must add up to 100", full.patch(f"{base}rig-month-plans/{pid}/", {"r1_pct": "80"}, format="json").status_code == 400)
        ok("more normal days than the month has are refused", full.patch(f"{base}rig-month-plans/{pid}/", {"non_ilm_days": "32"}, format="json").status_code == 400)
        ok("a negative day count is refused", full.patch(f"{base}rig-month-plans/{pid}/", {"non_ilm_days": "-1"}, format="json").status_code == 400)


        # a closed month is protected on the Masters page too
        RigMonthPlan.objects.filter(pk=pid).update(closed_on=D(2026, 11, 1))
        ok("a closed plan cannot be edited on the Masters page", full.patch(f"{base}rig-month-plans/{pid}/", {"non_ilm_days": "1"}, format="json").status_code == 400)
        ok("a closed plan cannot be deleted", full.delete(f"{base}rig-month-plans/{pid}/").status_code == 400 and RigMonthPlan.objects.filter(pk=pid).exists())
        ok("the closing fields cannot be set through the page", full.post(f"{base}rig-month-plans/", {"rig": rig.rig_id, "month": "2026-09-05", "r1_pct": "85", "r2_pct": "15", "r3_pct": "0", "closed_on": "2026-10-01"}, format="json").json().get("closed_on") is None)


        # weights are optional (carried over), but all three go together
        RigMonthPlan.objects.filter(rig=rig, month=D(2026, 8, 1)).delete()
        r = full.post(f"{base}rig-month-plans/", {"rig": rig.rig_id, "month": "2026-08-10"}, format="json")
        ok("a plan can be saved with no weights at all", r.status_code == 201 and r.json()["r1_pct"] is None, r.content[:200])
        ok("weights typed in part are refused", full.patch(f"{base}rig-month-plans/{r.json()['plan_id']}/", {"r1_pct": "80", "r2_pct": "20"}, format="json").status_code == 400)
        ok("all three typed and adding up to 100 are accepted", full.patch(f"{base}rig-month-plans/{r.json()['plan_id']}/", {"r1_pct": "80", "r2_pct": "20", "r3_pct": "0"}, format="json").status_code == 200)

        # ILM terms
        contract = m.current_contract(rig.rig_id, D(2026, 10, 13))
        IlmRateTerm.objects.filter(rig=rig).delete()
        r = full.post(f"{base}ilm-rate-terms/", {"rig": rig.rig_id, "contract": contract, "upto_km": "30", "flat_amount": "7757549", "extra_per_km": "58473.98"}, format="json")
        ok("ILM terms can be added", r.status_code == 201, r.content[:200])
        ok("a second set on the same rig and project is refused", full.post(f"{base}ilm-rate-terms/", {"rig": rig.rig_id, "contract": contract, "upto_km": "20", "extra_per_km": "1"}, format="json").status_code == 400)
        ok("negative amounts are refused", full.patch(f"{base}ilm-rate-terms/{r.json()['term_id']}/", {"extra_per_km": "-1"}, format="json").status_code == 400)

        # the report calculates from them
        first, last = D(2026, 10, 1), D(2026, 10, 31)
        rates = m.contract_rates(rig.rig_id, contract)
        normal = 24 * (Decimal("0.85") * rates[1] + Decimal("0.15") * rates[2])
        plan = RigMonthPlan.objects.get(pk=pid)
        from core.models import RigPlannedMove
        pj = m.projection_for(rig.rig_id, contract, first, last, RigMonthPlan.objects.get(pk=pid))
        ok("no planned move: the whole month x the normal day", pj["days"] == 31 and abs(pj["value"] - 31 * normal / m.CRORE) < Decimal("0.00001"), str(pj["value"]))
        # one planned ILM of 120 hours (5 days) over 42 km: flat 30 km, 12 km beyond; a second planned IPM of 48 hours (2 days)
        RigPlannedMove.objects.create(plan=plan, move_rate_id=6, planned_hours=120, planned_km=42)
        pj = m.projection_for(rig.rig_id, contract, first, last, RigMonthPlan.objects.get(pk=pid))
        amount = Decimal("7757549") + 12 * Decimal("58473.98")
        ok("the planned km are used", pj["km"] == 42, str(pj["km"]))
        ok("ILM amount = flat + km beyond x price per km", abs(pj["ilm_amount"] - amount) < Decimal("0.01"), str(pj["ilm_amount"]))
        ok("projection = 26 normal days + the ILM amount", abs(pj["value"] - (26 * normal + amount) / m.CRORE) < Decimal("0.00001"), str(pj["value"]))
        ok("planned MIS per hour = the amount / the 120 hours", abs(pj["planned"][0]["mis_hour"] - amount / 120) < Decimal("0.0001"), str(pj["planned"][0]["mis_hour"]))
        ipm_rate = rates.get(8, Decimal(0))
        RigPlannedMove.objects.create(plan=plan, move_rate_id=8, planned_hours=48)
        pj = m.projection_for(rig.rig_id, contract, first, last, RigMonthPlan.objects.get(pk=pid))
        if ipm_rate:
            ok("several moves in a month: each priced on its own, hours of both out of the normal days", len(pj["planned"]) == 2 and abs(pj["value"] - (24 * normal + amount + ipm_rate) / m.CRORE) < Decimal("0.00001"), str(pj["value"]))
        ok("the planned moves' hours add up (168 h = 7 days)", pj["ilm_hours"] == 168 and pj["ilm_days"] == 7)
        RigPlannedMove.objects.filter(plan=plan, move_rate_id=8).delete()
        RigPlannedMove.objects.filter(plan=plan).update(planned_km=10)
        pj = m.projection_for(rig.rig_id, contract, first, last, RigMonthPlan.objects.get(pk=pid))
        ok("under the flat limit: just the flat amount", pj["ilm_amount"] == Decimal("7757549"), str(pj["ilm_amount"]))
        # days from the project's start and end
        line = ProjectContractDtl.objects.filter(rig_id=rig.rig_id, contract_id=contract).first()
        # the start is the first daily report on the project; the project line's start is only used while the rig has not reported on it
        started = m.project_start_from_reports(rig.rig_id, contract)
        ok("the start is the date of the first daily report on the project", started is not None and started == DrillingDtl.objects.filter(rig_id=rig.rig_id, drilling_hdr__contract_id=contract).order_by("drilling_dtl_dt").first().drilling_dtl_dt, str(started))
        ProjectContractDtl.objects.filter(pk=line.pk).update(rig_active_from=D(2026, 10, 25))
        ok("a project line starting later does not move the start when reports exist", m.project_days(rig.rig_id, contract, first, last)[2] == 31)
        real = m.project_start_from_reports
        m.project_start_from_reports = lambda *a: D(2026, 10, 15)  # a rig whose first report is on the 15th
        ok("a rig whose first report is on the 15th counts 17 days", m.project_days(rig.rig_id, contract, first, last)[2] == 17)
        m.project_start_from_reports = lambda *a: D(2026, 11, 3)
        ok("a rig whose first report is after the month has no days that month", m.project_days(rig.rig_id, contract, first, last)[2] == 0)
        m.project_start_from_reports = lambda *a: None  # not reported yet: the project line's start is used
        ProjectContractDtl.objects.filter(pk=line.pk).update(rig_active_from=D(2026, 10, 15))
        ok("a rig that has not reported yet starts on its project line's date (17 days)", m.project_days(rig.rig_id, contract, first, last)[2] == 17)
        ProjectContractDtl.objects.filter(pk=line.pk).update(rig_active_from=D(2024, 7, 17), rig_active_to=D(2026, 10, 10))
        m.project_start_from_reports = real
        ok("a rig ending on the 10th counts 10 days", m.project_days(rig.rig_id, contract, first, last)[2] == 10)
        ProjectContractDtl.objects.filter(pk=line.pk).update(rig_active_to=D(2026, 9, 20))
        ok("a rig that ended last month has no days", m.project_days(rig.rig_id, contract, first, last)[2] == 0)
        ok("the pages are not offered as dropdown sources", all(getattr(v, "lookup", True) is False for v in (masters_views.DieselPriceViewSet, masters_views.RigMonthPlanViewSet, masters_views.IlmRateTermViewSet)))
        raise Rollback
except Rollback:
    pass
print("\nFAILED: " + ", ".join(fails) if fails else "\nall passed")
sys.exit(1 if fails else 0)
