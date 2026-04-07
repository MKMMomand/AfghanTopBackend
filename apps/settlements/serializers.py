from rest_framework import serializers

from .models import SettlementPayment, WalletLedgerEntry


class WalletLedgerEntrySerializer(serializers.ModelSerializer):
    transaction_uuid = serializers.CharField(source="transaction.uuid", read_only=True)

    class Meta:
        model = WalletLedgerEntry
        fields = [
            "id", "uuid", "entry_type", "amount", "balance_after", "note",
            "metadata", "transaction_uuid", "created_at",
        ]


class SettlementPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SettlementPayment
        fields = [
            "id", "uuid", "amount", "method", "status", "reference",
            "note", "processed_at", "created_at",
        ]
        read_only_fields = ["status", "processed_at"]


class SettlementPaymentCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    method = serializers.ChoiceField(choices=SettlementPayment.METHOD_CHOICES, default="cash")
    reference = serializers.CharField(max_length=120, required=False, allow_blank=True)
    note = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value


class CreditPeriodCompactSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(read_only=True)
    opening_limit = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    used_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    paid_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    receivable_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    profit_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    status = serializers.CharField(read_only=True)
    opened_at = serializers.DateTimeField(read_only=True)
    closed_at = serializers.DateTimeField(read_only=True, allow_null=True)


class SettlementOverviewSerializer(serializers.Serializer):
    profile_id = serializers.IntegerField()
    credit_limit = serializers.DecimalField(max_digits=12, decimal_places=2)
    available_limit = serializers.DecimalField(max_digits=12, decimal_places=2)
    outstanding_balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    month_topup_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    month_profit = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_topup_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_profit = serializers.DecimalField(max_digits=12, decimal_places=2)
    open_period = CreditPeriodCompactSerializer(allow_null=True)
    last_payment = SettlementPaymentSerializer(allow_null=True)
    recent_ledger = WalletLedgerEntrySerializer(many=True)
