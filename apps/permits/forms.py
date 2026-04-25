from django import forms

from apps.core.form_styles import apply_input_styling

from .models import CommunePermitPolicy, PermitConfig


class PermitConfigForm(forms.ModelForm):
    class Meta:
        model = PermitConfig
        fields = [
            "resident_price_cents", "visitor_price_cents", "professional_price_cents",
            "visitor_codes_per_year", "visitor_code_default_hours", "visitor_code_max_hours",
            "permit_default_validity_days",
            "max_vehicles_per_citizen", "max_companies_per_citizen",
            "max_active_pro_per_citizen", "allow_cumul_resident_pro",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_input_styling(self)


class CommunePermitPolicyForm(forms.ModelForm):
    class Meta:
        model = CommunePermitPolicy
        fields = [
            "is_enabled", "auto_attribution",
            "validity_days",
            "price_strategy", "price_fixed_cents", "price_grid",
            "price_exponential_base_cents", "price_exponential_factor",
            "max_active_per_citizen", "max_vehicles_per_card",
            "effective_from", "effective_until",
            "notes",
        ]
        widgets = {
            "effective_from": forms.DateInput(attrs={"type": "date"}),
            "effective_until": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "price_grid": forms.Textarea(
                attrs={"rows": 3, "placeholder": "[[1,1000],[2,2500],[3,5000]]"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_input_styling(self)

    def clean_price_grid(self):
        value = self.cleaned_data.get("price_grid") or []
        # JSONField may pass through a string when widget is Textarea — normalise.
        if isinstance(value, str):
            import json
            try:
                value = json.loads(value or "[]")
            except json.JSONDecodeError:
                raise forms.ValidationError("Format JSON invalide.")
        if not isinstance(value, list):
            raise forms.ValidationError("La grille doit être une liste.")
        for item in value:
            if not (isinstance(item, list) and len(item) == 2 and all(isinstance(n, (int, float)) for n in item)):
                raise forms.ValidationError("Chaque entrée doit être [rang, prix_centimes].")
        return value

    def clean(self):
        data = super().clean()
        vf = data.get("effective_from")
        vu = data.get("effective_until")
        if vf and vu and vf > vu:
            self.add_error("effective_until", "La date de fin doit être après la date de début.")
        return data
