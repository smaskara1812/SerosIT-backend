"""Serves stored files to signed-in users who may see them. The browser fetches a file with the user's access token (the pages turn the answer into a
picture), the server checks the right to the page the folder belongs to, and nothing in the address grants access."""

import os

from django.conf import settings
from django.http import FileResponse, Http404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from .media_uploads import FOLDER_PAGES
from .permissions import get_user_access


class MediaFileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, path):
        parts = [p for p in path.replace("\\", "/").split("/") if p]
        if len(parts) < 2 or any(p in (".", "..") for p in parts):
            raise Http404
        page = FOLDER_PAGES.get(parts[0])
        if page is None:
            raise Http404
        access = get_user_access(request)
        if not (access["is_admin"] or access["perms"].get(page, {}).get("view")):
            raise Http404  # no rights looks the same as no such file
        root = os.path.realpath(str(settings.MEDIA_ROOT))
        full = os.path.realpath(os.path.join(root, *parts))
        if not full.startswith(root + os.sep) or not os.path.isfile(full):
            raise Http404
        resp = FileResponse(open(full, "rb"))
        resp["X-Content-Type-Options"] = "nosniff"
        resp["Cache-Control"] = "private, max-age=300"
        return resp
