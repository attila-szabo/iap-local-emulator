"""Control API for test orchestration and emulator management.

Implements:
- POST /emulator/subscriptions - Create subscription
- POST /emulator/time/advance - Fast-forward time
- POST /emulator/subscriptions/{token}/renew - Trigger renewal
- POST /emulator/subscriptions/{token}/cancel - Cancel subscription
- POST /emulator/subscriptions/{token}/payment-failed - Simulate payment failure
- POST /emulator/subscriptions/{token}/pause - Pause subscription
- POST /emulator/subscriptions/{token}/resume - Resume subscription
- POST /emulator/reset - Reset all state
"""

from fastapi import APIRouter, HTTPException

from iap_emulator.logging_config import get_logger
from iap_emulator.models import (
    AdvanceTimeRequest,
    AdvanceTimeResponse,
    CreateSubscriptionRequest,
    CreateSubscriptionResponse,
)
from iap_emulator.models.api_request import (
    CancelSubscriptionRequest,
    CancelSubscriptionResponse,
    CreatePurchaseRequest,
    CreatePurchaseResponse,
    PauseSubscriptionRequest,
    PauseSubscriptionResponse,
    PaymentFailedResponse,
    PaymentRecoveredResponse,
    RenewSubscriptionResponse,
    ResetResponse,
    ResetTimeResponse,
    ResumeSubscriptionResponse,
    SetTimeRequest,
    SetTimeResponse,
    StatusResponse,
)
from iap_emulator.repositories.product_repository import ProductNotFoundError
from iap_emulator.services.purchase_manager import get_purchase_manager
from iap_emulator.services.subscription_engine import get_subscription_engine
from iap_emulator.services.time_controller import get_time_controller

logger = get_logger(__name__)
router = APIRouter(tags=["Control API"], prefix="/emulator")
purchase_manager = get_purchase_manager()
subscription_engine = get_subscription_engine()
time_controller = get_time_controller()


@router.post(
    "/purchases",
    response_model=CreatePurchaseResponse,
    status_code=201,
    summary="Create test purchase",
)
async def create_purchase(request: CreatePurchaseRequest) -> CreatePurchaseResponse:
    """Create a test purchase for a one-time product.

    This endpoint allows you to simulate a purchase without going through
    the actual Google Play billing flow. Useful for testing.

    Args:
        request: Purchase creation request

    Returns:
        CreatePurchaseResponse with purchase details

    Raises:
        404: Product not found
        400: Invalid request parameters
    """
    logger.info(
        "create_purchase_request",
        product_id=request.product_id,
        user_id=request.user_id,
        package_name=request.package_name,
    )

    try:
        # determine package name
        package_name = request.package_name or "com.example.app"

        purchase = purchase_manager.create_purchase(
            product_id=request.product_id,
            package_name=package_name,
            user_id=request.user_id,
            developer_payload=request.developer_payload,
        )

        logger.info(
            "create_purchase_success",
            product_id=purchase.product_id,
            token=purchase.token[:20] + "...",
            order_id=purchase.order_id,
        )

        response = CreatePurchaseResponse(
            token=purchase.token,
            product_id=purchase.product_id,
            user_id=purchase.user_id,
            order_id=purchase.order_id,
            purchase_time_millis=purchase.purchase_time_millis,
            purchase_state=purchase.purchase_state.value,
            acknowledgement_state=purchase.acknowledgement_state.value,
            consumption_state=purchase.consumption_state.value,
            message="Purchase created successfully",
        )
        return response
    except ProductNotFoundError:
        logger.warning(
            "product_not_found",
            product_id=request.product_id,
        )
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Product not found",
                "message": f"Product '{request.product_id}' does not exist in the catalog",
            },
        )
    except ValueError as e:
        logger.error(
            "invalid_purchase_request",
            error=str(e),
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid request",
                "message": str(e),
            },
        )


