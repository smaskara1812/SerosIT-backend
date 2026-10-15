"""Fuel and Water dashboard — how much diesel and water the rigs use, how that compares
rig to rig, and which daily figures look wrong.

Everything is read from the daily drilling reports (drilling_dtl), nothing is entered here.
Definitions, all over the chosen calendar year and the chosen rigs:

  Diesel / water consumed   sum of the daily Consumption: Diesel / Water figures
  Diesel received           sum of the daily Received: Diesel figures. Several rigs never record
                            receipts, so a balance (received minus consumed) is shown only for a
                            rig that recorded at least one receipt in the year.
  Per operating hour        diesel consumed / operating hours in the same reports
  Per metre drilled         diesel consumed / metres drilled in the same reports (all days, not
                            only drilling days, so it includes fuel burnt while not drilling)
  Per day                   total divided by the rig-days that carry a figure above zero, not by all
                            of them. A rig-day is one rig's daily report for one day, so five rigs
                            working the same day are five rig-days: across several rigs this is the
                            average per rig per day, and the counts shown with it are rig-days
  Days with use            share of a rig's reports with a diesel (or water) figure above zero. The
                            daily report requires the figure, so a zero is a real entry (none used)
                            and is not treated as missing. It describes how often a rig uses water or
                            diesel; it is not a data-quality score.
  Outlier day               a rig-day whose diesel (or water) is at least OUTLIER_FACTOR times that
                            rig's median day in the year, and at least the minimum below; usually a
                            mistyped number, so each one links to its daily report.

The current year is compared with the same stretch of last year, not all of it.
Rig scope is the same as every other drilling dashboard (dashboard_access).
"""

import statistics

from datetime import date

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from .dashboard_access import dashboard_rig_queryset, get_accessible_rig_ids, same_day_in_year
from .models import DrillingDtl
from .permissions import HasMenuPermission

ENTITY_KEY = "dashboards.fuel_water"
OUTLIER_FACTOR = 4
OUTLIER_MIN = {"diesel": 3000, "water": 50000}  # litres: below this a "high" day is not worth flagging
MAX_OUTLIERS = 20


def _f(v):
    return float(v or 0)


def _ratio(a, b, nd=1):
    return round(a / b, nd) if b else None


