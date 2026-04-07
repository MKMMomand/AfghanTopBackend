from django.db import models
from apps.common.models import TimeStampedModel


class TopUpProvider(TimeStampedModel):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("maintenance", "Maintenance"),
    ]
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=50, unique=True)
    base_url = models.URLField(blank=True)
    auth_token = models.CharField(max_length=255, blank=True)
    priority = models.PositiveIntegerField(default=1)
    success_rate = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    supported_networks = models.CharField(max_length=255, blank=True, help_text="Comma-separated networks such as AWCC,Roshan")
    supports_auto_network_detection = models.BooleanField(default=True)
    daily_cap = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="0 means unlimited")
    extra_config = models.JSONField(default=dict, blank=True)

    def supports_network(self, network: str | None) -> bool:
        if not network:
            return True
        configured = [item.strip().lower() for item in (self.supported_networks or '').split(',') if item.strip()]
        return not configured or network.lower() in configured

    def __str__(self):
        return self.name


class ProviderLog(TimeStampedModel):
    provider = models.ForeignKey(TopUpProvider, on_delete=models.CASCADE, related_name="logs")
    action = models.CharField(max_length=50)
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    is_success = models.BooleanField(default=False)
    reference = models.CharField(max_length=120, blank=True)

    def __str__(self):
        return f"{self.provider.code} - {self.action}"
