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


def _log_row_created(request, section, hdr, row):
    """A line of a section was added: logged as that row's own entry with its values."""
    _audit.record_action(
        request, "create", ENTITY_KEY, row.pk, f"{_hdr_label(hdr)} — {section}",
        {k: {"old": None, "new": v} for k, v in _audit.snapshot(row).items() if v not in (None, "")}, target=row,
    )


def _log_row_changed(request, section, hdr, row, before):
    """A line of a section was changed: logged as that row's own entry with what changed."""
    after = _audit.snapshot(row)
    changes = {k: {"old": before.get(k), "new": v} for k, v in after.items() if before.get(k) != v}
    if changes:
        _audit.record_action(request, "update", ENTITY_KEY, row.pk, f"{_hdr_label(hdr)} — {section}", changes, target=row)


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


# ── validation of the tab grids ──────────────────────────────────────────
# Mirrors frontend/src/lib/misHseChecks.js. A row you start must be complete;
# a row left entirely blank is ignored (legacy returns only hold the rows that
# were filled in).
INT_MAX = 2147483647
_WHOLE = "must be a whole number, 0 or more."


def _blank(v):
    return v is None or (isinstance(v, str) and not v.strip())


def _whole(v, label, errors, field):
    """Whole number 0..INT_MAX, or None (and an entry in errors)."""
    if _blank(v):
        errors[field] = f"Enter {label}."
        return None
    try:
        d = Decimal(str(v).strip())
    except InvalidOperation:
        d = None
    if d is None or not d.is_finite() or d != d.to_integral_value() or d < 0:
        errors[field] = f"{label} {_WHOLE}"
        return None
    if d > INT_MAX:
        errors[field] = f"{label} is too large."
        return None
    return int(d)


def _amount(v, label, errors, field, max_value):
    """Number 0..max_value with at most 2 decimals, or None (and an entry in errors)."""
    if _blank(v):
        errors[field] = f"Enter {label}."
        return None
    try:
        d = Decimal(str(v).strip())
    except InvalidOperation:
        d = None
    if d is None or not d.is_finite() or d < 0:
        errors[field] = f"{label} must be a number, 0 or more."
        return None
    if d != d.quantize(Decimal("0.01")):
        errors[field] = f"{label} can have at most 2 decimal places."
        return None
    if d > max_value:
        errors[field] = f"{label} is too large."
        return None
    return d


def _grid_response(row_errors, names):
    lines = []
    for rid, errs in row_errors.items():
        lines.extend(f"{names.get(rid, 'Row')}: {msg}" for msg in errs.values())
    return Response({"detail": "\n".join(lines), "row_errors": row_errors}, status=status.HTTP_400_BAD_REQUEST)


def check_manhours(rows):
    clean, errors = [], {}
    for row in rows:
        rid = row.get("hse_manhours_party_id")
        if not rid:
            continue
        e = {}
        personnel = None if _blank(row.get("no_of_personnel")) else _whole(row.get("no_of_personnel"), "No. of Personnel", e, "no_of_personnel")
        hours = _amount(row.get("hours_worked"), "Hours Worked", e, "hours_worked", Decimal("99.99"))
        if e:
            errors[rid] = e
        else:
            clean.append((rid, personnel, hours))
    return clean, errors


def check_meetings(rows):
    clean, errors = [], {}
    keys = ("total_meetings", "total_seros_employees", "total_contractors")
    for row in rows:
        rid = row.get("hse_meeting_id")
        if not rid:
            continue
        if all(_blank(row.get(k)) for k in keys):
            continue
        e = {}
        meetings = _whole(row.get("total_meetings"), "Total Meetings", e, "total_meetings")
        staff = _whole(row.get("total_seros_employees"), "Total SEROS Employees", e, "total_seros_employees")
        contractors = _whole(row.get("total_contractors"), "Total Contractors", e, "total_contractors")
        if not e:
            if meetings == 0 and (staff or contractors):
                msg = "must be 0 when there are no meetings."
                if staff:
                    e["total_seros_employees"] = f"Total SEROS Employees {msg}"
                if contractors:
                    e["total_contractors"] = f"Total Contractors {msg}"
            elif meetings and not (staff or contractors):
                e["total_seros_employees"] = "Enter the employees or contractors who attended (at least one is above 0)."
                e["total_contractors"] = e["total_seros_employees"]
        if e:
            errors[rid] = e
        else:
            clean.append((rid, meetings, staff, contractors))
    return clean, errors


