"""Product and subscription definition models.

Models from products.yaml configuration.
"""

from typing import Optional
from pydantic import BaseModel, Field


class ProductDefinition(BaseModel):
    """Product or subscription definition from configuration."""

    id: str = Field(..., description="Product or subscription ID")
    type: str = Field(..., description="Product type: 'inapp' or 'subs'")
    title: str = Field(..., description="Human-readable title")
    description: str = Field(..., description="Product description")
    price_micros: int = Field(..., description="Price in micros (1,000,000 = $1.00)")
    currency: str = Field(default="USD", description="ISO 4217 currency code")

    # Subscription-specific fields
    billing_period: Optional[str] = Field(None, description="ISO 8601 duration (e.g., P1Y, P1M)")
    trial_period: Optional[str] = Field(None, description="ISO 8601 trial duration (e.g., P30D)")
    grace_period: Optional[str] = Field(None, description="ISO 8601 grace period (e.g., P7D)")

    # Base plan and offer structure
    base_plan_id: Optional[str] = Field(None, description="Base plan identifier")
    offer_id: Optional[str] = Field(None, description="Promotional offer ID, null for base plan")

    # Additional metadata
    features: list[str] = Field(default_factory=list, description="List of features")
    max_users: Optional[int] = Field(None, description="Maximum users (for family plans)")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "premium.personal.yearly",
                "type": "subs",
                "title": "Premium Personal Yearly",
                "description": "Secure password management for one user",
                "price_micros": 29990000,
                "currency": "USD",
                "billing_period": "P1Y",
                "trial_period": "P30D",
                "grace_period": "P7D",
                "base_plan_id": "personal-yearly",
                "offer_id": None,
                "features": ["Unlimited passwords", "Secure vault"],
            }
        }


class PubSubConfig(BaseModel):
    """Pub/Sub configuration from products.yaml."""

    project_id: str = Field(..., description="GCP project ID")
    topic: str = Field(..., description="Pub/Sub topic name")
    default_subscription: str = Field(..., description="Default subscription name")


class SubscriptionBehaviorConfig(BaseModel):
    """Subscription behavior configuration for the emulator."""

    grace_period_behavior: str = Field(
        default="retain_access",
        description="User access during grace period: 'retain_access' or 'revoke_access'"
    )
    account_hold_behavior: str = Field(
        default="revoke_access",
        description="User access during account hold: 'retain_access' or 'revoke_access'"
    )
    allow_changes: bool = Field(
        default=True,
        description="Allow subscription changes (e.g., personal to family)"
    )
    proration_mode: str = Field(
        default="immediate_with_time_proration",
        description="Proration mode for subscription changes"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "grace_period_behavior": "retain_access",
                "account_hold_behavior": "revoke_access",
                "allow_changes": True,
                "proration_mode": "immediate_with_time_proration",
            }
        }


class EmulatorConfig(BaseModel):
    """Emulator behavior configuration."""

    auto_renew_enabled: bool = Field(default=True, description="Auto-renew subscriptions on time advance")
    rtdn_enabled: bool = Field(default=True, description="Send RTDN notifications")
    simulate_payment_failures: bool = Field(default=False, description="Simulate payment failures")
    payment_failure_rate: float = Field(default=0.05, description="Payment failure rate (0.0-1.0)")
    token_prefix: str = Field(default="emulator", description="Token prefix for generated tokens")
    token_length: int = Field(default=128, description="Length of generated tokens")
    subscriptions: SubscriptionBehaviorConfig = Field(
        default_factory=SubscriptionBehaviorConfig,
        description="Subscription behavior settings"
    )


class ProductsConfig(BaseModel):
    """Complete products.yaml configuration."""

    pubsub: PubSubConfig
    products: list[ProductDefinition] = Field(default_factory=list, description="One-time product definition")
    subscriptions:list[ProductDefinition] = Field(default_factory=list, description="Subscription definitions")
    default_package_name: str = Field(..., description="Default Android package name")
    emulator: EmulatorConfig = Field(default_factory=EmulatorConfig)
