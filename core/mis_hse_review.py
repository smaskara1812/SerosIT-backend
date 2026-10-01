"""QHSE → Monthly HSE Review.

Read-only aggregate/print report — distinct from MIS Monthly HSE Return
(the data-entry page): this one rolls data UP across many Return headers
(plus live Incident/Hazard Card data) for a chosen period and rig scope,
matching legacy's Prc_Qry_Monthly_HSE_Review.

Filter Type:
  SEROS   — every rig (optionally narrowed by Category, same
            Fs_Category -> rig-type mapping used elsewhere in this app —
            see _category_rig_type_ids). Manhours shows just Office/
            Field/Base-Yard (legacy's 'EOSIL' branch never showed Third
            Party here).
  PROJECT — rigs under one selected Project Contract (optionally narrowed
            further to a checked subset of that project's own rigs).
            Manhours additionally breaks out Third Party (Caterers/
            Contractors), matching legacy's 'PROJECT' branch.

Rebrand: legacy's Manhours/Incidents/Hazard-Card columns split EOSIL vs
OGDSL; both are long since folded into "SEROS" everywhere in this app
(see mis_hse_return.py's SEROS_PARTY_NAMES and MstHseManhoursParty's
party-type collapse at import time) — this report groups by name, not by
a hardcoded legacy party id, so the EOSIL-era and OGDSL-era rows for
"Field" or "Office Staff" already land in the same bucket automatically.

LTI Free Days per rig is NOT summed — it's legacy's carry-forward value:
whichever Return header (for that rig) falls inside the period supplies
its own manually-entered lti_free_days (see MisHseReturnIncidentsView),
shown only for a rig under an active Project Contract during the period
("Not in operation" otherwise). Legacy also added a day-count carried
forward from the last dated LTI incident, via a per-rig table of
hardcoded historical offsets — that table was already zeroed out in the
live stored proc (superseded/commented there), so this build doesn't
reimplement it either; carrying it forward added nothing live rows
didn't already capture.

Not implemented: the Vehicle/KM-Driven section, and VAF (Vehicle Accident
Frequency) along with it — both its numerator (Vehicle Incident count)
and its denominator (KM Driven) depend on that same missing vehicle
module (see mis_hse_return.py's docstring; same reasoning), so it's
dropped from the statistics entirely rather than shown as a fake 0.
"""

from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.db.models import Max, Min, Q
from django.http import HttpResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from . import audit as _audit
from .incident_views import _category_rig_type_ids
from .models import (
    HazardCard,
    Incident,
    MisMonthlyHseActivities,
    MisMonthlyHseEnvironment,
    MisMonthlyHseManhours,
    MisMonthlyHseMeetings,
    MisMonthlyHseReturnsHdr,
    MstFsCategory,
    MstIncidentType,
    MstRig,
    ProjectContract,
    ProjectContractDtl,
)
from .permissions import HasMenuPermission

ENTITY_KEY = "qhse.mis_hse_review"
SEROS_PARTY_NAMES = {"SEROS", "EOSIL", "OGDSL"}
# Legacy's two "SEROS-side" manhours rows combine into one "Office" line
# for the SEROS filter type (its two source party ids — Office Staff and
# Contract Staff — always get summed together there); Field and Base/Yard
# stay separate. See module docstring.
OFFICE_PARTY_NAMES = {"Office Staff", "Contract Staff"}

# incident_type_id sets for the safety-rate statistics — straight from
# legacy's hardcoded lists (Fatal, Permanent Total Disability, LTI,
# Restricted Work Case, Medical Treatment Case for TRIR; LTI alone for
# LTIF).
TRIR_INCIDENT_TYPE_IDS = [12, 18, 4, 3, 2]
LTIF_INCIDENT_TYPE_IDS = [4]


QUARTER_LABELS = {"APR_JUN": "Apr-Jun", "JUL_SEP": "Jul-Sep", "OCT_DEC": "Oct-Dec", "JAN_MAR": "Jan-Mar"}


