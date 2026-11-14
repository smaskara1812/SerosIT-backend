"""Rig Personnel > New Joinee Workflow > Applicants: people applying for field-staff (crew) jobs (legacy page frmFs_New_Appl_Dtl, procedure
Prc_Fs_New_Appl_Dtl; model docstring in hr/models.py FsNewApplDtl).

What the legacy page did and this one keeps:
  * the list shows applications that have not joined AND, as asked for this system, applicants who were sent an offer letter, with a flag; a person only sees and adds
    applicants of the FS categories he is mapped to (Masters > User FS Category Mapping, open today); an App Admin sees all;
  * application number = highest + 1; status starts N and is moved by the hiring flow only;
  * name, nationality, date of birth, gender and application date cannot be changed after saving; the rest can;
  * a "not to be rehired" match (date of birth plus first or last name, business system 6) must be confirmed before a new applicant is saved; a likely duplicate
    (same last name and date of birth) is only a warning (the legacy check was switched off);
  * Re-hire: pick a former (inactive) employee, the form is filled from his record and his photo is copied; the old employee is kept on the application;
  * delete is refused for an applicant who joined and has an offer letter.
Photo and CV are uploaded after the first save (files are named by the applicant's id). The five CDC columns are not carried.
"""

import os
import shutil
from datetime import date

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from core import audit as _audit
from core.media_uploads import IMAGE_EXTENSIONS, media_url, next_sequence, save_media_file
from core.models import MstFsCategory, MstFsEmployee, MstRank
from core.permissions import HasMenuPermission
from core.training_group import allowed_category_ids
from core.validation_helpers import fields_changed, phone_error
from hr.models import CtrlNtbrFs, FsNewApplDtl
from hr.views import HrMasterViewSet

