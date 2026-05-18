from django.contrib import messages
from django.db.models import Count, Exists, OuterRef, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView

from recruitment.forms import (
    ApplicationForm,
    CandidateForm,
    IntegrationCandidateFilterForm,
    RemoteTableSyncForm,
)
from recruitment.models import (
    AIClassificationRun,
    Application,
    Candidate,
    IntegrationCandidate,
    IntegrationCandidateLLMRun,
    JobOpening,
    RemoteTableRecord,
)
from recruitment.services import (
    CandidateAIClassifier,
    IntegrationCandidateService,
    IntegrationCandidateToLocalCandidateService,
    RemoteTableSyncService,
)


class DashboardView(TemplateView):
    template_name = "recruitment/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["candidate_count"] = Candidate.objects.count()
        context["job_count"] = JobOpening.objects.count()
        context["application_count"] = Application.objects.count()
        context["remote_records_count"] = RemoteTableRecord.objects.count()
        context["integration_candidate_count"] = IntegrationCandidate.objects.count()
        context["recent_runs"] = AIClassificationRun.objects.select_related("candidate")[:5]
        context["applications_by_stage"] = (
            Application.objects.values("stage").annotate(total=Count("id")).order_by("stage")
        )
        return context


class CandidateListView(ListView):
    model = Candidate
    template_name = "recruitment/candidate_list.html"
    context_object_name = "candidates"


class IntegrationCandidateListView(ListView):
    model = IntegrationCandidate
    template_name = "recruitment/integration_candidate_list.html"
    context_object_name = "integration_candidates"
    paginate_by = 25

    allowed_order_fields = {
        "full_name",
        "-full_name",
        "primary_profile",
        "sub_profile",
        "country",
        "province",
        "idIntegration",
        "-idIntegration",
        "-last_integrated_at",
    }

    def get_paginate_by(self, queryset):
        try:
            page_size = int(self.request.GET.get("page_size", self.paginate_by))
        except (TypeError, ValueError):
            page_size = self.paginate_by
        return page_size if page_size in {10, 25, 50, 100} else self.paginate_by

    def get_queryset(self):
        local_candidate_subquery = Candidate.objects.filter(idIntegration=OuterRef("idIntegration"))
        successful_run_subquery = IntegrationCandidateLLMRun.objects.filter(
            candidate=OuterRef("pk"),
            status=IntegrationCandidateLLMRun.Status.SUCCESS,
        )
        queryset = IntegrationCandidate.objects.annotate(
            has_local_candidate=Exists(local_candidate_subquery),
            is_processed=Exists(successful_run_subquery),
        )

        q = self.request.GET.get("q", "").strip()
        primary_profile = self.request.GET.get("primary_profile", "").strip()
        sub_profile = self.request.GET.get("sub_profile", "").strip()
        seniority_level = self.request.GET.get("seniority_level", "").strip()
        country = self.request.GET.get("country", "").strip()
        province = self.request.GET.get("province", "").strip()
        processed_status = self.request.GET.get("processed_status", "").strip()
        has_cv_link = self.request.GET.get("has_cv_link", "").strip()
        has_work_experience = self.request.GET.get("has_work_experience", "").strip()
        is_active = self.request.GET.get("is_active", "").strip()
        order = self.request.GET.get("order", "-last_integrated_at").strip()

        if q:
            search_filter = (
                Q(full_name__icontains=q)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(email__icontains=q)
                | Q(document_id__icontains=q)
                | Q(cuil__icontains=q)
            )
            if q.isdigit():
                search_filter |= Q(idIntegration=int(q))
            queryset = queryset.filter(search_filter)
        if primary_profile:
            queryset = queryset.filter(primary_profile__icontains=primary_profile)
        if sub_profile:
            queryset = queryset.filter(sub_profile__icontains=sub_profile)
        if seniority_level:
            queryset = queryset.filter(seniority_level__icontains=seniority_level)
        if country:
            queryset = queryset.filter(country__icontains=country)
        if province:
            queryset = queryset.filter(province__icontains=province)
        if processed_status == "true":
            queryset = queryset.filter(is_processed=True)
        elif processed_status == "false":
            queryset = queryset.filter(is_processed=False)
        if has_cv_link == "true":
            queryset = queryset.exclude(cv_s3_url="")
        elif has_cv_link == "false":
            queryset = queryset.filter(cv_s3_url="")
        if has_work_experience == "true":
            queryset = queryset.exclude(work_experience_json=[])
        elif has_work_experience == "false":
            queryset = queryset.filter(work_experience_json=[])
        if is_active == "true":
            queryset = queryset.filter(is_active=True)
        elif is_active == "false":
            queryset = queryset.filter(is_active=False)

        if order not in self.allowed_order_fields:
            order = "-last_integrated_at"
        return queryset.order_by(order, "-idIntegration")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query_data = self.request.GET.copy()
        form = IntegrationCandidateFilterForm(
            initial={
                "q": query_data.get("q", ""),
                "primary_profile": query_data.get("primary_profile", ""),
                "sub_profile": query_data.get("sub_profile", ""),
                "seniority_level": query_data.get("seniority_level", ""),
                "country": query_data.get("country", ""),
                "province": query_data.get("province", ""),
                "processed_status": query_data.get("processed_status", ""),
                "has_cv_link": query_data.get("has_cv_link", ""),
                "has_work_experience": query_data.get("has_work_experience", ""),
                "is_active": query_data.get("is_active", ""),
                "order": query_data.get("order", "-last_integrated_at"),
                "page_size": query_data.get("page_size", str(self.get_paginate_by(None))),
            }
        )
        context["filter_form"] = form
        context["current_order"] = self.request.GET.get("order", "-last_integrated_at")
        context["total_count"] = self.get_queryset().count()
        context["querystring_without_page"] = self._querystring_without("page")
        context["current_full_path"] = self.request.get_full_path()
        context["order_links"] = {
            "full_name": self._querystring_with(order="full_name"),
            "idIntegration": self._querystring_with(order="-idIntegration"),
            "primary_profile": self._querystring_with(order="primary_profile"),
            "country": self._querystring_with(order="country"),
            "last_integrated_at": self._querystring_with(order="-last_integrated_at"),
        }
        return context

    def _querystring_without(self, *keys):
        query = self.request.GET.copy()
        for key in keys:
            if key in query:
                del query[key]
        encoded = query.urlencode()
        return f"&{encoded}" if encoded else ""

    def _querystring_with(self, **kwargs):
        query = self.request.GET.copy()
        for key, value in kwargs.items():
            query[key] = value
        if "page" in query:
            del query["page"]
        encoded = query.urlencode()
        return f"?{encoded}" if encoded else "?"


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


