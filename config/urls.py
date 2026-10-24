from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path

from core.media_uploads import serve_media

urlpatterns = [
    path("admin/", admin.site.urls),
    # The HR module has its own routes; they must come before core's "api/" include.
    path("api/hr/", include("hr.urls")),
    path("api/", include("core.urls")),
]

# Media is served by a signed-link view in every mode (dev and production), never open static serving.
urlpatterns.append(re_path(r"^" + settings.MEDIA_URL.lstrip("/") + r"(?P<path>.+)$", serve_media))

if settings.ENABLE_SILK:
    urlpatterns.append(path("silk/", include("silk.urls", namespace="silk")))
