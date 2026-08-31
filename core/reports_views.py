import csv
import datetime

from django.db.models import F, Func, IntegerField, Prefetch
from django.db.models.functions import Coalesce, ExtractYear, Now
from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from . import audit as _audit
from .models import HazardCard, Incident, ItAssetHolder, MstItAsset
from .permissions import HasMenuPermission
from .reports_serializers import (
    SEVERITY_LABELS,
    HazardCardSerializer,
    IncidentSerializer,
    ItAssetReportSerializer,
)


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


class ItAssetReportViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only 'Asset Information' report — legacy's Print/Select-report
    screen (Asset Report / Asset Tech Dtls are the same underlying rows,
    the frontend just switches columns). GET supports ?holder_company=,
    ?location=, ?purchase_date_from=/?purchase_date_to= (YYYY-MM-DD), ?active=(Y|N), ?search=
    (sr no/tag/SAP code) and ?ordering=sr_no (prefix '-' to reverse).
    ?it_asset_type=, ?it_asset_mfg=, ?it_asset_model= and ?vendor= each
    accept a comma-separated list of ids for multi-select filtering."""

    queryset = MstItAsset.objects.select_related(
        "it_asset_type", "it_asset_subtype", "it_asset_mfg", "it_asset_model", "own_company", "vendor"
    ).prefetch_related(
        Prefetch(
            "holders",
            queryset=ItAssetHolder.objects.filter(it_asset_holder_to__isnull=True)
            .select_related("emp", "holder_user", "holder_company", "company_loc")
            .order_by("-it_asset_holder_from"),
            to_attr="current_holders",
        )
    )
    serializer_class = ItAssetReportSerializer
    entity_key = "reports.it_assets"
    permission_classes = [HasMenuPermission]
    search_fields = ["it_asset_sr_no", "it_asset_tag", "it_asset_sap_code"]

    def get_queryset(self):
        qs = self.queryset
        params = self.request.query_params

        holder_company = params.get("holder_company")
        if holder_company:
            qs = qs.filter(holders__holder_company_id=holder_company, holders__it_asset_holder_to__isnull=True)
        location = params.get("location")
        if location:
            qs = qs.filter(holders__company_loc_id=location, holders__it_asset_holder_to__isnull=True)
        it_asset_type = params.get("it_asset_type")
        if it_asset_type:
            qs = qs.filter(it_asset_type_id__in=it_asset_type.split(","))
        it_asset_mfg = params.get("it_asset_mfg")
        if it_asset_mfg:
            qs = qs.filter(it_asset_mfg_id__in=it_asset_mfg.split(","))
        it_asset_model = params.get("it_asset_model")
        if it_asset_model:
            qs = qs.filter(it_asset_model_id__in=it_asset_model.split(","))
        vendor = params.get("vendor")
        if vendor:
            qs = qs.filter(vendor_id__in=vendor.split(","))
        purchase_date_from = params.get("purchase_date_from")
        if purchase_date_from:
            qs = qs.filter(it_asset_pur_dt__gte=purchase_date_from)
        purchase_date_to = params.get("purchase_date_to")
        if purchase_date_to:
            qs = qs.filter(it_asset_pur_dt__lte=purchase_date_to)
        active = params.get("active")
        if active in ("Y", "N"):
            qs = qs.filter(it_asset_active=active)
        if holder_company or location:
            qs = qs.distinct()

        ordering = params.get("ordering", "sr_no")
        reverse = ordering.startswith("-")
        field = "it_asset_sr_no"
        qs = qs.order_by(f"-{field}" if reverse else field)
        return qs

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        qs = self.get_queryset()
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="it_assets_report.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "Asset Type", "Serial No", "Asset Tag", "SAP Code", "Make", "Model", "Subtype", "RAM", "HDD",
                "Specifications", "Product No", "MAC Address", "Owned By", "Holding Company", "Employee/Holder",
                "Location", "Holder Remark", "Vendor", "Purchase Date", "Warranty Date", "Active",
            ]
        )
        row_count = 0
        for r in qs.iterator(chunk_size=200):
            row_count += 1
            ser = self.serializer_class(r)
            d = ser.data
            writer.writerow(
                [
                    d["it_asset_type_name"], d["it_asset_sr_no"], d["it_asset_tag"] or "",
                    d["it_asset_sap_code"] or "", d["it_asset_mfg_name"], d["it_asset_model_name"],
                    d["it_asset_subtype_name"], d["it_asset_ram"] or "", d["it_asset_hdd"] or "",
                    d["it_asset_particulars"] or "", d["it_asset_product_no"] or "", d["it_asset_mac_addr"] or "",
                    d["own_company_abrv"], d["holding_company_abrv"], d["holder_name"], d["location_name"],
                    d["holder_remark"], d["vendor_name"], d["it_asset_pur_dt"] or "",
                    d["it_asset_warranty_upto"] or "", d["it_asset_active"],
                ]
            )
        _audit_export(request, self.entity_key, "IT Assets report export", row_count)
        return response