ENTITY_KEY = "hr.fs_applicants"
PHOTO_FOLDER, CV_FOLDER = "fs_applicant_photos", "fs_applicant_cv"
CV_EXTENSIONS = (".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".zip")
PHOTO_MB, CV_MB = 5, 10
STATUS = {"N": "New", "C": "Closed", "R": "Rejected", "A": "Accepted", "J": "Joined"}
BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
MIN_AGE = 15
FIXED_AFTER_SAVE = ("fs_emp_fname", "fs_emp_mname", "fs_emp_lname", "nationality", "fs_emp_dob", "gender", "fs_new_appl_dt")
NTBR_BUSINESS_SYSTEM = 6
_AUDIT_READ_ONLY = ["fs_new_appl_no", "fs_new_appl_status", "fs_emp", "fs_emp_photo_path", "cv_path", "cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]


def _years_ago(today, years):
    try:
        return today.replace(year=today.year - years)
    except ValueError:  # 29 February
        return today.replace(year=today.year - years, day=28)


def ntbr_matches(fname, lname, dob):
    """People in the not-to-be-rehired register of this business system with this date of birth and the same first or last name (case ignored)."""
    if not dob:
        return []
    fname, lname = (fname or "").strip().lower(), (lname or "").strip().lower()
    out = []
    for row in CtrlNtbrFs.objects.filter(business_system_id=NTBR_BUSINESS_SYSTEM, ntbr_fs_dob=dob):
        emp = MstFsEmployee.objects.filter(pk=row.fs_emp_id).first()
        if not emp:
            continue
        first, last = (emp.fs_emp_fname or "").strip().lower(), (emp.fs_emp_lname or "").strip().lower()
        if (fname and fname == first) or (lname and lname == last):
            out.append({"ntbr_fs_id": row.ntbr_fs_id, "name": str(emp), "dob": row.ntbr_fs_dob, "confirmed_dt": row.ntbr_cnfm_dt, "remark": row.remark,
                        "rejoin_allowed": row.ntbr_rejoin == "Y"})
    return out


class FsApplicantSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()
    category_name = serializers.CharField(source="appl_fs_category.fs_category_name", read_only=True, default="")
    rank_name = serializers.CharField(source="appl_rank.rank_name", read_only=True, default="")
    emp_type_name = serializers.CharField(source="appl_emp_type.emp_type_name", read_only=True, default="")
    nationality_name = serializers.CharField(source="nationality.country_name", read_only=True, default="")
    home_town_name = serializers.CharField(source="home_town.location_name", read_only=True, default="")
    domicile_state_name = serializers.CharField(source="domicile_state.country_state_name", read_only=True, default="")
    qualification_name = serializers.CharField(source="qualification.qualification_name", read_only=True, default="")
    pp_country_name = serializers.CharField(source="pp_country.country_name", read_only=True, default="")
    pp_place_name = serializers.CharField(source="pp_place.location_name", read_only=True, default="")
    offer_sent = serializers.SerializerMethodField()
    offer_letter_dt = serializers.SerializerMethodField()
    offer_letter_doj = serializers.SerializerMethodField()
    photo_url = serializers.SerializerMethodField()
    cv_url = serializers.SerializerMethodField()

    gender = serializers.ChoiceField(choices=["M", "F"])
    marital_status = serializers.ChoiceField(choices=["Unmarried", "Married"], required=False, allow_null=True, allow_blank=True)
    blood_group = serializers.ChoiceField(choices=BLOOD_GROUPS, required=False, allow_null=True, allow_blank=True)

    class Meta:
        model = FsNewApplDtl
        fields = "__all__"
        read_only_fields = _AUDIT_READ_ONLY

    def get_full_name(self, obj):
        return str(obj)

    def get_status_label(self, obj):
        return STATUS.get(obj.fs_new_appl_status, obj.fs_new_appl_status)

    def _offer(self, obj):
        return getattr(obj, "offer_letter", None)

    def get_offer_sent(self, obj):
        return self._offer(obj) is not None

    def get_offer_letter_dt(self, obj):
        o = self._offer(obj)
        return o.fs_offer_letter_dt if o else None

    def get_offer_letter_doj(self, obj):
        o = self._offer(obj)
        return o.fs_offer_letter_doj if o else None

    def _url(self, path, folder):
        if not path or not path.startswith(folder + "/") or not os.path.isfile(os.path.join(settings.MEDIA_ROOT, path)):
            return None
        return media_url(self.context.get("request"), path)

    def get_photo_url(self, obj):
        return self._url(obj.fs_emp_photo_path, PHOTO_FOLDER)

    def get_cv_url(self, obj):
        return self._url(obj.cv_path, CV_FOLDER)

    def validate(self, attrs):
        inst = self.instance
        request = self.context.get("request")
        today = date.today()

        def val(name):
            if name in attrs:
                return attrs[name]
            return getattr(inst, name, None) if inst is not None else None

        errors = {}
        if inst is not None:
            for name in FIXED_AFTER_SAVE:
                if name in attrs and fields_changed(inst, attrs, name):
                    errors[name] = "This can't be changed after the applicant is saved."
        if "prv_fs_emp" in attrs and inst is not None and fields_changed(inst, attrs, "prv_fs_emp"):
            errors["prv_fs_emp"] = "The former employee can't be changed after the applicant is saved."
        if inst is None:
            for name, msg in (("marital_status", "Select the marital status."), ("blood_group", "Select the blood group."), ("domicile_state", "Select the domicile state.")):
                if not val(name):
                    errors[name] = msg
        dob = val("fs_emp_dob")
        if dob and fields_changed(inst, attrs, "fs_emp_dob"):
            if dob >= today:
                errors["fs_emp_dob"] = "Date of birth must be before today."
            elif dob > _years_ago(today, MIN_AGE):
                errors["fs_emp_dob"] = f"The applicant must be at least {MIN_AGE} years old."
        applied = val("fs_new_appl_dt")
        if applied and fields_changed(inst, attrs, "fs_new_appl_dt") and applied > today:
            errors["fs_new_appl_dt"] = "The application date can't be in the future."
        married, marriage = val("marital_status") == "Married", val("marriage_dt")
        if married and not marriage and fields_changed(inst, attrs, "marital_status", "marriage_dt"):
            errors["marriage_dt"] = "Enter the marriage date."
        if marriage and fields_changed(inst, attrs, "marriage_dt") and marriage > today:
            errors["marriage_dt"] = "The marriage date can't be in the future."
        if not married and marriage:
            attrs["marriage_dt"] = None  # only a married applicant has a marriage date
        for name in ("fs_emp_tel_no", "fs_emp_mobile_no"):
            text = val(name)
            if text and fields_changed(inst, attrs, name):
                message = phone_error(text)
                if message:
                    errors[name] = message
        category, rank = val("appl_fs_category"), val("appl_rank")
        if category and fields_changed(inst, attrs, "appl_fs_category"):
            allowed = allowed_category_ids(request) if request else None
            if allowed is not None and category.pk not in allowed:
                errors["appl_fs_category"] = "You are not mapped to this category."
        if category and rank and fields_changed(inst, attrs, "appl_fs_category", "appl_rank") and rank.fs_category_id != category.pk:
            errors["appl_rank"] = "This rank does not belong to the category."
        prv = attrs.get("prv_fs_emp")
        if prv is not None and inst is None and prv.fs_emp_active == "Y":
            errors["prv_fs_emp"] = "This employee is still active. Only a former employee can be re-hired."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class FsApplicantViewSet(HrMasterViewSet):
    queryset = FsNewApplDtl.objects.select_related(
        "appl_fs_category", "appl_rank", "appl_emp_type", "nationality", "home_town", "domicile_state", "qualification", "pp_country", "pp_place", "offer_letter"
    )
    serializer_class = FsApplicantSerializer
    entity_key = ENTITY_KEY
    name_field = "fs_emp_lname"
    permission_classes = [HasMenuPermission]
    lookup = False
    search_fields = ["fs_emp_fname", "fs_emp_mname", "fs_emp_lname", "fs_emp_mobile_no", "fs_emp_email_pers"]
    action_perm_overrides = {
        "photo": ("add", "edit"), "cv": ("add", "edit"), "ntbr_check": ("add", "edit"), "rehire_search": "add", "rehire": "add", "categories": ("view", "add", "edit"),
    }

    _ORDERINGS = {
        "recent": ("-fs_new_appl_dt", "-fs_new_appl_id"),
        "dt": ("fs_new_appl_dt", "fs_new_appl_id"), "-dt": ("-fs_new_appl_dt", "-fs_new_appl_id"),
        "name": ("fs_emp_lname", "fs_emp_fname"), "-name": ("-fs_emp_lname", "-fs_emp_fname"),
        "no": ("fs_new_appl_no",), "-no": ("-fs_new_appl_no",),
    }

    def get_queryset(self):
        qs = self.queryset
        allowed = allowed_category_ids(self.request)
        if allowed is not None:
            qs = qs.filter(appl_fs_category_id__in=allowed)
        if self.action != "list":
            return qs
        p = self.request.query_params
        if p.get("status"):
            qs = qs.filter(fs_new_appl_status=p["status"])  # a chosen status shows exactly that, joined ones included
        elif p.get("scope") == "notjoined":
            qs = qs.exclude(fs_new_appl_status="J")  # the legacy list
        else:
            qs = qs.filter(~Q(fs_new_appl_status="J") | Q(offer_letter__isnull=False))  # not joined, or sent an offer letter
        if p.get("offer") == "sent":
            qs = qs.filter(offer_letter__isnull=False)
        elif p.get("offer") == "none":
            qs = qs.filter(offer_letter__isnull=True)
        if p.get("category"):
            qs = qs.filter(appl_fs_category_id=p["category"])
        if p.get("rank"):
            qs = qs.filter(appl_rank_id=p["rank"])
        if p.get("year"):
            qs = qs.filter(fs_new_appl_dt__year=p["year"])
        return qs.order_by(*self._ORDERINGS.get(p.get("ordering"), self._ORDERINGS["recent"]))

    def label_for(self, instance):
        return f"Applicant {instance}"

    # ── lists for the form and the page ─────────────────────────────────────────────────────────────────────────────────────────────────────

    def _categories(self, request):
        allowed = allowed_category_ids(request)
        qs = MstFsCategory.objects.order_by("fs_category_name")
        return qs if allowed is None else qs.filter(pk__in=allowed)

    @action(detail=False, methods=["get"], url_path="categories")
    def categories(self, request):
        """The FS categories this person may work with, in the shape a dropdown reads."""
        return Response([{"fs_category_id": c.pk, "fs_category_name": c.fs_category_name} for c in self._categories(request)])

    @action(detail=False, methods=["get"], url_path="meta")
    def meta(self, request):
        years = [d.year for d in FsNewApplDtl.objects.dates("fs_new_appl_dt", "year", order="DESC")]
        return Response({"years": years, "statuses": [{"value": k, "label": v} for k, v in STATUS.items()],
                         "categories": [{"id": c.pk, "name": c.fs_category_name} for c in self._categories(request)]})

    # ── the checks before saving a new applicant ────────────────────────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=["get"], url_path="ntbr-check")
    def ntbr_check(self, request):
        """?fname&lname&dob=YYYY-MM-DD(&exclude=<applicant id>): not-to-be-rehired matches (must be confirmed) and likely duplicates (a warning)."""
        p = request.query_params
        try:
            dob = date.fromisoformat(p.get("dob", ""))
        except ValueError:
            return Response({"ntbr": [], "duplicates": []})
        duplicates = []
        # A duplicate is someone still on the books with the same last name and date of birth: an application not yet joined/closed (New or Accepted),
        # or a working (active) employee. A person who joined and has since left is not one, and a re-hire (?rehire=1) is never checked.
        if p.get("lname") and not p.get("rehire"):
            lname = p["lname"].strip()
            qs = FsNewApplDtl.objects.filter(fs_emp_lname__iexact=lname, fs_emp_dob=dob, fs_new_appl_status__in=["N", "A"])
            allowed = allowed_category_ids(request)
            if allowed is not None:
                qs = qs.filter(appl_fs_category_id__in=allowed)
            if p.get("exclude", "").isdigit():
                qs = qs.exclude(pk=int(p["exclude"]))
            duplicates = [{"id": a.pk, "name": str(a), "application_no": a.fs_new_appl_no, "application_dt": a.fs_new_appl_dt, "status": STATUS.get(a.fs_new_appl_status, ""),
                           "kind": "application"} for a in qs.order_by("-fs_new_appl_id")[:5]]
            emps = MstFsEmployee.objects.filter(fs_emp_lname__iexact=lname, fs_emp_dob=dob, fs_emp_active="Y")
            if allowed is not None:
                emps = emps.filter(fs_category_id__in=allowed)
            duplicates += [{"id": e.pk, "name": str(e), "kind": "employee", "status": "Working employee"} for e in emps[:5]]
        return Response({"ntbr": ntbr_matches(p.get("fname"), p.get("lname"), dob), "duplicates": duplicates})

    # ── re-hire ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=["get"], url_path="rehire-search")
    def rehire_search(self, request):
        """Former (not active) FS employees, of the categories this person may work with, matching ?search= (name)."""
        qs = MstFsEmployee.objects.exclude(fs_emp_active="Y").select_related("fs_category", "rank")
        allowed = allowed_category_ids(request)
        if allowed is not None:
            qs = qs.filter(fs_category_id__in=allowed)
        text = request.query_params.get("search", "").strip()
        for word in text.split()[:3]:
            qs = qs.filter(Q(fs_emp_fname__icontains=word) | Q(fs_emp_mname__icontains=word) | Q(fs_emp_lname__icontains=word))
        if not text:
            return Response([])
        return Response([{"fs_emp_id": e.pk, "name": str(e), "category": e.fs_category.fs_category_name, "rank": e.rank.rank_name, "dob": e.fs_emp_dob,
                          "left_dt": e.fs_emp_dol} for e in qs.order_by("fs_emp_lname", "fs_emp_fname")[:20]])

    @action(detail=False, methods=["get"], url_path="rehire")
    def rehire(self, request):
        """?emp=<former employee id>: the form values taken from his record (what the legacy Re-hire button filled in)."""
        emp = MstFsEmployee.objects.select_related("nationality", "home_town", "domicile_state", "qualification", "pp_country", "pp_place", "fs_category", "rank", "emp_type").filter(
            pk=request.query_params.get("emp") or 0).first()
        allowed = allowed_category_ids(request)
        if not emp or (allowed is not None and emp.fs_category_id not in allowed):
            return Response({"error": "Employee not found."}, status=404)
        if emp.fs_emp_active == "Y":
            return Response({"error": "This employee is still active. Only a former employee can be re-hired."}, status=400)
        copy = ["fs_emp_fname", "fs_emp_mname", "fs_emp_lname", "permanent_addr", "mailing_addr", "emergency_addr", "fs_emp_tel_no", "fs_emp_mobile_no", "fs_emp_email_pers", "gender",
                "blood_group", "fs_emp_dob", "fs_emp_pob", "marital_status", "marriage_dt", "religion", "pan_no", "aadhaar_no", "area_of_interest", "pp_no", "pp_dt", "pin_code",
                "pp_valid_till", "pp_ecnr"]
        data = {name: getattr(emp, name) for name in copy}
        for name in ("nationality", "home_town", "domicile_state", "qualification", "pp_country", "pp_place"):
            obj = getattr(emp, name)
            data[name] = obj.pk if obj else None
        data.update({
            "nationality_name": emp.nationality.country_name, "home_town_name": emp.home_town.location_name if emp.home_town else "",
            "domicile_state_name": emp.domicile_state.country_state_name if emp.domicile_state else "",
            "qualification_name": emp.qualification.qualification_name if emp.qualification else "",
            "pp_country_name": emp.pp_country.country_name if emp.pp_country else "", "pp_place_name": emp.pp_place.location_name if emp.pp_place else "",
            "appl_fs_category": emp.fs_category_id, "category_name": emp.fs_category.fs_category_name, "appl_rank": emp.rank_id, "rank_name": emp.rank.rank_name,
            "appl_emp_type": emp.emp_type_id, "emp_type_name": emp.emp_type.emp_type_name, "prv_fs_emp": emp.pk,
            "fs_new_appl_dt": date.today(),
        })
        return Response(data)

    # ── create and update ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────

    def create(self, request, *args, **kwargs):
        # not to be rehired: asks for a confirmation (the legacy page did too); the server checks again so a skipped screen cannot get past it
        data = request.data
        try:
            dob = date.fromisoformat(str(data.get("fs_emp_dob") or ""))
        except ValueError:
            dob = None
        found = ntbr_matches(data.get("fs_emp_fname"), data.get("fs_emp_lname"), dob)
        if found and str(data.get("ntbr_confirmed")).lower() not in ("true", "1", "y"):
            return Response({"ntbr": found, "error": "This person is in the not-to-be-rehired register. Confirm to save the application anyway."}, status=400)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        uid = self._current_user_id(self.request) or 1
        top = FsNewApplDtl.objects.order_by("-fs_new_appl_no").values_list("fs_new_appl_no", flat=True).first() or 0
        instance = serializer.save(fs_new_appl_no=top + 1, fs_new_appl_status="N", cr_user_id=uid, cr_dt=timezone.now())
        old = instance.prv_fs_emp
        if old and old.fs_emp_photo_path:  # a re-hire starts with the former employee's picture, as in the legacy page
            src = os.path.join(settings.MEDIA_ROOT, old.fs_emp_photo_path)
            if os.path.isfile(src):
                ext = os.path.splitext(src)[1].lower()
                name = f"{instance.pk}_{next_sequence(PHOTO_FOLDER, instance.pk)}{ext}"
                os.makedirs(os.path.join(settings.MEDIA_ROOT, PHOTO_FOLDER), exist_ok=True)
                shutil.copy2(src, os.path.join(settings.MEDIA_ROOT, PHOTO_FOLDER, name))
                FsNewApplDtl.objects.filter(pk=instance.pk).update(fs_emp_photo_path=f"{PHOTO_FOLDER}/{name}")
                instance.refresh_from_db()
        changes = {k: {"old": None, "new": v} for k, v in self._snapshot(instance).items() if v not in (None, "")}
        _audit.record_action(self.request, "create", self.entity_key, instance.pk, self.label_for(instance), changes or None, target=instance)

    def perform_update(self, serializer):
        old_snapshot = self._snapshot(serializer.instance)
        instance = serializer.save(mod_user_id=self._current_user_id(self.request) or 1, mod_dt=timezone.now())
        changes = self._diff(old_snapshot, self._snapshot(instance))
        _audit.record_action(self.request, "update", self.entity_key, instance.pk, self.label_for(instance), changes or None, target=instance)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.fs_new_appl_status == "J" and hasattr(instance, "offer_letter"):
            return Response({"error": "This applicant has already joined as an employee and cannot be deleted."}, status=400)
        label = self.label_for(instance)
        pre = _audit.before_delete(instance)
        instance.delete()
        _audit.log_deleted(request, self.entity_key, label, pre)
        return Response(status=204)

    # ── files ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

    def _set_file(self, request, instance, field, folder, extensions, max_mb):
        """POST a file to set it, DELETE to clear it. Nothing is deleted from disk (every file is kept as <id>_<n>.<ext>); the history log has the old and new name."""
        old = getattr(instance, field) or ""
        if request.method == "DELETE":
            new = None
        else:
            f = request.FILES.get("file")
            if not f:
                return Response({"error": "file is required"}, status=400)
            seq = next_sequence(folder, instance.pk)
            new, error = save_media_file(f, folder, f"{instance.pk}_{seq}", allowed_extensions=extensions, max_size_mb=max_mb)
            if error:
                return Response({"error": error}, status=400)
        FsNewApplDtl.objects.filter(pk=instance.pk).update(**{field: new, "mod_user_id": self._current_user_id(request) or 1, "mod_dt": timezone.now()})
        _audit.record_action(request, "update", self.entity_key, instance.pk, self.label_for(instance), {field: {"old": old or None, "new": new}}, target=instance)
        return Response(self.get_serializer(self.get_queryset().get(pk=instance.pk)).data)

    @action(detail=True, methods=["post", "delete"], url_path="photo")
    def photo(self, request, pk=None):
        return self._set_file(request, self.get_object(), "fs_emp_photo_path", PHOTO_FOLDER, IMAGE_EXTENSIONS, PHOTO_MB)

    @action(detail=True, methods=["post", "delete"], url_path="cv")
    def cv(self, request, pk=None):
        return self._set_file(request, self.get_object(), "cv_path", CV_FOLDER, CV_EXTENSIONS, CV_MB)
