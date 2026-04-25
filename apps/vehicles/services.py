"""
Vehicle services. Plate mutation is *only* performed via the
:class:`PlateChangeRequest` workflow because changing a plate affects the
resident card linked to the vehicle.
"""
from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from .models import PlateChangeRequest, PlateChangeStatus, Vehicle, normalize_plate


# ----- vehicle CRUD (plate excluded from update_vehicle on purpose) ---------

def create_vehicle(*, owner, **fields) -> Vehicle:
    # Enforce the global per-citizen vehicle cap configured by admin (only
    # active vehicles count — archived ones are out of scope).
    from apps.permits.policies import enforce_max_vehicles_per_citizen
    enforce_max_vehicles_per_citizen(owner)
    return Vehicle.objects.create(owner=owner, **fields)


def update_vehicle(vehicle: Vehicle, **fields) -> Vehicle:
    """
    Update non-card-impacting fields (brand, model, color, registration_document).
    The plate is intentionally not allowed here — use the request workflow.
    """
    forbidden = {"plate"} & set(fields)
    if forbidden:
        raise ValueError(f"Plate change must go through PlateChangeRequest, not update_vehicle ({forbidden})")
    for k, v in fields.items():
        setattr(vehicle, k, v)
    vehicle.save()
    return vehicle


class VehicleError(Exception):
    """Soulevée pour blocages métier (ex: archivage refusé)."""


def archive_vehicle(vehicle: Vehicle, *, by_user, reason: str = "") -> Vehicle:
    """
    Soft-delete : marque le véhicule comme archivé. Refuse si une carte non
    terminale est encore liée (la suspendre ou l'annuler d'abord). L'historique
    des cartes reste intact (Permit.vehicle PROTECT).
    """
    if vehicle.owner_id != by_user.pk:
        raise PermissionDenied
    if vehicle.archived_at is not None:
        return vehicle  # idempotent

    from apps.permits.models import Permit, PermitStatus
    blocking = {
        PermitStatus.DRAFT, PermitStatus.SUBMITTED,
        PermitStatus.MANUAL_REVIEW, PermitStatus.AWAITING_PAYMENT,
        PermitStatus.ACTIVE, PermitStatus.SUSPENDED,
    }
    open_permits = Permit.objects.filter(vehicle=vehicle, status__in=blocking)
    if open_permits.exists():
        raise VehicleError(
            "Impossible d'archiver : ce véhicule a encore des cartes en cours "
            "ou actives. Annulez ou attendez l'expiration des cartes avant "
            "d'archiver. L'historique des cartes terminées reste consultable "
            "même après archivage."
        )

    # Pending plate-change requests must also be cleaned up.
    PlateChangeRequest.objects.filter(
        vehicle=vehicle, status=PlateChangeStatus.PENDING,
    ).update(
        status=PlateChangeStatus.CANCELLED, decided_at=timezone.now(),
        decision_notes="Annulée automatiquement : véhicule archivé.",
    )

    vehicle.archived_at = timezone.now()
    vehicle.archive_reason = reason
    vehicle.save(update_fields=["archived_at", "archive_reason", "updated_at"])
    return vehicle


def restore_vehicle(vehicle: Vehicle, *, by_user) -> Vehicle:
    if vehicle.owner_id != by_user.pk:
        raise PermissionDenied
    if vehicle.archived_at is None:
        return vehicle

    # Vérifier que la plaque n'a pas été reprise par un autre véhicule actif.
    clash = Vehicle.objects.filter(
        plate=vehicle.plate, archived_at__isnull=True,
    ).exclude(pk=vehicle.pk).exists()
    if clash:
        raise VehicleError(
            "Impossible de restaurer : la plaque est déjà utilisée par un "
            "autre véhicule actif."
        )
    vehicle.archived_at = None
    vehicle.archive_reason = ""
    vehicle.save(update_fields=["archived_at", "archive_reason", "updated_at"])
    return vehicle


# Backward-compat alias used by existing views/templates.
def delete_vehicle(vehicle: Vehicle, *, by_user=None, reason: str = "") -> Vehicle:
    """Alias historique vers ``archive_vehicle`` (soft-delete)."""
    return archive_vehicle(vehicle, by_user=by_user or vehicle.owner, reason=reason)


# ----- plate change request workflow ----------------------------------------

def submit_plate_change(
    vehicle: Vehicle,
    *,
    user,
    new_plate: str,
    new_registration_document=None,
    reason: str = "",
) -> PlateChangeRequest:
    if vehicle.owner_id != user.pk:
        raise PermissionDenied
    return PlateChangeRequest.objects.create(
        vehicle=vehicle,
        new_plate=new_plate,
        new_registration_document=new_registration_document,
        reason=reason,
    )


@transaction.atomic
def approve_plate_change(req: PlateChangeRequest, *, agent, notes: str = "") -> PlateChangeRequest:
    """
    Apply plate (and optional new registration document) to the vehicle, stamp
    the decision, and fire ``vehicle_plate_changed`` so the permits app can
    suspend the resident card linked to this vehicle.
    """
    if req.status != PlateChangeStatus.PENDING:
        raise ValueError(f"Cannot approve request in status {req.status}")

    new_plate = normalize_plate(req.new_plate)
    clash = Vehicle.objects.filter(plate=new_plate).exclude(pk=req.vehicle_id)
    if clash.exists():
        raise ValueError("Plate already taken on another vehicle")

    old_plate = req.vehicle.plate
    req.vehicle.plate = new_plate
    if req.new_registration_document:
        req.vehicle.registration_document = req.new_registration_document
    req.vehicle.save()

    req.status = PlateChangeStatus.APPROVED
    req.decided_at = timezone.now()
    req.decided_by = agent
    req.decision_notes = notes
    req.save()

    from .signals import vehicle_plate_changed
    vehicle_plate_changed.send(
        sender=Vehicle,
        vehicle=req.vehicle,
        old_plate=old_plate,
        new_plate=new_plate,
        agent=agent,
    )
    return req


def reject_plate_change(req: PlateChangeRequest, *, agent, notes: str) -> PlateChangeRequest:
    if req.status != PlateChangeStatus.PENDING:
        raise ValueError(f"Cannot reject request in status {req.status}")
    req.status = PlateChangeStatus.REJECTED
    req.decided_at = timezone.now()
    req.decided_by = agent
    req.decision_notes = notes
    req.save()
    return req


def cancel_plate_change(req: PlateChangeRequest, *, user) -> PlateChangeRequest:
    if req.vehicle.owner_id != user.pk:
        raise PermissionDenied
    if req.status != PlateChangeStatus.PENDING:
        raise ValueError(f"Cannot cancel request in status {req.status}")
    req.status = PlateChangeStatus.CANCELLED
    req.decided_at = timezone.now()
    req.save()
    return req
