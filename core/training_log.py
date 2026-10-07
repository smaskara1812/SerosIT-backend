"""QHSE → Training Log — rebuild of legacy frmHSE_Training_Log_Hdr (a training
session at a rig and the people who attended it).

Rules ported from frmHSE_Training_Log_Hdr.aspx(.cs) / clsHSE_Training_Log_Hdr.cs:
  - A log needs a Rig, a Course (a certificate that has active rank mappings),
    Training Date (not in the future), Location (50), Training Type (Internal
    or External), Duration in days, a Training Org, one of that org's trainers
    and Assessment Conducted (Y/N). The rig is fixed once saved.
  - A trainee's Training Party is "Seros" (our own staff — the old system's
    "EOSIL") or Operator / Visitor / Subcontractor / Other. For Seros the person
    is picked from the FS employee roster — active staff currently on that rig —
    and their category, name, designation (current rank), department (the
    rank's vessel department) and company (the rig's company on the training
    date) are copied in.
    Anyone else is typed: category, first and last name, designation (a rank of
    that category), department and company.
  - Certificate Issued is Y or N. Y needs the certificate number, its date (not
    in the future) and a valid-upto date (not before the issue date, and after
    today). N clears them and any uploaded file. A certificate file (image, PDF
    or Word) can be attached.
  - Once saved, only the certificate details of a trainee can change.
  - Deleting a log (a Delete right is an addition; legacy had none) deletes its
    trainees and their certificate files. Excel export is also an addition.
Rules about "active staff on the rig" and "not in the future" apply when a row
is created or the field is changed — old records are never re-judged.
"""

import os
from datetime import date

from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from . import audit as _audit
from .company_branding import resolve_rig_company_branding
from .masters_views import BaseMasterViewSet
from .media_uploads import media_url, save_media_file
from .models import (
    CertToRankMapping,
    FsCatgToRankMapping,
    FsEmpCurStatus,
    HseTrainingLogDtl,
    HseTrainingLogHdr,
    HseTrainingOrgDtl,
    HseTrainingOrgHdr,
    MstCert,
    MstFsCategory,
)
from .permissions import HasMenuPermission
from .training_group import allowed_category_ids
from .xlsx_export import build_xlsx_response

ENTITY_KEY = "qhse.training_log"
TITLE = "Training Log"
OWN_PARTY = "Seros"
OTHER_PARTIES = ("Operator", "Visitor", "Subcontractor", "Other")
CERT_SUBFOLDER = "training_cert"
CERT_EXTENSIONS = (".gif", ".png", ".jpeg", ".jpg", ".pdf", ".doc", ".docx")
_AUDIT_READ_ONLY = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]
CERT_FIELDS = ("certificate_issued", "certificate_no", "certificate_dt", "cert_valid_upto")


def _today():
    return timezone.now().date()


def _company_short(rig_id, on):
    return resolve_rig_company_branding(rig_id, on)["company_short_name"]


def _party_options():
    return [OWN_PARTY, *OTHER_PARTIES]


def _trainer_label(t):
    name = f"{t.trainer_fname} {t.trainer_lname}"
    return f"{name} ({t.trainer_qualification})" if t.trainer_qualification else name


def _staff_profile(status, on):
    """What a picked employee fills into a trainee row."""
    e = status.fs_emp
    return {
        "fs_category": status.fs_category,
        "trainee_fname": e.fs_emp_fname or "",
        "trainee_mname": e.fs_emp_mname or None,
        "trainee_lname": e.fs_emp_lname,
        "trainee_designation": status.rank.rank_name[:35],
        "trainee_department": status.rank.vessel_dept.vessel_dept_name[:50],
        "company_name": (_company_short(status.rig_id, on) or "")[:75],
    }


def _abs_path(rel):
    return os.path.join(settings.MEDIA_ROOT, rel.lstrip("/")) if rel else None


def _remove_file(rel):
    path = _abs_path(rel)
    if path and os.path.isfile(path):
        os.remove(path)


