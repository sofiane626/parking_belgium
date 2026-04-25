"""
Signals emitted by the vehicles domain.

``vehicle_plate_changed`` fires when an agent approves a
:class:`PlateChangeRequest`. The permits app subscribes to suspend resident
cards linked to the vehicle, since the plate change invalidates them.
"""
import django.dispatch

vehicle_plate_changed = django.dispatch.Signal()
