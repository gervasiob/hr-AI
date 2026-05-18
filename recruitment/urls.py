from django.urls import path

from recruitment import views

app_name = "recruitment"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("sincronizacion/", views.RemoteSyncView.as_view(), name="remote-sync"),
    path(
        "candidatos-integrados/",
        views.IntegrationCandidateListView.as_view(),
        name="integration-candidate-list",
    ),
    path("candidatos/", views.CandidateListView.as_view(), name="candidate-list"),
    path("candidatos/nuevo/", views.CandidateCreateView.as_view(), name="candidate-create"),
    path("candidatos/<int:pk>/", views.CandidateDetailView.as_view(), name="candidate-detail"),
    path(
        "candidatos-integrados/<int:pk>/extraer-skills/",
        views.ExtractIntegrationCandidateSkillsView.as_view(),
        name="integration-candidate-extract-skills",
    ),
    path(
        "candidatos-integrados/extraer-skills/batch/",
        views.BatchExtractIntegrationCandidateSkillsView.as_view(),
        name="integration-candidate-batch-extract-skills",
    ),
    path(
        "candidatos/<int:pk>/clasificar/",
        views.RunCandidateClassificationView.as_view(),
        name="candidate-classify",
    ),
    path("postulaciones/nueva/", views.ApplicationCreateView.as_view(), name="application-create"),
]
