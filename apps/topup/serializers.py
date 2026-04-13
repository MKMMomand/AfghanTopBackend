from decimal import Decimal
from rest_framework import serializers
from apps.common.utils import normalize_afghan_mobile
from .models import BulkTopupBatch, BulkTopupItem, CommissionRule, CustomerReminder, FavoriteNumber, ScheduledTopup, TopUpTransaction


class FavoriteNumberSerializer(serializers.ModelSerializer):
    class Meta:
        model = FavoriteNumber
        fields = ["id", "mobile_number", "label", "network", "category", "created_at"]

    def validate_mobile_number(self, value):
        return normalize_afghan_mobile(value)

    def validate(self, attrs):
        profile = getattr(self.instance, 'profile', None) or self.context['request'].user.shopkeeper_profile
        mobile_number = attrs.get('mobile_number') or getattr(self.instance, 'mobile_number', '')
        existing = FavoriteNumber.objects.filter(profile=profile)
        if self.instance:
            existing = existing.exclude(id=self.instance.id)

        duplicate_exists = any(
            normalize_afghan_mobile(item.mobile_number) == mobile_number
            for item in existing.only("mobile_number")
        )
        if duplicate_exists:
            raise serializers.ValidationError({"mobile_number": "This number is already in your favorites."})
        attrs["mobile_number"] = mobile_number
        return attrs


class TopUpTransactionSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source="provider.name", read_only=True)

    class Meta:
        model = TopUpTransaction
        fields = [
            "id", "uuid", "mobile_number", "network", "amount", "commission_percent", "commission_amount",
            "provider_cost", "agent_profit", "platform_profit", "platform_commission_percent",
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
            raise serializers.ValidationError("Amount must be greater than 0 AFN.")
        return value


class ScheduledTopupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduledTopup
        fields = [
            "id", "uuid", "mobile_number", "network", "amount", "schedule_for", "next_run_at", "last_run_at",
            "repeat_type", "is_active", "status", "note", "failure_reason", "last_transaction", "created_at",
        ]
        read_only_fields = ["status", "last_transaction", "created_at", "last_run_at", "failure_reason", "next_run_at"]

    def validate_mobile_number(self, value):
        return normalize_afghan_mobile(value)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than 0 AFN.")
        return value

    def create(self, validated_data):
        validated_data.setdefault("next_run_at", validated_data.get("schedule_for"))
        return super().create(validated_data)


class ScheduledTopupUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduledTopup
        fields = ["schedule_for", "repeat_type", "is_active", "note", "status"]


class BulkTopupItemInputSerializer(serializers.Serializer):
    mobile_number = serializers.CharField(max_length=20)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    network = serializers.CharField(max_length=50, allow_blank=True, required=False)
    label = serializers.CharField(max_length=120, allow_blank=True, required=False)

    def validate_mobile_number(self, value):
        return normalize_afghan_mobile(value)

    def validate_amount(self, value):
        if value <= Decimal("0"):
            raise serializers.ValidationError("Amount must be greater than 0 AFN.")
        return value


class BulkTopupCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=120, allow_blank=True, required=False)
    note = serializers.CharField(max_length=255, allow_blank=True, required=False)
    items = BulkTopupItemInputSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("Add at least one top-up item.")
        if len(value) > 100:
            raise serializers.ValidationError("You can submit up to 100 numbers in one bulk top-up.")
        return value


class BulkTopupItemSerializer(serializers.ModelSerializer):
    transaction_uuid = serializers.CharField(source="transaction.uuid", read_only=True)

    class Meta:
        model = BulkTopupItem
        fields = ["id", "uuid", "mobile_number", "network", "amount", "label", "status", "message", "transaction", "transaction_uuid", "created_at"]


class BulkTopupBatchSerializer(serializers.ModelSerializer):
    items = BulkTopupItemSerializer(many=True, read_only=True)

    class Meta:
        model = BulkTopupBatch
        fields = ["id", "uuid", "title", "note", "status", "total_items", "success_count", "failed_count", "total_amount", "created_at", "items"]


class CustomerReminderSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerReminder
        fields = [
            "id", "uuid", "favorite", "mobile_number", "label", "network", "preferred_amount", "reminder_at",
            "reminder_type", "status", "note", "last_topup", "created_at",
        ]
        read_only_fields = ["last_topup", "created_at"]

    def validate_mobile_number(self, value):
        return normalize_afghan_mobile(value)

    def validate_preferred_amount(self, value):
        if value <= Decimal("0"):
            raise serializers.ValidationError("Amount must be greater than 0 AFN.")
        return value


class CommissionRuleSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source="provider.name", read_only=True)

    class Meta:
        model = CommissionRule
        fields = [
            "id", "name", "scope", "provider", "provider_name", "profile", "network",
            "agent_percent", "platform_percent", "is_active", "priority", "created_at",
        ]
