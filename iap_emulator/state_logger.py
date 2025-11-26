"""Simple state change logging for subscriptions and purchases.

Tracks state transitions with before/after values for debugging and auditing.
"""

from typing import Any, Optional

from iap_emulator.logging_config import get_logger

logger = get_logger(__name__)


def log_subscription_state_change(
    token: str,
    subscription_id: str,
    old_state: Any,
    new_state: Any,
    reason: Optional[str] = None,
    **extra_context: Any,
) -> None:
    """Log subscription state change.

    Args:
        token: Subscription token
        subscription_id: Subscription product ID
        old_state: Previous state value
        new_state: New state value
        reason: Reason for state change
        **extra_context: Additional context (user_id, expiry, etc.)
    """
    logger.info(
        "subscription_state_changed",
        token=token[:20] + "..." if len(token) > 20 else token,
        subscription_id=subscription_id,
        old_state=str(old_state),
        new_state=str(new_state),
        reason=reason,
        **extra_context,
    )


def log_payment_state_change(
    token: str,
    subscription_id: str,
    old_payment_state: Any,
    new_payment_state: Any,
    reason: Optional[str] = None,
    **extra_context: Any,
) -> None:
    """Log payment state change.

    Args:
        token: Subscription token
        subscription_id: Subscription product ID
        old_payment_state: Previous payment state
        new_payment_state: New payment state
        reason: Reason for state change
        **extra_context: Additional context
    """
    logger.info(
        "payment_state_changed",
        token=token[:20] + "..." if len(token) > 20 else token,
        subscription_id=subscription_id,
        old_payment_state=str(old_payment_state),
        new_payment_state=str(new_payment_state),
        reason=reason,
        **extra_context,
    )


def log_purchase_state_change(
    token: str,
    product_id: str,
    old_state: Any,
    new_state: Any,
    reason: Optional[str] = None,
    **extra_context: Any,
) -> None:
    """Log purchase state change.

    Args:
        token: Purchase token
        product_id: Product ID
        old_state: Previous state value
        new_state: New state value
        reason: Reason for state change
        **extra_context: Additional context
    """
    logger.info(
        "purchase_state_changed",
        token=token[:20] + "..." if len(token) > 20 else token,
        product_id=product_id,
        old_state=str(old_state),
        new_state=str(new_state),
        reason=reason,
        **extra_context,
    )


def log_consumption_change(
    token: str,
    product_id: str,
    old_state: Any,
    new_state: Any,
    **extra_context: Any,
) -> None:
    """Log consumption state change.

    Args:
        token: Purchase token
        product_id: Product ID
        old_state: Previous consumption state
        new_state: New consumption state
        **extra_context: Additional context
    """
    logger.info(
        "consumption_state_changed",
        token=token[:20] + "..." if len(token) > 20 else token,
        product_id=product_id,
        old_state=str(old_state),
        new_state=str(new_state),
        **extra_context,
    )


def log_auto_renew_change(
    token: str,
    subscription_id: str,
    old_value: bool,
    new_value: bool,
    reason: Optional[str] = None,
    **extra_context: Any,
) -> None:
    """Log auto-renew setting change.

    Args:
        token: Subscription token
        subscription_id: Subscription product ID
        old_value: Previous auto-renew value
        new_value: New auto-renew value
        reason: Reason for change
        **extra_context: Additional context
    """
    logger.info(
        "auto_renew_changed",
        token=token[:20] + "..." if len(token) > 20 else token,
        subscription_id=subscription_id,
        old_value=old_value,
        new_value=new_value,
        reason=reason,
        **extra_context,
    )


def log_expiry_change(
    token: str,
    subscription_id: str,
    old_expiry_millis: int,
    new_expiry_millis: int,
    reason: str,
    **extra_context: Any,
) -> None:
    """Log subscription expiry time change.

    Args:
        token: Subscription token
        subscription_id: Subscription product ID
        old_expiry_millis: Previous expiry time
        new_expiry_millis: New expiry time
        reason: Reason for change (renewal, extension, etc.)
        **extra_context: Additional context
    """
    from datetime import datetime

    logger.info(
        "expiry_changed",
        token=token[:20] + "..." if len(token) > 20 else token,
        subscription_id=subscription_id,
        old_expiry=datetime.fromtimestamp(old_expiry_millis / 1000).isoformat(),
        new_expiry=datetime.fromtimestamp(new_expiry_millis / 1000).isoformat(),
        extension_days=(new_expiry_millis - old_expiry_millis) / (1000 * 86400),
        reason=reason,
        **extra_context,
    )
