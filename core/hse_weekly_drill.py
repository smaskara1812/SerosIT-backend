"""QHSE → HSE Weekly Drill — rebuild of legacy frmHSE_Weekly_Drill_Hdr
(header: Rig + Year + Week; detail: the drills carried out that week).

Rules ported from frmHSE_Weekly_Drill_Hdr.aspx(.cs), confirmed against the
legacy data rather than guessed:
  - Week defaults to the rig's last week that year + 1 (1 if none) — still
    editable, same as legacy's textbox (confirmed with the user).
  - No header Update (the detail rows depend on it); header Delete is live
    and removes its detail rows too.
  - A drill can only be added once per header, and only drills valid for
    the rig's type (Offshore/Onshore-only drills are hidden from the other
    kind of rig; null rig_type = both). Legacy hardcoded "rig id 1 =
    offshore" for this; we read the rig's real rig_type, same deviation as
    the HSE Drill Record page. Inactive drills aren't offered.
  - Last Drill Conducted Date: if this rig has no earlier entry for that
    drill, the user types it (first-time entry); otherwise it's the rig's
    latest earlier Drill Conducted Date for that drill and is locked —
    inferred from legacy rows, where it matches the previous entry's
    conducted date.
  - Editing a detail row only changes Drill Conducted Date and Remarks.
Legacy's per-week start/end dates are deliberately not carried over
(confirmed with the user).
"""

from datetime import date

from django.db.models import Count, Max, Q
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from . import audit as _audit
from .masters_views import BaseMasterViewSet
from .models import HseWeeklyDrillDtl, HseWeeklyDrillHdr, MstHseDrill, MstRig
from .permissions import HasMenuPermission

ENTITY_KEY = "qhse.hse_weekly_drill"
_AUDIT_READ_ONLY = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


def _drill_label(d):
    return f"{d.hse_drill_name} — {d.get_hse_drill_frequency_display()} — {d.rig_type.rig_type_name if d.rig_type_id else 'All'}"


def _previous_conducted_dt(rig_id, drill_id, before, exclude_dtl_id=None):
    qs = HseWeeklyDrillDtl.objects.filter(hdr__rig_id=rig_id, hse_drill_id=drill_id, drill_conducted_dt__lt=before)
    if exclude_dtl_id:
        qs = qs.exclude(pk=exclude_dtl_id)
    return qs.aggregate(m=Max("drill_conducted_dt"))["m"]


class HseWeeklyDrillHdrSerializer(serializers.ModelSerializer):
    rig_name = serializers.CharField(source="rig.rig_name", read_only=True, default="")
    year = serializers.IntegerField(min_value=1990, max_value=2100, write_only=True)
    drill_week = serializers.IntegerField(min_value=1, max_value=53)
    drill_year = serializers.DateField(read_only=True)
    dtl_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = HseWeeklyDrillHdr
        fields = "__all__"
        read_only_fields = _AUDIT_READ_ONLY

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["year"] = instance.drill_year.year
        return data

    def validate(self, attrs):
        attrs["drill_year"] = date(attrs.pop("year"), 1, 1)
        if HseWeeklyDrillHdr.objects.filter(rig=attrs["rig"], drill_year=attrs["drill_year"], drill_week=attrs["drill_week"]).exists():
            raise serializers.ValidationError({"drill_week": "This rig already has a record for that year and week."})
        return attrs