class ExtractIntegrationCandidateSkillsView(View):
    def post(self, request, pk):
        integration_candidate = get_object_or_404(IntegrationCandidate, pk=pk)
        candidate, run = IntegrationCandidateToLocalCandidateService().extract_and_sync(
            integration_candidate
        )
        if run.status == run.Status.SUCCESS and candidate:
            messages.success(
                request,
                f"Extraccion completada y candidato local actualizado: {candidate.full_name}.",
            )
        else:
            messages.error(
                request,
                f"La extraccion fallo: {run.error_message or 'error desconocido'}",
            )
        return redirect(request.POST.get("next") or "recruitment:integration-candidate-list")


class BatchExtractIntegrationCandidateSkillsView(View):
    def post(self, request):
        selected_ids = request.POST.getlist("selected_candidates")
        next_url = request.POST.get("next") or "recruitment:integration-candidate-list"
        if not selected_ids:
            messages.error(request, "Selecciona al menos un candidato integrado.")
            return redirect(next_url)

        integration_candidates = IntegrationCandidate.objects.filter(pk__in=selected_ids).order_by("pk")
        service = IntegrationCandidateToLocalCandidateService()
        success_count = 0
        failure_count = 0
        failed_items = []

        for integration_candidate in integration_candidates:
            try:
                candidate, run = service.extract_and_sync(integration_candidate)
            except Exception as exc:
                failure_count += 1
                failed_items.append(f"{integration_candidate.idIntegration}: {exc}")
                continue

            if run.status == run.Status.SUCCESS and candidate:
                success_count += 1
            else:
                failure_count += 1
                failed_items.append(
                    f"{integration_candidate.idIntegration}: {run.error_message or 'error desconocido'}"
                )

        if success_count:
            messages.success(
                request,
                f"Se procesaron correctamente {success_count} candidatos integrados.",
            )
        if failure_count:
            details = "; ".join(failed_items[:3])
            if failure_count > 3:
                details = f"{details}; y {failure_count - 3} mas"
            messages.error(
                request,
                f"Fallaron {failure_count} candidatos integrados. {details}",
            )

        return redirect(next_url)


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
        context["integration_result"] = kwargs.get("integration_result")
        context["integration_candidate_count"] = IntegrationCandidate.objects.count()
        return context

    def post(self, request, *args, **kwargs):
        service = self.service_class()
        integration_service = IntegrationCandidateService()
        dashboard = service.get_dashboard_data()
        form = RemoteTableSyncForm(request.POST, available_tables=dashboard["available_tables"])
        sync_results = []
        integration_result = None

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
                self.get_context_data(
                    form=form,
                    sync_results=sync_results,
                    integration_result=integration_result,
                )
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
            elif action == "integrate_candidates":
                sync_results.append(service.sync_table("cvfile"))
                integration_result = integration_service.integrate_candidates(reset=False)
                messages.success(request, "Se sincronizo cvfile y se integraron los candidatos en la tabla unificada.")
            elif action == "reset_and_integrate_candidates":
                sync_results.append(service.sync_table("cvfile", reset=True))
                integration_result = integration_service.integrate_candidates(reset=True)
                messages.success(request, "Se resincronizo cvfile y se borraron y reintegraron los candidatos unificados.")
            else:
                messages.error(request, "La accion solicitada no es valida.")
        except Exception as exc:
            messages.error(request, f"La sincronizacion fallo: {exc}")

        return self.render_to_response(
            self.get_context_data(
                sync_results=sync_results,
                integration_result=integration_result,
            )
        )
