"""Rig Personnel > New Joinee Workflow > Print Offer Letter: approved offer letters, ready to be viewed as a PDF (and, later, mailed to the applicant).

A separate, read-only page (new in this system, not a port of the legacy print screen): a list of approved letters with the same details as the Offer Letter
page, a "View offer letter" button that opens the PDF (hr/offer_letter_pdf.py), and the places for the mail buttons. Sending mail is NOT configured yet: the Send mail
button only answers that it is not set up. Letter status Sent / Resent (set when mail is sent, later) shows as the mail status.
Who sees what: the page's own right (hr.fs_offer_letter_print) plus the person's FS categories, as on the Applicants and Offer Letter pages. Nothing is changed here.
"""

from django.db.models import Q
from django.http import HttpResponse
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from core import audit as _audit
from core.permissions import HasMenuPermission
from core.training_group import allowed_category_ids
from hr import offer_letter_mail, offer_letter_pdf
from hr.models import FsOfferLetter
from hr.views import HrMasterViewSet
from hr.views.offer_letters import OfferLetterSerializer

ENTITY_KEY = "hr.fs_offer_letter_print"
MAIL_STATUS = {"S": "Sent", "R": "Resent"}  # a letter that was never sent says "Not sent"


class OfferLetterPrintSerializer(OfferLetterSerializer):
    """The offer letter as the Offer Letter page shows it, plus what printing needs: which template, whether it can be printed, why not, and the mail status."""

    template = serializers.SerializerMethodField()
    template_label = serializers.SerializerMethodField()
    print_problems = serializers.SerializerMethodField()
    print_warnings = serializers.SerializerMethodField()
    can_print = serializers.SerializerMethodField()
    mail_problems = serializers.SerializerMethodField()
    mail_status = serializers.SerializerMethodField()
    emp_type_name = serializers.CharField(source="fs_new_appl.appl_emp_type.emp_type_name", read_only=True, default="")

    def get_template(self, obj):
        return offer_letter_pdf.template_for(obj)

    def get_template_label(self, obj):
        return offer_letter_pdf.TEMPLATE_LABEL[offer_letter_pdf.template_for(obj)]

    def get_print_problems(self, obj):
        return offer_letter_pdf.problems_for(obj)

    def get_print_warnings(self, obj):
        return offer_letter_pdf.warnings_for(obj)

    def get_can_print(self, obj):
        return not offer_letter_pdf.problems_for(obj)

    def get_mail_problems(self, obj):
        return offer_letter_mail.mail_problems(obj)

    def get_mail_status(self, obj):
        return MAIL_STATUS.get(obj.offer_letter_status, "Not sent")