class TrainingLogHdrSerializer(serializers.ModelSerializer):
    rig_name = serializers.CharField(source="rig.rig_name", read_only=True)
    cert_name = serializers.CharField(source="cert.cert_name", read_only=True)
    training_org_name = serializers.CharField(source="training_org.training_org_name", read_only=True)
    trainer_name = serializers.SerializerMethodField()
    dtl_count = serializers.IntegerField(read_only=True, default=0)
    training_location = serializers.CharField(max_length=50)
    course_duration = serializers.IntegerField(min_value=1, max_value=255)
    assessment_conducted = serializers.ChoiceField(choices=("Y", "N"))

    class Meta:
        model = HseTrainingLogHdr
        fields = "__all__"
        read_only_fields = _AUDIT_READ_ONLY

    def get_trainer_name(self, obj):
        return _trainer_label(obj.training_org_dtl)

    def validate(self, attrs):
        inst = self.instance
        if "training_location" in attrs:
            attrs["training_location"] = attrs["training_location"].strip()
            if not attrs["training_location"]:
                raise serializers.ValidationError({"training_location": "This field is required."})

        if inst is not None and "rig" in attrs and attrs["rig"] != inst.rig:
            raise serializers.ValidationError({"rig": "The rig can't be changed once the log is saved."})

        training_dt = attrs.get("training_dt", getattr(inst, "training_dt", None))
        if training_dt and (inst is None or training_dt != inst.training_dt) and training_dt > _today():
            raise serializers.ValidationError({"training_dt": "Training Date can't be in the future."})

        cert = attrs.get("cert", getattr(inst, "cert", None))
        if cert and (inst is None or cert != inst.cert):
            if not CertToRankMapping.objects.filter(cert=cert, cert_to_rank_mapping_active="Y").exists():
                raise serializers.ValidationError({"cert": "Choose a course that has ranks mapped to it."})

        org = attrs.get("training_org", getattr(inst, "training_org", None))
        trainer = attrs.get("training_org_dtl", getattr(inst, "training_org_dtl", None))
        if org and trainer and trainer.hdr_id != org.pk:
            raise serializers.ValidationError({"training_org_dtl": "Choose a trainer from the selected Training Org."})
        return attrs


