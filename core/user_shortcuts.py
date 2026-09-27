"""Home page "Shortcuts" tray — user-customisable, not menu-permission
gated (it's a personal preference over pages the user already has access
to, not a delegable business page of its own). Keyed by login username
(see UserShortcut's own docstring) so it works for every authenticated
account, including one with no MstUser/UserProfile row."""

from django.db import transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import UserShortcut

MAX_SHORTCUTS = 24


class UserShortcutsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        paths = list(
            UserShortcut.objects.filter(user_login_id=request.user.username).values_list("path", flat=True)
        )
        return Response({"paths": paths, "max_shortcuts": MAX_SHORTCUTS})

    @transaction.atomic
    def put(self, request):
        paths = request.data.get("paths")
        if not isinstance(paths, list) or not all(isinstance(p, str) and p for p in paths):
            return Response({"error": "paths must be a list of non-empty strings"}, status=400)

        # De-dupe while preserving the order the user arranged, and cap to
        # a sane size — this is a personal UI list, not meant to grow
        # unbounded.
        seen = set()
        deduped = []
        for p in paths:
            if p not in seen:
                seen.add(p)
                deduped.append(p)
        deduped = deduped[:MAX_SHORTCUTS]

        UserShortcut.objects.filter(user_login_id=request.user.username).delete()
        UserShortcut.objects.bulk_create(
            [
                UserShortcut(user_login_id=request.user.username, path=p, sort_order=i)
                for i, p in enumerate(deduped)
            ]
        )
        return Response({"paths": deduped, "max_shortcuts": MAX_SHORTCUTS})
