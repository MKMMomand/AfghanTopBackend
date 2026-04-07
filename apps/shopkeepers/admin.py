from decimal import Decimal

from django.contrib import admin
from django.utils import timezone

from .models import AccountAuditLog, CreditPeriod, ServiceAccess, ShopDocument, ShopkeeperProfile


class ServiceAccessInline(admin.TabularInline):
    model = ServiceAccess
    extra = 0
    fields = (
        "service_code", "is_enabled", "cash_enabled", "credit_enabled",
        "credit_locked", "lock_reason", "credit_limit", "available_credit",
        "used_credit", "overdue_amount", "next_due_date",
    )


@admin.register(ShopkeeperProfile)
class ShopkeeperProfileAdmin(admin.ModelAdmin):
    list_display = (
        "unique_shop_id", "shop_name", "user", "status", "is_kyc_verified",
        "credit_limit", "available_limit", "outstanding_balance", "manual_hold",
    )
    search_fields = ("unique_shop_id", "shop_name", "user__mobile_number", "owner_name", "full_name")
    list_filter = ("status", "is_kyc_verified", "manual_hold")
    inlines = [ServiceAccessInline]
    actions = ["activate_selected_profiles", "suspend_selected_profiles", "release_manual_hold"]

    @admin.action(description="Activate selected profiles")
    def activate_selected_profiles(self, request, queryset):
        for profile in queryset:
            profile.status = "active"
            profile.is_kyc_verified = True
            profile.manual_hold = False
            profile.manual_hold_reason = ""
            profile.save(update_fields=["status", "is_kyc_verified", "manual_hold", "manual_hold_reason", "updated_at"])
            profile.user.approval_status = "approved"
            profile.user.is_active = True
            profile.user.is_mobile_verified = True
            profile.user.is_reseller = True
            profile.user.save(update_fields=["approval_status", "is_active", "is_mobile_verified", "is_reseller"])
            topup, _ = ServiceAccess.objects.get_or_create(profile=profile, service_code="topup")
            topup.is_enabled = True
            topup.cash_enabled = True
            topup.credit_enabled = False
            topup.credit_locked = True
            topup.lock_reason = "Enable credit after review and deposit."
            topup.recalculate_balances()
            topup.save()
            AccountAuditLog.objects.create(profile=profile, user=request.user, action="profile_activated", note="Profile activated from admin.")
            AccountAuditLog.objects.create(profile=profile, user=request.user, service_code="topup", action="service_enabled", note="Top-up service enabled for cash use.")

    @admin.action(description="Suspend selected profiles")
    def suspend_selected_profiles(self, request, queryset):
        queryset.update(status="suspended")

    @admin.action(description="Release selected manual holds")
    def release_manual_hold(self, request, queryset):
        queryset.update(manual_hold=False, manual_hold_reason="")


