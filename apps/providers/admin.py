from django.contrib import admin
from .models import ProviderLog, TopUpProvider


@admin.register(TopUpProvider)
class TopUpProviderAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "status", "priority", "supported_networks", "daily_cap", "commission_percent", "success_rate")
    list_filter = ("status",)
    search_fields = ("name", "code", "supported_networks")


@admin.register(ProviderLog)
class ProviderLogAdmin(admin.ModelAdmin):
    list_display = ("provider", "action", "is_success", "reference", "created_at")
    list_filter = ("is_success", "provider")
    search_fields = ("reference", "provider__name")
