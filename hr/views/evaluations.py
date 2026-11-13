"""Rig Personnel > New Joinee Workflow > Candidate Competencies Details: the interviewers' ratings of a candidate (rules in hr/evaluation.py).

The list is the candidate picker (name, rank, rig, date only); one candidate's sheet is the detail; ratings are saved with POST .../ratings/; the legacy
Excel printout is .../evaluation-form/. Own page right "hr.candidate_competencies": View opens the sheet, Add or Edit saves ratings, Export prints. Which
departments a person may rate is NOT a page right: it comes from Masters > Interviewer Mapping (see hr.evaluation).
"""

from django.http import HttpResponse
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from core import audit as _audit
from core.permissions import HasMenuPermission
from hr import evaluation as ev
from hr.models import CandidateInterviewHdr
from hr.views import HrMasterViewSet

ENTITY_KEY = "hr.candidate_competencies"


class CandidatePickSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    rank_name = serializers.CharField(source="rank.rank_name", read_only=True, default="")
    rig_name = serializers.CharField(source="rig.rig_name", read_only=True, default="")
    hiring_status_label = serializers.SerializerMethodField()
    panels = serializers.SerializerMethodField()
    score = serializers.SerializerMethodField()
    max = serializers.SerializerMethodField()

    class Meta:
        model = CandidateInterviewHdr
        fields = ["candidate_interview_hdr_id", "full_name", "rank_name", "rig_name", "interview_dt", "hiring_status", "hiring_status_label", "panels", "score", "max"]

    def get_full_name(self, obj):
        return str(obj)

    def get_hiring_status_label(self, obj):
        return ev.HIRING_STATUS.get(obj.hiring_status, obj.hiring_status)

    def _stats(self, obj):
        return (self.context.get("stats") or {}).get(obj.pk) or {"panels": [], "score": None, "max": 0}

    def get_panels(self, obj):
        return self._stats(obj)["panels"]

    def get_score(self, obj):
        return self._stats(obj)["score"]

    def get_max(self, obj):
        return self._stats(obj)["max"]


class CandidateEvaluationViewSet(HrMasterViewSet):
    queryset = CandidateInterviewHdr.objects.select_related("rig", "rank")
    serializer_class = CandidatePickSerializer
    entity_key = ENTITY_KEY
    name_field = "candidate_fname"
    permission_classes = [HasMenuPermission]
    lookup = False
    http_method_names = ["get", "post", "head", "options"]
    search_fields = ["candidate_fname", "candidate_mname", "candidate_lname", "mobile_no", "email_id"]
    action_perm_overrides = {"ratings": ("add", "edit"), "evaluation_form": "export"}

    def get_queryset(self):
        from django.db.models import Count

        qs = self.queryset.annotate(rated_depts=Count("competencies__department", distinct=True))
        params = self.request.query_params
        for name in ("hiring_status",):
            if params.get(name):
                qs = qs.filter(**{name: params[name]})
        for name in ("rig", "rank"):
            if params.get(name):
                qs = qs.filter(**{f"{name}_id": params[name]})
        if params.get("year"):
            qs = qs.filter(interview_dt__year=params["year"])
        total = len(ev.department_ids())
        state = params.get("ratings")
        if state == "none":
            qs = qs.filter(rated_depts=0)
        elif state == "partly":
            qs = qs.filter(rated_depts__gt=0, rated_depts__lt=total)
        elif state == "full":
            qs = qs.filter(rated_depts__gte=total) if total else qs.none()
        orderings = {
            "interview_dt": ("interview_dt", "candidate_interview_hdr_id"), "-interview_dt": ("-interview_dt", "-candidate_interview_hdr_id"),
            "name": ("candidate_fname", "candidate_lname"), "-name": ("-candidate_fname", "-candidate_lname"),
        }
        return qs.order_by(*orderings.get(params.get("ordering"), orderings["-interview_dt"]))

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.filter_queryset(self.get_queryset()))
        stats = ev.rating_summary([h.pk for h in page])
        data = self.get_serializer(page, many=True, context={**self.get_serializer_context(), "stats": stats}).data
        return self.get_paginated_response(data)

    @action(detail=False, methods=["get"], url_path="meta")
    def meta(self, request):
        years = [d.year for d in CandidateInterviewHdr.objects.dates("interview_dt", "year", order="DESC")]
        return Response({"years": years, "hiring_status": [{"value": k, "label": v} for k, v in ev.HIRING_STATUS.items()]})

    def label_for(self, instance):
        return f"Interview ratings of {instance}"

    def retrieve(self, request, *args, **kwargs):
        hdr = self.get_object()
        return Response(ev.build_sheet(hdr, self._current_user_id(request)))

    @action(detail=True, methods=["post"], url_path="ratings")
    def ratings(self, request, pk=None):
        hdr = self.get_object()
        uid = self._current_user_id(request)
        try:
            changed = ev.save_ratings(hdr, uid, request.data.get("panels"))
        except ev.RatingError as bad:
            return Response({"errors": {str(k): v for k, v in bad.errors.items()}}, status=bad.status)
        if changed:
            names = {}
            from core.models import MstCompetency

            for c in MstCompetency.objects.filter(pk__in=changed.keys()).select_related("department"):
                names[c.pk] = f"{c.department.dept_dispname}: {c.competency_name.strip()}"
            diff = {}
            for cid, (old_r, old_m, new_r, new_m) in changed.items():
                if old_r != new_r:
                    diff[f"{names.get(cid, cid)} rating"] = {"old": old_r, "new": new_r}
                if (old_m or None) != (new_m or None):
                    diff[f"{names.get(cid, cid)} remarks"] = {"old": old_m, "new": new_m}
            _audit.record_action(request, "update", self.entity_key, hdr.pk, self.label_for(hdr), diff or None, target=hdr)
        return Response(ev.build_sheet(hdr, uid))

    @action(detail=True, methods=["get"], url_path="evaluation-form")
    def evaluation_form(self, request, pk=None):
        hdr = self.get_object()
        data = ev.build_workbook(hdr, self._current_user_id(request))
        response = HttpResponse(data, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f'attachment; filename="Interview Evaluation - {hdr}.xlsx"'
        _audit.record_action(request, "export", self.entity_key, hdr.pk, self.label_for(hdr), {"evaluation_form": {"old": None, "new": True}})
        return response
