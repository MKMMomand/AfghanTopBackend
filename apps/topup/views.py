from django.db.models import Q
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsApprovedReseller
from apps.shopkeepers.models import ShopkeeperProfile

from .models import FavoriteNumber, ScheduledTopup, TopUpTransaction
from .serializers import FavoriteNumberSerializer, ScheduledTopupSerializer, TopUpCreateSerializer, TopUpTransactionSerializer
from .services import execute_topup


class ShopkeeperProfileMixin:
    def get_profile(self):
        return ShopkeeperProfile.objects.get(user=self.request.user)


class FavoriteNumberListCreateView(ShopkeeperProfileMixin, generics.ListCreateAPIView):
    serializer_class = FavoriteNumberSerializer
    permission_classes = [IsApprovedReseller]

    def get_queryset(self):
        qs = FavoriteNumber.objects.filter(profile=self.get_profile()).order_by("category", "label", "-created_at")
        category = self.request.query_params.get("category")
        search = (self.request.query_params.get("search") or "").strip()
        if category:
            qs = qs.filter(category__iexact=category)
        if search:
            qs = qs.filter(Q(mobile_number__icontains=search) | Q(label__icontains=search) | Q(network__icontains=search) | Q(category__icontains=search))
        return qs

    def perform_create(self, serializer):
        serializer.save(profile=self.get_profile())


class FavoriteNumberDetailView(ShopkeeperProfileMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = FavoriteNumberSerializer
    permission_classes = [IsApprovedReseller]

    def get_queryset(self):
        return FavoriteNumber.objects.filter(profile=self.get_profile())


class TransactionListView(ShopkeeperProfileMixin, generics.ListAPIView):
    serializer_class = TopUpTransactionSerializer
    permission_classes = [IsApprovedReseller]

    def get_queryset(self):
        qs = TopUpTransaction.objects.filter(profile=self.get_profile()).order_by("-created_at")
        q = (self.request.query_params.get("q") or "").strip()
        network = (self.request.query_params.get("network") or "").strip()
        status_value = (self.request.query_params.get("status") or "").strip()
        amount = (self.request.query_params.get("amount") or "").strip()
        date = (self.request.query_params.get("date") or "").strip()
        time = (self.request.query_params.get("time") or "").strip()
        mobile_number = (self.request.query_params.get("mobile_number") or "").strip()
        if q:
            qs = qs.filter(Q(mobile_number__icontains=q) | Q(provider_reference__icontains=q) | Q(message__icontains=q))
        if mobile_number:
            qs = qs.filter(mobile_number__icontains=mobile_number)
        if network:
            qs = qs.filter(network__iexact=network)
        if status_value:
            qs = qs.filter(status__iexact=status_value)
        if amount:
            qs = qs.filter(amount=amount)
        if date:
            qs = qs.filter(created_at__date=date)
        if time:
            qs = qs.filter(created_at__time__hour=int(time.split(':')[0]))
        return qs


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


class ScheduledTopupListCreateView(ShopkeeperProfileMixin, generics.ListCreateAPIView):
    serializer_class = ScheduledTopupSerializer
    permission_classes = [IsApprovedReseller]

    def get_queryset(self):
        return ScheduledTopup.objects.filter(profile=self.get_profile()).order_by('schedule_for', '-created_at')

    def perform_create(self, serializer):
        serializer.save(profile=self.get_profile())


class ScheduledTopupDetailView(ShopkeeperProfileMixin, generics.RetrieveDestroyAPIView):
    serializer_class = ScheduledTopupSerializer
    permission_classes = [IsApprovedReseller]

    def get_queryset(self):
        return ScheduledTopup.objects.filter(profile=self.get_profile())
