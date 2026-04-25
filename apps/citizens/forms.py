from django import forms

from apps.core.form_styles import apply_input_styling

from .models import AddressChangeRequest, CitizenProfile


class ProfileForm(forms.ModelForm):
    """Self-service editable fields — none of these impact resident cards."""

    class Meta:
        model = CitizenProfile
        fields = ["national_number", "phone", "date_of_birth"]
        widgets = {"date_of_birth": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_input_styling(self)


class AddressChangeRequestForm(forms.ModelForm):
    """Citizen submits this form. An agent then approves or rejects."""

    class Meta:
        model = AddressChangeRequest
        fields = ["street", "number", "box", "postal_code", "commune", "country", "reason"]
        widgets = {"reason": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_input_styling(self)


class AgentDecisionForm(forms.Form):
    """Shared by approve / reject endpoints — only carries the decision notes."""

    notes = forms.CharField(
        label="Notes",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Justification visible par le citoyen."}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_input_styling(self)
