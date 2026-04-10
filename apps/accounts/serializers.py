from django.contrib.auth import authenticate, get_user_model
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from apps.common.utils import normalize_afghan_mobile, validate_afghan_tazkira, is_valid_afghan_mobile
from apps.shopkeepers.models import AccountAuditLog, ServiceAccess, ShopkeeperProfile

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    shop_name = serializers.SerializerMethodField()

    def get_shop_name(self, obj):
        profile = getattr(obj, "shopkeeper_profile", None)
        return getattr(profile, "shop_name", "")

    class Meta:
        model = User
        fields = [
            "id", "username", "mobile_number", "email", "first_name", "last_name",
            "is_active", "role", "is_mobile_verified", "approval_status", "approval_note",
            "is_reseller", "shop_name",
        ]
        read_only_fields = fields


class ResellerRegistrationSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    mobile_number = serializers.CharField(max_length=20)
    tazkira_number = serializers.CharField(max_length=100)
    shop_name = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=6, style={"input_type": "password"})
    confirm_password = serializers.CharField(write_only=True, min_length=6, style={"input_type": "password"})

    def validate_full_name(self, value):
        value = value.strip()
        if len(value.split()) < 2:
            raise serializers.ValidationError("Please enter your full name.")
        return value

    def validate_mobile_number(self, value):
        value = normalize_afghan_mobile(value)
        if not value or not is_valid_afghan_mobile(value):
            raise serializers.ValidationError("Please enter a valid Afghan mobile number.")
        return value

    def validate_shop_name(self, value):
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError("Shop name must be at least 3 characters.")
        if ShopkeeperProfile.objects.filter(shop_name__iexact=value).exists():
            raise serializers.ValidationError("This shop name already exists.")
        return value

    def validate_tazkira_number(self, value):
        try:
            value = validate_afghan_tazkira(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))
        if ShopkeeperProfile.objects.filter(tazkira_number__iexact=value).exists():
            raise serializers.ValidationError("This tazkira number is already registered.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        if User.objects.filter(mobile_number=attrs["mobile_number"]).exists():
            raise serializers.ValidationError({
                "mobile_number": "An account with this mobile number already exists. Please sign in instead."
            })
        return attrs

    @transaction.atomic
    def save(self, **kwargs):
        mobile_number = self.validated_data["mobile_number"]
        full_name = self.validated_data["full_name"].strip()
        name_parts = full_name.split()
        first_name = name_parts[0]
        last_name = " ".join(name_parts[1:])

        user = User.objects.create_user(
            username=mobile_number,
            mobile_number=mobile_number,
            password=self.validated_data["password"],
            first_name=first_name,
            last_name=last_name,
            role="shopkeeper",
            approval_status="pending",
            is_mobile_verified=False,
            is_active=True,
            is_reseller=True,
        )

        profile = ShopkeeperProfile.objects.create(
            user=user,
            unique_shop_id=f"SHOP-{user.id:06d}",
            full_name=full_name,
            shop_name=self.validated_data["shop_name"].strip(),
            owner_name=full_name,
            tazkira_number=self.validated_data["tazkira_number"],
            status="pending",
            contact_number=mobile_number,
        )

        ServiceAccess.objects.create(
            profile=profile,
            service_code="topup",
            is_enabled=False,
            cash_enabled=False,
            credit_enabled=False,
            credit_locked=True,
            lock_reason="Pending approval.",
            credit_limit=0,
            available_credit=0,
            used_credit=0,
            overdue_amount=0,
            allow_credit_for_topup_only=True,
        )

        AccountAuditLog.objects.create(
            profile=profile,
            user=user,
            action="application_created",
            note="New agent application submitted.",
            metadata={"mobile_number": mobile_number, "tazkira_number": profile.tazkira_number},
        )

        return user


class RegistrationValidationSerializer(serializers.Serializer):
    field = serializers.ChoiceField(choices=["mobile_number", "shop_name", "tazkira_number"])
    value = serializers.CharField(max_length=150)

    def save(self, **kwargs):
        field = self.validated_data["field"]
        value = self.validated_data["value"].strip()

        if field == "mobile_number":
            value = normalize_afghan_mobile(value)
            exists = User.objects.filter(mobile_number=value).exists() if value else False
            return {"field": field, "normalized_value": value, "available": not exists, "message": "" if not exists else "This mobile number already exists."}

        if field == "shop_name":
            exists = ShopkeeperProfile.objects.filter(shop_name__iexact=value).exists() if value else False
            return {"field": field, "normalized_value": value, "available": not exists, "message": "" if not exists else "This shop name already exists."}

        try:
            normalized = validate_afghan_tazkira(value)
        except ValueError as exc:
            return {"field": field, "normalized_value": value, "available": False, "message": str(exc)}
        exists = ShopkeeperProfile.objects.filter(tazkira_number__iexact=normalized).exists() if normalized else False
        return {"field": field, "normalized_value": normalized, "available": not exists, "message": "" if not exists else "This tazkira number already exists."}


class ResellerLoginSerializer(serializers.Serializer):
    mobile_number = serializers.CharField(max_length=20)
    password = serializers.CharField(write_only=True, trim_whitespace=False, style={"input_type": "password"})

    def validate_mobile_number(self, value):
        value = normalize_afghan_mobile(value)
        if not value:
            raise serializers.ValidationError("Mobile number is required.")
        return value

    def validate(self, attrs):
        mobile_number = attrs["mobile_number"]
        password = attrs["password"]
        user = User.objects.filter(mobile_number=mobile_number).first()

        if not user:
            raise serializers.ValidationError({"mobile_number": "No agent account was found for this mobile number."})

        user = authenticate(username=user.username, password=password)
        if not user:
            raise serializers.ValidationError({"password": "Incorrect password."})

        if not user.is_active:
            raise serializers.ValidationError("This account is currently inactive.")

        if user.approval_status == "pending":
            raise serializers.ValidationError("Your application is still pending approval. Please wait for admin approval.")
        if user.approval_status == "rejected":
            note = user.approval_note or "Please contact support or submit a new application."
            raise serializers.ValidationError(f"Your agent application was rejected. {note}")
        if user.approval_status == "suspended":
            note = user.approval_note or "Please contact support."
            raise serializers.ValidationError(f"Your account is suspended. {note}")

        attrs["user"] = user
        return attrs

    def save(self, **kwargs):
        user = self.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        return {"user": user, "refresh": str(refresh), "access": str(refresh.access_token)}


class ApplicationStatusSerializer(serializers.Serializer):
    mobile_number = serializers.CharField(max_length=20)

    def validate_mobile_number(self, value):
        value = normalize_afghan_mobile(value)
        if not value:
            raise serializers.ValidationError("Mobile number is required.")
        return value

    def save(self, **kwargs):
        user = User.objects.filter(mobile_number=self.validated_data["mobile_number"]).first()
        if not user:
            raise serializers.ValidationError({"mobile_number": "No application found for this mobile number."})
        profile = getattr(user, "shopkeeper_profile", None)
        return {
            "mobile_number": user.mobile_number,
            "approval_status": user.approval_status,
            "approval_note": user.approval_note,
            "shop_name": getattr(profile, "shop_name", ""),
            "full_name": getattr(profile, "full_name", user.get_full_name()),
        }
