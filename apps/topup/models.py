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
    provider = models.ForeignKey(TopUpProvider, null=True, blank=True, on_delete=models.SET_NULL, related_name="transactions")
    provider_reference = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    message = models.CharField(max_length=255, blank=True)

    @property
    def total_charge(self):
        return self.amount

    def __str__(self):
        return f"{self.profile.unique_shop_id} - {self.mobile_number} - {self.amount}"
