from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import OTPRequest, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "id", "mobile_number", "username", "role", "approval_status",
        "is_reseller", "is_active", "is_mobile_verified", "is_staff",
    )
    list_filter = (
        "role", "approval_status", "is_reseller", "is_active",
        "is_mobile_verified", "is_staff", "is_superuser",
    )
    search_fields = ("mobile_number", "username", "first_name", "last_name", "email")
    ordering = ("-id",)
    fieldsets = (
        ("Login Info", {"fields": ("username", "password")}),
        ("Personal Info", {"fields": ("first_name", "last_name", "email", "mobile_number")}),
        ("Approval & Role", {"fields": ("role", "approval_status", "approval_note", "is_reseller", "is_mobile_verified")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        ("Create User", {
            "classes": ("wide",),
            "fields": (
                "username", "mobile_number", "password1", "password2",
                "role", "approval_status", "approval_note", "is_reseller",
                "is_mobile_verified", "is_active", "is_staff", "is_superuser",
            ),
        }),
    )
    readonly_fields = ("last_login", "date_joined")
    actions = ["approve_selected_resellers", "reject_selected_resellers"]

    @admin.action(description="Approve selected resellers")
    def approve_selected_resellers(self, request, queryset):
        queryset.update(approval_status="approved", is_active=True, is_mobile_verified=True, is_reseller=True)

    @admin.action(description="Reject selected resellers")
    def reject_selected_resellers(self, request, queryset):
        queryset.update(approval_status="rejected", is_active=False)


@admin.register(OTPRequest)
class OTPRequestAdmin(admin.ModelAdmin):
    list_display = ("mobile_number", "code", "purpose", "is_used", "created_at")
    list_filter = ("purpose", "is_used")
    search_fields = ("mobile_number", "code")
