"""The public candidate form: /api/public/onboarding/<step>/. No account, no JWT, nothing from the signed-in side of the system.

Every call carries the invite's token in the JSON body (not in the address, so it stays out of access logs); calls after the code check also carry the
signed form session. A wrong, expired, used or cancelled link all answer the same way, so nobody can tell which links exist. What may be written is
limited to the candidate's own draft, and (on Submit) one new candidate with its training and experience rows: no other row of the system can be read or
changed from here, and the HR-only columns (rig, rank, hiring status, notes ...) are never accepted.
"""

import json
import logging
import os

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from core import audit as _audit
from core.client_ip import client_ip
from core.media_uploads import next_sequence, save_media_file
from hr import onboarding as ob
from hr.models import CandidateInvite
from hr.views.candidates import (
    ENTITY_KEY, RESUME_EXTENSIONS, RESUME_FOLDER, CandidateExperienceSerializer, CandidateInterviewHdrSerializer, CandidateTrainingSerializer,
)

log = logging.getLogger("hr.onboarding")

INVALID = {"error": "This link isn't valid any more. Ask HR to send you a new one."}


class _IpThrottle(SimpleRateThrottle):
    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": client_ip(request)}


class FormThrottle(_IpThrottle):
    scope = "onboarding"
    rate = "240/min"


class CodeThrottle(_IpThrottle):
    scope = "onboarding_code"
    rate = "40/hour"


class _PublicView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [FormThrottle]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def invite_for(self, request):
        """The open invite for the token in the request, or None."""
        token = request.data.get("token") if hasattr(request.data, "get") else None
        if not isinstance(token, str) or not 20 <= len(token) <= 200:
            return None
        invite = CandidateInvite.objects.filter(token_hash=ob.hash_token(token)).first()
        return invite if invite and ob.is_open(invite) else None

    def session_for(self, request):
        """(invite, first_issue_time) for a request with a valid form session, else (None, error response)."""
        invite = self.invite_for(request)
        if invite is None:
            return None, Response(INVALID, status=404)
        first = ob.read_session(invite, request.data.get("session"))
        if first is None:
            return None, Response({"error": "session", "message": "Please check your code again to carry on."}, status=401)
        return (invite, first), None


class Start(_PublicView):
    def post(self, request):
        invite = self.invite_for(request)
        if invite is None:
            return Response(INVALID, status=404)
        if not invite.opened_dt:
            invite.opened_dt = timezone.now()
            invite.save(update_fields=["opened_dt"])
        return Response({"name": invite.candidate_name, "email_masked": ob.mask_email(invite.email_id), "expires_dt": invite.expires_dt, "locked": invite.locked})


class SendCode(_PublicView):
    throttle_classes = [FormThrottle, CodeThrottle]

    def post(self, request):
        invite = self.invite_for(request)
        if invite is None:
            return Response(INVALID, status=404)
        if invite.locked:
            return Response({"error": "locked", "message": "Too many wrong codes. Ask HR to send you a new link."}, status=403)
        now = timezone.now()
        if not invite.otp_window_start or (now - invite.otp_window_start).total_seconds() > 3600:
            invite.otp_window_start, invite.otp_sent_count = now, 0
        if invite.otp_sent_count >= ob.OTP_SENDS_PER_HOUR:
            return Response({"error": "too_many", "message": "A code was sent a few times already. Please try again in an hour."}, status=429)
        code = ob.new_code()
        ob.set_code(invite, code)
        invite.otp_sent_count += 1
        invite.otp_attempts = 0
        invite.save(update_fields=["otp_hash", "otp_expires_dt", "otp_sent_count", "otp_window_start", "otp_attempts"])
        if not ob.send_code_mail(invite, code):
            return Response({"error": "mail", "message": "We couldn't send the code. Please try again in a few minutes."}, status=502)
        return Response({"sent": True, "email_masked": ob.mask_email(invite.email_id), "valid_minutes": ob.OTP_MINUTES})


