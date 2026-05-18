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
