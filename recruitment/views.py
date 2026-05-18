from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView

from recruitment.forms import ApplicationForm, CandidateForm, RemoteTableSyncForm
from recruitment.models import (
    AIClassificationRun,
    Application,
    Candidate,
    JobOpening,
    RemoteTableRecord,
)
from recruitment.services import CandidateAIClassifier, RemoteTableSyncService


class DashboardView(TemplateView):
    template_name = "recruitment/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["candidate_count"] = Candidate.objects.count()
        context["job_count"] = JobOpening.objects.count()
        context["application_count"] = Application.objects.count()
        context["remote_records_count"] = RemoteTableRecord.objects.count()
        context["recent_runs"] = AIClassificationRun.objects.select_related("candidate")[:5]
        context["applications_by_stage"] = (
            Application.objects.values("stage").annotate(total=Count("id")).order_by("stage")
        )
        return context


class CandidateListView(ListView):
    model = Candidate
    template_name = "recruitment/candidate_list.html"
    context_object_name = "candidates"


class CandidateDetailView(DetailView):
    model = Candidate
    template_name = "recruitment/candidate_detail.html"
    context_object_name = "candidate"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        candidate = self.object
        context["experiences"] = candidate.experiences.all()
        context["educations"] = candidate.educations.all()
        context["skills"] = candidate.skills.select_related("skill").all()
        context["latest_run"] = candidate.classification_runs.first()
        context["extracted_skills"] = candidate.ai_extracted_skills.select_related(
            "classification_run",
            "normalized_skill",
        ).all()
        return context


class CandidateCreateView(CreateView):
    form_class = CandidateForm
    template_name = "recruitment/candidate_form.html"
    success_url = reverse_lazy("recruitment:candidate-list")


class ApplicationCreateView(CreateView):
    form_class = ApplicationForm
    template_name = "recruitment/application_form.html"
    success_url = reverse_lazy("recruitment:dashboard")


class RunCandidateClassificationView(View):
    def post(self, request, pk):
        candidate = get_object_or_404(Candidate, pk=pk)
        run = CandidateAIClassifier().classify_candidate(candidate)
        if run.status == AIClassificationRun.Status.SUCCESS:
            messages.success(request, "Clasificacion IA ejecutada correctamente.")
        else:
            messages.error(
                request,
                f"La clasificacion fallo: {run.error_message or 'error desconocido'}",
            )
        return redirect("recruitment:candidate-detail", pk=candidate.pk)


class RemoteSyncView(TemplateView):
    template_name = "recruitment/remote_sync.html"
    service_class = RemoteTableSyncService

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        service = self.service_class()
        dashboard = service.get_dashboard_data()
        context.update(dashboard)
        context["form"] = kwargs.get(
            "form",
            RemoteTableSyncForm(
                available_tables=dashboard["available_tables"],
                initial={"tables": dashboard["selected_tables"]},
            ),
        )
        context["sync_results"] = kwargs.get("sync_results", [])
        return context

    def post(self, request, *args, **kwargs):
        service = self.service_class()
        dashboard = service.get_dashboard_data()
        form = RemoteTableSyncForm(request.POST, available_tables=dashboard["available_tables"])
        sync_results = []

        if not form.is_valid():
            messages.error(request, "Selecciona al menos un formato valido de tablas.")
            return self.render_to_response(
                self.get_context_data(form=form, sync_results=sync_results)
            )

        selected_tables = form.cleaned_data["tables"]
        action = request.POST.get("action")
        service.update_selected_tables(selected_tables)

        if action in {"sync", "reset_sync", "purge"} and not selected_tables:
            messages.error(request, "Selecciona al menos una tabla para ejecutar la accion.")
            return self.render_to_response(
                self.get_context_data(form=form, sync_results=sync_results)
            )

        try:
            if action == "sync":
                sync_results = service.sync_tables(selected_tables)
                messages.success(request, "Sincronizacion incremental completada.")
            elif action == "reset_sync":
                sync_results = service.sync_and_reset_tables(selected_tables)
                messages.success(request, "Se borraron y volvieron a copiar las tablas seleccionadas.")
            elif action == "purge":
                service.reset_tables(selected_tables)
                messages.success(request, "Se borraron las tablas seleccionadas.")
            elif action == "purge_all_and_sync":
                copied_tables = [
                    tracker.table_name for tracker in dashboard["trackers"] if tracker.records_count > 0
                ]
                tables_to_reset = copied_tables or selected_tables or dashboard["available_tables"]
                service.reset_tables(tables_to_reset)
                sync_results = service.sync_tables(tables_to_reset)
                messages.success(request, "Se borraron todas las tablas copiadas y se volvieron a sincronizar.")
            else:
                messages.error(request, "La accion solicitada no es valida.")
        except Exception as exc:
            messages.error(request, f"La sincronizacion fallo: {exc}")

        return self.render_to_response(
            self.get_context_data(sync_results=sync_results)
        )
