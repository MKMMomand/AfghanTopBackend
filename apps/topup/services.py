from calendar import monthrange
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.providers.services import ProviderRouter
from apps.settlements.services import record_topup_debit
from apps.shopkeepers.models import AccountAuditLog, ServiceAccess

from .models import BulkTopupBatch, BulkTopupItem, ScheduledTopup, TopUpTransaction


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
    if compact.startswith("0"):
        compact = compact[1:]
    prefix = compact[:2]
    return prefixes.get(prefix, "Unknown")


def _get_topup_access(profile):
    access, _ = ServiceAccess.objects.get_or_create(profile=profile, service_code="topup")
    return access


def _validate_provider_rules(provider, amount: Decimal):
    cfg = provider.extra_config or {}
    min_amount = Decimal(str(cfg.get("min_amount", "0") or "0"))
    max_amount = Decimal(str(cfg.get("max_amount", "0") or "0"))
    if min_amount and amount < min_amount:
        raise ValueError(f"Minimum top-up amount for {provider.name} is {int(min_amount)} AFN.")
    if max_amount and amount > max_amount:
        raise ValueError(f"Maximum top-up amount for {provider.name} is {int(max_amount)} AFN.")


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
        _validate_provider_rules(selected_provider, amount)
        adapter = router.get_adapter(selected_provider)
        response = adapter.topup(mobile_number=mobile_number, amount=amount, network=network)
        last_response = (selected_provider, response)
        status_value = response.get("status")

        if status_value in {"success", "pending"}:
            commission_percent = selected_provider.commission_percent if status_value == "success" else Decimal("0")
            commission_amount = (amount * commission_percent) / Decimal("100") if status_value == "success" else Decimal("0")
            tx = TopUpTransaction.objects.create(
                profile=profile,
                mobile_number=mobile_number,
                network=network,
                amount=amount,
                commission_percent=commission_percent,
                commission_amount=commission_amount,
                provider=selected_provider,
                provider_reference=response.get("provider_reference", ""),
                status="success" if status_value == "success" else "pending",
                message=response.get("message", ""),
            )
            if status_value == "success":
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


@transaction.atomic
def refresh_transaction_status(tx: TopUpTransaction):
    if tx.status != "pending" or not tx.provider or not tx.provider_reference:
        return tx
    router = ProviderRouter()
    adapter = router.get_adapter(tx.provider)
    result = adapter.order_status(tx.provider_reference)
    if result.get("status") == "success":
        profile = tx.profile
        access = _get_topup_access(profile)
        access.recalculate_balances()
        access.save()
        if access.available_credit < tx.amount:
            tx.message = "Top-up provider marked the order successful, but available credit is not enough to settle it. Please review manually."
            tx.save(update_fields=["message", "updated_at"])
            return tx
        tx.status = "success"
        tx.message = result.get("message", tx.message)
        tx.save(update_fields=["status", "message", "updated_at"])
        record_topup_debit(profile, tx, service_code="topup")
        access.used_credit = (access.used_credit or Decimal("0")) + tx.amount
        access.next_due_date = access.next_due_date or (timezone.now() + timedelta(days=access.due_days or 7))
        access.recalculate_balances()
        access.save()
        AccountAuditLog.objects.create(
            profile=profile,
            user=profile.user,
            service_code="topup",
            action="limit_changed",
            note=f"Pending top-up debit of {tx.amount} settled after provider confirmation.",
            metadata={"mobile_number": tx.mobile_number, "transaction_uuid": str(tx.uuid), "provider_reference": tx.provider_reference},
        )
    elif result.get("status") == "failed":
        tx.status = "failed"
        tx.message = result.get("message", tx.message)
        tx.save(update_fields=["status", "message", "updated_at"])
    else:
        tx.message = result.get("message", tx.message)
        tx.save(update_fields=["message", "updated_at"])
    return tx


def get_provider_wallet_balance(provider):
    router = ProviderRouter()
    adapter = router.get_adapter(provider)
    return adapter.wallet_balance()


def _advance_next_run(entry: ScheduledTopup):
    base = entry.next_run_at or entry.schedule_for
    if entry.repeat_type == "daily":
        return base + timedelta(days=1)
    if entry.repeat_type == "weekly":
        return base + timedelta(days=7)
    if entry.repeat_type == "monthly":
        year = base.year + (1 if base.month == 12 else 0)
        month = 1 if base.month == 12 else base.month + 1
        day = min(base.day, monthrange(year, month)[1])
        return base.replace(year=year, month=month, day=day)
    return None


def process_due_scheduled_topups(limit=50, profile=None):
    now = timezone.now()
    qs = ScheduledTopup.objects.select_related("profile").filter(
        is_active=True,
        status__in=["scheduled", "failed"],
        next_run_at__lte=now,
    )
    if profile is not None:
        qs = qs.filter(profile=profile)
    due_entries = qs.order_by("next_run_at")[:limit]

    processed = 0
    for entry in due_entries:
        try:
            tx = execute_topup(
                profile=entry.profile,
                mobile_number=entry.mobile_number,
                amount=entry.amount,
                network=entry.network,
            )
            entry.last_transaction = tx
            entry.last_run_at = now
            if tx.status in {"success", "pending"}:
                entry.status = "sent" if tx.status == "success" else "scheduled"
                entry.failure_reason = ""
                next_run = _advance_next_run(entry)
                if next_run is None:
                    entry.is_active = tx.status == "pending"
                    entry.next_run_at = None if tx.status == "success" else entry.schedule_for
                else:
                    entry.status = "scheduled"
                    entry.next_run_at = next_run
            else:
                entry.status = "failed"
                entry.failure_reason = tx.message or "Scheduled top-up failed."
        except Exception as exc:
            entry.status = "failed"
            entry.failure_reason = str(exc)
            entry.last_run_at = now
        entry.save(update_fields=["last_transaction", "last_run_at", "status", "failure_reason", "is_active", "next_run_at", "updated_at"])
        processed += 1
    return processed


@transaction.atomic
def execute_bulk_topup(profile, items, title="", note=""):
    batch = BulkTopupBatch.objects.create(
        profile=profile,
        title=title,
        note=note,
        status="pending",
        total_items=len(items),
        total_amount=sum([item["amount"] for item in items], Decimal("0")),
    )

    success_count = 0
    failed_count = 0
    for item in items:
        try:
            tx = execute_topup(
                profile=profile,
                mobile_number=item["mobile_number"],
                amount=item["amount"],
                network=item.get("network") or None,
            )
            item_status = "success" if tx.status in {"success", "pending"} else "failed"
            if item_status == "success":
                success_count += 1
            else:
                failed_count += 1
            BulkTopupItem.objects.create(
                batch=batch,
                mobile_number=item["mobile_number"],
                network=item.get("network", ""),
                amount=item["amount"],
                label=item.get("label", ""),
                status=item_status,
                message=tx.message,
                transaction=tx,
            )
        except Exception as exc:
            failed_count += 1
            BulkTopupItem.objects.create(
                batch=batch,
                mobile_number=item["mobile_number"],
                network=item.get("network", ""),
                amount=item["amount"],
                label=item.get("label", ""),
                status="failed",
                message=str(exc),
            )

    batch.success_count = success_count
    batch.failed_count = failed_count
    if success_count == batch.total_items:
        batch.status = "completed"
    elif success_count > 0:
        batch.status = "partial"
    else:
        batch.status = "failed"
    batch.save(update_fields=["success_count", "failed_count", "status", "updated_at"])
    return batch