def check_activities(rows):
    clean, errors = [], {}
    keys = ("total_activities", "seros_emp_count", "contractor_count")
    for row in rows:
        rid = row.get("hse_activity_id")
        if not rid:
            continue
        if all(_blank(row.get(k)) for k in keys):
            continue
        e = {}
        total = _whole(row.get("total_activities"), "Total Activities", e, "total_activities")
        staff = _whole(row.get("seros_emp_count"), "SEROS Employees", e, "seros_emp_count")
        contractors = _whole(row.get("contractor_count"), "Contractors", e, "contractor_count")
        if e:
            errors[rid] = e
        else:
            clean.append((rid, total, staff, contractors))
    return clean, errors


def check_environment(rows):
    clean, errors = [], {}
    for row in rows:
        rid = row.get("hse_consumable_id")
        if not rid:
            continue
        remarks = (row.get("remarks") or "").strip()
        if _blank(row.get("total_quantity")) and not remarks:
            continue
        e = {}
        qty = _amount(row.get("total_quantity"), "Total Quantity", e, "total_quantity", Decimal("99999999.99"))
        if len(remarks) > 200:
            e["remarks"] = "Remarks can be at most 200 characters."
        if e:
            errors[rid] = e
        else:
            clean.append((rid, qty, remarks))
    return clean, errors


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

        if rig and MisMonthlyHseReturnsHdr.objects.filter(rig=rig, report_month=report_month).exists():
            return Response(
                {"report_month": f"{rig.rig_name} already has a MIS HSE Return for {report_month:%b %Y}."},
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
        _audit.record_action(
            request, "create", ENTITY_KEY, hdr.pk, _hdr_label(hdr),
            {k: {"old": None, "new": v} for k, v in _audit.snapshot(hdr).items() if v not in (None, "")}, target=hdr,
        )
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
        pre = _audit.before_delete(hdr)  # the return and its four sets of lines, for the audit trail
        hdr.delete()
        _audit.log_deleted(request, ENTITY_KEY, label, pre)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MisHseReturnManhoursView(APIView):
    entity_key = ENTITY_KEY
    permission_classes = [HasMenuPermission]

    def put(self, request, pk):
        hdr = get_object_or_404(MisMonthlyHseReturnsHdr, pk=pk)
        rows = request.data.get("rows", [])
        clean, errors = check_manhours(rows)
        if errors:
            names = dict(MstHseManhoursParty.objects.filter(pk__in=errors).values_list("pk", "hse_manhours_party_name"))
            return _grid_response(errors, names)
        uid = _current_user_id(request)
        now = timezone.now()
        for party_id, no_of_personnel, hours_worked in clean:
            obj = MisMonthlyHseManhours.objects.filter(hdr=hdr, party_id=party_id).first()
            if obj:
                before = _audit.snapshot(obj)
                obj.no_of_personnel = no_of_personnel
                obj.hours_worked = hours_worked
                obj.mod_user_id = uid
                obj.mod_dt = now
                obj.save()
                _log_row_changed(request, "Manhours", hdr, obj, before)
            else:
                obj = MisMonthlyHseManhours.objects.create(
                    hdr=hdr, party_id=party_id, no_of_personnel=no_of_personnel, hours_worked=hours_worked, cr_user_id=uid or 1, cr_dt=now
                )
                _log_row_created(request, "Manhours", hdr, obj)
        return Response({"saved": True})


class MisHseReturnIncidentsView(APIView):
    """LTI Free Days is the only editable field on this tab — every other
    row is a live computed count, never persisted (see MisHseReturnDetailView)."""

    entity_key = ENTITY_KEY
    permission_classes = [HasMenuPermission]

    def put(self, request, pk):
        hdr = get_object_or_404(MisMonthlyHseReturnsHdr, pk=pk)
        e = {}
        days = _whole(request.data.get("lti_free_days"), "LTI Free Days", e, "lti_free_days")
        if e:
            return Response(e, status=status.HTTP_400_BAD_REQUEST)
        before = _audit.snapshot(hdr)
        hdr.lti_free_days = days
        hdr.mod_user_id = _current_user_id(request)
        hdr.mod_dt = timezone.now()
        hdr.save(update_fields=["lti_free_days", "mod_user_id", "mod_dt"])
        after = _audit.snapshot(hdr)
        changes = {k: {"old": before.get(k), "new": v} for k, v in after.items() if before.get(k) != v}
        _audit.record_action(
            request, "update", ENTITY_KEY, hdr.pk, f"{_hdr_label(hdr)} — Incidents", changes or None, target=hdr
        )
        return Response({"saved": True, "lti_free_days": hdr.lti_free_days})


class MisHseReturnMeetingsView(APIView):
    entity_key = ENTITY_KEY
    permission_classes = [HasMenuPermission]

    def put(self, request, pk):
        hdr = get_object_or_404(MisMonthlyHseReturnsHdr, pk=pk)
        clean, errors = check_meetings(request.data.get("rows", []))
        if errors:
            names = dict(MstHseMeeting.objects.filter(pk__in=errors).values_list("pk", "hse_meeting_type"))
            return _grid_response(errors, names)
        uid = _current_user_id(request)
        now = timezone.now()
        for meeting_id, meetings, staff, contractors in clean:
            values = {"total_meetings": meetings, "total_seros_employees": staff, "total_contractors": contractors}
            obj = MisMonthlyHseMeetings.objects.filter(hdr=hdr, meeting_id=meeting_id).first()
            if obj:
                before = _audit.snapshot(obj)
                for k, v in values.items():
                    setattr(obj, k, v)
                obj.mod_user_id = uid
                obj.mod_dt = now
                obj.save()
                _log_row_changed(request, "Meetings", hdr, obj, before)
            else:
                obj = MisMonthlyHseMeetings.objects.create(hdr=hdr, meeting_id=meeting_id, cr_user_id=uid or 1, cr_dt=now, **values)
                _log_row_created(request, "Meetings", hdr, obj)
        return Response({"saved": True})


class MisHseReturnActivitiesView(APIView):
    entity_key = ENTITY_KEY
    permission_classes = [HasMenuPermission]

    def put(self, request, pk):
        hdr = get_object_or_404(MisMonthlyHseReturnsHdr, pk=pk)
        clean, errors = check_activities(request.data.get("rows", []))
        if errors:
            names = dict(MstHseActivity.objects.filter(pk__in=errors).values_list("pk", "hse_activity_name"))
            return _grid_response(errors, names)
        uid = _current_user_id(request)
        now = timezone.now()
        for activity_id, total, staff, contractors in clean:
            values = {"total_activities": total, "seros_emp_count": staff, "contractor_count": contractors}
            obj = MisMonthlyHseActivities.objects.filter(hdr=hdr, activity_id=activity_id).first()
            if obj:
                before = _audit.snapshot(obj)
                for k, v in values.items():
                    setattr(obj, k, v)
                obj.mod_user_id = uid
                obj.mod_dt = now
                obj.save()
                _log_row_changed(request, "Activities", hdr, obj, before)
            else:
                obj = MisMonthlyHseActivities.objects.create(hdr=hdr, activity_id=activity_id, cr_user_id=uid or 1, cr_dt=now, **values)
                _log_row_created(request, "Activities", hdr, obj)
        return Response({"saved": True})


class MisHseReturnEnvironmentView(APIView):
    entity_key = ENTITY_KEY
    permission_classes = [HasMenuPermission]

    def put(self, request, pk):
        hdr = get_object_or_404(MisMonthlyHseReturnsHdr, pk=pk)
        clean, errors = check_environment(request.data.get("rows", []))
        if errors:
            names = dict(MstHseConsumable.objects.filter(pk__in=errors).values_list("pk", "hse_consumable_name"))
            return _grid_response(errors, names)
        uid = _current_user_id(request)
        now = timezone.now()
        for consumable_id, total_quantity, remarks in clean:
            obj = MisMonthlyHseEnvironment.objects.filter(hdr=hdr, consumable_id=consumable_id).first()
            if obj:
                before = _audit.snapshot(obj)
                obj.total_quantity = total_quantity
                obj.remarks = remarks
                obj.mod_user_id = uid
                obj.mod_dt = now
                obj.save()
                _log_row_changed(request, "Environment Reporting", hdr, obj, before)
            else:
                obj = MisMonthlyHseEnvironment.objects.create(
                    hdr=hdr, consumable_id=consumable_id, total_quantity=total_quantity, remarks=remarks, cr_user_id=uid or 1, cr_dt=now
                )
                _log_row_created(request, "Environment Reporting", hdr, obj)
        return Response({"saved": True})
