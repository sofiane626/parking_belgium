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
        j.headline = "Votre carte est suspendue"
        j.badge = "Suspendue"
        j.badge_color = "red"
        j.permit_focus = suspended
        j.cta_label = "Voir le détail de la carte"
        j.cta_url = reverse("permits:detail", args=[suspended.pk])
        j.cta_style = "outline"
        j.cta_help = "Une suspension intervient typiquement après un changement d'adresse, de plaque ou un remboursement. Contactez votre commune si vous pensez qu'il s'agit d'une erreur."
        return j

    if awaiting_payment:
        j.headline = "Finalisez votre paiement pour activer votre carte"
        j.badge = "À payer"
        j.badge_color = "signal"
        j.permit_focus = awaiting_payment
        j.cta_label = "Payer maintenant"
        j.cta_url = reverse("payments:start", args=[awaiting_payment.pk])
        j.cta_style = "signal"
        j.cta_help = "Paiement sécurisé via Stripe (carte bancaire) ou simulation pour les tests."
        return j

    if in_review or submitted:
        permit = in_review or submitted
        j.headline = "Votre demande est en cours d'examen"
        j.badge = "En revue"
        j.badge_color = "brand"
        j.permit_focus = permit
        j.cta_label = "Voir l'état de la demande"
        j.cta_url = reverse("permits:detail", args=[permit.pk])
        j.cta_style = "outline"
        j.cta_help = "Un agent communal va valider votre demande sous 48 h ouvrées."
        return j

    if active:
        j.headline = "Votre carte est active"
        j.badge = "Active"
        j.badge_color = "emerald"
        j.permit_focus = active
        j.cta_label = "Voir ma carte"
        j.cta_url = reverse("permits:detail", args=[active.pk])
        j.cta_style = "outline"
        j.cta_help = "Vous pouvez aussi demander une carte visiteur pour accueillir des invités."
        return j

    # Pas encore de carte — on guide vers l'action suivante
    if not has_profile or not has_address:
        j.headline = "Complétez votre profil pour commencer"
        j.cta_label = "Compléter mon profil"
        j.cta_url = reverse("citizens:profile_edit")
        j.cta_style = "primary"
        j.cta_help = "Téléphone, date de naissance et adresse principale sont nécessaires pour demander une carte."
    elif not has_vehicle:
        j.headline = "Ajoutez votre véhicule pour pouvoir demander une carte"
        j.cta_label = "Ajouter mon premier véhicule"
        j.cta_url = reverse("vehicles:create")
        j.cta_style = "primary"
        j.cta_help = "Vous aurez besoin de votre certificat d'immatriculation (carte grise) au format PDF, JPG ou PNG."
    else:
        # On a profil + véhicule, plus qu'à demander la carte. On pointe
        # directement vers la création de carte (au lieu du détail véhicule
        # depuis lequel le citoyen devait deviner où trouver le bouton).
        first_vehicle = active_vehicles[0]
        j.headline = "Tout est prêt — demandez votre carte de stationnement"
        j.cta_label = "Demander ma carte riverain"
        j.cta_url = reverse("permits:create_for_vehicle", args=[first_vehicle.pk])
        j.cta_style = "primary"
        j.cta_help = "L'attribution est automatique pour la plupart des adresses bruxelloises. Le tarif dépend de votre commune."

    return j
