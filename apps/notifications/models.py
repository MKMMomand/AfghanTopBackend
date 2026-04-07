from django.conf import settings
from django.db import models
from apps.common.models import TimeStampedModel

class Notification(TimeStampedModel):
    TYPE_CHOICES = [
        ("info", "Info"),
        ("warning", "Warning"),
        ("success", "Success"),
        ("error", "Error"),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=150)
    message = models.TextField()
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="info")
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return self.title
