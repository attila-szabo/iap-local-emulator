"""API request models for control endpoints."""

from typing import Optional

from pydantic import BaseModel, Field


class CreatePurchaseRequest(BaseModel):
    """Request to a new one-time product purchase via control API."""

    product_id: str = Field(..., description="Product ID to purchase (e.g. coins_100")
    user_id: str = Field(..., description="User Id for this purchase")
    package_name: Optional[str] = Field(None, description="Android package name")
    developer_payload: Optional[str] = Field(None, description="Optional developer-specified payload")

    class Config:
        json_schema_extra = {
            "example": {
                "product_id": "coins.100",
                "user_id": "user-123",
                "package_name": "com.example.app",
                "developer_payload": "test-payload",
            }
        }


class CreatePurchaseResponse(BaseModel):
    """Response after creating a purchase"""

    token: str = Field(..., description="Generated purchase token")
    product_id: str = Field(..., description="Product ID")
    user_id: str = Field(..., description="User identifier")
    order_id: str = Field(..., description="Order ID")
    purchase_time_millis: int = Field(..., description="Purchase time (Unix millis)")
    purchase_state: int = Field(..., description="Purchase state (0=purchased)")
    acknowledgement_state: int = Field(..., description="Acknowledgement state (0=not acknowledged)")
    consumption_state: int = Field(..., description="Consumption state (0=not consumed)")
    message: str = Field(..., description="Success message")

    class Config:
        json_schema_extra = {
            "example": {
                "token": "emulator_purchase_abc123...",
                "product_id": "coins.100",
                "user_id": "user-123",
                "order_id": "GPA.1234-5678-9012-34567",
                "purchase_time_millis": 1700000000000,
                "purchase_state": 0,
                "acknowledgement_state": 0,
                "consumption_state": 0,
                "message": "Purchase created successfully",
            }
        }


class CreateSubscriptionRequest(BaseModel):
    """Request to create a new subscription via control API."""

    subscription_id: str = Field(..., description="Subscription product ID (e.g., premium.personal.yearly)")
    user_id: str = Field(..., description="User identifier for this subscription")
    package_name: Optional[str] = Field(None, description="Android package name (uses default if not provided)")
    start_trial: bool = Field(default=False, description="Whether to start in trial period")

    class Config:
        json_schema_extra = {
            "example": {
                "subscription_id": "premium.personal.yearly",
                "user_id": "user-123",
                "package_name": "com.example.secureapp",
                "start_trial": False,
            }
        }


class CreateSubscriptionResponse(BaseModel):
    """Response after creating a subscription."""

    token: str = Field(..., description="Generated purchase token")
    subscription_id: str = Field(..., description="Subscription product ID")
    user_id: str = Field(..., description="User identifier")
    order_id: str = Field(..., description="Order ID")
    start_time_millis: int = Field(..., description="Start time (Unix millis)")
    expiry_time_millis: int = Field(..., description="Expiry time (Unix millis)")
    in_trial: bool = Field(..., description="Whether in trial period")
    message: str = Field(..., description="Success message")

    class Config:
        json_schema_extra = {
            "example": {
                "token": "emulator_abc123...",
                "subscription_id": "premium.personal.yearly",
                "user_id": "user-123",
                "order_id": "GPA.1234-5678-9012-34567",
                "start_time_millis": 1700000000000,
                "expiry_time_millis": 1731536000000,
                "in_trial": False,
                "message": "Subscription created successfully",
            }
        }


class AdvanceTimeRequest(BaseModel):
    """Request to advance virtual time."""

    days: Optional[int] = Field(None, description="Days to advance")
    hours: Optional[int] = Field(None, description="Hours to advance")
    minutes: Optional[int] = Field(None, description="Minutes to advance")

    class Config:
        json_schema_extra = {
            "example": {
                "days": 365,
                "hours": 0,
                "minutes": 0,
            }
        }


