"""
Business services for the citizens domain.

Address mutations are *only* performed here. Self-service edits go through a
:class:`AddressChangeRequest` workflow because the spec requires resident-card
suspension on every address change — letting a citizen mutate their address
directly would bypass that contract.
"""
from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from .models import Address, AddressChangeRequest, CitizenProfile, RequestStatus
from .signals import address_changed


# ----- profile (no card impact) ---------------------------------------------

def get_or_create_profile(user) -> CitizenProfile:
    profile, _ = CitizenProfile.objects.get_or_create(user=user)
    return profile


def update_profile(profile: CitizenProfile, **fields) -> CitizenProfile:
    for k, v in fields.items():
        setattr(profile, k, v)
    profile.save()
    return profile


# ----- address writes (only called by trusted callers) ----------------------

@transaction.atomic
def upsert_address(profile: CitizenProfile, *, user, **fields) -> Address:
    """
    Create or update the principal address. Always emits ``address_changed``
    so downstream apps (permits) can react.

    Callers: registration form (initial creation) and
    :func:`approve_address_change` (agent-driven update). Never called from a
    citizen-facing edit endpoint.
    """
    snapshot_before: dict | None = None
    address, created = Address.objects.get_or_create(profile=profile, defaults=fields)

    if not created:
        snapshot_before = {f: getattr(address, f) for f in fields}
        for k, v in fields.items():
            setattr(address, k, v)
        address.location = None  # invalidate the cached geocoded point
        address.save()

    address_changed.send(
        sender=Address,
        profile=profile,
        address=address,
        created=created,
        previous=snapshot_before,
        user=user,
    )
    return address


# ----- address change request workflow --------------------------------------

ADDRESS_REQUEST_FIELDS = ("street", "number", "box", "postal_code", "commune", "country")


def submit_address_change(profile: CitizenProfile, *, user, **fields) -> AddressChangeRequest:
    """Create a pending request. Caller must own the profile."""
    if profile.user_id != user.pk:
        raise PermissionDenied
    return AddressChangeRequest.objects.create(profile=profile, **fields)


@transaction.atomic
def approve_address_change(req: AddressChangeRequest, *, agent, notes: str = "") -> AddressChangeRequest:
    """
    Apply the pending request to the underlying Address (which fires
    ``address_changed``) and stamp the decision.
    """
    if req.status != RequestStatus.PENDING:
        raise ValueError(f"Cannot approve request in status {req.status}")
    upsert_address(
        req.profile,
        user=agent,
        **{f: getattr(req, f) for f in ADDRESS_REQUEST_FIELDS},
    )
    req.status = RequestStatus.APPROVED
    req.decided_at = timezone.now()
    req.decided_by = agent
    req.decision_notes = notes
    req.save()
    return req


def reject_address_change(req: AddressChangeRequest, *, agent, notes: str) -> AddressChangeRequest:
    if req.status != RequestStatus.PENDING:
        raise ValueError(f"Cannot reject request in status {req.status}")
    req.status = RequestStatus.REJECTED
    req.decided_at = timezone.now()
    req.decided_by = agent
    req.decision_notes = notes
    req.save()
    return req


def cancel_address_change(req: AddressChangeRequest, *, user) -> AddressChangeRequest:
    """Citizen cancels their own pending request before agent review."""
    if req.profile.user_id != user.pk:
        raise PermissionDenied
    if req.status != RequestStatus.PENDING:
        raise ValueError(f"Cannot cancel request in status {req.status}")
    req.status = RequestStatus.CANCELLED
    req.decided_at = timezone.now()
    req.save()
    return req