def _last_day(d):
    return d.replace(day=monthrange(d.year, d.month)[1])


def resolve_report_title(params):
    """The PDF/page heading — names the period shape actually chosen
    (Monthly/Quarterly/Annual/Date Range) rather than a fixed "Monthly HSE
    Review" regardless of what was picked."""
    period_type = (params.get("period_type") or "").upper()
    if period_type == "MONTHLY":
        return "Monthly HSE Review"
    if period_type == "QUARTERLY":
        quarter_label = QUARTER_LABELS.get(params.get("quarter"))
        return f"Quarterly HSE Review ({quarter_label})" if quarter_label else "Quarterly HSE Review"
    if period_type == "ANNUAL":
        return "Annual HSE Review"
    if period_type == "DATE_RANGE":
        return "HSE Review (Date Range)"
    return "HSE Review"


def resolve_period(params):
    """Returns (date_from, date_to, period_label) or raises ValueError."""
    period_type = (params.get("period_type") or "").upper()
    if period_type == "MONTHLY":
        month = params.get("month")
        date_from = date.fromisoformat(f"{month}-01")
        date_to = _last_day(date_from)
        label = f"{date_from:%b-%Y}"
    elif period_type == "QUARTERLY":
        year = int(params.get("year"))
        quarter = params.get("quarter")
        start_month = {"APR_JUN": 4, "JUL_SEP": 7, "OCT_DEC": 10, "JAN_MAR": 1}[quarter]
        start_year = year if quarter != "JAN_MAR" else year + 1
        date_from = date(start_year, start_month, 1)
        end_month = start_month + 2
        end_year = start_year
        if end_month > 12:
            end_month -= 12
            end_year += 1
        date_to = _last_day(date(end_year, end_month, 1))
        label = f"{date_from:%b-%Y} to {date_to:%b-%Y}"
    elif period_type == "ANNUAL":
        year = int(params.get("year"))
        date_from = date(year, 1, 1)
        date_to = date(year, 12, 31)
        label = f"Jan-{year} to Dec-{year}"
    elif period_type == "DATE_RANGE":
        date_from = date.fromisoformat(f"{params.get('from_month')}-01")
        date_to = _last_day(date.fromisoformat(f"{params.get('to_month')}-01"))
        label = f"{date_from:%b-%Y} to {date_to:%b-%Y}"
    else:
        raise ValueError("Invalid period_type.")
    if date_to < date_from:
        raise ValueError("Period end is before period start.")
    return date_from, date_to, label


def resolve_rigs(params):
    """Returns (list of MstRig, filter_type, project_or_None)."""
    filter_type = (params.get("filter_type") or "SEROS").upper()
    if filter_type == "PROJECT":
        project_id = params.get("project")
        if not project_id:
            raise ValueError("A Project must be selected for Filter Type = PROJECT.")
        project = ProjectContract.objects.filter(pk=project_id).first()
        if not project:
            raise ValueError("Project not found.")
        rig_ids = list(ProjectContractDtl.objects.filter(contract_id=project_id).values_list("rig_id", flat=True))
        rigs_param = params.get("rigs")
        if rigs_param:
            wanted = {int(x) for x in rigs_param.split(",") if x.strip().isdigit()}
            rig_ids = [r for r in rig_ids if r in wanted]
        rigs = list(MstRig.objects.filter(rig_id__in=rig_ids).order_by("rig_name"))
        return rigs, filter_type, project

    rig_qs = MstRig.objects.all()
    category_id = params.get("category")
    if category_id:
        rig_type_ids = _category_rig_type_ids(category_id)
        if rig_type_ids is not None:
            rig_qs = rig_qs.filter(rig_type_id__in=rig_type_ids)
    return list(rig_qs.order_by("rig_name")), filter_type, None


