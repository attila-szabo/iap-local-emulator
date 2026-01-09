"""Subscription state and lifecycle models.

Includes subscription states, renewal tracking, billing periods.
"""

from enum import IntEnum
from typing import Optional

from pydantic import BaseModel, Field


class SubscriptionState(IntEnum):
    """Subscription state enum matching Google Play values."""

    ACTIVE = 0  # Subscription is active
    CANCELED = 1  # Subscription canceled, still valid until expiry
    IN_GRACE_PERIOD = 2  # Payment failed, in grace period
    ON_HOLD = 3  # Payment failed, grace period expired, on hold
    PAUSED = 4  # Subscription paused by user
    EXPIRED = 5  # Subscription expired


class NotificationType(IntEnum):
    """RTDN notification types matching Google Play values."""

    SUBSCRIPTION_RECOVERED = 1  # Subscription recovered from account hold
    SUBSCRIPTION_RENEWED = 2  # Subscription renewed
    SUBSCRIPTION_CANCELED = 3  # Subscription voluntarily canceled
    SUBSCRIPTION_PURCHASED = 4  # New subscription purchased
    SUBSCRIPTION_ON_HOLD = 5  # Entered account hold (payment failed)
    SUBSCRIPTION_IN_GRACE_PERIOD = 6  # In grace period (payment failed)
    SUBSCRIPTION_RESTARTED = 7  # Subscription restarted after pause
    SUBSCRIPTION_PRICE_CHANGE_CONFIRMED = 8  # User confirmed price change
    SUBSCRIPTION_DEFERRED = 9  # Subscription renewal deferred
    SUBSCRIPTION_PAUSED = 10  # Subscription paused by user
    SUBSCRIPTION_PAUSE_SCHEDULE_CHANGED = 11  # Pause schedule changed
    SUBSCRIPTION_REVOKED = 12  # Subscription revoked before expiry
    SUBSCRIPTION_EXPIRED = 13  # Subscription expired


class PaymentState(IntEnum):
    """Payment state for subscriptions."""

    PAYMENT_PENDING = 0  # Payment pending
    PAYMENT_RECEIVED = 1  # Payment received
    FREE_TRIAL = 2  # Free trial, no payment
    PAYMENT_FAILED = 3  # Payment failed


class CancelReason(IntEnum):
    """Subscription cancellation reasons."""

    USER_CANCELED = 0  # User canceled
    SYSTEM_CANCELED = 1  # System canceled
    REPLACED = 2  # Replaced with new subscription
    DEVELOPER_CANCELED = 3  # Developer canceled


