"""HR routes, served under /api/hr/. Register every HR viewset on this router; the structure check
(scripts/check_project_structure.py) requests each route without signing in and fails if one answers anything but 401/403."""

from rest_framework.routers import DefaultRouter

from hr.views import candidates, evaluations, invites

router = DefaultRouter()
router.register("candidate-interviews", candidates.CandidateInterviewViewSet, basename="hr-candidate-interview")
router.register("candidate-invites", invites.CandidateInviteViewSet, basename="hr-candidate-invite")
router.register("candidate-evaluations", evaluations.CandidateEvaluationViewSet, basename="hr-candidate-evaluation")
router.register("candidate-trainings", candidates.CandidateTrainingViewSet, basename="hr-candidate-training")
router.register("candidate-experiences", candidates.CandidateExperienceViewSet, basename="hr-candidate-experience")
router.register("candidate-competencies", candidates.CandidateCompetencyViewSet, basename="hr-candidate-competency")

urlpatterns = router.urls