class TrainingLogHdrViewSet(BaseMasterViewSet):
    queryset = HseTrainingLogHdr.objects.select_related("rig", "cert", "training_org", "training_org_dtl").annotate(dtl_count=Count("dtls"))
    serializer_class = TrainingLogHdrSerializer
    entity_key = ENTITY_KEY
    permission_classes = [HasMenuPermission]
    search_fields = ["rig__rig_name", "cert__cert_name", "training_location", "training_org__training_org_name"]

    def get_queryset(self):
        qs = self.queryset
        p = self.request.query_params
        for param, lookup in (("rig", "rig_id"), ("cert", "cert_id"), ("training_type", "training_type"), ("year", "training_dt__year")):
            if p.get(param):
                qs = qs.filter(**{lookup: p[param]})
        return qs.order_by("-training_dt", "-pk")

    def label_for(self, instance):
        return f"Training Log {instance.rig.rig_name} — {instance.cert.cert_name} ({instance.training_dt:%d/%m/%Y})"

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        count = instance.dtl_count
        label, pk = self.label_for(instance), instance.pk
        for path in instance.dtls.exclude(certificate_path__isnull=True).values_list("certificate_path", flat=True):
            _remove_file(path)
        instance.delete()
        _audit.record_action(request, "delete", self.entity_key, pk, label, {"trainees_deleted": {"old": count, "new": 0}} if count else None)
        return Response(status=204)

    # ── lookups the form needs ────────────────────────────────────────────
    @action(detail=False, methods=["get"], url_path="certificates")
    def certificates(self, request):
        ids = CertToRankMapping.objects.filter(cert_to_rank_mapping_active="Y").values_list("cert_id", flat=True)
        return Response([{"id": c.pk, "name": c.cert_name} for c in MstCert.objects.filter(pk__in=ids).order_by("cert_name")])

    @action(detail=False, methods=["get"], url_path="orgs")
    def orgs(self, request):
        return Response([{"id": o.pk, "name": o.training_org_name} for o in HseTrainingOrgHdr.objects.order_by("training_org_name")])

    @action(detail=False, methods=["get"], url_path="trainers")
    def trainers(self, request):
        org = request.query_params.get("org")
        if not (org and org.isdigit()):
            return Response([])
        qs = HseTrainingOrgDtl.objects.filter(hdr_id=org).order_by("trainer_fname", "trainer_lname")
        return Response([{"id": t.pk, "name": _trainer_label(t)} for t in qs])

    @action(detail=False, methods=["get"], url_path="party-options")
    def party_options(self, request):
        return Response({"company": OWN_PARTY, "options": _party_options()})

    @action(detail=False, methods=["get"], url_path="employees")
    def employees(self, request):
        """Active staff currently on ?rig=, with the fields a trainee row copies."""
        rig = request.query_params.get("rig")
        if not (rig and rig.isdigit()):
            return Response([])
        qs = (
            FsEmpCurStatus.objects.filter(rig_id=rig, fs_emp_active="Y")
            .select_related("fs_emp", "rank", "rank__vessel_dept", "fs_category")
            .order_by("fs_emp__fs_emp_lname", "fs_emp__fs_emp_fname")
        )
        on = request.query_params.get("date")
        try:
            when = date.fromisoformat(on) if on else _today()
        except ValueError:
            when = _today()
        company = _company_short(int(rig), when) or ""
        return Response(
            [
                {
                    "id": s.fs_emp_id,
                    "name": f"{s.fs_emp} ({s.fs_emp.fs_emp_staff_id})" if s.fs_emp.fs_emp_staff_id else str(s.fs_emp),
                    "fs_category": s.fs_category_id,
                    "fs_category_name": s.fs_category.fs_category_name,
                    "designation": s.rank.rank_name,
                    "department": s.rank.vessel_dept.vessel_dept_name,
                    "company": company,
                }
                for s in qs
            ]
        )

    @action(detail=False, methods=["get"], url_path="categories")
    def categories(self, request):
        qs = MstFsCategory.objects.order_by("fs_category_name")
        allowed = allowed_category_ids(request)
        if allowed is not None:
            qs = qs.filter(pk__in=allowed)
        return Response([{"id": c.pk, "name": c.fs_category_name} for c in qs])

    @action(detail=False, methods=["get"], url_path="ranks")
    def ranks(self, request):
        category = request.query_params.get("category")
        if not (category and category.isdigit()):
            return Response([])
        seen, out = set(), []
        for m in FsCatgToRankMapping.objects.filter(fs_category_id=category).select_related("rank").order_by("rank__rank_name"):
            if m.rank_id not in seen:
                seen.add(m.rank_id)
                out.append({"id": m.rank_id, "name": m.rank.rank_name})
        return Response(out)

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        qs = self.filter_queryset(self.get_queryset())
        rows = []
        for h in qs:
            base = [
                h.training_dt.strftime("%d/%m/%Y"), h.rig.rig_name, h.cert.cert_name, h.training_location, h.training_type,
                h.course_duration, h.training_org.training_org_name, _trainer_label(h.training_org_dtl),
                "Yes" if h.assessment_conducted == "Y" else "No",
            ]
            trainees = list(h.dtls.select_related("fs_category").order_by("pk"))
            if not trainees:
                rows.append(base + [""] * 8)
            for t in trainees:
                rows.append(base + [
                    t.training_party, " ".join(p for p in (t.trainee_fname, t.trainee_mname, t.trainee_lname) if p), t.fs_category.fs_category_name,
                    t.trainee_designation, t.company_name, "Yes" if t.certificate_issued == "Y" else "No", t.certificate_no or "",
                    t.cert_valid_upto.strftime("%d/%m/%Y") if t.cert_valid_upto else "",
                ])
        _audit.record_action(
            request, "export", self.entity_key, record_label=f"{TITLE} export",
            changes={**{k: {"old": None, "new": v} for k, v in request.query_params.items() if v}, "rows_exported": {"old": None, "new": len(rows)}},
        )
        return build_xlsx_response(
            f"{TITLE}.xlsx", TITLE, [TITLE],
            ["Training Date", "Rig", "Course", "Location", "Type", "Days", "Training Org", "Trainer", "Assessment",
             "Party", "Trainee", "Category", "Designation", "Company", "Certificate Issued", "Certificate No.", "Valid Upto"],
            rows, wide_columns=(2, 6),
        )


