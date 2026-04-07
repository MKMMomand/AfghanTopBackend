from rest_framework import serializers
from .models import CreditPeriod, ShopDocument, ShopkeeperProfile

class ShopDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopDocument
        fields = ["id", "document_type", "file", "note", "created_at"]

class CreditPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditPeriod
        fields = "__all__"
        read_only_fields = ["profile"]

class ShopkeeperProfileSerializer(serializers.ModelSerializer):
    documents = ShopDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = ShopkeeperProfile
        fields = [
            "id", "uuid", "unique_shop_id", "full_name", "email", "shop_name", "owner_name",
            "address", "trade_license_number", "tazkira_number", "status", "is_kyc_verified",
            "credit_limit", "available_limit", "outstanding_balance", "low_limit_threshold",
            "documents",
        ]
        read_only_fields = ["unique_shop_id", "status", "is_kyc_verified"]

class DashboardSummarySerializer(serializers.Serializer):
    shopkeeper = ShopkeeperProfileSerializer()
    daily_count = serializers.IntegerField()
    monthly_count = serializers.IntegerField()
    total_count = serializers.IntegerField()
    daily_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    monthly_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    low_limit_warning = serializers.BooleanField()
