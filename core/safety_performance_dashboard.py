"""Safety Performance dashboard — Hazard ID Cards and Incidents side by side.

Hazard cards are the *leading* signal (what people notice and report before
anything happens); incidents are the *lagging* one (what actually happened).
Putting them on one page shows whether reporting is healthy: a rig with many
hazard cards and few incidents is looking; a rig with neither may not be.

Definitions (all counts exclude soft-deleted records):
  Hazard cards         hazard_card rows raised in the chosen calendar year, by event date (the
                       current year is compared with the same stretch of last year)
  Positive recognition the hazard type "Positive Recognition" (good behaviour noticed) —
                       counted in the total, but left out of the hazard-location chart
  Open cards           status not Closed, raised in the last 12 months (older ones are legacy
                       cards that were never closed out and would drown the current picture);
                       aged from the event date
  Incidents            incident rows by incident date; "high" is severity H; "injuries" are
                       rows where a person was injured
  Days since last      from the most recent incident of any year on that rig

Rig scope is the same as every other drilling dashboard (dashboard_access): real
drilling rigs the user is mapped to. Incidents not tied to a rig are not counted.
"""

from datetime import date, timedelta

from django.db.models import Count, Max, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from .dashboard_access import dashboard_rig_queryset, get_accessible_rig_ids, same_day_in_year
from .models import HazardCard, Incident
from .permissions import HasMenuPermission

ENTITY_KEY = "dashboards.safety_performance"
POSITIVE = "Positive Recognition"
TOP_N = 8
OPEN_WINDOW_DAYS = 365


def _hazards(rig_ids):
    return HazardCard.objects.exclude(marked_as_deleted="Y").filter(rig_id__in=rig_ids)


def _incidents(rig_ids):
    return Incident.objects.exclude(marked_as_deleted="Y").filter(rig_id__in=rig_ids)


