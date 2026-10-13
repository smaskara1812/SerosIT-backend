"""Rig Moves and Well Lifecycle dashboard — how long rigs stay on a well, how long they wait
between wells, and how much time and distance the moves take.

Read from Drilling Information (one row per well / rig move) and the daily drilling reports.
Definitions, for wells *started* (first anchor-down) in the chosen calendar year:

  Days on well       completion date minus first anchor-down date. A well with no completion
                     date is open: it is left out of the averages and the longest-wells list and
                     shown on its own, flagged when it has been open for more than 90 days
                     (usually a well that was never closed in the system).
  Gap between wells  anchor-down of a well minus completion of the previous well on the same
                     rig (the rig's idle / moving time between jobs). Only when the previous
                     well is complete and the gap is not negative. If the previous well was never
                     given a completion date its end is unknown, so the next well has no gap (it
                     is counted in gap_unavailable) rather than a gap measured from an earlier well.
  Move type          the rate chosen on the well: ILM (inter-location move), IPM – Lateral or
                     IPM – Adjacent (intra-platform moves). "Not set" when the well has none.
  Distance           one field typed as nautical miles or kilometres, with no unit stored. The unit
                     follows the rig: kilometres on an onshore rig, nautical miles on an offshore
                     one (every distance in the data today is on an onshore rig). Kilometres are
                     totalled; nautical miles are never added in, only counted, and each well shows
                     its figure with its unit.
  Move hours         rig-move hours from the daily reports in the year (the six hour buckets of
                     the Drilling Report), not tied to the year a well started.

Rig scope is the same as every other drilling dashboard (dashboard_access).
"""

import statistics
from datetime import date, datetime

from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from .dashboard_access import dashboard_rig_queryset, get_accessible_rig_ids, same_day_in_year
from .models import DrillingDtl, DrillingHdr
from .permissions import HasMenuPermission

ENTITY_KEY = "dashboards.rig_moves"
MOVE_TYPES = ["ILM", "IPM - Lateral", "IPM - Adjacent", "Not set"]
BUCKETS = [("Up to 7 days", 0, 7), ("8–14 days", 8, 14), ("15–30 days", 15, 30), ("31–60 days", 31, 60), ("Over 60 days", 61, None)]
TOP_WELLS = 15
ONSHORE_RIG_TYPE, OFFSHORE_RIG_TYPE = 2, 1  # distance is kilometres on an onshore rig, nautical miles on an offshore one
STALE_OPEN_DAYS = 90  # an open well older than this is probably just never closed in the system


def _day(v):
    return v.date() if isinstance(v, datetime) else v


def _median(values, nd=1):
    return round(statistics.median(values), nd) if values else None


