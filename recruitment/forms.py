from django import forms

from recruitment.models import Application, Candidate


class CandidateForm(forms.ModelForm):
    class Meta:
        model = Candidate
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "location",
            "current_position",
            "availability",
            "summary",
            "resume_text",
            "linkedin_url",
            "portfolio_url",
            "desired_salary",
            "currency",
        ]
        widgets = {
            "summary": forms.Textarea(attrs={"rows": 4}),
            "resume_text": forms.Textarea(attrs={"rows": 8}),
        }


class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ["candidate", "job_opening", "source", "stage", "cover_letter", "recruiter_notes"]
        widgets = {
            "cover_letter": forms.Textarea(attrs={"rows": 4}),
            "recruiter_notes": forms.Textarea(attrs={"rows": 4}),
        }


class RemoteTableSyncForm(forms.Form):
    tables = forms.MultipleChoiceField(
        choices=(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Tablas a copiar",
    )

    def __init__(self, *args, available_tables=None, **kwargs):
        super().__init__(*args, **kwargs)
        available_tables = available_tables or []
        self.fields["tables"].choices = [(table, table) for table in available_tables]


class IntegrationCandidateFilterForm(forms.Form):
    q = forms.CharField(required=False, label="Buscar")
    primary_profile = forms.CharField(required=False, label="Perfil principal")
    sub_profile = forms.CharField(required=False, label="Subperfil")
    seniority_level = forms.CharField(required=False, label="Senioridad")
    country = forms.CharField(required=False, label="Pais")
    province = forms.CharField(required=False, label="Provincia")
    processed_status = forms.ChoiceField(
        required=False,
        label="Procesado",
        choices=(
            ("", "Todos"),
            ("true", "Procesados"),
            ("false", "No procesados"),
        ),
    )
    has_cv_link = forms.ChoiceField(
        required=False,
        label="CV link",
        choices=(
            ("", "Todos"),
            ("true", "Con CV"),
            ("false", "Sin CV"),
        ),
    )
    has_work_experience = forms.ChoiceField(
        required=False,
        label="Experiencia laboral",
        choices=(
            ("", "Todas"),
            ("true", "Con experiencia"),
            ("false", "Sin experiencia"),
        ),
    )
    is_active = forms.ChoiceField(
        required=False,
        label="Activo",
        choices=(
            ("", "Todos"),
            ("true", "Solo activos"),
            ("false", "Solo inactivos"),
        ),
    )
    order = forms.ChoiceField(
        required=False,
        label="Ordenar por",
        choices=(
            ("-last_integrated_at", "Ultima integracion"),
            ("full_name", "Nombre A-Z"),
            ("-full_name", "Nombre Z-A"),
            ("primary_profile", "Perfil principal"),
            ("sub_profile", "Subperfil"),
            ("country", "Pais"),
            ("province", "Provincia"),
            ("-idIntegration", "ID integracion desc"),
            ("idIntegration", "ID integracion asc"),
        ),
    )
    page_size = forms.ChoiceField(
        required=False,
        label="Por pagina",
        choices=(("10", "10"), ("25", "25"), ("50", "50"), ("100", "100")),
    )
