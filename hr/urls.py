"""HR routes, served under /api/hr/. Register every HR viewset on this router; the structure check
(scripts/check_project_structure.py) requests each route without signing in and fails if one answers anything but 401/403."""

from rest_framework.routers import DefaultRouter

router = DefaultRouter()
# router.register("candidates", views.CandidateViewSet, basename="hr-candidate")

urlpatterns = router.urls