@router.post(
    "/subscriptions",
    response_model=CreateSubscriptionResponse,
    status_code=201,
    summary="Create test subscription",
)
async def create_subscription(request: CreateSubscriptionRequest) -> CreateSubscriptionResponse:
    """Create a test subscription.

    This endpoint allows you to simulate a subscription purchase without going through
    the actual Google Play billing flow. Useful for testing subscription lifecycle.

    Args:
        request: Subscription creation request

    Returns:
        CreateSubscriptionResponse with subscription details

    Raises:
        404: Subscription product not found
        400: Invalid request parameters
    """

    logger.info(
        "create_subscription_request",
        subscription_id=request.subscription_id,
        user_id=request.user_id,
        start_trial=request.start_trial,
    )

    try:
        package_name = request.package_name or "com.example.app"

        subscription = subscription_engine.create_subscription(
            subscription_id=request.subscription_id,
            package_name=package_name,
            user_id=request.user_id,
            with_trial=request.start_trial,
        )

        logger.info(
            "create_subscription_success",
            subscription_id=subscription.subscription_id,
            token=subscription.token[:20] + "...",
            order_id=subscription.order_id,
            in_trial=subscription.in_trial,
            expiry_time=subscription.expiry_time_millis,
        )

        response = CreateSubscriptionResponse(
            token=subscription.token,
            subscription_id=subscription.subscription_id,
            user_id=subscription.user_id,
            order_id=subscription.order_id,
            start_time_millis=subscription.start_time_millis,
            expiry_time_millis=subscription.expiry_time_millis,
            in_trial=subscription.in_trial,
            message="Subscription created successfully",
        )
        return response
    except ProductNotFoundError:
        logger.warning(
            "subscription_not_found",
            subscription_id=request.subscription_id,
        )
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Subscription not found",
                "message": f"Subscription '{request.subscription_id}' does not exist in the catalog",
            },
        )
    except ValueError as e:
        logger.error(
            "invalid_subscription_request",
            error=str(e),
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid request",
                "message": str(e),
            },
        )


@router.get("/debug/products", summary="list all loaded products (debug only)")
async def list_products():
    """Debug endpoint to see what products are loaded."""
    from iap_emulator.repositories.product_repository import get_product_repository

    repo = get_product_repository()

    return {
        "total_products": len(repo),
        "product_ids": repo.get_all_subscription_ids(),
        "products_by_type": {
            "inapp": [p.id for p in repo.get_subscriptions_by_type("inapp")],
            "subs": [p.id for p in repo.get_subscriptions_by_type("subs")],
        },
    }


@router.get(
    "/debug/subscriptions",
    summary="List all subscriptions (debug only)",
)
async def list_subscriptions():
    """Debug endpoint to see all subscriptions in the store."""
    from iap_emulator.repositories.subscription_store import get_subscription_store

    store = get_subscription_store()
    stats = store.get_statistics()

    return {
        "total_subscriptions": stats["total_subscriptions"],
        "statistics": stats,
        "note": "Use subscription token from creation response to query individual subscriptions",
    }


@router.post(
    "/time/advance",
    response_model=AdvanceTimeResponse,
    summary="Advance virtual time",
)
async def advance_time(request: AdvanceTimeRequest) -> AdvanceTimeResponse:
    """Advance the emulator's virtual time forward.

    This triggers automatic processing of:
    - Subscription renewals that are due
    - Grace period expirations
    - Trial period expirations

    Args:
        request: Time advancement request (days, hours, minutes)

    Returns:
        AdvanceTimeResponse with time change details and events processed

    Raises:
        400: Invalid time parameters
    """

    logger.info(
        "advance_time_request",
        days=request.days,
        hours=request.hours,
        minutes=request.minutes,
    )

    try:
        previous_time = time_controller.get_current_time_millis()

        time_controller.advance_time(
            days=request.days or 0, hours=request.hours or 0, minutes=request.minutes or 0
        )

        current_time = time_controller.get_current_time_millis()
        advanced_by = current_time - previous_time

        # TODO: get actual counts from time controller, now it's placeholder
        renewals_processed = 0
        expirations_processed = 0
        events_published = 0

        logger.info(
            "advance_time_success",
            previous_time=previous_time,
            current_time=current_time,
            advanced_by_millis=advanced_by,
        )

        response = AdvanceTimeResponse(
            previous_time_millis=previous_time,
            current_time_millis=current_time,
            advanced_by_millis=advanced_by,
            renewals_processed=renewals_processed,
            expirations_processed=expirations_processed,
            events_published=events_published,
            message=f"Advanced time by {request.days or 0} days, {request.hours or 0} hours, {request.minutes or 0} minutes",
        )

        return response
    except ValueError as e:
        logger.error(
            "invalid_time_request",
            error=str(e),
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid request",
                "message": str(e),
            },
        )


