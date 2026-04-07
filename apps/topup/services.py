from datetime import timedelta
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from apps.providers.services import ProviderRouter
from apps.settlements.services import record_topup_debit
from apps.shopkeepers.models import AccountAuditLog, ServiceAccess
from .models import TopUpTransaction


def detect_network(mobile_number: str) -> str:
    prefixes = {
        "70": "AWCC",
        "71": "Salaam",
        "72": "Roshan",
        "73": "Etisalat",
        "74": "MTN",
        "76": "MTN",
        "77": "Etisalat",
        "78": "AWCC",
        "79": "Roshan",
    }
    compact = mobile_number.replace("+93", "")
    prefix = compact[:2]
    return prefixes.get(prefix, "Unknown")


def _get_topup_access(profile):
    access, _ = ServiceAccess.objects.get_or_create(profile=profile, service_code="topup")
    return access


@transaction.atomic
def execute_topup(profile, mobile_number, amount, network=None):
    if profile.status != "active":
        raise ValueError("Your account is not active for top-up transactions.")
    if profile.manual_hold:
        raise ValueError(profile.manual_hold_reason or "Your account is currently on hold. Please contact support.")

    access = _get_topup_access(profile)
    access.recalculate_balances()
    access.save()

    if not access.is_enabled:
        raise ValueError("Top-up service is not enabled for this account yet.")
    if not access.credit_enabled:
        raise ValueError("Top-up credit is not enabled for this account yet.")
    if access.credit_locked:
        raise ValueError(access.lock_reason or "Top-up credit is locked for this account.")
    if access.available_credit < amount:
        raise ValueError("Insufficient available top-up credit.")

    network = network or detect_network(mobile_number)
    router = ProviderRouter()
    provider = router.pick_provider(network=network)
    if not provider:
        raise ValueError("No active top-up provider is available.")

    providers_to_try = [provider, *router.fallback_providers(provider, network=network)]
    last_response = None

    for selected_provider in providers_to_try:
        adapter = router.get_adapter(selected_provider)
        response = adapter.topup(mobile_number=mobile_number, amount=amount, network=network)
        last_response = (selected_provider, response)
        if response.get("status") == "success":
            commission_percent = selected_provider.commission_percent
            commission_amount = (amount * commission_percent) / Decimal("100")
            tx = TopUpTransaction.objects.create(
                profile=profile,
                mobile_number=mobile_number,
                network=network,
                amount=amount,
                commission_percent=commission_percent,
                commission_amount=commission_amount,
                provider=selected_provider,
                provider_reference=response.get("provider_reference", ""),
                status="success",
                message=response.get("message", ""),
            )
            record_topup_debit(profile, tx, service_code="topup")
            access.used_credit = (access.used_credit or Decimal("0")) + amount
            access.next_due_date = access.next_due_date or (timezone.now() + timedelta(days=access.due_days or 7))
            access.recalculate_balances()
            access.save()
            AccountAuditLog.objects.create(
                profile=profile,
                user=profile.user,
                service_code="topup",
                action="limit_changed",
                note=f"Top-up debit of {amount} applied to service credit.",
                metadata={"mobile_number": mobile_number, "transaction_uuid": str(tx.uuid)},
            )
            return tx

    selected_provider, response = last_response
    return TopUpTransaction.objects.create(
        profile=profile,
        mobile_number=mobile_number,
        network=network,
        amount=amount,
        commission_percent=selected_provider.commission_percent,
        commission_amount=Decimal("0"),
        provider=selected_provider,
        provider_reference=response.get("provider_reference", ""),
        status="failed",
        message=response.get("message", "Top-up failed."),
    )
