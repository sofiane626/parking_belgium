"""
Vues citoyen — flux de paiement réel sécurisé + bouton simulation côté.

Routes (cf. urls.py) :
- ``permit_pay_start``    : GET récap + POST initiate (pending)
- ``payment_process``      : GET page confirmer/annuler avec token signé
- ``payment_confirm``      : POST signed_token → succeeded → mark_paid + email
- ``payment_cancel``       : POST → cancelled
- ``payment_simulate``     : POST → succeeded immédiat (staff/DEBUG only)
"""
from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.permits.models import Permit, PermitStatus

from . import card_gateway, stripe_gateway
from .card_gateway import CardError, CardInput
from .models import Payment, PaymentStatus
from .services import (
    PaymentError,
    can_simulate,
    cancel_payment,
    confirm_payment,
    initiate_payment,
    sign_reference,
    simulate_payment_success,
)


def _client_ip(request: HttpRequest) -> str | None:
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _own_permit(request: HttpRequest, pk: int) -> Permit:
    return get_object_or_404(Permit, pk=pk, citizen=request.user)


@login_required
def permit_pay_start(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Page récapitulative + initiation du paiement.

    GET  : affiche montant + bouton "Procéder au paiement" + bouton "Simuler"
           (ce dernier visible uniquement si ``can_simulate``).
    POST : crée un Payment PENDING et redirige vers la page de confirmation
           signée.
    """
    permit = _own_permit(request, pk)

    if request.method == "GET":
        live_payment = Payment.objects.filter(
            permit=permit, status__in=[PaymentStatus.PENDING, PaymentStatus.PROCESSING],
        ).first()
        return render(
            request,
            "payments/start.html",
            {
                "permit": permit,
                "live_payment": live_payment,
                "can_simulate": can_simulate(request.user),
                "stripe_enabled": stripe_gateway.is_enabled(),
                # Carte interne : toujours activée (aucun compte externe requis).
                "card_enabled": True,
            },
        )

    try:
        payment = initiate_payment(permit, by_user=request.user, ip=_client_ip(request))
    except PaymentError as exc:
        messages.error(request, str(exc))
        return redirect("permits:detail", pk=permit.pk)

    return redirect("payments:process", reference=payment.reference)


@login_required
def payment_process(request: HttpRequest, reference: str) -> HttpResponse:
    """
    Page de confirmation. Le token signé est posé dans le formulaire et n'est
    valide que 15 minutes — empêche replay et copie hors-bande.
    """
    payment = get_object_or_404(Payment, reference=reference, citizen=request.user)
    if payment.status == PaymentStatus.SUCCEEDED:
        return redirect("permits:detail", pk=payment.permit_id)
    if payment.status not in {PaymentStatus.PENDING, PaymentStatus.PROCESSING}:
        messages.info(request, _("Ce paiement n'est plus actif."))
        return redirect("permits:detail", pk=payment.permit_id)

    return render(
        request,
        "payments/process.html",
        {
            "payment": payment,
            "permit": payment.permit,
            "signed_token": sign_reference(payment.reference),
        },
    )


@login_required
def payment_confirm(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    signed = (request.POST.get("signed_token") or "").strip()
    if not signed:
        messages.error(request, _("Jeton de paiement manquant."))
        return redirect("permits:list")

    try:
        payment = confirm_payment(
            signed_reference=signed, by_user=request.user, ip=_client_ip(request)
        )
    except PaymentError as exc:
        messages.error(request, str(exc))
        return redirect("permits:list")
    except PermissionDenied:
        messages.error(request, _("Action non autorisée."))
        return redirect("permits:list")

    messages.success(request, _("Paiement validé. Votre carte est active. Un email de confirmation vous a été envoyé."))
    return redirect("permits:detail", pk=payment.permit_id)


@login_required
def payment_cancel(request: HttpRequest, reference: str) -> HttpResponse:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    payment = get_object_or_404(Payment, reference=reference, citizen=request.user)
    try:
        cancel_payment(payment, by_user=request.user)
    except PaymentError as exc:
        messages.error(request, str(exc))
    else:
        messages.info(request, _("Paiement annulé."))
    return redirect("permits:detail", pk=payment.permit_id)


@login_required
def payment_simulate(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Bouton "Simuler le paiement" — réservé staff/back-office (ou DEBUG=True
    pour développement local). Court-circuite la confirmation signée et
    valide le paiement immédiatement.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    if not can_simulate(request.user):
        raise PermissionDenied

    permit = _own_permit(request, pk)
    try:
        simulate_payment_success(permit, by_user=request.user, ip=_client_ip(request))
    except PaymentError as exc:
        messages.error(request, str(exc))
        return redirect("permits:detail", pk=permit.pk)

    messages.success(request, _("[TEST] Paiement simulé avec succès. Carte activée + email envoyé."))
    return redirect("permits:detail", pk=permit.pk)


# ----- Stripe Checkout (real flow, test mode) -------------------------------

@login_required
@require_POST
def stripe_checkout(request: HttpRequest, pk: int) -> HttpResponse:
    """Crée la session Stripe et redirige vers la page de paiement hostée."""
    permit = _own_permit(request, pk)
    if not stripe_gateway.is_enabled():
        messages.error(request, _("Le paiement par carte n'est pas configuré sur cette instance."))
        return redirect("payments:start", pk=permit.pk)
    try:
        _payment, url = stripe_gateway.create_checkout_session(
            permit, by_user=request.user, request=request, ip=_client_ip(request),
        )
    except (stripe_gateway.StripeError, stripe_gateway.StripeNotConfigured) as exc:
        messages.error(request, str(exc))
        return redirect("payments:start", pk=permit.pk)
    return redirect(url)


@login_required
def stripe_success(request: HttpRequest) -> HttpResponse:
    """
    Redirection retour Stripe (success_url). Confirme côté serveur via API
    pour ne pas faire confiance aux paramètres URL — le webhook reste la
    source de vérité ultime mais cette confirmation immédiate améliore l'UX.
    """
    session_id = request.GET.get("stripe_session", "")
    reference = request.GET.get("reference", "")

    payment = Payment.objects.filter(reference=reference, citizen=request.user).first()
    if payment is None:
        messages.error(request, _("Paiement introuvable."))
        return redirect("permits:list")

    try:
        stripe_gateway.confirm_from_session_id(
            session_id, by_user=request.user, ip=_client_ip(request),
        )
    except stripe_gateway.StripeError as exc:
        # Le webhook finalisera peut-être plus tard — affichage neutre.
        messages.warning(
            request,
            _("Le paiement est en cours de validation par Stripe. La carte sera "
              "activée dès confirmation. (%(detail)s)") % {"detail": exc},
        )
        return redirect("permits:detail", pk=payment.permit_id)

    messages.success(request, _("Paiement validé. Votre carte est active. Email de confirmation envoyé."))
    return redirect("permits:detail", pk=payment.permit_id)


@login_required
def stripe_cancel(request: HttpRequest) -> HttpResponse:
    reference = request.GET.get("reference", "")
    payment = stripe_gateway.cancel_session(reference, by_user=request.user)
    if payment is not None:
        messages.info(request, _("Paiement annulé. Vous pouvez reprendre quand vous voulez."))
        return redirect("permits:detail", pk=payment.permit_id)
    return redirect("permits:list")


# ----- Card (formulaire interne avec validation Luhn) -----------------------

@login_required
def card_form(request: HttpRequest, pk: int) -> HttpResponse:
    """
    Formulaire de paiement par carte. GET = affiche le form. POST = valide
    le PAN/Luhn/expiry/CVC, traite le paiement, active la carte. Le PAN n'est
    jamais persisté (seuls brand + last4 le sont).
    """
    permit = _own_permit(request, pk)

    if request.method == "GET":
        try:
            payment = card_gateway.initiate_card_payment(
                permit, by_user=request.user, ip=_client_ip(request),
            )
        except CardError as exc:
            messages.error(request, str(exc))
            return redirect("permits:detail", pk=permit.pk)
        return render(request, "payments/card_form.html", {
            "permit": permit, "payment": payment,
        })

    # POST : on récupère le payment live et traite la saisie.
    payment = Payment.objects.filter(
        permit=permit, citizen=request.user,
        status__in=[PaymentStatus.PENDING, PaymentStatus.PROCESSING],
        method="card",
    ).order_by("-initiated_at").first()
    if payment is None:
        messages.error(request, _("Aucun paiement carte en cours — recommencez."))
        return redirect("payments:start", pk=permit.pk)

    card = CardInput(
        number=request.POST.get("card_number", ""),
        holder=request.POST.get("card_holder", ""),
        exp_month=int(request.POST.get("exp_month") or 0),
        exp_year=int(request.POST.get("exp_year") or 0),
        cvc=request.POST.get("cvc", ""),
    )
    try:
        card_gateway.process_card_payment(
            payment, card, by_user=request.user, ip=_client_ip(request),
        )
    except CardError as exc:
        messages.error(request, str(exc))
        return render(request, "payments/card_form.html", {
            "permit": permit, "payment": payment,
            "form_values": {
                "card_holder": card.holder,
                "exp_month": card.exp_month or "",
                "exp_year": card.exp_year or "",
            },
        })

    messages.success(
        request,
        _("Paiement validé (carte %(brand)s •••• %(last4)s). Carte de stationnement activée.") % {
            "brand": payment.card_brand.upper() or "—",
            "last4": payment.card_last4,
        },
    )
    return redirect("permits:detail", pk=permit.pk)


@csrf_exempt
@require_POST
def stripe_webhook(request: HttpRequest) -> HttpResponse:
    """
    Webhook Stripe — la signature est vérifiée via STRIPE_WEBHOOK_SECRET.
    En local, lance ``stripe listen --forward-to localhost:8000/me/payments/stripe/webhook/``
    et copie le whsec_… affiché dans .env.
    """
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    try:
        event = stripe_gateway.verify_webhook(payload, sig_header)
    except stripe_gateway.StripeNotConfigured:
        return JsonResponse({"detail": "webhook secret not configured"}, status=503)
    except stripe_gateway.StripeError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)
    stripe_gateway.handle_webhook_event(event)
    return JsonResponse({"received": True})
