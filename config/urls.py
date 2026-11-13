from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path


urlpatterns = [
    path("admin/", admin.site.urls),
    # The HR module has its own routes; they must come before core's "api/" include.
    path("api/hr/", include("hr.urls")),
    # The public candidate form (no sign-in, own throttles, whitelisted writes): hr/public_views.py.
    path("api/public/onboarding/", include("hr.public_urls")),
    path("api/", include("core.urls")),
]

# Media is served only through /api/media/<path> (core/media_views.py): signed-in users with the right to the file's page, in every mode.

if settings.ENABLE_SILK:
    urlpatterns.append(path("silk/", include("silk.urls", namespace="silk")))
