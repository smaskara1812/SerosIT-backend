from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .drilling_report import DOWNTIME_TRIGGER_CODES, RIG_MOVE_CODES, STANDBY_CODES
from .models import DrillingDtl, DrillingDtlOps
from .validation_helpers import fields_changed

# Numbers that can't be below 0 (the legacy "greater than or equal to 0" rules).
NON_NEGATIVE = (
    "at_press_mbar", "vdl", "avdl", "kg", "kg_margin", "draft", "consumption_diesel", "consumption_water",
    "received_diesel", "received_water", "generated_water",
)
# Plain wording for the database digit limits (KG 99.99, KG Margin 9.99, Draft 99.99, Current K 9.9).
_LIMIT_MESSAGES = {"kg": "KG can be at most 99.99.", "kg_margin": "KG Margin can be at most 9.99.", "draft": "Draft can be at most 99.99.", "current_k": "Current K can be at most 9.9."}
MIN_SUMMARY_LENGTH = 10
MAX_DAY_HOURS = 24


def _bucket(code):
    """Which of the six hour buckets a rate code belongs to (same mapping as recompute_dtl_totals), or None."""
    if code == "R1":
        return "operating"
    if code in STANDBY_CODES:
        return "standby"
    if code.startswith("Other"):
        return "service"
    if code == "R3":
        return "repair_rate"
    if code == "R0":
        return "zero_rate"
    if code in RIG_MOVE_CODES:
        return "rig_move"
    return None


def _ops_key(rows):
    """What identifies a time-log row for "did the time log change"."""
    return sorted(
        (
            str(getattr(r.get("time_from"), "isoformat", lambda: r.get("time_from"))()), str(getattr(r.get("time_to"), "isoformat", lambda: r.get("time_to"))()),
            getattr(r.get("drilling_ops"), "pk", None), getattr(r.get("drilling_section"), "pk", None),
            str(r.get("depth_from")), str(r.get("depth_to")), getattr(r.get("prj_drilling_rate"), "pk", None),
        )
        for r in rows
    )


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
    # Suppresses DRF's auto-generated UniqueTogetherValidator for the
    # model's UniqueConstraint(rig, drilling_dtl_dt) — its generic "The
    # fields rig, drilling_dtl_dt must make a unique set." would otherwise
    # fire before validate() below gets a chance to give the friendlier,
    # rig-name-and-date message.
    validators = []

    class Meta:
        model = DrillingDtl
        fields = "__all__"
        extra_kwargs = {
            **{name: {"min_value": 0} for name in NON_NEGATIVE},
            **{
                name: {**({"min_value": 0} if name in NON_NEGATIVE else {}), "error_messages": {"max_digits": msg, "max_whole_digits": msg, "max_value": msg}}
                for name, msg in _LIMIT_MESSAGES.items()
            },
        }
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

    def validate(self, attrs):
        # Friendly 400 for the normal UI path — DrillingDtl's own
        # UniqueConstraint(rig, drilling_dtl_dt) is the DB-level backstop
        # for anything that bypasses this serializer.
        rig = attrs.get("rig") or getattr(self.instance, "rig", None)
        report_date = attrs.get("drilling_dtl_dt") or getattr(self.instance, "drilling_dtl_dt", None)
        if rig and report_date:
            qs = DrillingDtl.objects.filter(rig=rig, drilling_dtl_dt=report_date)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"drilling_dtl_dt": f"A drilling report already exists for {rig.rig_name} on {report_date}."}
                )
        return self._legacy_rules(attrs)

    def _legacy_rules(self, attrs):
        """Rules from the legacy document. A rule about a value is only judged when that value is
        new or changed, so an old report stays editable for something else."""
        inst = self.instance
        errors = {}

        if report_date := attrs.get("drilling_dtl_dt"):
            if fields_changed(inst, attrs, "drilling_dtl_dt") and report_date > timezone.now().date():
                errors["drilling_dtl_dt"] = "The Drilling Date can't be in the future."

        if inst is None and attrs.get("received_water") is None:
            errors["received_water"] = "Enter the Received Water (0 if none)."

        if "remark" in attrs or inst is None:
            remark = (attrs.get("remark") or "").strip()
            if fields_changed(inst, attrs, "remark"):
                if not remark:
                    errors["remark"] = "Enter the Operations Summary."
                elif len(remark) < MIN_SUMMARY_LENGTH:
                    errors["remark"] = f"Give more detail in the Operations Summary (at least {MIN_SUMMARY_LENGTH} characters)."
            if "remark" in attrs:
                attrs["remark"] = remark

        if "ops" in attrs:
            rows = attrs["ops"]
            old_rows = [] if inst is None else [
                {"time_from": o.time_from, "time_to": o.time_to, "drilling_ops": o.drilling_ops, "drilling_section": o.drilling_section,
                 "depth_from": o.depth_from, "depth_to": o.depth_to, "prj_drilling_rate": o.prj_drilling_rate}
                for o in inst.ops.select_related("drilling_ops", "drilling_section", "prj_drilling_rate")
            ]
            if inst is None or _ops_key(rows) != _ops_key(old_rows):
                totals, downtime = {}, False
                for r in rows:
                    code = r["prj_drilling_rate"].drilling_rate.rate_code
                    if code in DOWNTIME_TRIGGER_CODES:
                        downtime = True
                    bucket = _bucket(code)
                    if bucket:
                        totals[bucket] = totals.get(bucket, 0) + self._duration_hours(r["time_from"], r["time_to"])
                total = sum(totals.values(), 0)
                if total > MAX_DAY_HOURS:
                    errors["ops"] = f"The hours in the time log add up to {total}; a day can't be more than {MAX_DAY_HOURS}."
                reason = (attrs.get("downtime_reason") if "downtime_reason" in attrs else getattr(inst, "downtime_reason", None)) or ""
                if downtime and not reason.strip():
                    errors["downtime_reason"] = "Enter the Downtime Reason (the time log has Repair Rate or Zero Rate time)."

        if errors:
            raise serializers.ValidationError(errors)
        return attrs

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


class DrillingDtlSlimSerializer(DrillingDtlSerializer):
    """Rows for the list and the bulk CSV export: the same fields without the
    nested Time Log, which is about three quarters of each row and is only needed
    when one report is opened. A CSV cell can't hold that grid either (it came out
    as a text dump), and a single report's own export (export_one) writes it properly."""

    ops = None
