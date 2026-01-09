"""Pydantic models for API requests, responses, and domain objects."""

# Product configuration models
# API request models (Control API)
from .api_request import (
    AdvanceTimeRequest,
    AdvanceTimeResponse,
    CancelSubscriptionRequest,
    CancelSubscriptionResponse,
    CreatePurchaseRequest,
    CreatePurchaseResponse,
    CreateSubscriptionRequest,
    CreateSubscriptionResponse,
    ErrorResponse,
    PauseSubscriptionRequest,
    PauseSubscriptionResponse,
    PaymentFailedResponse,
    RenewSubscriptionResponse,
    ResetResponse,
    ResumeSubscriptionResponse,
)

# API response models (Android Publisher API v3)
from .api_response import (
    ProductPurchase,
    SubscriptionPurchase,
    SubscriptionPurchaseV2,
)

# Event models (RTDN)
from .events import (
    DeveloperNotification,
    OneTimeProductNotification,
    SubscriptionNotification,
    TestNotification,
)
from .product import (
    EmulatorConfig,
    ProductDefinition,
    ProductsConfig,
    PubSubConfig,
    SubscriptionBehaviorConfig,
)

# Purchase models
from .purchase import (
    AcknowledgementState,
    ConsumptionState,
    ProductPurchaseRecord,
    PurchaseState,
)

# Subscription models
from .subscription import (
    CancelReason,
    NotificationType,
    PaymentState,
    SubscriptionRecord,
    SubscriptionState,
)

__all__ = [
    # Product configuration
    "ProductDefinition",
    "PubSubConfig",
    "SubscriptionBehaviorConfig",
    "EmulatorConfig",
    "ProductsConfig",
    # Purchase
    "PurchaseState",
    "ConsumptionState",
    "AcknowledgementState",
    "ProductPurchaseRecord",
    # Subscription
    "SubscriptionState",
    "NotificationType",
    "PaymentState",
    "CancelReason",
    "SubscriptionRecord",
    # Events
    "SubscriptionNotification",
    "OneTimeProductNotification",
    "TestNotification",
    "DeveloperNotification",
    # API responses
    "ProductPurchase",
    "SubscriptionPurchase",
    "SubscriptionPurchaseV2",
    # API requests
    "CreatePurchaseRequest",
    "CreatePurchaseResponse",
    "CreateSubscriptionRequest",
    "CreateSubscriptionResponse",
    "AdvanceTimeRequest",
    "AdvanceTimeResponse",
    "CancelSubscriptionRequest",
    "CancelSubscriptionResponse",
    "RenewSubscriptionResponse",
    "PauseSubscriptionRequest",
    "PauseSubscriptionResponse",
    "ResumeSubscriptionResponse",
    "PaymentFailedResponse",
    "ResetResponse",
    "ErrorResponse",
]
