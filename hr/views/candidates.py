"""Rig Personnel > New Joinee Workflow > Candidate Interview Details.

Header (hr_candidate_interview_hdr) with its training and experience rows, plus read-only interviewer ratings. Rules come from the legacy page
(see CandidateInterviewHdr's docstring): checked only when the fields they involve are new or changed, so an old record that already breaks one can
still be edited for something else. The resume file is saved under media/candidate_resumes/<id>_<n>.<ext>.

One page, one right: the training, experience and rating rows share the header's entity key ("hr.candidate_interviews"), the way the HSE drill
tabs do. None of these lists may be used as a dropdown source (lookup = False): candidate records are personal data.
"""

import os
from datetime import date, timedelta

from django.conf import settings
from django.http import HttpResponse
from django.db.models import Count, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from core import audit as _audit
from core.media_uploads import media_url, next_sequence, save_media_file
from core.permissions import HasMenuPermission
from core.validation_helpers import fields_changed, is_valid_email, phone_error, EMAIL_MESSAGE
from hr.models import CandidateExperienceDtl, CandidateInterviewCompetency, CandidateInterviewHdr, CandidateTrainingDtl
from hr.resume_pdf import full_name, render_resume_pdf
from hr.views import HrMasterViewSet

ENTITY_KEY = "hr.candidate_interviews"
RESUME_FOLDER = "candidate_resumes"
RESUME_EXTENSIONS = (".pdf", ".doc", ".docx")
NEW_FLAG_HOURS = 24
HIRING_STATUS = {"N": "New", "R": "Rejected", "S": "Selected", "O": "On Hold"}
_AUDIT_READ_ONLY = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


def whole_months(start, end):
    """Complete months from start to end (the legacy page's own count: 2016-04-01 to 2018-11-30 is 2 years 7 months)."""
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return max(months, 0)


def _years_ago(today, years):
    try:
        return today.replace(year=today.year - years)
    except ValueError:  # 29 February
        return today.replace(year=today.year - years, day=28)


def _count(model):
    sub = model.objects.filter(hdr_id=OuterRef("pk")).order_by().values("hdr_id").annotate(c=Count("pk")).values("c")
    return Coalesce(Subquery(sub, output_field=IntegerField()), Value(0))


