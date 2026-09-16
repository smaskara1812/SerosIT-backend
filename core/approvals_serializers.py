from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import ApproverMapping, ApproverMappingDtl


class ApproverMappingDtlSerializer(serializers.ModelSerializer):
    # Declared explicitly (not left to ModelSerializer's default) so it's
    # writable and optional — DRF treats an AutoField PK as read-only by
    # default, but the parent's update() needs existing rows' ids back to
    # tell an edit apart from a new row.
    approver_mapping_dtl_id = serializers.IntegerField(required=False)
    rig_name = serializers.CharField(source="rig.rig_name", read_only=True, default="")
    dept_name = serializers.CharField(source="dept.dept_dispname", read_only=True, default="")

    class Meta:
        model = ApproverMappingDtl
        fields = [
            "approver_mapping_dtl_id",
            "rig",
            "rig_name",
            "dept",
            "dept_name",
            "receive_mail",
            "approve_yn",
            "open_for_revision_yn",
            "create_yn",
        ]


class ApproverMappingSerializer(serializers.ModelSerializer):
    approval_code_name = serializers.CharField(
        source="approval_code.approval_code", read_only=True, default=""
    )
    approval_desc = serializers.CharField(
        source="approval_code.approval_desc", read_only=True, default=""
    )
    approver_user_name = serializers.CharField(
        source="approver_user.user_name", read_only=True, default=""
    )
    approver_login_id = serializers.CharField(
        source="approver_user.user_login_id", read_only=True, default=""
    )
    approver_email = serializers.CharField(
        source="approver_user.user_email", read_only=True, default=""
    )
    details = ApproverMappingDtlSerializer(many=True, required=False)

    class Meta:
        model = ApproverMapping
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    @transaction.atomic
    def create(self, validated_data):
        details_data = validated_data.pop("details", [])
        # cr_user_id/cr_dt arrive merged into validated_data via the view's
        # serializer.save(cr_user_id=..., cr_dt=...) call — DrillingDtlOps
        # hit this exact gap first (NOT NULL cr_user_id/cr_dt on the child
        # row, never stamped), and ApproverMappingDtl has the identical
        # column shape, so it carries the identical latent bug: every path
        # that only ever edited existing rows never triggered it.
        cr_user_id = validated_data.get("cr_user_id")
        cr_dt = validated_data.get("cr_dt", timezone.now())
        instance = ApproverMapping.objects.create(**validated_data)
        for row in details_data:
            row.pop("approver_mapping_dtl_id", None)
            ApproverMappingDtl.objects.create(approver_mapping=instance, cr_user_id=cr_user_id, cr_dt=cr_dt, **row)
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        details_data = validated_data.pop("details", None)
        mod_user_id = validated_data.get("mod_user_id")
        mod_dt = validated_data.get("mod_dt", timezone.now())
        cr_user_id = mod_user_id if mod_user_id is not None else instance.cr_user_id
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if details_data is not None:
            # Sync the grid: rows carrying an id that belongs to this
            # mapping are updates, ids that don't appear are deletions,
            # everything else (no id, or an id from elsewhere) is a new
            # row — scoping the lookup to instance.details.all() means a
            # spoofed/foreign id can never edit another mapping's rows.
            existing = {d.approver_mapping_dtl_id: d for d in instance.details.all()}
            seen_ids = set()
            for row in details_data:
                row_id = row.pop("approver_mapping_dtl_id", None)
                if row_id and row_id in existing:
                    dtl = existing[row_id]
                    for attr, value in row.items():
                        setattr(dtl, attr, value)
                    dtl.mod_user_id = mod_user_id
                    dtl.mod_dt = mod_dt
                    dtl.save()
                    seen_ids.add(row_id)
                else:
                    ApproverMappingDtl.objects.create(
                        approver_mapping=instance, cr_user_id=cr_user_id, cr_dt=mod_dt, **row
                    )
            for dtl_id, dtl in existing.items():
                if dtl_id not in seen_ids:
                    dtl.delete()

        return instance
