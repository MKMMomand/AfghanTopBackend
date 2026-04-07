from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsApprovedReseller
from apps.shopkeepers.models import ShopkeeperProfile

from .models import SettlementPayment, WalletLedgerEntry
from .serializers import (
    SettlementOverviewSerializer,
    SettlementPaymentCreateSerializer,
    SettlementPaymentSerializer,
    WalletLedgerEntrySerializer,
)
from .services import create_settlement_payment, settlement_overview_data


class SettlementProfileMixin:
    def get_profile(self):
        return ShopkeeperProfile.objects.get(user=self.request.user)


class SettlementOverviewView(SettlementProfileMixin, APIView):
    permission_classes = [IsApprovedReseller]

    def get(self, request):
        data = settlement_overview_data(self.get_profile())
        return Response(SettlementOverviewSerializer(data).data)


class WalletLedgerListView(SettlementProfileMixin, generics.ListAPIView):
    serializer_class = WalletLedgerEntrySerializer
    permission_classes = [IsApprovedReseller]

    def get_queryset(self):
        return WalletLedgerEntry.objects.filter(profile=self.get_profile())


class SettlementPaymentListCreateView(SettlementProfileMixin, APIView):
    permission_classes = [IsApprovedReseller]

    def get(self, request):
        queryset = SettlementPayment.objects.filter(profile=self.get_profile())
        return Response(SettlementPaymentSerializer(queryset, many=True).data)

    def post(self, request):
        serializer = SettlementPaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payment = create_settlement_payment(profile=self.get_profile(), **serializer.validated_data)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SettlementPaymentSerializer(payment).data, status=status.HTTP_201_CREATED)