@router.post(
    "/time/set",
    response_model=SetTimeResponse,
    summary="Set virtual time to specific timestamp",
)
async def set_time(request: SetTimeRequest) -> SetTimeResponse:
    """Set the emulator's virtual time to a specific timestamp.

    This allows you to jump to any point in time, forward or backward.
    Useful for testing specific dates or scenarios.

    Args:
        request: Time set request with target timestamp

    Returns:
        SetTimeResponse with previous and new time

    Raises:
        400: Invalid timestamp
    """
    logger.info(
        "set_time_request",
        target_time_millis=request.time_millis,
    )

    try:
        # Get previous time
        previous_time = time_controller.get_current_time_millis()

        # Set time to specific timestamp
        time_controller.set_time(request.time_millis)

        # Get new time (should match requested time)
        current_time = time_controller.get_current_time_millis()

        logger.info(
            "set_time_success",
            previous_time=previous_time,
            current_time=current_time,
        )

        # Convert to human-readable format for message
        from datetime import datetime

        dt = datetime.fromtimestamp(request.time_millis / 1000.0)

        response = SetTimeResponse(
            previous_time_millis=previous_time,
            current_time_millis=current_time,
            message=f"Time set to {dt.strftime('%Y-%m-%d %H:%M:%S')} UTC",
        )

        return response

    except ValueError as e:
        logger.error(
            "invalid_set_time_request",
            error=str(e),
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid request",
                "message": str(e),
            },
        )


@router.post(
    "/time/reset",
    response_model=ResetTimeResponse,
    summary="Reset virtual time to real current time",
)
async def reset_time() -> ResetTimeResponse:
    """Reset the emulator's virtual time back to real current time.

    This clears any time offset and returns the emulator to normal operation.
    Useful after testing to return to real-time mode.

    Returns:
        ResetTimeResponse with time reset details
    """
    logger.info("reset_time_request")

    try:
        # Get previous time
        previous_time = time_controller.get_current_time_millis()

        # Reset to real time
        time_controller.reset_time()

        # Get current real time
        current_time = time_controller.get_current_time_millis()

        logger.info(
            "reset_time_success",
            previous_time=previous_time,
            current_time=current_time,
        )

        response = ResetTimeResponse(
            previous_time_millis=previous_time,
            current_time_millis=current_time,
            offset_cleared=True,
            message="Time reset to real current time",
        )

        return response

    except Exception as e:
        logger.error(
            "reset_time_failed",
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal error",
                "message": str(e),
            },
        )


@router.post(
    "/reset",
    response_model=ResetResponse,
    summary="Reset emulator state",
)
async def reset_emulator() -> ResetResponse:
    """Reset all emulator state.

    This clears:
    - All purchases
    - All subscriptions
    - Virtual time (resets to real time)

    Useful for starting fresh between test runs.

    Returns:
        ResetResponse with counts of deleted items
    """
    logger.info("reset_emulator_request")

    try:
        from iap_emulator.repositories.purchase_store import get_purchase_store
        from iap_emulator.repositories.subscription_store import get_subscription_store

        purchase_store = get_purchase_store()
        subscription_store = get_subscription_store()

        purchase_stats = purchase_store.get_statistics()
        subscription_stats = subscription_store.get_statistics()

        purchases_count = purchase_stats["total_purchases"]
        subscriptions_count = subscription_stats["total_subscriptions"]

        purchase_store.clear()
        subscription_store.clear()
        time_controller.reset_time()

        logger.info(
            "reset_emulator_success",
            purchases_deleted=purchases_count,
            subscriptions_deleted=subscriptions_count,
        )

        response = ResetResponse(
            subscriptions_deleted=subscriptions_count,
            purchases_deleted=purchases_count,
            time_reset=True,
            message="Emulator state reset successfully",
        )

        return response
    except Exception as e:
        logger.error(
            "reset_emulator_failed",
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal error",
                "message": str(e),
            },
        )


