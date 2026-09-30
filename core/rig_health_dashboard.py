"""Rig Health Index — one ranked score per active rig for a quick "what
needs attention" read, built from five components that already exist as
separate facts spread across other pages:

  1. Report freshness   — same "days since last daily report" idea as
                           Fleet Operating Picture (only meaningful for a
                           rig with an open well; a rig with no open well
                           can't be stale on something it isn't doing).
  2. Efficiency %        — the exact Performance Dashboard formula (100 -
                           downtime/24 per day), generalised to
                           calendar-year-to-date instead of one day/month.
  3. Open high-severity incident actions — IncidentAction rows still
                           action_status='OP', off an Incident with
                           incident_severity='H'. Live, not year-scoped —
                           an open action from last year is still open.
  4. Overdue certificates — RigCert.valid_till in the past.
  5. Overdue mandatory activities — ActivityMonitor rows with no
                           completion_dt, scheduled_dt in the past, and
                           their Activity marked Mandatory.

The Health Index itself is a plain unweighted average of the five 0-100
component scores — a sort key, not a hidden formula. Every component is
returned alongside it so the number can always be argued with.

Live snapshot (no year filter) — matches Fleet Operating Picture's own
"this is what's true right now" framing, since this is meant to answer
"what needs attention today," not a historical trend. Efficiency is the
one component that needs *some* window to mean anything, so it uses
calendar-year-to-date.
"""

from datetime import date

from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from .dashboard_access import dashboard_rig_queryset, get_accessible_rig_ids
from .models import ActivityMonitor, DrillingDtl, DrillingHdr, Incident, IncidentAction, RigCert
from .permissions import HasMenuPermission

DOWNTIME_FIELDS = ["repair_service_hrs", "repair_rate_hrs", "zero_rate_hrs"]


def _clamp(v):
    return max(0.0, min(100.0, v))


