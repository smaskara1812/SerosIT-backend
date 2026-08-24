import csv
import datetime

from django.db.models import F, Func, IntegerField
from django.db.models.functions import Coalesce, ExtractYear, Now
from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from . import audit as _audit
from .models import HazardCard, Incident
from .permissions import HasMenuPermission
from .reports_serializers import SEVERITY_LABELS, HazardCardSerializer, IncidentSerializer


def _audit_export(request, entity_key, label, row_count):
    """Every export is logged with the filters that produced it — reuses
    the audit trail's before/after diff table (there's no "before" for an
    export, so it's left blank) rather than adding a separate changes
    shape just for this one action."""
    changes = {
        k: {"old": None, "new": v}
        for k, v in request.query_params.items()
        if v not in (None, "")
    }
    changes["rows_exported"] = {"old": None, "new": row_count}
    _audit.record_action(request, "export", entity_key, record_label=label, changes=changes)

INCIDENT_ORDERING_FIELDS = {
    "date": "incident_date",
    "severity": "incident_severity",
    "npt_hours": "npt_hrs_loss",
    "financial_loss": "financial_loss_amt",
}


class IncidentViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only Incidents report — first of the operational listing pages
    (migrated from serosIS's chatbot listing) ported into the real app.
    GET supports ?rig=&year=&severity=&person_injured=&incident_type=&search=
    plus ?ordering= (one of date/severity/npt_hours/financial_loss, prefix
    with '-' to reverse; defaults to '-date')."""

    queryset = Incident.objects.select_related(
        "rig", "incident_type", "immediate_incident_cause", "work_location"
    ).exclude(marked_as_deleted="Y")
    serializer_class = IncidentSerializer
    entity_key = "reports.incidents"
    permission_classes = [HasMenuPermission]
    search_fields = [
        "incident_descr",
        "corrective_action",
        "preventive_action",
        "comments",
        "emp_name",
    ]

    def get_queryset(self):
        qs = self.queryset
        params = self.request.query_params

        rig_id = params.get("rig")
        if rig_id:
            qs = qs.filter(rig_id=rig_id)
        year = params.get("year")
        if year:
            qs = qs.filter(incident_date__year=year)
        severity = params.get("severity")
        if severity in ("H", "M", "L"):
            qs = qs.filter(incident_severity=severity)
        person_injured = params.get("person_injured")
        if person_injured in ("Y", "N"):
            qs = qs.filter(person_injured=person_injured)
        incident_type = params.get("incident_type")
        if incident_type:
            qs = qs.filter(incident_type_id=incident_type)

        ordering = params.get("ordering", "-date")
        reverse = ordering.startswith("-")
        field = INCIDENT_ORDERING_FIELDS.get(ordering.lstrip("-"))
        if field:
            qs = qs.order_by(f"-{field}" if reverse else field)
        else:
            qs = qs.order_by("-incident_date")
        return qs

    @action(detail=False, methods=["get"], url_path="meta")
    def meta(self, request):
        years = list(
            self.queryset.annotate(yr=ExtractYear("incident_date"))
            .values_list("yr", flat=True)
            .distinct()
            .order_by("-yr")
        )
        incident_types = list(
            self.queryset.exclude(incident_type__isnull=True)
            .values("incident_type_id", "incident_type__incident_type")
            .distinct()
            .order_by("incident_type__incident_type")
        )
        return Response(
            {
                "years": years,
                "incident_types": [
                    {"id": t["incident_type_id"], "name": t["incident_type__incident_type"]}
                    for t in incident_types
                ],
            }
        )

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        qs = self.get_queryset()
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="incidents.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "Incident No", "Date", "Rig", "Severity", "Type", "Injured",
                "NPT Hrs", "Manhours Loss", "Financial Loss", "Summary",
                "Immediate Cause", "Corrective Action", "Preventive Action",
                "Comments", "Employee", "Rank", "Work Location",
                "Drilling Superintendent", "Safety Officer", "Reported By",
            ]
        )
        row_count = 0
        for i in qs.iterator():
            row_count += 1
            writer.writerow(
                [
                    i.incident_no,
                    i.incident_date.date().isoformat(),
                    i.rig.rig_name if i.rig_id else "Unknown",
                    SEVERITY_LABELS.get(i.incident_severity, "Unknown"),
                    i.incident_type.incident_type if i.incident_type_id else "",
                    "Yes" if i.person_injured == "Y" else "No",
                    i.npt_hrs_loss or 0,
                    i.manhours_loss or 0,
                    i.financial_loss_amt if i.financial_loss_amt is not None else "",
                    i.incident_descr,
                    i.immediate_incident_cause.incident_cause_desc if i.immediate_incident_cause_id else "",
                    i.corrective_action or "",
                    i.preventive_action or "",
                    i.comments or "",
                    i.emp_name or "",
                    i.rank_name or "",
                    i.work_location.work_location if i.work_location_id else "",
                    i.drilling_superintendent or "",
                    i.safety_officer or "",
                    i.reported_by or "",
                ]
            )
        _audit_export(request, self.entity_key, "Incidents export", row_count)
        return response


class HazardCardViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only Hazard Cards report — mirrors serosIS's chatbot listing
    (get_hazard_card_listing). GET supports
    ?rig=&year=&hazard_type=&status=(open|closed)&tfs=&work_location=&search=
    plus ?ordering= (one of date/status/age, prefix with '-' to reverse;
    defaults to '-date')."""

    queryset = HazardCard.objects.select_related(
        "rig", "haz_type", "work_location", "resp_dept", "resp_rank"
    ).exclude(marked_as_deleted="Y")
    serializer_class = HazardCardSerializer
    entity_key = "reports.hazard_cards"
    permission_classes = [HasMenuPermission]
    search_fields = ["hazard_desc", "action_taken", "reported_by_name"]

    def get_queryset(self):
        qs = self.queryset
        params = self.request.query_params

        rig_id = params.get("rig")
        if rig_id:
            qs = qs.filter(rig_id=rig_id)
        year = params.get("year")
        if year:
            qs = qs.filter(event_dt__year=year)
        hazard_type = params.get("hazard_type")
        if hazard_type:
            qs = qs.filter(haz_type_id=hazard_type)
        status = params.get("status")
        if status == "open":
            qs = qs.exclude(haz_id_card_status="C")
        elif status == "closed":
            qs = qs.filter(haz_id_card_status="C")
        tfs = params.get("tfs")
        if tfs in ("Y", "N"):
            qs = qs.filter(timeout_for_safety=tfs)
        work_location = params.get("work_location")
        if work_location:
            qs = qs.filter(work_location_id=work_location)

        ordering = params.get("ordering", "-date")
        reverse = ordering.startswith("-")
        key = ordering.lstrip("-")
        if key == "date":
            qs = qs.order_by("-event_dt" if reverse else "event_dt")
        elif key == "status":
            qs = qs.order_by("-haz_id_card_status" if reverse else "haz_id_card_status")
        elif key == "age":
            qs = qs.annotate(
                age=Func(
                    Coalesce("close_out_dt", Now()),
                    F("event_dt"),
                    function="DATEDIFF",
                    output_field=IntegerField(),
                )
            )
            qs = qs.order_by("-age" if reverse else "age")
        else:
            qs = qs.order_by("-event_dt")
        return qs

    @action(detail=False, methods=["get"], url_path="meta")
    def meta(self, request):
        years = list(
            self.queryset.annotate(yr=ExtractYear("event_dt"))
            .values_list("yr", flat=True)
            .distinct()
            .order_by("-yr")
        )
        hazard_types = list(
            self.queryset.exclude(haz_type__isnull=True)
            .values("haz_type_id", "haz_type__haz_type_name")
            .distinct()
            .order_by("haz_type__haz_type_name")
        )
        work_locations = list(
            self.queryset.exclude(work_location__isnull=True)
            .values("work_location_id", "work_location__work_location")
            .distinct()
            .order_by("work_location__work_location")
        )
        return Response(
            {
                "years": years,
                "hazard_types": [
                    {"id": t["haz_type_id"], "name": t["haz_type__haz_type_name"]} for t in hazard_types
                ],
                "work_locations": [
                    {"id": w["work_location_id"], "name": w["work_location__work_location"]}
                    for w in work_locations
                ],
            }
        )

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        qs = self.get_queryset()
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="hazard_cards.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "Card No", "Date", "Rig", "Type", "Location", "Status", "TFS",
                "Description", "Action Taken", "Responsible Dept", "Responsible Rank",
                "Reported By", "Close Out Date", "Age (days)",
            ]
        )
        row_count = 0
        for h in qs.iterator():
            row_count += 1
            close_out = h.close_out_dt.date().isoformat() if h.close_out_dt else ""
            end = h.close_out_dt.date() if h.close_out_dt else datetime.date.today()
            writer.writerow(
                [
                    h.haz_id_card_no,
                    h.event_dt.date().isoformat(),
                    h.rig.rig_name if h.rig_id else "Unknown",
                    h.haz_type.haz_type_name if h.haz_type_id else "",
                    h.work_location.work_location if h.work_location_id else "",
                    "Closed" if h.haz_id_card_status == "C" else "Open",
                    "Yes" if h.timeout_for_safety == "Y" else "No",
                    h.hazard_desc,
                    h.action_taken or "",
                    h.resp_dept.dept_dispname if h.resp_dept_id else "",
                    h.resp_rank.rank_name if h.resp_rank_id else "",
                    h.reported_by_name or "",
                    close_out,
                    (end - h.event_dt.date()).days,
                ]
            )
        _audit_export(request, self.entity_key, "Hazard Cards export", row_count)
        return response
