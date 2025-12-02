"""Subscription lifecycle state machine and event processing.

Responsibilities:
- Manage subscription states (active, canceled, expired, paused, on hold, in grace period)
- Process renewals
- Handle cancellations
- Apply grace periods and account holds
- Trigger state transitions
- Calculate expiry times and billing periods
"""

import time
from typing import Optional

from iap_emulator.config import get_config
from iap_emulator.logging_config import get_logger
from iap_emulator.models.subscription import (
    CancelReason,
    PaymentState,
    SubscriptionRecord,
    SubscriptionState,
)
from iap_emulator.repositories.product_repository import (
    ProductNotFoundError,
    ProductRepository,
    get_product_repository,
)
from iap_emulator.repositories.subscription_store import (
    SubscriptionNotFoundError,
    SubscriptionStore,
    get_subscription_store,
)
from iap_emulator.utils.billing_period import parse_billing_period
from iap_emulator.utils.token_generator import (
    generate_order_id,
    generate_subscription_token,
)
from iap_emulator.models.subscription import NotificationType
from iap_emulator.services.event_dispatcher import get_event_dispatcher

logger = get_logger(__name__)


class SubscriptionError(Exception):
    """Base exception for subscription errors."""

    pass


class InvalidSubscriptionStateError(SubscriptionError):
    """Raised when an operation is invalid for the current subscription state."""

    pass