class CandidateInterviewHdrSerializer(serializers.ModelSerializer):
    rig_name = serializers.CharField(source="rig.rig_name", read_only=True, default="")
    rank_name = serializers.CharField(source="rank.rank_name", read_only=True, default="")
    full_name = serializers.SerializerMethodField()
    hiring_status_label = serializers.SerializerMethodField()
    resume_url = serializers.SerializerMethodField()
    resume_missing = serializers.SerializerMethodField()
    is_new_from_candidate = serializers.SerializerMethodField()
    trainings_count = serializers.IntegerField(read_only=True, default=0)
    experiences_count = serializers.IntegerField(read_only=True, default=0)
    competencies_count = serializers.IntegerField(read_only=True, default=0)

    suitable_for_role = serializers.ChoiceField(choices=["Y", "N"], allow_null=True, required=False, allow_blank=True)
    hiring_status = serializers.ChoiceField(choices=list(HIRING_STATUS), required=False)

    class Meta:
        model = CandidateInterviewHdr
        fields = "__all__"
        read_only_fields = _AUDIT_READ_ONLY + ["candidate_cert_path", "candidate_submitted_dt", "overall_performance"]

    def get_full_name(self, obj):
        return str(obj)

    def get_hiring_status_label(self, obj):
        return HIRING_STATUS.get(obj.hiring_status, obj.hiring_status)

    def _resume_file(self, obj):
        path = (obj.candidate_cert_path or "").strip()
        if not path or path.startswith(("N/", "/", "http")):
            return None
        return path if os.path.isfile(os.path.join(settings.MEDIA_ROOT, path)) else None

    def get_resume_url(self, obj):
        path = self._resume_file(obj)
        return media_url(self.context.get("request"), path) if path else None

    def get_resume_missing(self, obj):
        return bool((obj.candidate_cert_path or "").strip()) and self._resume_file(obj) is None

    def get_is_new_from_candidate(self, obj):
        sent = obj.candidate_submitted_dt
        if not sent:
            return False
        now = timezone.now() if timezone.is_aware(sent) else timezone.now().replace(tzinfo=None)
        return now - sent < timedelta(hours=NEW_FLAG_HOURS)

    def validate_email_id(self, value):
        if not is_valid_email(value):
            raise serializers.ValidationError(EMAIL_MESSAGE)
        return value.strip()

    def validate_mobile_no(self, value):
        message = phone_error(value)
        if message:
            raise serializers.ValidationError(message)
        return value.strip()

    def validate(self, attrs):
        inst = self.instance

        def val(name):
            if name in attrs:
                return attrs[name]
            return getattr(inst, name, None) if inst is not None else None

        errors = {}
        today = date.today()
        dob = val("candidate_dob")
        if dob and fields_changed(inst, attrs, "candidate_dob") and dob > _years_ago(today, 18):
            errors["candidate_dob"] = "The candidate must be at least 18 years old."
        interview = val("interview_dt")
        if interview and fields_changed(inst, attrs, "interview_dt") and interview > today:
            errors["interview_dt"] = "Interview date can't be in the future."
        for name, label in (("tot_experience_mths", "Total experience months"), ("exp_in_curr_pos_mths", "Months")):
            value = val(name)
            if value is not None and value > 11:
                errors[name] = f"{label} must be 0 to 11."
        total_y, total_m = val("tot_experience_yrs"), val("tot_experience_mths")
        cur_y, cur_m = val("exp_in_curr_pos_yrs"), val("exp_in_curr_pos_mths")
        if (cur_y is not None or cur_m is not None) and fields_changed(inst, attrs, "tot_experience_yrs", "tot_experience_mths", "exp_in_curr_pos_yrs", "exp_in_curr_pos_mths"):
            if ((cur_y or 0) * 12 + (cur_m or 0)) > ((total_y or 0) * 12 + (total_m or 0)):
                errors["exp_in_curr_pos_yrs"] = "Experience in the current position can't be more than total experience."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class CandidateInterviewViewSet(HrMasterViewSet):
    queryset = CandidateInterviewHdr.objects.select_related("rig", "rank").annotate(
        trainings_count=_count(CandidateTrainingDtl),
        experiences_count=_count(CandidateExperienceDtl),
        competencies_count=_count(CandidateInterviewCompetency),
    )
    serializer_class = CandidateInterviewHdrSerializer
    entity_key = ENTITY_KEY
    name_field = "candidate_fname"
    permission_classes = [HasMenuPermission]
    lookup = False
    search_fields = ["candidate_fname", "candidate_mname", "candidate_lname", "email_id", "mobile_no", "designated_post"]

    _ORDERINGS = {
        "recent": ("-cr_dt", "-candidate_interview_hdr_id"),  # the default: newest entries first, so a candidate's own submission is at the top
        "interview_dt": ("interview_dt", "candidate_interview_hdr_id"),
        "-interview_dt": ("-interview_dt", "-candidate_interview_hdr_id"),
        "name": ("candidate_fname", "candidate_lname"),
        "-name": ("-candidate_fname", "-candidate_lname"),
    }

    def get_queryset(self):
        qs = self.queryset
        params = self.request.query_params
        for name in ("hiring_status", "rig", "rank", "suitable_for_role"):
            if params.get(name):
                qs = qs.filter(**{f"{name}_id" if name in ("rig", "rank") else name: params[name]})
        if params.get("new") == "1":
            qs = qs.filter(candidate_submitted_dt__gte=timezone.now() - timedelta(hours=NEW_FLAG_HOURS))
        if params.get("year"):
            qs = qs.filter(interview_dt__year=params["year"])
        return qs.order_by(*self._ORDERINGS.get(params.get("ordering"), self._ORDERINGS["recent"]))

    def label_for(self, instance):
        return f"Candidate {instance}"

    @action(detail=False, methods=["get"], url_path="meta")
    def meta(self, request):
        years = [d.year for d in CandidateInterviewHdr.objects.dates("interview_dt", "year", order="DESC")]
        return Response({"years": years, "hiring_status": [{"value": k, "label": v} for k, v in HIRING_STATUS.items()]})

    @action(detail=True, methods=["get"], url_path="resume-pdf")
    def resume_pdf(self, request, pk=None):
        """Generate Resume: the Bio Data of Key Personnel sheet, built from the saved record (hr/resume_pdf.py). Needs View on the page."""
        instance = self.get_object()
        pdf = render_resume_pdf(instance)
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="Resume - {full_name(instance)}.pdf"'
        _audit.record_action(request, "export", self.entity_key, instance.pk, self.label_for(instance), {"resume_generated": {"old": None, "new": True}})
        return response

    @action(detail=True, methods=["post"], url_path="resume")
    def upload_resume(self, request, pk=None):
        """Saves the resume (PDF, DOC or DOCX) as candidate_resumes/<id>_<n>.<ext> and points the record at it. An earlier file is kept on disk;
        the History log holds the old and new path."""
        instance = self.get_object()
        f = request.FILES.get("file")
        if not f:
            return Response({"error": "file is required"}, status=400)
        seq = next_sequence(RESUME_FOLDER, instance.pk)
        rel_path, error = save_media_file(f, RESUME_FOLDER, f"{instance.pk}_{seq}", allowed_extensions=RESUME_EXTENSIONS)
        if error:
            return Response({"error": error}, status=400)
        old = instance.candidate_cert_path
        uid = self._current_user_id(request)
        CandidateInterviewHdr.objects.filter(pk=instance.pk).update(candidate_cert_path=rel_path, mod_user_id=uid or 1, mod_dt=timezone.now())
        _audit.record_action(
            request, "update", self.entity_key, instance.pk, self.label_for(instance),
            {"candidate_cert_path": {"old": old or None, "new": rel_path}}, target=instance,
        )
        instance.refresh_from_db()
        return Response(self.get_serializer(self.get_queryset().get(pk=instance.pk)).data, status=200)

    def perform_create(self, serializer):
        uid = self._current_user_id(self.request)
        instance = serializer.save(cr_user_id=uid or 1, cr_dt=timezone.now(), hiring_status=serializer.validated_data.get("hiring_status") or "N")
        changes = {k: {"old": None, "new": v} for k, v in self._snapshot(instance).items() if v not in (None, "")}
        _audit.record_action(self.request, "create", self.entity_key, instance.pk, self.label_for(instance), changes or None, target=instance)

    def perform_update(self, serializer):
        old_snapshot = self._snapshot(serializer.instance)
        uid = self._current_user_id(self.request)
        instance = serializer.save(mod_user_id=uid or 1, mod_dt=timezone.now())
        changes = self._diff(old_snapshot, self._snapshot(instance))
        _audit.record_action(self.request, "update", self.entity_key, instance.pk, self.label_for(instance), changes or None, target=instance)


