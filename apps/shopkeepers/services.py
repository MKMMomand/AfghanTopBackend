from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
from apps.topup.models import TopUpTransaction

def shop_dashboard_summary(profile):
    now = timezone.now()
    start_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    txs = TopUpTransaction.objects.filter(profile=profile, status="success")
    daily = txs.filter(created_at__gte=start_day)
    monthly = txs.filter(created_at__gte=start_month)

    daily_amount = sum((tx.amount for tx in daily), Decimal("0"))
    monthly_amount = sum((tx.amount for tx in monthly), Decimal("0"))
    total_amount = sum((tx.amount for tx in txs), Decimal("0"))

    return {
        "shopkeeper": profile,
        "daily_count": daily.count(),
        "monthly_count": monthly.count(),
        "total_count": txs.count(),
        "daily_amount": daily_amount,
        "monthly_amount": monthly_amount,
        "total_amount": total_amount,
        "low_limit_warning": profile.available_limit <= profile.low_limit_threshold,
    }
