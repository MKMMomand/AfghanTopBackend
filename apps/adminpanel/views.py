from django.contrib.auth import get_user_model
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications.models import Notification
from apps.settlements.models import SettlementPayment
from apps.shopkeepers.models import ShopkeeperProfile
from apps.topup.models import TopUpTransaction

from .serializers import (
    AdminDashboardSerializer,
    AdminLoginSerializer,
    AdminNotificationCreateSerializer,
    AdminSettlementSerializer,
    AdminShopkeeperListSerializer,
    AdminTopupSerializer,
    AdminUserSerializer,
    CreditAdjustmentSerializer,
    ShopkeeperAdminDetailSerializer,
    ShopkeeperDecisionSerializer,
)
from .services import apply_credit_adjustment, apply_shopkeeper_decision

User = get_user_model()


class IsAdminAppUser(permissions.BasePermission):
    message = "Admin access is required."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and user.is_active and (
                user.is_superuser or user.is_staff or getattr(user, "role", "") == "admin"
            )
        )


class AdminLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = AdminLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.save()
        return Response(
            {
                "message": "Admin login successful.",
                "access": payload["access"],
                "refresh": payload["refresh"],
                "user": AdminUserSerializer(payload["user"]).data,
            },
            status=status.HTTP_200_OK,
        )


class AdminMeView(generics.RetrieveAPIView):
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminAppUser]

    def get_object(self):
        return self.request.user


class AdminDashboardView(APIView):
    permission_classes = [IsAdminAppUser]

    def get(self, request):
        today = timezone.localdate()
        topups_today = TopUpTransaction.objects.filter(created_at__date=today)
        settlements = SettlementPayment.objects.filter(status="approved")
        data = {
            "total_users": User.objects.filter(is_reseller=True).count(),
            "pending_users": User.objects.filter(is_reseller=True, approval_status="pending").count(),
            "approved_users": User.objects.filter(is_reseller=True, approval_status="approved").count(),
            "suspended_users": User.objects.filter(is_reseller=True, approval_status__in=["suspended", "rejected"]).count(),
            "active_profiles": ShopkeeperProfile.objects.filter(status="active").count(),
            "total_outstanding": ShopkeeperProfile.objects.aggregate(value=Sum("outstanding_balance"))["value"] or 0,
            "total_available_limit": ShopkeeperProfile.objects.aggregate(value=Sum("available_limit"))["value"] or 0,
            "today_topups": topups_today.count(),
            "today_topup_amount": topups_today.aggregate(value=Sum("amount"))["value"] or 0,
            "successful_topups": topups_today.filter(status="success").count(),
            "failed_topups": topups_today.filter(status="failed").count(),
            "approved_settlements": settlements.count(),
            "approved_settlement_amount": settlements.aggregate(value=Sum("amount"))["value"] or 0,
        }
        return Response(AdminDashboardSerializer(data).data)


class AdminShopkeeperListView(generics.ListAPIView):
    serializer_class = AdminShopkeeperListSerializer
    permission_classes = [IsAdminAppUser]

    def get_queryset(self):
        queryset = User.objects.filter(is_reseller=True).select_related("shopkeeper_profile").order_by("-date_joined")
        search = self.request.query_params.get("search", "").strip()
        approval_status = self.request.query_params.get("approval_status", "").strip()
        profile_status = self.request.query_params.get("profile_status", "").strip()
        if approval_status:
            queryset = queryset.filter(approval_status=approval_status)
        if profile_status:
            queryset = queryset.filter(shopkeeper_profile__status=profile_status)
        if search:
            queryset = queryset.filter(
                Q(mobile_number__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(email__icontains=search)
                | Q(shopkeeper_profile__shop_name__icontains=search)
                | Q(shopkeeper_profile__unique_shop_id__icontains=search)
            )
        return queryset


class AdminShopkeeperDetailView(generics.RetrieveAPIView):
    serializer_class = ShopkeeperAdminDetailSerializer
    permission_classes = [IsAdminAppUser]
    lookup_url_kwarg = "user_id"

    def get_object(self):
        return ShopkeeperProfile.objects.select_related("user").prefetch_related("service_accesses", "audit_logs", "documents").get(user_id=self.kwargs["user_id"])


class AdminShopkeeperDecisionView(APIView):
    permission_classes = [IsAdminAppUser]

    def post(self, request, user_id: int):
        profile = ShopkeeperProfile.objects.select_related("user").get(user_id=user_id)
        serializer = ShopkeeperDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = apply_shopkeeper_decision(profile=profile, actor=request.user, **serializer.validated_data)
        return Response(ShopkeeperAdminDetailSerializer(profile).data)


class AdminCreditAdjustmentView(APIView):
    permission_classes = [IsAdminAppUser]

    def post(self, request, user_id: int):
        profile = ShopkeeperProfile.objects.select_related("user").get(user_id=user_id)
        serializer = CreditAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = apply_credit_adjustment(profile=profile, actor=request.user, **serializer.validated_data)
        return Response(result, status=status.HTTP_200_OK)


class AdminTopupListView(generics.ListAPIView):
    serializer_class = AdminTopupSerializer
    permission_classes = [IsAdminAppUser]

    def get_queryset(self):
        queryset = TopUpTransaction.objects.select_related("profile__user").order_by("-created_at")
        status_value = self.request.query_params.get("status", "").strip()
        search = self.request.query_params.get("search", "").strip()
        if status_value:
            queryset = queryset.filter(status=status_value)
        if search:
            queryset = queryset.filter(
                Q(mobile_number__icontains=search)
                | Q(profile__shop_name__icontains=search)
                | Q(profile__user__mobile_number__icontains=search)
                | Q(provider_reference__icontains=search)
            )
        return queryset[:200]


class AdminSettlementListView(generics.ListAPIView):
    serializer_class = AdminSettlementSerializer
    permission_classes = [IsAdminAppUser]

    def get_queryset(self):
        queryset = SettlementPayment.objects.select_related("profile__user").order_by("-created_at")
        status_value = self.request.query_params.get("status", "").strip()
        search = self.request.query_params.get("search", "").strip()
        if status_value:
            queryset = queryset.filter(status=status_value)
        if search:
            queryset = queryset.filter(
                Q(profile__shop_name__icontains=search)
                | Q(profile__user__mobile_number__icontains=search)
                | Q(reference__icontains=search)
            )
        return queryset[:200]


class AdminSendNotificationView(APIView):
    permission_classes = [IsAdminAppUser]

    def post(self, request):
        serializer = AdminNotificationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        users = User.objects.filter(is_reseller=True, is_active=True) if data["target"] == "all" else User.objects.filter(id=data["user_id"], is_reseller=True)
        created = [Notification(user=user, title=data["title"], message=data["message"], type=data["type"]) for user in users]
        Notification.objects.bulk_create(created)
        return Response({"created": len(created)}, status=status.HTTP_201_CREATED)
