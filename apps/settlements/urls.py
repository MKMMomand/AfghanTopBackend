from django.urls import path
from .views import SettlementOverviewView, SettlementPaymentListCreateView, WalletLedgerListView

urlpatterns = [
    path("overview/", SettlementOverviewView.as_view(), name="settlement-overview"),
    path("ledger/", WalletLedgerListView.as_view(), name="wallet-ledger-list"),
    path("payments/", SettlementPaymentListCreateView.as_view(), name="settlement-payment-list-create"),
]
