from django.urls import path

from . import views

urlpatterns = [
    path("permit/<int:pk>/start/", views.permit_pay_start, name="start"),
    path("permit/<int:pk>/simulate/", views.payment_simulate, name="simulate"),

    # Carte bancaire (formulaire interne, validation Luhn)
    path("permit/<int:pk>/card/", views.card_form, name="card_form"),

    # Stripe Checkout (real payment in test mode)
    path("permit/<int:pk>/stripe/", views.stripe_checkout, name="stripe_checkout"),
    path("stripe/success/", views.stripe_success, name="stripe_success"),
    path("stripe/cancel/", views.stripe_cancel, name="stripe_cancel"),
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),

    # Internal-free flow (kept as fallback / secondary path)
    path("confirm/", views.payment_confirm, name="confirm"),
    path("ref/<str:reference>/", views.payment_process, name="process"),
    path("ref/<str:reference>/cancel/", views.payment_cancel, name="cancel"),
]