class Verify(_PublicView):
    throttle_classes = [FormThrottle, CodeThrottle]

    def post(self, request):
        invite = self.invite_for(request)
        if invite is None:
            return Response(INVALID, status=404)
        if invite.locked:
            return Response({"error": "locked", "message": "Too many wrong codes. Ask HR to send you a new link."}, status=403)
        if not invite.otp_hash:
            return Response({"error": "no_code", "message": "Ask for a code first."}, status=400)
        invite.otp_attempts += 1
        if ob.code_matches(invite, str(request.data.get("code") or "")):
            invite.otp_hash, invite.otp_expires_dt, invite.otp_attempts = "", None, 0
            invite.session_nonce = ob.new_nonce()
            invite.verified_dt = invite.verified_dt or timezone.now()
            invite.save(update_fields=["otp_hash", "otp_expires_dt", "otp_attempts", "session_nonce", "verified_dt"])
            return Response({"session": ob.issue_session(invite)})
        if invite.otp_attempts >= ob.OTP_TRIES:
            invite.locked = True
            invite.otp_hash = ""
            invite.save(update_fields=["otp_attempts", "locked", "otp_hash"])
            return Response({"error": "locked", "message": "Too many wrong codes. Ask HR to send you a new link."}, status=403)
        invite.save(update_fields=["otp_attempts"])
        left = ob.OTP_TRIES - invite.otp_attempts
        return Response({"error": "wrong", "message": f"That code isn't right. {left} {'try' if left == 1 else 'tries'} left."}, status=400)


class Load(_PublicView):
    def post(self, request):
        got, err = self.session_for(request)
        if err:
            return err
        invite, first = got
        return Response({
            "draft": ob.load_draft(invite), "version": invite.draft_version, "name": invite.candidate_name, "email": invite.email_id,
            "has_resume": bool(invite.resume_path), "resume_name": os.path.basename(invite.resume_path), "session": ob.issue_session(invite, first),
        })


class Save(_PublicView):
    def post(self, request):
        got, err = self.session_for(request)
        if err:
            return err
        invite, first = got
        raw = request.data.get("draft")
        try:
            version = int(request.data.get("version"))
        except (TypeError, ValueError):
            version = -1
        if version != invite.draft_version:
            return Response({"error": "conflict", "message": "This form was changed in another window. Reload to see the latest.", "version": invite.draft_version}, status=409)
        draft = ob.clean_draft(raw)
        text = json.dumps(draft, separators=(",", ":"))
        if len(text.encode()) > ob.DRAFT_MAX_BYTES:
            return Response({"error": "too_big", "message": "That is more than the form can hold."}, status=413)
        invite.draft = text
        invite.draft_version += 1
        invite.draft_saved_dt = timezone.now()
        invite.save(update_fields=["draft", "draft_version", "draft_saved_dt"])
        return Response({"version": invite.draft_version, "saved_dt": invite.draft_saved_dt, "session": ob.issue_session(invite, first)})


class Resume(_PublicView):
    def post(self, request):
        got, err = self.session_for(request)
        if err:
            return err
        invite, first = got
        f = request.FILES.get("file")
        if not f:
            return Response({"error": "file", "message": "Choose a file."}, status=400)
        seq = next_sequence(RESUME_FOLDER, f"i{invite.pk}")
        rel_path, error = save_media_file(f, RESUME_FOLDER, f"i{invite.pk}_{seq}", allowed_extensions=RESUME_EXTENSIONS)
        if error:
            return Response({"error": "file", "message": error}, status=400)
        old = invite.resume_path
        invite.resume_path = rel_path
        invite.save(update_fields=["resume_path"])
        if old and old != rel_path:  # the person's own earlier upload for this invite
            try:
                os.remove(os.path.join(settings.MEDIA_ROOT, old))
            except OSError:
                pass
        return Response({"has_resume": True, "resume_name": os.path.basename(rel_path), "session": ob.issue_session(invite, first)})


# draft key -> header column, for the answers the candidate gives himself
_HDR_MAP = {
    "fname": "candidate_fname", "mname": "candidate_mname", "lname": "candidate_lname", "father": "father_name", "nationality": "nationality",
    "mobile": "mobile_no", "present_addr": "present_addr", "permanent_addr": "permanent_addr", "qualification": "edu_qualification",
    "dob": "candidate_dob", "tot_y": "tot_experience_yrs", "tot_m": "tot_experience_mths", "cur_y": "exp_in_curr_pos_yrs",
    "cur_m": "exp_in_curr_pos_mths", "source": "recruitment_source", "recommendation": "hiring_reccomendation",
}
_BACK = {v: k for k, v in _HDR_MAP.items()}
_TRAIN_MAP = {"type": "training_type", "agency": "training_agency", "cert_no": "training_cert_no", "cert_dt": "training_cert_dt",
              "valid_from": "cert_valid_from_dt", "valid_to": "cert_valid_to_dt"}