class OfferLetterPrintViewSet(HrMasterViewSet):
    queryset = FsOfferLetter.objects.filter(cr_status="F", l1_approval_status="A").select_related(
        "fs_new_appl", "fs_new_appl__appl_fs_category", "fs_new_appl__appl_emp_type", "rank", "rig_site_mapping", "rig_site_mapping__rig", "company", "authority_user",
        "travel_eligibility", "travel_eligibility__rank",
    ).prefetch_related("components__component")
    serializer_class = OfferLetterPrintSerializer
    entity_key = ENTITY_KEY
    name_field = "fs_offer_letter_dt"
    permission_classes = [HasMenuPermission]
    lookup = False
    http_method_names = ["get", "head", "options", "post"]  # no create / edit / delete here; the only POST is the Send mail button
    search_fields = ["fs_new_appl__fs_emp_fname", "fs_new_appl__fs_emp_lname", "rig_site_mapping__rig__rig_name", "rank__rank_name"]
    action_perm_overrides = {"pdf": "view", "send_mail": "view", "send_mail_bulk": "view", "meta": "view"}

    _ORDERINGS = {
        "recent": ("-fs_offer_letter_dt", "-fs_new_appl_id"),
        "dt": ("fs_offer_letter_dt", "fs_new_appl_id"), "-dt": ("-fs_offer_letter_dt", "-fs_new_appl_id"),
        "name": ("fs_new_appl__fs_emp_lname", "fs_new_appl__fs_emp_fname"), "-name": ("-fs_new_appl__fs_emp_lname", "-fs_new_appl__fs_emp_fname"),
        "doj": ("fs_offer_letter_doj",), "-doj": ("-fs_offer_letter_doj",),
    }

    def get_queryset(self):
        qs = self.queryset
        allowed = allowed_category_ids(self.request)
        if allowed is not None:
            qs = qs.filter(fs_new_appl__appl_fs_category_id__in=allowed)
        if self.action != "list":
            return qs
        p = self.request.query_params
        if p.get("template") == offer_letter_pdf.PER_DAY:
            qs = qs.filter(fs_new_appl__appl_emp_type_id=offer_letter_pdf.PER_DAY_EMP_TYPE)
        elif p.get("template") == offer_letter_pdf.FIXED_TERM:
            qs = qs.exclude(fs_new_appl__appl_emp_type_id=offer_letter_pdf.PER_DAY_EMP_TYPE)
        if p.get("response"):
            qs = qs.filter(response_status=p["response"]) if p["response"] != "N" else qs.filter(Q(response_status="N") | Q(response_status=""))
        if p.get("mail") == "sent":
            qs = qs.filter(offer_letter_status__in=["S", "R"])
        elif p.get("mail") == "not_sent":
            qs = qs.exclude(offer_letter_status__in=["S", "R"])
        if p.get("rig"):
            qs = qs.filter(rig_site_mapping__rig_id=p["rig"])
        if p.get("year", "").isdigit():
            qs = qs.filter(fs_offer_letter_dt__year=int(p["year"]))
        if p.get("category", "").isdigit():
            qs = qs.filter(fs_new_appl__appl_fs_category_id=int(p["category"]))
        return qs.order_by(*(self._ORDERINGS.get(p.get("ordering")) or self._ORDERINGS["recent"]))

    def create(self, request, *args, **kwargs):
        return Response({"error": "Offer letters are made on the Offer Letter page."}, status=405)

    def label_for(self, instance):
        return f"{instance.fs_new_appl} — offer letter {instance.fs_offer_letter_dt}"

    @action(detail=False, methods=["get"], url_path="meta")
    def meta(self, request):
        years = [d.year for d in FsOfferLetter.objects.filter(cr_status="F", l1_approval_status="A").dates("fs_offer_letter_dt", "year", order="DESC")]
        return Response({"years": years, "templates": [{"value": k, "label": v} for k, v in offer_letter_pdf.TEMPLATE_LABEL.items()],
                         "responses": [{"value": "N", "label": "New"}, {"value": "A", "label": "Accepted"}, {"value": "D", "label": "Declined"}, {"value": "C", "label": "Closed"}]})

    @action(detail=True, methods=["get"], url_path="pdf")
    def pdf(self, request, pk=None):
        """The letter as a PDF. ?letterhead=0 leaves out the header and footer images (for pre-printed stationery)."""
        letter = self.get_object()
        with_letterhead = request.query_params.get("letterhead", "1") not in ("0", "false", "no")
        try:
            data = offer_letter_pdf.render_offer_letter_pdf(letter, with_letterhead=with_letterhead)
        except offer_letter_pdf.LetterNotReady as exc:
            return Response({"error": str(exc)}, status=400)
        _audit.record_action(request, "export", self.entity_key, letter.pk, self.label_for(letter), {"offer_letter_pdf": {"old": None, "new": "with letterhead" if with_letterhead else "without letterhead"}})
        response = HttpResponse(data, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{offer_letter_pdf.file_name(letter)}"'
        return response

    def _send_one(self, request, letter):
        """Checks one letter and mails it. Returns (ok, message)."""
        problems = offer_letter_mail.mail_problems(letter)
        if problems:
            return False, " ".join(problems)
        try:
            pdf = offer_letter_pdf.render_offer_letter_pdf(letter, with_letterhead=True)
            offer_letter_mail.send_offer_letter(letter, pdf, request)
        except offer_letter_mail.MailNotConfigured as exc:
            return False, str(exc)
        except offer_letter_pdf.LetterNotReady as exc:
            return False, str(exc)
        _audit.record_action(request, "update", self.entity_key, letter.pk, self.label_for(letter), {"offer_letter_mailed": {"old": None, "new": True}})
        return True, "Sent"

    @action(detail=True, methods=["post"], url_path="send-mail")
    def send_mail(self, request, pk=None):
        """Mails the letter to the applicant. Not configured yet: answers that, after checking the letter."""
        ok, message = self._send_one(request, self.get_object())
        return Response({"error": message} if not ok else {"sent": True}, status=200 if ok else (501 if message == offer_letter_mail.NOT_CONFIGURED else 400))

    @action(detail=False, methods=["post"], url_path="send-mail-bulk")
    def send_mail_bulk(self, request):
        """Mails several letters at once: body {"ids": [applicant ids]}. Each applicant gets his own mail with his own letter. Every letter is checked first and each gets its own
        result, so one bad letter never stops the rest. Mail is not configured yet: the answer says so and still lists which letters would go and which cannot, and why."""
        ids = request.data.get("ids")
        if not isinstance(ids, list) or not ids or not all(isinstance(i, int) for i in ids):
            return Response({"error": "Select at least one offer letter."}, status=400)
        if len(set(ids)) > offer_letter_mail.MAX_BULK:
            return Response({"error": f"Select at most {offer_letter_mail.MAX_BULK} letters at a time."}, status=400)
        letters = {l.pk: l for l in self.get_queryset().filter(pk__in=ids)}
        results = []
        for pk in dict.fromkeys(ids):
            letter = letters.get(pk)
            if letter is None:
                results.append({"id": pk, "name": "", "ok": False, "ready": False, "message": "Not found, or not an approved letter you can see."})
                continue
            problems = offer_letter_mail.mail_problems(letter)
            if problems:
                results.append({"id": pk, "name": str(letter.fs_new_appl), "ok": False, "ready": False, "message": " ".join(problems)})
                continue
            ok, message = self._send_one(request, letter)
            results.append({"id": pk, "name": str(letter.fs_new_appl), "ok": ok, "ready": True, "message": message})
        ready, sent = sum(1 for r in results if r["ready"]), sum(1 for r in results if r["ok"])
        body = {"results": results, "ready": ready, "sent": sent, "blocked": len(results) - ready}
        if not offer_letter_mail.MAIL_CONFIGURED:
            body["error"] = offer_letter_mail.NOT_CONFIGURED
            return Response(body, status=501)
        return Response(body)
