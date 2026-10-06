"""QHSE → HSE - Leading Indicators (legacy frmLeading_Indicators_Hdr and
Prc_Leading_Indicators_Hdr). Standalone — it shares no code with the Lagging
page (core/hse_lagging_indicators.py), only the common masters/helpers.

Rules ported from legacy:
  - Add saves the header and creates its detail rows from the current
    Workgroup→Indicator Type mapping, limited to indicator types whose Report
    Type is "Leading"; every subtype of a type gets its own row (a type with
    none gets one row), ordered by workgroup, indicator type, subtype order.
    Rows are fixed at Add — later master changes never touch an existing report.
  - The header can't be edited afterwards; only the detail rows (sessions,
    persons, duration + type, active) change, saved in one go.
  - Period is a month and can't be in the future; Report No. (max 12, letters/
    digits allowed) must be unique — confirmed with the user (duplicate rig +
    period is fine).
  - Total Duration > 0 requires a Duration Type (Hrs/Wks); 0 clears it.
Deliberate changes: Company is looked up from Rig + Period with the shared
company_branding resolver and stays editable (legacy hardcoded a default);
Delete (permission-gated) and Excel export are provided though legacy has
neither.
"""

from datetime import date

from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.validators import UniqueValidator

from . import audit as _audit
from .company_branding import _resolve_company_name, resolve_rig_company_branding
from .masters_views import BaseMasterViewSet
from .models import LeadingIndicatorsDtl, LeadingIndicatorsHdr, MstIndicatorSubtype, WkgrpIndicatorTypeMapping
from .permissions import HasMenuPermission
from .xlsx_export import build_xlsx_response

ENTITY_KEY = "qhse.leading_indicators"
TITLE = "HSE - Leading Indicators"
REPORT_TYPE = "Leading"
MAX_COUNT = 99999
DURATION_LABELS = {"H": "Hrs", "W": "Wks"}
COUNT_FIELDS = (
    ("total_sessions", "Total Sessions"),
    ("no_of_persons", "No. Of Persons"),
    ("total_duration", "Total Duration"),
)
_AUDIT_READ_ONLY = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


def _parse_period(value):
    try:
        y, m = value.split("-")
        return date(int(y), int(m), 1)
    except (AttributeError, ValueError):
        raise serializers.ValidationError("Period must be a valid month and year.")


def _dtl_label(row):
    sub = row.indicator_subtype.indicator_subtype_name if row.indicator_subtype_id else None
    return row.indicator_type.indicator_type_name + (f" / {sub}" if sub else "")


def _create_detail_rows(hdr, uid):
    mappings = (
        WkgrpIndicatorTypeMapping.objects.filter(indicator_type__report_type=REPORT_TYPE)
        .select_related("workgroup", "indicator_type")
        .order_by("workgroup__workgroup_order", "indicator_type__indicator_type_order", "wkgrp_ind_type_map_id")
    )
    subtypes_by_type = {}
    for st in MstIndicatorSubtype.objects.order_by("indicator_subtype_order", "indicator_subtype_id"):
        subtypes_by_type.setdefault(st.indicator_type_id, []).append(st)
    now = timezone.now()
    rows = [
        LeadingIndicatorsDtl(
            hdr=hdr, workgroup=m.workgroup, indicator_type=m.indicator_type, indicator_subtype=st,
            cr_user_id=uid or 1, cr_dt=now,
        )
        for m in mappings
        for st in subtypes_by_type.get(m.indicator_type_id, [None])
    ]
    LeadingIndicatorsDtl.objects.bulk_create(rows)
    return len(rows)


class LeadingIndicatorsHdrSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="pk", read_only=True)
    rig_name = serializers.CharField(source="rig.rig_name", read_only=True, default="")
    company_name = serializers.SerializerMethodField()
    report_no = serializers.CharField(
        max_length=12,
        validators=[UniqueValidator(queryset=LeadingIndicatorsHdr.objects.all(), message="This Report No. is already used.")],
    )
    period = serializers.DateField(read_only=True)
    period_month = serializers.CharField(write_only=True)
    dtl_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = LeadingIndicatorsHdr
        fields = "__all__"
        read_only_fields = _AUDIT_READ_ONLY

    def get_company_name(self, obj):
        name, _ = _resolve_company_name(obj.company_id, obj.period)
        return name or obj.company.company_name

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["period_month"] = instance.period.strftime("%Y-%m")
        return data

    def validate_report_no(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Report No. must be entered.")
        return value

    def validate(self, attrs):
        period = _parse_period(attrs.pop("period_month"))
        if period > date.today():
            raise serializers.ValidationError({"period_month": "Period can't be in the future."})
        attrs["period"] = period
        return attrs


class LeadingIndicatorsViewSet(BaseMasterViewSet):
    queryset = LeadingIndicatorsHdr.objects.select_related("rig", "company").annotate(dtl_count=Count("dtls"))
    serializer_class = LeadingIndicatorsHdrSerializer
    entity_key = ENTITY_KEY
    permission_classes = [HasMenuPermission]
    search_fields = ["report_no", "rig__rig_name"]
    # No header Update in legacy. Delete isn't in legacy either, but the
    # provision exists (permission-gated; admins can simply never grant it) —
    # it removes the report and all its detail rows.
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        qs = self.queryset
        p = self.request.query_params
        if p.get("rig"):
            qs = qs.filter(rig_id=p["rig"])
        if p.get("year"):
            qs = qs.filter(period__year=p["year"])
        return qs.order_by("-period", "-pk")

    def label_for(self, instance):
        return f"{TITLE} {instance.report_no}"

    @action(detail=False, methods=["get"], url_path="meta")
    def meta(self, request):
        return Response({"years": [d.year for d in LeadingIndicatorsHdr.objects.dates("period", "year", order="DESC")]})

    @action(detail=False, methods=["get"], url_path="company-for")
    def company_for(self, request):
        """Company that applies to a rig in a month — same lookup the reports
        use; blank when none is mapped (the user then picks)."""
        try:
            on = _parse_period(request.query_params.get("period"))
            rig_id = int(request.query_params.get("rig"))
        except (TypeError, ValueError, serializers.ValidationError):
            return Response({"error": "?rig= and ?period=YYYY-MM are required"}, status=400)
        b = resolve_rig_company_branding(rig_id, on)
        return Response({"company_id": b["company_id"], "company_name": b["company_name"]})

    def perform_create(self, serializer):
        uid = self._current_user_id(self.request)
        with transaction.atomic():
            instance = serializer.save(cr_user_id=uid or 1, cr_dt=timezone.now())
            created = _create_detail_rows(instance, uid)
        changes = {k: {"old": None, "new": v} for k, v in self._snapshot(instance).items() if v not in (None, "")}
        changes["detail_rows_created"] = {"old": None, "new": created}
        _audit.record_action(self.request, "create", self.entity_key, instance.pk, self.label_for(instance), changes)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        count = instance.dtl_count
        label, pk = self.label_for(instance), instance.pk
        instance.delete()
        _audit.record_action(
            request, "delete", self.entity_key, pk, label,
            {"detail_rows_deleted": {"old": count, "new": 0}} if count else None,
        )
        return Response(status=204)

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        """Excel of the reports list as currently filtered/searched."""
        qs = self.filter_queryset(self.get_queryset())
        rows = [
            [h.report_no, h.rig.rig_name, _resolve_company_name(h.company_id, h.period)[0] or h.company.company_name,
             h.period.strftime("%m/%Y"), h.dtl_count]
            for h in qs
        ]
        _audit.record_action(
            request, "export", self.entity_key, record_label=f"{TITLE} list export",
            changes={**{k: {"old": None, "new": v} for k, v in request.query_params.items() if v}, "rows_exported": {"old": None, "new": len(rows)}},
        )
        return build_xlsx_response(f"{TITLE}.xlsx", TITLE[:31], [TITLE], ["Report No.", "Rig", "Company", "Period", "Detail Rows"], rows)

    @action(detail=True, methods=["get"], url_path="export-report")
    def export_report(self, request, pk=None):
        """Excel of one report: its header and the full grid."""
        hdr = self.get_object()
        company = _resolve_company_name(hdr.company_id, hdr.period)[0] or hdr.company.company_name
        rows = [
            [
                r.workgroup.workgroup_name, r.indicator_type.indicator_type_name,
                r.indicator_subtype.indicator_subtype_name if r.indicator_subtype_id else "",
                r.total_sessions or None, r.no_of_persons or None, r.total_duration or None,
                DURATION_LABELS.get(r.duration_type, ""), r.active,
            ]
            for r in LeadingIndicatorsDtl.objects.filter(hdr=hdr).select_related("workgroup", "indicator_type", "indicator_subtype").order_by("pk")
        ]
        _audit.record_action(
            request, "export", self.entity_key, hdr.pk, self.label_for(hdr), {"rows_exported": {"old": None, "new": len(rows)}}
        )
        return build_xlsx_response(
            f"{TITLE} - {hdr.report_no}.xlsx", "Report",
            [TITLE, f"Report No.: {hdr.report_no}    Rig: {hdr.rig.rig_name}    Company: {company}    Period: {hdr.period:%m/%Y}"],
            ["Work Group", "Indicator Type", "Indicator Subtype", "Total Sessions", "No. Of Persons", "Total Duration", "Duration Type", "Active"],
            rows, wide_columns=(1, 2),
        )

    @action(detail=True, methods=["get"], url_path="details")
    def details(self, request, pk=None):
        hdr = self.get_object()
        rows = LeadingIndicatorsDtl.objects.filter(hdr=hdr).select_related("workgroup", "indicator_type", "indicator_subtype").order_by("pk")
        return Response(
            [
                {
                    "id": r.pk,
                    "workgroup": r.workgroup.workgroup_name,
                    "indicator_type": r.indicator_type.indicator_type_name,
                    "indicator_subtype": r.indicator_subtype.indicator_subtype_name if r.indicator_subtype_id else "",
                    "total_sessions": r.total_sessions,
                    "no_of_persons": r.no_of_persons,
                    "total_duration": r.total_duration,
                    "duration_type": r.duration_type or "",
                    "active": r.active,
                }
                for r in rows
            ]
        )

    @action(detail=True, methods=["post"], url_path="save-details")
    def save_details(self, request, pk=None):
        """Saves the changed detail rows in one go (legacy's Update only sent
        rows flagged Data_Change = 'Y'). All-or-nothing."""
        hdr = self.get_object()
        payload = request.data.get("rows")
        if not isinstance(payload, list) or not payload:
            return Response({"error": "No rows to save."}, status=400)
        existing = {r.pk: r for r in LeadingIndicatorsDtl.objects.filter(hdr=hdr).select_related("indicator_type", "indicator_subtype")}
        errors, updates = [], []
        for item in payload:
            row = existing.get(item.get("id"))
            if row is None:
                return Response({"error": "A row doesn't belong to this report."}, status=400)
            label, problems, values = _dtl_label(row), [], {}
            for field, name in COUNT_FIELDS:
                raw = item.get(field)
                raw = 0 if raw in (None, "") else raw
                try:
                    n = int(raw)
                    if not 0 <= n <= MAX_COUNT or str(raw).strip() != str(n):
                        raise ValueError
                except (TypeError, ValueError):
                    problems.append(f"{name} must be a whole number from 0 to {MAX_COUNT}")
                    n = 0
                values[field] = n
            dur = (item.get("duration_type") or "").strip() or None
            if dur not in (None, "H", "W"):
                problems.append("Duration Type must be Hrs or Wks")
            if values["total_duration"] > 0 and not dur:
                problems.append("Duration Type must be selected")
            values["duration_type"] = dur if values["total_duration"] > 0 else None
            active = item.get("active")
            if active not in ("Y", "N"):
                problems.append("Active must be Y or N")
            values["active"] = active
            if problems:
                errors.append(f"{label}: " + "; ".join(problems))
            else:
                updates.append((row, label, values))
        if errors:
            return Response({"error": "Please fix:\n" + "\n".join(errors)}, status=400)

        uid = self._current_user_id(request)
        changes, now = {}, timezone.now()
        with transaction.atomic():
            for row, label, values in updates:
                diff = {f: (getattr(row, f), v) for f, v in values.items() if getattr(row, f) != v}
                if not diff:
                    continue
                for f, (old, new) in diff.items():
                    changes[f"{label} — {f}"] = {"old": old, "new": new}
                    setattr(row, f, new)
                row.mod_user_id, row.mod_dt = uid, now
                row.save()
        if changes:
            _audit.record_action(request, "update", self.entity_key, hdr.pk, self.label_for(hdr), changes)
        return Response({"updated": len({k.rsplit(' — ', 1)[0] for k in changes})})