class FuelWaterDashboardView(APIView):
    permission_classes = [HasMenuPermission]
    entity_key = ENTITY_KEY

    def get(self, request):
        today = timezone.now().date()
        accessible = get_accessible_rig_ids(request)  # None = every rig

        rig_qs = dashboard_rig_queryset()
        if accessible is not None:
            rig_qs = rig_qs.filter(rig_id__in=accessible)
        rigs = list(rig_qs.order_by("rig_name").values("rig_id", "rig_name"))
        names = {r["rig_id"]: r["rig_name"] for r in rigs}
        requested = request.query_params.get("rigs")
        if requested:
            wanted = {int(x) for x in requested.split(",") if x.strip().isdigit()}
            rig_ids = [r["rig_id"] for r in rigs if r["rig_id"] in wanted]
        else:
            rig_ids = [r["rig_id"] for r in rigs]

        year_param = request.query_params.get("year")
        year = int(year_param) if year_param and year_param.isdigit() else today.year
        years = sorted({d.year for d in DrillingDtl.objects.filter(rig_id__in=[r["rig_id"] for r in rigs]).dates("drilling_dtl_dt", "year")}) or [today.year]

        base = DrillingDtl.objects.filter(rig_id__in=rig_ids)
        cur = base.filter(drilling_dtl_dt__year=year)
        # The current year is only part-way through, so it is compared with the same stretch of last year.
        if year == today.year:
            prev = base.filter(drilling_dtl_dt__gte=date(year - 1, 1, 1), drilling_dtl_dt__lte=same_day_in_year(year - 1, today))
            compare_label = f"same period of {year - 1}"
        else:
            prev = base.filter(drilling_dtl_dt__year=year - 1)
            compare_label = str(year - 1)

        totals = cur.aggregate(
            days=Count("pk"),
            diesel=Sum("consumption_diesel"),
            diesel_in=Sum("received_diesel"),
            water=Sum("consumption_water"),
            hours=Sum("operating_hrs"),
            metres=Sum("drilling_meterage"),
            diesel_days=Count("pk", filter=Q(consumption_diesel__gt=0)),
            water_days=Count("pk", filter=Q(consumption_water__gt=0)),
        )
        prev_totals = prev.aggregate(diesel=Sum("consumption_diesel"), water=Sum("consumption_water"), days=Count("pk"))
        diesel, water = _f(totals["diesel"]), _f(totals["water"])

        # By rig
        rows = []
        for r in cur.values("rig_id").annotate(
            days=Count("pk"),
            diesel=Sum("consumption_diesel"),
            diesel_in=Sum("received_diesel"),
            water=Sum("consumption_water"),
            hours=Sum("operating_hrs"),
            metres=Sum("drilling_meterage"),
            diesel_days=Count("pk", filter=Q(consumption_diesel__gt=0)),
            water_days=Count("pk", filter=Q(consumption_water__gt=0)),
            receipt_days=Count("pk", filter=Q(received_diesel__gt=0)),
        ):
            d, w, recv, hrs, m, n = _f(r["diesel"]), _f(r["water"]), _f(r["diesel_in"]), _f(r["hours"]), _f(r["metres"]), r["days"]
            rows.append(
                {
                    "rig_id": r["rig_id"],
                    "rig_name": names.get(r["rig_id"], ""),
                    "days": n,
                    "diesel": round(d),
                    "diesel_per_day": _ratio(d, r["diesel_days"], 0),
                    "diesel_per_hour": _ratio(d, hrs),
                    "diesel_per_metre": _ratio(d, m),
                    "diesel_received": round(recv),
                    "diesel_balance": round(recv - d) if r["receipt_days"] else None,
                    "diesel_use_pct": round(r["diesel_days"] / n * 100) if n else None,
                    "water": round(w),
                    "water_per_day": _ratio(w, r["water_days"], 0),
                    "water_use_pct": round(r["water_days"] / n * 100) if n else None,
                }
            )
        rows.sort(key=lambda r: -r["diesel"])

        # By month: fleet totals, and diesel per operating hour
        by_month = {f"{year}-{m:02d}": {"month": f"{year}-{m:02d}", "diesel": 0.0, "diesel_in": 0.0, "water": 0.0, "hours": 0.0} for m in range(1, 13)}
        for r in cur.annotate(m=TruncMonth("drilling_dtl_dt")).values("m").annotate(
            diesel=Sum("consumption_diesel"), diesel_in=Sum("received_diesel"), water=Sum("consumption_water"), hours=Sum("operating_hrs")
        ):
            by_month[r["m"].strftime("%Y-%m")] = {
                "month": r["m"].strftime("%Y-%m"),
                "diesel": _f(r["diesel"]),
                "diesel_in": _f(r["diesel_in"]),
                "water": _f(r["water"]),
                "hours": _f(r["hours"]),
            }
        monthly = [
            {**m, "diesel": round(m["diesel"]), "diesel_in": round(m["diesel_in"]), "water": round(m["water"]), "diesel_per_hour": _ratio(m["diesel"], m["hours"])}
            for _, m in sorted(by_month.items())
        ]

        # Outlier days: far above that rig's own median day
        outliers = []
        per_rig = {}
        for pk, rid, dt, dsl, wtr in cur.values_list("pk", "rig_id", "drilling_dtl_dt", "consumption_diesel", "consumption_water"):
            per_rig.setdefault(rid, []).append((pk, dt, _f(dsl), _f(wtr)))
        for rid, days in per_rig.items():
            for kind, idx in (("diesel", 2), ("water", 3)):
                vals = [d[idx] for d in days if d[idx] > 0]
                if len(vals) < 10:
                    continue
                med = statistics.median(vals)
                for d in days:
                    if d[idx] >= OUTLIER_MIN[kind] and d[idx] >= OUTLIER_FACTOR * med:
                        outliers.append(
                            {
                                "report_id": d[0],
                                "date": d[1],
                                "rig_id": rid,
                                "rig_name": names.get(rid, ""),
                                "kind": kind,
                                "value": round(d[idx]),
                                "median": round(med),
                                "times_median": round(d[idx] / med, 1),
                            }
                        )
        outliers.sort(key=lambda o: -o["times_median"])

        return Response(
            {
                "as_of": today,
                "year": year,
                "years": years,
                "rigs": rigs,
                "outlier_factor": OUTLIER_FACTOR,
                "compare_label": compare_label,
                "summary": {
                    "days": totals["days"],
                    "diesel": round(diesel),
                    "diesel_prev": round(_f(prev_totals["diesel"])),
                    "diesel_days": totals["diesel_days"],
                    "water_days": totals["water_days"],
                    "diesel_per_day": _ratio(diesel, totals["diesel_days"], 0),
                    "diesel_per_hour": _ratio(diesel, _f(totals["hours"])),
                    "diesel_per_metre": _ratio(diesel, _f(totals["metres"])),
                    "diesel_received": round(_f(totals["diesel_in"])),
                    "water": round(water),
                    "water_prev": round(_f(prev_totals["water"])),
                    "water_per_day": _ratio(water, totals["water_days"], 0),
                    "outlier_days": len({o["report_id"] for o in outliers}),
                },
                "by_month": monthly,
                "by_rig": rows,
                "outliers": outliers[:MAX_OUTLIERS],
            }
        )
