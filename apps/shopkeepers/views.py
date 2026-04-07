from decimal import Decimal

from rest_framework import generics
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsApprovedReseller

from .models import ShopDocument, ShopkeeperProfile
from .serializers import DashboardSummarySerializer, ShopDocumentSerializer, ShopkeeperProfileSerializer
from .services import shop_dashboard_summary


class EnsureShopkeeperProfileMixin:
    def get_profile(self):
        profile, created = ShopkeeperProfile.objects.get_or_create(
            user=self.request.user,
            defaults={
                "unique_shop_id": f"SHOP-{self.request.user.id:06d}",
                "full_name": self.request.user.get_full_name(),
                "email": self.request.user.email or "",
                "status": "active" if getattr(self.request.user, "approval_status", "pending") == "approved" else "pending",
                "credit_limit": Decimal("5000"),
                "available_limit": Decimal("5000"),
                "low_limit_threshold": Decimal("500"),
            },
        )
        desired_status = "active" if getattr(self.request.user, "approval_status", "pending") == "approved" else "pending"
        needs_update = False
        if profile.status != desired_status:
            profile.status = desired_status
            needs_update = True
        if not profile.credit_limit:
            profile.credit_limit = Decimal("5000")
            needs_update = True
        if not profile.available_limit and not profile.outstanding_balance:
            profile.available_limit = profile.credit_limit
            needs_update = True
        if not profile.low_limit_threshold:
            profile.low_limit_threshold = Decimal("500")
            needs_update = True
        if needs_update:
            profile.save()
        return profile


class ShopkeeperProfileView(EnsureShopkeeperProfileMixin, generics.RetrieveUpdateAPIView):
    serializer_class = ShopkeeperProfileSerializer
    permission_classes = [IsApprovedReseller]

    def get_object(self):
        return self.get_profile()


class ShopDocumentListCreateView(EnsureShopkeeperProfileMixin, generics.ListCreateAPIView):
    serializer_class = ShopDocumentSerializer
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsApprovedReseller]

    def get_queryset(self):
        return ShopDocument.objects.filter(profile=self.get_profile()).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(profile=self.get_profile())


class DashboardSummaryView(EnsureShopkeeperProfileMixin, APIView):
    permission_classes = [IsApprovedReseller]

    def get(self, request):
        summary = shop_dashboard_summary(self.get_profile())
        data = DashboardSummarySerializer(summary).data
        return Response(data)
