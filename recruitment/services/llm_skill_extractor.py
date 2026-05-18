import json
import os
from pathlib import Path

from django.conf import settings
from django.utils.text import slugify
from django.utils import timezone
from dotenv import load_dotenv
from openai import OpenAI

from recruitment.models import IntegrationCandidate, IntegrationCandidateLLMRun, LLMAllowedSkill


PROMPT_TEMPLATE = """
You are an HR AI specialized in candidate skill extraction.

Analyze the candidate information and extract:

1. Technical skills
2. Soft skills
3. Education-related skills
4. Language skills

Rules:
- Return ONLY valid JSON
- Do not include explanations
- Do not include markdown
- Do not invent information not supported by the candidate profile
- Normalize skill names
- Infer reasonable skills from work experience and education
- Use these levels only:
  J = Junior
  I = Intermediate
  A = Advanced
  E = Expert

{{skill_selection_rules}}

For each skill return:
- code
- name
- level

{{allowed_skills_section}}

Candidate information:
----------------------

Education:
{{education}}

Work Experience:
{{work_experience}}

Languages:
{{languages}}

Summary:
{{summary}}

Expected JSON structure:
{
  "techSkills": [],
  "softSkills": [],
  "educationSkills": [],
  "langSkills": []
}
""".strip()


class IntegrationCandidateLLMSkillExtractor:
    RESPONSE_KEYS = {
        "techSkills": LLMAllowedSkill.Category.TECHNICAL,
        "softSkills": LLMAllowedSkill.Category.SOFT,
        "educationSkills": LLMAllowedSkill.Category.EDUCATION,
        "langSkills": LLMAllowedSkill.Category.LANGUAGE,
    }
    ALLOWED_LEVELS = {"J", "I", "A", "E"}

    def extract_candidate_skills(self, candidate: IntegrationCandidate) -> IntegrationCandidateLLMRun:
        api_key = self._get_openai_api_key()
        model_name = self._get_openai_model()
        if not api_key:
            raise RuntimeError("Falta OPENAI_API_KEY para ejecutar la extraccion LLM.")

        payload = candidate.build_llm_skill_payload()
        allowed_snapshot = self._build_allowed_skills_snapshot()
        prompt = self._build_prompt(payload, allowed_snapshot)

        run = IntegrationCandidateLLMRun.objects.create(
            candidate=candidate,
            status=IntegrationCandidateLLMRun.Status.PENDING,
            provider="openai",
            model_name=model_name,
            request_payload=payload,
            request_prompt=prompt,
            allowed_skills_snapshot=allowed_snapshot,
        )

        try:
            raw_response = self._call_model(prompt, api_key=api_key, model_name=model_name)
            normalized_response = self._normalize_response(raw_response, allowed_snapshot)
            run.status = IntegrationCandidateLLMRun.Status.SUCCESS
            run.raw_response = json.dumps(raw_response, ensure_ascii=True, indent=2)
            run.normalized_response = normalized_response
            run.executed_at = timezone.now()
            run.save(
                update_fields=[
                    "status",
                    "raw_response",
                    "normalized_response",
                    "executed_at",
                    "updated_at",
                ]
            )
        except Exception as exc:
            run.status = IntegrationCandidateLLMRun.Status.FAILED
            run.error_message = str(exc)
            run.executed_at = timezone.now()
            run.save(
                update_fields=["status", "error_message", "executed_at", "updated_at"]
            )
        return run

    def _call_model(self, prompt: str, api_key: str, model_name: str) -> dict:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model_name,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)

    def _reload_env_file(self):
        base_dir = getattr(settings, "BASE_DIR", Path(__file__).resolve().parents[2])
        load_dotenv(Path(base_dir) / ".env", override=True)

    def _get_openai_api_key(self) -> str:
        api_key = (getattr(settings, "OPENAI_API_KEY", "") or "").strip()
        if api_key:
            return api_key
        self._reload_env_file()
        return os.getenv("OPENAI_API_KEY", "").strip()

    def _get_openai_model(self) -> str:
        model_name = (getattr(settings, "OPENAI_MODEL", "") or "").strip()
        if model_name:
            return model_name
        self._reload_env_file()
        return os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()

    def _build_allowed_skills_snapshot(self) -> dict:
        skills = LLMAllowedSkill.objects.filter(is_active=True).order_by("category", "name")
        snapshot = {
            "techSkills": [],
            "softSkills": [],
            "educationSkills": [],
            "langSkills": [],
        }
        category_to_key = {
            LLMAllowedSkill.Category.TECHNICAL: "techSkills",
            LLMAllowedSkill.Category.SOFT: "softSkills",
            LLMAllowedSkill.Category.EDUCATION: "educationSkills",
            LLMAllowedSkill.Category.LANGUAGE: "langSkills",
        }
        for skill in skills:
            snapshot[category_to_key[skill.category]].append(
                {
                    "code": skill.code,
                    "name": skill.name,
                }
            )
        return snapshot

    def _build_prompt(self, payload: dict, allowed_snapshot: dict) -> str:
        has_allowed_skills = any(allowed_snapshot.values())
        if has_allowed_skills:
            skill_selection_rules = "- Use ONLY the provided allowed skills list"
            allowed_skills_section = (
                "Allowed skills catalog:\n"
                "----------------------\n"
                f"{json.dumps(allowed_snapshot, ensure_ascii=True, indent=2)}"
            )
        else:
            skill_selection_rules = (
                "- There is no allowed skills catalog available, so extract the most relevant skills "
                "directly from the candidate information\n"
                "- Create a short normalized code for each skill"
            )
            allowed_skills_section = (
                "Allowed skills catalog:\n"
                "----------------------\n"
                "No catalog was provided. Return relevant normalized skills inferred from the profile."
            )

        replacements = {
            "{{skill_selection_rules}}": skill_selection_rules,
            "{{allowed_skills_section}}": allowed_skills_section,
            "{{education}}": json.dumps(payload.get("education", []), ensure_ascii=True, indent=2),
            "{{work_experience}}": json.dumps(
                payload.get("work_experience", []), ensure_ascii=True, indent=2
            ),
            "{{languages}}": json.dumps(payload.get("languages", []), ensure_ascii=True, indent=2),
            "{{summary}}": json.dumps(
                {
                    "summary": payload.get("summary", ""),
                    "technical_skills_text": payload.get("technical_skills_text", ""),
                    "profile_description": payload.get("profile_description", ""),
                },
                ensure_ascii=True,
                indent=2,
            ),
        }
        prompt = PROMPT_TEMPLATE
        for placeholder, value in replacements.items():
            prompt = prompt.replace(placeholder, value)
        return prompt

    def _normalize_response(self, raw_response: dict, allowed_snapshot: dict) -> dict:
        has_allowed_skills = any(allowed_snapshot.values())
        normalized = {
            "techSkills": [],
            "softSkills": [],
            "educationSkills": [],
            "langSkills": [],
        }

        for response_key in normalized.keys():
            allowed_items = allowed_snapshot.get(response_key, [])
            allowed_by_code = {item["code"].upper(): item for item in allowed_items}
            allowed_by_name = {item["name"].strip().lower(): item for item in allowed_items}

            for item in raw_response.get(response_key, []):
                code = str(item.get("code", "")).strip().upper()
                name = str(item.get("name", "")).strip()
                level = str(item.get("level", "")).strip().upper()

                if level not in self.ALLOWED_LEVELS:
                    continue

                if not has_allowed_skills:
                    normalized_item = self._normalize_open_skill(code=code, name=name, level=level)
                    if normalized_item:
                        normalized[response_key].append(normalized_item)
                    continue

                allowed_item = None
                if code and code in allowed_by_code:
                    allowed_item = allowed_by_code[code]
                elif name and name.lower() in allowed_by_name:
                    allowed_item = allowed_by_name[name.lower()]

                if not allowed_item:
                    continue

                normalized[response_key].append(
                    {
                        "code": allowed_item["code"],
                        "name": allowed_item["name"],
                        "level": level,
                    }
                )

            normalized[response_key] = self._deduplicate(normalized[response_key])

        return normalized

    def _normalize_open_skill(self, code: str, name: str, level: str) -> dict | None:
        normalized_name = name or code.replace("_", " ").replace("-", " ").title()
        normalized_name = normalized_name.strip()
        if not normalized_name:
            return None

        normalized_code = code or slugify(normalized_name).replace("-", "_").upper()
        normalized_code = normalized_code.strip("_")
        if not normalized_code:
            return None

        return {
            "code": normalized_code,
            "name": normalized_name,
            "level": level,
        }

    def _deduplicate(self, items: list[dict]) -> list[dict]:
        unique_items = []
        seen = set()
        for item in items:
            key = (item["code"], item["level"])
            if key in seen:
                continue
            seen.add(key)
            unique_items.append(item)
        return unique_items