class HseWeeklyDrillHdrViewSet(BaseMasterViewSet):
    queryset = HseWeeklyDrillHdr.objects.select_related("rig").annotate(dtl_count=Count("dtls"))
    serializer_class = HseWeeklyDrillHdrSerializer
    entity_key = ENTITY_KEY
    permission_classes = [HasMenuPermission]
    search_fields = ["rig__rig_name"]
    # No header Update in legacy.
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        qs = self.queryset
        params = self.request.query_params
        if params.get("rig"):
            qs = qs.filter(rig_id=params["rig"])
        if params.get("year"):
            qs = qs.filter(drill_year__year=params["year"])
        return qs.order_by("-drill_year", "-drill_week", "rig__rig_name")

    def label_for(self, instance):
        return f"HSE Weekly Drill {instance.rig.rig_name} {instance.drill_year.year} W{instance.drill_week}"

    @action(detail=False, methods=["get"], url_path="meta")
    def meta(self, request):
        years = HseWeeklyDrillHdr.objects.dates("drill_year", "year", order="DESC")
        return Response({"years": [d.year for d in years]})

    @action(detail=False, methods=["get"], url_path="next-week")
    def next_week(self, request):
        rig, year = request.query_params.get("rig"), request.query_params.get("year")
        if not (rig and rig.isdigit() and year and year.isdigit()):
            return Response({"error": "?rig= and ?year= are required"}, status=400)
        last = HseWeeklyDrillHdr.objects.filter(rig_id=rig, drill_year__year=year).aggregate(m=Max("drill_week"))["m"]
        return Response({"week": (last or 0) + 1})

    @action(detail=True, methods=["get"], url_path="drills")
    def drills(self, request, pk=None):
        """Drills still pickable for this header: active, valid for the
        rig's type, and not already added."""
        hdr = self.get_object()
        rig = MstRig.objects.get(pk=hdr.rig_id)
        qs = (
            MstHseDrill.objects.filter(hse_drill_active="Y")
            .filter(Q(rig_type__isnull=True) | Q(rig_type_id=rig.rig_type_id))
            .exclude(weekly_drill_dtls__hdr=hdr)
            .select_related("rig_type")
            .order_by("hse_drill_name")
        )
        return Response([{"id": d.hse_drill_id, "name": d.hse_drill_name, "label": _drill_label(d)} for d in qs])

    @action(detail=True, methods=["get"], url_path="last-conducted")
    def last_conducted(self, request, pk=None):
        hdr = self.get_object()
        drill, on = request.query_params.get("drill"), request.query_params.get("date")
        try:
            conducted = date.fromisoformat(on)
            drill_id = int(drill)
        except (TypeError, ValueError):
            return Response({"error": "?drill= and ?date=YYYY-MM-DD are required"}, status=400)
        prev = _previous_conducted_dt(hdr.rig_id, drill_id, conducted)
        return Response({"first_time": prev is None, "last_conducted_dt": prev.isoformat() if prev else None})

    def destroy(self, request, *args, **kwargs):
        # Same single-audit-entry-with-cascade-count approach as the HSE
        # Drill Record header's destroy().
        instance = self.get_object()
        count = instance.dtl_count
        label, pk = self.label_for(instance), instance.pk
        instance.delete()
        _audit.record_action(
            request, "delete", self.entity_key, pk, label, {"drills_deleted": {"old": count, "new": 0}} if count else None
        )
        return Response(status=204)


class HseWeeklyDrillDtlSerializer(serializers.ModelSerializer):
    hse_drill_name = serializers.CharField(source="hse_drill.hse_drill_name", read_only=True, default="")

    class Meta:
        model = HseWeeklyDrillDtl
        fields = "__all__"
        read_only_fields = _AUDIT_READ_ONLY
        # validate() below gives the friendlier duplicate-drill message.
        validators = []

    def validate(self, attrs):
        if self.instance is not None:
            # Legacy's row Edit only touches Conducted Date + Remarks.
            for locked in ("hdr", "hse_drill", "drill_last_conducted_dt"):
                if locked in attrs and attrs[locked] != getattr(self.instance, locked):
                    raise serializers.ValidationError({locked: "Can't be changed — delete the row and add it again."})
            return attrs

        hdr, drill, conducted = attrs["hdr"], attrs["hse_drill"], attrs["drill_conducted_dt"]
        if HseWeeklyDrillDtl.objects.filter(hdr=hdr, hse_drill=drill).exists():
            raise serializers.ValidationError({"hse_drill": "This drill is already added for this week."})
        rig = hdr.rig
        if drill.hse_drill_active != "Y" or (drill.rig_type_id and drill.rig_type_id != rig.rig_type_id):
            raise serializers.ValidationError({"hse_drill": "This drill isn't available for this rig."})

        prev = _previous_conducted_dt(hdr.rig_id, drill.pk, conducted)
        if prev:
            attrs["drill_last_conducted_dt"] = prev
        else:
            last = attrs.get("drill_last_conducted_dt")
            if not last:
                raise serializers.ValidationError(
                    {"drill_last_conducted_dt": "Enter the Last Drill Conducted Date — this is the first entry for this drill on this rig."}
                )
            if last >= conducted:
                raise serializers.ValidationError({"drill_last_conducted_dt": "Must be before the Drill Conducted Date."})
        return attrs


class HseWeeklyDrillDtlViewSet(BaseMasterViewSet):
    queryset = HseWeeklyDrillDtl.objects.select_related("hdr", "hdr__rig", "hse_drill")
    serializer_class = HseWeeklyDrillDtlSerializer
    entity_key = ENTITY_KEY
    permission_classes = [HasMenuPermission]

    def get_queryset(self):
        qs = self.queryset
        if self.request.query_params.get("hdr"):
            qs = qs.filter(hdr_id=self.request.query_params["hdr"])
        return qs.order_by("hse_weekly_drill_dtl_id")

    def label_for(self, instance):
        h = instance.hdr
        return f"{h.rig.rig_name} {h.drill_year.year} W{h.drill_week} — {instance.hse_drill.hse_drill_name}"
