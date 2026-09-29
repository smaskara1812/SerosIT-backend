"""QHSE → Incident Details — the Add/Update workflow for the Incident
table (already fully migrated as a straight copy of legacy
eos_Incident_Details; see models.Incident's own docstring). Distinct from
reports_views.IncidentViewSet, which is a read-only report/listing over
the same table.

Two pieces of real business logic live here, both verified against the
legacy frmIncident_Details.aspx(.cs) rather than guessed:
  - Incident No. resets per Financial Year (MAX+1 scoped to whichever FY
    incident_date falls in) — confirmed with the user directly, since the
    legacy form's own auto-numbering code was commented out/moved into a
    stored procedure this app doesn't have.
  - Contractor is required exactly when `third_party` (the Injury
    section's own "Belongs To" dropdown, legacy control ddlThird_Party —
    NOT the top-level "Incident Belongs To" / `incident_party`) is "0"
    (TP Contractors) or "1" (Operator Contractors) — verified from
    InsertUpdateData's own literal condition, which checks ddlThird_Party
    only, not ddlIncident_Party.
"""

import os

from django.db import transaction
from django.db.models import Max
from django.db.models.functions import ExtractYear
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from . import audit as _audit
from . import mail_templates
from . import notification_triggers
from .incident_flash_report import render_flash_report_pdf
from .incident_register_report import render_incident_register_pdf
from .incident_serializers import (
    IncidentActionSerializer,
    IncidentDetailSerializer,
    IncidentRegisterSerializer,
    IncidentRootCauseSerializer,
)
from .masters_views import BaseMasterViewSet
from .media_uploads import media_url, save_media_file
from .models import (
    FsCatgToRigTypeMapping,
    Incident,
    IncidentAction,
    IncidentPhoto,
    IncidentRootCause,
    MstFinancialYear,
    MstFsCategory,
    MstIncidentType,
    MstRig,
)
from .permissions import HasMenuPermission
from .xlsx_export import build_xlsx_response