def _manhours_rows(rig_ids, date_from, date_to, filter_type):
    qs = MisMonthlyHseManhours.objects.filter(
        hdr__rig_id__in=rig_ids, hdr__report_month__gte=date_from, hdr__report_month__lte=date_to
    ).select_related("party")
    seros_totals = {}
    tp_totals = {}
    for m in qs:
        hours = Decimal(m.no_of_personnel or 0) * Decimal(m.hours_worked or 0)
        name = m.party.hse_manhours_party_name
        if m.party.hse_manhours_party_type == "SEROS":
            key = "Office" if name in OFFICE_PARTY_NAMES else name
            seros_totals[key] = seros_totals.get(key, Decimal(0)) + hours
        else:
            tp_totals[name] = tp_totals.get(name, Decimal(0)) + hours

    rows = [{"label": label, "total_man_hours": total} for label, total in sorted(seros_totals.items())]
    third_party_rows = []
    if filter_type == "PROJECT":
        third_party_rows = [{"label": label, "total_man_hours": total} for label, total in sorted(tp_totals.items())]
    grand_total = sum(seros_totals.values()) + (sum(tp_totals.values()) if filter_type == "PROJECT" else Decimal(0))
    return rows, third_party_rows, grand_total


def _total_hours_worked(rig_ids, date_from, date_to, filter_type):
    _, _, total = _manhours_rows(rig_ids, date_from, date_to, "PROJECT" if filter_type == "PROJECT" else "SEROS")
    return total


def _incidents_rows(rig_ids, date_from, date_to):
    qs = Incident.objects.filter(
        rig_id__in=rig_ids, incident_date__date__gte=date_from, incident_date__date__lte=date_to
    ).exclude(marked_as_deleted="Y")
    no_party = Q(incident_party__isnull=True) | Q(incident_party="") | Q(incident_party="0")
    rows = []
    for itype in MstIncidentType.objects.filter(show_on_mis_hse_report="Y").order_by("incident_type"):
        type_qs = qs.filter(incident_type=itype)
        seros = type_qs.exclude(no_party).count()
        contractor = type_qs.filter(no_party).count()
        rows.append(
            {"incident_type": itype.incident_type, "total": seros + contractor, "seros": seros, "contractor": contractor}
        )
    return rows


def _hazard_card_summary(rig_ids, date_from, date_to):
    qs = HazardCard.objects.filter(
        rig_id__in=rig_ids, event_dt__date__gte=date_from, event_dt__date__lte=date_to
    ).exclude(marked_as_deleted="Y")
    seros_qs = qs.filter(reported_by_party__in=SEROS_PARTY_NAMES)
    others_qs = qs.exclude(reported_by_party__in=SEROS_PARTY_NAMES)

    def counts(base_qs):
        return base_qs.count(), base_qs.filter(haz_id_card_status="O").count(), base_qs.filter(haz_id_card_status="C").count()

    seros_total, seros_open, seros_close = counts(seros_qs)
    others_total, others_open, others_close = counts(others_qs)
    return {
        "total": {"total": seros_total + others_total, "seros": seros_total, "others": others_total},
        "open": {"total": seros_open + others_open, "seros": seros_open, "others": others_open},
        "close": {"total": seros_close + others_close, "seros": seros_close, "others": others_close},
    }


def _activities_rows(rig_ids, date_from, date_to):
    from .models import MstHseActivity

    qs = MisMonthlyHseActivities.objects.filter(
        hdr__rig_id__in=rig_ids, hdr__report_month__gte=date_from, hdr__report_month__lte=date_to
    )
    totals = {}
    for row in qs:
        totals[row.activity_id] = totals.get(row.activity_id, 0) + (row.total_activities or 0)
    return [
        {"activity_name": a.hse_activity_name, "total_number": totals.get(a.hse_activity_id, 0)}
        for a in MstHseActivity.objects.order_by("hse_activity_name")
    ]


