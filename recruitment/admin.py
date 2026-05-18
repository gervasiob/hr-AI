from django.contrib import admin

from recruitment.models import (
    AIClassificationRun,
    AIExtractedSkill,
    Application,
    Candidate,
    CandidateEducation,
    CandidateExperience,
    CandidateSkill,
    IntegrationCandidate,
    IntegrationCandidateLLMRun,
    JobOpening,
    JobSkillRequirement,
    LLMAllowedSkill,
    Organization,
    RemoteTableRecord,
    RemoteTableSync,
    Skill,
)
from recruitment.services.llm_skill_extractor import IntegrationCandidateLLMSkillExtractor


class CandidateEducationInline(admin.TabularInline):
    model = CandidateEducation
    extra = 0


class CandidateExperienceInline(admin.TabularInline):
    model = CandidateExperience
    extra = 0


class CandidateSkillInline(admin.TabularInline):
    model = CandidateSkill
    extra = 0
    autocomplete_fields = ["skill"]


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ("idIntegration", "full_name", "email", "cv_s3_url", "location", "current_position", "availability")
    search_fields = ("first_name", "last_name", "email", "current_position", "idIntegration", "cv_s3_url")
    list_filter = ("availability", "location")
    inlines = [CandidateEducationInline, CandidateExperienceInline, CandidateSkillInline]


class JobSkillRequirementInline(admin.TabularInline):
    model = JobSkillRequirement
    extra = 0
    autocomplete_fields = ["skill"]


@admin.register(JobOpening)
class JobOpeningAdmin(admin.ModelAdmin):
    list_display = ("title", "organization", "status", "modality", "published_at")
    list_filter = ("status", "modality", "organization")
    search_fields = ("title", "description", "requirements")
    inlines = [JobSkillRequirementInline]


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("candidate", "job_opening", "stage", "source", "ai_score", "created_at")
    list_filter = ("stage", "job_opening", "job_opening__organization")
    search_fields = ("candidate__first_name", "candidate__last_name", "job_opening__title")


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("name", "category")
    list_filter = ("category",)
    search_fields = ("name",)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "industry", "size")
    search_fields = ("name", "industry")


@admin.register(AIClassificationRun)
class AIClassificationRunAdmin(admin.ModelAdmin):
    list_display = ("candidate", "status", "provider", "model_name", "executed_at")
    list_filter = ("status", "provider", "model_name")
    search_fields = ("candidate__first_name", "candidate__last_name", "error_message")


@admin.register(AIExtractedSkill)
class AIExtractedSkillAdmin(admin.ModelAdmin):
    list_display = ("candidate", "skill_name", "category", "confidence")
    list_filter = ("category",)
    search_fields = ("candidate__first_name", "candidate__last_name", "skill_name")


@admin.register(RemoteTableSync)
class RemoteTableSyncAdmin(admin.ModelAdmin):
    list_display = (
        "table_name",
        "is_selected",
        "records_count",
        "last_remote_id",
        "last_synced_at",
        "last_sync_status",
    )
    list_filter = ("is_selected", "last_sync_status")
    search_fields = ("table_name", "endpoint", "last_error")


@admin.register(RemoteTableRecord)
class RemoteTableRecordAdmin(admin.ModelAdmin):
    list_display = ("table", "remote_id", "created_at", "updated_at")
    list_filter = ("table__table_name",)
    search_fields = ("table__table_name",)


@admin.register(IntegrationCandidate)
class IntegrationCandidateAdmin(admin.ModelAdmin):
    list_display = (
        "idIntegration",
        "full_name",
        "email",
        "cv_s3_url",
        "primary_profile",
        "sub_profile",
        "seniority_level",
        "last_integrated_at",
    )
    list_filter = ("source_system", "country", "province", "seniority_level", "is_active")
    search_fields = (
        "full_name",
        "first_name",
        "last_name",
        "email",
        "document_id",
        "cuil",
        "primary_profile",
        "sub_profile",
    )
    actions = ["run_llm_skill_extraction"]

    @admin.action(description="Ejecutar extraccion LLM de skills")
    def run_llm_skill_extraction(self, request, queryset):
        extractor = IntegrationCandidateLLMSkillExtractor()
        success_count = 0
        failed_count = 0
        for candidate in queryset:
            run = extractor.extract_candidate_skills(candidate)
            if run.status == IntegrationCandidateLLMRun.Status.SUCCESS:
                success_count += 1
            else:
                failed_count += 1
        self.message_user(
            request,
            f"Extracciones completadas. Exitosas: {success_count}. Fallidas: {failed_count}.",
        )


@admin.register(LLMAllowedSkill)
class LLMAllowedSkillAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("code", "name", "description")


@admin.register(IntegrationCandidateLLMRun)
class IntegrationCandidateLLMRunAdmin(admin.ModelAdmin):
    list_display = ("candidate", "status", "provider", "model_name", "prompt_version", "executed_at")
    list_filter = ("status", "provider", "model_name", "prompt_version")
    search_fields = ("candidate__full_name", "candidate__email", "error_message")
