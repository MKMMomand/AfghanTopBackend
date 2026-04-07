from django.contrib import admin
from .models import FavoriteNumber, TopUpTransaction

@admin.register(FavoriteNumber)
class FavoriteNumberAdmin(admin.ModelAdmin):
    list_display = ("profile", "mobile_number", "label", "network")
    search_fields = ("mobile_number", "label")

@admin.register(TopUpTransaction)
class TopUpTransactionAdmin(admin.ModelAdmin):
    list_display = ("profile", "mobile_number", "network", "amount", "provider", "status", "created_at")
    list_filter = ("status", "network", "provider")
    search_fields = ("mobile_number", "provider_reference")
