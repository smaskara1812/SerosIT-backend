"""Checks the Rig Operations dashboard against the Rig Operations workbook (Dashboard.xlsx, spec rig-ops-dashboard-spec.md section 9) on the development data:
EE01 and SR03 over the workbook's dates, the hours by class, the top operations, the wells table, the status board, days to check, the metres rule (the daily
report's own figure; the workbook's depth-change figure differs by one typo day), the scope of each widget, the rights, and the shared productive rule.
Reads only; nothing is written.

    cd backend
    .venv/bin/python scripts/check_rig_operations_dashboard.py
"""
import datetime, os, sys, django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.test import APIClient
from core import rate_classes as rc
from core.dashboard_access import dashboard_rig_queryset
from core.models import MstRig, UserPermission, UserProfile
from core.permissions import invalidate_user_access
from core.rig_operations_dashboard import build_payload

fails = []


def ok(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {detail}" if not cond else ""))
    if not cond:
        fails.append(name)


class Rollback(Exception):
    pass


def near(a, b, tol=0.011):
    return a is not None and abs(a - b) <= tol


D = datetime.date
ids = {r.rig_id for r in dashboard_rig_queryset()}
ee01 = MstRig.objects.get(rig_name="EE01").rig_id
sr03 = MstRig.objects.get(rig_name="SR03").rig_id

# the shared rule
ok("every class but Zero Rate is productive", rc.PRODUCTIVE_CLASSES == {rc.OPERATING, rc.STANDBY, rc.REPAIR, rc.FORCE_MAJEURE, rc.RIG_MOVE})
ok("rate types map to the classes of the daily report", rc.class_of(1) == rc.OPERATING and rc.class_of(15) == rc.STANDBY and rc.class_of(4) == rc.ZERO_RATE and rc.class_of(8) == rc.RIG_MOVE and rc.class_of(9) == rc.UNMAPPED)

# EE01 over the workbook's dates (workbook: 8,659.5 h, 361 rig-days, 2 wells, 2 days to check)
p = build_payload({ee01}, ids, D(2025, 9, 12), D(2026, 9, 30))
k = p["kpis"]
ok("EE01 total hours 8,659.5, operating 6,695.75 (77.32 %)", near(k["total_hrs"], 8659.5) and near(k["operating_hrs"], 6695.75) and near(k["operating_pct"], 77.32), str(k))
ok("EE01 productive hours 8,492.75 (98.07 %)", near(k["productive_hrs"], 8492.75) and near(k["productivity_pct"], 98.07), str(k))
ok("EE01 drilling hours 2,786.75", near(k["drilling_hrs"], 2786.75))
ok("EE01 metres are the daily report's figure (13,805.1; the workbook's depth change gives 13,741.1: one reversed-depth day of 64 m)", near(k["drilled_m"], 13805.1, 0.06), str(k["drilled_m"]))
ok("EE01 ROP = metres / drilling hours", near(k["avg_rop"], round(13805.1 / 2786.75, 2)))
ok("EE01 diesel 2,042,441 L", k["diesel_l"] == 2042441)
ok("EE01 rig-days 361, wells completed 2, days to check 2", k["rig_days"] == 361 and k["wells_completed"] == 2 and k["days_to_check"] == 2, str(k))
cls = {c["class"]: c["hours"] for c in p["hours_by_class"]}
ok("EE01 hours by class (workbook)", near(cls["Operating"], 6695.75) and near(cls["Standby"], 1188.5) and near(cls["Repair"], 163.25) and near(cls["Force Majeure"], 15.5) and near(cls["Zero Rate"], 166.75) and near(cls["Rig Move"], 429.75) and cls["Unmapped"] == 0, str(cls))
ops = [(o["operation"], o["hours"]) for o in p["top_operations"]]
ok("EE01 top 10 operations (workbook order and hours)", ops == [("2: Drill actual", 2786.75), ("6: Trips", 2235.25), ("5: Circulate & condition mud", 596.25), ("23: Other", 444.25), ("12: Run casing & cement", 435.75), ("1: Rig up/Tear down/Rig move", 429.75), ("13: Wait on cement", 375.25), ("14: Rig up/down BOP", 312.75), ("11: Wire line logs", 253.75), ("8: Repair rig", 200.75)], str(ops))
ok("the reversed-depth typo is warned about (EE01, 21 Sep 2026)", any("Depth To below Depth From" in w and "21 Sep 2026" in w for w in p["warnings"]), str(p["warnings"]))
ok("revenue is priced from the project rates (not 0 as in the workbook) and has no rig-move lump sum", k["revenue_cr"] > 0)

# SR03 (workbook: 1,499 h, 559.5 operating, 98.1 %, 2,532.3 m, ROP 9.08, 102,981 L, 63 rig-days, 1 check day)
q = build_payload({sr03}, ids, D(2026, 5, 14), D(2026, 7, 15))["kpis"]
ok("SR03 hours, operating, productivity, metres, ROP, diesel, rig-days, check day", near(q["total_hrs"], 1499) and near(q["operating_hrs"], 559.5) and near(q["productivity_pct"], 98.1, 0.06) and near(q["drilled_m"], 2532.3, 0.06) and near(q["avg_rop"], 9.08) and q["diesel_l"] == 102981 and q["rig_days"] == 63 and q["days_to_check"] >= 1, str(q))
ok("wells completed counts the completion date (SR03: 2; the workbook inferred 1)", q["wells_completed"] == 2, str(q["wells_completed"]))

# scope of each widget
full = build_payload({ee01}, ids, D(2025, 9, 12), D(2026, 9, 30))
rigs_in_comparison = {c["rig"] for c in full["comparison"] if c["rig"] != "Total"}
ok("the rig comparison ignores the rig filter (every rig with data in the dates)", {"EE01", "SR03", "Axom Rhino"} <= rigs_in_comparison, str(rigs_in_comparison))
tot = full["comparison"][-1]
ok("the comparison total is the sum of its rows", near(tot["total_hrs"], sum(c["total_hrs"] for c in full["comparison"][:-1]), 0.05) and tot["rig_days"] == sum(c["rig_days"] for c in full["comparison"][:-1]))
ok("the monthly trend is 12 months ending at the To month, the daily trend 31 days ending at To", len(full["monthly"]) == 12 and full["monthly"][-1]["month"] == "2026-09" and len(full["daily"]) == 31 and full["daily"][-1]["date"] == "2026-09-30")
narrow = build_payload({ee01}, ids, D(2026, 9, 1), D(2026, 9, 30))
ok("the monthly trend does not depend on From (September is the same either way)", narrow["monthly"][-1]["total_hrs"] == full["monthly"][-1]["total_hrs"])
ok("the status board ignores the filters (every recent rig)", len(full["status_board"]) >= 3 and {b["rig"] for b in full["status_board"]} >= {"EE01", "SR03"})
ee_board = next(b for b in full["status_board"] if b["rig"] == "EE01")
ok("the status board shows the latest report, well, depth, section, operation, rate", ee_board["last_report"] >= "2026-09-30" and ee_board["location"] and ee_board["depth_m"] and ee_board["last_operation"] and ee_board["rate"])
wells = full["wells"]
w1 = next(w for w in wells if w["location"] == "SOUTH BAGHJAAN 15")
ok("the well table matches the workbook (SOUTH BAGHJAAN 15: 89 days, 4,360 m, 4,709.1 m drilled, ROP 6.46, 99.4 %)", w1["days"] == 89 and w1["depth_m"] == 4360 and near(w1["drilled_m"], 4709.1, 0.06) and near(w1["rop"], 6.46) and near(w1["productivity_pct"], 99.41, 0.05) and w1["status"] == "Completed", str(w1))
ok("the well table is the latest 12 wells of the chosen rigs, oldest first", len(wells) <= 12 and all(w["rig"] == "EE01" for w in wells) and [w["first_report"] for w in wells] == sorted(w["first_report"] for w in wells))
ok("days to check lists each flagged day with its problem", full["days_to_check_total"] >= 2 and all(r["problems"] for r in full["days_to_check"]))
none = build_payload({ee01}, ids, D(2031, 1, 1), D(2031, 1, 31))
ok("dates with no data give zeros, not an error", none["kpis"]["total_hrs"] == 0 and none["kpis"]["productivity_pct"] is None)


# links to the records, and the load limits
ok("the status board rows carry the report and the well to open", all(b["dtl_id"] for b in full["status_board"]) and any(b["hdr_id"] for b in full["status_board"]))
ok("days to check carry the report to open and list only the chosen rigs, newest first", all(r["dtl_id"] and r["rig_id"] == ee01 for r in full["days_to_check"]) and [r["date"] for r in full["days_to_check"]] == sorted((r["date"] for r in full["days_to_check"]), reverse=True))
ok("the reversed-depth days carry the report to open", any(d["rig_id"] == ee01 and d["date"] == "2026-09-21" and d["dtl_id"] for d in full["depth_error_days"]))
import json
from django.db import connection
from django.test.utils import CaptureQueriesContext
with CaptureQueriesContext(connection) as q:
    everything = build_payload(ids, ids, None, None)
ok(f"all rigs, all the data: a fixed number of queries ({len(q)}), not one set per rig", len(q) <= 20, str(len(q)))
ok("the answer stays small (under 200 KB) and the lists are capped", len(json.dumps(everything, default=str)) < 200_000 and len(everything["days_to_check"]) <= 500 and len(everything["wells"]) <= 12 and len(everything["monthly"]) == 12 and len(everything["daily"]) == 31)

# rights and the endpoint
try:
    with transaction.atomic():
        U = get_user_model()
        def mk(n, grant):
            u = U.objects.create_user(username=n, password="x")
            uid = (UserProfile.objects.order_by("-user_id").first().user_id or 0) + 1
            UserProfile.objects.create(user_id=uid, user_login_id=n, is_app_admin=False)
            if grant:
                UserPermission.objects.create(user_id=uid, menu_key="dashboards.rig_operations", can_view=True, can_add=False, can_edit=False, can_delete=False, can_export=False)
            invalidate_user_access(n)
            c = APIClient(HTTP_HOST="localhost"); c.force_authenticate(u); return c
        nobody, viewer = mk("rod_none", False), mk("rod_view", True)
        ok("no right, no dashboard", nobody.get("/api/dashboards/rig-operations/").status_code == 403)
        r = viewer.get(f"/api/dashboards/rig-operations/?rigs={ee01}&from=2025-09-12&to=2026-09-30")
        ok("a viewer gets the same figures through the endpoint", r.status_code == 200 and near(r.json()["kpis"]["total_hrs"], 8659.5) and r.json()["selected_rig_ids"] == [ee01])
        ok("a bad date is ignored, not an error", viewer.get("/api/dashboards/rig-operations/?from=zzz").status_code == 200)
        raise Rollback
except Rollback:
    pass
print("\nFAILED: " + ", ".join(fails) if fails else "\nall passed")
sys.exit(1 if fails else 0)
