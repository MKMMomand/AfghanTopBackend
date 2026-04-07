from decimal import Decimal

from django.db import models

from apps.common.models import TimeStampedModel, UUIDModel
from apps.shopkeepers.models import CreditPeriod, ShopkeeperProfile
from apps.topup.models import TopUpTransaction


class WalletLedgerEntry(TimeStampedModel, UUIDModel):
    ENTRY_CHOICES = [
        ("topup_debit", "Top-up Debit"),
        ("settlement_credit", "Settlement Credit"),
        ("adjustment_debit", "Adjustment Debit"),
        ("adjustment_credit", "Adjustment Credit"),
    ]

    profile = models.ForeignKey(ShopkeeperProfile, on_delete=models.CASCADE, related_name="wallet_ledger_entries")
    credit_period = models.ForeignKey(CreditPeriod, null=True, blank=True, on_delete=models.SET_NULL, related_name="ledger_entries")
    transaction = models.ForeignKey(TopUpTransaction, null=True, blank=True, on_delete=models.SET_NULL, related_name="ledger_entries")
    entry_type = models.CharField(max_length=30, choices=ENTRY_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    note = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def signed_amount(self) -> Decimal:
        if self.entry_type in {"settlement_credit", "adjustment_credit"}:
            return self.amount
        return self.amount * Decimal("-1")

    def __str__(self):
        return f"{self.profile.unique_shop_id} - {self.entry_type} - {self.amount}"


class SettlementPayment(TimeStampedModel, UUIDModel):
    METHOD_CHOICES = [
        ("cash", "Cash"),
        ("bank", "Bank Transfer"),
        ("wallet", "Wallet"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    profile = models.ForeignKey(ShopkeeperProfile, on_delete=models.CASCADE, related_name="settlement_payments")
    credit_period = models.ForeignKey(CreditPeriod, null=True, blank=True, on_delete=models.SET_NULL, related_name="settlement_payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default="cash")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="approved")
    reference = models.CharField(max_length=120, blank=True)
    note = models.CharField(max_length=255, blank=True)
    ledger_entry = models.OneToOneField(WalletLedgerEntry, null=True, blank=True, on_delete=models.SET_NULL, related_name="payment")
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.profile.unique_shop_id} - {self.amount} - {self.status}"
