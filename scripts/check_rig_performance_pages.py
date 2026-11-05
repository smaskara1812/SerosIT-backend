"""Checks the Reports > Rig Performance pages' data: the rights (View to see, Export to download), the month filter, the report payload (a table per rig, the
FINAL table with its totals), the future-month and no-data messages, the Excel download, and the rate sheet (rates, weights, normal day, ILM block,
projection). Reads the development data (October 2026); nothing is written (the test users are rolled back).

    cd backend
    .venv/bin/python scripts/check_rig_performance_pages.py
"""
import datetime, io, os, sys, django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings"); django.setup()
from django.contrib.auth import get_user_model
from django.db import transaction
from openpyxl import load_workbook
from rest_framework.test import APIClient
from core.models import IlmRateTerm, RigMonthPlan, UserPermission, UserProfile
from core.permissions import invalidate_user_access

fails = []


def ok(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + (f"  {detail}" if not cond else ""))
    if not cond:
        fails.append(name)


class Rollback(Exception):
    pass


def mk(n, grants):
    U = get_user_model(); u = U.objects.create_user(username=n, password="x")
    uid = (UserProfile.objects.order_by("-user_id").first().user_id or 0) + 1
    UserProfile.objects.create(user_id=uid, user_login_id=n, is_app_admin=False)
    for key, flags in grants.items():
        UserPermission.objects.create(user_id=uid, menu_key=key, can_view="view" in flags, can_add="edit" in flags, can_edit="edit" in flags, can_delete=False, can_export="export" in flags)
    invalidate_user_access(n)
    c = APIClient(HTTP_HOST="localhost"); c.force_authenticate(u); return c