CONTRACTOR_REQUIRED_THIRD_PARTY = {"0", "1"}
PHOTO_ALLOWED_EXTENSIONS = (".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".png")


def _resolve_financial_year(incident_date):
    fy = MstFinancialYear.objects.filter(
        fin_year_from__lte=incident_date, fin_year_to__gte=incident_date
    ).first()
    if not fy:
        raise ValidationError({"incident_date": "No financial year is configured for this date."})
    return fy


def _next_incident_no(financial_year):
    last = Incident.objects.filter(financial_year=financial_year).aggregate(m=Max("incident_no"))["m"]
    return (last or 0) + 1


def _validate_contractor_rule(data, instance=None):
    person_injured = data.get("person_injured", getattr(instance, "person_injured", None))
    third_party = data.get("third_party") if "third_party" in data else getattr(instance, "third_party", None)
    contractor = data.get("contractor") if "contractor" in data else getattr(instance, "contractor", None)
    if person_injured == "Y" and third_party in CONTRACTOR_REQUIRED_THIRD_PARTY and not contractor:
        raise ValidationError(
            {"contractor": "Contractor is required when Belongs To is TP Contractors or Operator Contractors."}
        )


class IncidentDetailViewSet(BaseMasterViewSet):
    queryset = Incident.objects.select_related(
        "rig", "incident_type", "immediate_incident_cause", "immediate_incident_cause_2",
        "rig_operation", "work_location", "contact_expo_type", "country", "operator",
        "contractor", "financial_loss_currency", "part_of_body_1", "part_of_body_2",
        "part_of_body_3", "part_of_body_4", "rptd_by_rank", "financial_year", "fs_emp",
    ).prefetch_related("photos").exclude(marked_as_deleted="Y")
    serializer_class = IncidentDetailSerializer
    entity_key = "qhse.incident_details"
    search_fields = [
        "incident_descr", "rig_incident_no", "emp_name", "comments",
        "reported_by", "well_no", "drilling_superintendent", "safety_officer",
        "work_location__work_location", "operator__operator_name", "country__country_name",
        "rig__rig_name", "incident_type__incident_type", "immediate_cause_descr",
        "corrective_action", "preventive_action",
    ]

    # Explicit allow-list rather than a raw ?ordering=<column> passthrough —
    # same reasoning as DrillingDtlViewSet's own _ORDERINGS.
    _ORDERINGS = {
        "incident_date": ("incident_date",),
        "-incident_date": ("-incident_date",),
        "incident_no": ("incident_no",),
        "-incident_no": ("-incident_no",),
        "rig_incident_no": ("rig_incident_no",),
        "-rig_incident_no": ("-rig_incident_no",),
    }

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
        if person_injured == "Y":
            qs = qs.filter(person_injured="Y")
        elif person_injured == "N":
            qs = qs.exclude(person_injured="Y")
        incident_type = params.get("incident_type")
        if incident_type:
            qs = qs.filter(incident_type_id=incident_type)

        ordering = params.get("ordering")
        return qs.order_by(*self._ORDERINGS.get(ordering, ("-incident_date",)))

    def label_for(self, instance):
        return str(instance)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    @action(detail=True, methods=["get"], url_path="flash-report")
    def flash_report(self, request, pk=None):
        instance = self.get_object()
        pdf_bytes = render_flash_report_pdf(instance)
        filename = f"Incident Flash Report - {instance.rig_incident_no or instance.incident_no}.pdf"
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        return response

    @action(detail=False, methods=["get"], url_path="meta")
    def meta(self, request):
        years = list(
            self.queryset.annotate(yr=ExtractYear("incident_date"))
            .values_list("yr", flat=True)
            .distinct()
            .order_by("-yr")
        )
        return Response({"years": years})

    def perform_create(self, serializer):
        data = serializer.validated_data
        _validate_contractor_rule(data)
        incident_date = data["incident_date"]
        fy = _resolve_financial_year(incident_date)
        incident_no = _next_incident_no(fy)

        uid = self._current_user_id(self.request)
        instance = serializer.save(
            financial_year=fy,
            incident_no=incident_no,
            cr_user_id=uid or 1,
            cr_dt=timezone.now(),
        )
        changes = {k: {"old": None, "new": v} for k, v in self._snapshot(instance).items() if v not in (None, "")}
        _audit.record_action(self.request, "create", self.entity_key, instance.pk, self.label_for(instance), changes or None)
        transaction.on_commit(lambda: self._notify_create(instance, uid))

    def _notify_create(self, instance, actor_user_id):
        """Fires only if a NotificationTrigger row exists for
        (entity_key, 'create') — see notification_triggers.py. No rule
        configured is a silent no-op, same as a missing recipient list.

        The Flash Report PDF is rendered here (main thread, on_commit,
        still has DB access) rather than inside the mail's own background
        thread — attachments crossing that boundary must already be plain
        bytes, per queue_notification_email's own contract."""
        subject, body = mail_templates.incident_created_mail(instance)
        pdf_bytes = render_flash_report_pdf(instance)
        filename = f"Incident Flash Report - {instance.rig_incident_no or instance.incident_no}.pdf"
        notification_triggers.trigger(
            self.entity_key,
            "create",
            subject,
            body,
            sent_by_user_id=actor_user_id,
            attachments=[(filename, pdf_bytes, "application/pdf")],
        )

    def perform_update(self, serializer):
        data = serializer.validated_data
        _validate_contractor_rule(data, instance=serializer.instance)
        old_snapshot = self._snapshot(serializer.instance)
        uid = self._current_user_id(self.request)
        instance = serializer.save(mod_user_id=uid, mod_dt=timezone.now())
        changes = self._diff(old_snapshot, self._snapshot(instance))
        _audit.record_action(self.request, "update", self.entity_key, instance.pk, self.label_for(instance), changes or None)

    def destroy(self, request, *args, **kwargs):
        """Legacy soft-deletes (marked_as_deleted='Y', cascade-hides
        photos/actions/root-causes) rather than a real DELETE — matches
        clsIncident_Details.DeleteMe's own "no physical delete" comment,
        which this app's base destroy() doesn't do by default."""
        instance = self.get_object()
        uid = self._current_user_id(request)
        instance.marked_as_deleted = "Y"
        instance.deleted_remarks = request.data.get("deleted_remarks") or None
        instance.mod_user_id = uid
        instance.mod_dt = timezone.now()
        instance.save()
        _audit.record_action(request, "delete", self.entity_key, instance.pk, self.label_for(instance), None)
        return Response(status=204)

    @action(detail=True, methods=["post"], url_path="photos")
    def upload_photo(self, request, pk=None):
        """One file per call (the frontend calls this once per selected
        file) — named `<incident id>_<next sequence for this incident>`,
        matching legacy's own Insert_Incident_Images numbering exactly."""
        instance = self.get_object()
        f = request.FILES.get("file")
        if not f:
            return Response({"error": "file is required"}, status=400)

        next_seq = instance.photos.count() + 1
        rel_path, error = save_media_file(
            f, "incident_photos", f"{instance.pk}_{next_seq}", allowed_extensions=PHOTO_ALLOWED_EXTENSIONS
        )
        if error:
            return Response({"error": error}, status=400)

        uid = self._current_user_id(request)
        photo = IncidentPhoto.objects.create(
            incident=instance, incident_photo_path=rel_path, cr_user_id=uid or 1, cr_dt=timezone.now()
        )
        _audit.record_action(
            request, "update", self.entity_key, instance.pk, self.label_for(instance),
            {"photo_added": {"old": None, "new": rel_path}},
        )
        return Response(
            {"incident_photo_id": photo.incident_photo_id, "incident_photo_path": rel_path, "url": media_url(request, rel_path)},
            status=201,
        )

    @upload_photo.mapping.delete
    def delete_photo(self, request, pk=None):
        instance = self.get_object()
        photo_id = request.query_params.get("photo_id")
        try:
            photo = instance.photos.get(pk=photo_id)
        except IncidentPhoto.DoesNotExist:
            return Response({"error": "Photo not found."}, status=404)

        abs_path = None
        try:
            from django.conf import settings

            abs_path = os.path.join(settings.MEDIA_ROOT, photo.incident_photo_path)
        except Exception:
            pass
        rel_path = photo.incident_photo_path
        photo.delete()
        if abs_path and os.path.exists(abs_path):
            os.remove(abs_path)
        _audit.record_action(
            request, "update", self.entity_key, instance.pk, self.label_for(instance),
            {"photo_removed": {"old": rel_path, "new": None}},
        )
        return Response(status=204)


class IncidentRootCauseViewSet(BaseMasterViewSet):
    """QHSE → Incident Root Cause — legacy frmIncident_Root_Cause.aspx(.cs).
    One or more root-cause/subcause rows recorded against an Incident,
    always scoped to a single Incident at a time in the UI (the ?incident=
    filter below), matching the legacy form's own single-incident-at-a-time
    grid. See IncidentRootCauseSerializer's own docstring for the one
    simplified rule (Root Subcause Others is optional here, not
    conditionally required — the legacy "Others" subcause id list isn't
    fully present in our imported data)."""

    queryset = IncidentRootCause.objects.select_related(
        "incident", "incident__rig", "root_cause", "root_subcause"
    ).exclude(marked_as_deleted="Y")
    serializer_class = IncidentRootCauseSerializer
    entity_key = "qhse.incident_root_cause"

    def get_queryset(self):
        qs = self.queryset
        incident_id = self.request.query_params.get("incident")
        if incident_id:
            qs = qs.filter(incident_id=incident_id)
        return qs.order_by("-cr_dt")

    def label_for(self, instance):
        return f"{instance.incident} — {instance.root_cause}"

    def perform_create(self, serializer):
        uid = self._current_user_id(self.request)
        instance = serializer.save(cr_user_id=uid or 1, cr_dt=timezone.now())
        changes = {k: {"old": None, "new": v} for k, v in self._snapshot(instance).items() if v not in (None, "")}
        _audit.record_action(self.request, "create", self.entity_key, instance.pk, self.label_for(instance), changes or None)

    def perform_update(self, serializer):
        old_snapshot = self._snapshot(serializer.instance)
        uid = self._current_user_id(self.request)
        instance = serializer.save(mod_user_id=uid, mod_dt=timezone.now())
        changes = self._diff(old_snapshot, self._snapshot(instance))
        _audit.record_action(self.request, "update", self.entity_key, instance.pk, self.label_for(instance), changes or None)

    def destroy(self, request, *args, **kwargs):
        """Legacy soft-deletes (marked_as_deleted='Y') rather than a real
        DELETE — same reasoning as IncidentDetailViewSet.destroy above."""
        instance = self.get_object()
        uid = self._current_user_id(request)
        instance.marked_as_deleted = "Y"
        instance.deleted_remarks = request.data.get("deleted_remarks") or None
        instance.mod_user_id = uid
        instance.mod_dt = timezone.now()
        instance.save()
        _audit.record_action(request, "delete", self.entity_key, instance.pk, self.label_for(instance), None)
        return Response(status=204)


class IncidentActionViewSet(BaseMasterViewSet):
    """QHSE → Incident Actions — legacy frmIncident_Actions.aspx(.cs).
    Scoped to one Incident at a time via ?incident=, same shape as
    IncidentRootCauseViewSet. See IncidentActionSerializer's own docstring
    for the two real business rules (Completion Dt forces status to 'CL';
    Target/Completion Dt must be >= the incident's own date)."""

    queryset = IncidentAction.objects.select_related(
        "incident", "incident__rig", "incident__incident_type"
    ).exclude(marked_as_deleted="Y")
    serializer_class = IncidentActionSerializer
    entity_key = "qhse.incident_actions"

    def get_queryset(self):
        qs = self.queryset
        incident_id = self.request.query_params.get("incident")
        if incident_id:
            qs = qs.filter(incident_id=incident_id)
        return qs.order_by("-cr_dt")

    def label_for(self, instance):
        return f"{instance.incident} — {instance.action_recommended[:40]}"

    def perform_create(self, serializer):
        uid = self._current_user_id(self.request)
        instance = serializer.save(action_status="OP", cr_user_id=uid or 1, cr_dt=timezone.now())
        changes = {k: {"old": None, "new": v} for k, v in self._snapshot(instance).items() if v not in (None, "")}
        _audit.record_action(self.request, "create", self.entity_key, instance.pk, self.label_for(instance), changes or None)

    def perform_update(self, serializer):
        old_snapshot = self._snapshot(serializer.instance)
        uid = self._current_user_id(self.request)
        # Filling Completion Dt always closes the action, overriding
        # whatever the status field itself was set to — matches legacy's
        # own InsertUpdateData, which does this unconditionally on Update.
        completion_dt = serializer.validated_data.get("completion_dt")
        status_override = {"action_status": "CL"} if completion_dt else {}
        instance = serializer.save(mod_user_id=uid, mod_dt=timezone.now(), **status_override)
        changes = self._diff(old_snapshot, self._snapshot(instance))
        _audit.record_action(self.request, "update", self.entity_key, instance.pk, self.label_for(instance), changes or None)

    def destroy(self, request, *args, **kwargs):
        """Legacy soft-deletes (marked_as_deleted='Y') rather than a real
        DELETE — same reasoning as IncidentDetailViewSet.destroy above."""
        instance = self.get_object()
        uid = self._current_user_id(request)
        instance.marked_as_deleted = "Y"
        instance.deleted_remarks = request.data.get("deleted_remarks") or None
        instance.mod_user_id = uid
        instance.mod_dt = timezone.now()
        instance.save()
        _audit.record_action(request, "delete", self.entity_key, instance.pk, self.label_for(instance), None)
        return Response(status=204)


def _category_rig_type_ids(category_id):
    """Rig types an Fs Category actually applies to, per
    FsCatgToRigTypeMapping.mapping_active='Y' — e.g. "Onshore Rig
    Personnel" -> {Onshore Rig, Repair Yard}. Returns None (no restriction)
    if the category has no active mapping at all, rather than an empty set
    that would silently zero out every rig."""
    rig_type_ids = list(
        FsCatgToRigTypeMapping.objects.filter(
            fs_category_id=category_id, mapping_active="Y"
        ).values_list("rig_type_id", flat=True)
    )
    return rig_type_ids or None


class IncidentRegisterViewSet(viewsets.ReadOnlyModelViewSet):
    """QHSE → Incident Register — read-only, ports rfrmIncident_Register.aspx's
    filter-driven grid (Category, Rig(s), Incident Type(s), date range)
    rather than duplicating the fuller Incidents report (reports.incidents):
    this one is deliberately narrow — five columns, multi-select rig/type,
    an explicit From/To range — matching the legacy page's own shape.

    GET supports ?category=&rigs=&incident_types=&date_from=&date_to=
    &search=&ordering= (one of date/rig/type, prefix '-' to reverse;
    defaults to '-date'). rigs/incident_types are comma-joined id lists.
    category (an Fs_Category id) narrows the *rig* filter to whichever rig
    types that category maps to (see _category_rig_type_ids) — it doesn't
    filter incidents directly, matching how the legacy Category dropdown
    only ever scoped the Rig picker, never the incident rows themselves."""

    queryset = Incident.objects.select_related("rig", "incident_type").exclude(marked_as_deleted="Y")
    serializer_class = IncidentRegisterSerializer
    entity_key = "qhse.incident_register"
    permission_classes = [HasMenuPermission]
    search_fields = ["incident_descr"]

    def get_queryset(self):
        qs = self.queryset
        params = self.request.query_params

        category_id = params.get("category")
        if category_id and category_id.isdigit():
            rig_type_ids = _category_rig_type_ids(category_id)
            if rig_type_ids is not None:
                qs = qs.filter(rig__rig_type_id__in=rig_type_ids)

        rigs = params.get("rigs")
        if rigs:
            rig_ids = [x for x in rigs.split(",") if x.strip().isdigit()]
            if rig_ids:
                qs = qs.filter(rig_id__in=rig_ids)

        incident_types = params.get("incident_types")
        if incident_types:
            type_ids = [x for x in incident_types.split(",") if x.strip().isdigit()]
            if type_ids:
                qs = qs.filter(incident_type_id__in=type_ids)

        date_from = params.get("date_from")
        if date_from:
            qs = qs.filter(incident_date__date__gte=date_from)
        date_to = params.get("date_to")
        if date_to:
            qs = qs.filter(incident_date__date__lte=date_to)

        ordering = params.get("ordering", "-date")
        reverse = ordering.startswith("-")
        field = {"date": "incident_date", "rig": "rig__rig_name", "type": "incident_type__incident_type"}.get(
            ordering.lstrip("-")
        )
        if field:
            qs = qs.order_by(f"-{field}" if reverse else field)
        else:
            qs = qs.order_by("-incident_date")
        return qs

    def _filter_summary(self, request):
        """Human-readable caption for the print/PDF header — mirrors the
        legacy report's "For the Period X to Y" caption, extended with
        whichever Category/date range is actually active."""
        params = request.query_params
        parts = []
        category_id = params.get("category")
        if category_id and category_id.isdigit():
            category = MstFsCategory.objects.filter(pk=category_id).first()
            if category:
                parts.append(category.fs_category_name)
        date_from = params.get("date_from")
        date_to = params.get("date_to")
        if date_from or date_to:
            parts.append(f"Period: {date_from or '…'} to {date_to or '…'}")
        return " · ".join(parts) if parts else "All incidents"

    @action(detail=False, methods=["get"], url_path="meta")
    def meta(self, request):
        """Filter-bar options. `?category=` narrows the rig list the same
        way get_queryset's own category filter does, so picking a category
        in the UI also trims which rigs the Rig picker offers — matching
        the legacy page's Category-scopes-the-Rig-search-window behavior."""
        categories = list(
            MstFsCategory.objects.filter(rig_type_mappings__mapping_active="Y")
            .distinct()
            .order_by("fs_category_name")
            .values("fs_category_id", "fs_category_name")
        )

        rig_qs = MstRig.objects.all()
        category_id = request.query_params.get("category")
        if category_id and category_id.isdigit():
            rig_type_ids = _category_rig_type_ids(category_id)
            if rig_type_ids is not None:
                rig_qs = rig_qs.filter(rig_type_id__in=rig_type_ids)
        rigs = list(rig_qs.order_by("rig_name").values("rig_id", "rig_name"))

        incident_types = list(
            MstIncidentType.objects.order_by("incident_type").values("incident_type_id", "incident_type")
        )

        return Response(
            {
                "categories": [
                    {"id": c["fs_category_id"], "name": c["fs_category_name"]} for c in categories
                ],
                "rigs": [{"id": r["rig_id"], "name": r["rig_name"]} for r in rigs],
                "incident_types": [
                    {"id": t["incident_type_id"], "name": t["incident_type"]} for t in incident_types
                ],
            }
        )

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        """.xlsx, not .csv — matches every other export in this app (see
        xlsx_export.py's own docstring: CSV can't carry the bold/grey/
        bordered header row the rest of the app's exports all have)."""
        qs = self.get_queryset()
        rows = [
            [
                i.rig.rig_name if i.rig_id else "Unknown",
                i.rig_incident_no or "",
                i.incident_date.strftime("%d/%m/%Y %H:%M") if i.incident_date else "",
                i.incident_type.incident_abrv if i.incident_type_id else "",
                i.incident_descr,
            ]
            for i in qs.iterator()
        ]
        filename = f"incident-register-{timezone.now().date().isoformat()}.xlsx"
        response = build_xlsx_response(
            filename,
            "Incident Register",
            ["Incident Register", self._filter_summary(request)],
            ["Rig", "Incident No.", "Date & Time of Incident", "Incident Type", "Brief Description"],
            rows,
            wide_columns=(4,),
        )
        _audit.record_action(
            request, "export", self.entity_key, record_label="Incident Register Excel export",
            changes={"rows_exported": {"old": None, "new": len(rows)}},
        )
        return response

    @action(detail=False, methods=["get"], url_path="print")
    def print_pdf(self, request):
        """PDF version of the current filtered list — same WeasyPrint
        pipeline as the per-incident Flash Report (incident_flash_report.py),
        landscape and row-based rather than a single-incident letterhead
        (see incident_register_report.py)."""
        qs = self.get_queryset()
        pdf_bytes = render_incident_register_pdf(qs, self._filter_summary(request))
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = 'inline; filename="Incident Register.pdf"'
        _audit.record_action(
            request, "export", self.entity_key, record_label="Incident Register PDF print",
            changes={"rows_printed": {"old": None, "new": qs.count()}},
        )
        return response
