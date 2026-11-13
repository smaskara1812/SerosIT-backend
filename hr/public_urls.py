"""The public candidate form's routes, served under /api/public/onboarding/ (no sign-in). Nothing else may be added here without the same care:
see hr/public_views.py."""

from django.urls import path

from hr import public_views as v

urlpatterns = [
    path("start/", v.Start.as_view()),
    path("send-code/", v.SendCode.as_view()),
    path("verify/", v.Verify.as_view()),
    path("load/", v.Load.as_view()),
    path("save/", v.Save.as_view()),
    path("resume/", v.Resume.as_view()),
    path("submit/", v.Submit.as_view()),
]