class SafetyPerformanceDashboardView(APIView):
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

        all_rig_ids = [r["rig_id"] for r in rigs]
        years = sorted(
            {d.year for d in _hazards(all_rig_ids).dates("event_dt", "year")}
            | {d.year for d in _incidents(all_rig_ids).dates("incident_date", "year")}
        ) or [today.year]

        hz = _hazards(rig_ids)
        inc = _incidents(rig_ids)
        hz_year, inc_year = hz.filter(event_dt__year=year), inc.filter(incident_date__year=year)
        # The current year is only part-way through, so it is compared with the same stretch of last year.
        if year == today.year:
            upto = same_day_in_year(year - 1, today)
            hz_prev = hz.filter(event_dt__date__gte=date(year - 1, 1, 1), event_dt__date__lte=upto)
            inc_prev = inc.filter(incident_date__date__gte=date(year - 1, 1, 1), incident_date__date__lte=upto)
            compare_label = f"same period of {year - 1}"
        else:
            hz_prev, inc_prev = hz.filter(event_dt__year=year - 1), inc.filter(incident_date__year=year - 1)
            compare_label = str(year - 1)

        positive = Q(haz_type__haz_type_name=POSITIVE)
        hz_totals = hz_year.aggregate(n=Count("pk"), positive=Count("pk", filter=positive), tfs=Count("pk", filter=Q(timeout_for_safety="Y")))
        inc_totals = inc_year.aggregate(
            n=Count("pk"), high=Count("pk", filter=Q(incident_severity="H")), injuries=Count("pk", filter=Q(person_injured="Y"))
        )
        n_hz, n_inc = hz_totals["n"], inc_totals["n"]

        # Open hazard cards (live, last 12 months) and how old they are
        open_qs = hz.exclude(haz_id_card_status="C").filter(event_dt__date__gte=today - timedelta(days=OPEN_WINDOW_DAYS))
        # Age in whole days, so every open card lands in exactly one bucket (edges are inclusive).
        def aged(youngest, oldest):
            q = Q(event_dt__date__lte=today - timedelta(days=youngest))
            return q & Q(event_dt__date__gte=today - timedelta(days=oldest)) if oldest is not None else q

        buckets = open_qs.aggregate(
            total=Count("pk"),
            b0=Count("pk", filter=Q(event_dt__date__gte=today - timedelta(days=30))),
            b1=Count("pk", filter=aged(31, 90)),
            b2=Count("pk", filter=aged(91, 180)),
            b3=Count("pk", filter=aged(181, None)),
        )
        open_ageing = [
            {"bucket": "Up to 30 days", "count": buckets["b0"]},
            {"bucket": "31–90 days", "count": buckets["b1"]},
            {"bucket": "91–180 days", "count": buckets["b2"]},
            {"bucket": "Over 180 days", "count": buckets["b3"]},
        ]
        open_total = buckets["total"]

        last_incident = inc.aggregate(m=Max("incident_date"))["m"]
        days_since = (today - last_incident.date()).days if last_incident else None

        # Month by month: hazard cards by type, incidents by severity
        type_names = list(
            hz_year.exclude(haz_type__isnull=True).values_list("haz_type__haz_type_name", flat=True).distinct().order_by("haz_type__haz_type_name")
        )
        months = {f"{year}-{m:02d}": {"month": f"{year}-{m:02d}", "hazards": {t: 0 for t in type_names}, "incidents": 0} for m in range(1, 13)}
        for row in (
            hz_year.exclude(haz_type__isnull=True)
            .annotate(m=TruncMonth("event_dt"))
            .values("m", "haz_type__haz_type_name")
            .annotate(n=Count("pk"))
        ):
            months[row["m"].strftime("%Y-%m")]["hazards"][row["haz_type__haz_type_name"]] = row["n"]
        for row in inc_year.annotate(m=TruncMonth("incident_date")).values("m").annotate(n=Count("pk")):
            months[row["m"].strftime("%Y-%m")]["incidents"] = row["n"]

        # By rig
        by_rig = {rid: {"rig_id": rid, "rig_name": names.get(rid, ""), "hazards": 0, "positive": 0, "tfs": 0, "incidents": 0, "high": 0, "injuries": 0, "open_hazards": 0, "days_since_incident": None} for rid in rig_ids}
        for row in hz_year.values("rig_id").annotate(n=Count("pk"), pos=Count("pk", filter=positive), tfs=Count("pk", filter=Q(timeout_for_safety="Y"))):
            r = by_rig.get(row["rig_id"])
            if r:
                r["hazards"], r["positive"], r["tfs"] = row["n"], row["pos"], row["tfs"]
        for row in inc_year.values("rig_id").annotate(n=Count("pk"), high=Count("pk", filter=Q(incident_severity="H")), inj=Count("pk", filter=Q(person_injured="Y"))):
            r = by_rig.get(row["rig_id"])
            if r:
                r["incidents"], r["high"], r["injuries"] = row["n"], row["high"], row["inj"]
        for row in open_qs.values("rig_id").annotate(n=Count("pk")):
            r = by_rig.get(row["rig_id"])
            if r:
                r["open_hazards"] = row["n"]
        for row in inc.values("rig_id").annotate(m=Max("incident_date")):
            r = by_rig.get(row["rig_id"])
            if r and row["m"]:
                r["days_since_incident"] = (today - row["m"].date()).days
        rows = []
        for r in by_rig.values():
            r["tfs_pct"] = round(r["tfs"] / r["hazards"] * 100) if r["hazards"] else None
            rows.append(r)
        rows.sort(key=lambda r: (-(r["hazards"] + r["incidents"]), r["rig_name"]))

        hazards_by_location = [
            {"name": row["work_location__work_location"] or "Not recorded", "count": row["n"]}
            for row in hz_year.exclude(positive)
            .values("work_location__work_location")
            .annotate(n=Count("pk"))
            .order_by("-n")[:TOP_N]
        ]
        hazards_by_party = [
            {"name": row["reported_by_party"] or "Not recorded", "count": row["n"]}
            for row in hz_year.values("reported_by_party").annotate(n=Count("pk")).order_by("-n")
        ]
        incidents_by_type = [
            {"name": row["incident_type__incident_type"] or "Not recorded", "count": row["n"]}
            for row in inc_year.values("incident_type__incident_type").annotate(n=Count("pk")).order_by("-n")[:TOP_N]
        ]
        severity = {row["incident_severity"]: row["n"] for row in inc_year.values("incident_severity").annotate(n=Count("pk"))}

        return Response(
            {
                "as_of": today,
                "year": year,
                "years": years,
                "compare_label": compare_label,
                "rigs": rigs,
                "summary": {
                    "hazards": n_hz,
                    "hazards_prev": hz_prev.count(),
                    "positive": hz_totals["positive"],
                    "positive_pct": round(hz_totals["positive"] / n_hz * 100) if n_hz else None,
                    "tfs_pct": round(hz_totals["tfs"] / n_hz * 100) if n_hz else None,
                    "incidents": n_inc,
                    "incidents_prev": inc_prev.count(),
                    "high": inc_totals["high"],
                    "injuries": inc_totals["injuries"],
                    "open_hazards": open_total,
                    "open_over_30": open_total - buckets["b0"],
                    "days_since_last_incident": days_since,
                    "last_incident_date": last_incident.date() if last_incident else None,
                },
                "hazard_types": type_names,
                "by_month": [months[k] for k in sorted(months)],
                "by_rig": rows,
                "open_ageing": open_ageing,
                "hazards_by_location": hazards_by_location,
                "hazards_by_party": hazards_by_party,
                "incidents_by_type": incidents_by_type,
                "incidents_by_severity": {"H": severity.get("H", 0), "M": severity.get("M", 0), "L": severity.get("L", 0)},
            }
        )
