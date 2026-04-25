from django import forms
from django.utils.translation import gettext_lazy as _

from apps.core.form_styles import apply_input_styling

from .models import REGISTRATION_DOC_MAX_BYTES, PlateChangeRequest, Vehicle, normalize_plate


class VehicleCreateForm(forms.ModelForm):
    """Initial registration of a vehicle — plate + carte grise are mandatory."""

    class Meta:
        model = Vehicle
        fields = ["plate", "brand", "model", "color", "registration_document"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["registration_document"].required = True
        apply_input_styling(self)

    def clean_plate(self) -> str:
        value = normalize_plate(self.cleaned_data["plate"])
        if Vehicle.objects.filter(plate=value).exists():
            raise forms.ValidationError(_("Cette plaque est déjà enregistrée."))
        return value

    def clean_registration_document(self):
        f = self.cleaned_data.get("registration_document")
        if f and hasattr(f, "size") and f.size > REGISTRATION_DOC_MAX_BYTES:
            raise forms.ValidationError(_("Le fichier dépasse 5 Mo."))
        return f


class VehicleEditForm(forms.ModelForm):
    """
    Edit a vehicle's non-card-impacting fields. The plate is intentionally
    absent — it must go through :class:`PlateChangeRequest`.
    """

    class Meta:
        model = Vehicle
        fields = ["brand", "model", "color", "registration_document"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["registration_document"].required = False
        apply_input_styling(self)

    def clean_registration_document(self):
        f = self.cleaned_data.get("registration_document")
        if f and hasattr(f, "size") and f.size > REGISTRATION_DOC_MAX_BYTES:
            raise forms.ValidationError(_("Le fichier dépasse 5 Mo."))
        return f


class PlateChangeRequestForm(forms.ModelForm):
    """Citizen submits this; an agent then approves or rejects."""

    class Meta:
        model = PlateChangeRequest
        fields = ["new_plate", "new_registration_document", "reason"]
        widgets = {"reason": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, vehicle: Vehicle | None = None, **kwargs):
        self.vehicle = vehicle
        super().__init__(*args, **kwargs)
        apply_input_styling(self)

    def clean_new_plate(self) -> str:
        value = normalize_plate(self.cleaned_data["new_plate"])
        if self.vehicle and value == normalize_plate(self.vehicle.plate):
            raise forms.ValidationError(_("La nouvelle plaque doit être différente de l'actuelle."))
        clash = Vehicle.objects.filter(plate=value)
        if self.vehicle:
            clash = clash.exclude(pk=self.vehicle.pk)
        if clash.exists():
            raise forms.ValidationError(_("Cette plaque est déjà attribuée à un autre véhicule."))
        return value

    def clean_new_registration_document(self):
        f = self.cleaned_data.get("new_registration_document")
        if f and hasattr(f, "size") and f.size > REGISTRATION_DOC_MAX_BYTES:
            raise forms.ValidationError(_("Le fichier dépasse 5 Mo."))
        return f
