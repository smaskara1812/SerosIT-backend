"""QHSE → Training Org — rebuild of legacy frmHSE_Training_Org_Hdr (an
organisation that delivers training, its contacts, and its trainers).

Rules ported from frmHSE_Training_Org_Hdr.aspx(.cs) / clsHSE_Training_Org_Hdr.cs:
  - Required to create: Org Name (75), Address (100), Location. Country is
    taken from the location, never typed.
  - Name and Location are fixed once saved; address, the two contact people
    and their phone numbers (50 / 15 characters) and the email (30, must look
    like an email) stay editable.
  - A trainer needs a first and last name (25 each); middle name (25),
    qualification (50), mobile (digits only, 15) and email (50, must look
    like an email) are optional. Trainers can be added, edited and deleted.
  - Deleting an org deletes its trainers (legacy deleted only the org).
Legacy's Training Log points at these rows by id, so imported ids were kept.
Excel export of the orgs and their trainers is an addition.
"""

import re

from django.db.models import Count
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from . import audit as _audit
from .masters_views import BaseMasterViewSet
from .models import HseTrainingOrgDtl, HseTrainingOrgHdr
from .permissions import HasMenuPermission
from .xlsx_export import build_xlsx_response

ENTITY_KEY = "qhse.training_org"
TITLE = "Training Org"
_AUDIT_READ_ONLY = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


def _optional(max_length, **kw):
    return serializers.CharField(max_length=max_length, required=False, allow_blank=True, allow_null=True, **kw)


def _blank_to_none(attrs, names):
    for n in names:
        if n in attrs and isinstance(attrs[n], str):
            attrs[n] = attrs[n].strip() or None


class TrainingOrgHdrSerializer(serializers.ModelSerializer):
    training_org_name = serializers.CharField(max_length=75)
    training_org_address = serializers.CharField(max_length=100)
    contact_person_1 = _optional(50)
    tel_no_1 = _optional(15)
    contact_person_2 = _optional(50)
    tel_no_2 = _optional(15)
    training_org_email = serializers.EmailField(max_length=30, required=False, allow_blank=True, allow_null=True)
    location_name = serializers.CharField(source="location.location_name", read_only=True)
    country_name = serializers.CharField(source="country.country_name", read_only=True)
    dtl_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = HseTrainingOrgHdr
        fields = "__all__"
        read_only_fields = ["country", *_AUDIT_READ_ONLY]

    def validate(self, attrs):
        inst = self.instance
        for name in ("training_org_name", "training_org_address"):
            if name in attrs:
                attrs[name] = attrs[name].strip()
                if not attrs[name]:
                    raise serializers.ValidationError({name: "This field is required."})
        _blank_to_none(attrs, ("contact_person_1", "tel_no_1", "contact_person_2", "tel_no_2", "training_org_email"))
        if inst is not None:
            for locked, msg in (("training_org_name", "The name can't be changed once it is saved."), ("location", "The location can't be changed once it is saved.")):
                if locked in attrs and attrs[locked] != getattr(inst, locked):
                    raise serializers.ValidationError({locked: msg})
        elif "location" in attrs:
            attrs["country"] = attrs["location"].country
        return attrs


class TrainingOrgHdrViewSet(BaseMasterViewSet):
    queryset = HseTrainingOrgHdr.objects.select_related("location", "country").annotate(dtl_count=Count("dtls"))
    serializer_class = TrainingOrgHdrSerializer
    entity_key = ENTITY_KEY
    name_field = "training_org_name"
    permission_classes = [HasMenuPermission]
    search_fields = ["training_org_name", "location__location_name", "contact_person_1", "contact_person_2"]

    def label_for(self, instance):
        return f"Training Org {instance.training_org_name}"

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        count = instance.dtl_count
        label, pk = self.label_for(instance), instance.pk
        instance.delete()
        _audit.record_action(
            request, "delete", self.entity_key, pk, label, {"trainers_deleted": {"old": count, "new": 0}} if count else None
        )
        return Response(status=204)

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        qs = self.filter_queryset(self.get_queryset())
        rows = []
        for h in qs:
            base = [h.training_org_name, h.training_org_address, h.location.location_name, h.country.country_name,
                    h.contact_person_1 or "", h.tel_no_1 or "", h.contact_person_2 or "", h.tel_no_2 or "", h.training_org_email or ""]
            trainers = list(h.dtls.order_by("training_org_dtl_id"))
            if not trainers:
                rows.append(base + ["", "", "", ""])
            for t in trainers:
                rows.append(base + [
                    " ".join(p for p in (t.trainer_fname, t.trainer_mname, t.trainer_lname) if p),
                    t.trainer_qualification or "", t.trainer_mobile_no or "", t.trainer_email_id or "",
                ])
        _audit.record_action(
            request, "export", self.entity_key, record_label=f"{TITLE} list export",
            changes={**{k: {"old": None, "new": v} for k, v in request.query_params.items() if v}, "rows_exported": {"old": None, "new": len(rows)}},
        )
        return build_xlsx_response(
            f"{TITLE}.xlsx", TITLE, [TITLE],
            ["Org Name", "Address", "Location", "Country", "Contact Person 1", "Tel No 1", "Contact Person 2", "Tel No 2", "Org Email",
             "Trainer", "Qualification", "Trainer Mobile", "Trainer Email"],
            rows, wide_columns=(1,),
        )


class TrainingOrgDtlSerializer(serializers.ModelSerializer):
    trainer_fname = serializers.CharField(max_length=25)
    trainer_lname = serializers.CharField(max_length=25)
    trainer_mname = _optional(25)
    trainer_qualification = _optional(50)
    trainer_mobile_no = serializers.RegexField(r"^\d*$", max_length=15, required=False, allow_blank=True, allow_null=True,
                                               error_messages={"invalid": "Mobile number can contain digits only."})
    trainer_email_id = serializers.EmailField(max_length=50, required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = HseTrainingOrgDtl
        fields = "__all__"
        read_only_fields = _AUDIT_READ_ONLY

    def validate(self, attrs):
        for name in ("trainer_fname", "trainer_lname"):
            if name in attrs:
                attrs[name] = attrs[name].strip()
                if not attrs[name]:
                    raise serializers.ValidationError({name: "This field is required."})
        _blank_to_none(attrs, ("trainer_mname", "trainer_qualification", "trainer_mobile_no", "trainer_email_id"))
        if self.instance is not None and "hdr" in attrs and attrs["hdr"] != self.instance.hdr:
            raise serializers.ValidationError({"hdr": "Can't be changed — delete the trainer and add them again."})
        return attrs


class TrainingOrgDtlViewSet(BaseMasterViewSet):
    queryset = HseTrainingOrgDtl.objects.select_related("hdr")
    serializer_class = TrainingOrgDtlSerializer
    entity_key = ENTITY_KEY
    permission_classes = [HasMenuPermission]
    # Trainers are part of editing the org, so Edit is enough as well.
    action_perm_overrides = {"create": ("add", "edit"), "destroy": ("edit", "delete")}

    def get_queryset(self):
        qs = self.queryset
        if self.request.query_params.get("hdr"):
            qs = qs.filter(hdr_id=self.request.query_params["hdr"])
        return qs.order_by("training_org_dtl_id")

    def label_for(self, instance):
        return f"{instance.hdr.training_org_name} — {instance.trainer_fname} {instance.trainer_lname}"
