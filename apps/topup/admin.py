from django.contrib import admin
from .models import BulkTopupBatch, BulkTopupItem, CustomerReminder, FavoriteNumber, ScheduledTopup, TopUpTransaction


@admin.register(FavoriteNumber)
class FavoriteNumberAdmin(admin.ModelAdmin):
    list_display = ("profile", "mobile_number", "label", "network")
    search_fields = ("mobile_number", "label")


@admin.register(TopUpTransaction)
class TopUpTransactionAdmin(admin.ModelAdmin):
    list_display = ("profile", "mobile_number", "network", "amount", "provider", "status", "created_at")
    list_filter = ("status", "network", "provider")
    search_fields = ("mobile_number", "provider_reference")


@admin.register(ScheduledTopup)
class ScheduledTopupAdmin(admin.ModelAdmin):
    list_display = ("profile", "mobile_number", "network", "amount", "next_run_at", "repeat_type", "status", "is_active")
    list_filter = ("status", "repeat_type", "is_active", "network")
    search_fields = ("mobile_number", "note")


class BulkTopupItemInline(admin.TabularInline):
    model = BulkTopupItem
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(BulkTopupBatch)
class BulkTopupBatchAdmin(admin.ModelAdmin):
    list_display = ("profile", "title", "status", "total_items", "success_count", "failed_count", "total_amount", "created_at")
    list_filter = ("status",)
    search_fields = ("title", "note")
    inlines = [BulkTopupItemInline]


@admin.register(CustomerReminder)
class CustomerReminderAdmin(admin.ModelAdmin):
    list_display = ("profile", "mobile_number", "label", "preferred_amount", "reminder_at", "reminder_type", "status")
    list_filter = ("status", "reminder_type", "network")
    search_fields = ("mobile_number", "label", "note")
