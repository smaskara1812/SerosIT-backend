"""QHSE → HSE Drills / Exercises — Add/Update workflow for
HseDrillRecordHdr (see that model's own docstring).

Ported from frmHSE_Drill_Record_Hdr.aspx(.cs)/clsHSE_Drill_Record_Hdr.cs,
with two real business rules confirmed from that code:
  - Drill Record No. is never user-entered — server-generated on create as
    "{Rig short name}/{Sr. No. rigwise}/{Calendar year of Drill Date}",
    with the rigwise serial number also server-computed (MAX+1 per rig).
  - A new record's Drill Date must be on or after the rig's own most
    recent drill date — legacy rejects an insert that would backdate a
    rig's drill history. This is enforced on create only, matching
    legacy's own Insert-branch-only check (Update never re-validates it).

One deliberate deviation: legacy's "Type of Drill" picker filtered by a
single hardcoded rig id standing in for "is this rig offshore" (Rig_Id==1
specifically, not a real rig-type lookup). This build reads the rig's
actual MstRig.rig_type instead, via Mst_HSE_Drill's own rig_type (null =
every rig type) — correct for every rig, not just the one legacy
hardcoded.

Not implemented: legacy's "Initiated By"/"PIC-OIM" Fs Employee pickers are
scoped to employees assigned to the selected rig — MstEmployee (this app's
Fs Employee equivalent) carries no rig association at all, so that
filtering has no equivalent data to drive it here. The picker is the same
unfiltered employee search used elsewhere in this app (e.g. Hazard ID
Card's Reported By).

Child tables from the legacy page (Event/Observation/Improvement/
Corrective Action/Photo Upload) are modeled (see models.py) and their
legacy data is migrated — see SQL commands/import_hse_drill_record.sql —
but there's no add/edit UI for them yet, and the printable Drill Record
report built from them isn't built either; both stay on hold pending the
legacy UI reference for those forms.
"""

from decimal import Decimal

from django.db.models import Count, IntegerField, Max, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from . import audit as _audit
from .masters_views import BaseMasterViewSet
from .models import (
    HseDrillRecordCorrectiveAction,
    HseDrillRecordEvent,
    HseDrillRecordHdr,
    HseDrillRecordImprovement,
    HseDrillRecordObservation,
    HseDrillRecordPhotoUpload,
    MstHseDrill,
    MstRig,
)
from .permissions import HasMenuPermission


def _child_count(model):
    """A correlated-subquery row count for one child table, instead of a
    Count(..., distinct=True) annotation. Annotating all five child
    reverse-FKs as joins in the same query multiplies their row counts
    against each other (e.g. 13 events x 6 observations x 5 improvements
    x 3 corrective actions x 8 photos = 9,360 joined rows for one header,
    even with distinct=True pruning the final count back down) — cheap at
    63 headers, but it scales with the product of the child counts, not
    their sum, so it gets expensive fast as more drills accumulate. A
    subquery counts each child table on its own and never joins them
    together."""
    sub = model.objects.filter(hdr_id=OuterRef("pk")).order_by().values("hdr_id").annotate(c=Count("pk")).values("c")
    return Coalesce(Subquery(sub, output_field=IntegerField()), Value(0))

# Decimal(4,2) fields using legacy's packed MM.SS format (fractional part
# is seconds 00-59, not a true decimal fraction) — validated below.
MM_SS_FIELDS = [
    "initial_response_time",
    "fire_team_1_duration",
    "fire_team_2_duration",
    "snr_team_duration",
    "drill_muster",
    "abandon_muster_offshore",
    "total_time_of_drill",
]


def _validate_mm_ss(attrs):
    for field in MM_SS_FIELDS:
        value = attrs.get(field)
        if value is None:
            continue
        seconds = abs(value) % 1
        if round(seconds * 100) > 59:
            raise ValidationError({field: "Seconds (the part after the decimal point) cannot be greater than 59."})