@admin.register(ServiceAccess)
class ServiceAccessAdmin(admin.ModelAdmin):
    list_display = (
        "profile", "service_code", "is_enabled", "cash_enabled", "credit_enabled",
        "credit_locked", "credit_limit", "available_credit", "used_credit", "overdue_amount", "next_due_date",
    )
    list_filter = ("service_code", "is_enabled", "cash_enabled", "credit_enabled", "credit_locked", "auto_lock_on_overdue")
    search_fields = ("profile__unique_shop_id", "profile__shop_name", "profile__user__mobile_number")
    actions = [
        "enable_service", "disable_service", "enable_credit", "lock_credit",
        "unlock_credit", "mark_as_overdue", "clear_overdue",
    ]

    def save_model(self, request, obj, form, change):
        previous_limit = None
        if change:
            previous_limit = ServiceAccess.objects.get(pk=obj.pk).credit_limit
        obj.recalculate_balances()
        super().save_model(request, obj, form, change)
        if change and previous_limit != obj.credit_limit:
            AccountAuditLog.objects.create(
                profile=obj.profile, user=request.user, service_code=obj.service_code,
                action="limit_changed", note=f"Service limit changed from {previous_limit} to {obj.credit_limit}."
            )

    @admin.action(description="Enable selected services")
    def enable_service(self, request, queryset):
        for access in queryset:
            access.is_enabled = True
            access.save(update_fields=["is_enabled", "updated_at"])
            AccountAuditLog.objects.create(profile=access.profile, user=request.user, service_code=access.service_code, action="service_enabled", note="Service enabled.")

    @admin.action(description="Disable selected services")
    def disable_service(self, request, queryset):
        for access in queryset:
            access.is_enabled = False
            access.save(update_fields=["is_enabled", "updated_at"])
            AccountAuditLog.objects.create(profile=access.profile, user=request.user, service_code=access.service_code, action="service_disabled", note="Service disabled.")

    @admin.action(description="Enable credit for selected services")
    def enable_credit(self, request, queryset):
        for access in queryset:
            access.credit_enabled = True
            access.credit_locked = False if access.overdue_amount <= 0 else True
            access.lock_reason = "" if not access.credit_locked else access.lock_reason or "Credit locked due to overdue balance."
            access.recalculate_balances()
            access.save()
            AccountAuditLog.objects.create(profile=access.profile, user=request.user, service_code=access.service_code, action="credit_enabled", note="Service credit enabled.")

    @admin.action(description="Lock selected service credit")
    def lock_credit(self, request, queryset):
        for access in queryset:
            access.credit_locked = True
            access.lock_reason = access.lock_reason or "Locked manually from admin."
            access.save(update_fields=["credit_locked", "lock_reason", "updated_at"])
            AccountAuditLog.objects.create(profile=access.profile, user=request.user, service_code=access.service_code, action="credit_locked", note=access.lock_reason)

    @admin.action(description="Unlock selected service credit")
    def unlock_credit(self, request, queryset):
        for access in queryset:
            access.credit_locked = False
            access.lock_reason = ""
            access.save(update_fields=["credit_locked", "lock_reason", "updated_at"])
            AccountAuditLog.objects.create(profile=access.profile, user=request.user, service_code=access.service_code, action="credit_unlocked", note="Credit unlocked.")

    @admin.action(description="Mark selected service credit as overdue")
    def mark_as_overdue(self, request, queryset):
        for access in queryset:
            access.overdue_amount = max(access.overdue_amount, access.used_credit)
            access.credit_locked = True
            access.lock_reason = "Credit locked due to overdue balance."
            access.next_due_date = access.next_due_date or timezone.now()
            access.save(update_fields=["overdue_amount", "credit_locked", "lock_reason", "next_due_date", "updated_at"])
            AccountAuditLog.objects.create(profile=access.profile, user=request.user, service_code=access.service_code, action="overdue_marked", note="Service credit marked overdue.")

    @admin.action(description="Clear overdue for selected service credit")
    def clear_overdue(self, request, queryset):
        for access in queryset:
            access.overdue_amount = Decimal("0")
            access.recalculate_balances()
            access.credit_locked = False if access.credit_enabled else True
            access.lock_reason = "" if not access.credit_locked else access.lock_reason
            access.save()
            AccountAuditLog.objects.create(profile=access.profile, user=request.user, service_code=access.service_code, action="credit_unlocked", note="Overdue cleared and credit restored.")


@admin.register(AccountAuditLog)
class AccountAuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "profile", "service_code", "action", "user", "note")
    list_filter = ("action", "service_code")
    search_fields = ("profile__unique_shop_id", "profile__shop_name", "profile__user__mobile_number", "note")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ShopDocument)
class ShopDocumentAdmin(admin.ModelAdmin):
    list_display = ("profile", "document_type", "created_at")
    list_filter = ("document_type",)


@admin.register(CreditPeriod)
class CreditPeriodAdmin(admin.ModelAdmin):
    list_display = ("profile", "title", "status", "opening_limit", "used_amount", "receivable_amount", "profit_amount")
    list_filter = ("status",)
