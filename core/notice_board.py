"""Admin > Notice Board: notices for the home page banner.

Who may post is the page's own User Rights (menu key admin.notice_board): App Admins always, anyone else only when an
admin grants them View / Add / Edit / Delete on it. Every signed-in user may read the notices that are live right now,
through /api/notices/live/, which returns only the fields the banner shows and never drafts, scheduled or expired ones.

Text is plain text only (the banner never renders HTML). A link must be a page inside the app ("/qhse/...") or an
https address. The end time is required and must be after the start.
"""

from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .masters_views import BaseMasterViewSet
from .models import MstUser, Notice, UserProfile

LIVE_LIMIT = 8  # the banner rotates through at most this many at once


def status_of(notice, now=None):
    now = now or timezone.now()
    if notice.is_published != "Y":
        return "draft"
    if notice.ends_at <= now:
        return "expired"
    if notice.starts_at > now:
        return "scheduled"
    return "live"


def poster_name(user):
    """The name to show as the poster: the person's name in the user list when they have a profile, else the name on
    their login (a Django superuser has no profile)."""
    profile = UserProfile.objects.filter(user_login_id=user.username).first()
    mst = MstUser.objects.filter(user_id=profile.user_id).first() if profile else None
    name = (getattr(mst, "display_name", None) or getattr(mst, "user_name", None)) if mst else None
    return (name or user.get_full_name() or user.username)[:60]


class NoticeSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    posted_by = serializers.SerializerMethodField()

    class Meta:
        model = Notice
        fields = "__all__"
        read_only_fields = ["cr_user_id", "cr_dt", "mod_user_id", "mod_dt"]

    def get_status(self, obj):
        return status_of(obj)

    def get_posted_by(self, obj):
        if obj.posted_by_name:
            return obj.posted_by_name
        names = self.context.setdefault("_poster_names", {})  # rows from before this column existed
        if obj.cr_user_id not in names:
            u = MstUser.objects.filter(user_id=obj.cr_user_id).first()
            names[obj.cr_user_id] = (getattr(u, "display_name", None) or getattr(u, "user_name", None) or "") if u else ""
        return names[obj.cr_user_id]

    def create(self, validated_data):
        validated_data["posted_by_name"] = poster_name(self.context["request"].user)
        return super().create(validated_data)

    def validate_title(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Enter a title.")
        return value

    def validate_message(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Enter the message.")
        return value

    def validate_link_url(self, value):
        value = (value or "").strip()
        if not value:
            return None
        if value.startswith("/") and not value.startswith("//"):
            return value
        if value.lower().startswith("https://"):
            return value
        raise serializers.ValidationError("A link must be a page in the app (starting with /) or an https:// address.")

    def validate(self, attrs):
        inst = self.instance
        starts = attrs.get("starts_at", inst.starts_at if inst else None)
        ends = attrs.get("ends_at", inst.ends_at if inst else None)
        errors = {}
        if "ends_at" in attrs or inst is None:
            if not ends:
                errors["ends_at"] = "Choose when the notice ends."
            elif starts and ends <= starts:
                errors["ends_at"] = "The end must be after the start."
        if "link_url" in attrs and attrs.get("link_url") and not (attrs.get("link_label") or (inst and inst.link_label)):
            attrs["link_label"] = "Open"
        if "link_url" in attrs and not attrs.get("link_url"):
            attrs["link_label"] = None
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class NoticeViewSet(BaseMasterViewSet):
    queryset = Notice.objects.all()
    serializer_class = NoticeSerializer
    entity_key = "admin.notice_board"
    name_field = "title"
    search_fields = ["title", "message"]
    filterable_fields = ["kind"]
    lookup = False  # the banner has its own endpoint; nobody picks from this list in another page

    def get_queryset(self):
        qs = super().get_queryset()
        now = timezone.now()
        status = self.request.query_params.get("status")
        if status == "draft":
            qs = qs.exclude(is_published="Y")
        elif status == "live":
            qs = qs.filter(is_published="Y", starts_at__lte=now, ends_at__gt=now)
        elif status == "scheduled":
            qs = qs.filter(is_published="Y", starts_at__gt=now)
        elif status == "expired":
            qs = qs.filter(is_published="Y", ends_at__lte=now)
        return qs.order_by("-starts_at", "-notice_id")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def live_notices_api(request):
    """What the home banner shows: notices that are published and between their start and end, pinned first."""
    now = timezone.now()
    rows = (
        Notice.objects.filter(is_published="Y", starts_at__lte=now, ends_at__gt=now)
        .order_by("-is_pinned", "-starts_at", "-notice_id")[:LIVE_LIMIT]
    )
    return Response(
        [
            {
                "notice_id": n.notice_id,
                "title": n.title,
                "message": n.message,
                "kind": n.kind,
                "link_label": n.link_label,
                "link_url": n.link_url,
                "is_pinned": n.is_pinned == "Y",
                "ends_at": n.ends_at.isoformat(),
            }
            for n in rows
        ]
    )
