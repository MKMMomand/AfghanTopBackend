from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsApprovedReseller
from apps.providers.models import TopUpProvider
from apps.shopkeepers.models import ShopkeeperProfile

from .models import BulkTopupBatch, CustomerReminder, FavoriteNumber, ScheduledTopup, TopUpTransaction
from .serializers import (
    BulkTopupBatchSerializer,
    BulkTopupCreateSerializer,
    CustomerReminderSerializer,
    FavoriteNumberSerializer,
    ScheduledTopupSerializer,
    ScheduledTopupUpdateSerializer,
    TopUpCreateSerializer,
    TopUpTransactionSerializer,
)
from .ai_service import AiContext, AiServiceError, OpenAISuggestionsService
from .services import (
    execute_bulk_topup,
    execute_topup,
    get_provider_wallet_balance,
    process_due_scheduled_topups,
    refresh_transaction_status,
)


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
        http_status = status.HTTP_202_ACCEPTED if tx.status == "pending" else status.HTTP_201_CREATED
        return Response(TopUpTransactionSerializer(tx).data, status=http_status)


class TransactionRefreshStatusView(ShopkeeperProfileMixin, APIView):
    permission_classes = [IsApprovedReseller]

    def post(self, request, pk: int):
        tx = TopUpTransaction.objects.filter(profile=self.get_profile(), pk=pk).select_related("provider").first()
        if not tx:
            return Response({"detail": "Transaction not found."}, status=status.HTTP_404_NOT_FOUND)
        tx = refresh_transaction_status(tx)
        return Response(TopUpTransactionSerializer(tx).data)


class ProviderWalletBalanceView(APIView):
    permission_classes = [IsApprovedReseller]

    def get(self, request):
        provider_code = (request.query_params.get("provider") or "sendaf").strip().lower()
        provider = TopUpProvider.objects.filter(code__iexact=provider_code, status="active").first()
        if not provider:
            return Response({"detail": "Active provider not found."}, status=status.HTTP_404_NOT_FOUND)
        result = get_provider_wallet_balance(provider)
        http_status = status.HTTP_200_OK if result.get("status") == "success" else status.HTTP_502_BAD_GATEWAY
        return Response(result, status=http_status)


class ScheduledTopupListCreateView(ShopkeeperProfileMixin, generics.ListCreateAPIView):
    serializer_class = ScheduledTopupSerializer
    permission_classes = [IsApprovedReseller]

    def get_queryset(self):
        qs = ScheduledTopup.objects.filter(profile=self.get_profile()).order_by('next_run_at', 'schedule_for', '-created_at')
        status_value = (self.request.query_params.get("status") or "").strip()
        active_only = (self.request.query_params.get("active_only") or "").strip().lower()
        if status_value:
            qs = qs.filter(status__iexact=status_value)
        if active_only in {"1", "true", "yes"}:
            qs = qs.filter(is_active=True)
        return qs

    def perform_create(self, serializer):
        serializer.save(profile=self.get_profile())


class ScheduledTopupDetailView(ShopkeeperProfileMixin, generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsApprovedReseller]

    def get_queryset(self):
        return ScheduledTopup.objects.filter(profile=self.get_profile())

    def get_serializer_class(self):
        if self.request.method in {"PATCH", "PUT"}:
            return ScheduledTopupUpdateSerializer
        return ScheduledTopupSerializer


class BulkTopupBatchListView(ShopkeeperProfileMixin, generics.ListAPIView):
    serializer_class = BulkTopupBatchSerializer
    permission_classes = [IsApprovedReseller]

    def get_queryset(self):
        return BulkTopupBatch.objects.filter(profile=self.get_profile()).prefetch_related("items").order_by("-created_at")


class BulkTopupCreateView(ShopkeeperProfileMixin, APIView):
    permission_classes = [IsApprovedReseller]

    def post(self, request):
        serializer = BulkTopupCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = self.get_profile()
        batch = execute_bulk_topup(
            profile=profile,
            items=serializer.validated_data["items"],
            title=serializer.validated_data.get("title", ""),
            note=serializer.validated_data.get("note", ""),
        )
        batch.refresh_from_db()
        return Response(BulkTopupBatchSerializer(batch).data, status=status.HTTP_201_CREATED)


class CustomerReminderListCreateView(ShopkeeperProfileMixin, generics.ListCreateAPIView):
    serializer_class = CustomerReminderSerializer
    permission_classes = [IsApprovedReseller]

    def get_queryset(self):
        qs = CustomerReminder.objects.filter(profile=self.get_profile()).order_by("reminder_at", "-created_at")
        status_value = (self.request.query_params.get("status") or "").strip()
        due_only = (self.request.query_params.get("due_only") or "").strip().lower()
        if status_value:
            qs = qs.filter(status__iexact=status_value)
        if due_only in {"1", "true", "yes"}:
            qs = qs.filter(status="pending", reminder_at__lte=timezone.now())
        return qs

    def perform_create(self, serializer):
        serializer.save(profile=self.get_profile())


