from django.urls import path
from .views import (
    BulkTopupBatchListView,
    BulkTopupCreateView,
    CustomerReminderDetailView,
    CustomerReminderListCreateView,
    FavoriteNumberDetailView,
    FavoriteNumberListCreateView,
    ProviderWalletBalanceView,
    ScheduledTopupDetailView,
    ScheduledTopupListCreateView,
    TransactionCreateView,
    TransactionListView,
    TransactionRefreshStatusView,
    process_my_due_scheduled_view,
)

urlpatterns = [
    path("favorites/", FavoriteNumberListCreateView.as_view(), name="favorite-number-list-create"),
    path("favorites/<int:pk>/", FavoriteNumberDetailView.as_view(), name="favorite-number-detail"),
    path("transactions/", TransactionListView.as_view(), name="transaction-list"),
    path("transactions/create/", TransactionCreateView.as_view(), name="transaction-create"),
    path("transactions/<int:pk>/refresh-status/", TransactionRefreshStatusView.as_view(), name="transaction-refresh-status"),
    path("provider/wallet-balance/", ProviderWalletBalanceView.as_view(), name="provider-wallet-balance"),
    path("scheduled/", ScheduledTopupListCreateView.as_view(), name="scheduled-topup-list-create"),
    path("scheduled/<int:pk>/", ScheduledTopupDetailView.as_view(), name="scheduled-topup-detail"),
    path("scheduled/process-due/", process_my_due_scheduled_view, name="scheduled-process-due"),
    path("bulk/", BulkTopupBatchListView.as_view(), name="bulk-topup-list"),
    path("bulk/create/", BulkTopupCreateView.as_view(), name="bulk-topup-create"),
    path("reminders/", CustomerReminderListCreateView.as_view(), name="customer-reminder-list-create"),
    path("reminders/<int:pk>/", CustomerReminderDetailView.as_view(), name="customer-reminder-detail"),
]
