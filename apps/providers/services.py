from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from apps.topup.models import TopUpTransaction

from .adapters import GenericHttpProviderAdapter, MockProviderAdapter
from .models import TopUpProvider


class ProviderRouter:
    """Priority-based provider routing with simple network and daily cap checks."""

    def available_providers(self, network: str | None = None):
        queryset = TopUpProvider.objects.filter(status="active").order_by("priority", "-success_rate", "name")
        providers = [provider for provider in queryset if provider.supports_network(network)]
        if not providers and network:
            providers = list(queryset)
        return providers

    def pick_provider(self, network: str | None = None):
        for provider in self.available_providers(network):
            if self._within_daily_cap(provider):
                return provider
        return None

    def fallback_providers(self, primary, network: str | None = None):
        return [provider for provider in self.available_providers(network) if provider.id != getattr(primary, 'id', None) and self._within_daily_cap(provider)]

    def get_adapter(self, provider):
        if provider.base_url:
            return GenericHttpProviderAdapter(provider)
        return MockProviderAdapter(provider)

    def _within_daily_cap(self, provider: TopUpProvider) -> bool:
        if not provider.daily_cap or provider.daily_cap <= 0:
            return True
        start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        used = TopUpTransaction.objects.filter(provider=provider, status="success", created_at__gte=start).aggregate(total=Sum("amount")).get("total") or Decimal("0")
        return used < provider.daily_cap