def _environment_rows(rig_ids, date_from, date_to):
    from .models import MstHseConsumable

    qs = MisMonthlyHseEnvironment.objects.filter(
        hdr__rig_id__in=rig_ids, hdr__report_month__gte=date_from, hdr__report_month__lte=date_to
    )
    totals = {}
    for row in qs:
        totals[row.consumable_id] = totals.get(row.consumable_id, Decimal(0)) + (row.total_quantity or Decimal(0))
    return [
        {"consumable_name": c.hse_consumable_name, "unit": c.hse_consumption_unit, "total_quantity": totals.get(c.hse_consumable_id, Decimal(0))}
        for c in MstHseConsumable.objects.order_by("hse_consumable_id")
    ]


def _meetings_total(rig_ids, date_from, date_to):
    qs = MisMonthlyHseMeetings.objects.filter(
        hdr__rig_id__in=rig_ids, hdr__report_month__gte=date_from, hdr__report_month__lte=date_to
    )
    return sum((row.total_meetings or 0) for row in qs)


def _lti_rows(rigs, date_from, date_to):
    rig_ids = [r.rig_id for r in rigs]
    active_rig_ids = set(
        ProjectContractDtl.objects.filter(rig_id__in=rig_ids, rig_active_from__lte=date_to)
        .filter(Q(rig_active_to__isnull=True) | Q(rig_active_to__gte=date_from))
        .values_list("rig_id", flat=True)
    )
    lti_map = {}
    for row in (
        MisMonthlyHseReturnsHdr.objects.filter(
            rig_id__in=rig_ids, report_month__gte=date_from, report_month__lte=date_to, lti_free_days__isnull=False
        )
        .order_by("rig_id", "-report_month")
    ):
        lti_map.setdefault(row.rig_id, row.lti_free_days)

    return [
        {
            "rig_id": r.rig_id,
            "rig_name": r.rig_name,
            "active": r.rig_id in active_rig_ids,
            "lti_free_days": lti_map.get(r.rig_id, 0) if r.rig_id in active_rig_ids else None,
        }
        for r in rigs
    ]


def _statistics(rig_ids, period_type, date_from, date_to, filter_type):
    if period_type == "DATE_RANGE":
        stat_from, stat_to = date_from, date_to
    else:
        stat_from, stat_to = date(date_from.year, 1, 1), date_to

    total_hours = _total_hours_worked(rig_ids, stat_from, stat_to, filter_type)

    def incident_count(type_ids):
        return (
            Incident.objects.filter(
                rig_id__in=rig_ids, incident_date__date__gte=stat_from, incident_date__date__lte=stat_to, incident_type_id__in=type_ids
            )
            .exclude(marked_as_deleted="Y")
            .count()
        )

    trir_incidents = incident_count(TRIR_INCIDENT_TYPE_IDS)
    ltif_incidents = incident_count(LTIF_INCIDENT_TYPE_IDS)

    def rate(count, multiplier):
        if not total_hours:
            return Decimal(0)
        return (Decimal(count) * multiplier) / total_hours

    return {
        "statistic_from": stat_from,
        "statistic_to": stat_to,
        "total_hours_worked": total_hours,
        "ltif": rate(ltif_incidents, 1000000),
        "trir": rate(trir_incidents, 200000),
    }


