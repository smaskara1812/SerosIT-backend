"""QHSE → MIS Monthly HSE Return.

Single page: one header record (Rig/Cost Centre + Report No + Report
Month) with six tabs hanging off it — Manhours, Incidents, Meetings, Haz
ID and Prompt Cards, HSE Inspections/Drills/Audits, Environment Reporting.
Every tab except Cards (which is pure computed, no save) has its own Save,
matching legacy's per-tab update procs; the header itself has no Update at
all once created (only Add/Delete), same as legacy — Report No/Period are
locked in after Add.

Rebrand: legacy split every party-of-work column EOSIL vs OGDSL depending
on which company currently owned the rig's cost centre that month. This
build drops that split — there's one company now (SEROS) — so every
column just reads "SEROS ..." instead of resolving a company per rig/month.
Legacy data still has literal 'EOSIL'/'OGDSL' values in HazardCard's
reported_by_party column (pre-rebrand rows) — SEROS_PARTY_NAMES folds all
three into the single "SEROS" bucket for the Cards counts below.

List of vehicles is intentionally not implemented — the source spec for
this page explicitly flagged it "not to implement" (no master exists).
"""

from calendar import monthrange
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import audit as _audit
from .models import (
    HazardCard,
    Incident,
    MisMonthlyHseActivities,
    MisMonthlyHseEnvironment,
    MisMonthlyHseManhours,
    MisMonthlyHseMeetings,
    MisMonthlyHseReturnsHdr,
    MstCostCentre,
    MstHseActivity,
    MstHseConsumable,
    MstHseManhoursParty,
    MstHseMeeting,
    MstIncidentType,
    UserProfile,
)
from .permissions import HasMenuPermission

ENTITY_KEY = "qhse.mis_hse_return"
OFFICE_COST_CENTRE_TYPE_ID = 3
PAGE_SIZE = 20
SEROS_PARTY_NAMES = {"SEROS", "EOSIL", "OGDSL"}


def _current_user_id(request):
    try:
        return UserProfile.objects.get(user_login_id=request.user.username).user_id
    except UserProfile.DoesNotExist:
        return None


def _month_bounds(report_month):
    last_day = monthrange(report_month.year, report_month.month)[1]
    return report_month.replace(day=1), report_month.replace(day=last_day)


def _hdr_label(hdr):
    where = hdr.rig.rig_name if hdr.rig_id else hdr.cost_centre.cost_centre_name
    return f"{where} — {hdr.report_month:%b %Y}"


def _header_dict(hdr):
    return {
        "monthly_hse_returns_hdr_id": hdr.monthly_hse_returns_hdr_id,
        "cost_centre": hdr.cost_centre_id,
        "cost_centre_name": hdr.cost_centre.cost_centre_name if hdr.cost_centre_id else "",
        "rig": hdr.rig_id,
        "rig_name": hdr.rig.rig_name if hdr.rig_id else "",
        "report_no": hdr.report_no,
        "report_month": hdr.report_month,
    }


def _to_decimal(value):
    """Blank/None → None (an empty box), otherwise a Decimal. Raises
    InvalidOperation on anything unparsable so the caller can 400."""
    if value in (None, ""):
        return None
    return Decimal(str(value))


def _to_int(value):
    if value in (None, ""):
        return None
    return int(value)


