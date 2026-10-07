"""QHSE → Training Group — rebuild of legacy frmHSE_Training_Group_Hdr
(a named group, and the ranks in it with whether training is mandatory).

Rules ported from frmHSE_Training_Group_Hdr.aspx(.cs) and its stored procedure:
  - A group is created from its name alone (up to 30 characters) and starts
    Active. Afterwards the name is locked and only Active can change.
  - Switching a group to inactive switches all its ranks off; an inactive
    group can't be changed again (legacy greys out Update) — so nothing can
    be added to, or switched back on in, an inactive group.
  - A rank row is Category + Rank + Mandatory Training (Yes/No). Ranks come
    from the category-to-rank mapping, and a rank already in the group under
    that category isn't offered again. Existing rows can change Mandatory and
    Active, or be deleted.
  - Category choices are limited to the categories mapped to the signed-in
    user (an App Admin sees all). Legacy did the same.
  - Deleting a group deletes its rank rows (legacy deleted only the group).
Legacy rows repeat some ranks within a group and one has a blank Mandatory
flag; they were imported untouched, and only new rows are held to the rules.
Excel export of the groups and their ranks is an addition.
"""

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from . import audit as _audit
from .masters_views import BaseMasterViewSet
from .models import (
    FsCatgToRankMapping,
    HseTrainingGroupDtl,
    HseTrainingGroupHdr,
    MstFsCategory,
    MstUserFsCatgMapping,
    UserProfile,
)
from .permissions import HasMenuPermission, get_user_access
from .xlsx_export import build_xlsx_response

ENTITY_KEY = "qhse.training_group"
TITLE = "Training Group"
_AUDIT_READ_ONLY = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]
YES_NO = ("Y", "N")


def allowed_category_ids(request):
    """None means every category (App Admin); otherwise the ids mapped to
    this user today."""
    if get_user_access(request)["is_admin"]:
        return None
    profile = UserProfile.objects.filter(user_login_id=request.user.username).first()
    if not profile:
        return []
    today = timezone.now().date()
    return list(
        MstUserFsCatgMapping.objects.filter(user_id=profile.user_id, mapping_from__lte=today)
        .filter(Q(mapping_to__isnull=True) | Q(mapping_to__gte=today))
        .values_list("fs_category_id", flat=True)
    )


def _taken_rank_ids(hdr_id, category_id):
    return HseTrainingGroupDtl.objects.filter(hdr_id=hdr_id, fs_category_id=category_id).values_list("rank_id", flat=True)


class TrainingGroupHdrSerializer(serializers.ModelSerializer):
    training_group_hdr_name = serializers.CharField(max_length=30)
    training_group_hdr_active = serializers.ChoiceField(choices=YES_NO, required=False)
    dtl_count = serializers.IntegerField(read_only=True, default=0)
    active_dtl_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = HseTrainingGroupHdr
        fields = "__all__"
        read_only_fields = _AUDIT_READ_ONLY

    def validate_training_group_hdr_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("This field is required.")
        return value

    def validate(self, attrs):
        inst = self.instance
        if inst is None:
            attrs["training_group_hdr_active"] = "Y"
            return attrs
        if inst.training_group_hdr_active != "Y":
            raise serializers.ValidationError("This group is inactive and can no longer be changed.")
        if "training_group_hdr_name" in attrs and attrs["training_group_hdr_name"] != inst.training_group_hdr_name:
            raise serializers.ValidationError({"training_group_hdr_name": "The group name can't be changed once it is saved."})
        return attrs