class RigHealthDashboardView(APIView):
    permission_classes = [HasMenuPermission]
    entity_key = "dashboards.rig_health"

    def get(self, request):
        today = timezone.now().date()
        year_start = date(today.year, 1, 1)
        accessible = get_accessible_rig_ids(request)  # None = every rig

        rig_qs = dashboard_rig_queryset().filter(rig_active="Y")
        if accessible is not None:
            rig_qs = rig_qs.filter(rig_id__in=accessible)

        requested = request.query_params.get("rigs")
        all_active_rigs = list(rig_qs.order_by("rig_name"))
        if requested:
            requested_ids = {int(x) for x in requested.split(",") if x.strip().isdigit()}
            effective_rigs = [r for r in all_active_rigs if r.rig_id in requested_ids]
        else:
            effective_rigs = all_active_rigs
        effective_rig_ids = [r.rig_id for r in effective_rigs]

        # 1. Report freshness — open well + latest report per rig, same
        # facts Fleet Operating Picture reads.
        open_well_rig_ids = set(
            DrillingHdr.objects.filter(rig_id__in=effective_rig_ids, drilling_completion_dt__isnull=True)
            .values_list("rig_id", flat=True)
            .distinct()
        )
        latest_report_by_rig = {}
        for row in (
            DrillingDtl.objects.filter(rig_id__in=effective_rig_ids)
            .order_by("rig_id", "-drilling_dtl_dt")
            .values("rig_id", "drilling_dtl_dt")
        ):
            latest_report_by_rig.setdefault(row["rig_id"], row["drilling_dtl_dt"])

        # 2. Efficiency, calendar-year-to-date — downtime hours and reported
        # day-count per rig, summed separately (not combined in one
        # annotate) to avoid the same to-many join fan-out risk noted on
        # Report Trust's own aggregations.
        ytd_dtl_qs = DrillingDtl.objects.filter(
            rig_id__in=effective_rig_ids, drilling_dtl_dt__gte=year_start, drilling_dtl_dt__lte=today
        )
        downtime_by_rig = {
            row["rig_id"]: sum(float(row[f] or 0) for f in DOWNTIME_FIELDS)
            for row in ytd_dtl_qs.values("rig_id").annotate(**{f: Sum(f) for f in DOWNTIME_FIELDS})
        }
        days_reported_by_rig = dict(
            ytd_dtl_qs.values("rig_id").annotate(n=Count("*")).values_list("rig_id", "n")
        )

        # 3. Open high-severity incident actions, live (no year scope).
        open_hi_sev_rows = (
            IncidentAction.objects.filter(
                incident__rig_id__in=effective_rig_ids,
                incident__incident_severity="H",
                action_status="OP",
            )
            .exclude(marked_as_deleted="Y")
            .exclude(incident__marked_as_deleted="Y")
            .values("incident__rig_id")
        )
        open_hi_sev_count_by_rig = {}
        for row in open_hi_sev_rows:
            rid = row["incident__rig_id"]
            open_hi_sev_count_by_rig[rid] = open_hi_sev_count_by_rig.get(rid, 0) + 1

        # 4. Overdue certificates, live.
        overdue_cert_rows = RigCert.objects.filter(
            rig_id__in=effective_rig_ids, valid_till__isnull=False, valid_till__lt=today
        ).values("rig_id")
        overdue_cert_count_by_rig = {}
        for row in overdue_cert_rows:
            overdue_cert_count_by_rig[row["rig_id"]] = overdue_cert_count_by_rig.get(row["rig_id"], 0) + 1

        # 5. Overdue mandatory activities, live.
        overdue_activity_rows = ActivityMonitor.objects.filter(
            rig_id__in=effective_rig_ids,
            completion_dt__isnull=True,
            scheduled_dt__lt=today,
            activity__activity_nature="M",
        ).values("rig_id")
        overdue_activity_count_by_rig = {}
        for row in overdue_activity_rows:
            overdue_activity_count_by_rig[row["rig_id"]] = overdue_activity_count_by_rig.get(row["rig_id"], 0) + 1

        rows = []
        for rig in effective_rigs:
            rid = rig.rig_id
            has_open_well = rid in open_well_rig_ids
            last_report_dt = latest_report_by_rig.get(rid)
            days_since_report = (today - last_report_dt).days if last_report_dt else None

            if not has_open_well:
                freshness_score = 100.0
            elif days_since_report is None:
                freshness_score = 0.0
            else:
                freshness_score = _clamp(100 - days_since_report * 10)

            downtime = downtime_by_rig.get(rid, 0.0)
            days_reported = days_reported_by_rig.get(rid, 0)
            if days_reported:
                efficiency_pct = round(100 - (downtime / (24 * days_reported) * 100), 1)
                efficiency_score = _clamp(efficiency_pct)
            else:
                efficiency_pct = None
                efficiency_score = None

            open_hi_sev = open_hi_sev_count_by_rig.get(rid, 0)
            hi_sev_score = _clamp(100 - open_hi_sev * 25)

            overdue_certs = overdue_cert_count_by_rig.get(rid, 0)
            cert_score = _clamp(100 - overdue_certs * 25)

            overdue_activities = overdue_activity_count_by_rig.get(rid, 0)
            activity_score = _clamp(100 - overdue_activities * 20)

            component_scores = [freshness_score, hi_sev_score, cert_score, activity_score]
            if efficiency_score is not None:
                component_scores.append(efficiency_score)
            health_index = round(sum(component_scores) / len(component_scores), 1)

            rows.append(
                {
                    "rig_id": rid,
                    "rig_name": rig.rig_name,
                    "health_index": health_index,
                    "has_open_well": has_open_well,
                    "days_since_report": days_since_report,
                    "freshness_score": round(freshness_score, 1),
                    "efficiency_pct": efficiency_pct,
                    "efficiency_score": round(efficiency_score, 1) if efficiency_score is not None else None,
                    "open_hi_sev_actions": open_hi_sev,
                    "hi_sev_score": round(hi_sev_score, 1),
                    "overdue_certs": overdue_certs,
                    "cert_score": round(cert_score, 1),
                    "overdue_mandatory_activities": overdue_activities,
                    "activity_score": round(activity_score, 1),
                }
            )

        rows.sort(key=lambda r: r["health_index"])

        summary = {
            "rigs_scored": len(rows),
            "avg_health_index": round(sum(r["health_index"] for r in rows) / len(rows), 1) if rows else None,
            "rigs_below_60": sum(1 for r in rows if r["health_index"] < 60),
            "total_open_hi_sev_actions": sum(r["open_hi_sev_actions"] for r in rows),
            "total_overdue_certs": sum(r["overdue_certs"] for r in rows),
            "total_overdue_activities": sum(r["overdue_mandatory_activities"] for r in rows),
        }

        return Response(
            {
                "as_of": today,
                "rigs": [{"rig_id": r.rig_id, "rig_name": r.rig_name} for r in all_active_rigs],
                "summary": summary,
                "rows": rows,
            }
        )
