from .approvals_serializers import ApproverMappingSerializer
from .masters_views import BaseMasterViewSet
from .models import ApproverMapping


class ApproverMappingViewSet(BaseMasterViewSet):
    """Header (Approval Code / User / Level / Active) + a nested Rig/Dept
    scoping grid — a genuine master-detail form, unlike every other master
    here which is either a flat table or two separate flat masters. Built
    on BaseMasterViewSet for the same permission/pagination/audit/export
    plumbing as everything else; only the nested-row bookkeeping (in
    ApproverMappingSerializer) and the audit snapshot below are custom."""

    queryset = ApproverMapping.objects.select_related("approval_code", "approver_user").prefetch_related(
        "details__rig", "details__dept"
    )
    serializer_class = ApproverMappingSerializer
    entity_key = "admin.approver_mapping"
    # No plain name column on this model — get_queryset below supplies its
    # own ordering and label_for its own label, so this is only a fallback.
    name_field = "approver_mapping_id"
    active_field = "approver_active"
    search_fields = [
        "approval_code__approval_code",
        "approval_code__approval_desc",
        "approver_user__user_login_id",
        "approver_user__user_name",
    ]
    # details__rig lets the list be scoped to "everyone who can act on this
    # rig", a real admin question the nested grid alone can't answer at a
    # glance — a plain field-lookup filter, same mechanism as approval_code.
    filterable_fields = ["approval_code", "details__rig"]

    # Explicit allow-list rather than a raw ?ordering=<column> passthrough —
    # keeps client input from reaching order_by() directly and only exposes
    # orderings that make sense on this list (name_field has no real column
    # to fall back on here, unlike every other master).
    _ORDERINGS = {
        "approval_code": ("approval_code__approval_code", "approver_level", "approver_user__user_name"),
        "-approval_code": ("-approval_code__approval_code", "approver_level", "approver_user__user_name"),
        "level": ("approver_level", "approval_code__approval_code", "approver_user__user_name"),
        "-level": ("-approver_level", "approval_code__approval_code", "approver_user__user_name"),
        "user": ("approver_user__user_name", "approval_code__approval_code", "approver_level"),
        "-user": ("-approver_user__user_name", "approval_code__approval_code", "approver_level"),
    }

    def get_queryset(self):
        qs = self._apply_filterable_fields(self._apply_active_filter(self.queryset))
        # details__rig is a related-table lookup — matching headers can
        # otherwise repeat once per matching detail row.
        if self.request.query_params.get("details__rig"):
            qs = qs.distinct()
        ordering = self._ORDERINGS.get(self.request.query_params.get("ordering"))
        return qs.order_by(*(ordering or self._ORDERINGS["approval_code"]))

    def label_for(self, instance):
        return (
            f"{instance.approval_code.approval_code} — "
            f"{instance.approver_user.user_login_id} (L{instance.approver_level})"
        )

    def _snapshot(self, instance):
        # The header fields alone would make every real edit to this page —
        # adding/removing a rig, flipping an Approve flag — invisible in the
        # audit trail, since that's all nested detail-grid data. Appending a
        # lightweight summary of the current rows means a diff on this
        # record actually reflects what changed, at the cost of showing
        # "details changed" rather than a per-row breakdown.
        snap = super()._snapshot(instance)
        snap["details"] = [
            {
                "rig_id": d.rig_id,
                "dept_id": d.dept_id,
                "receive_mail": d.receive_mail,
                "approve_yn": d.approve_yn,
                "open_for_revision_yn": d.open_for_revision_yn,
                "create_yn": d.create_yn,
            }
            for d in instance.details.all().order_by("approver_mapping_dtl_id")
        ]
        return snap