@router.get(
    "/status",
    response_model=StatusResponse,
    summary="Get emulator status",
)
async def get_status() -> StatusResponse:
    """Get current emulator status and statistics.

    Returns information about:
    - Current virtual time
    - Time offset from real time
    - Number of purchases and subscriptions
    - Product catalog size

    Returns:
        StatusResponse with emulator status and statistics
    """
    logger.debug("get_status_request")

    try:
        from iap_emulator.repositories.product_repository import get_product_repository
        from iap_emulator.repositories.purchase_store import get_purchase_store
        from iap_emulator.repositories.subscription_store import get_subscription_store

        purchase_store = get_purchase_store()
        subscription_store = get_subscription_store()
        product_repo = get_product_repository()

        # Get statistics
        purchase_stats = purchase_store.get_statistics()
        subscription_stats = subscription_store.get_statistics()

        # Get current time info
        current_time = time_controller.get_current_time_millis()

        # Calculate time offset (current virtual time - real time)
        import time

        real_time = int(time.time() * 1000)
        time_offset = current_time - real_time

        response = StatusResponse(
            status="running",
            current_time_millis=current_time,
            time_offset_millis=time_offset,
            statistics={
                "total_purchases": purchase_stats.get("total_purchases", 0),
                "total_subscriptions": subscription_stats.get("total_subscriptions", 0),
                "active_subscriptions": subscription_stats.get("active_subscriptions", 0),
                "subscriptions_in_trial": subscription_stats.get("subscriptions_in_trial", 0),
                "subscriptions_in_grace_period": subscription_stats.get(
                    "subscriptions_in_grace_period", 0
                ),
                "total_products": len(product_repo),
            },
        )

        return response

    except Exception as e:
        logger.error(
            "get_status_failed",
            error=str(e),
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal error",
                "message": str(e),
            },
        )


@router.post(
    "/subscriptions/{token}/renew",
    response_model=RenewSubscriptionResponse,
    summary="Manually renew subscription",
)
async def renew_subscription(token: str) -> RenewSubscriptionResponse:
    """Manually trigger subscription renewal.

    Forces an immediate renewal regardless of expiry time.
    Useful for testing renewal logic without time manipulation.

    Args:
        token: Subscription purchase token

    Returns:
        RenewSubscriptionResponse with renewal details

    Raises:
        404: Subscription not found
        400: Invalid subscription state for renewal
    """
    logger.info(
        "renew_subscription_request",
        token=token[:20] + "...",
    )

    try:
        from iap_emulator.repositories.subscription_store import SubscriptionNotFoundError

        # Get subscription
        subscription = subscription_engine.get_subscription(token)

        # Store previous expiry
        previous_expiry = subscription.expiry_time_millis

        # Renew subscription
        subscription_engine.renew_subscription(token)

        # Get updated subscription
        updated_subscription = subscription_engine.get_subscription(token)

        logger.info(
            "renew_subscription_success",
            token=token[:20] + "...",
            previous_expiry=previous_expiry,
            new_expiry=updated_subscription.expiry_time_millis,
            renewal_count=updated_subscription.renewal_count,
        )

        response = RenewSubscriptionResponse(
            token=token,
            previous_expiry_millis=previous_expiry,
            new_expiry_millis=updated_subscription.expiry_time_millis,
            renewal_count=updated_subscription.renewal_count,
            message="Subscription renewed successfully",
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
                "error": "Subscription not found",
                "message": f"No subscription found with token: {token[:20]}...",
            },
        )
    except Exception as e:
        logger.error(
            "renew_subscription_failed",
            token=token[:20] + "...",
            error=str(e),
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Renewal failed",
                "message": str(e),
            },
        )


