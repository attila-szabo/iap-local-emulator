"""RTDN event models - DeveloperNotification and notification types.

Maps to Google Play Real-time Developer Notifications schema.
"""

from typing import Optional
from pydantic import BaseModel, Field

from .subscription import NotificationType


class SubscriptionNotification(BaseModel):
    """Subscription notification payload within DeveloperNotification."""

    version: str = Field(default="1.0", description="Notification version")
    notification_type: int = Field(..., description="Type of notification (1-13)")
    purchase_token: str = Field(..., description="Purchase token for the subscription")
    subscription_id: str = Field(..., description="Subscription product ID")

    class Config:
        json_schema_extra = {
            "example": {
                "version": "1.0",
                "notification_type": NotificationType.SUBSCRIPTION_RENEWED,
                "purchase_token": "emulator_abc123...",
                "subscription_id": "premium.personal.yearly",
            }
        }


class OneTimeProductNotification(BaseModel):
    """One-time product notification payload within DeveloperNotification."""

    version: str = Field(default="1.0", description="Notification version")
    notification_type: int = Field(..., description="Type of notification (1-4)")
    purchase_token: str = Field(..., description="Purchase token for the product")
    sku: str = Field(..., description="Product SKU/ID")

    class Config:
        json_schema_extra = {
            "example": {
                "version": "1.0",
                "notification_type": 1,  # ONE_TIME_PRODUCT_PURCHASED
                "purchase_token": "emulator_product_xyz789...",
                "sku": "com.example.premium_unlock",
            }
        }


class TestNotification(BaseModel):
    """Test notification for Pub/Sub configuration validation."""

    version: str = Field(default="1.0", description="Notification version")

    class Config:
        json_schema_extra = {"example": {"version": "1.0"}}


class DeveloperNotification(BaseModel):
    """Root RTDN message published to Pub/Sub.

    This matches the exact Google Play RTDN schema.
    """

    version: str = Field(default="1.0", description="Notification version")
    package_name: str = Field(..., description="Android package name")

    # Event timestamp
    event_time_millis: int = Field(..., description="Event timestamp (Unix millis)")

    # Only one of these will be populated per notification
    subscription_notification: Optional[SubscriptionNotification] = Field(
        None, description="Subscription event data"
    )
    one_time_product_notification: Optional[OneTimeProductNotification] = Field(
        None, description="One-time product event data"
    )
    test_notification: Optional[TestNotification] = Field(None, description="Test notification data")

    class Config:
        json_schema_extra = {
            "example": {
                "version": "1.0",
                "package_name": "com.example.secureapp",
                "event_time_millis": 1700000000000,
                "subscription_notification": {
                    "version": "1.0",
                    "notification_type": NotificationType.SUBSCRIPTION_RENEWED,
                    "purchase_token": "emulator_abc123...",
                    "subscription_id": "premium.personal.yearly",
                },
            }
        }
