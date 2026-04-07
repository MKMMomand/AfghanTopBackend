from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.notifications.models import Notification
from apps.shopkeepers.models import AccountAuditLog, CreditPeriod, ServiceAccess, ShopkeeperProfile
from apps.topup.models import TopUpTransaction

from .models import SettlementPayment, WalletLedgerEntry


def get_or_create_open_period(profile: ShopkeeperProfile) -> CreditPeriod:
    open_period = profile.credit_periods.filter(status="open").order_by("-opened_at").first()
    if open_period:
        needs_update = False
        credit_limit = profile.credit_limit or Decimal('0')
        if (open_period.opening_limit or Decimal('0')) <= 0 and credit_limit > 0:
            open_period.opening_limit = credit_limit
            needs_update = True
        if (open_period.closing_limit or Decimal('0')) <= 0 and credit_limit > 0:
            open_period.closing_limit = max(Decimal('0'), credit_limit - (open_period.used_amount or Decimal('0')) + (open_period.paid_amount or Decimal('0')))
            needs_update = True
        if needs_update:
            open_period.save(update_fields=["opening_limit", "closing_limit", "updated_at"])
        return open_period

    now = timezone.now()
    title = f"{now.strftime('%B %Y')} Cycle"
    outstanding = profile.outstanding_balance or Decimal('0')
    available = profile.available_limit or Decimal('0')
    credit_limit = profile.credit_limit or outstanding + available
    return CreditPeriod.objects.create(
        profile=profile,
        title=title,
        opening_limit=credit_limit,
        closing_limit=available,
        used_amount=outstanding,
        paid_amount=Decimal('0'),
        receivable_amount=outstanding,
        profit_amount=Decimal('0'),
        opened_at=now,
        status='open',
    )


def _recompute_profile_balances(profile: ShopkeeperProfile):
    debit_total = sum((entry.amount for entry in profile.wallet_ledger_entries.filter(entry_type__in=["topup_debit", "adjustment_debit"])), Decimal('0'))
    credit_total = sum((entry.amount for entry in profile.wallet_ledger_entries.filter(entry_type__in=["settlement_credit", "adjustment_credit"])), Decimal('0'))
    outstanding = max(Decimal('0'), debit_total - credit_total)
    available = max(Decimal('0'), (profile.credit_limit or Decimal('0')) - outstanding)
    profile.outstanding_balance = outstanding
    profile.available_limit = available
    profile.save(update_fields=["outstanding_balance", "available_limit", "updated_at"])
    return outstanding, available


def record_topup_debit(profile: ShopkeeperProfile, tx: TopUpTransaction, service_code: str = "topup"):
    period = get_or_create_open_period(profile)
    balance_after = (profile.outstanding_balance or Decimal('0')) + tx.amount
    WalletLedgerEntry.objects.create(
        profile=profile,
        credit_period=period,
        transaction=tx,
        entry_type="topup_debit",
        amount=tx.amount,
        balance_after=balance_after,
        note=f"Top-up for {tx.mobile_number}",
        metadata={"transaction_uuid": str(tx.uuid), "provider_reference": tx.provider_reference, "service_code": service_code},
    )

    period.used_amount += tx.amount
    period.receivable_amount += tx.amount
    period.profit_amount += tx.commission_amount
    period.closing_limit = max(Decimal('0'), period.opening_limit - period.used_amount + period.paid_amount)
    period.save(update_fields=["used_amount", "receivable_amount", "profit_amount", "closing_limit", "updated_at"])

    outstanding, available = _recompute_profile_balances(profile)

    if available <= (profile.low_limit_threshold or Decimal('0')):
        Notification.objects.create(
            user=profile.user,
            title="Low credit warning",
            message=f"Your available limit is now {available}. Please settle your balance soon.",
            type="warning",
        )

    return outstanding, available


@transaction.atomic
def create_settlement_payment(profile: ShopkeeperProfile, amount: Decimal, method: str = "cash", reference: str = "", note: str = "", service_code: str = "topup") -> SettlementPayment:
    if amount <= 0:
        raise ValueError("Settlement amount must be greater than zero.")
    if (profile.outstanding_balance or Decimal('0')) <= 0:
        raise ValueError("There is no outstanding balance to settle.")

    amount = min(amount, profile.outstanding_balance)
    period = get_or_create_open_period(profile)

    balance_after = max(Decimal('0'), (profile.outstanding_balance or Decimal('0')) - amount)
    ledger_entry = WalletLedgerEntry.objects.create(
        profile=profile,
        credit_period=period,
        entry_type="settlement_credit",
        amount=amount,
        balance_after=balance_after,
        note=note or "Settlement payment received",
        metadata={"reference": reference, "method": method, "service_code": service_code},
    )

    payment = SettlementPayment.objects.create(
        profile=profile,
        credit_period=period,
        amount=amount,
        method=method,
        status="approved",
        reference=reference,
        note=note,
        ledger_entry=ledger_entry,
        processed_at=timezone.now(),
    )

    period.paid_amount += amount
    period.receivable_amount = max(Decimal('0'), period.receivable_amount - amount)
    period.closing_limit = max(Decimal('0'), period.opening_limit - period.used_amount + period.paid_amount)
    if period.receivable_amount <= 0:
        period.status = "closed"
        period.closed_at = timezone.now()
    period.save(update_fields=["paid_amount", "receivable_amount", "closing_limit", "status", "closed_at", "updated_at"])

    _recompute_profile_balances(profile)

    access = ServiceAccess.objects.filter(profile=profile, service_code=service_code).first()
    if access:
        access.used_credit = max(Decimal('0'), (access.used_credit or Decimal('0')) - amount)
        access.overdue_amount = max(Decimal('0'), (access.overdue_amount or Decimal('0')) - amount)
        access.last_payment_at = timezone.now()
        if access.overdue_amount <= 0 and access.credit_enabled:
            access.credit_locked = False
            if access.lock_reason == "Credit locked due to overdue balance.":
                access.lock_reason = ""
        access.recalculate_balances()
        access.save()

    AccountAuditLog.objects.create(
        profile=profile,
        user=profile.user,
        service_code=service_code,
        action="payment_recorded",
        note=f"Payment of {amount} recorded for {service_code}.",
        metadata={"reference": reference, "method": method},
    )

    Notification.objects.create(
        user=profile.user,
        title="Settlement recorded",
        message=f"AFN {amount} was recorded against your outstanding balance.",
        type="success",
    )
    return payment


def settlement_overview_data(profile: ShopkeeperProfile) -> dict:
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    txs = TopUpTransaction.objects.filter(profile=profile, status="success")
    month_txs = txs.filter(created_at__gte=month_start)

    month_amount = sum((tx.amount for tx in month_txs), Decimal("0"))
    month_profit = sum((tx.commission_amount for tx in month_txs), Decimal("0"))
    total_amount = sum((tx.amount for tx in txs), Decimal("0"))
    total_profit = sum((tx.commission_amount for tx in txs), Decimal("0"))

    open_period = profile.credit_periods.filter(status="open").order_by("-opened_at").first()
    last_payment = profile.settlement_payments.filter(status="approved").first()
    recent_ledger = profile.wallet_ledger_entries.select_related("transaction").all()[:10]

    return {
        "profile_id": profile.id,
        "credit_limit": profile.credit_limit,
        "available_limit": profile.available_limit,
        "outstanding_balance": profile.outstanding_balance,
        "month_topup_amount": month_amount,
        "month_profit": month_profit,
        "total_topup_amount": total_amount,
        "total_profit": total_profit,
        "last_payment": last_payment,
        "recent_ledger": list(recent_ledger),
        "open_period": open_period,
    }
