from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.common.models import TimeStampedModel
from apps.common.utils import normalize_afghan_mobile


class User(AbstractUser):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("agent", "Agent"),
        ("shopkeeper", "Shopkeeper"),
        ("viewer", "Viewer"),
    ]
    APPROVAL_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("suspended", "Suspended"),
    ]

    username = models.CharField(max_length=150, unique=True)
    mobile_number = models.CharField(max_length=20, unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="shopkeeper")
    is_mobile_verified = models.BooleanField(default=False)
    approval_status = models.CharField(max_length=20, choices=APPROVAL_CHOICES, default="pending")
    approval_note = models.CharField(max_length=255, blank=True)
    is_reseller = models.BooleanField(default=True)

    REQUIRED_FIELDS = []
    EMAIL_FIELD = "email"

    def save(self, *args, **kwargs):
        self.mobile_number = normalize_afghan_mobile(self.mobile_number)
        if not self.username:
            self.username = self.mobile_number
        super().save(*args, **kwargs)

    @property
    def is_approved_reseller(self):
        return self.is_active and self.is_reseller and self.approval_status == "approved"

    def __str__(self):
        return self.mobile_number


class OTPRequest(TimeStampedModel):
    PURPOSE_CHOICES = [
        ("login", "Login"),
        ("register", "Register"),
    ]
    mobile_number = models.CharField(max_length=20, db_index=True)
    code = models.CharField(max_length=10)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES, default="login")
    is_used = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        self.mobile_number = normalize_afghan_mobile(self.mobile_number)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.mobile_number} - {self.code}"
