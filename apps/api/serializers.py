"""
Serializers DRF.

Volontairement minimaux : l'API publique expose la *décision* (autorisé ou
non) plus quelques attributs strictement nécessaires à la traçabilité côté
client (numéro de carte, période de validité, type). Aucun PII inutile —
ni nom, ni adresse, ni email du citoyen.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.core.models import Commune
from apps.permits.models import Permit


class CommuneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Commune
        fields = ["niscode", "name_fr", "name_nl", "name_en", "postal_codes"]


class ZoneSerializer(serializers.Serializer):
    """
    Une "zone" exposée via l'API correspond à un ``zonecode`` de la version GIS
    active, dédupliqué sur (zonecode, commune). C'est cet identifiant qui sert
    de clé d'autorisation côté scan-car.
    """
    zonecode = serializers.CharField()
    commune_niscode = serializers.CharField(source="niscode")


class CheckRightSerializer(serializers.Serializer):
    """Réponse compacte pour l'endpoint ``/check-right/``."""
    authorized = serializers.BooleanField()
    plate = serializers.CharField()
    zone = serializers.CharField(allow_null=True, required=False)
    checked_at = serializers.DateTimeField()
    permit = serializers.SerializerMethodField()

    def get_permit(self, obj) -> dict | None:
        permit: Permit | None = obj.get("permit")
        if not permit:
            return None
        return {
            "id": permit.pk,
            "type": permit.permit_type,
            "valid_from": permit.valid_from,
            "valid_until": permit.valid_until,
            "zones": [z.zone_code for z in permit.zones.all()],
        }
