from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Organization(TimeStampedModel):
    class CompanySize(models.TextChoices):
        SMALL = "small", "Pequena"
        MEDIUM = "medium", "Mediana"
        LARGE = "large", "Grande"
        ENTERPRISE = "enterprise", "Enterprise"

    name = models.CharField(max_length=255)
    tax_id = models.CharField("CUIT/NIF", max_length=50, blank=True)
    website = models.URLField(blank=True)
    industry = models.CharField(max_length=120, blank=True)
    size = models.CharField(
        max_length=20,
        choices=CompanySize.choices,
        default=CompanySize.MEDIUM,
    )
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Skill(TimeStampedModel):
    class Category(models.TextChoices):
        TECHNICAL = "technical", "Tecnica"
        SOFT = "soft", "Soft"
        EDUCATION = "education", "Educacion"

    name = models.CharField(max_length=120, unique=True)
    category = models.CharField(max_length=20, choices=Category.choices)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


class Candidate(TimeStampedModel):
    class Availability(models.TextChoices):
        IMMEDIATE = "immediate", "Inmediata"
        TWO_WEEKS = "two_weeks", "2 semanas"
        ONE_MONTH = "one_month", "1 mes"
        NEGOTIABLE = "negotiable", "A convenir"

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=50, blank=True)
    document_id = models.CharField(max_length=50, blank=True)
    location = models.CharField(max_length=120, blank=True)
    linkedin_url = models.URLField(blank=True)
    portfolio_url = models.URLField(blank=True)
    summary = models.TextField(blank=True)
    resume_text = models.TextField(blank=True)
    desired_salary = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    currency = models.CharField(max_length=10, default="USD")
    availability = models.CharField(
        max_length=20,
        choices=Availability.choices,
        default=Availability.NEGOTIABLE,
    )
    current_position = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def build_ai_payload(self):
        education = list(
            self.educations.values(
                "education_level",
                "institution",
                "degree",
                "field_of_study",
                "description",
            )
        )
        experience = list(
            self.experiences.values(
                "company",
                "position",
                "employment_type",
                "achievements",
                "technologies",
            )
        )
        current_skills = list(
            self.skills.select_related("skill").values(
                "skill__name",
                "skill__category",
                "source",
                "proficiency",
                "evidence_text",
            )
        )
        return {
            "candidate": {
                "full_name": self.full_name,
                "email": self.email,
                "location": self.location,
                "current_position": self.current_position,
                "availability": self.availability,
                "summary": self.summary,
                "resume_text": self.resume_text,
            },
            "education": education,
            "experience": experience,
            "current_skills": current_skills,
        }


class CandidateEducation(TimeStampedModel):
    class EducationLevel(models.TextChoices):
        HIGH_SCHOOL = "high_school", "Secundario"
        TECHNICAL = "technical", "Tecnico"
        BACHELOR = "bachelor", "Grado"
        MASTER = "master", "Maestria"
        DOCTORATE = "doctorate", "Doctorado"
        COURSE = "course", "Curso"
        CERTIFICATION = "certification", "Certificacion"

    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.CASCADE,
        related_name="educations",
    )
    institution = models.CharField(max_length=255)
    degree = models.CharField(max_length=255)
    field_of_study = models.CharField(max_length=255, blank=True)
    education_level = models.CharField(max_length=20, choices=EducationLevel.choices)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-end_date", "-start_date", "institution"]

    def __str__(self):
        return f"{self.degree} - {self.institution}"