class HseDrillRecordHdrSerializer(serializers.ModelSerializer):
    rig_name = serializers.CharField(source="rig.rig_name", read_only=True, default="")
    hse_drill_1_name = serializers.CharField(source="hse_drill_1.hse_drill_name", read_only=True, default="")
    hse_drill_2_name = serializers.CharField(source="hse_drill_2.hse_drill_name", read_only=True, default="")
    initiated_by_fs_emp_1_name = serializers.SerializerMethodField()
    initiated_by_fs_emp_2_name = serializers.SerializerMethodField()
    approved_by_oim_fs_emp_name = serializers.SerializerMethodField()
    # Child-row counts — read off the queryset's own annotations
    # (get_queryset below), not a live .count() per field here, so listing
    # 60+ rows doesn't fire 5 extra queries each. Lets the frontend show
    # exactly what a Delete would cascade into before the user confirms.
    events_count = serializers.IntegerField(read_only=True, default=0)
    observations_count = serializers.IntegerField(read_only=True, default=0)
    improvements_count = serializers.IntegerField(read_only=True, default=0)
    corrective_actions_count = serializers.IntegerField(read_only=True, default=0)
    photo_uploads_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = HseDrillRecordHdr
        fields = "__all__"
        read_only_fields = ["drill_record_sr_no", "drill_record_no", "cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def get_initiated_by_fs_emp_1_name(self, obj):
        return str(obj.initiated_by_fs_emp_1) if obj.initiated_by_fs_emp_1_id else ""

    def get_initiated_by_fs_emp_2_name(self, obj):
        return str(obj.initiated_by_fs_emp_2) if obj.initiated_by_fs_emp_2_id else ""

    def get_approved_by_oim_fs_emp_name(self, obj):
        return str(obj.approved_by_oim_fs_emp) if obj.approved_by_oim_fs_emp_id else ""

    def validate(self, attrs):
        _validate_mm_ss(attrs)
        head_count = attrs.get("head_count", getattr(self.instance, "head_count", None))
        participants = attrs.get("no_of_participants", getattr(self.instance, "no_of_participants", None))
        if head_count is not None and participants is not None and participants > head_count:
            raise ValidationError({"no_of_participants": "No. of Participants cannot be greater than Head Count."})

        drill_1 = attrs.get("hse_drill_1", getattr(self.instance, "hse_drill_1", None))
        drill_2 = attrs.get("hse_drill_2", getattr(self.instance, "hse_drill_2", None)) if "hse_drill_2" in attrs else getattr(self.instance, "hse_drill_2", None)
        if drill_1 and drill_2 and drill_1 == drill_2:
            raise ValidationError({"hse_drill_2": "Type of Drill/Training - 2 must differ from - 1."})

        emp_1 = attrs.get("initiated_by_fs_emp_1", getattr(self.instance, "initiated_by_fs_emp_1", None))
        emp_2 = (
            attrs.get("initiated_by_fs_emp_2", getattr(self.instance, "initiated_by_fs_emp_2", None))
            if "initiated_by_fs_emp_2" in attrs
            else getattr(self.instance, "initiated_by_fs_emp_2", None)
        )
        if emp_1 and emp_2 and emp_1 == emp_2:
            raise ValidationError({"initiated_by_fs_emp_2": "Initiated By - 2 must differ from - 1."})
        return attrs


def _next_drill_record_no(rig, drill_dt):
    sr_no = (HseDrillRecordHdr.objects.filter(rig=rig).aggregate(m=Max("drill_record_sr_no"))["m"] or 0) + 1
    return sr_no, f"{rig.rig_short_name}/{sr_no}/{drill_dt.year}"


class HseDrillRecordHdrViewSet(BaseMasterViewSet):
    queryset = HseDrillRecordHdr.objects.select_related(
        "rig", "hse_drill_1", "hse_drill_2", "initiated_by_fs_emp_1", "initiated_by_fs_emp_2", "approved_by_oim_fs_emp"
    ).annotate(
        events_count=_child_count(HseDrillRecordEvent),
        observations_count=_child_count(HseDrillRecordObservation),
        improvements_count=_child_count(HseDrillRecordImprovement),
        corrective_actions_count=_child_count(HseDrillRecordCorrectiveAction),
        photo_uploads_count=_child_count(HseDrillRecordPhotoUpload),
    )
    serializer_class = HseDrillRecordHdrSerializer
    entity_key = "qhse.hse_drill_record"
    permission_classes = [HasMenuPermission]
    search_fields = ["drill_record_no", "drill_location"]

    _ORDERINGS = {
        "drill_dt": ("drill_dt", "drill_record_hdr_id"),
        "-drill_dt": ("-drill_dt", "-drill_record_hdr_id"),
        "drill_record_no": ("drill_record_no",),
        "-drill_record_no": ("-drill_record_no",),
        "head_count": ("head_count", "-drill_dt"),
        "-head_count": ("-head_count", "-drill_dt"),
    }

    def get_queryset(self):
        qs = self.queryset
        params = self.request.query_params
        rig_id = params.get("rig")
        if rig_id:
            qs = qs.filter(rig_id=rig_id)
        year = params.get("year")
        if year:
            qs = qs.filter(drill_dt__year=year)
        hse_drill = params.get("hse_drill")
        if hse_drill:
            qs = qs.filter(Q(hse_drill_1_id=hse_drill) | Q(hse_drill_2_id=hse_drill))
        ordering = params.get("ordering")
        return qs.order_by(*self._ORDERINGS.get(ordering, self._ORDERINGS["-drill_dt"]))

    def label_for(self, instance):
        return f"HSE Drill {instance.drill_record_no}"

    @action(detail=False, methods=["get"], url_path="meta")
    def meta(self, request):
        years = [d.year for d in self.queryset.dates("drill_dt", "year", order="DESC")]
        # The master has several active rows sharing a name (e.g. four
        # "Fire Drill"/"fire drill" differing only by case) — the frequency
        # + rig-type suffix is what actually tells them apart, same label
        # format as the form's own rig-context picker.
        drill_types = (
            MstHseDrill.objects.filter(hse_drill_active="Y").select_related("rig_type").order_by("hse_drill_name")
        )
        return Response(
            {
                "years": years,
                "drill_types": [
                    {
                        "id": d.hse_drill_id,
                        "name": d.hse_drill_name,
                        "label": f"{d.hse_drill_name} — {d.get_hse_drill_frequency_display()} — {d.rig_type.rig_type_name if d.rig_type_id else 'All'}",
                    }
                    for d in drill_types
                ],
            }
        )

    @action(detail=False, methods=["get"], url_path="rig-context")
    def rig_context(self, request):
        """Type of Drill/Training options for a given Rig, scoped to that
        rig's own rig_type (or drills with no rig_type restriction)."""
        rig_id = request.query_params.get("rig")
        if not rig_id or not rig_id.isdigit():
            return Response({"error": "?rig= is required"}, status=400)
        rig = MstRig.objects.filter(pk=rig_id).first()
        if not rig:
            return Response({"error": "Unknown rig"}, status=404)

        drills = (
            MstHseDrill.objects.filter(hse_drill_active="Y")
            .filter(Q(rig_type__isnull=True) | Q(rig_type_id=rig.rig_type_id))
            .select_related("rig_type")
            .order_by("hse_drill_name")
        )
        return Response(
            [
                {
                    "id": d.hse_drill_id,
                    "name": d.hse_drill_name,
                    "label": f"{d.hse_drill_name} — {d.get_hse_drill_frequency_display()} — {d.rig_type.rig_type_name if d.rig_type_id else 'All'}",
                }
                for d in drills
            ]
        )

    def perform_create(self, serializer):
        data = serializer.validated_data
        rig = data["rig"]
        drill_dt = data["drill_dt"]

        max_drill_dt = HseDrillRecordHdr.objects.filter(rig=rig).aggregate(m=Max("drill_dt"))["m"]
        if max_drill_dt and drill_dt.date() < max_drill_dt.date():
            raise ValidationError(
                {"drill_dt": f"Drill date must be on or after this rig's most recent drill date ({max_drill_dt:%d/%m/%Y})."}
            )

        sr_no, drill_no = _next_drill_record_no(rig, drill_dt)
        uid = self._current_user_id(self.request)
        instance = serializer.save(
            drill_record_sr_no=sr_no,
            drill_record_no=drill_no,
            cr_user_id=uid or 1,
            cr_dt=timezone.now(),
        )
        changes = {k: {"old": None, "new": v} for k, v in self._snapshot(instance).items() if v not in (None, "")}
        _audit.record_action(self.request, "create", self.entity_key, instance.pk, self.label_for(instance), changes or None)

    def perform_update(self, serializer):
        old_snapshot = self._snapshot(serializer.instance)
        uid = self._current_user_id(self.request)
        instance = serializer.save(mod_user_id=uid or 1, mod_dt=timezone.now())
        changes = self._diff(old_snapshot, self._snapshot(instance))
        _audit.record_action(self.request, "update", self.entity_key, instance.pk, self.label_for(instance), changes or None)

    def destroy(self, request, *args, **kwargs):
        # Reimplements BaseMasterViewSet.destroy() (rather than calling
        # super() then logging again) so there's exactly one audit entry
        # per delete, carrying the cascade counts — deleting a header
        # CASCADEs to its five child tables (see those models' own
        # docstrings), and the audit trail should record what else went
        # with it, not just the header row, matching the legacy delete
        # confirmation's own warning ("It will delete multiple data from
        # other forms").
        instance = self.get_object()
        cascade_counts = {
            "events_deleted": instance.events_count,
            "observations_deleted": instance.observations_count,
            "improvements_deleted": instance.improvements_count,
            "corrective_actions_deleted": instance.corrective_actions_count,
            "photo_uploads_deleted": instance.photo_uploads_count,
        }
        label = self.label_for(instance)
        pk = instance.pk
        instance.delete()
        changes = {k: {"old": v, "new": 0} for k, v in cascade_counts.items() if v}
        _audit.record_action(request, "delete", self.entity_key, pk, label, changes or None)
        return Response(status=204)
