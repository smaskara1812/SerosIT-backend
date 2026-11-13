"""Rig Personnel > Candidate Interview Details > Invites: HR creates an invitation, resends it, extends it or cancels it, and watches its progress.

Same page right as Candidate Interview Details ("hr.candidate_interviews"): the invites are a part of that page. The link is shown ONCE (on create and on
resend); only its hash is stored, so a resend makes a new link and the old one stops working. A resend keeps the person's saved draft.
"""

from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from core import audit as _audit
from core.permissions import HasMenuPermission
from hr import onboarding as ob
from hr.models import CandidateInvite
from hr.views import HrMasterViewSet

ENTITY_KEY = "hr.candidate_interviews"


class CandidateInviteSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    hdr_name = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()

    class Meta:
        model = CandidateInvite
        fields = [
            "candidate_invite_id", "candidate_name", "email_id", "expires_dt", "opened_dt", "verified_dt", "submitted_dt", "cancelled_dt", "hdr",
            "hdr_name", "draft_saved_dt", "last_mail_dt", "resend_count", "locked", "cr_dt", "status", "progress",
        ]
        read_only_fields = fields

    def get_status(self, obj):
        return ob.status_of(obj)

    def get_hdr_name(self, obj):
        return str(obj.hdr) if obj.hdr_id else ""

    def get_progress(self, obj):
        return ob.progress(ob.load_draft(obj)) if obj.draft and not obj.submitted_dt else None


class CandidateInviteViewSet(HrMasterViewSet):
    queryset = CandidateInvite.objects.select_related("hdr")
    serializer_class = CandidateInviteSerializer
    entity_key = ENTITY_KEY
    name_field = "candidate_name"
    permission_classes = [HasMenuPermission]
    lookup = False
    http_method_names = ["get", "post", "head", "options"]
    search_fields = ["candidate_name", "email_id"]
    action_perm_overrides = {"resend": "edit", "cancel": "edit", "extend": "edit"}

    def get_queryset(self):
        qs = self.queryset.order_by("-candidate_invite_id")
        status = self.request.query_params.get("status")
        now = timezone.now()
        if status == "submitted":
            qs = qs.filter(submitted_dt__isnull=False)
        elif status == "cancelled":
            qs = qs.filter(submitted_dt__isnull=True, cancelled_dt__isnull=False)
        elif status == "expired":
            qs = qs.filter(submitted_dt__isnull=True, cancelled_dt__isnull=True, expires_dt__lt=now)
        elif status == "waiting":  # still open: not submitted, cancelled or expired
            qs = qs.filter(submitted_dt__isnull=True, cancelled_dt__isnull=True, expires_dt__gte=now)
        return qs

    def label_for(self, instance):
        return f"Invite {instance.candidate_name}"

    def _uid(self, request):
        return self._current_user_id(request) or 1

    def _log(self, request, action_name, invite, changes=None):
        _audit.record_action(request, action_name, self.entity_key, invite.pk, self.label_for(invite), changes, target=invite)

    def _issue_link(self, invite, days, request):
        """A new token (the old link stops working), a new expiry, everything about the code reset. Returns (link, mail_sent)."""
        token = ob.new_token()
        invite.token_hash = ob.hash_token(token)
        invite.expires_dt = timezone.now() + timedelta(days=days)
        invite.otp_hash, invite.otp_expires_dt, invite.otp_attempts, invite.otp_sent_count, invite.otp_window_start = "", None, 0, 0, None
        invite.locked = False
        invite.session_nonce = ob.new_nonce()
        link = ob.link_for(token, request)
        return link, ob.send_invite_mail(invite, link)

    def create(self, request, *args, **kwargs):
        name = str(request.data.get("candidate_name") or "").strip()
        email = str(request.data.get("email_id") or "").strip()
        try:
            days = int(request.data.get("expires_days") or ob.INVITE_DAYS)
        except (TypeError, ValueError):
            days = ob.INVITE_DAYS
        errors = {}
        if not name:
            errors["candidate_name"] = "Enter the candidate's name."
        elif len(name) > 60:
            errors["candidate_name"] = "The name can be 60 characters at most."
        if not ob.is_valid_email(email):
            errors["email_id"] = ob.EMAIL_MESSAGE
        elif len(email) > 40:
            errors["email_id"] = "The email can be 40 characters at most."
        if not 1 <= days <= 30:
            errors["expires_days"] = "The link can work for 1 to 30 days."
        if errors:
            return Response(errors, status=400)
        now = timezone.now()
        invite = CandidateInvite(candidate_name=name, email_id=email, expires_dt=now, token_hash=ob.hash_token(ob.new_token()), cr_user_id=self._uid(request), cr_dt=now)
        link, sent = self._issue_link(invite, days, request)
        invite.save()
        self._log(request, "create", invite, {"candidate_name": {"old": None, "new": name}, "email_id": {"old": None, "new": email}, "mail_sent": {"old": None, "new": sent}})
        data = self.get_serializer(invite).data
        return Response({**data, "link": link, "mail_sent": sent}, status=201)

    @action(detail=True, methods=["post"], url_path="resend")
    def resend(self, request, pk=None):
        invite = self.get_object()
        if invite.submitted_dt or invite.cancelled_dt:
            return Response({"error": "This invite is already submitted or cancelled."}, status=400)
        link, sent = self._issue_link(invite, ob.INVITE_DAYS, request)
        invite.resend_count += 1
        invite.mod_user_id, invite.mod_dt = self._uid(request), timezone.now()
        invite.save()
        self._log(request, "update", invite, {"resent": {"old": None, "new": True}, "mail_sent": {"old": None, "new": sent}})
        return Response({**self.get_serializer(invite).data, "link": link, "mail_sent": sent})

    @action(detail=True, methods=["post"], url_path="extend")
    def extend(self, request, pk=None):
        invite = self.get_object()
        if invite.submitted_dt or invite.cancelled_dt:
            return Response({"error": "This invite is already submitted or cancelled."}, status=400)
        try:
            days = int(request.data.get("days") or ob.INVITE_DAYS)
        except (TypeError, ValueError):
            days = ob.INVITE_DAYS
        if not 1 <= days <= 30:
            return Response({"days": "Extend by 1 to 30 days."}, status=400)
        old = invite.expires_dt
        invite.expires_dt = max(invite.expires_dt, timezone.now()) + timedelta(days=days)
        invite.mod_user_id, invite.mod_dt = self._uid(request), timezone.now()
        invite.save()
        self._log(request, "update", invite, {"expires_dt": {"old": str(old), "new": str(invite.expires_dt)}})
        return Response(self.get_serializer(invite).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        invite = self.get_object()
        if invite.submitted_dt:
            return Response({"error": "This invite is already submitted."}, status=400)
        invite.cancelled_dt = timezone.now()
        invite.session_nonce = ""  # ends any open form session
        invite.draft = ""
        invite.mod_user_id, invite.mod_dt = self._uid(request), timezone.now()
        invite.save()
        self._log(request, "update", invite, {"cancelled": {"old": None, "new": True}})
        return Response(self.get_serializer(invite).data)
