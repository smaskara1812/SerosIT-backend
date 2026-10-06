"""QHSE → Corrective Actions Reporting — rebuild of legacy
frmOther_QHSE_Actions (table other_qhse_action, MstQhseCategory + Rig).

Rules ported from frmOther_QHSE_Actions.aspx(.cs):
  - Required: Category, ICR No., Date, Rig, Details of Findings, Action
    Party, Target Date. Action Planned/Taken is optional.
  - Date can't be in the future; Target Date and Actual Closure Date can't
    be before it.
  - New records are Open. Actual Closure Date and Action Status only exist
    once a record is being edited; entering a closure date closes it, and
    Closed with no closure date is refused.
  - A Closed record is locked: no update, no delete (legacy greyed out
    Update/Delete). The lock is enforced here, not just on the screen.
Excel export of the filtered list is an addition (legacy had none).
"""

from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from . import audit as _audit
from .masters_views import BaseMasterViewSet
from .models import OtherQhseAction
from .permissions import HasMenuPermission
from .xlsx_export import build_xlsx_response

ENTITY_KEY = "qhse.corrective_actions"
TITLE = "Corrective Actions Reporting"
STATUS_LABELS = {"OP": "Open", "IN": "In Process", "CL": "Closed"}
_AUDIT_READ_ONLY = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


def _fmt(d):
    return d.strftime("%d/%m/%Y") if d else ""


class CorrectiveActionSerializer(serializers.ModelSerializer):
    qhse_category_name = serializers.CharField(source="qhse_category.qhse_category_name", read_only=True)
    rig_name = serializers.CharField(source="rig.rig_name", read_only=True)
    action_status = serializers.ChoiceField(choices=list(STATUS_LABELS), required=False)
    icr_no = serializers.CharField(max_length=15)
    action_recommended = serializers.CharField(max_length=500)
    action_party = serializers.CharField(max_length=100)
    action_taken = serializers.CharField(max_length=250, required=False, allow_blank=True, allow_null=True)
    target_date = serializers.DateField(required=True, allow_null=False)

    class Meta:
        model = OtherQhseAction
        fields = "__all__"
        read_only_fields = _AUDIT_READ_ONLY

    def validate(self, attrs):
        inst = self.instance
        if inst and inst.action_status == "CL":
            raise serializers.ValidationError("This record is Closed and can no longer be edited.")

        def pick(name):
            return attrs[name] if name in attrs else getattr(inst, name, None)

        dt, target = pick("other_qhse_action_dt"), pick("target_date")
        if dt and (inst is None or "other_qhse_action_dt" in attrs and attrs["other_qhse_action_dt"] != inst.other_qhse_action_dt):
            if dt > timezone.now().date():
                raise serializers.ValidationError({"other_qhse_action_dt": "Date can't be in the future."})
        if dt and target and target < dt:
            raise serializers.ValidationError({"target_date": "Target Date can't be before the Date."})

        if inst is None:
            # Closure date and status only exist on an existing record.
            attrs.pop("completion_dt", None)
            attrs["action_status"] = "OP"
            return attrs

        completion = pick("completion_dt")
        if completion:
            if dt and completion < dt:
                raise serializers.ValidationError({"completion_dt": "Actual Closure Date can't be before the Date."})
            attrs["action_status"] = "CL"
        elif pick("action_status") == "CL":
            raise serializers.ValidationError({"completion_dt": "Enter the Actual Closure Date to close this record."})
        return attrs


class CorrectiveActionViewSet(BaseMasterViewSet):
    queryset = OtherQhseAction.objects.select_related("qhse_category", "rig")
    serializer_class = CorrectiveActionSerializer
    entity_key = ENTITY_KEY
    permission_classes = [HasMenuPermission]
    search_fields = ["icr_no", "action_recommended", "action_party", "rig__rig_name"]

    def get_queryset(self):
        qs = self.queryset
        p = self.request.query_params
        if p.get("category"):
            qs = qs.filter(qhse_category_id=p["category"])
        if p.get("rig"):
            qs = qs.filter(rig_id=p["rig"])
        if p.get("status") in STATUS_LABELS:
            qs = qs.filter(action_status=p["status"])
        return qs.order_by("-other_qhse_action_dt", "-other_qhse_action_id")

    def label_for(self, instance):
        return f"Corrective Action {instance.icr_no}"

    def destroy(self, request, *args, **kwargs):
        if self.get_object().action_status == "CL":
            return Response({"error": "A Closed record can't be deleted."}, status=400)
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        qs = self.filter_queryset(self.get_queryset())
        rows = [
            [
                a.icr_no, a.qhse_category.qhse_category_name, a.rig.rig_name, _fmt(a.other_qhse_action_dt),
                a.action_recommended, a.action_taken or "", a.action_party, _fmt(a.target_date),
                _fmt(a.completion_dt), STATUS_LABELS.get(a.action_status, a.action_status),
            ]
            for a in qs
        ]
        _audit.record_action(
            request, "export", self.entity_key, record_label=f"{TITLE} list export",
            changes={**{k: {"old": None, "new": v} for k, v in request.query_params.items() if v}, "rows_exported": {"old": None, "new": len(rows)}},
        )
        return build_xlsx_response(
            f"{TITLE}.xlsx", TITLE[:31], [TITLE],
            ["ICR No.", "Category", "Rig", "Date", "Details of Findings", "Action Planned/Taken", "Action Party", "Target Date", "Actual Closure Date", "Status"],
            rows, wide_columns=(4, 5, 6),
        )