class SubscriptionRecord(BaseModel):
    """Internal subscription record tracking state and lifecycle."""

    token: str = Field(..., description="Unique purchase token")
    subscription_id: str = Field(..., description="Product subscription ID (e.g., premium.personal.yearly)")
    package_name: str = Field(..., description="Android package name")
    user_id: str = Field(..., description="User identifier for this subscription")

    # Timestamps
    start_time_millis: int = Field(..., description="Subscription start time (Unix millis)")
    expiry_time_millis: int = Field(..., description="Current expiry time (Unix millis)")
    purchase_time_millis: int = Field(..., description="Original purchase time (Unix millis)")

    # State
    state: SubscriptionState = Field(default=SubscriptionState.ACTIVE, description="Current subscription state")
    payment_state: PaymentState = Field(default=PaymentState.PAYMENT_RECEIVED, description="Payment state")
    auto_renewing: bool = Field(default=True, description="Whether subscription will auto-renew")

    # Cancellation
    cancel_reason: Optional[CancelReason] = Field(None, description="Reason for cancellation")
    canceled_time_millis: Optional[int] = Field(None, description="When subscription was canceled")

    # Trial
    in_trial: bool = Field(default=False, description="Whether in trial period")
    trial_expiry_millis: Optional[int] = Field(None, description="Trial expiry time")

    # Grace period and account hold
    grace_period_end_millis: Optional[int] = Field(None, description="Grace period end time")
    account_hold_start_millis: Optional[int] = Field(None, description="Account hold start time")

    # Pause
    pause_start_millis: Optional[int] = Field(None, description="Pause start time")
    pause_end_millis: Optional[int] = Field(None, description="Pause end time")

    # Acknowledgement
    acknowledgement_state: int = Field(default=0, description="Acknowledgement state (0=not acknowledged, 1=acknowledged)")

    # Renewal count
    renewal_count: int = Field(default=0, description="Number of times renewed")

    # Linked product info
    order_id: str = Field(..., description="Unique order ID")
    price_amount_micros: int = Field(..., description="Price paid in micros")
    price_currency_code: str = Field(default="USD", description="Currency code")

    def set_state(self, new_state: SubscriptionState, reason: Optional[str] = None) -> None:
        """Change subscription state and log the transition.

        Args:
            new_state: New state to transition to
            reason: Reason for state change
        """
        from iap_emulator.state_logger import log_subscription_state_change

        old_state = self.state
        if old_state != new_state:
            self.state = new_state
            log_subscription_state_change(
                token=self.token,
                subscription_id=self.subscription_id,
                old_state=old_state.name,
                new_state=new_state.name,
                reason=reason,
                user_id=self.user_id,
            )

    def set_payment_state(self, new_payment_state: PaymentState, reason: Optional[str] = None) -> None:
        """Change payment state and log the transition.

        Args:
            new_payment_state: New payment state
            reason: Reason for change
        """
        from iap_emulator.state_logger import log_payment_state_change

        old_state = self.payment_state
        if old_state != new_payment_state:
            self.payment_state = new_payment_state
            log_payment_state_change(
                token=self.token,
                subscription_id=self.subscription_id,
                old_payment_state=old_state.name,
                new_payment_state=new_payment_state.name,
                reason=reason,
                user_id=self.user_id,
            )

    def set_auto_renewing(self, auto_renewing: bool, reason: Optional[str] = None) -> None:
        """Change auto-renewing setting and log the change.

        Args:
            auto_renewing: New auto-renewing value
            reason: Reason for change
        """
        from iap_emulator.state_logger import log_auto_renew_change

        old_value = self.auto_renewing
        if old_value != auto_renewing:
            self.auto_renewing = auto_renewing
            log_auto_renew_change(
                token=self.token,
                subscription_id=self.subscription_id,
                old_value=old_value,
                new_value=auto_renewing,
                reason=reason,
                user_id=self.user_id,
            )

    def extend_expiry(self, new_expiry_millis: int, reason: str) -> None:
        """Extend subscription expiry and log the change.

        Args:
            new_expiry_millis: New expiry time in milliseconds
            reason: Reason for extension (renewal, grace period, etc.)
        """
        from iap_emulator.state_logger import log_expiry_change

        old_expiry = self.expiry_time_millis
        self.expiry_time_millis = new_expiry_millis
        log_expiry_change(
            token=self.token,
            subscription_id=self.subscription_id,
            old_expiry_millis=old_expiry,
            new_expiry_millis=new_expiry_millis,
            reason=reason,
            user_id=self.user_id,
            renewal_count=self.renewal_count,
        )

    def acknowledge(self) -> None:
        """Mark subscription as acknowledged.

        Idempotent operation - safe to call multiple times.
        """
        if self.acknowledgement_state != 1:
            self.acknowledgement_state = 1

    class Config:
        json_schema_extra = {
            "example": {
                "token": "emulator_abc123...",
                "subscription_id": "premium.personal.yearly",
                "package_name": "com.example.secureapp",
                "user_id": "user-123",
                "start_time_millis": 1700000000000,
                "expiry_time_millis": 1731536000000,
                "purchase_time_millis": 1700000000000,
                "state": SubscriptionState.ACTIVE,
                "payment_state": PaymentState.PAYMENT_RECEIVED,
                "auto_renewing": True,
                "in_trial": False,
                "renewal_count": 0,
                "order_id": "GPA.1234-5678-9012-34567",
                "price_amount_micros": 29990000,
                "price_currency_code": "USD",
            }
        }
