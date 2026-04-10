from rest_framework import serializers
from apps.common.utils import normalize_afghan_mobile
from .models import FavoriteNumber, TopUpTransaction


class FavoriteNumberSerializer(serializers.ModelSerializer):
    class Meta:
        model = FavoriteNumber
        fields = ["id", "mobile_number", "label", "network", "category", "created_at"]


class TopUpTransactionSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source="provider.name", read_only=True)

    class Meta:
        model = TopUpTransaction
        fields = [
            "id", "uuid", "mobile_number", "network", "amount", "commission_percent", "commission_amount",
            "provider", "provider_name", "provider_reference", "status", "message", "created_at",
        ]
        read_only_fields = ["commission_percent", "commission_amount", "provider", "provider_reference", "status", "message"]


class TopUpCreateSerializer(serializers.Serializer):
    mobile_number = serializers.CharField(max_length=20)
    network = serializers.CharField(max_length=50, allow_blank=True, required=False)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)

    def validate_mobile_number(self, value):
        return normalize_afghan_mobile(value)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value
