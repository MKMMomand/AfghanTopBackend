from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel, UUIDModel


class ShopkeeperProfile(TimeStampedModel, UUIDModel):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("active", "Active"),
        ("suspended", "Suspended"),
        ("blocked", "Blocked"),
    ]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shopkeeper_profile")
    unique_shop_id = models.CharField(max_length=30, unique=True)
    full_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    shop_name = models.CharField(max_length=150, blank=True)
    owner_name = models.CharField(max_length=150, blank=True)
    address = models.TextField(blank=True)
    trade_license_number = models.CharField(max_length=100, blank=True)
    tazkira_number = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    is_kyc_verified = models.BooleanField(default=False)

    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    available_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    outstanding_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    low_limit_threshold = models.DecimalField(max_digits=12, decimal_places=2, default=500)

    manual_hold = models.BooleanField(default=False)
    manual_hold_reason = models.CharField(max_length=255, blank=True)
    internal_note = models.TextField(blank=True)

    def __str__(self):
        return f"{self.unique_shop_id} - {self.shop_name or self.user.mobile_number}"


class ShopDocument(TimeStampedModel):
    DOCUMENT_TYPES = [
        ("tazkira", "Tazkira"),
        ("license", "Trade License"),
        ("other", "Other"),
    ]
    profile = models.ForeignKey(ShopkeeperProfile, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    file = models.FileField(upload_to="shop_documents/")
    note = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.profile.unique_shop_id} - {self.document_type}"


class CreditPeriod(TimeStampedModel):
    STATUS_CHOICES = [
        ("open", "Open"),
        ("closed", "Closed"),
        ("overdue", "Overdue"),
    ]
    profile = models.ForeignKey(ShopkeeperProfile, on_delete=models.CASCADE, related_name="credit_periods")
    title = models.CharField(max_length=120)
    opening_limit = models.DecimalField(max_digits=12, decimal_places=2)
    closing_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    used_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    receivable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    profit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    opened_at = models.DateTimeField()
    closed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.profile.unique_shop_id} - {self.title}"


class ServiceAccess(TimeStampedModel):
    SERVICE_CHOICES = [
        ("topup", "Top-up"),
        ("data_bundle", "Data Bundle"),
        ("bill_payment", "Bill Payment"),
        ("money_transfer", "Money Transfer"),
        ("sim_services", "SIM Services"),
        ("other", "Other"),
    ]

    profile = models.ForeignKey(ShopkeeperProfile, on_delete=models.CASCADE, related_name="service_accesses")
    service_code = models.CharField(max_length=30, choices=SERVICE_CHOICES, default="topup")
    is_enabled = models.BooleanField(default=False)
    cash_enabled = models.BooleanField(default=False)
    credit_enabled = models.BooleanField(default=False)
    credit_locked = models.BooleanField(default=True)
    lock_reason = models.CharField(max_length=255, blank=True)
    admin_note = models.CharField(max_length=255, blank=True)

    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    available_credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    used_credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overdue_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    allow_credit_for_topup_only = models.BooleanField(default=True)
    auto_lock_on_overdue = models.BooleanField(default=True)
    due_days = models.PositiveIntegerField(default=7)
    next_due_date = models.DateTimeField(null=True, blank=True)
    last_payment_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("profile", "service_code")
        ordering = ["service_code", "profile_id"]

    def __str__(self):
        return f"{self.profile.unique_shop_id} - {self.service_code}"

    @property
    def is_overdue(self):
        return self.overdue_amount > 0 or (self.next_due_date and self.next_due_date < timezone.now() and self.used_credit > 0)

    def recalculate_balances(self):
        self.available_credit = max(Decimal("0"), (self.credit_limit or Decimal("0")) - (self.used_credit or Decimal("0")))
        if self.auto_lock_on_overdue and self.is_overdue:
            self.credit_locked = True
            if not self.lock_reason:
                self.lock_reason = "Credit locked due to overdue balance."
        elif not self.is_overdue and self.credit_enabled and (self.credit_limit or Decimal("0")) > 0 and self.lock_reason == "Credit locked due to overdue balance.":
            self.credit_locked = False
            self.lock_reason = ""


class AccountAuditLog(TimeStampedModel):
    ACTION_CHOICES = [
        ("application_created", "Application Created"),
        ("application_approved", "Application Approved"),
        ("application_rejected", "Application Rejected"),
        ("profile_activated", "Profile Activated"),
        ("service_enabled", "Service Enabled"),
        ("service_disabled", "Service Disabled"),
        ("credit_enabled", "Credit Enabled"),
        ("credit_locked", "Credit Locked"),
        ("credit_unlocked", "Credit Unlocked"),
        ("limit_changed", "Limit Changed"),
        ("payment_recorded", "Payment Recorded"),
        ("overdue_marked", "Overdue Marked"),
    ]

    profile = models.ForeignKey(ShopkeeperProfile, on_delete=models.CASCADE, related_name="audit_logs")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="account_audit_logs")
    service_code = models.CharField(max_length=30, blank=True)
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    note = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.profile.unique_shop_id} - {self.action}"