class CandidateExperience(TimeStampedModel):
    class EmploymentType(models.TextChoices):
        FULL_TIME = "full_time", "Tiempo completo"
        PART_TIME = "part_time", "Medio tiempo"
        CONTRACTOR = "contractor", "Contratista"
        FREELANCE = "freelance", "Freelance"
        INTERNSHIP = "internship", "Pasantia"

    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.CASCADE,
        related_name="experiences",
    )
    company = models.CharField(max_length=255)
    position = models.CharField(max_length=255)
    employment_type = models.CharField(
        max_length=20,
        choices=EmploymentType.choices,
        default=EmploymentType.FULL_TIME,
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_current = models.BooleanField(default=False)
    achievements = models.TextField(blank=True)
    technologies = models.TextField(blank=True)

    class Meta:
        ordering = ["-end_date", "-start_date", "company"]

    def __str__(self):
        return f"{self.position} @ {self.company}"


class CandidateSkill(TimeStampedModel):
    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        RESUME = "resume", "CV"
        AI = "ai", "IA"

    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.CASCADE,
        related_name="skills",
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.CASCADE,
        related_name="candidate_skills",
    )
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    proficiency = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    years_experience = models.PositiveSmallIntegerField(default=0)
    evidence_text = models.TextField(blank=True)
    ai_confidence = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["skill__category", "skill__name"]
        unique_together = ("candidate", "skill", "source")

    def __str__(self):
        return f"{self.candidate.full_name} - {self.skill.name}"


class JobOpening(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        OPEN = "open", "Abierta"
        PAUSED = "paused", "Pausada"
        CLOSED = "closed", "Cerrada"

    class Modality(models.TextChoices):
        ONSITE = "onsite", "Presencial"
        HYBRID = "hybrid", "Hibrida"
        REMOTE = "remote", "Remota"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="job_openings",
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    requirements = models.TextField(blank=True)
    location = models.CharField(max_length=120, blank=True)
    modality = models.CharField(
        max_length=20,
        choices=Modality.choices,
        default=Modality.HYBRID,
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    closing_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "title"]

    def __str__(self):
        return self.title

    def publish(self):
        self.status = self.Status.OPEN
        if not self.published_at:
            self.published_at = timezone.now()
        self.save(update_fields=["status", "published_at", "updated_at"])


class JobSkillRequirement(TimeStampedModel):
    class Priority(models.TextChoices):
        REQUIRED = "required", "Excluyente"
        IMPORTANT = "important", "Importante"
        NICE_TO_HAVE = "nice_to_have", "Deseable"

    job_opening = models.ForeignKey(
        JobOpening,
        on_delete=models.CASCADE,
        related_name="skill_requirements",
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.CASCADE,
        related_name="job_requirements",
    )
    priority = models.CharField(max_length=20, choices=Priority.choices)
    min_proficiency = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    is_mandatory = models.BooleanField(default=False)

    class Meta:
        ordering = ["priority", "skill__name"]
        unique_together = ("job_opening", "skill")

    def __str__(self):
        return f"{self.job_opening.title} - {self.skill.name}"


class Application(TimeStampedModel):
    class Stage(models.TextChoices):
        APPLIED = "applied", "Postulado"
        SCREENING = "screening", "Screening"
        INTERVIEW = "interview", "Entrevista"
        TECHNICAL = "technical", "Tecnica"
        OFFER = "offer", "Oferta"
        HIRED = "hired", "Contratado"
        REJECTED = "rejected", "Rechazado"

    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.CASCADE,
        related_name="applications",
    )
    job_opening = models.ForeignKey(
        JobOpening,
        on_delete=models.CASCADE,
        related_name="applications",
    )
    source = models.CharField(max_length=100, blank=True)
    stage = models.CharField(max_length=20, choices=Stage.choices, default=Stage.APPLIED)
    cover_letter = models.TextField(blank=True)
    recruiter_notes = models.TextField(blank=True)
    ai_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("candidate", "job_opening")

    def __str__(self):
        return f"{self.candidate.full_name} -> {self.job_opening.title}"


