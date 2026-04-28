"""
État du parcours citoyen : où en est-il, quelle est la prochaine action ?

Consommé par le dashboard citoyen pour afficher un stepper progressif et
mettre en évidence le bon CTA selon la situation. La logique est centralisée
ici pour rester testable indépendamment du template.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from apps.citizens.models import Address, CitizenProfile
from apps.permits.models import Permit, PermitStatus

# Ordre des étapes du parcours principal (création de la première carte
# riverain). Toute progression au-delà boucle sur "carte active".
STEP_PROFILE      = "profile"
STEP_VEHICLE      = "vehicle"
STEP_REQUEST      = "request"
STEP_REVIEW       = "review"
STEP_PAYMENT      = "payment"
STEP_ACTIVE       = "active"
STEP_SUSPENDED    = "suspended"

STATE_DONE     = "done"
STATE_CURRENT  = "current"
STATE_PENDING  = "pending"
STATE_BLOCKED  = "blocked"


@dataclass
class JourneyStep:
    key: str
    label: str
    state: str  # done / current / pending / blocked
    icon: str   # caractère unicode affiché dans le bullet
    detail: str = ""


@dataclass
class CitizenJourney:
    steps: list[JourneyStep]
    cta_label: str = ""
    cta_url: str = ""
    cta_style: str = "primary"  # primary / signal / outline / muted
    cta_help: str = ""
    headline: str = ""
    badge: str = ""              # texte d'un badge contextuel (ex: "Suspendue")
    badge_color: str = "slate"   # slate / brand / signal / red / emerald
    permit_focus: Optional[Permit] = None
    pending_address_request: object = None


def compute_journey(
    user,
    *,
    profile: CitizenProfile,
    address: Optional[Address],
    vehicles_qs,
    permits_qs,
    pending_address_request=None,
) -> CitizenJourney:
    """
    Renvoie l'état du parcours pour un citoyen.

    On regarde :
    1. profil rempli ?            → STEP_PROFILE
    2. au moins un véhicule ?     → STEP_VEHICLE
    3. au moins une demande ?     → STEP_REQUEST
    4. carte en revue manuelle ?  → STEP_REVIEW
    5. carte en attente paiement ?→ STEP_PAYMENT
    6. carte active ?             → STEP_ACTIVE
    7. carte suspendue ?          → STEP_SUSPENDED (override prioritaire)

    Le CTA et le headline sont calés sur la prochaine étape qui demande
    une action du citoyen.
    """
    from django.urls import reverse

    has_profile = bool(profile and profile.phone)
    has_address = address is not None
    active_vehicles = [v for v in vehicles_qs if not v.is_archived]
    has_vehicle = len(active_vehicles) > 0

    # Permits non terminaux/refusés/annulés (en cours d'usage)
    active_permits = [
        p for p in permits_qs
        if p.status not in {
            PermitStatus.CANCELLED, PermitStatus.EXPIRED,
            PermitStatus.REFUSED, PermitStatus.DRAFT,
        }
    ]
    suspended = next((p for p in active_permits if p.status == PermitStatus.SUSPENDED), None)
    awaiting_payment = next((p for p in active_permits if p.status == PermitStatus.AWAITING_PAYMENT), None)
    in_review = next((p for p in active_permits if p.status == PermitStatus.MANUAL_REVIEW), None)
    submitted = next((p for p in active_permits if p.status == PermitStatus.SUBMITTED), None)
    active = next((p for p in active_permits if p.status == PermitStatus.ACTIVE), None)

    # ---- état des étapes (toutes affichées, l'icône reflète l'état)
    steps = [
        JourneyStep(STEP_PROFILE, "Profil",
                    STATE_DONE if has_profile and has_address else STATE_CURRENT,
                    "1"),
        JourneyStep(STEP_VEHICLE, "Véhicule",
                    STATE_DONE if has_vehicle else (STATE_CURRENT if has_profile else STATE_PENDING),
                    "2"),
        JourneyStep(STEP_REQUEST, "Demande",
                    STATE_DONE if active_permits else (STATE_CURRENT if has_vehicle else STATE_PENDING),
                    "3"),
        JourneyStep(STEP_PAYMENT, "Paiement",
                    STATE_CURRENT if awaiting_payment else
                    (STATE_DONE if active else STATE_PENDING),
                    "4"),
        JourneyStep(STEP_ACTIVE, "Carte active",
                    STATE_DONE if active else
                    (STATE_BLOCKED if suspended else STATE_PENDING),
                    "✓" if active else "5"),
    ]

    # ---- CTA contextuel : on cale sur la prochaine action attendue
    j = CitizenJourney(steps=steps, pending_address_request=pending_address_request)

    if suspended:
        j.headline = "Carte suspendue"
        j.badge = "Suspendue"
        j.badge_color = "red"
        j.permit_focus = suspended
        j.cta_label = "Voir le détail de la carte"
        j.cta_url = reverse("permits:detail", args=[suspended.pk])
        j.cta_style = "outline"
        j.cta_help = "Une suspension fait suite à un changement d'adresse, de plaque ou à un remboursement. Contactez votre commune en cas d'erreur."
        return j

    if awaiting_payment:
        j.headline = "Paiement requis pour activer la carte"
        j.badge = "À payer"
        j.badge_color = "signal"
        j.permit_focus = awaiting_payment
        j.cta_label = "Payer maintenant"
        j.cta_url = reverse("payments:start", args=[awaiting_payment.pk])
        j.cta_style = "signal"
        j.cta_help = "Paiement par carte bancaire via Stripe."
        return j

    if in_review or submitted:
        permit = in_review or submitted
        j.headline = "Demande en cours d'examen"
        j.badge = "En revue"
        j.badge_color = "brand"
        j.permit_focus = permit
        j.cta_label = "Voir l'état de la demande"
        j.cta_url = reverse("permits:detail", args=[permit.pk])
        j.cta_style = "outline"
        j.cta_help = "Validation par un agent communal sous 48 h ouvrées."
        return j

    if active:
        j.headline = "Carte active"
        j.badge = "Active"
        j.badge_color = "emerald"
        j.permit_focus = active
        j.cta_label = "Voir ma carte"
        j.cta_url = reverse("permits:detail", args=[active.pk])
        j.cta_style = "outline"
        j.cta_help = "Une carte visiteur peut être créée pour accueillir des invités."
        return j

    # Pas encore de carte — on guide vers l'action suivante
    if not has_profile or not has_address:
        j.headline = "Profil à compléter"
        j.cta_label = "Compléter mon profil"
        j.cta_url = reverse("citizens:profile_edit")
        j.cta_style = "primary"
        j.cta_help = "Téléphone, date de naissance et adresse principale requis pour demander une carte."
    elif not has_vehicle:
        j.headline = "Aucun véhicule enregistré"
        j.cta_label = "Ajouter un véhicule"
        j.cta_url = reverse("vehicles:create")
        j.cta_style = "primary"
        j.cta_help = "Le certificat d'immatriculation est requis (PDF, JPG ou PNG)."
    else:
        # On a profil + véhicule, plus qu'à demander la carte. On pointe
        # vers le wizard React qui guide en 5 étapes (incluant l'aperçu de
        # la zone d'attribution avant de soumettre).
        first_vehicle = active_vehicles[0]
        j.headline = "Demande de carte de stationnement"
        j.cta_label = "Demander ma carte riverain"
        j.cta_url = reverse("permits:wizard", args=[first_vehicle.pk])
        j.cta_style = "primary"
        j.cta_help = "Demande guidée en 5 étapes : zone d'attribution, tarif et paiement."

    return j
