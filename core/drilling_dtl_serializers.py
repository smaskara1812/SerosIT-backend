from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from rest_framework import serializers

from .models import DrillingDtl, DrillingDtlOps


class DrillingDtlOpsSerializer(serializers.ModelSerializer):
    # Declared explicitly (not left to ModelSerializer's default) so it's
    # writable and optional — same reasoning as ApproverMappingDtlSerializer:
    # an AutoField PK defaults to read-only, but the parent's nested-write
    # sync needs existing rows' ids back to tell an edit from a new row.
    drilling_dtl_ops_id = serializers.IntegerField(required=False)
    drilling_ops_name = serializers.CharField(source="drilling_ops.drilling_ops_name", read_only=True, default="")
    drilling_section_name = serializers.CharField(
        source="drilling_section.drilling_section_name", read_only=True, default=""
    )
    rate_code = serializers.CharField(source="prj_drilling_rate.drilling_rate.rate_code", read_only=True, default="")
    # duration and rop_trip_mh are both server-computed (never trust a
    # client-supplied value for a field the legacy data itself derives) —
    # read-only here. Confirmed against real historical rows: rop_trip_mh is
    # round((Depth_To - Depth_From) / Duration), sign kept (a decreasing
    # depth — tripping out — gives a real negative ROP, not an error).
    duration = serializers.DecimalField(max_digits=4, decimal_places=2, read_only=True)
    rop_trip_mh = serializers.IntegerField(read_only=True)

    class Meta:
        model = DrillingDtlOps
        fields = [
            "drilling_dtl_ops_id",
            "time_from",
            "time_to",
            "work_shift",
            "duration",
            "drilling_ops",
            "drilling_ops_name",
            "drilling_section",
            "drilling_section_name",
            "depth_from",
            "depth_to",
            "rop_trip_mh",
            "operation_desc",
            "prj_drilling_rate",
            "rate_code",
        ]

    def validate(self, attrs):
        time_from = attrs.get("time_from")
        time_to = attrs.get("time_to")
        if time_from and time_to and time_to <= time_from:
            raise serializers.ValidationError("Time To must be after Time From.")
        return attrs


class DrillingDtlSerializer(serializers.ModelSerializer):
    rig_name = serializers.CharField(source="rig.rig_name", read_only=True, default="")
    location = serializers.CharField(source="drilling_hdr.location", read_only=True, default="")
    contract = serializers.IntegerField(source="drilling_hdr.contract_id", read_only=True, default=None)
    contract_no = serializers.CharField(source="drilling_hdr.contract.prj_contract_no", read_only=True, default="")
    ops = DrillingDtlOpsSerializer(many=True, required=False)

    class Meta:
        model = DrillingDtl
        fields = "__all__"
        read_only_fields = [
            "drilling_hdr",
            "operating_hrs",
            "standby_hrs",
            "repair_service_hrs",
            "repair_rate_hrs",
            "zero_rate_hrs",
            "rig_move_hrs",
            "drilling_meterage",
            "cr_status",
            "l1_approval_status",
            "l1_approval_dt",
            "l1_user_id",
            "opened_for_revision_by",
            "opened_for_revision_dt",
            "revision_note",
            "cr_user_id",
            "cr_dt",
            "mod_user_id",
            "mod_dt",
        ]

    def _duration_hours(self, time_from, time_to):
        delta = time_to - time_from
        return (Decimal(delta.total_seconds()) / Decimal(3600)).quantize(Decimal("0.01"))

    def _rop_trip(self, depth_from, depth_to, duration):
        # Sign kept deliberately — a decreasing depth (tripping out) gives a
        # real negative ROP in the legacy data, not an error condition.
        if not duration:
            return 0
        rop = (Decimal(depth_to) - Decimal(depth_from)) / duration
        return int(rop.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    @transaction.atomic
    def create(self, validated_data):
        from django.utils import timezone

        ops_data = validated_data.pop("ops", [])
        # cr_user_id/cr_dt arrive merged into validated_data via the view's
        # serializer.save(cr_user_id=..., cr_dt=...) call — reuse the same
        # stamp for every new Ops row rather than leaving its own NOT NULL
        # cr_user_id/cr_dt unset (DrillingDtlOps has no default for either).
        cr_user_id = validated_data.get("cr_user_id")
        cr_dt = validated_data.get("cr_dt", timezone.now())
        instance = DrillingDtl.objects.create(**validated_data)
        for row in ops_data:
            row.pop("drilling_dtl_ops_id", None)
            row["duration"] = self._duration_hours(row["time_from"], row["time_to"])
            row["rop_trip_mh"] = self._rop_trip(row["depth_from"], row["depth_to"], row["duration"])
            DrillingDtlOps.objects.create(drilling_dtl=instance, cr_user_id=cr_user_id, cr_dt=cr_dt, **row)
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        from django.utils import timezone

        ops_data = validated_data.pop("ops", None)
        mod_user_id = validated_data.get("mod_user_id")
        mod_dt = validated_data.get("mod_dt", timezone.now())
        # New rows added on an edit still need a cr_user_id/cr_dt of their
        # own — the record's original creator stamp doesn't apply to a row
        # that didn't exist then, so a new row is "created" by whoever is
        # editing right now, same as mod_user_id below.
        cr_user_id = mod_user_id if mod_user_id is not None else instance.cr_user_id
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if ops_data is not None:
            existing = {o.drilling_dtl_ops_id: o for o in instance.ops.all()}
            seen_ids = set()
            for row in ops_data:
                row_id = row.pop("drilling_dtl_ops_id", None)
                row["duration"] = self._duration_hours(row["time_from"], row["time_to"])
                row["rop_trip_mh"] = self._rop_trip(row["depth_from"], row["depth_to"], row["duration"])
                if row_id and row_id in existing:
                    op = existing[row_id]
                    for attr, value in row.items():
                        setattr(op, attr, value)
                    op.mod_user_id = mod_user_id
                    op.mod_dt = mod_dt
                    op.save()
                    seen_ids.add(row_id)
                else:
                    DrillingDtlOps.objects.create(
                        drilling_dtl=instance, cr_user_id=cr_user_id, cr_dt=mod_dt, **row
                    )
            for op_id, op in existing.items():
                if op_id not in seen_ids:
                    op.delete()

        return instance
