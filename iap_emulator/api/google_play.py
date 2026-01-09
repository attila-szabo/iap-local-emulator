"""Android Publisher API v3 emulation endpoints.

Implements:
- GET /androidpublisher/v3/applications/{packageName}/purchases/products/{productId}/tokens/{token}
- GET /androidpublisher/v3/applications/{packageName}/purchases/subscriptions/{subscriptionId}/tokens/{token}
- POST /androidpublisher/v3/applications/{packageName}/purchases/subscriptions/{subscriptionId}/tokens/{token}:acknowledge
- POST /androidpublisher/v3/applications/{packageName}/orders/{orderId}:refund
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Path, Query
from iap_emulator.logging_config import get_logger
from iap_emulator.models import (
    ProductPurchaseRecord,
    SubscriptionRecord,
    SubscriptionState,
    PaymentState,
)
from iap_emulator.models.api_request import DeferSubscriptionRequest
from iap_emulator.models.api_response import ProductPurchase, SubscriptionPurchase
from iap_emulator.repositories.purchase_store import PurchaseNotFoundError
from iap_emulator.repositories.subscription_store import SubscriptionNotFoundError
from iap_emulator.services.purchase_manager import PurchaseManager
from iap_emulator.services.subscription_engine import SubscriptionEngine

logger = get_logger(__name__)
router = APIRouter(tags=["Google Play API"])

purchase_manager = PurchaseManager()
subscription_engine = SubscriptionEngine()


def _convert_product_purchase(record: ProductPurchaseRecord) -> ProductPurchase:
    return ProductPurchase(
        purchaseTimeMillis=str(record.purchase_time_millis),
        purchaseState=record.purchase_state.value,
        consumptionState=record.consumption_state.value,
        acknowledgementState=record.acknowledgement_state.value,
        orderId=record.order_id,
        purchaseToken=record.token,
        productId=record.product_id,
        quantity=1,
        regionCode="US",
        developerPayload=record.developer_payload,
    )


def _convert_subscription_purchase(record: SubscriptionRecord) -> SubscriptionPurchase:
    """Convert internal SubscriptionRecord to Google API format.

    Args:
        record: Internal subscription record

    Returns:
        SubscriptionPurchase API response
    """

    # Determine auto-renewing based on state and flag
    # Subscription is auto-renewing only if ACTIVE and auto_renewing flag is True
    auto_renewing = record.state == SubscriptionState.ACTIVE and record.auto_renewing

    # Convert payment state to API format
    # Map internal PaymentState to Google's values
    payment_state_value: Optional[int] = None
    if record.payment_state == PaymentState.PAYMENT_PENDING:
        payment_state_value = 0
    elif record.payment_state == PaymentState.PAYMENT_RECEIVED:
        payment_state_value = 1
    elif record.payment_state == PaymentState.FREE_TRIAL:
        payment_state_value = 2
    elif record.payment_state == PaymentState.PAYMENT_FAILED:
        payment_state_value = 3

    # Convert cancel reason to API format (optional)
    cancel_reason_value: Optional[int] = None
    if record.cancel_reason is not None:
        # Handle both enum and string values (defensive)
        if isinstance(record.cancel_reason, int):
            cancel_reason_value = record.cancel_reason
        elif hasattr(record.cancel_reason, "value"):
            cancel_reason_value = record.cancel_reason.value
        else:
            # Fallback for string values
            cancel_reason_value = 0  # Default to USER_CANCELED

    # User cancellation time (optional)
    user_cancellation_time: Optional[str] = None
    if record.canceled_time_millis is not None:
        user_cancellation_time = str(record.canceled_time_millis)

    # Auto-resume time for paused subscriptions (optional)
    auto_resume_time: Optional[str] = None
    if record.pause_end_millis is not None:
        auto_resume_time = str(record.pause_end_millis)

    return SubscriptionPurchase(
        startTimeMillis=str(record.start_time_millis),
        expiryTimeMillis=str(record.expiry_time_millis),
        autoResumeTimeMillis=auto_resume_time,
        autoRenewing=auto_renewing,
        priceCurrencyCode=record.price_currency_code,
        priceAmountMicros=str(record.price_amount_micros),
        countryCode="US",  # Default country code
        developerPayload=None,  # Subscriptions typically don't use developer payload
        paymentState=payment_state_value,
        cancelReason=cancel_reason_value,
        userCancellationTimeMillis=user_cancellation_time,
        orderId=record.order_id,
        purchaseToken=record.token,
        acknowledgementState=record.acknowledgement_state,
    )


@router.get(
    "/androidpublisher/v3/applications/{packageName}/purchases/products/{productId}/tokens/{token}",
    response_model=ProductPurchase,
)
async def get_product_purchase(
    packageName: str = Path(...), productId: str = Path(...), token: str = Path(...)
) -> ProductPurchase:
    logger.info(
        "get_product_purchase_request",
        package_name=packageName,
        product_id=productId,
        token=token[:20] + "...",
    )
    try:
        purchase = purchase_manager.get_purchase(token)
    except PurchaseNotFoundError:
        logger.warning(
            "purchase_not_found",
            token=token[:20] + "...",
        )
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": 404,
                    "message": "The purchase token was not found.",
                    "status": "NOT_FOUND",
                }
            },
        )

    if purchase.package_name != packageName:
        logger.warning(
            "package_name_mismatch",
            expected=packageName,
            actual=purchase.package_name,
            token=token[:20] + "...",
        )
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": 404,
                    "message": "The purchase does not exist for this package.",
                    "status": "NOT_FOUND",
                }
            },
        )

    if purchase.product_id != productId:
        logger.warning(
            "product_id_mismatch",
            expected=productId,
            actual=purchase.product_id,
            token=token[:20] + "...",
        )
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": 404,
                    "message": "The purchase does not exist for this product.",
                    "status": "NOT_FOUND",
                }
            },
        )

    response = _convert_product_purchase(purchase)
    logger.info(
        "get_product_purchase_success",
        product_id=productId,
        purchase_state=purchase.purchase_state.name,
    )
    return response


@router.get(
    "/androidpublisher/v3/applications/{packageName}/purchases/subscriptions/{subscriptionId}/tokens/{token}",
    response_model=SubscriptionPurchase,
)
async def get_subscription_purchase(
    packageName: str = Path(...),
    subscriptionId: str = Path(...),
    token: str = Path(...),
) -> SubscriptionPurchase:
    """Query subscription purchase details by token.

    Emulates: GET androidpublisher/v3/.../purchases/subscriptions/{subscriptionId}/tokens/{token}

    Args:
        packageName: Android package name (e.g., com.example.app)
        subscriptionId: Subscription ID (e.g., premium.yearly)
        token: Purchase token from client

    Returns:
        SubscriptionPurchase details

    Raises:
        404: Subscription not found
    """
    logger.info(
        "get_subscription_purchase_request",
        package_name=packageName,
        subscription_id=subscriptionId,
        token=token[:20] + "...",
    )

    try:
        subscription = subscription_engine.get_subscription(token)

        # Validate package name matches
        if subscription.package_name != packageName:
            logger.warning(
                "package_name_mismatch",
                expected=packageName,
                actual=subscription.package_name,
                token=token[:20] + "...",
            )
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": 404,
                        "message": "The subscription does not exist for this package.",
                        "status": "NOT_FOUND",
                    }
                },
            )
            # Validate subscription ID matches
        if subscription.subscription_id != subscriptionId:
            logger.warning(
                "subscription_id_mismatch",
                expected=subscriptionId,
                actual=subscription.subscription_id,
                token=token[:20] + "...",
            )
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": 404,
                        "message": "The subscription does not exist for this product.",
                        "status": "NOT_FOUND",
                    }
                },
            )

        response = _convert_subscription_purchase(subscription)

        logger.info(
            "get_subscription_purchase_success",
            subscription_id=subscriptionId,
            state=subscription.state.name,
            auto_renewing=subscription.auto_renewing,
            expiry_time=subscription.expiry_time_millis,
        )

        return response
    except SubscriptionNotFoundError:
        logger.warning(
            "subscription_not_found",
            token=token[:20] + "...",
        )
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": 404,
                    "message": "The subscription token was not found.",
                    "status": "NOT_FOUND",
                }
            },
        )


@router.post(
    "/androidpublisher/v3/applications/{packageName}/purchases/products/{productId}/tokens/{token}:acknowledge",
    status_code=204,
    summary="Acknowledge product purchase",
)
async def acknowledge_product_purchase(
    packageName: str = Path(..., description="Android package name"),
    productId: str = Path(..., description="Product SKU/ID"),
    token: str = Path(..., description="Purchase token"),
):
    """Acknowledge a product purchase.

    Emulates: POST androidpublisher/v3/.../products/{productId}/tokens/{token}:acknowledge

    Args:
        packageName: Android package name
        productId: Product ID
        token: Purchase token

    Returns:
        204 No Content on success

    Raises:
        404: Purchase not found
    """

    logger.info(
        "acknowledge_product_request",
        package_name=packageName,
        product_id=productId,
        token=token[:20] + "...",
    )
    try:
        # Get purchase and validate
        purchase = purchase_manager.get_purchase(token)

        if purchase.package_name != packageName:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": 404,
                        "message": "The purchase does not exist for this package.",
                        "status": "NOT_FOUND",
                    }
                },
            )

        if purchase.product_id != productId:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": 404,
                        "message": "The purchase does not exist for this product.",
                        "status": "NOT_FOUND",
                    }
                },
            )

        # Acknowledge the purchase (idempotent - safe to call multiple times)
        purchase_manager.acknowledge_purchase(token)

        logger.info(
            "acknowledge_product_success",
            product_id=productId,
            token=token[:20] + "...",
        )

        return None  # 204 No Content

    except PurchaseNotFoundError:
        logger.warning(
            "purchase_not_found",
            token=token[:20] + "...",
        )
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": 404,
                    "message": "The purchase token was not found.",
                    "status": "NOT_FOUND",
                }
            },
        )


@router.post(
    "/androidpublisher/v3/applications/{packageName}/purchases/subscriptions/{subscriptionId}/tokens/{token}:cancel",
    status_code=204,
    summary="Cancel subscription",
)
async def cancel_subscription(
    packageName: str = Path(..., description="Android package name"),
    subscriptionId: str = Path(..., description="Subscription product ID"),
    token: str = Path(..., description="Purchase token"),
):
    """Cancel a subscription (user keeps access until expiry).

    Emulates: POST androidpublisher/v3/.../subscriptions/{subscriptionId}/tokens/{token}:cancel

    Args:
        packageName: Android package name
        subscriptionId: Subscription ID
        token: Purchase token

    Returns:
        204 No Content on success

    Raises:
        404: Subscription not found
    """
    logger.info(
        "cancel_subscription_request",
        package_name=packageName,
        subscription_id=subscriptionId,
        token=token[:20] + "...",
    )

    try:
        # Get subscription and validate
        subscription = subscription_engine.get_subscription(token)

        if subscription.package_name != packageName:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": 404,
                        "message": "The subscription does not exist for this package.",
                        "status": "NOT_FOUND",
                    }
                },
            )

        if subscription.subscription_id != subscriptionId:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": 404,
                        "message": "The subscription does not exist for this product.",
                        "status": "NOT_FOUND",
                    }
                },
            )

        # Cancel subscription (developer-initiated)
        subscription_engine.cancel(token, reason="developer")

        logger.info(
            "cancel_subscription_success",
            subscription_id=subscriptionId,
            token=token[:20] + "...",
        )

        return None  # 204 No Content

    except SubscriptionNotFoundError:
        logger.warning(
            "subscription_not_found",
            token=token[:20] + "...",
        )
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": 404,
                    "message": "The subscription token was not found.",
                    "status": "NOT_FOUND",
                }
            },
        )


@router.post(
    "/androidpublisher/v3/applications/{packageName}/purchases/subscriptions/{subscriptionId}/tokens/{token}:revoke",
    status_code=204,
    summary="Revoke subscription",
)
async def revoke_subscription(
    packageName: str = Path(..., description="Android package name"),
    subscriptionId: str = Path(..., description="Subscription product ID"),
    token: str = Path(..., description="Purchase token"),
):
    """Revoke a subscription immediately (user loses access now).

    Emulates: POST androidpublisher/v3/.../subscriptions/{subscriptionId}/tokens/{token}:revoke

    Args:
        packageName: Android package name
        subscriptionId: Subscription ID
        token: Purchase token

    Returns:
        204 No Content on success

    Raises:
        404: Subscription not found
    """
    logger.info(
        "revoke_subscription_request",
        package_name=packageName,
        subscription_id=subscriptionId,
        token=token[:20] + "...",
    )

    try:
        # Get subscription and validate
        subscription = subscription_engine.get_subscription(token)

        if subscription.package_name != packageName:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": 404,
                        "message": "The subscription does not exist for this package.",
                        "status": "NOT_FOUND",
                    }
                },
            )

        if subscription.subscription_id != subscriptionId:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": 404,
                        "message": "The subscription does not exist for this product.",
                        "status": "NOT_FOUND",
                    }
                },
            )

        # Revoke subscription (immediate termination)
        subscription_engine.revoke(token)

        logger.info(
            "revoke_subscription_success",
            subscription_id=subscriptionId,
            token=token[:20] + "...",
        )

        return None  # 204 No Content

    except SubscriptionNotFoundError:
        logger.warning(
            "subscription_not_found",
            token=token[:20] + "...",
        )
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": 404,
                    "message": "The subscription token was not found.",
                    "status": "NOT_FOUND",
                }
            },
        )


@router.post(
    "/androidpublisher/v3/applications/{packageName}/purchases/subscriptions/{subscriptionId}/tokens/{token}:defer",
    response_model=SubscriptionPurchase,
    summary="Defer subscription renewal",
)
async def defer_subscription(
    packageName: str = Path(..., description="Android package name"),
    subscriptionId: str = Path(..., description="Subscription product ID"),
    token: str = Path(..., description="Purchase token"),
    request: DeferSubscriptionRequest = ...,
) -> SubscriptionPurchase:
    """Defer subscription renewal by extending expiry time.

    Emulates: POST androidpublisher/v3/.../subscriptions/{subscriptionId}/tokens/{token}:defer

    Args:
        packageName: Android package name
        subscriptionId: Subscription ID
        token: Purchase token
        request: Deferral request with new expiry time

    Returns:
        Updated SubscriptionPurchase details

    Raises:
        400: Invalid deferral time
        404: Subscription not found
    """
    logger.info(
        "defer_subscription_request",
        package_name=packageName,
        subscription_id=subscriptionId,
        token=token[:20] + "...",
    )

    try:
        # Get subscription and validate
        subscription = subscription_engine.get_subscription(token)

        if subscription.package_name != packageName:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": 404,
                        "message": "The subscription does not exist for this package.",
                        "status": "NOT_FOUND",
                    }
                },
            )

        if subscription.subscription_id != subscriptionId:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": 404,
                        "message": "The subscription does not exist for this product.",
                        "status": "NOT_FOUND",
                    }
                },
            )

        # Extract new expiry time from request
        deferral_info = request.deferralInfo
        new_expiry_str = deferral_info.get("expectedExpiryTimeMillis") or deferral_info.get(
            "desiredExpiryTimeMillis"
        )

        if not new_expiry_str:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": 400,
                        "message": "Missing expectedExpiryTimeMillis or desiredExpiryTimeMillis in deferralInfo.",
                        "status": "INVALID_ARGUMENT",
                    }
                },
            )

        try:
            new_expiry_millis = int(new_expiry_str)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": 400,
                        "message": "Invalid expiry time format. Must be a numeric string.",
                        "status": "INVALID_ARGUMENT",
                    }
                },
            )

        # Defer the subscription
        try:
            updated_subscription = subscription_engine.defer_subscription(token, new_expiry_millis)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": 400,
                        "message": str(e),
                        "status": "INVALID_ARGUMENT",
                    }
                },
            )

        # Convert to API response format
        response = _convert_subscription_purchase(updated_subscription)

        logger.info(
            "defer_subscription_success",
            subscription_id=subscriptionId,
            new_expiry_millis=new_expiry_millis,
            token=token[:20] + "...",
        )

        return response

    except SubscriptionNotFoundError:
        logger.warning(
            "subscription_not_found",
            token=token[:20] + "...",
        )
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": 404,
                    "message": "The subscription token was not found.",
                    "status": "NOT_FOUND",
                }
            },
        )


@router.post(
    "/androidpublisher/v3/applications/{packageName}/purchases/subscriptions/{subscriptionId}/tokens/{token}:acknowledge",
    status_code=204,
    summary="Acknowledge subscription purchase",
)
async def acknowledge_subscription_purchase(
    packageName: str = Path(..., description="Android package name"),
    subscriptionId: str = Path(..., description="Subscription product ID"),
    token: str = Path(..., description="Purchase token"),
):
    """Acknowledge a subscription purchase.

    Emulates: POST androidpublisher/v3/.../subscriptions/{subscriptionId}/tokens/{token}:acknowledge

    This endpoint marks the subscription as acknowledged.

    Args:
        packageName: Android package name
        subscriptionId: Subscription ID
        token: Purchase token

    Returns:
        204 No Content on success

    Raises:
        404: Subscription not found
    """
    logger.info(
        "acknowledge_subscription_request",
        package_name=packageName,
        subscription_id=subscriptionId,
        token=token[:20] + "...",
    )

    try:
        subscription = subscription_engine.get_subscription(token)

        if subscription.package_name != packageName:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": 404,
                        "message": "The subscription does not exist for this package.",
                        "status": "NOT_FOUND",
                    }
                },
            )

        if subscription.subscription_id != subscriptionId:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": 404,
                        "message": "The subscription does not exist for this product.",
                        "status": "NOT_FOUND",
                    }
                },
            )

        subscription_engine.acknowledge_subscription(token)

        logger.info(
            "acknowledge_subscription_success",
            subscription_id=subscriptionId,
            token=token[:20] + "...",
        )

        return None  # 204 No Content

    except SubscriptionNotFoundError:
        logger.warning(
            "subscription_not_found",
            token=token[:20] + "...",
        )
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": 404,
                    "message": "The subscription token was not found.",
                    "status": "NOT_FOUND",
                }
            },
        )


@router.post(
    "/androidpublisher/v3/applications/{packageName}/orders/{orderId}:refund",
    status_code=204,
    summary="Refund an order",
)
async def refund_order(
    packageName: str = Path(..., description="Android package name"),
    orderId: str = Path(..., description="Order ID"),
    revoke: bool = Query(False, description="Whether to revoke access immediately (subscriptions only)"),
) -> None:
    """Refund an order (product purchase or subscription).

    Emulates: POST androidpublisher/v3/applications/{packageName}/orders/{orderId}:refund

    This endpoint works for both product purchases and subscriptions.
    For products, refunding sets the purchase state to CANCELED.
    For subscriptions, refunding revokes the subscription immediately.

    Args:
        packageName: Android package name
        orderId: Order ID to refund
        revoke: Whether to revoke access immediately (applies to subscriptions)

    Returns:
        204 No Content on success

    Raises:
        404: Order not found
    """
    logger.info(
        "refund_order_request",
        package_name=packageName,
        order_id=orderId,
        revoke=revoke,
    )

    # Try to find the order in products first
    try:
        purchase = purchase_manager.get_purchase_by_order_id(orderId)

        # Validate package name
        if purchase.package_name != packageName:
            logger.warning(
                "package_name_mismatch_refund",
                expected=packageName,
                actual=purchase.package_name,
                order_id=orderId,
            )
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": 404,
                        "message": "The order does not exist for this package.",
                        "status": "NOT_FOUND",
                    }
                },
            )

        # Refund the product purchase
        purchase_manager.refund_purchase(orderId)

        logger.info(
            "refund_order_success",
            order_id=orderId,
            order_type="product",
            product_id=purchase.product_id,
        )

        return None  # 204 No Content

    except PurchaseNotFoundError:
        # Not a product purchase, try subscription
        pass

    # Try to find the order in subscriptions
    try:
        subscription = subscription_engine.get_subscription_by_order_id(orderId)

        # Validate package name
        if subscription.package_name != packageName:
            logger.warning(
                "package_name_mismatch_refund",
                expected=packageName,
                actual=subscription.package_name,
                order_id=orderId,
            )
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": 404,
                        "message": "The order does not exist for this package.",
                        "status": "NOT_FOUND",
                    }
                },
            )

        # Refund the subscription (revokes immediately)
        subscription_engine.refund_subscription(orderId)

        logger.info(
            "refund_order_success",
            order_id=orderId,
            order_type="subscription",
            subscription_id=subscription.subscription_id,
        )

        return None  # 204 No Content

    except SubscriptionNotFoundError:
        # Order not found in either products or subscriptions
        logger.warning(
            "order_not_found_refund",
            order_id=orderId,
        )
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": 404,
                    "message": "The order was not found.",
                    "status": "NOT_FOUND",
                }
            },
        )
