from django.db import models
from apps.common.models import TimeStampedModel, UUIDModel
from apps.shopkeepers.models import ShopkeeperProfile
from apps.providers.models import TopUpProvider


class FavoriteNumber(TimeStampedModel):
    profile = models.ForeignKey(ShopkeeperProfile, on_delete=models.CASCADE, related_name="favorite_numbers")
    mobile_number = models.CharField(max_length=20)
    label = models.CharField(max_length=100, blank=True)
    network = models.CharField(max_length=50, blank=True)
    category = models.CharField(max_length=60, blank=True)

    class Meta:
        unique_together = ("profile", "mobile_number")

    def __str__(self):
        return f"{self.profile.unique_shop_id} - {self.mobile_number}"


class TopUpTransaction(TimeStampedModel, UUIDModel):
    STATUS_CHOICES = [("pending", "Pending"), ("success", "Success"), ("failed", "Failed"), ("reversed", "Reversed")]
    profile = models.ForeignKey(ShopkeeperProfile, on_delete=models.CASCADE, related_name="transactions")
    mobile_number = models.CharField(max_length=20)
    network = models.CharField(max_length=50, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    commission_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    provider_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    agent_profit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    platform_profit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    platform_commission_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    provider = models.ForeignKey(TopUpProvider, null=True, blank=True, on_delete=models.SET_NULL, related_name="transactions")
    provider_reference = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    message = models.CharField(max_length=255, blank=True)

    @property
    def total_charge(self):
        return self.amount

    def __str__(self):
        return f"{self.profile.unique_shop_id} - {self.mobile_number} - {self.amount}"


class CommissionRule(TimeStampedModel):
    SCOPE_CHOICES = [
        ("default", "Default"),
        ("provider", "Provider"),
        ("network", "Network"),
        ("profile", "Profile"),
    ]

    name = models.CharField(max_length=120)
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default="default")
    provider = models.ForeignKey(TopUpProvider, null=True, blank=True, on_delete=models.CASCADE, related_name="commission_rules")
    profile = models.ForeignKey(ShopkeeperProfile, null=True, blank=True, on_delete=models.CASCADE, related_name="commission_rules")
    network = models.CharField(max_length=50, blank=True)
    agent_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    platform_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["scope", "-priority", "name"]

    def __str__(self):
        return self.name


class ScheduledTopup(TimeStampedModel, UUIDModel):
    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("sent", "Sent"),
        ("cancelled", "Cancelled"),
        ("failed", "Failed"),
    ]
    REPEAT_CHOICES = [
        ("once", "Once"),
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
    ]

    profile = models.ForeignKey(ShopkeeperProfile, on_delete=models.CASCADE, related_name="scheduled_topups")
    mobile_number = models.CharField(max_length=20)
    network = models.CharField(max_length=50, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    schedule_for = models.DateTimeField()
    next_run_at = models.DateTimeField(null=True, blank=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    repeat_type = models.CharField(max_length=20, choices=REPEAT_CHOICES, default="once")
    is_active = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="scheduled")
    note = models.CharField(max_length=255, blank=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    last_transaction = models.ForeignKey(TopUpTransaction, null=True, blank=True, on_delete=models.SET_NULL, related_name="scheduled_entries")

    class Meta:
        ordering = ["next_run_at", "schedule_for", "-created_at"]

    def __str__(self):
        return f"{self.profile.unique_shop_id} - {self.mobile_number} - {self.schedule_for}"


class BulkTopupBatch(TimeStampedModel, UUIDModel):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("partial", "Partial"),
        ("failed", "Failed"),
    ]

    profile = models.ForeignKey(ShopkeeperProfile, on_delete=models.CASCADE, related_name="bulk_topup_batches")
    title = models.CharField(max_length=120, blank=True)
    note = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    total_items = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.profile.unique_shop_id} - bulk - {self.created_at:%Y-%m-%d %H:%M}"


class BulkTopupItem(TimeStampedModel, UUIDModel):
    STATUS_CHOICES = [("pending", "Pending"), ("success", "Success"), ("failed", "Failed")]

    batch = models.ForeignKey(BulkTopupBatch, on_delete=models.CASCADE, related_name="items")
    mobile_number = models.CharField(max_length=20)
    network = models.CharField(max_length=50, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    label = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    message = models.CharField(max_length=255, blank=True)
    transaction = models.ForeignKey(TopUpTransaction, null=True, blank=True, on_delete=models.SET_NULL, related_name="bulk_items")

    class Meta:
        ordering = ["created_at", "id"]


class CustomerReminder(TimeStampedModel, UUIDModel):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("done", "Done"),
        ("missed", "Missed"),
        ("cancelled", "Cancelled"),
    ]
    TYPE_CHOICES = [
        ("manual", "Manual"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
        ("smart", "Smart"),
    ]

    profile = models.ForeignKey(ShopkeeperProfile, on_delete=models.CASCADE, related_name="customer_reminders")
    favorite = models.ForeignKey(FavoriteNumber, null=True, blank=True, on_delete=models.SET_NULL, related_name="reminders")
    mobile_number = models.CharField(max_length=20)
    label = models.CharField(max_length=120, blank=True)
    network = models.CharField(max_length=50, blank=True)
    preferred_amount = models.DecimalField(max_digits=12, decimal_places=2, default=25)
    reminder_at = models.DateTimeField()
    reminder_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="manual")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    note = models.CharField(max_length=255, blank=True)
    last_topup = models.ForeignKey(TopUpTransaction, null=True, blank=True, on_delete=models.SET_NULL, related_name="reminder_entries")

    class Meta:
        ordering = ["reminder_at", "-created_at"]

    def __str__(self):
        return f"{self.profile.unique_shop_id} - reminder - {self.mobile_number}"
