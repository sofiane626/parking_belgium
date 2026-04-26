"""
Signaux d'audit "passifs" — pour les modèles dont les modifications ne
passent pas systématiquement par un service explicite (PolygonRule modifié
depuis l'admin Django ou une vue dashboard simple).

Pour les flux qui ont déjà un service métier (Permit, Payment, User,
Vehicle, Token), on log directement depuis le service plutôt qu'ici — on
préserve le contexte (actor, raison, IP) qu'un signal post_save ne voit pas.
"""
from __future__ import annotations

from django.contrib.auth.signals import user_login_failed
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.rules.models import PolygonRule
from apps.permits.models import CommunePermitPolicy, PermitConfig

from .services import AuditAction, extract_request_ip, log as audit_log


@receiver(user_login_failed)
def _on_login_failed(sender, credentials, request=None, **kwargs):
    audit_log(
        AuditAction.AUTH_FAILED,
        actor=None,
        ip=extract_request_ip(request),
        payload={"context": {"username": credentials.get("username", "")}},
    )


@receiver(post_save, sender=PolygonRule)
def _on_polygon_rule_changed(sender, instance: PolygonRule, created: bool, **kwargs):
    audit_log(
        AuditAction.POLYGON_RULE_CHANGED,
        actor=getattr(instance, "created_by", None),
        target=instance,
        payload={"context": {
            "created": created,
            "polygon_id": instance.polygon_id,
            "permit_type": instance.permit_type,
            "action_type": instance.action_type,
            "target_zone_code": instance.target_zone_code,
            "is_active": instance.is_active,
        }},
    )


@receiver(post_delete, sender=PolygonRule)
def _on_polygon_rule_deleted(sender, instance: PolygonRule, **kwargs):
    audit_log(
        AuditAction.POLYGON_RULE_CHANGED,
        actor=None, target=instance,
        payload={"context": {"deleted": True, "polygon_id": instance.polygon_id}},
    )


@receiver(post_save, sender=CommunePermitPolicy)
def _on_policy_changed(sender, instance: CommunePermitPolicy, created: bool, **kwargs):
    audit_log(
        AuditAction.POLICY_CHANGED,
        actor=getattr(instance, "updated_by", None),
        target=instance,
        payload={"context": {
            "created": created,
            "commune_id": instance.commune_id,
            "permit_type": instance.permit_type,
            "is_enabled": instance.is_enabled,
            "validity_days": instance.validity_days,
            "price_strategy": instance.price_strategy,
            "price_fixed_cents": instance.price_fixed_cents,
        }},
    )


@receiver(post_save, sender=PermitConfig)
def _on_permit_config_changed(sender, instance: PermitConfig, created: bool, **kwargs):
    audit_log(
        AuditAction.PERMIT_CONFIG_CHANGED,
        actor=getattr(instance, "updated_by", None),
        target=instance,
        payload={"context": {
            "created": created,
            "resident_price_cents": instance.resident_price_cents,
            "visitor_price_cents": instance.visitor_price_cents,
            "professional_price_cents": instance.professional_price_cents,
            "max_vehicles_per_citizen": instance.max_vehicles_per_citizen,
            "visitor_codes_per_year": instance.visitor_codes_per_year,
        }},
    )