class CustomerReminderDetailView(ShopkeeperProfileMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CustomerReminderSerializer
    permission_classes = [IsApprovedReseller]

    def get_queryset(self):
        return CustomerReminder.objects.filter(profile=self.get_profile())


@api_view(["POST"])
@permission_classes([IsApprovedReseller])
def process_my_due_scheduled_view(request):
    profile = ShopkeeperProfile.objects.get(user=request.user)
    processed = process_due_scheduled_topups(limit=100, profile=profile)
    return Response({"processed": processed})


class AiSuggestionsView(ShopkeeperProfileMixin, APIView):
    permission_classes = [IsApprovedReseller]

    def get(self, request):
        profile = self.get_profile()
        transactions = list(TopUpTransaction.objects.filter(profile=profile).order_by('-created_at')[:80])
        favorites = list(FavoriteNumber.objects.filter(profile=profile).order_by('category', 'label', '-created_at')[:20])
        reminders = list(CustomerReminder.objects.filter(profile=profile).order_by('reminder_at', '-created_at')[:20])

        try:
            cards = OpenAISuggestionsService().generate_cards(
                AiContext(
                    user_identifier=str(request.user.pk),
                    transactions=[
                        {
                            "mobile_number": tx.mobile_number,
                            "network": tx.network,
                            "amount": str(tx.amount),
                            "status": tx.status,
                            "created_at": tx.created_at.isoformat() if tx.created_at else None,
                            "message": tx.message,
                        }
                        for tx in transactions
                    ],
                    favorites=[
                        {
                            "mobile_number": fav.mobile_number,
                            "label": fav.label,
                            "network": fav.network,
                            "category": fav.category,
                            "created_at": fav.created_at.isoformat() if fav.created_at else None,
                        }
                        for fav in favorites
                    ],
                    reminders=[
                        {
                            "mobile_number": reminder.mobile_number,
                            "label": reminder.label,
                            "network": reminder.network,
                            "preferred_amount": str(reminder.preferred_amount),
                            "status": reminder.status,
                            "reminder_at": reminder.reminder_at.isoformat() if reminder.reminder_at else None,
                            "note": reminder.note,
                        }
                        for reminder in reminders
                    ],
                )
            )
            return Response({'cards': cards[:4], 'engine': 'openai', 'source': 'openai'})
        except AiServiceError:
            pass

        cards = []

        if transactions:
            number_frequency = {}
            amount_frequency = {}
            network_frequency = {}
            pending_tx = None
            for tx in transactions:
                if tx.mobile_number:
                    number_frequency[tx.mobile_number] = number_frequency.get(tx.mobile_number, 0) + 1
                amount_key = str(int(tx.amount)) if float(tx.amount).is_integer() else str(tx.amount)
                amount_frequency[amount_key] = amount_frequency.get(amount_key, 0) + 1
                if tx.network:
                    network_frequency[tx.network] = network_frequency.get(tx.network, 0) + 1
                if pending_tx is None and 'pending' in (tx.status or '').lower():
                    pending_tx = tx

            def top_key(values):
                return sorted(values.items(), key=lambda x: x[1], reverse=True)[0][0] if values else None

            top_number = top_key(number_frequency)
            top_amount = top_key(amount_frequency)
            top_network = top_key(network_frequency)

            if top_number and top_amount:
                cards.append({
                    'type': 'repeat_topup',
                    'title': 'Repeat best selling top up',
                    'message': f'{top_number} appears most often in your live records. Recharge {top_amount} AFN{f" on {top_network}" if top_network else ""} with one tap.',
                    'action_label': 'Top up now',
                    'mobile_number': top_number,
                    'amount': top_amount,
                    'network': top_network,
                    'confidence': 0.95,
                    'source': 'backend',
                })

            if pending_tx:
                cards.append({
                    'type': 'review_pending',
                    'title': 'Pending transaction needs review',
                    'message': f'{pending_tx.mobile_number} is still marked {pending_tx.status}. Review it before sending another recharge.',
                    'action_label': 'Open transactions',
                    'route': 'transactions',
                    'confidence': 0.9,
                    'source': 'backend',
                })

        due_reminder = next((r for r in reminders if (r.status or '').lower() == 'pending' and r.reminder_at and r.reminder_at <= timezone.now()), None)
        if due_reminder:
            cards.append({
                'type': 'due_reminder',
                'title': 'Reminder is due now',
                'message': f'{due_reminder.label or due_reminder.mobile_number} is due for {int(due_reminder.preferred_amount)} AFN on {due_reminder.network}.',
                'action_label': 'Use reminder',
                'mobile_number': due_reminder.mobile_number,
                'amount': str(int(due_reminder.preferred_amount)),
                'network': due_reminder.network,
                'confidence': 0.92,
                'source': 'backend',
            })

        if favorites:
            fav = favorites[0]
            cards.append({
                'type': 'favorite_shortcut',
                'title': 'Favorite customer shortcut',
                'message': f'{fav.label or fav.mobile_number} is ready as a fast recharge shortcut from your live favorites.',
                'action_label': 'Open favorite',
                'mobile_number': fav.mobile_number,
                'network': fav.network,
                'confidence': 0.84,
                'source': 'backend',
            })

        if len(cards) < 4:
            cards.append({
                'type': 'balance_snapshot',
                'title': 'Check credit and balances',
                'message': 'Review your current available limit, outstanding balance, and recent ledger movement from one screen.',
                'action_label': 'Open credit',
                'route': 'credit',
                'confidence': 0.8,
                'source': 'backend',
            })

        return Response({'cards': cards[:4], 'engine': 'heuristic-v1', 'source': 'backend'})