class TrainingLogDtlSerializer(serializers.ModelSerializer):
    fs_category_name = serializers.CharField(source="fs_category.fs_category_name", read_only=True)
    fs_emp_name = serializers.SerializerMethodField()
    certificate_url = serializers.SerializerMethodField()
    certificate_issued = serializers.ChoiceField(choices=("Y", "N"))

    class Meta:
        model = HseTrainingLogDtl
        fields = "__all__"
        read_only_fields = [*_AUDIT_READ_ONLY, "certificate_path"]
        extra_kwargs = {
            "fs_category": {"required": False},
            "trainee_fname": {"required": False, "allow_blank": True},
            "trainee_lname": {"required": False, "allow_blank": True},
            "trainee_designation": {"required": False, "allow_blank": True},
            "trainee_department": {"required": False, "allow_blank": True},
            "company_name": {"required": False, "allow_blank": True},
            "trainee_mname": {"allow_blank": True, "allow_null": True},
            "certificate_no": {"allow_blank": True, "allow_null": True},
        }

    def get_fs_emp_name(self, obj):
        return str(obj.fs_emp) if obj.fs_emp_id else ""

    def get_certificate_url(self, obj):
        return media_url(self.context.get("request"), obj.certificate_path)

    # ── validation ────────────────────────────────────────────────────────
    def _certificate_rules(self, attrs, inst):
        issued = attrs.get("certificate_issued", getattr(inst, "certificate_issued", None))
        if issued == "N":
            attrs["certificate_no"] = attrs["certificate_dt"] = attrs["cert_valid_upto"] = None
            return
        no = (attrs.get("certificate_no", getattr(inst, "certificate_no", None)) or "").strip()
        issued_on = attrs.get("certificate_dt", getattr(inst, "certificate_dt", None))
        valid = attrs.get("cert_valid_upto", getattr(inst, "cert_valid_upto", None))
        if len(no) > 25:
            raise serializers.ValidationError({"certificate_no": "Certificate No. can be at most 25 characters."})
        errors = {}
        if not no:
            errors["certificate_no"] = "Enter the Certificate No."
        if not issued_on:
            errors["certificate_dt"] = "Enter the Certificate Date."
        elif (inst is None or "certificate_dt" in attrs and issued_on != inst.certificate_dt) and issued_on > _today():
            errors["certificate_dt"] = "Certificate Date can't be in the future."
        if not valid:
            errors["cert_valid_upto"] = "Enter the date the certificate is valid up to."
        else:
            if issued_on and valid < issued_on:
                errors["cert_valid_upto"] = "Valid Upto can't be before the Certificate Date."
            elif (inst is None or "cert_valid_upto" in attrs and valid != inst.cert_valid_upto) and valid <= _today():
                errors["cert_valid_upto"] = "Valid Upto must be after today."
        if errors:
            raise serializers.ValidationError(errors)
        attrs["certificate_no"] = no

    def validate(self, attrs):
        inst = self.instance
        if inst is not None:
            # After saving, only the certificate details can change.
            for name, value in attrs.items():
                if name not in CERT_FIELDS and getattr(inst, name) != value and not (value in ("", None) and getattr(inst, name) in ("", None)):
                    raise serializers.ValidationError({name: "Can't be changed — remove the trainee and add them again."})
            self._certificate_rules(attrs, inst)
            return attrs

        hdr = attrs["hdr"]
        party = (attrs.get("training_party") or "").strip()
        if party not in _party_options():
            raise serializers.ValidationError({"training_party": "Choose a Training Party from the list."})
        attrs["training_party"] = party

        if party == OWN_PARTY:
            emp = attrs.get("fs_emp")
            if emp is None:
                raise serializers.ValidationError({"fs_emp": "Select the employee."})
            status = FsEmpCurStatus.objects.filter(fs_emp=emp).select_related("fs_emp", "rank", "rank__vessel_dept", "fs_category").first()
            if not status or status.rig_id != hdr.rig_id or status.fs_emp_active != "Y":
                raise serializers.ValidationError({"fs_emp": "This employee isn't active on this rig."})
            attrs.update(_staff_profile(status, hdr.training_dt))
        else:
            attrs["fs_emp"] = None
            errors = {}
            for name, msg in (("fs_category", "Select the Category."), ("trainee_fname", "Enter the first name."), ("trainee_lname", "Enter the last name."),
                              ("trainee_designation", "Enter the Designation."), ("trainee_department", "Enter the Department."), ("company_name", "Enter the Company.")):
                value = attrs.get(name)
                if isinstance(value, str):
                    value = attrs[name] = value.strip()
                if not value:
                    errors[name] = msg
            if errors:
                raise serializers.ValidationError(errors)
            allowed = allowed_category_ids(self.context["request"])
            if allowed is not None and attrs["fs_category"].pk not in allowed:
                raise serializers.ValidationError({"fs_category": "You don't have access to this category."})
            if isinstance(attrs.get("trainee_mname"), str):
                attrs["trainee_mname"] = attrs["trainee_mname"].strip() or None
        self._certificate_rules(attrs, None)
        return attrs


