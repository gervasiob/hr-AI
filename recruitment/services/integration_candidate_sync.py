from django.db import transaction

from recruitment.models import Candidate, IntegrationCandidate
from recruitment.services.llm_skill_extractor import IntegrationCandidateLLMSkillExtractor


class IntegrationCandidateToLocalCandidateService:
    def extract_and_sync(self, integration_candidate: IntegrationCandidate):
        run = IntegrationCandidateLLMSkillExtractor().extract_candidate_skills(integration_candidate)
        if run.status != run.Status.SUCCESS:
            return None, run

        normalized = run.normalized_response or {}
        candidate = self._upsert_candidate(integration_candidate, normalized)
        return candidate, run

    @transaction.atomic
    def _upsert_candidate(self, integration_candidate: IntegrationCandidate, normalized: dict) -> Candidate:
        candidate = Candidate.objects.filter(idIntegration=integration_candidate.idIntegration).first()

        if not candidate and integration_candidate.email:
            candidate = Candidate.objects.filter(email__iexact=integration_candidate.email).first()

        if candidate is None:
            candidate = Candidate(idIntegration=integration_candidate.idIntegration)

        candidate.idIntegration = integration_candidate.idIntegration
        candidate.first_name = integration_candidate.first_name or integration_candidate.full_name or "Sin nombre"
        candidate.last_name = integration_candidate.last_name or "-"
        candidate.email = self._resolve_email(integration_candidate, candidate)
        candidate.phone = integration_candidate.phone or ""
        candidate.document_id = integration_candidate.document_id or ""
        candidate.location = self._build_location(integration_candidate)
        candidate.cv_s3_url = integration_candidate.cv_s3_url or ""
        candidate.portfolio_url = integration_candidate.cv_s3_url or candidate.portfolio_url or ""
        candidate.summary = integration_candidate.summary or ""
        candidate.resume_text = self._build_resume_text(integration_candidate)
        candidate.desired_salary = integration_candidate.expected_salary
        candidate.current_position = (
            integration_candidate.current_job
            or integration_candidate.sub_profile
            or integration_candidate.primary_profile
            or ""
        )
        candidate.techSkills = normalized.get("techSkills", [])
        candidate.softSkills = normalized.get("softSkills", [])
        candidate.educationSkills = normalized.get("educationSkills", [])
        candidate.langSkills = normalized.get("langSkills", [])
        candidate.save()
        return candidate

    def _resolve_email(self, integration_candidate: IntegrationCandidate, candidate: Candidate) -> str:
        if integration_candidate.email:
            return integration_candidate.email
        if candidate.pk and candidate.email:
            return candidate.email
        return f"integration-{integration_candidate.idIntegration}@local.invalid"

    def _build_location(self, integration_candidate: IntegrationCandidate) -> str:
        parts = [
            integration_candidate.zone,
            integration_candidate.province,
            integration_candidate.country,
        ]
        return ", ".join(part for part in parts if part)

    def _build_resume_text(self, integration_candidate: IntegrationCandidate) -> str:
        parts = [
            integration_candidate.summary,
            integration_candidate.technical_skills_text,
            integration_candidate.profile_description,
        ]
        return "\n\n".join(part for part in parts if part)
