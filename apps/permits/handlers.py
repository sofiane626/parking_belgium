"""
Cross-app subscribers that keep card lifecycle in sync with citizen events:

- Address change → suspend the citizen's active resident cards.
- Vehicle plate change → suspend the active card linked to that vehicle.

These are wired in :class:`apps.permits.apps.PermitsConfig.ready`.
"""
from django.db.models.signals import Signal
from django.dispatch import receiver

from apps.citizens.models import Address
from apps.citizens.signals import address_changed
from apps.vehicles.models import Vehicle
from apps.vehicles.signals import vehicle_plate_changed

from .services import (
    suspend_active_permits_for_citizen,
    suspend_active_permits_for_vehicle,
)


@receiver(address_changed, sender=Address)
def on_address_changed(sender, *, profile, address, created, previous, user, **kwargs):
    if created:
        # Initial registration creates the address — there are no cards yet.
        return
    suspend_active_permits_for_citizen(
        profile.user,
        reason=f"Adresse modifiée le {address.updated_at:%Y-%m-%d}.",
    )


@receiver(vehicle_plate_changed, sender=Vehicle)
def on_vehicle_plate_changed(sender, *, vehicle, old_plate, new_plate, agent, **kwargs):
    suspend_active_permits_for_vehicle(
        vehicle,
        reason=f"Plaque changée {old_plate} → {new_plate}.",
    )