@router.post(
    "/subscriptions/{token}/cancel",
    response_model=CancelSubscriptionResponse,
    summary="Cancel subscription",
)
async def cancel_subscription_control(
    token: str,
    request: CancelSubscriptionRequest = CancelSubscriptionRequest(),
) -> CancelSubscriptionResponse:
    """Cancel a subscription.

    Args:
        token: Subscription purchase token
        request: Cancellation request with reason and immediate flag

    Returns:
        CancelSubscriptionResponse with cancellation details

    Raises:
        404: Subscription not found
    """
    logger.info(
        "cancel_subscription_control_request",
        token=token[:20] + "...",
        cancel_reason=request.cancel_reason,
        immediate=request.immediate,
    )

    try:
        from iap_emulator.models.subscription import CancelReason
        from iap_emulator.repositories.subscription_store import SubscriptionNotFoundError

        # Map cancel reason int to enum
        reason_map = {
            0: CancelReason.USER_CANCELED,
            1: CancelReason.SYSTEM_CANCELED,
            2: CancelReason.REPLACED,
            3: CancelReason.DEVELOPER_CANCELED,
        }
        reason = reason_map.get(request.cancel_reason, "user")

        # Cancel subscription
        subscription_engine.cancel_subscription(
            token, cancel_reason=reason, immediate=request.immediate
        )

        # Get updated subscription
        subscription = subscription_engine.get_subscription(token)

        logger.info(
            "cancel_subscription_control_success",
            token=token[:20] + "...",
            canceled_time=subscription.canceled_time_millis,
            expiry_time=subscription.expiry_time_millis,
        )

        response = CancelSubscriptionResponse(
            token=token,
            canceled_time_millis=subscription.canceled_time_millis or 0,
            expiry_time_millis=subscription.expiry_time_millis,
            auto_renewing=subscription.auto_renewing,
            message="Subscription canceled successfully",
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
                "error": "Subscription not found",
                "message": f"No subscription found with token: {token[:20]}...",
            },
        )


@router.post(
    "/subscriptions/{token}/payment-failed",
    response_model=PaymentFailedResponse,
    summary="Simulate payment failure",
)
async def simulate_payment_failure(token: str) -> PaymentFailedResponse:
    """Simulate a payment failure for a subscription.

    Moves subscription into grace period. Useful for testing
    grace period and account hold flows.

    Args:
        token: Subscription purchase token

    Returns:
        PaymentFailedResponse with grace period details

    Raises:
        404: Subscription not found
        400: Invalid subscription state
    """
    logger.info(
        "payment_failure_request",
        token=token[:20] + "...",
    )

    try:
        # Get current time
        import time

        from iap_emulator.repositories.subscription_store import SubscriptionNotFoundError

        current_time = int(time.time() * 1000)

        # Trigger payment failure
        subscription_engine.simulate_payment_failure(token)

        # Get updated subscription
        subscription = subscription_engine.get_subscription(token)

        logger.info(
            "payment_failure_success",
            token=token[:20] + "...",
            new_state=subscription.state.name,
            grace_period_end=subscription.grace_period_end_millis,
        )

        response = PaymentFailedResponse(
            token=token,
            payment_failed_time_millis=current_time,
            grace_period_end_millis=subscription.grace_period_end_millis,
            new_state=subscription.state.value,
            message="Payment failure simulated, subscription in grace period",
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
                "error": "Subscription not found",
                "message": f"No subscription found with token: {token[:20]}...",
            },
        )
    except Exception as e:
        logger.error(
            "payment_failure_failed",
            token=token[:20] + "...",
            error=str(e),
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Payment failure simulation failed",
                "message": str(e),
            },
        )


@router.post(
    "/subscriptions/{token}/payment-recovered",
    response_model=PaymentRecoveredResponse,
    summary="Recover from payment failure",
)
async def recover_payment(token: str) -> PaymentRecoveredResponse:
    """Recover a subscription from payment failure.

    Moves subscription from grace period or account hold back to active.

    Args:
        token: Subscription purchase token

    Returns:
        PaymentRecoveredResponse with recovery details

    Raises:
        404: Subscription not found
        400: Invalid subscription state
    """
    logger.info(
        "payment_recovery_request",
        token=token[:20] + "...",
    )

    try:
        # Get current time
        import time

        from iap_emulator.repositories.subscription_store import SubscriptionNotFoundError

        current_time = int(time.time() * 1000)

        # Recover payment
        subscription_engine.recover_from_payment_failure(token)

        # Get updated subscription
        subscription = subscription_engine.get_subscription(token)

        logger.info(
            "payment_recovery_success",
            token=token[:20] + "...",
            new_state=subscription.state.name,
            new_expiry=subscription.expiry_time_millis,
        )

        response = PaymentRecoveredResponse(
            token=token,
            recovery_time_millis=current_time,
            new_state=subscription.state.value,
            new_expiry_millis=subscription.expiry_time_millis,
            message="Payment recovered, subscription reactivated",
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
                "error": "Subscription not found",
                "message": f"No subscription found with token: {token[:20]}...",
            },
        )
    except Exception as e:
        logger.error(
            "payment_recovery_failed",
            token=token[:20] + "...",
            error=str(e),
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Payment recovery failed",
                "message": str(e),
            },
        )


