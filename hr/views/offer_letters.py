"""Rig Personnel > New Joinee Workflow > Offer Letter (legacy page frmFs_Offer_Letter, procedure Prc_Fs_Offer_Letter; model docstrings in hr/models.py).

One offer letter per applicant. The pay is a list of components (Masters > Earnings and Deductions, table mst_ed) instead of one column each; the header keeps everything else.

Creator / approver steps run on the shared engine in core/approvals.py (Approval Code OFFER_LETTER, Admin > Approver Mapping, scoped by rig), exactly like the
Drilling Report:
  creator saves a draft -> Finalize (cr_status F) -> approver Approves or Rejects (level 1) -> Revise (approver only): "self" reopens it for the approver's own edit,
  "previous" sends it back to the creator. Reject is final. Reviving a letter (either Revise) also puts the letter and response status back to New and the applicant
  back to New, as the legacy Revise did.
Who may edit: the creator while the letter is a draft or sent back; the approver only while it is reopened for revision; nobody once finalised.
The response given by the applicant (accepted / declined / closed) is saved on the letter and passed on to the applicant's status (N->N, A->A, D->R, C->C), unless the
applicant has already joined.
Not built yet (later): the mail sent on finalize, printing the letter, sending it to the applicant (letter status S / R), Excel import.
"""

from datetime import date

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from core import approvals
from core import audit as _audit
from core.models import ApproverMappingDtl, MstEd, MstUser, RigSiteMapping
from core.permissions import HasMenuPermission
from core.training_group import allowed_category_ids
from hr import offer_letter_autoclose
from hr.models import FsNewApplDtl, FsOfferLetter, FsOfferLetterComponent
from hr.views import HrMasterViewSet

ENTITY_KEY = "hr.fs_offer_letters"
APPROVAL_CODE = "OFFER_LETTER"
BASIC_ID, PF_EMPLOYER_ID = 1, 8
LETTER_STATUS = {"N": "New", "S": "Sent", "C": "Changed", "R": "Resent"}
RESPONSE_STATUS = {"N": "New", "A": "Accepted", "D": "Declined", "C": "Closed"}
APPLICANT_STATUS_FOR_RESPONSE = {"N": "N", "A": "A", "D": "R", "C": "C"}  # legacy: the letter's response is the applicant's status
ALL_RIGHTS = {"create": True, "approve": True, "revise": True, "receive_mail": False, "level": 0}


def workflow_state(letter):
    if letter.cr_status == "F":
        if letter.l1_approval_status == "A":
            return "approved"
        if letter.l1_approval_status == "R":
            return "rejected"
        return "pending"
    return "sent_back" if letter.cr_status == "N" else "draft"


WORKFLOW_LABEL = {"draft": "Draft", "sent_back": "Sent back", "pending": "Awaiting approval", "approved": "Approved", "rejected": "Rejected"}


class ComponentSerializer(serializers.ModelSerializer):
    component_name = serializers.CharField(source="component.ed_name", read_only=True)
    component_abbrv = serializers.CharField(source="component.ed_abrv", read_only=True)

    class Meta:
        model = FsOfferLetterComponent
        fields = ["component", "component_name", "component_abbrv", "amount", "counts_in_total", "show_in_letter", "sort_order"]
        extra_kwargs = {"sort_order": {"required": False}}


