from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsApprovedReseller
from apps.shopkeepers.models import ShopkeeperProfile

from .models import FavoriteNumber, TopUpTransaction
from .serializers import FavoriteNumberSerializer, TopUpCreateSerializer, TopUpTransactionSerializer
from .services import execute_topup


class ShopkeeperProfileMixin:
    def get_profile(self):
        return ShopkeeperProfile.objects.get(user=self.request.user)


class FavoriteNumberListCreateView(ShopkeeperProfileMixin, generics.ListCreateAPIView):
    serializer_class = FavoriteNumberSerializer
    permission_classes = [IsApprovedReseller]

    def get_queryset(self):
        return FavoriteNumber.objects.filter(profile=self.get_profile()).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(profile=self.get_profile())


class TransactionListView(ShopkeeperProfileMixin, generics.ListAPIView):
    serializer_class = TopUpTransactionSerializer
    permission_classes = [IsApprovedReseller]
    filterset_fields = ["status", "network", "provider"]
    search_fields = ["mobile_number", "provider_reference"]
    ordering_fields = ["created_at", "amount"]

    def get_queryset(self):
        return TopUpTransaction.objects.filter(profile=self.get_profile()).order_by("-created_at")


class TransactionCreateView(ShopkeeperProfileMixin, APIView):
    permission_classes = [IsApprovedReseller]

    def post(self, request):
        serializer = TopUpCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = self.get_profile()
        try:
            tx = execute_topup(profile=profile, **serializer.validated_data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TopUpTransactionSerializer(tx).data, status=status.HTTP_201_CREATED)
