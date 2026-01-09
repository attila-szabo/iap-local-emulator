"""API response models matching Android Publisher API v3 schema.

ProductPurchase and SubscriptionPurchase response formats.
"""

from typing import Optional

from pydantic import BaseModel, Field


class ProductPurchase(BaseModel):
    """Response for GET /androidpublisher/v3/.../products/{productId}/tokens/{token}

    Matches Google Play Android Publisher API v3 ProductPurchase schema.
    """

    kind: str = Field(default="androidpublisher#productPurchase", description="Resource type")
    purchaseTimeMillis: str = Field(..., description="Purchase time (Unix millis as string)")
    purchaseState: int = Field(..., description="Purchase state (0=purchased, 1=canceled, 2=pending)")
    consumptionState: int = Field(..., description="Consumption state (0=not consumed, 1=consumed)")
    developerPayload: Optional[str] = Field(None, description="Developer-specified payload")
    orderId: str = Field(..., description="Unique order ID")
    acknowledgementState: int = Field(..., description="Acknowledgement state (0=not acked, 1=acked)")
    purchaseToken: str = Field(..., description="Purchase token")
    productId: str = Field(..., description="Product SKU/ID")
    quantity: int = Field(default=1, description="Quantity purchased")
    obfuscatedExternalAccountId: Optional[str] = Field(None, description="Obfuscated account ID")
    obfuscatedExternalProfileId: Optional[str] = Field(None, description="Obfuscated profile ID")
    regionCode: str = Field(default="US", description="Region code")

    class Config:
        json_schema_extra = {
            "example": {
                "kind": "androidpublisher#productPurchase",
                "purchaseTimeMillis": "1700000000000",
                "purchaseState": 0,
                "consumptionState": 0,
                "orderId": "GPA.9876-5432-1098-76543",
                "acknowledgementState": 0,
                "purchaseToken": "emulator_product_xyz789...",
                "productId": "com.example.premium_unlock",
                "quantity": 1,
                "regionCode": "US",
            }
        }


class SubscriptionPurchase(BaseModel):
    """Response for GET /androidpublisher/v3/.../subscriptions/{subscriptionId}/tokens/{token}

    Matches Google Play Android Publisher API v3 SubscriptionPurchase schema.
    """

    kind: str = Field(default="androidpublisher#subscriptionPurchase", description="Resource type")
    startTimeMillis: str = Field(..., description="Subscription start time (Unix millis as string)")
    expiryTimeMillis: str = Field(..., description="Subscription expiry time (Unix millis as string)")
    autoResumeTimeMillis: Optional[str] = Field(None, description="Auto-resume time for paused subscriptions")
    autoRenewing: bool = Field(..., description="Whether subscription will auto-renew")
    priceCurrencyCode: str = Field(..., description="ISO 4217 currency code")
    priceAmountMicros: str = Field(..., description="Price in micros (as string)")
    countryCode: str = Field(default="US", description="ISO 3166-1 alpha-2 country code")
    developerPayload: Optional[str] = Field(None, description="Developer-specified payload")
    paymentState: Optional[int] = Field(None, description="Payment state (0=pending, 1=received, 2=trial, 3=failed)")
    cancelReason: Optional[int] = Field(None, description="Cancel reason (0=user, 1=system, 2=replaced, 3=developer)")
    userCancellationTimeMillis: Optional[str] = Field(None, description="User cancellation time")
    orderId: str = Field(..., description="Unique order ID")
    linkedPurchaseToken: Optional[str] = Field(None, description="Token of related purchase")
    purchaseType: Optional[int] = Field(None, description="Purchase type (0=test, 1=promo, 2=rewarded)")
    acknowledgementState: int = Field(default=0, description="Acknowledgement state (0=not acked, 1=acked)")
    obfuscatedExternalAccountId: Optional[str] = Field(None, description="Obfuscated account ID")
    obfuscatedExternalProfileId: Optional[str] = Field(None, description="Obfuscated profile ID")
    profileName: Optional[str] = Field(None, description="Profile name")
    emailAddress: Optional[str] = Field(None, description="User email address")
    givenName: Optional[str] = Field(None, description="User given name")
    familyName: Optional[str] = Field(None, description="User family name")
    profileId: Optional[str] = Field(None, description="Profile ID")
    purchaseToken: str = Field(..., description="Purchase token")

    class Config:
        json_schema_extra = {
            "example": {
                "kind": "androidpublisher#subscriptionPurchase",
                "startTimeMillis": "1700000000000",
                "expiryTimeMillis": "1731536000000",
                "autoRenewing": True,
                "priceCurrencyCode": "USD",
                "priceAmountMicros": "29990000",
                "countryCode": "US",
                "paymentState": 1,
                "orderId": "GPA.1234-5678-9012-34567",
                "acknowledgementState": 0,
                "purchaseToken": "emulator_abc123...",
            }
        }


class SubscriptionPurchaseV2(BaseModel):
    """Response for Android Publisher API v2 subscription format (extended).

    Includes additional fields for subscription states, grace period, account hold, etc.
    """

    kind: str = Field(default="androidpublisher#subscriptionPurchaseV2", description="Resource type")
    startTime: str = Field(..., description="Subscription start time (RFC 3339)")
    regionCode: str = Field(default="US", description="Region code")
    subscriptionState: int = Field(..., description="Subscription state (0-5)")
    latestOrderId: str = Field(..., description="Latest order ID")
    acknowledgementState: int = Field(default=0, description="Acknowledgement state")
    externalAccountId: Optional[str] = Field(None, description="External account ID")
    canceledStateContext: Optional[dict] = Field(None, description="Cancellation context")
    pausedStateContext: Optional[dict] = Field(None, description="Pause context")

    class Config:
        json_schema_extra = {
            "example": {
                "kind": "androidpublisher#subscriptionPurchaseV2",
                "startTime": "2023-11-14T12:00:00.000Z",
                "regionCode": "US",
                "subscriptionState": 0,
                "latestOrderId": "GPA.1234-5678-9012-34567",
                "acknowledgementState": 0,
            }
        }
