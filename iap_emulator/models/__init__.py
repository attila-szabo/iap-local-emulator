"""Pydantic models for API requests, responses, and domain objects."""

# Product configuration models
from .product import (
    ProductDefinition,
    PubSubConfig,
    SubscriptionBehaviorConfig,
    EmulatorConfig,
    ProductsConfig,
)

# Purchase models
from .purchase import (
    PurchaseState,
    ConsumptionState,
    AcknowledgementState,
    ProductPurchaseRecord,
)

# Subscription models
from .subscription import (
    SubscriptionState,
    NotificationType,
    PaymentState,
    CancelReason,
    SubscriptionRecord,
)

# Event models (RTDN)
from .events import (
    SubscriptionNotification,
    OneTimeProductNotification,
    TestNotification,
    DeveloperNotification,
)

# API response models (Android Publisher API v3)
from .api_response import (
    ProductPurchase,
    SubscriptionPurchase,
    SubscriptionPurchaseV2,
)

# API request models (Control API)
from .api_request import (
    CreatePurchaseRequest,
    CreatePurchaseResponse,
    CreateSubscriptionRequest,
    CreateSubscriptionResponse,
    AdvanceTimeRequest,
    AdvanceTimeResponse,
    CancelSubscriptionRequest,
    CancelSubscriptionResponse,
    RenewSubscriptionResponse,
    PauseSubscriptionRequest,
    PauseSubscriptionResponse,
    ResumeSubscriptionResponse,
    PaymentFailedResponse,
    ResetResponse,
    ErrorResponse,
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