class TrainingLogDtlViewSet(BaseMasterViewSet):
    queryset = HseTrainingLogDtl.objects.select_related("hdr", "fs_category", "fs_emp")
    serializer_class = TrainingLogDtlSerializer
    entity_key = ENTITY_KEY
    permission_classes = [HasMenuPermission]
    # Trainees are part of editing the log, so Edit is enough as well.
    action_perm_overrides = {"create": ("add", "edit"), "destroy": ("edit", "delete"), "certificate": ("add", "edit")}

    def get_queryset(self):
        qs = self.queryset
        if self.request.query_params.get("hdr"):
            qs = qs.filter(hdr_id=self.request.query_params["hdr"])
        return qs.order_by("pk")

    def label_for(self, instance):
        return f"{instance.hdr.rig.rig_name} {instance.hdr.training_dt:%d/%m/%Y} — {instance.trainee_fname} {instance.trainee_lname}"

    def perform_update(self, serializer):
        old_path = serializer.instance.certificate_path
        super().perform_update(serializer)
        inst = serializer.instance
        if inst.certificate_issued == "N" and old_path:
            _remove_file(old_path)
            inst.certificate_path = None
            inst.save(update_fields=["certificate_path"])

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        _remove_file(instance.certificate_path)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post", "delete"], url_path="certificate")
    def certificate(self, request, pk=None):
        if request.method == "DELETE":
            return self.delete_photo(request, pk)
        return self.upload_photo(request, pk)

    def upload_photo(self, request, pk=None):
        """The certificate file for a trainee (permission name shared with the
        other upload actions: Add or Edit)."""
        instance = self.get_object()
        if instance.certificate_issued != "Y":
            return Response({"error": "Set Certificate Issued to Yes before attaching a file."}, status=400)
        f = request.FILES.get("file")
        if not f:
            return Response({"error": "file is required"}, status=400)
        rel, error = save_media_file(f, CERT_SUBFOLDER, str(instance.pk), allowed_extensions=CERT_EXTENSIONS, max_size_mb=5)
        if error:
            return Response({"error": error}, status=400)
        if instance.certificate_path and instance.certificate_path != rel:
            _remove_file(instance.certificate_path)
        instance.certificate_path = rel
        instance.mod_user_id, instance.mod_dt = self._current_user_id(request), timezone.now()
        instance.save(update_fields=["certificate_path", "mod_user_id", "mod_dt"])
        _audit.record_action(request, "update", self.entity_key, instance.pk, self.label_for(instance), {"certificate_file": {"old": None, "new": rel}})
        return Response(self.get_serializer(instance).data)

    def delete_photo(self, request, pk=None):
        instance = self.get_object()
        if not instance.certificate_path:
            return Response({"error": "There is no file to remove."}, status=404)
        old = instance.certificate_path
        _remove_file(old)
        instance.certificate_path = None
        instance.mod_user_id, instance.mod_dt = self._current_user_id(request), timezone.now()
        instance.save(update_fields=["certificate_path", "mod_user_id", "mod_dt"])
        _audit.record_action(request, "update", self.entity_key, instance.pk, self.label_for(instance), {"certificate_file": {"old": old, "new": None}})
        return Response(self.get_serializer(instance).data)