class RigMovesDashboardView(APIView):
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

        # Every well of these rigs, oldest first, so each one can see the well before it.
        wells = list(
            DrillingHdr.objects.filter(rig_id__in=rig_ids, first_anchor_down_dt__isnull=False)
            .order_by("rig_id", "first_anchor_down_dt", "pk")
            .values("pk", "rig_id", "location", "first_anchor_down_dt", "drilling_completion_dt", "distance_covered_kms_knots", "drilling_rate__rate_code", "rig__rig_type_id")
        )
        years = sorted({_day(w["first_anchor_down_dt"]).year for w in wells}) or [today.year]
        year_param = request.query_params.get("year")
        year = int(year_param) if year_param and year_param.isdigit() else (today.year if today.year in years else years[-1])

        prev_end = {}  # rig -> completion of the previous well
        enriched = []
        for w in wells:
            start, end = _day(w["first_anchor_down_dt"]), _day(w["drilling_completion_dt"]) if w["drilling_completion_dt"] else None
            gap, blocked = None, False
            before = prev_end.get(w["rig_id"], "none")
            if before == "none":
                pass  # first well on record for this rig
            elif before is None:
                blocked = True  # the previous well was never given a completion date
            else:
                g = (start - before).days
                gap = g if g >= 0 else None
            prev_end[w["rig_id"]] = end
            enriched.append(
                {
                    "id": w["pk"],
                    "rig_id": w["rig_id"],
                    "rig_name": names.get(w["rig_id"], ""),
                    "location": w["location"],
                    "start": start,
                    "end": end,
                    "open": end is None,
                    "days": ((end or today) - start).days,
                    "gap": gap,
                    "gap_blocked": blocked,
                    "move_type": w["drilling_rate__rate_code"] or "Not set",
                    "distance": float(w["distance_covered_kms_knots"]) if w["distance_covered_kms_knots"] else None,
                    "distance_unit": "km" if w["rig__rig_type_id"] == ONSHORE_RIG_TYPE else ("NM" if w["rig__rig_type_id"] == OFFSHORE_RIG_TYPE else None),
                }
            )
        mine = [w for w in enriched if w["start"].year == year]
        # The current year is only part-way through, so it is compared with the same stretch of last year.
        if year == today.year:
            upto = same_day_in_year(year - 1, today)
            prev_count = sum(1 for w in enriched if date(year - 1, 1, 1) <= w["start"] <= upto)
            compare_label = f"same period of {year - 1}"
        else:
            prev_count = sum(1 for w in enriched if w["start"].year == year - 1)
            compare_label = str(year - 1)

        done = [w["days"] for w in mine if not w["open"]]
        gaps = [w["gap"] for w in mine if w["gap"] is not None]
        with_distance = [w for w in mine if w["distance"]]
        km_wells = [w for w in with_distance if w["distance_unit"] == "km"]
        nm_wells = [w for w in with_distance if w["distance_unit"] == "NM"]

        # Rig-move hours from the daily reports
        dtl = DrillingDtl.objects.filter(rig_id__in=rig_ids, drilling_dtl_dt__year=year)
        move_hours = float(dtl.aggregate(s=Sum("rig_move_hrs"))["s"] or 0)
        hours_by_rig = {r["rig_id"]: float(r["s"] or 0) for r in dtl.values("rig_id").annotate(s=Sum("rig_move_hrs"))}
        hours_by_month = {f"{year}-{m:02d}": 0.0 for m in range(1, 13)}
        for r in dtl.annotate(m=TruncMonth("drilling_dtl_dt")).values("m").annotate(s=Sum("rig_move_hrs")):
            hours_by_month[r["m"].strftime("%Y-%m")] = float(r["s"] or 0)

        # Wells started by month and move type
        by_month = {f"{year}-{m:02d}": {"month": f"{year}-{m:02d}", **{t: 0 for t in MOVE_TYPES}, "move_hours": 0} for m in range(1, 13)}
        for w in mine:
            key = f"{year}-{w['start'].month:02d}"
            by_month[key][w["move_type"] if w["move_type"] in MOVE_TYPES else "Not set"] += 1
        for k, v in hours_by_month.items():
            by_month[k]["move_hours"] = round(v)

        histogram = [
            {"bucket": label, "count": sum(1 for d in done if d >= lo and (hi is None or d <= hi))} for label, lo, hi in BUCKETS
        ]

        # By rig
        rig_rows = []
        for rid in rig_ids:
            ws = [w for w in mine if w["rig_id"] == rid]
            d = [w["days"] for w in ws if not w["open"]]
            rig_rows.append(
                {
                    "rig_id": rid,
                    "rig_name": names.get(rid, ""),
                    "wells": len(ws),
                    "open_wells": sum(1 for w in ws if w["open"]),
                    "median_days": _median(d),
                    "longest_days": max(d) if d else None,
                    "median_gap": _median([w["gap"] for w in ws if w["gap"] is not None]),
                    "move_hours": round(hours_by_rig.get(rid, 0)),
                    "distance_recorded": sum(1 for w in ws if w["distance"]),
                    "distance_km": round(sum(w["distance"] for w in ws if w["distance"] and w["distance_unit"] == "km"), 1) or None,
                    "distance_nm_wells": sum(1 for w in ws if w["distance"] and w["distance_unit"] == "NM"),
                }
            )
        rig_rows = [r for r in rig_rows if r["wells"] or r["move_hours"]]
        rig_rows.sort(key=lambda r: (-r["wells"], -r["move_hours"], r["rig_name"]))

        longest = sorted((w for w in mine if not w["open"]), key=lambda w: -w["days"])[:TOP_WELLS]
        # Wells with no completion date, whatever year they started in: either genuinely under way or
        # never closed in the system. Ones open longer than STALE_OPEN_DAYS are flagged.
        open_list = sorted((w for w in enriched if w["open"]), key=lambda w: -w["days"])

        return Response(
            {
                "as_of": today,
                "year": year,
                "years": years,
                "compare_label": compare_label,
                "rigs": rigs,
                "move_types": MOVE_TYPES,
                "summary": {
                    "wells": len(mine),
                    "wells_prev": prev_count,
                    "open_wells": sum(1 for w in mine if w["open"]),
                    "open_wells_now": sum(1 for w in enriched if w["open"]),
                    "median_days": _median(done),
                    "p90_days": sorted(done)[int(len(done) * 0.9)] if len(done) >= 10 else None,  # meaningless on fewer wells
                    "gap_unavailable": sum(1 for w in mine if w["gap_blocked"]),
                    "median_gap": _median(gaps),
                    "move_hours": round(move_hours),
                    "distance_recorded": len(with_distance),
                    "distance_km": round(sum(w["distance"] for w in km_wells), 1) if km_wells else None,
                    "distance_km_wells": len(km_wells),
                    "distance_nm_wells": len(nm_wells),
                    "onshore_wells": sum(1 for w in mine if w["distance_unit"] == "km"),
                },
                "by_month": [by_month[k] for k in sorted(by_month)],
                "duration_histogram": histogram,
                "by_rig": rig_rows,
                "longest_wells": longest,
                "open_wells": [{**w, "stale": w["days"] > STALE_OPEN_DAYS} for w in open_list],
                "stale_open_days": STALE_OPEN_DAYS,
            }
        )
