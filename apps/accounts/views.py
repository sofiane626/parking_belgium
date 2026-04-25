from django.contrib.auth import login
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView

from .forms import CitizenRegistrationForm


class RegisterView(CreateView):
    form_class = CitizenRegistrationForm
    template_name = "registration/register.html"
    success_url = reverse_lazy("core:post_login_redirect")

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("core:post_login_redirect")
        return super().dispatch(request, *args, **kwargs)
