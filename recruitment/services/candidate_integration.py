import ast
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags

from recruitment.models import IntegrationCandidate, RemoteTableRecord


class IntegrationCandidateService:
    REQUIRED_TABLES = [
        "candidate",
    ]

    OPTIONAL_TABLES = [
        "candidateprofile",
        "formattedcv",
        "cvfile",
        "formattedcveducation",
        "formattedcvworkexperience",
        "formattedcvcertification",
        "candidatelanguage",
        "language",
        "primaryprofile",
        "subprofile",
        "senioritylevel",
    ]

    def integrate_candidates(self, reset: bool = False) -> dict:
        if reset:
            IntegrationCandidate.objects.all().delete()

        datasets = self._load_datasets(self.REQUIRED_TABLES + self.OPTIONAL_TABLES)
        candidates = datasets["candidate"]
        if not candidates:
            raise RuntimeError(
                "No hay registros sincronizados de la tabla 'candidate'. Sincronizala antes de integrar."
            )

        profile_by_candidate = self._group_by_key(
            datasets["candidateprofile"], "candidate", selector=self._select_candidate_profile
        )
        formatted_cv_by_candidate = self._group_by_key(
            datasets["formattedcv"], "candidate", selector=self._select_formatted_cv
        )
        cv_file_by_candidate = self._group_by_key(
            datasets["cvfile"], "candidate", selector=self._select_cv_file
        )
        education_by_formatted_cv = self._group_by_key(datasets["formattedcveducation"], "formatted_cv")
        experience_by_formatted_cv = self._group_by_key(
            datasets["formattedcvworkexperience"], "formatted_cv"
        )
        certification_by_formatted_cv = self._group_by_key(
            datasets["formattedcvcertification"], "formatted_cv"
        )
        languages_by_candidate = self._group_by_key(datasets["candidatelanguage"], "candidate")

        language_lookup = self._lookup_by_id(datasets["language"])
        primary_profile_lookup = self._lookup_by_id(datasets["primaryprofile"])
        sub_profile_lookup = self._lookup_by_id(datasets["subprofile"])
        seniority_lookup = self._lookup_by_id(datasets["senioritylevel"])

        created_count = 0
        updated_count = 0

        with transaction.atomic():
            for candidate_payload in candidates:
                integration_payload = self._build_integrated_payload(
                    candidate_payload=candidate_payload,
                    candidate_profile=profile_by_candidate.get(str(candidate_payload["id"])),
                    formatted_cv=formatted_cv_by_candidate.get(str(candidate_payload["id"])),
                    cv_file=cv_file_by_candidate.get(str(candidate_payload["id"])),
                    education_by_formatted_cv=education_by_formatted_cv,
                    experience_by_formatted_cv=experience_by_formatted_cv,
                    certification_by_formatted_cv=certification_by_formatted_cv,
                    languages_by_candidate=languages_by_candidate,
                    language_lookup=language_lookup,
                    primary_profile_lookup=primary_profile_lookup,
                    sub_profile_lookup=sub_profile_lookup,
                    seniority_lookup=seniority_lookup,
                )

                obj, created = IntegrationCandidate.objects.update_or_create(
                    idIntegration=int(candidate_payload["id"]),
                    defaults=integration_payload,
                )
                created_count += int(created)
                updated_count += int(not created)

        return {
            "processed_count": len(candidates),
            "created_count": created_count,
            "updated_count": updated_count,
            "total_integrated": IntegrationCandidate.objects.count(),
        }

    def _load_datasets(self, table_names: list[str]) -> dict[str, list[dict]]:
        datasets = {}
        for table_name in table_names:
            datasets[table_name] = list(
                RemoteTableRecord.objects.filter(table__table_name=table_name)
                .order_by("remote_id")
                .values_list("payload", flat=True)
            )
        return datasets

    def _lookup_by_id(self, rows: list[dict]) -> dict[str, dict]:
        return {str(row.get("id")): row for row in rows if row.get("id") not in (None, "")}

    def _group_by_key(self, rows: list[dict], key: str, selector=None) -> dict[str, list | dict]:
        grouped = defaultdict(list)
        for row in rows:
            value = row.get(key)
            if value in (None, ""):
                continue
            grouped[str(value)].append(row)

        if selector is None:
            return dict(grouped)
        return {group_key: selector(group_rows) for group_key, group_rows in grouped.items()}

    def _select_candidate_profile(self, rows: list[dict]) -> dict:
        selected = [row for row in rows if self._to_bool(row.get("is_selected"))]
        if selected:
            return selected[0]
        return rows[0]

    def _select_formatted_cv(self, rows: list[dict]) -> dict:
        return sorted(
            rows,
            key=lambda row: (
                self._safe_sort_value(row.get("parsed_at")),
                self._safe_sort_value(row.get("id")),
            ),
            reverse=True,
        )[0]

    def _select_cv_file(self, rows: list[dict]) -> dict:
        prioritized_rows = [row for row in rows if self._to_str(row.get("s3_url"))]
        source_rows = prioritized_rows or rows
        return sorted(
            source_rows,
            key=lambda row: (
                self._to_bool(row.get("is_active")),
                self._safe_sort_value(row.get("uploaded_at")),
                self._safe_sort_value(row.get("id")),
            ),
            reverse=True,
        )[0]

    def _build_integrated_payload(
        self,
        candidate_payload: dict,
        candidate_profile: dict | None,
        formatted_cv: dict | None,
        cv_file: dict | None,
        education_by_formatted_cv: dict,
        experience_by_formatted_cv: dict,
        certification_by_formatted_cv: dict,
        languages_by_candidate: dict,
        language_lookup: dict,
        primary_profile_lookup: dict,
        sub_profile_lookup: dict,
        seniority_lookup: dict,
    ) -> dict:
        formatted_cv_id = str(formatted_cv.get("id")) if formatted_cv else None
        education_rows = education_by_formatted_cv.get(formatted_cv_id, []) if formatted_cv_id else []
        experience_rows = (
            experience_by_formatted_cv.get(formatted_cv_id, []) if formatted_cv_id else []
        )
        certification_rows = (
            certification_by_formatted_cv.get(formatted_cv_id, []) if formatted_cv_id else []
        )
        language_rows = languages_by_candidate.get(str(candidate_payload["id"]), [])

        primary_profile_name = self._lookup_name(
            primary_profile_lookup, candidate_profile.get("primary_profile") if candidate_profile else None
        )
        sub_profile_name = self._lookup_name(
            sub_profile_lookup, candidate_profile.get("sub_profile") if candidate_profile else None
        )
        seniority_level_name = self._lookup_name(
            seniority_lookup,
            candidate_profile.get("seniority_level") if candidate_profile else None,
        )

        languages_json = self._build_languages(language_rows, language_lookup)
        skills_json = self._build_skills(candidate_profile, formatted_cv)

        full_name = self._first_non_empty(
            formatted_cv.get("full_name") if formatted_cv else "",
            f"{candidate_payload.get('first_name', '')} {candidate_payload.get('last_name', '')}".strip(),
        )

        integrated_payload = {
            "candidate": candidate_payload,
            "candidate_profile": candidate_profile or {},
            "formatted_cv": formatted_cv or {},
            "cv_file": cv_file or {},
            "education": education_rows,
            "work_experience": experience_rows,
            "certifications": certification_rows,
            "languages": languages_json,
            "skills": skills_json,
        }

        return {
            "source_system": "ngovatek_hr",
            "formatted_cv_id": self._to_int(formatted_cv.get("id")) if formatted_cv else None,
            "first_name": self._to_str(candidate_payload.get("first_name")),
            "last_name": self._to_str(candidate_payload.get("last_name")),
            "full_name": full_name,
            "email": self._to_str(
                self._first_non_empty(
                    candidate_payload.get("email"),
                    formatted_cv.get("email") if formatted_cv else "",
                )
            ),
            "alt_email": self._to_str(candidate_payload.get("alt_email")),
            "phone": self._to_str(
                self._first_non_empty(
                    candidate_payload.get("phone"),
                    formatted_cv.get("phone_number") if formatted_cv else "",
                )
            ),
            "document_id": self._to_str(candidate_payload.get("dni")),
            "cuil": self._to_str(candidate_payload.get("cuil")),
            "gender": self._to_str(candidate_payload.get("gender")),
            "birth_date": self._to_date(candidate_payload.get("birth_date")),
            "age": self._to_int(candidate_payload.get("age")),
            "address": self._to_str(
                self._first_non_empty(
                    candidate_payload.get("address"),
                    formatted_cv.get("address") if formatted_cv else "",
                )
            ),
            "cv_s3_url": self._to_str(cv_file.get("s3_url") if cv_file else ""),
            "zone": self._to_str(
                self._first_non_empty(
                    candidate_payload.get("zone"),
                    formatted_cv.get("zone") if formatted_cv else "",
                )
            ),
            "province": self._to_str(candidate_payload.get("province")),
            "country": self._to_str(candidate_payload.get("country")),
            "available_to_apply": self._to_bool(candidate_payload.get("available_to_apply"), True),
            "availability_days": self._to_int(candidate_payload.get("availability_days")),
            "is_blacklisted": self._to_bool(candidate_payload.get("is_blacklisted")),
            "blacklist_reason": self._to_str(candidate_payload.get("blacklist_reason")),
            "is_active": self._to_bool(candidate_payload.get("is_active"), True),
            "rejection_email_sent": self._to_bool(candidate_payload.get("rejection_email_sent")),
            "current_salary": self._to_decimal(candidate_payload.get("current_salary")),
            "expected_salary": self._to_decimal(candidate_payload.get("expected_salary")),
            "health_insurance": self._to_str(candidate_payload.get("health_insurance")),
            "bonuses": self._to_str(candidate_payload.get("bonuses")),
            "trainings": self._to_str(candidate_payload.get("trainings")),
            "observations": self._to_str(candidate_payload.get("observations")),
            "current_job": self._to_str(candidate_profile.get("current_job") if candidate_profile else ""),
            "primary_profile": primary_profile_name,
            "sub_profile": sub_profile_name,
            "seniority": self._to_str(
                self._first_non_empty(
                    candidate_profile.get("seniority") if candidate_profile else "",
                    formatted_cv.get("seniority") if formatted_cv else "",
                )
            ),
            "seniority_level": seniority_level_name,
            "experience_years": self._to_decimal(
                self._first_non_empty(
                    candidate_profile.get("experience_years") if candidate_profile else "",
                    formatted_cv.get("experience_years") if formatted_cv else "",
                )
            ),
            "summary": self._to_str(
                self._first_non_empty(
                    formatted_cv.get("summary") if formatted_cv else "",
                    candidate_payload.get("observations"),
                )
            ),
            "technical_skills_text": self._to_str(
                self._first_non_empty(
                    formatted_cv.get("technical_skills") if formatted_cv else "",
                    candidate_profile.get("skills_description") if candidate_profile else "",
                )
            ),
            "languages_text": ", ".join(item["language"] for item in languages_json if item["language"]),
            "profile_description": self._to_str(formatted_cv.get("profile") if formatted_cv else ""),
            "skills_json": skills_json,
            "languages_json": languages_json,
            "education_json": education_rows,
            "work_experience_json": [self._normalize_experience_row(row) for row in experience_rows],
            "certifications_json": certification_rows,
            "integrated_payload": integrated_payload,
            "last_integrated_at": timezone.now(),
        }

    def _build_languages(self, language_rows: list[dict], language_lookup: dict) -> list[dict]:
        results = []
        for row in language_rows:
            results.append(
                {
                    "language": self._lookup_name(language_lookup, row.get("language")),
                    "written_level": self._to_str(row.get("written_level_obj") or row.get("written_level")),
                    "oral_level": self._to_str(row.get("oral_level_obj") or row.get("oral_level")),
                }
            )
        return results

    def _build_skills(self, candidate_profile: dict | None, formatted_cv: dict | None) -> list[dict]:
        values = []
        if candidate_profile:
            values.extend(self._parse_array_value(candidate_profile.get("skills_description_arr")))
            values.extend(self._split_text_values(candidate_profile.get("skills_description")))
        if formatted_cv:
            values.extend(self._split_text_values(formatted_cv.get("technical_skills")))

        unique_values = []
        seen = set()
        for value in values:
            normalized = value.strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            unique_values.append({"name": normalized, "category": "technical"})
        return unique_values

    def _normalize_experience_row(self, row: dict) -> dict:
        return {
            "company_name": self._to_str(row.get("company_name")),
            "position_title": self._to_str(row.get("position_title")),
            "start_date": row.get("start_date"),
            "end_date": row.get("end_date"),
            "description": self._to_str(row.get("description")),
            "memo": strip_tags(self._to_str(row.get("memo"))),
        }

    def _parse_array_value(self, value) -> list[str]:
        if not value:
            return []
        if isinstance(value, list):
            return [self._to_str(item) for item in value]
        try:
            parsed = ast.literal_eval(str(value))
            if isinstance(parsed, list):
                return [self._to_str(item) for item in parsed]
        except (SyntaxError, ValueError):
            pass
        return self._split_text_values(value)

    def _split_text_values(self, value) -> list[str]:
        text = self._to_str(value)
        if not text:
            return []
        for separator in ["|", ";", "\n"]:
            text = text.replace(separator, ",")
        return [item.strip() for item in text.split(",") if item.strip()]

    def _lookup_name(self, lookup: dict, key) -> str:
        if key in (None, ""):
            return ""
        row = lookup.get(str(key), {})
        return self._to_str(row.get("name"))

    def _first_non_empty(self, *values):
        for value in values:
            if value not in (None, ""):
                return value
        return ""

    def _to_str(self, value) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _to_int(self, value):
        if value in (None, ""):
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    def _to_decimal(self, value):
        if value in (None, ""):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None

    def _to_bool(self, value, default=False) -> bool:
        if value in (None, ""):
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"true", "1", "yes", "si"}

    def _to_date(self, value):
        if value in (None, ""):
            return None
        if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
            return value
        try:
            return timezone.datetime.fromisoformat(str(value)).date()
        except (TypeError, ValueError):
            return None

    def _safe_sort_value(self, value):
        if value in (None, ""):
            return ""
        return str(value)
