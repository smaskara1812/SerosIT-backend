"""QHSE → Hazard ID Card — the Add/Update workflow for the HazardCard
table (see models.HazardCard's own docstring). Distinct from
reports_views.HazardCardViewSet, which is a read-only report/listing over
the same table.

Ported from frmHazard_ID_Card.aspx(.cs)/clsHazard_ID_Card.cs, with two
real business rules confirmed from that code rather than guessed:
  - Project No. is never picked by the user — it's the rig's currently
    active ProjectContractDtl line (Get_Prj_No_Operator_Location_Of_Rig),
    resolved server-side from whichever rig is selected, same as
    dashboard_access.current_contract_by_rig already does for Fleet
    Operating Picture / Contract Exposure.
  - "Reported by" splits on Reported By Party: party == 'EOSIL' resolves
    to an MstEmployee FK (reported_by_fs_emp); every other party is plain
    free text (reported_by_name), with the other field cleared.

Two things have no legacy code to confirm against (the stored procedures
that implement them aren't part of this repo):
  - Haz ID Card No. generation — Prc_Hazard_ID_Card's INSERT branch
    returns it as an output param; there's no visible per-year-reset
    pattern in the sample data, so this app uses a plain global MAX+1
    (confirmed with the user directly), same shape as Incident's own
    per-FY _next_incident_no but without the FY scoping.
  - The exact "Reported by party" option list — GetCompanyName() rebinds
    it from a DB proc not in these files. REPORTED_BY_PARTY_OPTIONS below
    is the best reconstruction available (the aspx's static placeholder
    list plus 'EOSIL', which the code-behind explicitly special-cases even
    though it's absent from that static list) — flagged here in case the
    real list turns out to differ.

The Responsible Dept -> Responsible Rank cascade (Rig -> rig_type ->
Fs_Category via FsCatgToRigTypeMapping -> eligible MstVesselDept rows via
MstRank.business_system_id_6='Y' -> eligible MstRank rows for that
dept+category) is exposed here as `rig-context` rather than reusing the
generic masters endpoints, since "vessel depts eligible for this rig" is a
derived query (distinct vessel_dept_id off MstRank), not a plain field
filter on MstVesselDept itself.
"""

from django.db.models import Max
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from . import audit as _audit
from .dashboard_access import current_contract_by_rig
from .hazard_card_serializers import HazardCardDetailSerializer
from .incident_views import _category_rig_type_ids
from .masters_views import BaseMasterViewSet
from .models import FsCatgToRigTypeMapping, HazardCard, MstFsCategory, MstRank, MstRig, MstVesselDept
from .permissions import HasMenuPermission

# See module docstring — reconstructed, not confirmed from a DB proc.
REPORTED_BY_PARTY_OPTIONS = ["SEROS", "EOSIL", "Operator", "Visitor", "Subcontractor", "Other"]

# Legacy's Get_Vessel_Dept_Wise_Rank comment: when a rig's rig_type has no
# active Fs_Category mapping at all, the underlying proc falls back to
# categories 4/5 rather than returning an empty list.
_FALLBACK_FS_CATEGORY_IDS = [4, 5]


def _fs_category_id_for_rig(rig):
    mapping = FsCatgToRigTypeMapping.objects.filter(rig_type_id=rig.rig_type_id, mapping_active="Y").first()
    return mapping.fs_category_id if mapping else None


def _eligible_vessel_depts(fs_category_id):
    category_ids = [fs_category_id] if fs_category_id else _FALLBACK_FS_CATEGORY_IDS
    dept_ids = (
        MstRank.objects.filter(business_system_id_6="Y", fs_category_id__in=category_ids)
        .values_list("vessel_dept_id", flat=True)
        .distinct()
    )
    return list(MstVesselDept.objects.filter(vessel_dept_id__in=dept_ids).order_by("vessel_dept_name"))


def _next_haz_id_card_no():
    last = HazardCard.objects.aggregate(m=Max("haz_id_card_no"))["m"]
    return (last or 0) + 1


def _validate_reported_by(data, instance=None):
    party = data.get("reported_by_party", getattr(instance, "reported_by_party", None))
    fs_emp = data.get("reported_by_fs_emp") if "reported_by_fs_emp" in data else getattr(instance, "reported_by_fs_emp", None)
    name = data.get("reported_by_name") if "reported_by_name" in data else getattr(instance, "reported_by_name", None)
    if party == "EOSIL":
        if not fs_emp:
            raise ValidationError({"reported_by_fs_emp": "Reported By is required when party is EOSIL."})
    elif not name:
        raise ValidationError({"reported_by_name": "Reported By is required."})


