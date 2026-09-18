import csv
import functools

from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import approvals, mail_recipients, mail_templates, mailer
from .drilling_dtl_serializers import DrillingDtlSerializer
from .drilling_report import recompute_dtl_totals, resolve_drilling_hdr
from .masters_views import BaseMasterViewSet
from .models import ApproverMappingDtl, DrillingDtl, MailRecipientMapping, MstUser, MstUserRigMapping, UserMailCredential

APPROVAL_CODE = "DRILLING_DTL"


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_rigs_api(request):
    """Rigs the current user can pick on the Drilling Report form's Rig
    field — scoped to their own MstUserRigMapping, same "Filter the Rig"
    rule the original Drilling Information doc asked to apply "now
    onward" to every later form, not just that one."""
    from .models import MstRig, UserProfile

    if request.user.is_superuser:
        rigs = MstRig.objects.filter(rig_active="Y").order_by("rig_name")
    else:
        try:
            uid = UserProfile.objects.get(user_login_id=request.user.username).user_id
        except UserProfile.DoesNotExist:
            uid = None
        if uid is None:
            rigs = MstRig.objects.none()
        else:
            rig_ids = MstUserRigMapping.objects.filter(user_id=uid, mapping_to__isnull=True).values_list(
                "rig_id", flat=True
            )
            rigs = MstRig.objects.filter(rig_id__in=set(rig_ids)).order_by("rig_name")
    return Response([{"rig_id": r.rig_id, "rig_name": r.rig_name} for r in rigs])


_EMPTY_WELL = {
    "drilling_hdr": None,
    "location": "",
    "contract": None,
    "contract_no": "",
    "drilling_completion_dt": None,
    "suggested_date": None,
}


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def resolve_well_api(request):
    """?rig=<id>&date=<yyyy-mm-dd optional> — what Rig(+Date) on the
    Drilling Report form resolves to, so the frontend can show
    Location/Project live before the record is ever saved (the form has no
    Project field of its own, same as the legacy screen).

    date omitted (picking a Rig for a brand-new report): resolves to
    whichever well for that rig is still actively drilling
    (drilling_completion_dt IS NULL) — falling back to the rig's most
    recently started well if every one of its wells is already completed —
    and suggests the next Drilling Date as (latest existing Drilling Dtl
    for that well + 1 day), or the well's own spud date if it has no daily
    reports yet.

    date given (editing an existing report, or backfilling a past date):
    resolves whichever well actually covers that date, same as before."""
    from django.db.models import Max

    from .models import DrillingHdr

    rig_id = request.query_params.get("rig")
    date = request.query_params.get("date")
    if not rig_id:
        return Response(_EMPTY_WELL)

    if date:
        hdr = resolve_drilling_hdr(rig_id, date)
    else:
        hdr = (
            DrillingHdr.objects.filter(rig_id=rig_id, drilling_completion_dt__isnull=True)
            .order_by("-first_anchor_down_dt")
            .first()
            or DrillingHdr.objects.filter(rig_id=rig_id).order_by("-first_anchor_down_dt").first()
        )
    if not hdr:
        return Response(_EMPTY_WELL)

    last_dtl_date = DrillingDtl.objects.filter(drilling_hdr_id=hdr.pk).aggregate(m=Max("drilling_dtl_dt"))["m"]
    if last_dtl_date:
        suggested_date = last_dtl_date + timezone.timedelta(days=1)
    else:
        suggested_date = hdr.first_anchor_down_dt.date()

    return Response(
        {
            "drilling_hdr": hdr.drilling_hdr_id,
            "location": hdr.location,
            "contract": hdr.contract_id,
            "contract_no": hdr.contract.prj_contract_no if hdr.contract_id else "",
            "drilling_completion_dt": hdr.drilling_completion_dt.date().isoformat() if hdr.drilling_completion_dt else None,
            "suggested_date": suggested_date.isoformat(),
        }
    )