class AdvanceTimeResponse(BaseModel):
    """Response after advancing time."""

    previous_time_millis: int = Field(..., description="Previous virtual time")
    current_time_millis: int = Field(..., description="New virtual time")
    advanced_by_millis: int = Field(..., description="Time advanced in milliseconds")
    renewals_processed: int = Field(..., description="Number of renewals processed")
    expirations_processed: int = Field(..., description="Number of expirations processed")
    events_published: int = Field(..., description="Number of RTDN events published")
    message: str = Field(..., description="Success message")

    class Config:
        json_schema_extra = {
            "example": {
                "previous_time_millis": 1700000000000,
                "current_time_millis": 1731536000000,
                "advanced_by_millis": 31536000000,
                "renewals_processed": 5,
                "expirations_processed": 2,
                "events_published": 7,
                "message": "Advanced time by 365 days",
            }
        }


class CancelSubscriptionRequest(BaseModel):
    """Request to cancel a subscription."""

    cancel_reason: int = Field(default=0, description="Cancel reason (0=user, 1=system, 2=replaced, 3=developer)")
    immediate: bool = Field(
        default=False, description="If true, cancel immediately; if false, cancel at period end"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "cancel_reason": 0,
                "immediate": False,
            }
        }


class CancelSubscriptionResponse(BaseModel):
    """Response after canceling a subscription."""

    token: str = Field(..., description="Purchase token")
    canceled_time_millis: int = Field(..., description="Cancellation time")
    expiry_time_millis: int = Field(..., description="When subscription will expire")
    auto_renewing: bool = Field(..., description="Auto-renew status (should be false)")
    message: str = Field(..., description="Success message")

    class Config:
        json_schema_extra = {
            "example": {
                "token": "emulator_abc123...",
                "canceled_time_millis": 1700000000000,
                "expiry_time_millis": 1731536000000,
                "auto_renewing": False,
                "message": "Subscription canceled successfully",
            }
        }


class RenewSubscriptionResponse(BaseModel):
    """Response after renewing a subscription."""

    token: str = Field(..., description="Purchase token")
    previous_expiry_millis: int = Field(..., description="Previous expiry time")
    new_expiry_millis: int = Field(..., description="New expiry time")
    renewal_count: int = Field(..., description="Total renewal count")
    message: str = Field(..., description="Success message")

    class Config:
        json_schema_extra = {
            "example": {
                "token": "emulator_abc123...",
                "previous_expiry_millis": 1731536000000,
                "new_expiry_millis": 1763072000000,
                "renewal_count": 1,
                "message": "Subscription renewed successfully",
            }
        }


class PauseSubscriptionRequest(BaseModel):
    """Request to pause a subscription."""

    pause_duration_days: Optional[int] = Field(
        None, description="Duration to pause in days (if not specified, pauses indefinitely)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "pause_duration_days": 90,
            }
        }


class PauseSubscriptionResponse(BaseModel):
    """Response after pausing a subscription."""

    token: str = Field(..., description="Purchase token")
    pause_start_millis: int = Field(..., description="Pause start time")
    pause_end_millis: Optional[int] = Field(None, description="Pause end time (if duration specified)")
    message: str = Field(..., description="Success message")

    class Config:
        json_schema_extra = {
            "example": {
                "token": "emulator_abc123...",
                "pause_start_millis": 1700000000000,
                "pause_end_millis": 1707776000000,
                "message": "Subscription paused successfully",
            }
        }


class ResumeSubscriptionResponse(BaseModel):
    """Response after resuming a subscription."""

    token: str = Field(..., description="Purchase token")
    resume_time_millis: int = Field(..., description="Resume time")
    new_expiry_millis: int = Field(..., description="New expiry time")
    message: str = Field(..., description="Success message")

    class Config:
        json_schema_extra = {
            "example": {
                "token": "emulator_abc123...",
                "resume_time_millis": 1700000000000,
                "new_expiry_millis": 1731536000000,
                "message": "Subscription resumed successfully",
            }
        }


class PaymentFailedResponse(BaseModel):
    """Response after simulating payment failure."""

    token: str = Field(..., description="Purchase token")
    payment_failed_time_millis: int = Field(..., description="Payment failure time")
    grace_period_end_millis: Optional[int] = Field(None, description="Grace period end time")
    new_state: int = Field(..., description="New subscription state")
    message: str = Field(..., description="Success message")

    class Config:
        json_schema_extra = {
            "example": {
                "token": "emulator_abc123...",
                "payment_failed_time_millis": 1700000000000,
                "grace_period_end_millis": 1700604800000,
                "new_state": 2,  # IN_GRACE_PERIOD
                "message": "Payment failure simulated, subscription in grace period",
            }
        }