class TrainingGroupHdrViewSet(BaseMasterViewSet):
    queryset = HseTrainingGroupHdr.objects.annotate(
        dtl_count=Count("dtls"), active_dtl_count=Count("dtls", filter=Q(dtls__training_group_dtl_active="Y"))
    )
    serializer_class = TrainingGroupHdrSerializer
    entity_key = ENTITY_KEY
    name_field = "training_group_hdr_name"
    active_field = "training_group_hdr_active"
    permission_classes = [HasMenuPermission]
    search_fields = ["training_group_hdr_name"]

    def label_for(self, instance):
        return f"Training Group {instance.training_group_hdr_name}"

    def perform_update(self, serializer):
        was_active = serializer.instance.training_group_hdr_active == "Y"
        super().perform_update(serializer)
        inst = serializer.instance
        if was_active and inst.training_group_hdr_active == "N":
            uid = self._current_user_id(self.request)
            count = HseTrainingGroupDtl.objects.filter(hdr=inst, training_group_dtl_active="Y").update(
                training_group_dtl_active="N", mod_user_id=uid, mod_dt=timezone.now()
            )
            if count:
                _audit.record_action(
                    self.request, "update", self.entity_key, inst.pk, self.label_for(inst),
                    {"ranks_switched_off": {"old": count, "new": 0}},
                )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        count = instance.dtl_count
        label, pk = self.label_for(instance), instance.pk
        instance.delete()
        _audit.record_action(
            request, "delete", self.entity_key, pk, label, {"ranks_deleted": {"old": count, "new": 0}} if count else None
        )
        return Response(status=204)

    @action(detail=False, methods=["get"], url_path="categories")
    def categories(self, request):
        """Categories this user may add ranks under."""
        qs = MstFsCategory.objects.order_by("fs_category_name")
        allowed = allowed_category_ids(request)
        if allowed is not None:
            qs = qs.filter(pk__in=allowed)
        return Response([{"id": c.pk, "name": c.fs_category_name} for c in qs])

    @action(detail=True, methods=["get"], url_path="ranks")
    def ranks(self, request, pk=None):
        """Ranks pickable for this group under ?category=: mapped to that
        category and not already in the group under it."""
        hdr = self.get_object()
        category = request.query_params.get("category")
        if not (category and category.isdigit()):
            return Response({"error": "?category= is required"}, status=400)
        allowed = allowed_category_ids(request)
        if allowed is not None and int(category) not in allowed:
            return Response([])
        mapped = (
            FsCatgToRankMapping.objects.filter(fs_category_id=category)
            .exclude(rank_id__in=_taken_rank_ids(hdr.pk, category))
            .select_related("rank")
            .order_by("rank__rank_name")
        )
        seen, out = set(), []
        for m in mapped:
            if m.rank_id not in seen:
                seen.add(m.rank_id)
                out.append({"id": m.rank_id, "name": m.rank.rank_name})
        return Response(out)

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        qs = self.filter_queryset(self.get_queryset())
        rows = []
        for h in qs:
            status = "Active" if h.training_group_hdr_active == "Y" else "Inactive"
            dtls = list(h.dtls.select_related("fs_category", "rank").order_by("rank__rank_name"))
            if not dtls:
                rows.append([h.training_group_hdr_name, status, "", "", "", ""])
            for d in dtls:
                rows.append([
                    h.training_group_hdr_name, status, d.fs_category.fs_category_name, d.rank.rank_name,
                    {"Y": "Yes", "N": "No"}.get(d.mandatory_training, ""), "Yes" if d.training_group_dtl_active == "Y" else "No",
                ])
        _audit.record_action(
            request, "export", self.entity_key, record_label=f"{TITLE} list export",
            changes={**{k: {"old": None, "new": v} for k, v in request.query_params.items() if v}, "rows_exported": {"old": None, "new": len(rows)}},
        )
        return build_xlsx_response(
            f"{TITLE}.xlsx", TITLE, [TITLE], ["Group", "Group Status", "Category", "Rank", "Mandatory Training", "Rank Active"], rows,
        )


class TrainingGroupDtlSerializer(serializers.ModelSerializer):
    fs_category_name = serializers.CharField(source="fs_category.fs_category_name", read_only=True)
    rank_name = serializers.CharField(source="rank.rank_name", read_only=True)
    mandatory_training = serializers.ChoiceField(choices=YES_NO, required=False)
    training_group_dtl_active = serializers.ChoiceField(choices=YES_NO, required=False)
    is_repeat = serializers.SerializerMethodField()

    class Meta:
        model = HseTrainingGroupDtl
        fields = "__all__"
        read_only_fields = _AUDIT_READ_ONLY
        validators = []

    def get_is_repeat(self, obj):
        return HseTrainingGroupDtl.objects.filter(hdr_id=obj.hdr_id, fs_category_id=obj.fs_category_id, rank_id=obj.rank_id).count() > 1

    def validate(self, attrs):
        inst = self.instance
        if inst is not None:
            for locked in ("hdr", "fs_category", "rank"):
                if locked in attrs and attrs[locked] != getattr(inst, locked):
                    raise serializers.ValidationError({locked: "Can't be changed — delete the row and add it again."})
            if inst.hdr.training_group_hdr_active != "Y":
                raise serializers.ValidationError("This group is inactive and can no longer be changed.")
            return attrs

        hdr, category, rank = attrs["hdr"], attrs["fs_category"], attrs["rank"]
        if hdr.training_group_hdr_active != "Y":
            raise serializers.ValidationError("This group is inactive — ranks can't be added to it.")
        if not attrs.get("mandatory_training"):
            raise serializers.ValidationError({"mandatory_training": "This field is required."})
        allowed = allowed_category_ids(self.context["request"])
        if allowed is not None and category.pk not in allowed:
            raise serializers.ValidationError({"fs_category": "You don't have access to this category."})
        if not FsCatgToRankMapping.objects.filter(fs_category=category, rank=rank).exists():
            raise serializers.ValidationError({"rank": "This rank doesn't belong to the chosen category."})
        if rank.pk in _taken_rank_ids(hdr.pk, category.pk):
            raise serializers.ValidationError({"rank": "This rank is already in the group under this category."})
        attrs["training_group_dtl_active"] = "Y"
        return attrs


class TrainingGroupDtlViewSet(BaseMasterViewSet):
    queryset = HseTrainingGroupDtl.objects.select_related("hdr", "fs_category", "rank")
    serializer_class = TrainingGroupDtlSerializer
    entity_key = ENTITY_KEY
    permission_classes = [HasMenuPermission]
    # A rank row is part of editing the group, so Edit is enough as well.
    action_perm_overrides = {"create": ("add", "edit"), "destroy": ("edit", "delete")}

    def get_queryset(self):
        qs = self.queryset
        if self.request.query_params.get("hdr"):
            qs = qs.filter(hdr_id=self.request.query_params["hdr"])
        return qs.order_by("rank__rank_name", "training_group_dtl_id")

    def label_for(self, instance):
        return f"{instance.hdr.training_group_hdr_name} — {instance.rank.rank_name}"
