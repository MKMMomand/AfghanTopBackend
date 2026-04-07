from decimal import Decimal

from django.contrib.auth import authenticate, get_user_model
from django.db.models import Q
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from apps.notifications.models import Notification
from apps.settlements.models import SettlementPayment
from apps.shopkeepers.models import AccountAuditLog, ServiceAccess, ShopkeeperProfile
from apps.topup.models import TopUpTransaction

User = get_user_model()


class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "mobile_number",
            "email",
            "first_name",
            "last_name",
            "role",
            "approval_status",
            "is_active",
            "is_staff",
            "is_superuser",
        ]
        read_only_fields = fields


class AdminLoginSerializer(serializers.Serializer):
    username_or_mobile = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        value = attrs["username_or_mobile"].strip()
        password = attrs["password"]

        user = User.objects.filter(
            Q(username__iexact=value) | Q(mobile_number=value) | Q(email__iexact=value)
        ).first()
        if not user:
            raise serializers.ValidationError({"username_or_mobile": "No admin account was found."})

        auth_user = authenticate(username=user.username, password=password)
        if not auth_user:
            raise serializers.ValidationError({"password": "Incorrect password."})

        if not auth_user.is_active:
            raise serializers.ValidationError("This admin account is inactive.")

        if not (auth_user.is_superuser or auth_user.is_staff or getattr(auth_user, "role", "") == "admin"):
            raise serializers.ValidationError("This account is not allowed to access the admin app.")

        attrs["user"] = auth_user
        return attrs

    def save(self, **kwargs):
        user = self.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        return {"user": user, "access": str(refresh.access_token), "refresh": str(refresh)}


class AdminDashboardSerializer(serializers.Serializer):
    total_users = serializers.IntegerField()
    pending_users = serializers.IntegerField()
    approved_users = serializers.IntegerField()
    suspended_users = serializers.IntegerField()
    active_profiles = serializers.IntegerField()
    total_outstanding = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_available_limit = serializers.DecimalField(max_digits=12, decimal_places=2)
    today_topups = serializers.IntegerField()
    today_topup_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    successful_topups = serializers.IntegerField()
    failed_topups = serializers.IntegerField()
    approved_settlements = serializers.IntegerField()
    approved_settlement_amount = serializers.DecimalField(max_digits=12, decimal_places=2)


class AdminShopkeeperListSerializer(serializers.ModelSerializer):
    shop_name = serializers.CharField(source="shopkeeper_profile.shop_name", read_only=True)
    unique_shop_id = serializers.CharField(source="shopkeeper_profile.unique_shop_id", read_only=True)
    profile_status = serializers.CharField(source="shopkeeper_profile.status", read_only=True)
    outstanding_balance = serializers.DecimalField(source="shopkeeper_profile.outstanding_balance", max_digits=12, decimal_places=2, read_only=True)
    available_limit = serializers.DecimalField(source="shopkeeper_profile.available_limit", max_digits=12, decimal_places=2, read_only=True)
    credit_limit = serializers.DecimalField(source="shopkeeper_profile.credit_limit", max_digits=12, decimal_places=2, read_only=True)
    documents_count = serializers.SerializerMethodField()

    def get_documents_count(self, obj):
        profile = getattr(obj, "shopkeeper_profile", None)
        return profile.documents.count() if profile else 0

    class Meta:
        model = User
        fields = [
            "id",
            "mobile_number",
            "first_name",
            "last_name",
            "email",
            "approval_status",
            "approval_note",
            "is_active",
            "shop_name",
            "unique_shop_id",
            "profile_status",
            "outstanding_balance",
            "available_limit",
            "credit_limit",
            "documents_count",
            "date_joined",
        ]


class ServiceAccessSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceAccess
        fields = [
            "id",
            "service_code",
            "is_enabled",
            "cash_enabled",
            "credit_enabled",
            "credit_locked",
            "lock_reason",
            "admin_note",
            "credit_limit",
            "available_credit",
            "used_credit",
            "overdue_amount",
            "allow_credit_for_topup_only",
            "auto_lock_on_overdue",
            "due_days",
            "next_due_date",
            "last_payment_at",
        ]


class AccountAuditLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    def get_actor_name(self, obj):
        if obj.user:
            full_name = obj.user.get_full_name().strip()
            return full_name or obj.user.username
        return ""

    class Meta:
        model = AccountAuditLog
        fields = ["id", "action", "service_code", "note", "metadata", "created_at", "actor_name"]


class ShopkeeperAdminDetailSerializer(serializers.ModelSerializer):
    user = AdminUserSerializer(read_only=True)
    service_accesses = ServiceAccessSerializer(many=True, read_only=True)
    audit_logs = serializers.SerializerMethodField()
    documents = serializers.SerializerMethodField()

    def get_audit_logs(self, obj):
        logs = obj.audit_logs.all()[:12]
        return AccountAuditLogSerializer(logs, many=True).data

    def get_documents(self, obj):
        return [
            {
                "id": d.id,
                "document_type": d.document_type,
                "file": d.file.url if d.file else "",
                "note": d.note,
                "created_at": d.created_at,
            }
            for d in obj.documents.all().order_by("-created_at")[:10]
        ]

    class Meta:
        model = ShopkeeperProfile
        fields = [
            "id",
            "uuid",
            "unique_shop_id",
            "full_name",
            "email",
            "shop_name",
            "owner_name",
            "address",
            "trade_license_number",
            "tazkira_number",
            "status",
            "is_kyc_verified",
            "credit_limit",
            "available_limit",
            "outstanding_balance",
            "low_limit_threshold",
            "manual_hold",
            "manual_hold_reason",
            "internal_note",
            "created_at",
            "updated_at",
            "user",
            "service_accesses",
            "audit_logs",
            "documents",
        ]


class ShopkeeperDecisionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject", "suspend", "reactivate"])
    note = serializers.CharField(required=False, allow_blank=True)
    enable_topup_service = serializers.BooleanField(required=False, default=True)
    enable_credit = serializers.BooleanField(required=False, default=True)
    credit_limit = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=Decimal("5000.00"))
    low_limit_threshold = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=Decimal("500.00"))


class CreditAdjustmentSerializer(serializers.Serializer):
    adjustment_type = serializers.ChoiceField(choices=["credit", "debit"])
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    reason = serializers.CharField(max_length=255)
    service_code = serializers.CharField(max_length=30, required=False, default="topup")

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value


class AdminTopupSerializer(serializers.ModelSerializer):
    shop_name = serializers.CharField(source="profile.shop_name", read_only=True)
    unique_shop_id = serializers.CharField(source="profile.unique_shop_id", read_only=True)
    shop_mobile = serializers.CharField(source="profile.user.mobile_number", read_only=True)

    class Meta:
        model = TopUpTransaction
        fields = [
            "id",
            "uuid",
            "mobile_number",
            "network",
            "amount",
            "commission_percent",
            "commission_amount",
            "provider_reference",
            "status",
            "message",
            "created_at",
            "shop_name",
            "unique_shop_id",
            "shop_mobile",
        ]


class AdminSettlementSerializer(serializers.ModelSerializer):
    shop_name = serializers.CharField(source="profile.shop_name", read_only=True)
    unique_shop_id = serializers.CharField(source="profile.unique_shop_id", read_only=True)
    shop_mobile = serializers.CharField(source="profile.user.mobile_number", read_only=True)

    class Meta:
        model = SettlementPayment
        fields = [
            "id",
            "uuid",
            "amount",
            "method",
            "status",
            "reference",
            "note",
            "processed_at",
            "created_at",
            "shop_name",
            "unique_shop_id",
            "shop_mobile",
        ]


class AdminNotificationCreateSerializer(serializers.Serializer):
    target = serializers.ChoiceField(choices=["all", "user"])
    user_id = serializers.IntegerField(required=False)
    title = serializers.CharField(max_length=150)
    message = serializers.CharField()
    type = serializers.ChoiceField(choices=Notification.TYPE_CHOICES, default="info")

    def validate(self, attrs):
        if attrs["target"] == "user" and not attrs.get("user_id"):
            raise serializers.ValidationError({"user_id": "user_id is required for user notifications."})
        return attrs
