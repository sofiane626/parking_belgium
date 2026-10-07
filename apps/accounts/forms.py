from django import forms
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.citizens.models import Address, CitizenProfile
from apps.citizens.services import upsert_address
from apps.core.form_styles import apply_input_styling
from apps.core.models import Commune

from .models import Role, User


class CitizenRegistrationForm(UserCreationForm):
    """
    Self-service registration. Captures the User credentials, the civic profile
    (phone, date of birth, national register number) and the principal address
    in a single atomic submission. The role is forced to ``citizen`` — back-office
    roles are never granted by client input.
    """

    # CitizenProfile fields
    phone = forms.CharField(label=_("téléphone"), max_length=30)
    date_of_birth = forms.DateField(
        label=_("date de naissance"),
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    national_number = forms.CharField(label=_("numéro de registre national"), max_length=15)

    # Address fields
    street = forms.CharField(label=_("rue"), max_length=200)
    number = forms.CharField(label=_("numéro"), max_length=20)
    box = forms.CharField(label=_("boîte"), max_length=20, required=False)
    postal_code = forms.CharField(
        label=_("code postal"), max_length=10,
        help_text=_("La commune est déduite automatiquement à partir du code postal."),
    )
    # Commune n'est plus saisi : il est déduit en clean() à partir du CP. Le
    # template affiche un champ en lecture seule rempli en JS pour le retour
    # visuel, mais la valeur retenue côté serveur est toujours celle calculée
    # depuis postal_code → on ignore donc tout input commune envoyé par le
    # client (anti-falsification : un user ne peut pas se réclamer d'une autre
    # commune que celle de son code postal).
    country = forms.CharField(label=_("pays"), max_length=2, initial="BE")

    # RGPD — consentement éclairé obligatoire pour pouvoir enregistrer le compte.
    accept_privacy = forms.BooleanField(
        required=True,
        label=_("J'ai lu et j'accepte la politique de confidentialité et les conditions d'utilisation."),
        error_messages={"required": _("Vous devez accepter pour créer un compte.")},
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "first_name", "last_name")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make the User-side niceties non-optional — registration without a
        # name/email is a UX trap, not a privacy gain.
        for name in ("email", "first_name", "last_name"):
            self.fields[name].required = True
        apply_input_styling(self)

    def clean_username(self):
        from .services import ANONYMOUS_USERNAME_PREFIX
        username = self.cleaned_data.get("username", "")
        if username.lower().startswith(ANONYMOUS_USERNAME_PREFIX):
            raise forms.ValidationError(
                _("Ce nom d'utilisateur est réservé. Choisissez-en un autre.")
            )
        return username

    def clean(self):
        cleaned = super().clean()
        pc = (cleaned.get("postal_code") or "").strip()
        if pc:
            commune = Commune.for_postal_code(pc)
            if commune is None:
                self.add_error(
                    "postal_code",
                    _("Code postal non reconnu pour la Région bruxelloise. "
                      "Vérifiez le code (1000–1299)."),
                )
            else:
                cleaned["commune"] = commune
        return cleaned

    @transaction.atomic
    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        user.role = Role.CITIZEN
        # Snapshot de l'instant exact où l'utilisateur a coché la case.
        # Stocker des deux côtés (privacy + terms) parce que l'unique case
        # couvre les deux documents — si on les sépare un jour, le code
        # consommateur reste correct.
        now = timezone.now()
        user.accepted_privacy_at = now
        user.accepted_terms_at = now
        if not commit:
            return user
        user.save()
        profile = CitizenProfile.objects.create(
            user=user,
            phone=self.cleaned_data["phone"],
            date_of_birth=self.cleaned_data["date_of_birth"],
            national_number=self.cleaned_data["national_number"],
        )
        upsert_address(
            profile,
            user=user,
            street=self.cleaned_data["street"],
            number=self.cleaned_data["number"],
            box=self.cleaned_data.get("box", ""),
            postal_code=self.cleaned_data["postal_code"],
            commune=self.cleaned_data["commune"],
            country=self.cleaned_data["country"],
        )
        return user


class AccountDeletionForm(forms.Form):
    """
    Confirmation de la désinscription : le citoyen ressaisit son mot de passe.
    La vérification elle-même est faite par le service
    ``delete_citizen_account``.
    """

    password = forms.CharField(
        label=_("Mot de passe actuel"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_input_styling(self)


class LockoutAuthenticationMixin:
    """
    Refuse la connexion d'un identifiant verrouillé, même avec le bon mot de
    passe, et signale chaque échec au service anti brute-force. Toute la
    logique (compteur, seuil, durée) est dans ``apps.accounts.services``.
    """

    def clean(self):
        from .services import is_login_locked, lockout_message, register_login_failure

        username = self.cleaned_data.get("username")
        if username and is_login_locked(username):
            raise forms.ValidationError(lockout_message(), code="locked")
        try:
            return super().clean()
        except forms.ValidationError:
            if username and register_login_failure(username, request=self.request):
                raise forms.ValidationError(lockout_message(), code="locked")
            raise


class LoginForm(LockoutAuthenticationMixin, AuthenticationForm):
    """Formulaire de connexion du site (accounts:login)."""


class AdminLoginForm(LockoutAuthenticationMixin, AdminAuthenticationForm):
    """Formulaire de connexion de l'admin Django (/admin/), même protection."""