class AIClassificationRun(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        SUCCESS = "success", "Exitosa"
        FAILED = "failed", "Fallida"

    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.CASCADE,
        related_name="classification_runs",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    provider = models.CharField(max_length=50, default="openai")
    model_name = models.CharField(max_length=100, blank=True)
    prompt_version = models.CharField(max_length=50, default="v1")
    request_payload = models.JSONField(default=dict, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    tokens_prompt = models.PositiveIntegerField(default=0)
    tokens_completion = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Clasificacion {self.candidate.full_name} - {self.created_at:%Y-%m-%d %H:%M}"


class AIExtractedSkill(TimeStampedModel):
    classification_run = models.ForeignKey(
        AIClassificationRun,
        on_delete=models.CASCADE,
        related_name="extracted_skills",
    )
    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.CASCADE,
        related_name="ai_extracted_skills",
    )
    normalized_skill = models.ForeignKey(
        Skill,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_extractions",
    )
    skill_name = models.CharField(max_length=120)
    category = models.CharField(max_length=20, choices=Skill.Category.choices)
    evidence_text = models.TextField(blank=True)
    confidence = models.DecimalField(max_digits=4, decimal_places=2, default=0.50)

    class Meta:
        ordering = ["category", "-confidence", "skill_name"]

    def __str__(self):
        return f"{self.skill_name} - {self.get_category_display()}"


class RemoteTableSync(TimeStampedModel):
    class SyncStatus(models.TextChoices):
        IDLE = "idle", "Inactiva"
        SUCCESS = "success", "Exitosa"
        FAILED = "failed", "Fallida"

    table_name = models.CharField(max_length=120, unique=True)
    endpoint = models.CharField(max_length=255, blank=True)
    is_selected = models.BooleanField(default=False)
    last_remote_id = models.PositiveBigIntegerField(default=0)
    records_count = models.PositiveIntegerField(default=0)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_sync_status = models.CharField(
        max_length=20,
        choices=SyncStatus.choices,
        default=SyncStatus.IDLE,
    )
    last_error = models.TextField(blank=True)

    class Meta:
        ordering = ["table_name"]

    def __str__(self):
        return self.table_name


class RemoteTableRecord(TimeStampedModel):
    table = models.ForeignKey(
        RemoteTableSync,
        on_delete=models.CASCADE,
        related_name="records",
    )
    remote_id = models.PositiveBigIntegerField()
    payload = models.JSONField(default=dict, blank=True)
    source_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["table__table_name", "remote_id"]
        unique_together = ("table", "remote_id")

    def __str__(self):
        return f"{self.table.table_name} #{self.remote_id}"


class IntegrationCandidate(TimeStampedModel):
    idIntegration = models.PositiveBigIntegerField(unique=True, db_index=True)
    source_system = models.CharField(max_length=100, default="ngovatek_hr")
    formatted_cv_id = models.PositiveBigIntegerField(null=True, blank=True)

    first_name = models.CharField(max_length=120, blank=True)
    last_name = models.CharField(max_length=120, blank=True)
    full_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    alt_email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    document_id = models.CharField(max_length=50, blank=True)
    cuil = models.CharField(max_length=50, blank=True)
    gender = models.CharField(max_length=30, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    age = models.PositiveIntegerField(null=True, blank=True)

    address = models.CharField(max_length=255, blank=True)
    zone = models.CharField(max_length=120, blank=True)
    province = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=120, blank=True)

    available_to_apply = models.BooleanField(default=True)
    availability_days = models.PositiveIntegerField(null=True, blank=True)
    is_blacklisted = models.BooleanField(default=False)
    blacklist_reason = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    rejection_email_sent = models.BooleanField(default=False)

    current_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    expected_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    health_insurance = models.CharField(max_length=255, blank=True)
    bonuses = models.TextField(blank=True)
    trainings = models.TextField(blank=True)
    observations = models.TextField(blank=True)

    current_job = models.CharField(max_length=255, blank=True)
    primary_profile = models.CharField(max_length=255, blank=True)
    sub_profile = models.CharField(max_length=255, blank=True)
    seniority = models.CharField(max_length=255, blank=True)
    seniority_level = models.CharField(max_length=255, blank=True)
    experience_years = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    summary = models.TextField(blank=True)
    technical_skills_text = models.TextField(blank=True)
    languages_text = models.TextField(blank=True)
    profile_description = models.TextField(blank=True)

    skills_json = models.JSONField(default=list, blank=True)
    languages_json = models.JSONField(default=list, blank=True)
    education_json = models.JSONField(default=list, blank=True)
    work_experience_json = models.JSONField(default=list, blank=True)
    certifications_json = models.JSONField(default=list, blank=True)
    integrated_payload = models.JSONField(default=dict, blank=True)

    last_integrated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["last_name", "first_name", "idIntegration"]
        db_table = "integrationCandidates"

    def __str__(self):
        return self.full_name or f"IntegrationCandidate #{self.idIntegration}"