class SubscriptionEngine:
    """Subscription lifecycle management engine.

    Handles subscription creation, state transitions, renewals, and cancellations.
    Integrates with SubscriptionStore for persistence and ProductRepository for
    product definitions.
    """

    def __init__(
            self,
            subscription_store: Optional[SubscriptionStore] = None,
            product_repository: Optional[ProductRepository] = None,
    ):
        """Initialize subscription engine.

        Args:
            subscription_store: Subscription storage (defaults to global instance)
            product_repository: Product repository (defaults to global instance)
        """
        self.store = subscription_store or get_subscription_store()
        self.product_repo = product_repository or get_product_repository()
        self.config = get_config()
        self._time_controller = None  # Lazy loaded to avoid circular import
        self._event_dispatcher = None  # Lazy loaded to avoid circular import

        logger.info("subscription_engine_initialized")

    def _get_time_controller(self):
        """lazy load time controller to avoid circular import"""
        if self._time_controller is None:
            from iap_emulator.services.time_controller import get_time_controller
            self._time_controller = get_time_controller()
        return self._time_controller

    def _get_event_dispatcher(self):
        """lazy load event dispatcher to avoid circular import"""
        if self._event_dispatcher is None:
            from iap_emulator.services.event_dispatcher import get_event_dispatcher
            self._event_dispatcher = get_event_dispatcher()
        return self._event_dispatcher

    def _publish_event(
            self,
            notification_type: NotificationType, subscription: SubscriptionRecord
    ) -> None:
        """Publish a subscription lifecycle event.

        Args:
            notification_type: Type of event to publish
            subscription: Subscription record
        """
        try:
            dispatcher = self._get_event_dispatcher()
            dispatcher.publish_subscription_event(
                notification_type=notification_type,
                purchase_token=subscription.token,
                subscription_id=subscription.subscription_id,
                package_name=subscription.package_name
            )
        except Exception as e:
            # Log error but don't fail the operation
            logger.error(
                "event_publish_failed",
                notification_type=notification_type.name,
                subscription_id=subscription.subscription_id,
                token=subscription.token[:16] + "...",
                error=str(e),
                exc_info=True,
            )

    def create_subscription(
            self,
            subscription_id: str,
            user_id: str,
            package_name: Optional[str] = None,
            start_time_millis: Optional[int] = None,
            with_trial: bool = False,
    ) -> SubscriptionRecord:
        """Create a new subscription.

        Args:
            subscription_id: Product subscription ID (e.g., "premium.personal.yearly")
            user_id: User identifier
            package_name: Android package name (defaults to config default)
            start_time_millis: Subscription start time (defaults to now)
            with_trial: Whether to start with trial period

        Returns:
            Created SubscriptionRecord

        Raises:
            ProductNotFoundError: If subscription_id is not found
            SubscriptionError: If user already has this subscription
        """
        # Get product definition
        product = self.product_repo.get_by_id(subscription_id)

        # Use default package name if not provided
        if package_name is None:
            package_name = self.config.default_package_name

        # Check if user already has an active subscription
        existing = self.store.get_user_subscription(
            user_id=user_id,
            subscription_id=subscription_id,
            package_name=package_name,
        )
        if existing and existing.state in (
                SubscriptionState.ACTIVE,
                SubscriptionState.PAUSED,
                SubscriptionState.IN_GRACE_PERIOD,
                SubscriptionState.ON_HOLD,
        ):
            raise SubscriptionError(
                f"User {user_id} already has an active subscription for {subscription_id}"
            )

        # Generate token and order ID
        token = generate_subscription_token()
        order_id = generate_order_id()

        # Determine start time
        if start_time_millis is None:
            start_time_millis = int(time.time() * 1000)

        # Calculate expiry time
        trial_expiry_millis = None
        in_trial = False

        if with_trial and product.trial_period:
            # Start with trial period
            trial_period_millis = parse_billing_period(product.trial_period)
            trial_expiry_millis = start_time_millis + trial_period_millis
            expiry_time_millis = trial_expiry_millis
            in_trial = True
            payment_state = PaymentState.FREE_TRIAL
        else:
            # Regular subscription without trial
            billing_period_millis = parse_billing_period(product.billing_period)
            expiry_time_millis = start_time_millis + billing_period_millis
            payment_state = PaymentState.PAYMENT_RECEIVED

        # Create subscription record
        subscription = SubscriptionRecord(
            token=token,
            subscription_id=subscription_id,
            package_name=package_name,
            user_id=user_id,
            start_time_millis=start_time_millis,
            expiry_time_millis=expiry_time_millis,
            purchase_time_millis=start_time_millis,
            state=SubscriptionState.ACTIVE,
            payment_state=payment_state,
            auto_renewing=True,
            in_trial=in_trial,
            trial_expiry_millis=trial_expiry_millis,
            renewal_count=0,
            order_id=order_id,
            price_amount_micros=product.price_micros,
            price_currency_code=product.currency,
        )

        # Store subscription
        self.store.add(subscription)

        logger.info(
            "subscription_created",
            token=token[:20] + "...",
            subscription_id=subscription_id,
            user_id=user_id,
            package_name=package_name,
            in_trial=in_trial,
            expiry_millis=expiry_time_millis,
        )

        # publish
        self._publish_event(NotificationType.SUBSCRIPTION_PURCHASED, subscription)

        return subscription

    def cancel_subscription(
            self,
            token: str,
            cancel_reason: CancelReason = CancelReason.USER_CANCELED,
            immediate: bool = False,
    ) -> SubscriptionRecord:
        """Cancel a subscription.

        By default, cancellation sets auto_renewing=False and marks the subscription
        as canceled, but it remains valid until expiry. With immediate=True, the
        subscription is expired immediately.

        Args:
            token: Subscription token
            cancel_reason: Reason for cancellation
            immediate: If True, expire immediately; otherwise cancel at period end

        Returns:
            Updated SubscriptionRecord

        Raises:
            SubscriptionNotFoundError: If token not found
            InvalidSubscriptionStateError: If subscription cannot be canceled
        """
        subscription = self.store.get_by_token(token)

        # Validate state
        if subscription.state not in (
                SubscriptionState.ACTIVE,
                SubscriptionState.PAUSED,
                SubscriptionState.IN_GRACE_PERIOD,
                SubscriptionState.ON_HOLD,
        ):
            raise InvalidSubscriptionStateError(
                f"Cannot cancel subscription in {subscription.state.name} state"
            )

        # Mark as canceled
        canceled_time_millis = int(time.time() * 1000)
        subscription.canceled_time_millis = canceled_time_millis
        subscription.cancel_reason = cancel_reason
        subscription.set_auto_renewing(
            False, reason=f"Canceled: {cancel_reason.name}"
        )

        if immediate:
            # Expire immediately
            subscription.set_state(
                SubscriptionState.EXPIRED,
                reason=f"Immediate cancellation: {cancel_reason.name}",
            )
            subscription.expiry_time_millis = canceled_time_millis
        else:
            # Cancel at period end
            subscription.set_state(
                SubscriptionState.CANCELED,
                reason=f"Canceled: {cancel_reason.name}",
            )

        # Update in store
        self.store.update(subscription)

        logger.info(
            "subscription_canceled",
            token=token[:20] + "...",
            subscription_id=subscription.subscription_id,
            user_id=subscription.user_id,
            cancel_reason=cancel_reason.name,
            immediate=immediate,
            expiry_millis=subscription.expiry_time_millis,
        )
        if immediate:
            # immediate cancellation = expired
            self._publish_event(NotificationType.SUBSCRIPTION_EXPIRED, subscription)
        else:
            # deferred cancellation = subscription canceled (will expire at the billing period end)
            self._publish_event(NotificationType.SUBSCRIPTION_CANCELED, subscription)
        return subscription

    def pause_subscription(
            self,
            token: str,
            pause_duration_millis: int,
    ) -> SubscriptionRecord:
        """Pause a subscription.

        Pauses the subscription and extends the expiry time by the pause duration.
        The subscription remains paused until explicitly resumed or the pause period ends.

        Args:
            token: Subscription token
            pause_duration_millis: Duration to pause in milliseconds

        Returns:
            Updated SubscriptionRecord

        Raises:
            SubscriptionNotFoundError: If token not found
            InvalidSubscriptionStateError: If subscription cannot be paused
            ValueError: If pause_duration_millis is invalid
        """
        if pause_duration_millis <= 0:
            raise ValueError("Pause duration must be positive")

        subscription = self.store.get_by_token(token)

        # Validate state - can only pause active subscriptions
        if subscription.state != SubscriptionState.ACTIVE:
            raise InvalidSubscriptionStateError(
                f"Cannot pause subscription in {subscription.state.name} state. "
                "Only ACTIVE subscriptions can be paused."
            )

        # Set pause times
        current_time_millis = int(time.time() * 1000)
        subscription.pause_start_millis = current_time_millis
        subscription.pause_end_millis = current_time_millis + pause_duration_millis

        # Extend expiry by pause duration
        old_expiry = subscription.expiry_time_millis
        subscription.extend_expiry(
            old_expiry + pause_duration_millis,
            reason="Subscription paused",
        )

        # Transition to paused state
        subscription.set_state(
            SubscriptionState.PAUSED,
            reason="User paused subscription",
        )

        # Update in store
        self.store.update(subscription)

        logger.info(
            "subscription_paused",
            token=token[:20] + "...",
            subscription_id=subscription.subscription_id,
            user_id=subscription.user_id,
            pause_start=subscription.pause_start_millis,
            pause_end=subscription.pause_end_millis,
            new_expiry=subscription.expiry_time_millis,
        )

        self._publish_event(NotificationType.SUBSCRIPTION_PAUSED, subscription)

        return subscription

    def resume_subscription(self, token: str) -> SubscriptionRecord:
        """Resume a paused subscription.

        Transitions the subscription from PAUSED to ACTIVE state and clears pause times.

        Args:
            token: Subscription token

        Returns:
            Updated SubscriptionRecord

        Raises:
            SubscriptionNotFoundError: If token not found
            InvalidSubscriptionStateError: If subscription is not paused
        """
        subscription = self.store.get_by_token(token)

        # Validate state
        if subscription.state != SubscriptionState.PAUSED:
            raise InvalidSubscriptionStateError(
                f"Cannot resume subscription in {subscription.state.name} state. "
                "Only PAUSED subscriptions can be resumed."
            )

        # Calculate how much pause time was actually used
        current_time_millis = int(time.time() * 1000)
        if subscription.pause_start_millis:
            actual_pause_duration = (
                    current_time_millis - subscription.pause_start_millis
            )
            logger.debug(
                "pause_duration_calculated",
                token=token[:20] + "...",
                actual_pause_millis=actual_pause_duration,
                scheduled_pause_millis=(
                    subscription.pause_end_millis - subscription.pause_start_millis
                    if subscription.pause_end_millis
                    else 0
                ),
            )

        # Clear pause times
        subscription.pause_start_millis = None
        subscription.pause_end_millis = None

        # Transition to active state
        subscription.set_state(
            SubscriptionState.ACTIVE,
            reason="User resumed subscription",
        )

        # Update in store
        self.store.update(subscription)

        logger.info(
            "subscription_resumed",
            token=token[:20] + "...",
            subscription_id=subscription.subscription_id,
            user_id=subscription.user_id,
            expiry_millis=subscription.expiry_time_millis,
        )

        self._publish_event(NotificationType.SUBSCRIPTION_RESTARTED, subscription)

        return subscription

    def get_subscription(self, token: str) -> SubscriptionRecord:
        """Get subscription by token.

        Args:
            token: Subscription token

        Returns:
            SubscriptionRecord

        Raises:
            SubscriptionNotFoundError: If token not found
        """
        return self.store.get_by_token(token)

    def get_user_subscriptions(
            self, user_id: str, package_name: Optional[str] = None
    ) -> list[SubscriptionRecord]:
        """Get all subscriptions for a user.

        Args:
            user_id: User identifier
            package_name: Optional package name filter

        Returns:
            List of SubscriptionRecord objects
        """
        subscriptions = self.store.get_by_user(user_id)

        if package_name:
            subscriptions = [
                s for s in subscriptions if s.package_name == package_name
            ]

        return subscriptions

    def has_active_subscription(
            self,
            user_id: str,
            subscription_id: str,
            package_name: Optional[str] = None,
    ) -> bool:
        """Check if user has an active subscription.

        Args:
            user_id: User identifier
            subscription_id: Subscription product ID
            package_name: Package name (defaults to config default)

        Returns:
            True if user has active subscription, False otherwise
        """
        if package_name is None:
            package_name = self.config.default_package_name

        subscription = self.store.get_user_subscription(
            user_id=user_id,
            subscription_id=subscription_id,
            package_name=package_name,
        )

        if subscription is None:
            return False

        # Check if subscription is in an active state
        return subscription.state in (
            SubscriptionState.ACTIVE,
            SubscriptionState.PAUSED,
            SubscriptionState.IN_GRACE_PERIOD,
        )

    def renew_subscription(
            self,
            token: str,
            renewal_time_millis: Optional[int] = None,
    ) -> SubscriptionRecord:
        """Renew a subscription for another billing period.

        Extends the subscription expiry by one billing period and increments
        the renewal count. Handles trial-to-paid transitions.

        Args:
            token: Subscription token
            renewal_time_millis: Time of renewal (defaults to current expiry time)

        Returns:
            Updated SubscriptionRecord

        Raises:
            SubscriptionNotFoundError: If token not found
            InvalidSubscriptionStateError: If subscription cannot be renewed
            SubscriptionError: If renewal would be invalid
        """
        subscription = self.store.get_by_token(token)

        # Validate state - can only renew active or canceled subscriptions
        if subscription.state not in (
                SubscriptionState.ACTIVE,
                SubscriptionState.CANCELED,
        ):
            raise InvalidSubscriptionStateError(
                f"Cannot renew subscription in {subscription.state.name} state. "
                "Only ACTIVE or CANCELED subscriptions can be renewed."
            )

        # Cannot renew if auto-renewing is disabled (unless canceled, which will be reactivated)
        if not subscription.auto_renewing and subscription.state != SubscriptionState.CANCELED:
            raise SubscriptionError(
                "Cannot renew subscription with auto_renewing=False. "
                "Enable auto-renewal first."
            )

        # Get product definition for billing period
        product = self.product_repo.get_by_id(subscription.subscription_id)

        # Determine renewal time (defaults to current expiry)
        if renewal_time_millis is None:
            renewal_time_millis = subscription.expiry_time_millis

        # Handle trial-to-paid transition
        if subscription.in_trial:
            # Transitioning from trial to paid
            subscription.in_trial = False
            subscription.set_payment_state(
                PaymentState.PAYMENT_RECEIVED,
                reason="Trial ended, first paid renewal",
            )

        # Calculate new expiry
        billing_period_millis = parse_billing_period(product.billing_period)
        new_expiry_millis = renewal_time_millis + billing_period_millis

        # Extend expiry
        subscription.extend_expiry(
            new_expiry_millis,
            reason=f"Renewal #{subscription.renewal_count + 1}",
        )

        # Increment renewal count
        subscription.renewal_count += 1

        # If subscription was canceled, reactivate it
        if subscription.state == SubscriptionState.CANCELED:
            subscription.set_state(
                SubscriptionState.ACTIVE,
                reason="Subscription renewed after cancellation",
            )
            subscription.set_auto_renewing(True, reason="Renewed subscription")
            subscription.cancel_reason = None
            subscription.canceled_time_millis = None

        # Update in store
        self.store.update(subscription)

        logger.info(
            "subscription_renewed",
            token=token[:20] + "...",
            subscription_id=subscription.subscription_id,
            user_id=subscription.user_id,
            renewal_count=subscription.renewal_count,
            new_expiry=new_expiry_millis,
            from_trial=subscription.in_trial,
        )

        self._publish_event(NotificationType.SUBSCRIPTION_RENEWED, subscription)

        return subscription

    def simulate_payment_failure(
            self,
            token: str,
            failure_time_millis: Optional[int] = None,
    ) -> SubscriptionRecord:
        """Simulate a payment failure, moving subscription to grace period.

        When a renewal payment fails, the subscription enters a grace period
        where the user may retain or lose access depending on configuration.
        After the grace period expires, the subscription moves to account hold.

        Args:
            token: Subscription token
            failure_time_millis: Time of payment failure (defaults to now)

        Returns:
            Updated SubscriptionRecord

        Raises:
            SubscriptionNotFoundError: If token not found
            InvalidSubscriptionStateError: If subscription cannot have payment failure
        """
        subscription = self.store.get_by_token(token)

        # Can only fail payment on active subscriptions
        if subscription.state != SubscriptionState.ACTIVE:
            raise InvalidSubscriptionStateError(
                f"Cannot simulate payment failure on {subscription.state.name} subscription. "
                "Only ACTIVE subscriptions can have payment failures."
            )

        # Get product definition for grace period
        product = self.product_repo.get_by_id(subscription.subscription_id)

        if not product.grace_period:
            raise SubscriptionError(
                f"Product {subscription.subscription_id} has no grace_period configured"
            )

        # Determine failure time
        if failure_time_millis is None:
            failure_time_millis = int(time.time() * 1000)

        # Calculate grace period end
        grace_period_millis = parse_billing_period(product.grace_period)
        grace_period_end_millis = failure_time_millis + grace_period_millis
        subscription.grace_period_end_millis = grace_period_end_millis

        # Update payment state
        subscription.set_payment_state(
            PaymentState.PAYMENT_FAILED,
            reason="Payment failed at renewal",
        )

        # Transition to grace period
        subscription.set_state(
            SubscriptionState.IN_GRACE_PERIOD,
            reason="Payment failed, entered grace period",
        )

        # Update in store
        self.store.update(subscription)

        logger.info(
            "subscription_payment_failed",
            token=token[:20] + "...",
            subscription_id=subscription.subscription_id,
            user_id=subscription.user_id,
            grace_period_end=grace_period_end_millis,
            expiry_millis=subscription.expiry_time_millis,
        )

        self._publish_event(NotificationType.SUBSCRIPTION_IN_GRACE_PERIOD, subscription)

        return subscription

    def transition_to_account_hold(
            self,
            token: str,
            hold_time_millis: Optional[int] = None,
    ) -> SubscriptionRecord:
        """Transition subscription from grace period to account hold.

        Called when grace period expires without payment recovery.

        Args:
            token: Subscription token
            hold_time_millis: Time of account hold start (defaults to now)

        Returns:
            Updated SubscriptionRecord

        Raises:
            SubscriptionNotFoundError: If token not found
            InvalidSubscriptionStateError: If subscription is not in grace period
        """
        subscription = self.store.get_by_token(token)

        # Must be in grace period
        if subscription.state != SubscriptionState.IN_GRACE_PERIOD:
            raise InvalidSubscriptionStateError(
                f"Cannot transition to account hold from {subscription.state.name}. "
                "Must be IN_GRACE_PERIOD."
            )

        # Determine hold start time
        if hold_time_millis is None:
            hold_time_millis = int(time.time() * 1000)

        # Set account hold start time
        subscription.account_hold_start_millis = hold_time_millis

        # Clear grace period end
        subscription.grace_period_end_millis = None

        # Transition to on hold
        subscription.set_state(
            SubscriptionState.ON_HOLD,
            reason="Grace period expired without payment",
        )

        # Update in store
        self.store.update(subscription)

        logger.info(
            "subscription_on_hold",
            token=token[:20] + "...",
            subscription_id=subscription.subscription_id,
            user_id=subscription.user_id,
            hold_start=hold_time_millis,
            expiry_millis=subscription.expiry_time_millis,
        )

        self._publish_event(NotificationType.SUBSCRIPTION_ON_HOLD, subscription)

        return subscription

    def recover_from_payment_failure(
            self,
            token: str,
            recovery_time_millis: Optional[int] = None,
    ) -> SubscriptionRecord:
        """Recover subscription from payment failure (grace period or account hold).

        When payment is successfully retried, the subscription returns to active state.
        The expiry time is extended by the remaining grace period/hold duration.

        Args:
            token: Subscription token
            recovery_time_millis: Time of recovery (defaults to now)

        Returns:
            Updated SubscriptionRecord

        Raises:
            SubscriptionNotFoundError: If token not found
            InvalidSubscriptionStateError: If subscription is not in recoverable state
        """
        subscription = self.store.get_by_token(token)

        # Can only recover from grace period or account hold
        if subscription.state not in (
                SubscriptionState.IN_GRACE_PERIOD,
                SubscriptionState.ON_HOLD,
        ):
            raise InvalidSubscriptionStateError(
                f"Cannot recover from {subscription.state.name}. "
                "Must be IN_GRACE_PERIOD or ON_HOLD."
            )

        # Determine recovery time
        if recovery_time_millis is None:
            recovery_time_millis = int(time.time() * 1000)

        # Update payment state to received
        subscription.set_payment_state(
            PaymentState.PAYMENT_RECEIVED,
            reason="Payment recovered",
        )

        # Clear grace period and hold markers
        subscription.grace_period_end_millis = None
        subscription.account_hold_start_millis = None

        # Transition to active
        old_state = subscription.state
        subscription.set_state(
            SubscriptionState.ACTIVE,
            reason=f"Recovered from {old_state.name}",
        )

        # Update in store
        self.store.update(subscription)

        logger.info(
            "subscription_recovered",
            token=token[:20] + "...",
            subscription_id=subscription.subscription_id,
            user_id=subscription.user_id,
            recovered_from=old_state.name,
            recovery_time=recovery_time_millis,
            expiry_millis=subscription.expiry_time_millis,
        )

        self._publish_event(NotificationType.SUBSCRIPTION_RECOVERED, subscription)

        return subscription

    def process_grace_period_expirations(
            self,
            current_time_millis: int,
    ) -> list[SubscriptionRecord]:
        """Process all subscriptions with expired grace periods.

        Transitions subscriptions from IN_GRACE_PERIOD to ON_HOLD if their
        grace period has expired.

        Args:
            current_time_millis: Current time to check against

        Returns:
            List of subscriptions transitioned to account hold
        """
        grace_period_subs = self.store.get_in_grace_period()
        transitioned = []

        for subscription in grace_period_subs:
            if (
                    subscription.grace_period_end_millis
                    and current_time_millis >= subscription.grace_period_end_millis
            ):
                try:
                    updated = self.transition_to_account_hold(
                        subscription.token,
                        hold_time_millis=current_time_millis,
                    )
                    transitioned.append(updated)
                except Exception as e:
                    logger.error(
                        "grace_period_expiration_failed",
                        token=subscription.token[:20] + "...",
                        error=str(e),
                    )

        if transitioned:
            logger.info(
                "grace_periods_processed",
                count=len(transitioned),
                current_time=current_time_millis,
            )

        return transitioned

    def defer_subscription(self, token: str, new_expiry_millis: int) -> SubscriptionRecord:
        """Defer subscription renewal by extending expiry time.

        Args:
            token: Subscription token
            new_expiry_millis: New expiry time in milliseconds

        Returns:
            Updated SubscriptionRecord

        Raises:
            SubscriptionNotFoundError: If subscription not found
            ValueError: If new expiry is before current expiry
        """
        subscription = self.store.get_by_token(token)

        # Validate new expiry is in the future
        if new_expiry_millis <= subscription.expiry_time_millis:
            raise ValueError(
                f"New expiry time ({new_expiry_millis}) must be after "
                f"current expiry ({subscription.expiry_time_millis})"
            )

        # Update expiry time
        old_expiry = subscription.expiry_time_millis
        subscription.expiry_time_millis = new_expiry_millis

        # Update in store
        self.store.update(subscription)

        logger.info(
            "subscription_deferred",
            token=token[:20] + "...",
            subscription_id=subscription.subscription_id,
            old_expiry_millis=old_expiry,
            new_expiry_millis=new_expiry_millis,
            deferred_by_millis=new_expiry_millis - old_expiry,
        )

        self._publish_event(NotificationType.SUBSCRIPTION_DEFERRED, subscription)

        return subscription

    def revoke_subscription(
            self,
            token: str,
            revoke_time_millis: Optional[int] = None,
    ) -> SubscriptionRecord:
        """Revoke a subscription immediately (used by Google API revoke endpoint).

        Revocation is an immediate cancellation that terminates access right away,
        typically used by Google Play to revoke subscriptions due to refunds or
        violations.

        Args:
            token: Subscription token
            revoke_time_millis: Time of revocation (defaults to now)

        Returns:
            Updated SubscriptionRecord

        Raises:
            SubscriptionNotFoundError: If token not found
            InvalidSubscriptionStateError: If subscription cannot be revoked
        """
        subscription = self.store.get_by_token(token)

        # Can only revoke non-expired subscriptions
        if subscription.state == SubscriptionState.EXPIRED:
            raise InvalidSubscriptionStateError(
                "Cannot revoke an already expired subscription"
            )

        # Determine revoke time
        if revoke_time_millis is None:
            revoke_time_millis = int(time.time() * 1000)

        # Mark as revoked (use canceled fields for tracking)
        subscription.canceled_time_millis = revoke_time_millis
        subscription.cancel_reason = CancelReason.SYSTEM_CANCELED
        subscription.set_auto_renewing(False, reason="Subscription revoked")

        # Expire immediately
        subscription.set_state(
            SubscriptionState.EXPIRED,
            reason="Subscription revoked",
        )
        subscription.expiry_time_millis = revoke_time_millis

        # Update in store
        self.store.update(subscription)

        logger.info(
            "subscription_revoked",
            token=token[:20] + "...",
            subscription_id=subscription.subscription_id,
            user_id=subscription.user_id,
            revoke_time=revoke_time_millis,
        )

        # Publish SUBSCRIPTION_REVOKED event
        self._publish_event(NotificationType.SUBSCRIPTION_REVOKED, subscription)

        return subscription

    def acknowledge_subscription(self, token: str) -> SubscriptionRecord:
        """Acknowledge a subscription purchase.

        Marks the subscription as acknowledged.

        Args:
            token: Subscription token

        Returns:
            Updated SubscriptionRecord

        Raises:
            SubscriptionNotFoundError: If token not found
        """
        subscription = self.store.get_by_token(token)

        subscription.acknowledge()
        self.store.update(subscription)

        logger.info(
            "subscription_acknowledged",
            token=token[:20] + "...",
            subscription_id=subscription.subscription_id,
            user_id=subscription.user_id,
        )

        return subscription


# Global engine instance
_engine_instance: Optional[SubscriptionEngine] = None


def get_subscription_engine() -> SubscriptionEngine:
    """Get global subscription engine instance (singleton).

    Returns:
        SubscriptionEngine instance
    """
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = SubscriptionEngine()
    return _engine_instance
