from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.providers.models import TopUpProvider
from apps.shopkeepers.models import CreditPeriod, ShopkeeperProfile


class Command(BaseCommand):
    help = "Seed a demo shopkeeper and provider for Afghan Top testing."

    def handle(self, *args, **options):
        User = get_user_model()
        user, _ = User.objects.get_or_create(
            mobile_number="+93700111222",
            defaults={
                "username": "+93700111222",
                "first_name": "Demo",
                "last_name": "Shop",
                "role": "shopkeeper",
                "is_mobile_verified": True,
            },
        )
        provider, _ = TopUpProvider.objects.get_or_create(
            code="mock-primary",
            defaults={
                "name": "Mock Primary Provider",
                "priority": 1,
                "commission_percent": Decimal("3.50"),
                "status": "active",
                "supported_networks": "AWCC,Roshan,Etisalat,Salaam,MTN",
                "daily_cap": Decimal("0"),
            },
        )
        TopUpProvider.objects.get_or_create(
            code="mock-backup",
            defaults={
                "name": "Mock Backup Provider",
                "priority": 2,
                "commission_percent": Decimal("3.00"),
                "status": "active",
                "supported_networks": "AWCC,Roshan,Etisalat,Salaam,MTN",
                "daily_cap": Decimal("0"),
            },
        )
        profile, _ = ShopkeeperProfile.objects.get_or_create(
            user=user,
            defaults={
                "unique_shop_id": "SHOP-000001",
                "full_name": "Demo Shopkeeper",
                "shop_name": "Afghan Top Test Shop",
                "owner_name": "Demo Owner",
                "address": "Kabul",
                "status": "active",
                "credit_limit": Decimal("100000"),
                "available_limit": Decimal("100000"),
                "low_limit_threshold": Decimal("5000"),
            },
        )
        CreditPeriod.objects.get_or_create(
            profile=profile,
            status="open",
            defaults={
                "title": timezone.now().strftime("%B %Y"),
                "opening_limit": profile.credit_limit,
                "closing_limit": profile.available_limit,
                "used_amount": Decimal("0"),
                "paid_amount": Decimal("0"),
                "receivable_amount": Decimal("0"),
                "profit_amount": Decimal("0"),
                "opened_at": timezone.now(),
            },
        )
        self.stdout.write(self.style.SUCCESS(f"Demo data ready. User={user.mobile_number}, Primary Provider={provider.name}"))