class MisHseReturnView(APIView):
    """Search (list) + Add (create)."""

    entity_key = ENTITY_KEY
    permission_classes = [HasMenuPermission]

    def get(self, request):
        qs = MisMonthlyHseReturnsHdr.objects.select_related("rig", "cost_centre").order_by(
            "-report_month", "-monthly_hse_returns_hdr_id"
        )
        rig_id = request.query_params.get("rig")
        if rig_id:
            qs = qs.filter(rig_id=rig_id)
        search = request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(report_no__icontains=search)
                | Q(rig__rig_name__icontains=search)
                | Q(cost_centre__cost_centre_name__icontains=search)
            )
        total = qs.count()
        try:
            page = max(int(request.query_params.get("page", 1)), 1)
        except ValueError:
            page = 1
        page_size = PAGE_SIZE
        start = (page - 1) * page_size
        rows = [_header_dict(h) for h in qs[start : start + page_size]]
        return Response({"rows": rows, "count": total, "has_more": start + page_size < total})

    def post(self, request):
        data = request.data
        cost_centre_id = data.get("cost_centre")
        report_no = (data.get("report_no") or "").strip()
        report_month_raw = data.get("report_month")

        errors = {}
        if not report_no:
            errors["report_no"] = "Report No. must be entered."
        if not report_month_raw:
            errors["report_month"] = "Report Period must be entered."
        if not cost_centre_id:
            errors["cost_centre"] = "Cost Centre must be selected."
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            report_month = date.fromisoformat(f"{str(report_month_raw)[:7]}-01")
        except ValueError:
            return Response({"report_month": "Invalid period."}, status=status.HTTP_400_BAD_REQUEST)

        today = date.today()
        if report_month >= today.replace(day=1):
            return Response(
                {"report_month": "Period must be earlier than the current month."}, status=status.HTTP_400_BAD_REQUEST
            )

        # rig is left null for an Office/Base-Yard Cost Centre that isn't
        # mapped to any rig — legacy has real headers like this (e.g.
        # "Essar House - Mahalaxmi"), so this is expected, not an error.
        cost_centre = get_object_or_404(MstCostCentre, pk=cost_centre_id)
        rig = cost_centre.rig

        if MisMonthlyHseReturnsHdr.objects.filter(cost_centre=cost_centre, report_month=report_month).exists():
            return Response(
                {
                    "report_month": (
                        f"A MIS HSE Return already exists for {cost_centre.cost_centre_name} on {report_month:%b %Y}."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        uid = _current_user_id(request)
        now = timezone.now()
        hdr = MisMonthlyHseReturnsHdr.objects.create(
            cost_centre=cost_centre,
            rig=rig,
            report_no=report_no,
            report_month=report_month,
            cr_user_id=uid or 1,
            cr_dt=now,
        )
        _audit.record_action(request, "create", ENTITY_KEY, hdr.pk, _hdr_label(hdr), None)
        return Response(_header_dict(hdr), status=status.HTTP_201_CREATED)


class MisHseReturnDetailView(APIView):
    """Retrieve (loads all six tabs in one call) + Delete."""

    entity_key = ENTITY_KEY
    permission_classes = [HasMenuPermission]

    def get(self, request, pk):
        hdr = get_object_or_404(MisMonthlyHseReturnsHdr.objects.select_related("rig", "cost_centre"), pk=pk)
        month_start, month_end = _month_bounds(hdr.report_month)
        cc_type_id = hdr.cost_centre.cost_centre_type_id if hdr.cost_centre_id else None
        is_office = cc_type_id == OFFICE_COST_CENTRE_TYPE_ID

        party_qs = MstHseManhoursParty.objects.all()
        if cc_type_id:
            party_qs = party_qs.filter(Q(cost_centre_type_id=cc_type_id) | Q(cost_centre_type__isnull=True))
        saved_manhours = {m.party_id: m for m in hdr.manhours.all()}
        manhours_rows = [
            {
                "hse_manhours_party_id": party.hse_manhours_party_id,
                "party_name": party.hse_manhours_party_name,
                "party_type": party.hse_manhours_party_type,
                "no_of_personnel": saved.no_of_personnel if saved else None,
                "hours_worked": saved.hours_worked if saved else Decimal(9 if is_office else 12),
            }
            for party in party_qs.order_by("hse_manhours_party_type", "hse_manhours_party_name")
            for saved in [saved_manhours.get(party.hse_manhours_party_id)]
        ]

        incident_qs = Incident.objects.filter(
            rig_id=hdr.rig_id, incident_date__date__gte=month_start, incident_date__date__lte=month_end
        ).exclude(marked_as_deleted="Y")
        no_party = Q(incident_party__isnull=True) | Q(incident_party="") | Q(incident_party="0")
        incident_rows = [
            {
                "incident_type_id": itype.incident_type_id,
                "incident_type": itype.incident_type,
                "seros_total_incidents": incident_qs.filter(incident_type=itype).exclude(no_party).count(),
                "contractor_total_incidents": incident_qs.filter(incident_type=itype).filter(no_party).count(),
            }
            for itype in MstIncidentType.objects.filter(show_on_mis_hse_report="Y").order_by("incident_type")
        ]

        saved_meetings = {m.meeting_id: m for m in hdr.meetings.all()}
        meeting_rows = [
            {
                "hse_meeting_id": meeting.hse_meeting_id,
                "meeting_type": meeting.hse_meeting_type,
                "total_meetings": saved.total_meetings if saved else None,
                "total_seros_employees": saved.total_seros_employees if saved else None,
                "total_contractors": saved.total_contractors if saved else None,
            }
            for meeting in MstHseMeeting.objects.order_by("hse_meeting_type")
            for saved in [saved_meetings.get(meeting.hse_meeting_id)]
        ]

        card_qs = HazardCard.objects.filter(
            rig_id=hdr.rig_id, event_dt__date__gte=month_start, event_dt__date__lte=month_end
        ).exclude(marked_as_deleted="Y")
        cards = {
            "seros_open_cards": card_qs.filter(reported_by_party__in=SEROS_PARTY_NAMES, haz_id_card_status="O").count(),
            "seros_closed_cards": card_qs.filter(reported_by_party__in=SEROS_PARTY_NAMES, haz_id_card_status="C").count(),
            "others_open_cards": card_qs.exclude(reported_by_party__in=SEROS_PARTY_NAMES)
            .filter(haz_id_card_status="O")
            .count(),
            "others_closed_cards": card_qs.exclude(reported_by_party__in=SEROS_PARTY_NAMES)
            .filter(haz_id_card_status="C")
            .count(),
        }

        saved_activities = {a.activity_id: a for a in hdr.hse_activities.all()}
        activity_rows = [
            {
                "hse_activity_id": activity.hse_activity_id,
                "activity_name": activity.hse_activity_name,
                "activity_type": activity.hse_activity_type,
                "activity_type_display": activity.get_hse_activity_type_display(),
                "total_activities": saved.total_activities if saved else None,
                "seros_emp_count": saved.seros_emp_count if saved else None,
                "contractor_count": saved.contractor_count if saved else None,
            }
            for activity in MstHseActivity.objects.order_by("hse_activity_name")
            for saved in [saved_activities.get(activity.hse_activity_id)]
        ]

        saved_env = {e.consumable_id: e for e in hdr.environment_rows.all()}
        environment_rows = [
            {
                "hse_consumable_id": consumable.hse_consumable_id,
                "consumable_name": consumable.hse_consumable_name,
                "unit": consumable.hse_consumption_unit,
                "total_quantity": saved.total_quantity if saved else None,
                "remarks": saved.remarks if saved else "",
            }
            for consumable in MstHseConsumable.objects.order_by("hse_consumable_id")
            for saved in [saved_env.get(consumable.hse_consumable_id)]
        ]

        return Response(
            {
                "header": _header_dict(hdr),
                "lti_free_days": hdr.lti_free_days,
                "manhours": manhours_rows,
                "incidents": incident_rows,
                "meetings": meeting_rows,
                "cards": cards,
                "activities": activity_rows,
                "environment": environment_rows,
            }
        )

    def delete(self, request, pk):
        hdr = get_object_or_404(MisMonthlyHseReturnsHdr, pk=pk)
        label = _hdr_label(hdr)
        hdr.delete()
        _audit.record_action(request, "delete", ENTITY_KEY, pk, label, None)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MisHseReturnManhoursView(APIView):
    entity_key = ENTITY_KEY
    permission_classes = [HasMenuPermission]

    def put(self, request, pk):
        hdr = get_object_or_404(MisMonthlyHseReturnsHdr, pk=pk)
        uid = _current_user_id(request)
        now = timezone.now()
        try:
            for row in request.data.get("rows", []):
                party_id = row.get("hse_manhours_party_id")
                if not party_id:
                    continue
                no_of_personnel = _to_int(row.get("no_of_personnel"))
                hours_worked = _to_decimal(row.get("hours_worked"))
                obj = MisMonthlyHseManhours.objects.filter(hdr=hdr, party_id=party_id).first()
                if obj:
                    obj.no_of_personnel = no_of_personnel
                    obj.hours_worked = hours_worked
                    obj.mod_user_id = uid
                    obj.mod_dt = now
                    obj.save()
                else:
                    MisMonthlyHseManhours.objects.create(
                        hdr=hdr,
                        party_id=party_id,
                        no_of_personnel=no_of_personnel,
                        hours_worked=hours_worked,
                        cr_user_id=uid or 1,
                        cr_dt=now,
                    )
        except (InvalidOperation, ValueError, TypeError):
            return Response({"detail": "Invalid number in Manhours grid."}, status=status.HTTP_400_BAD_REQUEST)
        _audit.record_action(request, "update", ENTITY_KEY, hdr.pk, f"{_hdr_label(hdr)} — Manhours", None)
        return Response({"saved": True})


class MisHseReturnIncidentsView(APIView):
    """LTI Free Days is the only editable field on this tab — every other
    row is a live computed count, never persisted (see MisHseReturnDetailView)."""

    entity_key = ENTITY_KEY
    permission_classes = [HasMenuPermission]

    def put(self, request, pk):
        hdr = get_object_or_404(MisMonthlyHseReturnsHdr, pk=pk)
        try:
            hdr.lti_free_days = _to_int(request.data.get("lti_free_days"))
        except (ValueError, TypeError):
            return Response({"detail": "Invalid LTI Free Days."}, status=status.HTTP_400_BAD_REQUEST)
        hdr.mod_user_id = _current_user_id(request)
        hdr.mod_dt = timezone.now()
        hdr.save(update_fields=["lti_free_days", "mod_user_id", "mod_dt"])
        _audit.record_action(request, "update", ENTITY_KEY, hdr.pk, f"{_hdr_label(hdr)} — Incidents", None)
        return Response({"saved": True, "lti_free_days": hdr.lti_free_days})


class MisHseReturnMeetingsView(APIView):
    entity_key = ENTITY_KEY
    permission_classes = [HasMenuPermission]

    def put(self, request, pk):
        hdr = get_object_or_404(MisMonthlyHseReturnsHdr, pk=pk)
        uid = _current_user_id(request)
        now = timezone.now()
        try:
            for row in request.data.get("rows", []):
                meeting_id = row.get("hse_meeting_id")
                if not meeting_id:
                    continue
                values = {
                    "total_meetings": _to_int(row.get("total_meetings")),
                    "total_seros_employees": _to_int(row.get("total_seros_employees")),
                    "total_contractors": _to_int(row.get("total_contractors")),
                }
                obj = MisMonthlyHseMeetings.objects.filter(hdr=hdr, meeting_id=meeting_id).first()
                if obj:
                    for k, v in values.items():
                        setattr(obj, k, v)
                    obj.mod_user_id = uid
                    obj.mod_dt = now
                    obj.save()
                else:
                    MisMonthlyHseMeetings.objects.create(hdr=hdr, meeting_id=meeting_id, cr_user_id=uid or 1, cr_dt=now, **values)
        except (ValueError, TypeError):
            return Response({"detail": "Invalid number in Meetings grid."}, status=status.HTTP_400_BAD_REQUEST)
        _audit.record_action(request, "update", ENTITY_KEY, hdr.pk, f"{_hdr_label(hdr)} — Meetings", None)
        return Response({"saved": True})


class MisHseReturnActivitiesView(APIView):
    entity_key = ENTITY_KEY
    permission_classes = [HasMenuPermission]

    def put(self, request, pk):
        hdr = get_object_or_404(MisMonthlyHseReturnsHdr, pk=pk)
        uid = _current_user_id(request)
        now = timezone.now()
        try:
            for row in request.data.get("rows", []):
                activity_id = row.get("hse_activity_id")
                if not activity_id:
                    continue
                values = {
                    "total_activities": _to_int(row.get("total_activities")),
                    "seros_emp_count": _to_int(row.get("seros_emp_count")),
                    "contractor_count": _to_int(row.get("contractor_count")),
                }
                obj = MisMonthlyHseActivities.objects.filter(hdr=hdr, activity_id=activity_id).first()
                if obj:
                    for k, v in values.items():
                        setattr(obj, k, v)
                    obj.mod_user_id = uid
                    obj.mod_dt = now
                    obj.save()
                else:
                    MisMonthlyHseActivities.objects.create(
                        hdr=hdr, activity_id=activity_id, cr_user_id=uid or 1, cr_dt=now, **values
                    )
        except (ValueError, TypeError):
            return Response({"detail": "Invalid number in Activities grid."}, status=status.HTTP_400_BAD_REQUEST)
        _audit.record_action(request, "update", ENTITY_KEY, hdr.pk, f"{_hdr_label(hdr)} — Activities", None)
        return Response({"saved": True})


class MisHseReturnEnvironmentView(APIView):
    entity_key = ENTITY_KEY
    permission_classes = [HasMenuPermission]

    def put(self, request, pk):
        hdr = get_object_or_404(MisMonthlyHseReturnsHdr, pk=pk)
        uid = _current_user_id(request)
        now = timezone.now()
        try:
            for row in request.data.get("rows", []):
                consumable_id = row.get("hse_consumable_id")
                if not consumable_id:
                    continue
                total_quantity = _to_decimal(row.get("total_quantity"))
                remarks = row.get("remarks") or ""
                obj = MisMonthlyHseEnvironment.objects.filter(hdr=hdr, consumable_id=consumable_id).first()
                if obj:
                    obj.total_quantity = total_quantity
                    obj.remarks = remarks
                    obj.mod_user_id = uid
                    obj.mod_dt = now
                    obj.save()
                else:
                    MisMonthlyHseEnvironment.objects.create(
                        hdr=hdr,
                        consumable_id=consumable_id,
                        total_quantity=total_quantity,
                        remarks=remarks,
                        cr_user_id=uid or 1,
                        cr_dt=now,
                    )
        except (InvalidOperation, ValueError, TypeError):
            return Response({"detail": "Invalid number in Environment Reporting grid."}, status=status.HTTP_400_BAD_REQUEST)
        _audit.record_action(request, "update", ENTITY_KEY, hdr.pk, f"{_hdr_label(hdr)} — Environment Reporting", None)
        return Response({"saved": True})