class ResetResponse(BaseModel):
    """Response after resetting emulator state."""

    subscriptions_deleted: int = Field(..., description="Number of subscriptions deleted")
    purchases_deleted: int = Field(..., description="Number of purchases deleted")
    time_reset: bool = Field(..., description="Whether time was reset")
    message: str = Field(..., description="Success message")

    class Config:
        json_schema_extra = {
            "example": {
                "subscriptions_deleted": 10,
                "purchases_deleted": 5,
                "time_reset": True,
                "message": "Emulator state reset successfully",
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(..., description="Error message")
    details: Optional[str] = Field(None, description="Additional error details")

    class Config:
        json_schema_extra = {
            "example": {
                "error": "Subscription not found",
                "details": "No subscription found with token: emulator_xyz...",
            }
        }


class SetTimeRequest(BaseModel):
    """Request to set virtual time to a specific timestamp."""

    time_millis: int = Field(..., description="Unix timestamp in milliseconds to set time to")

    class Config:
        json_schema_extra = {
            "example": {
                "time_millis": 1731536000000,
            }
        }


class SetTimeResponse(BaseModel):
    """Response after setting time."""

    previous_time_millis: int = Field(..., description="Previous virtual time")
    current_time_millis: int = Field(..., description="New virtual time (as set)")
    message: str = Field(..., description="Success message")

    class Config:
        json_schema_extra = {
            "example": {
                "previous_time_millis": 1700000000000,
                "current_time_millis": 1731536000000,
                "message": "Time set to 2024-11-14 00:00:00 UTC",
            }
        }


class ResetTimeResponse(BaseModel):
    """Response after resetting time to real time."""

    previous_time_millis: int = Field(..., description="Previous virtual time")
    current_time_millis: int = Field(..., description="Current real time")
    offset_cleared: bool = Field(..., description="Whether time offset was cleared")
    message: str = Field(..., description="Success message")

    class Config:
        json_schema_extra = {
            "example": {
                "previous_time_millis": 1731536000000,
                "current_time_millis": 1700000000000,
                "offset_cleared": True,
                "message": "Time reset to real current time",
            }
        }


class StatusResponse(BaseModel):
    """Emulator status response."""

    status: str = Field(..., description="Emulator status (running, idle)")
    current_time_millis: int = Field(..., description="Current virtual time")
    time_offset_millis: int = Field(..., description="Time offset from real time (0 if not set)")
    statistics: dict = Field(..., description="Statistics about stored data")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "running",
                "current_time_millis": 1700000000000,
                "time_offset_millis": 31536000000,
                "statistics": {
                    "total_purchases": 5,
                    "total_subscriptions": 10,
                    "active_subscriptions": 8,
                    "total_products": 6,
                },
            }
        }


class DeferSubscriptionRequest(BaseModel):
    """Request to defer a subscription renewal (Google Play API format).

    According to Android Publisher API v3, this extends the subscription's
    expiration time to the specified timestamp.
    """

    deferralInfo: dict = Field(
        ...,
        description="Deferral information containing expectedExpiryTimeMillis",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "deferralInfo": {
                    "expectedExpiryTimeMillis": "1763072000000",
                    "desiredExpiryTimeMillis": "1763072000000",
                }
            }
        }


class PaymentRecoveredResponse(BaseModel):
    """Response after recovering from payment failure."""

    token: str = Field(..., description="Purchase token")
    recovery_time_millis: int = Field(..., description="Payment recovery time")
    new_state: int = Field(..., description="New subscription state (should be ACTIVE)")
    new_expiry_millis: int = Field(..., description="New expiry time after recovery")
    message: str = Field(..., description="Success message")

    class Config:
        json_schema_extra = {
            "example": {
                "token": "emulator_abc123...",
                "recovery_time_millis": 1700000000000,
                "new_state": 0,  # ACTIVE
                "new_expiry_millis": 1731536000000,
                "message": "Payment recovered, subscription reactivated",
            }
        }
