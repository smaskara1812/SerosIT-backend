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

from django.db.models import Max
from django.db.models.functions import ExtractYear
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from . import audit as _audit
from .incident_serializers import IncidentDetailSerializer
from .masters_views import BaseMasterViewSet
from .media_uploads import media_url, save_media_file
from .models import Incident, IncidentPhoto, MstFinancialYear

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
