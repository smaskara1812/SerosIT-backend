"""Contract Exposure dashboard — commercial view of the fleet: hours
logged against each billing rate code, and which rigs' contracts are
running out soon.

Estimated contract value (hours x rate) is deliberately not shown yet —
holding off until requirements around how rate should be applied per
project are clearer, rather than shipping a number that might be read as
more authoritative than it is.

"Coverage gap" is a stricter, more actionable flag than the plain "Idle"
count on Fleet Operating Picture: a rig that's active (rig_active='Y') but
has no current contract line is failing to earn revenue right now, whereas
"idle" alone also includes rigs that are inactive by design (out of
service, decommissioned, etc.) and aren't really a gap to fix.
"""

from django.db.models import Sum
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from .dashboard_access import current_contract_by_rig, dashboard_rig_queryset, get_accessible_rig_ids
from .models import DrillingDtlOps
from .permissions import HasMenuPermission

ENDING_BUCKETS_DAYS = [30, 60, 90]


class ContractExposureDashboardView(APIView):
    permission_classes = [HasMenuPermission]
    entity_key = "dashboards.contract_exposure"

    def get(self, request):
        today = timezone.now().date()
        accessible = get_accessible_rig_ids(request)  # None = every rig

        rig_qs = dashboard_rig_queryset()
        if accessible is not None:
            rig_qs = rig_qs.filter(rig_id__in=accessible)
        accessible_rigs = list(rig_qs.order_by("rig_name"))

        requested = request.query_params.get("rigs")
        if requested:
            requested_ids = {int(x) for x in requested.split(",") if x.strip().isdigit()}
            effective_rigs = [r for r in accessible_rigs if r.rig_id in requested_ids]
        else:
            effective_rigs = accessible_rigs
        effective_rig_ids = [r.rig_id for r in effective_rigs]

        year_param = request.query_params.get("year")
        year = int(year_param) if year_param and year_param.isdigit() else today.year

        available_years = sorted(
            {
                d.year
                for d in DrillingDtlOps.objects.filter(drilling_dtl__rig_id__in=effective_rig_ids).dates(
                    "drilling_dtl__drilling_dtl_dt", "year"
                )
            }
        ) or [today.year]

        contract_by_rig = current_contract_by_rig(effective_rig_ids, today)

        # KPIs + per-rig coverage table.
        rows = []
        on_contract = coverage_gaps = 0
        ending_counts = {d: 0 for d in ENDING_BUCKETS_DAYS}
        for rig in effective_rigs:
            line = contract_by_rig.get(rig.rig_id)
            if line:
                on_contract += 1
                if line.rig_active_to and line.rig_active_to >= today:
                    days_left = (line.rig_active_to - today).days
                    for bucket in ENDING_BUCKETS_DAYS:
                        if days_left <= bucket:
                            ending_counts[bucket] += 1
                            break
            elif rig.rig_active == "Y":
                coverage_gaps += 1

            rows.append(
                {
                    "rig_id": rig.rig_id,
                    "rig_name": rig.rig_name,
                    "rig_active": rig.rig_active,
                    "contract_no": line.contract.prj_contract_no if line else None,
                    "operator_name": line.contract.operator.operator_name if line else None,
                    "location_name": line.contract.location.location_name if line else None,
                    "contract_start": line.rig_active_from if line else None,
                    "contract_ends": line.rig_active_to if line else None,
                    "days_remaining": (line.rig_active_to - today).days
                    if line and line.rig_active_to
                    else None,
                }
            )

        summary = {
            "on_contract": on_contract,
            "idle": len(effective_rigs) - on_contract,
            "coverage_gaps": coverage_gaps,
            **{f"ending_{d}d": ending_counts[d] for d in ENDING_BUCKETS_DAYS},
        }

        # Hours by rate code — fleet total, selected year. Every logged ops
        # row carries its own prj_drilling_rate FK straight to the rate
        # type actually billed for that time block.
        rate_rows = (
            DrillingDtlOps.objects.filter(
                drilling_dtl__rig_id__in=effective_rig_ids, drilling_dtl__drilling_dtl_dt__year=year
            )
            .values("prj_drilling_rate__drilling_rate__rate_code")
            .annotate(hours=Sum("duration"))
            .order_by("-hours")
        )
        hours_by_rate_code = [
            {"rate_code": row["prj_drilling_rate__drilling_rate__rate_code"] or "Unspecified", "hours": float(row["hours"] or 0)}
            for row in rate_rows
        ]

        return Response(
            {
                "as_of": today,
                "years": available_years,
                "year": year,
                "summary": summary,
                "rigs": [{"rig_id": r.rig_id, "rig_name": r.rig_name} for r in accessible_rigs],
                "rows": rows,
                "hours_by_rate_code": hours_by_rate_code,
            }
        )