class OfferLetterSerializer(serializers.ModelSerializer):
    components = ComponentSerializer(many=True)
    applicant_name = serializers.SerializerMethodField()
    applicant_no = serializers.IntegerField(source="fs_new_appl.fs_new_appl_no", read_only=True)
    applicant_status = serializers.CharField(source="fs_new_appl.fs_new_appl_status", read_only=True)
    applicant_email = serializers.CharField(source="fs_new_appl.fs_emp_email_pers", read_only=True, default="")
    applicant_address = serializers.CharField(source="fs_new_appl.mailing_addr", read_only=True, default="")
    category_name = serializers.CharField(source="fs_new_appl.appl_fs_category.fs_category_name", read_only=True, default="")
    rank_name = serializers.CharField(source="rank.rank_name", read_only=True, default="")
    rig_id = serializers.IntegerField(source="rig_site_mapping.rig_id", read_only=True)
    rig_name = serializers.CharField(source="rig_site_mapping.rig.rig_name", read_only=True, default="")
    rig_site_label = serializers.SerializerMethodField()
    camp_office_addr = serializers.CharField(source="rig_site_mapping.camp_office_addr", read_only=True, default="")
    company_name = serializers.CharField(source="company.company_name", read_only=True, default="")
    authority_name = serializers.SerializerMethodField()
    travel_eligibility_name = serializers.SerializerMethodField()
    letter_status_label = serializers.SerializerMethodField()
    response_status_label = serializers.SerializerMethodField()
    workflow = serializers.SerializerMethodField()
    workflow_label = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()
    total_of_components = serializers.SerializerMethodField()
    auto_close_note = serializers.SerializerMethodField()

    class Meta:
        model = FsOfferLetter
        fields = "__all__"
        read_only_fields = ["offer_letter_status", "response_status", "cr_status", "l1_approval_status", "l1_approval_dt", "l1_user_id", "opened_for_revision_by",
                            "opened_for_revision_dt", "revision_note", "auto_closed_dt", "cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    # ── read side ──
    def get_applicant_name(self, obj):
        return str(obj.fs_new_appl)

    # The three labels below are written exactly as the dropdowns write them (the same text as display_name on their own lists), so a picked value does not flicker
    # between two spellings once the form reloads it.
    def get_rig_site_label(self, obj):
        m = obj.rig_site_mapping
        return f"{m.rig.rig_name} — {m.company.company_name}" if m else ""

    def get_authority_name(self, obj):
        u = obj.authority_user
        return f"{u.user_name} ({u.user_login_id})" if u else ""

    def get_travel_eligibility_name(self, obj):
        t = obj.travel_eligibility
        return f"{t.rank.rank_name} — {t.get_travel_mode_display()}" if t else ""

    def get_letter_status_label(self, obj):
        return LETTER_STATUS.get(obj.offer_letter_status or "N", "")

    def get_response_status_label(self, obj):
        return RESPONSE_STATUS.get(obj.response_status or "N", "")

    def get_workflow(self, obj):
        return workflow_state(obj)

    def get_workflow_label(self, obj):
        return WORKFLOW_LABEL[workflow_state(obj)]

    def _user_name(self, uid):
        cache = self.context.setdefault("_names", {})
        if uid not in cache:
            u = MstUser.objects.filter(pk=uid).first() if uid else None
            cache[uid] = (" ".join(p for p in (u.first_name, u.last_name) if p) or u.user_login_id) if u else ""
        return cache[uid]

    def get_created_by_name(self, obj):
        return self._user_name(obj.cr_user_id)

    def get_approved_by_name(self, obj):
        return self._user_name(obj.l1_user_id)

    def get_auto_close_note(self, obj):
        return offer_letter_autoclose.note_text() if obj.auto_closed_dt else ""

    def get_total_of_components(self, obj):
        return sum(c.amount for c in obj.components.all() if c.counts_in_total == "Y")

    # ── write side ──
    def validate_components(self, rows):
        seen = set()
        for row in rows:
            comp = row["component"]
            if comp.pk in seen:
                raise serializers.ValidationError(f"{comp.ed_name} is listed twice.")
            seen.add(comp.pk)
            if comp.in_offer_letter != "Y" or comp.ed_active != "Y":
                existing = self.instance and self.instance.components.filter(component=comp).exists()
                if not existing:
                    raise serializers.ValidationError(f"{comp.ed_name} cannot be used on an offer letter.")
            if row["amount"] < 0:
                raise serializers.ValidationError(f"{comp.ed_name}: the amount cannot be negative.")
        return rows

    def validate(self, attrs):
        inst = self.instance
        errors = {}
        today = date.today()

        def val(name):
            return attrs[name] if name in attrs else getattr(inst, name, None)

        if inst is None:
            appl = attrs.get("fs_new_appl")
            if appl is None:
                errors["fs_new_appl"] = "Select the applicant."
            else:
                allowed = allowed_category_ids(self.context["request"])
                if allowed is not None and appl.appl_fs_category_id not in allowed:
                    errors["fs_new_appl"] = "You do not work with this applicant's category."
                elif appl.fs_new_appl_status != "N":
                    errors["fs_new_appl"] = "An offer letter can only be made for a New applicant."
                elif FsOfferLetter.objects.filter(pk=appl.pk).exists():
                    errors["fs_new_appl"] = "This applicant already has an offer letter."
        dt, doj, end = val("fs_offer_letter_dt"), val("fs_offer_letter_doj"), val("contract_end_dt")
        if dt and dt > today and (inst is None or dt != inst.fs_offer_letter_dt):
            errors["fs_offer_letter_dt"] = "The offer letter date cannot be after today."
        if dt and doj and doj < dt:
            errors["fs_offer_letter_doj"] = "The date of joining cannot be before the offer letter date."
        if doj and end and end < doj:
            errors["contract_end_dt"] = "The contract end date cannot be before the date of joining."
        def required_text(name, message):
            """Required on a new letter. On an old one only if it already has a value: a letter that never had a contact or a location (legacy left them
            empty on about 3,200 letters) can still be saved without them, but a value it has cannot be wiped."""
            if (val(name) or "").strip():
                return
            if inst is None or (getattr(inst, name, None) or "").strip():
                errors[name] = message

        required_text("contact_person", "Enter the contact person.")
        required_text("contact_tel_no", "Enter the contact number.")
        required_text("rig_location", "Enter the rig location.")
        if val("authority_user") is None:
            errors["authority_user"] = "Select who signs the letter."
        if val("included_pf") not in ("Y", "N"):
            errors["included_pf"] = "Say whether PF is included (Y or N)."
        on_days, off_days, desc = val("on_days"), val("off_days"), (val("on_off_desc") or "").strip()
        had_days = inst is not None and ((inst.on_days and inst.off_days) or (inst.on_off_desc or "").strip())
        if not desc and not (on_days and off_days) and (inst is None or had_days):
            errors["on_off_desc"] = "Enter the on and off days, or a description."
        for name in ("on_days", "off_days"):
            if val(name) is not None and val(name) < 0:
                errors[name] = "Cannot be negative."
        salary = val("salary_amt")
        if salary is None or salary <= 0:
            errors["salary_amt"] = "Enter the total salary."
        rows = attrs.get("components")
        if rows is None and inst is not None:
            rows = [{"component": c.component, "amount": c.amount, "counts_in_total": c.counts_in_total} for c in inst.components.all()]
        # The pay rules (Basic, PF, total) apply to a new letter and whenever the pay is changed. An old letter whose pay does not add up (legacy letters before 2020
        # were made under another rule) can still have its other details corrected without touching the pay.
        pay_changed = inst is None
        if inst is not None:
            old_rows = {(c.component_id, c.amount, c.counts_in_total) for c in inst.components.all()}
            new_rows = {(r["component"].pk, r["amount"], r.get("counts_in_total", "Y")) for r in (rows or [])}
            pay_changed = old_rows != new_rows or val("salary_amt") != inst.salary_amt or val("included_pf") != inst.included_pf
        if rows is not None and pay_changed:
            by_id = {r["component"].pk: r for r in rows}
            basic = by_id.get(BASIC_ID)
            if not basic or basic["amount"] <= 0:
                errors["components"] = "Enter the Basic salary (more than 0)."
            elif val("included_pf") == "N" and by_id.get(PF_EMPLOYER_ID) and by_id[PF_EMPLOYER_ID]["amount"] > 0:
                errors["components"] = "PF must be 0 when PF is not included."
            elif salary:
                total = sum(r["amount"] for r in rows if r.get("counts_in_total", "Y") == "Y")
                if total != salary:
                    errors["components"] = f"The components that count toward the total add up to {total:,}, but the total salary is {salary:,}. They must be equal."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def _save_components(self, letter, rows):
        order = {c.pk: c.ed_order for c in MstEd.objects.filter(pk__in=[r["component"].pk for r in rows])}
        letter.components.all().delete()
        FsOfferLetterComponent.objects.bulk_create([
            FsOfferLetterComponent(offer_letter=letter, component=r["component"], amount=r["amount"], counts_in_total=r.get("counts_in_total", "Y"),
                                   show_in_letter=r.get("show_in_letter", "Y"), sort_order=r.get("sort_order") or order.get(r["component"].pk, 0))
            for r in rows])

    @transaction.atomic
    def create(self, validated_data):
        rows = validated_data.pop("components")
        letter = FsOfferLetter.objects.create(**validated_data)
        self._save_components(letter, rows)
        return letter

    @transaction.atomic
    def update(self, instance, validated_data):
        rows = validated_data.pop("components", None)
        validated_data.pop("fs_new_appl", None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()
        if rows is not None:
            self._save_components(instance, rows)
        return instance


class OfferLetterViewSet(HrMasterViewSet):
    queryset = FsOfferLetter.objects.select_related(
        "fs_new_appl", "fs_new_appl__appl_fs_category", "rank", "rig_site_mapping", "rig_site_mapping__rig", "company", "authority_user", "travel_eligibility", "travel_eligibility__rank"
    ).prefetch_related("components__component")
    serializer_class = OfferLetterSerializer
    entity_key = ENTITY_KEY
    name_field = "fs_offer_letter_dt"
    permission_classes = [HasMenuPermission]
    lookup = False
    export_exclude_fields = ["components"]  # the pay lines do not fit one CSV row; the total is in salary_amt
    search_fields = ["fs_new_appl__fs_emp_fname", "fs_new_appl__fs_emp_lname", "rig_site_mapping__rig__rig_name", "contact_person"]
    action_perm_overrides = {"applicant_search": ("add", "edit"), "applicant_info": ("add", "edit"), "meta": ("view", "add", "edit"), "components_master": ("view", "add", "edit"),
                             "response": "edit"}

    _ORDERINGS = {
        "recent": ("-fs_offer_letter_dt", "-fs_new_appl_id"),
        "dt": ("fs_offer_letter_dt", "fs_new_appl_id"), "-dt": ("-fs_offer_letter_dt", "-fs_new_appl_id"),
        "name": ("fs_new_appl__fs_emp_lname", "fs_new_appl__fs_emp_fname"), "-name": ("-fs_new_appl__fs_emp_lname", "-fs_new_appl__fs_emp_fname"),
        "doj": ("fs_offer_letter_doj",), "-doj": ("-fs_offer_letter_doj",),
    }

    # ── who may see what ──
    def _uid(self):
        return self._current_user_id(self.request)

    def get_queryset(self):
        qs = self.queryset
        allowed = allowed_category_ids(self.request)
        if allowed is not None:
            qs = qs.filter(fs_new_appl__appl_fs_category_id__in=allowed)
        if self.action != "list":
            return qs
        p = self.request.query_params
        state = p.get("state")
        pending = Q(l1_approval_status__isnull=True) | Q(l1_approval_status__in=("", "N"))
        if state == "draft":
            qs = qs.filter(Q(cr_status__isnull=True) | Q(cr_status=""))
        elif state == "sent_back":
            qs = qs.filter(cr_status="N")
        elif state == "pending":
            qs = qs.filter(cr_status="F").filter(pending)
        elif state == "approved":
            qs = qs.filter(cr_status="F", l1_approval_status="A")
        elif state == "rejected":
            qs = qs.filter(cr_status="F", l1_approval_status="R")
        if p.get("response"):
            qs = qs.filter(response_status=p["response"]) if p["response"] != "N" else qs.filter(Q(response_status="N") | Q(response_status=""))
        if p.get("letter") in ("N", "S", "C", "R"):
            qs = qs.filter(offer_letter_status=p["letter"]) if p["letter"] != "N" else qs.filter(Q(offer_letter_status="N") | Q(offer_letter_status=""))
        if p.get("rig"):
            qs = qs.filter(rig_site_mapping__rig_id=p["rig"])
        if p.get("year", "").isdigit():
            qs = qs.filter(fs_offer_letter_dt__year=int(p["year"]))
        scope, uid = p.get("scope"), self._uid()
        if scope == "pending_for_me" and uid is not None:
            rigs = ApproverMappingDtl.objects.filter(approver_mapping__approval_code__approval_code=APPROVAL_CODE, approver_mapping__approver_user_id=uid,
                                                     approver_mapping__approver_active="Y", approve_yn="Y").values_list("rig_id", flat=True)
            qs = qs.filter(rig_site_mapping__rig_id__in=set(rigs), cr_status="F").filter(pending)
        elif scope == "approved_by_me" and uid is not None:
            qs = qs.filter(l1_user_id=uid, l1_approval_status="A")
        return qs.order_by(*(self._ORDERINGS.get(p.get("ordering")) or self._ORDERINGS["recent"]))

    def label_for(self, instance):
        return f"{instance.fs_new_appl} — offer letter {instance.fs_offer_letter_dt}"

    def _role(self, letter):
        if self.request.user.is_superuser:
            return dict(ALL_RIGHTS)
        return approvals.get_role(APPROVAL_CODE, self._uid(), letter.rig_site_mapping.rig_id)

    def _can_edit(self, letter, caps):
        return (letter.cr_status in (None, "", "N") and caps["create"]) or approvals.can_edit_as_approver(letter, caps)

    def _snapshot(self, instance):
        snap = super()._snapshot(instance)
        snap["components"] = [{"component": c.component.ed_name, "amount": c.amount, "counts_in_total": c.counts_in_total, "show_in_letter": c.show_in_letter}
                              for c in instance.components.all().order_by("sort_order", "component_id")]
        return snap

    # ── create / update / delete ──
    def create(self, request, *args, **kwargs):
        appl = FsNewApplDtl.objects.filter(pk=request.data.get("fs_new_appl") or 0).select_related("appl_fs_category").first()
        rsm = RigSiteMapping.objects.filter(pk=request.data.get("rig_site_mapping") or 0).first()
        if rsm and not request.user.is_superuser:
            caps = approvals.get_role(APPROVAL_CODE, self._uid(), rsm.rig_id)
            if not caps["create"]:
                return Response({"error": "You are not set up to create offer letters for this rig (Admin > Approver Mapping)."}, status=403)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        instance = serializer.save(cr_user_id=self._uid() or 1, cr_dt=timezone.now(), offer_letter_status="N", response_status="N")
        instance = self.get_queryset().get(pk=instance.pk)
        changes = {k: {"old": None, "new": v} for k, v in self._snapshot(instance).items() if v not in (None, "", [])}
        _audit.record_action(self.request, "create", self.entity_key, instance.pk, self.label_for(instance), changes or None, target=instance)

    def update(self, request, *args, **kwargs):
        letter = self.get_object()
        if not self._can_edit(letter, self._role(letter)):
            return Response({"error": "This offer letter cannot be edited now. It is finalised, or you are not its creator."}, status=403)
        return super().update(request, *args, **kwargs)

    def perform_update(self, serializer):
        old = self._snapshot(serializer.instance)
        extra = {"mod_user_id": self._uid() or 1, "mod_dt": timezone.now()}
        if serializer.instance.offer_letter_status in ("S", "R", "C"):
            extra["offer_letter_status"] = "C"  # a letter already sent and then changed
        instance = serializer.save(**extra)
        instance = self.get_queryset().get(pk=instance.pk)
        _audit.record_action(self.request, "update", self.entity_key, instance.pk, self.label_for(instance), self._diff(old, self._snapshot(instance)) or None, target=instance)

    def destroy(self, request, *args, **kwargs):
        letter = self.get_object()
        if letter.cr_status == "F" or letter.offer_letter_status in ("S", "C", "R"):
            return Response({"error": "A finalised or sent offer letter cannot be deleted. Ask the approver to revise it first."}, status=400)
        if letter.fs_new_appl.fs_new_appl_status == "J":
            return Response({"error": "This applicant has already joined."}, status=400)
        label, pre = self.label_for(letter), _audit.before_delete(letter)
        letter.delete()
        _audit.log_deleted(request, self.entity_key, label, pre)
        return Response(status=204)

    # ── pickers and helpers for the form ──
    @action(detail=False, methods=["get"], url_path="meta")
    def meta(self, request):
        years = [d.year for d in FsOfferLetter.objects.dates("fs_offer_letter_dt", "year", order="DESC")]
        return Response({"years": years, "workflow": [{"value": k, "label": v} for k, v in WORKFLOW_LABEL.items()],
                         "responses": [{"value": k, "label": v} for k, v in RESPONSE_STATUS.items()],
                         "letters": [{"value": k, "label": v} for k, v in LETTER_STATUS.items()]})

    @action(detail=False, methods=["get"], url_path="components")
    def components_master(self, request):
        return Response([{"component": c.pk, "name": c.ed_name, "abbrv": c.ed_abrv, "counts_in_total": "Y" if c.counts_in_total == "Y" else "N", "sort_order": c.ed_order}
                         for c in MstEd.objects.filter(in_offer_letter="Y", ed_active="Y").order_by("ed_order")])

    @action(detail=False, methods=["get"], url_path="applicant-search")
    def applicant_search(self, request):
        """Applicants a letter can be made for: New ones, in the person's categories, without a letter yet."""
        qs = FsNewApplDtl.objects.filter(fs_new_appl_status="N", offer_letter__isnull=True).select_related("appl_fs_category", "appl_rank")
        allowed = allowed_category_ids(request)
        if allowed is not None:
            qs = qs.filter(appl_fs_category_id__in=allowed)
        text = request.query_params.get("search", "").strip()
        for word in text.split()[:3]:
            qs = qs.filter(Q(fs_emp_fname__icontains=word) | Q(fs_emp_mname__icontains=word) | Q(fs_emp_lname__icontains=word) | Q(fs_new_appl_no=int(word) if word.isdigit() else -1))
        size = 30
        offset = int(request.query_params["offset"]) if request.query_params.get("offset", "").isdigit() else 0
        rows = list(qs.order_by("-fs_new_appl_id")[offset:offset + size + 1])  # one extra row tells whether there is a next page
        return Response({"results": [{"id": a.pk, "name": str(a), "application_no": a.fs_new_appl_no, "category": a.appl_fs_category.fs_category_name, "rank": a.appl_rank.rank_name,
                                      "status": a.fs_new_appl_status} for a in rows[:size]], "has_more": len(rows) > size})

    @action(detail=False, methods=["get"], url_path="applicant-info")
    def applicant_info(self, request):
        """?applicant=<id>: what the form shows once an applicant is picked (name, address, e-mail, and the rank on his application)."""
        qs = FsNewApplDtl.objects.select_related("appl_fs_category", "appl_rank")
        allowed = allowed_category_ids(request)
        if allowed is not None:
            qs = qs.filter(appl_fs_category_id__in=allowed)
        a = qs.filter(pk=request.query_params.get("applicant") or 0).first()
        if not a:
            return Response({"error": "Applicant not found."}, status=404)
        return Response({"id": a.pk, "name": str(a), "application_no": a.fs_new_appl_no, "email": a.fs_emp_email_pers or "", "address": a.mailing_addr or "",
                         "category": a.appl_fs_category.fs_category_name, "rank": a.appl_rank_id, "rank_name": a.appl_rank.rank_name, "status": a.fs_new_appl_status,
                         "has_letter": FsOfferLetter.objects.filter(pk=a.pk).exists()})

    # ── workflow ──
    @action(detail=True, methods=["get"], url_path="role")
    def role(self, request, pk=None):
        letter = self.get_object()
        caps = self._role(letter)
        joined = letter.fs_new_appl.fs_new_appl_status == "J"
        return Response({
            "can_edit": self._can_edit(letter, caps),
            "can_finalize": approvals.can_finalize(letter, caps),
            "can_approve": approvals.can_approve(letter, caps),
            "can_reject": approvals.can_reject(letter, caps),
            "can_revise_self": approvals.can_revise_self(letter, caps) and not joined,
            "can_revise_previous": approvals.can_revise_previous(letter, caps) and not joined,
            "can_set_response": letter.cr_status == "F" and letter.l1_approval_status == "A" and not joined,
        })

    def _transition(self, request, gate, apply_fn, label, resets_letter=False):
        letter = self.get_object()
        caps = self._role(letter)
        if not gate(letter, caps):
            return Response({"error": "You don't have permission to do that on this offer letter."}, status=403)
        applicant = letter.fs_new_appl
        if resets_letter and applicant.fs_new_appl_status == "J":
            return Response({"error": "This applicant has already joined, so the letter cannot be revised."}, status=400)
        uid = self._uid()
        old = self._snapshot(letter)
        with transaction.atomic():
            apply_fn(letter, uid)
            if resets_letter:  # legacy Revise: the letter starts again, and so does the applicant
                letter.offer_letter_status, letter.response_status, letter.auto_closed_dt = "N", "N", None
                FsNewApplDtl.objects.filter(pk=applicant.pk).update(fs_new_appl_status="N", mod_user_id=uid, mod_dt=timezone.now())
            letter.save()
        letter = self.get_queryset().get(pk=letter.pk)
        _audit.record_action(request, label, self.entity_key, letter.pk, self.label_for(letter), self._diff(old, self._snapshot(letter)) or None, target=letter)
        return Response(self.get_serializer(letter).data)

    @action(detail=True, methods=["post"], url_path="finalize")
    def finalize(self, request, pk=None):
        return self._transition(request, approvals.can_finalize, approvals.finalize, "finalize")

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        return self._transition(request, approvals.can_approve, approvals.approve, "approve")

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        return self._transition(request, approvals.can_reject, approvals.reject, "reject")

    @action(detail=True, methods=["post"], url_path="revise-self")
    def revise_self(self, request, pk=None):
        return self._transition(request, approvals.can_revise_self, approvals.revise_self, "revise_self", resets_letter=True)

    @action(detail=True, methods=["post"], url_path="revise-previous")
    def revise_previous(self, request, pk=None):
        note = request.data.get("note")
        return self._transition(request, approvals.can_revise_previous, lambda rec, uid: approvals.revise_previous(rec, uid, note=note), "revise_previous", resets_letter=True)

    @action(detail=True, methods=["post"], url_path="response")
    def response(self, request, pk=None):
        """The applicant's answer (N / A / D / C). Only on an approved letter; passed on to the applicant's status unless he has joined."""
        letter = self.get_object()
        value = request.data.get("response_status")
        if value not in RESPONSE_STATUS:
            return Response({"error": "Choose New, Accepted, Declined or Closed."}, status=400)
        if letter.cr_status != "F" or letter.l1_approval_status != "A":
            return Response({"error": "The response can be recorded once the letter is approved."}, status=400)
        applicant = letter.fs_new_appl
        if applicant.fs_new_appl_status == "J":
            return Response({"error": "This applicant has already joined."}, status=400)
        uid, old = self._uid(), self._snapshot(letter)
        old["applicant_status"] = applicant.fs_new_appl_status
        with transaction.atomic():
            letter.response_status, letter.mod_user_id, letter.mod_dt = value, uid, timezone.now()
            letter.auto_closed_dt = None  # a response given by a person replaces the automatic close
            letter.save()
            FsNewApplDtl.objects.filter(pk=applicant.pk).update(fs_new_appl_status=APPLICANT_STATUS_FOR_RESPONSE[value], mod_user_id=uid, mod_dt=timezone.now())
        letter = self.get_queryset().get(pk=letter.pk)
        new = self._snapshot(letter)
        new["applicant_status"] = APPLICANT_STATUS_FOR_RESPONSE[value]
        _audit.record_action(request, "update", self.entity_key, letter.pk, self.label_for(letter), self._diff(old, new) or None, target=letter)
        return Response(self.get_serializer(letter).data)
