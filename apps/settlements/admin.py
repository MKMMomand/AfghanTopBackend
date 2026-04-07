from django.contrib import admin

from .models import SettlementPayment, WalletLedgerEntry


@admin.register(WalletLedgerEntry)
class WalletLedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("profile", "entry_type", "amount", "balance_after", "created_at")
    list_filter = ("entry_type",)
    search_fields = ("profile__unique_shop_id", "note", "transaction__mobile_number")


@admin.register(SettlementPayment)
class SettlementPaymentAdmin(admin.ModelAdmin):
    list_display = ("profile", "amount", "method", "status", "reference", "processed_at")
    list_filter = ("status", "method")
    search_fields = ("profile__unique_shop_id", "reference", "note")
