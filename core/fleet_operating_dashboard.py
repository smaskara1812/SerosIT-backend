"""Fleet Operating Picture dashboard — a live snapshot, not a year-filtered
trend like Rig Utilisation / Drilling Performance: which rigs are on
contract vs idle, what well each is currently on, and which rigs have gone
quiet (an open well with no recent daily report).

"Silent" threshold is 3+ days without a report on an open well, not 1 —
explicit product decision, since a single missed day is routine reporting
lag, not an operational red flag.
"""

from datetime import timedelta

from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from .dashboard_access import current_contract_by_rig, dashboard_rig_queryset, get_accessible_rig_ids
from .models import DrillingDtl, DrillingHdr
from .permissions import HasMenuPermission

SILENT_DAYS_THRESHOLD = 3
CONTRACT_ENDING_SOON_DAYS = 30


class FleetOperatingDashboardView(APIView):
    permission_classes = [HasMenuPermission]
    entity_key = "dashboards.fleet_operating_picture"

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

        contract_by_rig = current_contract_by_rig(effective_rig_ids, today)

        # Current open well per rig (no completion date yet). Same
        # most-recent-wins tie-break if a rig somehow has more than one.
        open_wells = (
            DrillingHdr.objects.filter(rig_id__in=effective_rig_ids, drilling_completion_dt__isnull=True)
            .order_by("rig_id", "-first_anchor_down_dt")
        )
        open_well_by_rig = {}
        for well in open_wells:
            open_well_by_rig.setdefault(well.rig_id, well)

        # Latest daily report per rig (date + people-on-board fields).
        latest_reports = (
            DrillingDtl.objects.filter(rig_id__in=effective_rig_ids)
            .order_by("rig_id", "-drilling_dtl_dt")
            .values("rig_id", "drilling_dtl_dt", "pob_operator", "pob_essar", "pob_essar_serv", "pob_others")
        )
        latest_report_by_rig = {}
        for row in latest_reports:
            latest_report_by_rig.setdefault(row["rig_id"], row)

        rows = []
        active_rigs = on_contract = open_wells_count = silent_count = ending_soon_count = 0
        for rig in effective_rigs:
            if rig.rig_active == "Y":
                active_rigs += 1

            contract_line = contract_by_rig.get(rig.rig_id)
            if contract_line:
                on_contract += 1
                if (
                    contract_line.rig_active_to
                    and today <= contract_line.rig_active_to <= today + timedelta(days=CONTRACT_ENDING_SOON_DAYS)
                ):
                    ending_soon_count += 1

            well = open_well_by_rig.get(rig.rig_id)
            latest_report = latest_report_by_rig.get(rig.rig_id)
            days_since_report = (today - latest_report["drilling_dtl_dt"]).days if latest_report else None

            is_silent = False
            if well:
                open_wells_count += 1
                is_silent = days_since_report is None or days_since_report >= SILENT_DAYS_THRESHOLD
                if is_silent:
                    silent_count += 1

            pob_total = None
            if latest_report:
                pob_total = sum(
                    latest_report[f] or 0
                    for f in ("pob_operator", "pob_essar", "pob_essar_serv", "pob_others")
                )

            rows.append(
                {
                    "rig_id": rig.rig_id,
                    "rig_name": rig.rig_name,
                    "rig_active": rig.rig_active,
                    "contract_no": contract_line.contract.prj_contract_no if contract_line else None,
                    "operator_name": contract_line.contract.operator.operator_name if contract_line else None,
                    "contract_ends": contract_line.rig_active_to if contract_line else None,
                    "well_location": well.location if well else None,
                    "water_depth": well.total_water_depth if well else None,
                    "days_on_well": (today - well.first_anchor_down_dt.date()).days if well else None,
                    "last_report_dt": latest_report["drilling_dtl_dt"] if latest_report else None,
                    "days_since_report": days_since_report,
                    "is_silent": is_silent,
                    "pob_total": pob_total,
                }
            )

        return Response(
            {
                "as_of": today,
                "silent_days_threshold": SILENT_DAYS_THRESHOLD,
                "summary": {
                    "active_rigs": active_rigs,
                    "total_rigs": len(effective_rigs),
                    "on_contract": on_contract,
                    "idle": len(effective_rigs) - on_contract,
                    "open_wells": open_wells_count,
                    "silent_rigs": silent_count,
                    "contracts_ending_soon": ending_soon_count,
                },
                "rigs": [{"rig_id": r.rig_id, "rig_name": r.rig_name} for r in accessible_rigs],
                "rows": rows,
            }
        )