_TRAIN_BACK = {v: k for k, v in _TRAIN_MAP.items()}
_EXP_MAP = {"from": "exp_from_dt", "to": "exp_to_dt", "company": "company_name", "designation": "designation"}
_EXP_BACK = {v: k for k, v in _EXP_MAP.items()}
_REQUIRED = {
    "fname": "Enter your first name.", "lname": "Enter your last name.", "father": "Enter your father's name.", "dob": "Enter your date of birth.",
    "nationality": "Enter your nationality.", "mobile": "Enter your mobile number.", "present_addr": "Enter your present address.",
    "permanent_addr": "Enter your permanent address.", "qualification": "Enter your qualification.", "tot_y": "Enter your total experience in years (0 if none).",
}


class _Invalid(Exception):
    def __init__(self, errors):
        self.errors = errors


def _flat(errors, back):
    return {back.get(k, k): (v[0] if isinstance(v, list) and v else str(v)) for k, v in errors.items() if k != "hdr"}


class Submit(_PublicView):
    def post(self, request):
        got, err = self.session_for(request)
        if err:
            return err
        invite, first = got
        draft = ob.clean_draft(request.data.get("draft")) if request.data.get("draft") is not None else ob.load_draft(invite)
        if draft["same_addr"]:
            draft["permanent_addr"] = draft["present_addr"]
        fields = {k: msg for k, msg in _REQUIRED.items() if draft.get(k) in ("", None)}
        if fields:
            return Response({"error": "invalid", "fields": fields}, status=400)
        data = {col: (draft[k] if draft[k] != "" else None) for k, col in _HDR_MAP.items()}
        data["tot_experience_mths"] = data["tot_experience_mths"] or 0
        data["email_id"] = invite.email_id  # always the invited address, whatever was typed
        try:
            with transaction.atomic():
                invite = CandidateInvite.objects.select_for_update().get(pk=invite.pk)
                if not ob.is_open(invite):
                    return Response(INVALID, status=404)
                ser = CandidateInterviewHdrSerializer(data=data)
                if not ser.is_valid():
                    raise _Invalid({"fields": _flat(ser.errors, _BACK)})
                now = timezone.now()
                hdr = ser.save(
                    cr_user_id=invite.cr_user_id, cr_dt=now, hiring_status="N", candidate_submitted_dt=now,
                    candidate_cert_path=invite.resume_path or "",
                )
                for key, rows, mapping, serializer_class, back in (
                    ("trainings", draft["trainings"], _TRAIN_MAP, CandidateTrainingSerializer, _TRAIN_BACK),
                    ("experiences", draft["experiences"], _EXP_MAP, CandidateExperienceSerializer, _EXP_BACK),
                ):
                    problems = {}
                    for i, row in enumerate(rows):
                        payload = {col: (row.get(k) or None) for k, col in mapping.items()}
                        payload["hdr"] = hdr.pk
                        child = serializer_class(data=payload)
                        if child.is_valid():
                            child.save(cr_user_id=invite.cr_user_id, cr_dt=now)
                        else:
                            problems[i] = _flat(child.errors, back)
                    if problems:
                        raise _Invalid({key: problems})
                invite.submitted_dt, invite.hdr, invite.draft, invite.session_nonce = now, hdr, "", ""
                invite.save(update_fields=["submitted_dt", "hdr", "draft", "session_nonce"])
        except _Invalid as bad:
            return Response({"error": "invalid", **bad.errors}, status=400)
        _audit._create(None, "candidate (invite)", "create", ENTITY_KEY, _audit.entity_label(ENTITY_KEY), hdr.pk, f"Candidate {hdr}",
                       {"entered_by_candidate": {"old": None, "new": True}, "invite": {"old": None, "new": invite.pk}}, request, target=hdr)
        # The confirmation mail is best effort: the details are already saved, so a mail problem never undoes or fails the submit.
        try:
            confirmed = ob.send_submitted_mail(invite, hdr)
        except Exception:
            log.exception("confirmation mail for invite %s failed", invite.pk)
            confirmed = False
        return Response({"submitted": True, "confirmation_sent": confirmed})