R, M = "reports.rig_performance", "reports.rig_performance_masters"
base = "/api/reports/rig-performance/"
try:
    with transaction.atomic():
        nobody = mk("rpp_none", {})
        viewer = mk("rpp_view", {R: "view", M: "view"})
        exporter = mk("rpp_exp", {R: "view export"})
        ok("no rights, no report / rate sheet / download", nobody.get(base + "?month=2026-10").status_code == 403 and nobody.get(base + "rate-sheet/?month=2026-10").status_code == 403 and nobody.get(base + "download/?month=2026-10").status_code == 403)
        ok("a viewer sees the report and the rate sheet but cannot download", viewer.get(base + "?month=2026-10").status_code == 200 and viewer.get(base + "rate-sheet/?month=2026-10").status_code == 200 and viewer.get(base + "download/?month=2026-10").status_code == 403)
        ok("the report right does not open the rate sheet", exporter.get(base + "rate-sheet/?month=2026-10").status_code == 403)
        ok("a bad month is refused", viewer.get(base + "?month=abc").status_code == 400 and viewer.get(base + "?month=1999-01").status_code == 400)

        d = viewer.get(base + "?month=2026-10").json()
        ok("October 2026: a table per rig and a FINAL table", d["label"] == "October 2026" and len(d["rigs"]) >= 2 and d["final"] is not None and d["final"]["rigs"] == [r["name"] for r in d["rigs"]], str(d.get("message")))
        rig = d["rigs"][0]
        ok("a rig table has a row per day to the last day reported", len(rig["rows"]) == (datetime.date.fromisoformat(d["end"]) - datetime.date(2026, 10, 1)).days + 1 and rig["rows"][0]["reported"] in (True, False))
        reported = [r for r in rig["rows"] if r["reported"]]
        ok("each reported day has hours per column, a total, productivity and revenue", reported and all(len(r["hours"]) == len(rig["cols"]) and r["total"] is not None and r["revenue"] is not None for r in reported))
        f = d["final"]
        ok("FINAL has a row per day with a value per rig, totals, targets and projections", len(f["days"]) == len(rig["rows"]) and all(len(x["productivity"]) == len(f["rigs"]) for x in f["days"]) and len(f["targets"]) == len(f["rigs"]) and f["targets"][0] == 0.96 and len(f["projections"]) == len(f["rigs"]))
        ok("the total revenue is the sum of the rigs' revenue", abs(f["totals"]["total"] - sum(r["revenue"] for r in d["rigs"])) < 0.001)
        ok("the notes are included", any("Projection working" in n["text"] for n in d["notes"]))
        fut = viewer.get(base + "?month=2099-01").json()
        ok("a month that has not started gives a message, not an error", fut["final"] is None and "not started" in fut["message"])
        none = viewer.get(base + "?month=2026-11").json()
        ok("a month with no reports says so", none["final"] is None and "no daily drilling report" in none["message"], str(none.get("message")))

        x = exporter.get(base + "download/?month=2026-10")
        ok("the Excel download is the month's workbook", x.status_code == 200 and "Rig_Performance-October-2026.xlsx" in x["Content-Disposition"] and "FINAL-OCT-26" in load_workbook(io.BytesIO(x.content)).sheetnames)
        ok("a month with nothing downloads as a 404 message", exporter.get(base + "download/?month=2026-11").status_code == 404)

        rs = viewer.get(base + "rate-sheet/?month=2026-10").json()
        ee01 = next(r for r in rs["rigs"] if r["name"] == "EE01")
        ok("the rate sheet shows the rates per day, weights and the normal day", [r["code"] for r in ee01["rates"]] == ["R1", "R2", "R3"] and ee01["rates"][0]["weight"] == 85 and abs(ee01["rates"][0]["per_day"] - 2249256) < 1 and abs(ee01["normal_day"] - 2215516.8) < 1, str(ee01["rates"]))
        ok("it shows the days, the projection and the ILM block", ee01["days_on_project"] == 31 and ee01["projection_cr"] > 0 and "term" in ee01["ilm"] and ee01["ilm"]["term"]["upto_km"] == 30, str(ee01["ilm"]))
        ok("the projection equals the report's", abs(ee01["projection_cr"] - next(p for n, p in zip(f["rigs"], f["projections"]) if n == "EE01")) < 0.0001)

        # editing in place (Edit on the Masters page)
        editor = mk("rpp_edit", {M: "view edit"})
        rig_id, contract_id = ee01["rig_id"], ee01["contract_id"]
        body = {"rig": rig_id, "month": "2026-10", "ilm_days": "5", "non_ilm_days": "", "r1_pct": "80", "r2_pct": "20", "r3_pct": "0", "note": "check"}
        ok("a viewer cannot save a plan or ILM terms", viewer.put(base + "plan/", body, format="json").status_code == 403 and viewer.put(base + "ilm-terms/", {"rig": rig_id, "contract": contract_id, "upto_km": "30"}, format="json").status_code == 403)
        RigMonthPlan.objects.filter(rig_id=rig_id).delete()
        IlmRateTerm.objects.filter(rig_id=rig_id).delete()
        r = editor.put(base + "plan/", body, format="json")
        ok("an editor can save the plan (created)", r.status_code == 200 and r.json()["created"] is True, r.content[:200])
        r = editor.put(base + "plan/", {**body, "ilm_days": "6"}, format="json")
        ok("saving again updates the same row", r.status_code == 200 and r.json()["created"] is False and RigMonthPlan.objects.filter(rig_id=rig_id).count() == 1)
        ok("a bad plan is refused with a message (weights not 100)", editor.put(base + "plan/", {**body, "r1_pct": "50"}, format="json").status_code == 400 and "100" in editor.put(base + "plan/", {**body, "r1_pct": "50"}, format="json").json()["detail"])
        ok("too many days are refused", editor.put(base + "plan/", {**body, "ilm_days": "40"}, format="json").status_code == 400)
        r = editor.put(base + "ilm-terms/", {"rig": rig_id, "contract": contract_id, "upto_km": "30", "flat_amount": "4000000", "extra_per_km": "50000"}, format="json")
        ok("an editor can save ILM terms", r.status_code == 200 and IlmRateTerm.objects.filter(rig_id=rig_id, contract_id=contract_id).count() == 1, r.content[:200])
        ok("negative ILM terms are refused", editor.put(base + "ilm-terms/", {"rig": rig_id, "contract": contract_id, "upto_km": "-1"}, format="json").status_code == 400)
        e2 = next(x for x in editor.get(base + "rate-sheet/?month=2026-10").json()["rigs"] if x["name"] == "EE01")
        ok("the rate sheet shows the saved plan and recalculates", e2["plan"]["exists"] and e2["plan"]["ilm_days"] == 6 and e2["plan"]["r1_pct"] == 80 and e2["ilm"]["term"]["flat_amount"] == 4000000 and e2["non_ilm_days"] == 25 and abs(e2["ilm"]["mis_cr"] - 4000000 / 1e7 / 6) < 0.0001, str(e2["plan"]))
        from core.models import SysAuditLog as AuditLog
        ok("the changes are in the audit history", AuditLog.objects.filter(entity="reports.rig_performance_masters").count() >= 2)

        # closing and reopening a month (the month must have ended)
        RigMonthPlan.objects.filter(rig_id=rig_id).delete()
        r = editor.post(base + "plan/close/", {"rig": rig_id, "month": "2026-10"}, format="json")
        ok("an ended month can be closed (ILM days 0 when none entered)", r.status_code == 200 and RigMonthPlan.objects.get(rig_id=rig_id, month=datetime.date(2026, 10, 1)).closed_on is not None, r.content[:200])
        ok("closing it again is refused", editor.post(base + "plan/close/", {"rig": rig_id, "month": "2026-10"}, format="json").status_code == 409)
        r = editor.put(base + "plan/", {**body, "ilm_days": "2"}, format="json")
        ok("a closed month cannot be changed", r.status_code == 400 and "closed" in r.json()["detail"], r.content[:200])
        sheet = next(x for x in editor.get(base + "rate-sheet/?month=2026-10").json()["rigs"] if x["name"] == "EE01")
        ok("the rate sheet shows it as closed, with the history", sheet["closed"] and sheet["closed"]["on"] and sheet["can_close"] is False and isinstance(sheet["history"], list), str(sheet["closed"]))
        ok("a viewer cannot reopen", viewer.post(base + "plan/reopen/", {"rig": rig_id, "month": "2026-10", "reason": "x"}, format="json").status_code == 403)
        ok("reopening needs a reason", editor.post(base + "plan/reopen/", {"rig": rig_id, "month": "2026-10", "reason": " "}, format="json").status_code == 400)
        ok("a closed month can be reopened with a reason", editor.post(base + "plan/reopen/", {"rig": rig_id, "month": "2026-10", "reason": "check"}, format="json").status_code == 200 and RigMonthPlan.objects.get(rig_id=rig_id, month=datetime.date(2026, 10, 1)).closed_on is None)
        ok("the reopening is in the audit history", AuditLog.objects.filter(entity="reports.rig_performance_masters", action="reopen", note="check").exists())
        ok("after reopening it can be changed again", editor.put(base + "plan/", {**body, "ilm_days": "2"}, format="json").status_code == 200)
        ok("a month that has not ended cannot be closed", editor.post(base + "plan/close/", {"rig": rig_id, "month": f"{datetime.date.today():%Y-%m}"}, format="json").status_code == 409)
        from core.models import ProjectContractDtl
        ProjectContractDtl.objects.filter(rig_id=rig_id, contract_id=contract_id).update(rig_active_from=datetime.date(2026, 10, 16))
        r = editor.put(base + "plan/", {**body, "ilm_days": "17"}, format="json")
        ok("ILM days beyond the days on the project are refused (project from 16 Oct = 16 days)", r.status_code == 400 and "16 days" in r.json()["detail"], r.content[:200])
        ok("ILM days within the project's days are accepted", editor.put(base + "plan/", {**body, "ilm_days": "3"}, format="json").status_code == 200)

        # months where a rig reported but its project line does not cover the month used to fail the whole report (Mar 2024)
        for mon in ("2024-03", "2023-07", "2022-05"):
            rr = viewer.get(base + f"?month={mon}")
            ok(f"{mon}: the report builds", rr.status_code == 200 and (rr.json().get("final") is not None or rr.json().get("message")), rr.content[:160])
            ok(f"{mon}: the rate sheet builds", viewer.get(base + f"rate-sheet/?month={mon}").status_code == 200)
        ok("a rig with no project days in the month (SR03, Mar 2024) is explained, not an error", any("SR03: reported this month but has no days on a project line" in n["text"] for n in viewer.get(base + "?month=2024-03").json()["notes"]))

        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as qc:
            viewer.get(base + "?month=2024-03")
        ok(f"a busy month (7 rigs, Mar 2024) loads with a bounded number of queries ({len(qc)}), not one per activity line", len(qc) < 400, str(len(qc)))
        raise Rollback
except Rollback:
    pass
print("\nFAILED: " + ", ".join(fails) if fails else "\nall passed")
sys.exit(1 if fails else 0)
