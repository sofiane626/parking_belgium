from django import forms

from apps.core.form_styles import apply_input_styling

from .models import Company


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = [
            "name", "vat_number", "activity",
            "street", "number", "box", "postal_code", "commune", "country",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_input_styling(self)
