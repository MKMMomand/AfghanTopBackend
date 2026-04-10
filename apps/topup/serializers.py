from rest_framework import serializers
from apps.common.utils import normalize_afghan_mobile
from .models import FavoriteNumber, ScheduledTopup, TopUpTransaction


class FavoriteNumberSerializer(serializers.ModelSerializer):
    class Meta:
        model = FavoriteNumber
        fields = ["id", "mobile_number", "label", "network", "category", "created_at"]

    def validate_mobile_number(self, value):
        return normalize_afghan_mobile(value)

    def validate(self, attrs):
        profile = getattr(self.instance, 'profile', None) or self.context['request'].user.shopkeeper_profile
        mobile_number = attrs.get('mobile_number') or getattr(self.instance, 'mobile_number', '')
        qs = FavoriteNumber.objects.filter(profile=profile, mobile_number=mobile_number)
        if self.instance:
            qs = qs.exclude(id=self.instance.id)
        if qs.exists():
            raise serializers.ValidationError({"mobile_number": "This number is already in your favorites."})
        return attrs


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
        if value < 25:
            raise serializers.ValidationError("Minimum top-up amount is 25 AFN.")
        return value


class ScheduledTopupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduledTopup
        fields = [
            "id", "uuid", "mobile_number", "network", "amount", "schedule_for",
            "status", "note", "last_transaction", "created_at",
        ]
        read_only_fields = ["status", "last_transaction", "created_at"]

    def validate_mobile_number(self, value):
        return normalize_afghan_mobile(value)

    def validate_amount(self, value):
        if value < 25:
            raise serializers.ValidationError("Minimum top-up amount is 25 AFN.")
        return value