# ── Child rows ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

class CandidateTrainingSerializer(serializers.ModelSerializer):
    class Meta:
        model = CandidateTrainingDtl
        fields = "__all__"
        read_only_fields = _AUDIT_READ_ONLY

    def validate(self, attrs):
        inst = self.instance
        valid_from = attrs.get("cert_valid_from_dt", getattr(inst, "cert_valid_from_dt", None))
        valid_to = attrs.get("cert_valid_to_dt", getattr(inst, "cert_valid_to_dt", None))
        issued = attrs.get("training_cert_dt", getattr(inst, "training_cert_dt", None))
        errors = {}
        if valid_from and valid_to and valid_to < valid_from and fields_changed(inst, attrs, "cert_valid_from_dt", "cert_valid_to_dt"):
            errors["cert_valid_to_dt"] = "Valid upto can't be before valid from."
        if issued and issued > date.today() and fields_changed(inst, attrs, "training_cert_dt"):
            errors["training_cert_dt"] = "Certificate date can't be in the future."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class CandidateExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CandidateExperienceDtl
        fields = "__all__"
        read_only_fields = _AUDIT_READ_ONLY + ["exp_years", "exp_months"]

    def validate(self, attrs):
        inst = self.instance
        start = attrs.get("exp_from_dt", getattr(inst, "exp_from_dt", None))
        end = attrs.get("exp_to_dt", getattr(inst, "exp_to_dt", None))
        errors = {}
        if start and end and end < start:
            errors["exp_to_dt"] = "To date can't be before the from date."
        if end and end > date.today() and fields_changed(inst, attrs, "exp_to_dt"):
            errors["exp_to_dt"] = "To date can't be in the future."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def _with_duration(self, validated):
        start = validated.get("exp_from_dt", getattr(self.instance, "exp_from_dt", None))
        end = validated.get("exp_to_dt", getattr(self.instance, "exp_to_dt", None))
        months = whole_months(start, end)
        validated["exp_years"], validated["exp_months"] = divmod(months, 12)
        return validated

    def create(self, validated):
        return super().create(self._with_duration(validated))

    def update(self, instance, validated):
        return super().update(instance, self._with_duration(validated))


