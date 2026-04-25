"""
Signals emitted by the citizens domain.

``address_changed`` is fired whenever a citizen's principal address is updated.
Other apps (notably ``permits``) subscribe to it to suspend active cards — the
spec says cards must be suspended on address change. This module is the
contract; the actual subscriber lands when the permits app is built.
"""
import django.dispatch

address_changed = django.dispatch.Signal()
