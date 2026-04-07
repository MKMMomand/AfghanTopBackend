from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.notifications.models import Notification
from apps.settlements.models import WalletLedgerEntry
from apps.settlements.services import _recompute_profile_balances
from apps.shopkeepers.models import AccountAuditLog, CreditPeriod, ServiceAccess, ShopkeeperProfile


def _ensure_topup_access(profile: ShopkeeperProfile) -> ServiceAccess:
    access, _ = ServiceAccess.objects.get_or_create(profile=profile, service_code="topup")
    return access


@transaction.atomic
def apply_shopkeeper_decision(*, profile: ShopkeeperProfile, actor, action: str, note: str = "", enable_topup_service: bool = True, enable_credit: bool = True, credit_limit: Decimal = Decimal("5000.00"), low_limit_threshold: Decimal = Decimal("500.00")):
    user = profile.user
    access = _ensure_topup_access(profile)

    if action == "approve":
        user.approval_status = "approved"
        user.approval_note = note
        user.is_active = True
        profile.status = "active"
        profile.manual_hold = False
        profile.manual_hold_reason = ""
        profile.credit_limit = credit_limit
        profile.low_limit_threshold = low_limit_threshold
        if (profile.available_limit or Decimal("0")) <= 0 and (profile.outstanding_balance or Decimal("0")) <= 0:
            profile.available_limit = credit_limit
        access.is_enabled = enable_topup_service
        access.cash_enabled = True
        access.credit_enabled = enable_credit
        access.credit_limit = credit_limit
        access.used_credit = access.used_credit or Decimal("0")
        access.credit_locked = not enable_credit
        access.lock_reason = "" if enable_credit else "Credit disabled by admin."
        access.recalculate_balances()
        action_code = "application_approved"
        notification_title = "Application approved"
        notification_message = "Your Afghan Top reseller account is now approved."
        notification_type = "success"
    elif action == "reject":
        user.approval_status = "rejected"
        user.approval_note = note
        profile.status = "blocked"
        profile.manual_hold = True
        profile.manual_hold_reason = note or "Application rejected."
        access.is_enabled = False
        access.credit_enabled = False
        access.credit_locked = True
        access.lock_reason = note or "Application rejected."
        action_code = "application_rejected"
        notification_title = "Application rejected"
        notification_message = note or "Your application was rejected. Please contact support."
        notification_type = "warning"
    elif action == "suspend":
        user.approval_status = "suspended"
        user.approval_note = note
        profile.status = "suspended"
        profile.manual_hold = True
        profile.manual_hold_reason = note or "Account suspended."
        access.credit_locked = True
        access.lock_reason = note or "Account suspended."
        action_code = "credit_locked"
        notification_title = "Account suspended"
        notification_message = note or "Your account was suspended by admin."
        notification_type = "warning"
    else:
        user.approval_status = "approved"
        user.approval_note = note
        user.is_active = True
        profile.status = "active"
        profile.manual_hold = False
        profile.manual_hold_reason = ""
        access.is_enabled = True
        access.credit_enabled = True
        access.credit_locked = False if (access.credit_limit or Decimal("0")) > 0 else True
        access.lock_reason = "" if (access.credit_limit or Decimal("0")) > 0 else "No credit limit configured."
        access.recalculate_balances()
        action_code = "profile_activated"
        notification_title = "Account reactivated"
        notification_message = note or "Your account is active again."
        notification_type = "success"

    user.save(update_fields=["approval_status", "approval_note", "is_active"])
    profile.save()
    access.save()

    AccountAuditLog.objects.create(
        profile=profile,
        user=actor,
        service_code="topup",
        action=action_code,
        note=note,
        metadata={"action": action},
    )
    Notification.objects.create(
        user=user,
        title=notification_title,
        message=notification_message,
        type=notification_type,
    )
    return profile


@transaction.atomic
def apply_credit_adjustment(*, profile: ShopkeeperProfile, actor, adjustment_type: str, amount: Decimal, reason: str, service_code: str = "topup"):
    access = _ensure_topup_access(profile)
    period = profile.credit_periods.filter(status="open").order_by("-opened_at").first()
    if not period:
        now = timezone.now()
        period = CreditPeriod.objects.create(
            profile=profile,
            title=f"{now.strftime('%B %Y')} Cycle",
            opening_limit=profile.credit_limit or Decimal("0"),
            closing_limit=profile.available_limit or Decimal("0"),
            used_amount=profile.outstanding_balance or Decimal("0"),
            paid_amount=Decimal("0"),
            receivable_amount=profile.outstanding_balance or Decimal("0"),
            profit_amount=Decimal("0"),
            opened_at=now,
            status="open",
        )

    entry_type = "adjustment_credit" if adjustment_type == "credit" else "adjustment_debit"
    current_outstanding = profile.outstanding_balance or Decimal("0")
    balance_after = max(Decimal("0"), current_outstanding - amount) if adjustment_type == "credit" else current_outstanding + amount

    WalletLedgerEntry.objects.create(
        profile=profile,
        credit_period=period,
        entry_type=entry_type,
        amount=amount,
        balance_after=balance_after,
        note=reason,
        metadata={"service_code": service_code, "adjusted_by": actor.username if actor else ""},
    )

    outstanding, available = _recompute_profile_balances(profile)
    access.used_credit = outstanding
    access.credit_limit = profile.credit_limit
    access.recalculate_balances()
    if adjustment_type == "credit" and (access.overdue_amount or Decimal("0")) > 0:
        access.overdue_amount = max(Decimal("0"), (access.overdue_amount or Decimal("0")) - amount)
    access.save()

    AccountAuditLog.objects.create(
        profile=profile,
        user=actor,
        service_code=service_code,
        action="payment_recorded" if adjustment_type == "credit" else "limit_changed",
        note=reason,
        metadata={"adjustment_type": adjustment_type, "amount": str(amount)},
    )
    Notification.objects.create(
        user=profile.user,
        title="Wallet adjusted",
        message=f"AFN {amount} was {'added back' if adjustment_type == 'credit' else 'debited'} by admin. Reason: {reason}",
        type="info",
    )
    return {"outstanding_balance": outstanding, "available_limit": available}
