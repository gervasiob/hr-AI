import json
from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from openai import OpenAI

from recruitment.models import (
    AIClassificationRun,
    AIExtractedSkill,
    Candidate,
    CandidateSkill,
    Skill,
)


SYSTEM_PROMPT = """
Eres un analista de talento especializado en reclutamiento tecnico.
Debes leer el perfil del candidato y devolver un JSON con estas claves exactas:
- technical_skills
- soft_skills
- education_skills

Cada clave debe contener una lista de objetos con:
- name
- evidence
- confidence

No agregues texto extra. Responde solo JSON valido.
""".strip()


class CandidateAIClassifier:
    def classify_candidate(self, candidate: Candidate) -> AIClassificationRun:
        payload = candidate.build_ai_payload()
        run = AIClassificationRun.objects.create(
            candidate=candidate,
            status=AIClassificationRun.Status.PENDING,
            provider="openai" if settings.OPENAI_API_KEY else "heuristic",
            model_name=settings.OPENAI_MODEL if settings.OPENAI_API_KEY else "heuristic-v1",
            request_payload=payload,
        )

        try:
            result = self._call_model(payload) if self._can_use_openai() else self._heuristic(payload)
            self._persist_result(candidate, run, result)
            run.status = AIClassificationRun.Status.SUCCESS
            run.raw_response = result
            run.executed_at = timezone.now()
            run.save(
                update_fields=["status", "raw_response", "executed_at", "updated_at"]
            )
        except Exception as exc:
            run.status = AIClassificationRun.Status.FAILED
            run.error_message = str(exc)
            run.executed_at = timezone.now()
            run.save(
                update_fields=["status", "error_message", "executed_at", "updated_at"]
            )
        return run

    def _can_use_openai(self) -> bool:
        return settings.AI_CLASSIFIER_ENABLED and bool(settings.OPENAI_API_KEY)

    def _call_model(self, payload: dict) -> dict:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=True, indent=2),
                },
            ],
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)

    def _heuristic(self, payload: dict) -> dict:
        text_parts = [
            payload["candidate"].get("summary", ""),
            payload["candidate"].get("resume_text", ""),
        ]
        for item in payload.get("experience", []):
            text_parts.extend(
                [
                    item.get("position", ""),
                    item.get("achievements", ""),
                    item.get("technologies", ""),
                ]
            )
        for item in payload.get("education", []):
            text_parts.extend(
                [
                    item.get("degree", ""),
                    item.get("field_of_study", ""),
                    item.get("description", ""),
                ]
            )
        source_text = " ".join(part for part in text_parts if part).lower()

        return {
            "technical_skills": self._extract_keywords(
                source_text,
                [
                    "python",
                    "django",
                    "postgresql",
                    "sql",
                    "javascript",
                    "react",
                    "aws",
                    "docker",
                    "git",
                    "rest api",
                ],
            ),
            "soft_skills": self._extract_keywords(
                source_text,
                [
                    "liderazgo",
                    "comunicacion",
                    "trabajo en equipo",
                    "resolucion de problemas",
                    "adaptabilidad",
                    "mentoria",
                    "gestion",
                    "negociacion",
                ],
            ),
            "education_skills": self._extract_keywords(
                source_text,
                [
                    "ingenieria",
                    "licenciatura",
                    "maestria",
                    "doctorado",
                    "certificacion",
                    "bootcamp",
                    "curso",
                    "analisis de datos",
                ],
            ),
        }

    def _extract_keywords(self, text: str, keywords: list[str]) -> list[dict]:
        matches = []
        for keyword in keywords:
            if keyword in text:
                matches.append(
                    {
                        "name": keyword.title(),
                        "evidence": f"Detectado en el perfil por coincidencia con '{keyword}'.",
                        "confidence": 0.72,
                    }
                )
        return matches

    def _persist_result(self, candidate: Candidate, run: AIClassificationRun, result: dict) -> None:
        AIExtractedSkill.objects.filter(classification_run=run).delete()

        category_map = {
            "technical_skills": Skill.Category.TECHNICAL,
            "soft_skills": Skill.Category.SOFT,
            "education_skills": Skill.Category.EDUCATION,
        }

        for result_key, category in category_map.items():
            for item in result.get(result_key, []):
                skill_name = (item.get("name") or "").strip()
                if not skill_name:
                    continue
                skill, _ = Skill.objects.get_or_create(
                    name=skill_name,
                    defaults={"category": category},
                )
                if skill.category != category:
                    skill.category = category
                    skill.save(update_fields=["category", "updated_at"])

                confidence = Decimal(str(item.get("confidence", 0.5))).quantize(
                    Decimal("0.01")
                )
                AIExtractedSkill.objects.create(
                    classification_run=run,
                    candidate=candidate,
                    normalized_skill=skill,
                    skill_name=skill_name,
                    category=category,
                    evidence_text=item.get("evidence", ""),
                    confidence=confidence,
                )

                CandidateSkill.objects.update_or_create(
                    candidate=candidate,
                    skill=skill,
                    source=CandidateSkill.Source.AI,
                    defaults={
                        "proficiency": 3,
                        "years_experience": 0,
                        "evidence_text": item.get("evidence", ""),
                        "ai_confidence": confidence,
                    },
                )