def _validate_close_out(data, instance=None):
    status = data.get("haz_id_card_status", getattr(instance, "haz_id_card_status", None))
    close_out_dt = data.get("close_out_dt") if "close_out_dt" in data else getattr(instance, "close_out_dt", None)
    event_dt = data.get("event_dt", getattr(instance, "event_dt", None))
    if status == "C" and not close_out_dt:
        raise ValidationError({"close_out_dt": "Close Out Date/Time is required when Status is Closed."})
    if close_out_dt and event_dt and close_out_dt <= event_dt:
        raise ValidationError({"close_out_dt": "Close Out Date/Time must be after the Event Date/Time."})


class HazardCardViewSet(BaseMasterViewSet):
    queryset = HazardCard.objects.select_related(
        "rig", "contract", "contract__operator", "contract__location", "work_location", "haz_type",
        "resp_dept", "resp_rank", "reported_by_fs_emp",
    ).exclude(marked_as_deleted="Y")
    serializer_class = HazardCardDetailSerializer
    entity_key = "qhse.hazard_id_card"
    permission_classes = [HasMenuPermission]
    search_fields = ["haz_id_card_no", "hazard_desc", "action_taken", "reported_by_name"]

    _ORDERINGS = {
        "event_dt": ("event_dt",),
        "-event_dt": ("-event_dt",),
        "haz_id_card_no": ("haz_id_card_no",),
        "-haz_id_card_no": ("-haz_id_card_no",),
    }

    def get_queryset(self):
        qs = self.queryset
        params = self.request.query_params

        category_id = params.get("category")
        if category_id and category_id.isdigit():
            rig_type_ids = _category_rig_type_ids(category_id)
            if rig_type_ids is not None:
                qs = qs.filter(rig__rig_type_id__in=rig_type_ids)
        rig_id = params.get("rig")
        if rig_id:
            qs = qs.filter(rig_id=rig_id)
        year = params.get("year")
        if year:
            qs = qs.filter(event_dt__year=year)
        hazard_type = params.get("hazard_type")
        if hazard_type:
            qs = qs.filter(haz_type_id=hazard_type)
        status = params.get("status")
        if status == "open":
            qs = qs.exclude(haz_id_card_status="C")
        elif status == "closed":
            qs = qs.filter(haz_id_card_status="C")
        tfs = params.get("tfs")
        if tfs == "Y":
            qs = qs.filter(timeout_for_safety="Y")
        elif tfs == "N":
            # Legacy data never has a literal 'N' here — every non-Y row
            # is '' (confirmed: 28,494 '' rows vs 2,939 'Y', zero 'N').
            # Same "anything but Y is No" reasoning as
            # BaseMasterViewSet._apply_active_filter's own '' vs 'N' note.
            qs = qs.exclude(timeout_for_safety="Y")
        work_location = params.get("work_location")
        if work_location:
            qs = qs.filter(work_location_id=work_location)
        date_from = params.get("date_from")
        if date_from:
            qs = qs.filter(event_dt__date__gte=date_from)
        date_to = params.get("date_to")
        if date_to:
            qs = qs.filter(event_dt__date__lte=date_to)

        ordering = params.get("ordering")
        return qs.order_by(*self._ORDERINGS.get(ordering, ("-event_dt",)))

    def label_for(self, instance):
        return f"Haz ID Card #{instance.haz_id_card_no}"

    @action(detail=False, methods=["get"], url_path="meta")
    def meta(self, request):
        years = [d.year for d in self.queryset.dates("event_dt", "year", order="DESC")]
        hazard_types = list(
            self.queryset.exclude(haz_type__isnull=True)
            .values("haz_type_id", "haz_type__haz_type_name")
            .distinct()
            .order_by("haz_type__haz_type_name")
        )
        work_locations = list(
            self.queryset.exclude(work_location__isnull=True)
            .values("work_location_id", "work_location__work_location")
            .distinct()
            .order_by("work_location__work_location")
        )
        # Same Category concept as Incident Register's own filter bar —
        # scopes the Rig list to whichever rig types that Fs Category maps
        # to (see _category_rig_type_ids), not a filter on the cards
        # themselves.
        categories = list(
            MstFsCategory.objects.filter(rig_type_mappings__mapping_active="Y")
            .distinct()
            .order_by("fs_category_name")
            .values("fs_category_id", "fs_category_name")
        )
        return Response(
            {
                "years": years,
                "reported_by_party_options": REPORTED_BY_PARTY_OPTIONS,
                "hazard_types": [
                    {"id": t["haz_type_id"], "name": t["haz_type__haz_type_name"]} for t in hazard_types
                ],
                "work_locations": [
                    {"id": w["work_location_id"], "name": w["work_location__work_location"]}
                    for w in work_locations
                ],
                "categories": [
                    {"id": c["fs_category_id"], "name": c["fs_category_name"]} for c in categories
                ],
            }
        )

    @action(detail=False, methods=["get"], url_path="rig-context")
    def rig_context(self, request):
        """Everything that cascades off picking a Rig: the rig's active
        Project Contract (read-only display, never picked directly) and
        the Responsible Dept options eligible for that rig's category."""
        rig_id = request.query_params.get("rig")
        if not rig_id or not rig_id.isdigit():
            return Response({"error": "?rig= is required"}, status=400)
        rig = MstRig.objects.filter(pk=rig_id).first()
        if not rig:
            return Response({"error": "Unknown rig"}, status=404)

        today = timezone.now().date()
        line = current_contract_by_rig([rig.rig_id], today).get(rig.rig_id)
        contract = None
        if line:
            c = line.contract
            contract = {
                "id": c.prj_contract_id,
                "label": f"{c.prj_contract_no} ({c.operator.operator_name}) - {c.location.location_name}",
            }

        fs_category_id = _fs_category_id_for_rig(rig)
        vessel_depts = [
            {"id": d.vessel_dept_id, "name": d.vessel_dept_name} for d in _eligible_vessel_depts(fs_category_id)
        ]
        return Response({"contract": contract, "fs_category_id": fs_category_id, "vessel_depts": vessel_depts})

    @action(detail=False, methods=["get"], url_path="ranks")
    def ranks(self, request):
        """Responsible Rank options for a given Rig + Responsible Dept
        (vessel dept) pair — MstRank rows matching that dept, that rig's
        resolved fs_category, and business_system_id_6='Y'."""
        rig_id = request.query_params.get("rig")
        vessel_dept_id = request.query_params.get("vessel_dept")
        if not rig_id or not rig_id.isdigit() or not vessel_dept_id or not vessel_dept_id.isdigit():
            return Response({"error": "?rig= and ?vessel_dept= are required"}, status=400)
        rig = MstRig.objects.filter(pk=rig_id).first()
        if not rig:
            return Response({"error": "Unknown rig"}, status=404)

        fs_category_id = _fs_category_id_for_rig(rig)
        category_ids = [fs_category_id] if fs_category_id else _FALLBACK_FS_CATEGORY_IDS
        ranks = MstRank.objects.filter(
            vessel_dept_id=vessel_dept_id, business_system_id_6="Y", fs_category_id__in=category_ids
        ).order_by("rank_order")
        return Response([{"id": r.rank_id, "name": r.rank_name} for r in ranks])

    def _resolve_contract(self, rig):
        today = timezone.now().date()
        line = current_contract_by_rig([rig.rig_id], today).get(rig.rig_id)
        if not line:
            raise ValidationError({"rig": "No active Project Contract is assigned in master data for this rig."})
        return line.contract

    def perform_create(self, serializer):
        data = serializer.validated_data
        _validate_reported_by(data)
        _validate_close_out(data)
        contract = self._resolve_contract(data["rig"])
        uid = self._current_user_id(self.request)
        instance = serializer.save(
            contract=contract,
            haz_id_card_no=_next_haz_id_card_no(),
            timeout_for_safety=data.get("timeout_for_safety") or "N",
            reported_by_fs_emp=data.get("reported_by_fs_emp") if data.get("reported_by_party") == "EOSIL" else None,
            reported_by_name=data.get("reported_by_name") if data.get("reported_by_party") != "EOSIL" else None,
            cr_user_id=uid or 1,
            cr_dt=timezone.now(),
        )
        changes = {k: {"old": None, "new": v} for k, v in self._snapshot(instance).items() if v not in (None, "")}
        _audit.record_action(self.request, "create", self.entity_key, instance.pk, self.label_for(instance), changes or None)

    def perform_update(self, serializer):
        data = serializer.validated_data
        _validate_reported_by(data, instance=serializer.instance)
        _validate_close_out(data, instance=serializer.instance)
        old_snapshot = self._snapshot(serializer.instance)
        uid = self._current_user_id(self.request)
        save_kwargs = {"mod_user_id": uid, "mod_dt": timezone.now()}
        new_rig = data.get("rig")
        if new_rig is not None and new_rig != serializer.instance.rig:
            # Rig actually changed — re-resolve which contract that rig is
            # on today. Otherwise the contract already stored on the card
            # is left untouched: re-resolving on every save was silently
            # rewriting it to "today's" contract for that rig on every
            # edit (even an unrelated remark or status change), and
            # outright blocked saving any card whose rig has no contract
            # active today even though the card already had one on file.
            # Confirmed against real data: 325 open cards stored on an
            # older contract, 164 with none active today.
            save_kwargs["contract"] = self._resolve_contract(new_rig)
        party = data.get("reported_by_party", serializer.instance.reported_by_party)
        if "reported_by_party" in data or "reported_by_fs_emp" in data or "reported_by_name" in data:
            save_kwargs["reported_by_fs_emp"] = data.get("reported_by_fs_emp") if party == "EOSIL" else None
            save_kwargs["reported_by_name"] = data.get("reported_by_name") if party != "EOSIL" else None
        instance = serializer.save(**save_kwargs)
        changes = self._diff(old_snapshot, self._snapshot(instance))
        _audit.record_action(self.request, "update", self.entity_key, instance.pk, self.label_for(instance), changes or None)

    def destroy(self, request, *args, **kwargs):
        """Soft delete — matches clsHazard_ID_Card's DeleteMe (which sets
        Marked_As_Deleted + Deleted_Remarks rather than a real DELETE), and
        the legacy form's own popup which requires a >=10 char reason."""
        instance = self.get_object()
        remarks = (request.data.get("deleted_remarks") or "").strip()
        if len(remarks) < 10:
            return Response({"error": "A reason for delete of at least 10 characters is required."}, status=400)
        uid = self._current_user_id(request)
        instance.marked_as_deleted = "Y"
        instance.deleted_remarks = remarks[:100]
        instance.mod_user_id = uid
        instance.mod_dt = timezone.now()
        instance.save()
        _audit.record_action(request, "delete", self.entity_key, instance.pk, self.label_for(instance), None)
        return Response(status=204)

    def _filter_summary(self, request):
        """One chip string per active filter, for the print/PDF header —
        every filter this viewset's get_queryset actually reads, so the
        report is self-describing about exactly what's included rather
        than requiring the reader to trust an unlabeled row count."""
        params = request.query_params
        parts = []
        category_id = params.get("category")
        if category_id and category_id.isdigit():
            category = MstFsCategory.objects.filter(pk=category_id).first()
            if category:
                parts.append(f"Category: {category.fs_category_name}")
        rig_id = params.get("rig")
        if rig_id:
            rig = MstRig.objects.filter(pk=rig_id).first()
            if rig:
                parts.append(f"Rig: {rig.rig_name}")
        year = params.get("year")
        if year:
            parts.append(f"Year: {year}")
        hazard_type = params.get("hazard_type")
        if hazard_type and hazard_type.isdigit():
            ht = self.queryset.filter(haz_type_id=hazard_type).values_list("haz_type__haz_type_name", flat=True).first()
            if ht:
                parts.append(f"Type: {ht}")
        work_location = params.get("work_location")
        if work_location and work_location.isdigit():
            wl = (
                self.queryset.filter(work_location_id=work_location)
                .values_list("work_location__work_location", flat=True)
                .first()
            )
            if wl:
                parts.append(f"Location: {wl}")
        status = params.get("status")
        if status in ("open", "closed"):
            parts.append(f"Status: {status.capitalize()}")
        tfs = params.get("tfs")
        if tfs in ("Y", "N"):
            parts.append(f"Timeout For Safety: {'Yes' if tfs == 'Y' else 'No'}")
        # Period isn't listed here — it's shown inline in the report's own
        # repeating page title instead (see report() below).
        search = params.get("search")
        if search:
            parts.append(f'Search: "{search}"')
        return parts or ["All hazard cards"]

    @action(detail=False, methods=["get"], url_path="report")
    def report(self, request):
        """Print Report — the filter-driven pie-chart + detail-table PDF
        (see hazard_card_report.py's own docstring for what's confirmed
        vs. reconstructed)."""
        from datetime import date as _date

        from .hazard_card_report import render_hazard_card_report_pdf

        def _fmt_date(d):
            try:
                return _date.fromisoformat(d).strftime("%d/%m/%Y")
            except (TypeError, ValueError):
                return "…"

        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        period_label = f"{_fmt_date(date_from)} - {_fmt_date(date_to)}" if (date_from or date_to) else None

        qs = self.get_queryset()
        filter_summary = self._filter_summary(request)
        pdf_bytes = render_hazard_card_report_pdf(qs, filter_summary, period_label)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = 'inline; filename="Hazard ID Card Report.pdf"'
        _audit.record_action(
            request, "export", self.entity_key, record_label="Hazard ID Card Report PDF print",
            changes={
                "filters": {"old": None, "new": " · ".join(filter_summary)},
                "period": {"old": None, "new": period_label},
                "rows_printed": {"old": None, "new": qs.count()},
            },
        )
        return response