def build_report(params):
    date_from, date_to, period_label = resolve_period(params)
    rigs, filter_type, project = resolve_rigs(params)
    rig_ids = [r.rig_id for r in rigs]

    manhours_rows, manhours_tp_rows, manhours_total = _manhours_rows(rig_ids, date_from, date_to, filter_type)

    return {
        "date_from": date_from,
        "date_to": date_to,
        "period_label": period_label,
        "report_title": resolve_report_title(params),
        "filter_type": filter_type,
        "project_label": project.prj_contract_no if project else None,
        "rig_count": len(rigs),
        "manhours": {"rows": manhours_rows, "third_party_rows": manhours_tp_rows, "total": manhours_total},
        "meetings_total": _meetings_total(rig_ids, date_from, date_to),
        "incidents": _incidents_rows(rig_ids, date_from, date_to),
        "hazard_card": _hazard_card_summary(rig_ids, date_from, date_to),
        "activities": _activities_rows(rig_ids, date_from, date_to),
        "environment": _environment_rows(rig_ids, date_from, date_to),
        "lti": _lti_rows(rigs, date_from, date_to),
        "statistics": _statistics(rig_ids, (params.get("period_type") or "").upper(), date_from, date_to, filter_type),
    }


class MisHseReviewMetaView(APIView):
    entity_key = ENTITY_KEY
    permission_classes = [HasMenuPermission]

    def get(self, request):
        categories = list(
            MstFsCategory.objects.filter(rig_type_mappings__mapping_active="Y")
            .distinct()
            .order_by("fs_category_name")
            .values("fs_category_id", "fs_category_name")
        )
        projects = list(
            ProjectContract.objects.select_related("location")
            .order_by("-prj_start_dt")
            .values("prj_contract_id", "prj_contract_no", "location__location_name", "prj_start_dt", "prj_end_dt")
        )
        # Lets the frontend hint "data exists from X to Y" next to the
        # Period fields before a user picks a year/quarter/month blind and
        # gets an empty report back — see MisHseReviewPage's period hint.
        bounds = MisMonthlyHseReturnsHdr.objects.aggregate(earliest=Min("report_month"), latest=Max("report_month"))
        return Response(
            {
                "categories": [{"id": c["fs_category_id"], "name": c["fs_category_name"]} for c in categories],
                "projects": [
                    {
                        "id": p["prj_contract_id"],
                        "name": f"{p['prj_contract_no']} — {p['location__location_name']}",
                        "start": p["prj_start_dt"],
                        "end": p["prj_end_dt"],
                    }
                    for p in projects
                ],
                "data_range": {"earliest": bounds["earliest"], "latest": bounds["latest"]},
            }
        )


class ProjectRigsView(APIView):
    """Rigs attached to a given Project Contract — populates the "Project
    Rigs" checklist once Filter Type = PROJECT and a project is picked."""

    entity_key = ENTITY_KEY
    permission_classes = [HasMenuPermission]

    def get(self, request):
        project_id = request.query_params.get("project")
        if not project_id:
            return Response({"rigs": []})
        rig_ids = ProjectContractDtl.objects.filter(contract_id=project_id).values_list("rig_id", flat=True)
        rigs = MstRig.objects.filter(rig_id__in=rig_ids).order_by("rig_name").values("rig_id", "rig_name")
        return Response({"rigs": [{"id": r["rig_id"], "name": r["rig_name"]} for r in rigs]})


class MisHseReviewView(APIView):
    entity_key = ENTITY_KEY
    permission_classes = [HasMenuPermission]

    def get(self, request):
        try:
            report = build_report(request.query_params)
        except (ValueError, KeyError, TypeError) as exc:
            return Response({"detail": str(exc) or "Invalid filters."}, status=400)
        return Response(report)


class MisHseReviewPrintView(APIView):
    entity_key = ENTITY_KEY
    permission_classes = [HasMenuPermission]

    def get(self, request):
        from .mis_hse_review_report import render_mis_hse_review_pdf

        try:
            report = build_report(request.query_params)
        except (ValueError, KeyError, TypeError) as exc:
            return Response({"detail": str(exc) or "Invalid filters."}, status=400)
        pdf_bytes = render_mis_hse_review_pdf(report)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{report["report_title"]}.pdf"'
        _audit.record_action(
            request,
            "export",
            ENTITY_KEY,
            record_label=f"{report['report_title']} PDF — {report['period_label']}",
            changes=None,
        )
        return response