class DrillingDtlViewSet(BaseMasterViewSet):
    """Drilling Report / Daily Report — one row per rig, per day, with a
    nested Ops time-log grid. Rig+Date resolve the well (DrillingHdr)
    automatically, same as the legacy form's own Location/Spud Date
    auto-fill. Approval actions (finalize/approve/revise) are separate
    detail actions below rather than plain field edits, since each one is
    gated by a real role check via core/approvals.py, not just "can this
    user edit this master.\""""

    queryset = DrillingDtl.objects.select_related("rig", "drilling_hdr", "drilling_hdr__contract").prefetch_related(
        "ops__drilling_ops", "ops__drilling_section", "ops__prj_drilling_rate__drilling_rate"
    )
    serializer_class = DrillingDtlSerializer
    entity_key = "drilling.drilling_report"
    name_field = "drilling_dtl_id"
    search_fields = ["rig__rig_name", "remark"]
    filterable_fields = ["rig"]

    def _user_rig_ids(self, request):
        """Visible rigs = rigs the user is directly mapped to (their own
        reporting scope) UNION rigs they hold any approver-mapping
        capability on (create/approve/revise) — an approver needs to see
        records for rigs they can act on even if they aren't themselves
        rig-mapped, e.g. to see rejected records "in their scope" that a
        counterpart approver rejected."""
        if request.user.is_superuser:
            return None
        uid = self._current_user_id(request)
        if uid is None:
            return None
        mapped_rig_ids = set(
            MstUserRigMapping.objects.filter(user_id=uid, mapping_to__isnull=True).values_list("rig_id", flat=True)
        )
        approver_rig_ids = set(
            ApproverMappingDtl.objects.filter(
                approver_mapping__approval_code__approval_code=APPROVAL_CODE,
                approver_mapping__approver_user_id=uid,
                approver_mapping__approver_active="Y",
            ).values_list("rig_id", flat=True)
        )
        return mapped_rig_ids | approver_rig_ids

    # Explicit allow-list rather than a raw ?ordering=<column> passthrough —
    # same reasoning as ProjectDrillingRateViewSet's own ILM param: never
    # let client input reach order_by() directly.
    _ORDERINGS = {
        "date": ("drilling_dtl_dt",),
        "-date": ("-drilling_dtl_dt",),
        "rig": ("rig__rig_name", "drilling_dtl_dt"),
        "-rig": ("-rig__rig_name", "drilling_dtl_dt"),
        "operating_hrs": ("operating_hrs", "-drilling_dtl_dt"),
        "-operating_hrs": ("-operating_hrs", "-drilling_dtl_dt"),
        "meterage": ("drilling_meterage", "-drilling_dtl_dt"),
        "-meterage": ("-drilling_meterage", "-drilling_dtl_dt"),
    }

    def get_queryset(self):
        qs = self._apply_filterable_fields(self.queryset)
        request = self.request
        my_rigs = self._user_rig_ids(request)
        if my_rigs is not None:
            qs = qs.filter(rig_id__in=my_rigs)

        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        if date_from:
            qs = qs.filter(drilling_dtl_dt__gte=date_from)
        if date_to:
            qs = qs.filter(drilling_dtl_dt__lte=date_to)

        status = request.query_params.get("status")
        if status == "draft":
            qs = qs.filter(Q(cr_status__isnull=True) | Q(cr_status=""))
        elif status == "sent_for_revision":
            qs = qs.filter(cr_status="N")
        elif status == "pending":
            qs = qs.filter(cr_status="F").filter(Q(l1_approval_status__isnull=True) | Q(l1_approval_status__in=("", "N")))
        elif status == "approved":
            qs = qs.filter(cr_status="F", l1_approval_status="A")
        elif status == "rejected":
            qs = qs.filter(cr_status="F", l1_approval_status="R")

        scope = request.query_params.get("scope")
        uid = self._current_user_id(request)
        if scope == "pending_for_me" and uid is not None:
            approver_rig_ids = ApproverMappingDtl.objects.filter(
                approver_mapping__approval_code__approval_code=APPROVAL_CODE,
                approver_mapping__approver_user_id=uid,
                approver_mapping__approver_active="Y",
                approve_yn="Y",
            ).values_list("rig_id", flat=True)
            qs = qs.filter(rig_id__in=set(approver_rig_ids), cr_status="F").filter(
                Q(l1_approval_status__isnull=True) | Q(l1_approval_status__in=("", "N"))
            )
        elif scope == "approved_by_me" and uid is not None:
            qs = qs.filter(l1_user_id=uid, l1_approval_status="A")

        ordering = self._ORDERINGS.get(request.query_params.get("ordering"))
        return qs.order_by(*(ordering or ("-drilling_dtl_dt",)))

    def label_for(self, instance):
        return f"{instance.rig.rig_name} — {instance.drilling_dtl_dt}"

    def _snapshot(self, instance):
        # Same reasoning as ApproverMapping's own override — the Ops grid is
        # where the real day-to-day edits happen, and the header fields
        # alone would make every one of them invisible in the audit trail.
        snap = super()._snapshot(instance)
        snap["ops"] = [
            {
                "time_from": o.time_from.isoformat(),
                "time_to": o.time_to.isoformat(),
                "drilling_ops_id": o.drilling_ops_id,
                "drilling_section_id": o.drilling_section_id,
                "prj_drilling_rate_id": o.prj_drilling_rate_id,
                "duration": str(o.duration),
            }
            for o in instance.ops.all().order_by("drilling_dtl_ops_id")
        ]
        return snap

    def perform_create(self, serializer):
        uid = self._current_user_id(self.request)
        rig_id = serializer.validated_data.get("rig").rig_id if serializer.validated_data.get("rig") else None
        report_date = serializer.validated_data.get("drilling_dtl_dt")
        hdr = resolve_drilling_hdr(rig_id, report_date) if rig_id and report_date else None
        instance = serializer.save(cr_user_id=uid or 1, cr_dt=timezone.now(), drilling_hdr=hdr)
        recompute_dtl_totals(instance, uid)
        changes = {k: {"old": None, "new": v} for k, v in self._snapshot(instance).items() if v not in (None, "")}
        from . import audit as _audit

        _audit.record_action(self.request, "create", self.entity_key, instance.pk, self.label_for(instance), changes or None)

    def perform_update(self, serializer):
        old_snapshot = self._snapshot(serializer.instance)
        uid = self._current_user_id(self.request)
        rig = serializer.validated_data.get("rig") or serializer.instance.rig
        report_date = serializer.validated_data.get("drilling_dtl_dt") or serializer.instance.drilling_dtl_dt
        hdr = resolve_drilling_hdr(rig.rig_id, report_date)
        instance = serializer.save(mod_user_id=uid, mod_dt=timezone.now(), drilling_hdr=hdr)
        recompute_dtl_totals(instance, uid)
        changes = self._diff(old_snapshot, self._snapshot(instance))
        from . import audit as _audit

        _audit.record_action(self.request, "update", self.entity_key, instance.pk, self.label_for(instance), changes or None)

    def _role(self, instance):
        uid = self._current_user_id(self.request)
        if self.request.user.is_superuser:
            return {"create": True, "approve": True, "revise": True, "receive_mail": False, "level": 0}
        return approvals.get_role(APPROVAL_CODE, uid, instance.rig_id)

    @action(detail=True, methods=["get"], url_path="export")
    def export_one(self, request, pk=None):
        """A single report's own CSV — the collection-level /export/ (free
        from BaseMasterViewSet) only ever emits flat header rows, one per
        record, with no sensible way to fit a record's own Time Log grid
        into that shape. This is the shape someone actually wants for one
        specific day: the header fields as a key/value block, then the full
        Ops grid as its own table underneath, in one file."""
        instance = self.get_object()
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        filename = f"drilling-report-{instance.rig.rig_name}-{instance.drilling_dtl_dt}.csv"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response.write("﻿")  # BOM — see BaseMasterViewSet.export()'s own note on this.
        writer = csv.writer(response)

        writer.writerow(["Field", "Value"])
        header_rows = [
            ("Rig", instance.rig.rig_name),
            ("Drilling Date", instance.drilling_dtl_dt),
            ("Location", instance.drilling_hdr.location if instance.drilling_hdr_id else ""),
            ("Project", instance.drilling_hdr.contract.prj_contract_no if instance.drilling_hdr_id and instance.drilling_hdr.contract_id else ""),
            ("POB Operator", instance.pob_operator),
            ("POB Seros", instance.pob_essar),
            ("POB Seros Serv", instance.pob_essar_serv),
            ("POB Others", instance.pob_others),
            ("Wind Speed (kts)", instance.wind_speed),
            ("Current K (kts)", instance.current_k),
            ("At Press (mbar)", instance.at_press_mbar),
            ("VDL (MT)", instance.vdl),
            ("AVDL (MT)", instance.avdl),
            ("Total VDL (MT)", instance.tot_vdl),
            ("KG (Mtr)", instance.kg),
            ("KG Margin (Mtr)", instance.kg_margin),
            ("Draft (Mtr)", instance.draft),
            ("Consumption Diesel (L)", instance.consumption_diesel),
            ("Consumption Water (L)", instance.consumption_water),
            ("Received Diesel (L)", instance.received_diesel),
            ("Received Water (L)", instance.received_water),
            ("Generated Water (L)", instance.generated_water),
            ("Operating Hrs", instance.operating_hrs),
            ("Standby Hrs", instance.standby_hrs),
            ("Service Hrs", instance.repair_service_hrs),
            ("Repair Rate Hrs", instance.repair_rate_hrs),
            ("Zero Rate Hrs", instance.zero_rate_hrs),
            ("Rig Move Hrs", instance.rig_move_hrs),
            ("Drilling Meterage", instance.drilling_meterage),
            ("Operations Summary", instance.remark),
            ("Downtime Reason", instance.downtime_reason),
            ("Status", "Approved" if instance.l1_approval_status == "A" else "Rejected" if instance.l1_approval_status == "R"
                else "Pending approval" if instance.cr_status == "F"
                else "Sent for revision" if instance.cr_status == "N" else "Draft"),
        ]
        for label, value in header_rows:
            writer.writerow([label, value if value is not None else ""])

        writer.writerow([])
        writer.writerow(["Time Log"])
        writer.writerow(
            ["From", "To", "Shift", "Duration", "Operation", "Section", "Depth From", "Depth To", "ROP/Trip", "Remarks", "Rate"]
        )
        for op in instance.ops.select_related("drilling_ops", "drilling_section", "prj_drilling_rate__drilling_rate").order_by(
            "time_from"
        ):
            writer.writerow(
                [
                    op.time_from.strftime("%H:%M"),
                    op.time_to.strftime("%H:%M"),
                    op.get_work_shift_display(),
                    op.duration,
                    op.drilling_ops.drilling_ops_name,
                    op.drilling_section.drilling_section_name,
                    op.depth_from,
                    op.depth_to,
                    op.rop_trip_mh,
                    op.operation_desc,
                    op.prj_drilling_rate.drilling_rate.rate_code,
                ]
            )

        from . import audit as _audit

        _audit.record_action(request, "export", self.entity_key, instance.pk, self.label_for(instance))
        return response

    @action(detail=True, methods=["get"], url_path="role")
    def role(self, request, pk=None):
        """What the current user is allowed to do on this record — drives
        which action buttons the frontend shows (a courtesy only; every
        action below re-checks this same gate server-side regardless)."""
        instance = self.get_object()
        caps = self._role(instance)
        return Response(
            {
                "can_finalize": approvals.can_finalize(instance, caps),
                "can_approve": approvals.can_approve(instance, caps),
                "can_reject": approvals.can_reject(instance, caps),
                "can_revise_self": approvals.can_revise_self(instance, caps),
                "can_revise_previous": approvals.can_revise_previous(instance, caps),
                "can_edit_as_approver": approvals.can_edit_as_approver(instance, caps),
            }
        )

    def _do_transition(self, request, pk, gate, apply_fn, action_label, notify_event=None):
        instance = self.get_object()
        caps = self._role(instance)
        if not gate(instance, caps):
            return Response({"error": "You don't have permission to do that on this record."}, status=403)
        uid = self._current_user_id(request)
        old_snapshot = self._snapshot(instance)
        apply_fn(instance, uid)
        instance.save()
        from . import audit as _audit

        changes = self._diff(old_snapshot, self._snapshot(instance))
        _audit.record_action(request, action_label, self.entity_key, instance.pk, self.label_for(instance), changes or None)
        if notify_event:
            transaction.on_commit(lambda: self._notify_mail(instance, uid, notify_event))
        return Response(self.get_serializer(instance).data)

    def _notify_mail(self, instance, actor_user_id, event_type):
        """Fires the approval-notification email for one transition — see
        core/mail_recipients.py for who gets it, core/mailer.py for how it's
        actually sent (queued on a background thread, never blocks this
        request). A missing cached credential or a resolver returning no
        recipients is a silent no-op here, not an error — mailer.py's own
        fallback path and EmailLog cover visibility from here on."""
        if actor_user_id is None:
            return
        recipients = mail_recipients.resolve_drilling_mail(event_type, instance.rig_id, instance.cr_user_id, actor_user_id)
        if not (recipients["to"] or recipients["cc"] or recipients["bcc"]):
            return

        actor = MstUser.objects.select_related("emp").filter(user_id=actor_user_id).first()
        cred = UserMailCredential.objects.filter(user_id=actor_user_id).first()
        label = dict(MailRecipientMapping.EVENT_CHOICES).get(event_type, event_type)
        subject, body = mail_templates.drilling_report_mail(instance, actor, event_type)
        mailer.queue_notification_email(
            subject=subject,
            body=body,
            is_html=True,
            to=recipients["to"],
            cc=recipients["cc"],
            bcc=recipients["bcc"],
            from_email=actor.user_email if actor else None,
            auth_user=actor.user_login_id if actor else None,
            auth_password=cred.password if cred else None,
            trigger=f"Drilling Report #{instance.drilling_dtl_id} {label}",
            trigger_code=f"drilling_report.{event_type.lower()}",
            sent_by_user_id=actor_user_id,
        )

    @action(detail=True, methods=["post"], url_path="finalize")
    def finalize(self, request, pk=None):
        return self._do_transition(
            request, pk, approvals.can_finalize, approvals.finalize, "finalize",
            notify_event=MailRecipientMapping.EVENT_FINALIZE,
        )

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        return self._do_transition(
            request, pk, approvals.can_approve, approvals.approve, "approve",
            notify_event=MailRecipientMapping.EVENT_APPROVE,
        )

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        return self._do_transition(
            request, pk, approvals.can_reject, approvals.reject, "reject",
            notify_event=MailRecipientMapping.EVENT_REJECT,
        )

    @action(detail=True, methods=["post"], url_path="revise-self")
    def revise_self(self, request, pk=None):
        # No mail — the approver is just reopening the record for their own
        # editing, it hasn't moved to anyone else.
        return self._do_transition(request, pk, approvals.can_revise_self, approvals.revise_self, "revise_self")

    @action(detail=True, methods=["post"], url_path="revise-previous")
    def revise_previous(self, request, pk=None):
        note = request.data.get("note")
        apply_fn = functools.partial(approvals.revise_previous, note=note)
        return self._do_transition(
            request, pk, approvals.can_revise_previous, apply_fn, "revise_previous",
            notify_event=MailRecipientMapping.EVENT_REVISE_PREVIOUS,
        )