class CandidateCompetencySerializer(serializers.ModelSerializer):
    competency_name = serializers.CharField(source="competency.competency_name", read_only=True)
    department_name = serializers.CharField(source="department.dept_dispname", read_only=True, default="")
    interviewer_name = serializers.SerializerMethodField()

    class Meta:
        model = CandidateInterviewCompetency
        fields = "__all__"
        read_only_fields = _AUDIT_READ_ONLY

    def get_interviewer_name(self, obj):
        return obj.interviewer.user.user_login_id if obj.interviewer_id else ""


class _CandidateChildMixin:
    """One candidate at a time (?hdr=<id>), like the legacy grids. A mixin, not a viewset: HrMasterViewSet refuses a class with no queryset."""

    permission_classes = [HasMenuPermission]
    entity_key = ENTITY_KEY
    lookup = False
    order_field = None

    def get_queryset(self):
        qs = self.queryset
        hdr = self.request.query_params.get("hdr")
        if hdr:
            qs = qs.filter(hdr_id=hdr)
        return qs.order_by(self.order_field)

    def label_for(self, instance):
        return f"{instance.hdr} — {getattr(instance, self.label_field) or ''}"[:120]


class CandidateTrainingViewSet(_CandidateChildMixin, HrMasterViewSet):
    queryset = CandidateTrainingDtl.objects.select_related("hdr")
    serializer_class = CandidateTrainingSerializer
    name_field = "training_type"
    label_field = "training_type"
    order_field = "candidate_train_dtl_id"


class CandidateExperienceViewSet(_CandidateChildMixin, HrMasterViewSet):
    queryset = CandidateExperienceDtl.objects.select_related("hdr")
    serializer_class = CandidateExperienceSerializer
    name_field = "company_name"
    label_field = "company_name"
    order_field = "exp_from_dt"


class CandidateCompetencyViewSet(_CandidateChildMixin, HrMasterViewSet):
    """Interviewer ratings, read only for now."""

    queryset = CandidateInterviewCompetency.objects.select_related("hdr", "competency", "department", "interviewer", "interviewer__user")
    serializer_class = CandidateCompetencySerializer
    name_field = "remarks"
    label_field = "remarks"
    order_field = "candidate_interview_comp_id"
    http_method_names = ["get", "head", "options"]
