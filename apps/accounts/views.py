from django.conf import settings
from django.contrib.auth import login
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView
from django.views.i18n import set_language as django_set_language

from .forms import CitizenRegistrationForm


class RegisterView(CreateView):
    form_class = CitizenRegistrationForm
    template_name = "registration/register.html"
    success_url = reverse_lazy("core:post_login_redirect")

    def form_valid(self, form):
        response = super().form_valid(form)
        # La langue active au moment du register (préfixe URL ou cookie) devient
        # la langue préférée du compte : citoyen qui s'inscrit sur /nl/register/
        # recevra ses emails en NL par défaut.
        from django.utils import translation as _trans
        valid = {c for c, _n in settings.LANGUAGES}
        current = _trans.get_language()
        if current in valid and self.object.preferred_language != current:
            self.object.preferred_language = current
            self.object.save(update_fields=["preferred_language"])
        login(self.request, self.object)
        return response

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("core:post_login_redirect")
        return super().dispatch(request, *args, **kwargs)


def set_language_persistent(request):
    """
    Wrapper autour de la vue ``django.views.i18n.set_language`` qui persiste
    aussi le choix dans ``user.preferred_language`` pour les utilisateurs
    connectés. Permet aux emails transactionnels d'utiliser la bonne langue.
    """
    response = django_set_language(request)
    if request.method == "POST" and request.user.is_authenticated:
        chosen = request.POST.get("language") or ""
        valid_codes = {code for code, _name in settings.LANGUAGES}
        if chosen in valid_codes and request.user.preferred_language != chosen:
            request.user.preferred_language = chosen
            request.user.save(update_fields=["preferred_language"])
    return response