@router.post(
    "/subscriptions/{token}/pause",
    response_model=PauseSubscriptionResponse,
    summary="Pause subscription",
)
async def pause_subscription(
    token: str,
    request: PauseSubscriptionRequest = PauseSubscriptionRequest(),
) -> PauseSubscriptionResponse:
    """Pause a subscription.

    Args:
        token: Subscription purchase token
        request: Pause request with optional duration

    Returns:
        PauseSubscriptionResponse with pause details

    Raises:
        404: Subscription not found
        400: Invalid subscription state
    """
    logger.info(
        "pause_subscription_request",
        token=token[:20] + "...",
        pause_duration_days=request.pause_duration_days,
    )

    try:
        # Get current time
        import time

        from iap_emulator.repositories.subscription_store import SubscriptionNotFoundError

        current_time = int(time.time() * 1000)

        # Calculate pause end time if duration specified
        pause_end_millis = None
        if request.pause_duration_days:
            pause_end_millis = current_time + (request.pause_duration_days * 24 * 60 * 60 * 1000)

        # Pause subscription
        subscription_engine.pause_subscription(token, pause_end_millis=pause_end_millis)

        # Get updated subscription
        subscription = subscription_engine.get_subscription(token)

        logger.info(
            "pause_subscription_success",
            token=token[:20] + "...",
            pause_start=subscription.pause_start_millis,
            pause_end=subscription.pause_end_millis,
        )

        response = PauseSubscriptionResponse(
            token=token,
            pause_start_millis=subscription.pause_start_millis or current_time,
            pause_end_millis=subscription.pause_end_millis,
            message="Subscription paused successfully",
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
                "error": "Subscription not found",
                "message": f"No subscription found with token: {token[:20]}...",
            },
        )
    except Exception as e:
        logger.error(
            "pause_subscription_failed",
            token=token[:20] + "...",
            error=str(e),
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Pause failed",
                "message": str(e),
            },
        )


@router.post(
    "/subscriptions/{token}/resume",
    response_model=ResumeSubscriptionResponse,
    summary="Resume paused subscription",
)
async def resume_subscription(token: str) -> ResumeSubscriptionResponse:
    """Resume a paused subscription.

    Args:
        token: Subscription purchase token

    Returns:
        ResumeSubscriptionResponse with resume details

    Raises:
        404: Subscription not found
        400: Subscription not paused
    """
    logger.info(
        "resume_subscription_request",
        token=token[:20] + "...",
    )

    try:
        # Get current time
        import time

        from iap_emulator.repositories.subscription_store import SubscriptionNotFoundError

        current_time = int(time.time() * 1000)

        # Resume subscription
        subscription_engine.resume_subscription(token)

        # Get updated subscription
        subscription = subscription_engine.get_subscription(token)

        logger.info(
            "resume_subscription_success",
            token=token[:20] + "...",
            new_expiry=subscription.expiry_time_millis,
        )

        response = ResumeSubscriptionResponse(
            token=token,
            resume_time_millis=current_time,
            new_expiry_millis=subscription.expiry_time_millis,
            message="Subscription resumed successfully",
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
                "error": "Subscription not found",
                "message": f"No subscription found with token: {token[:20]}...",
            },
        )
    except Exception as e:
        logger.error(
            "resume_subscription_failed",
            token=token[:20] + "...",
            error=str(e),
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Resume failed",
                "message": str(e),
            },
        )
