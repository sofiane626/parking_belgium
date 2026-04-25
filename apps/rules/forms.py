from django import forms
from django.utils.translation import gettext_lazy as _

from apps.core.form_styles import apply_input_styling

from .models import PolygonRule, RuleAction


class PolygonRuleForm(forms.ModelForm):
    """Back-office form to create/edit a PolygonRule on a given polygon."""

    class Meta:
        model = PolygonRule
        fields = [
            "permit_type",
            "action_type",
            "target_zone_code",
            "priority",
            "valid_from",
            "valid_until",
            "is_active",
            "description",
        ]
        widgets = {
            "valid_from": forms.DateInput(attrs={"type": "date"}),
            "valid_until": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_input_styling(self)

    def clean(self):
        data = super().clean()
        action = data.get("action_type")
        target = (data.get("target_zone_code") or "").strip()
        if action in (RuleAction.ADD_ZONE, RuleAction.REPLACE_MAIN_ZONE) and not target:
            self.add_error("target_zone_code", _("Requis pour cette action."))
        if action in (RuleAction.MANUAL_REVIEW, RuleAction.DENY):
            data["target_zone_code"] = ""  # ignored for these actions
        vf = data.get("valid_from")
        vu = data.get("valid_until")
        if vf and vu and vf > vu:
            self.add_error("valid_until", _("La date de fin doit être après la date de début."))
        return data
