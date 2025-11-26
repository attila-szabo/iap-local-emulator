"""Tests for state change logging functionality.

Tests subscription and purchase state transitions with automatic logging.
"""

import os
import time

import pytest

from iap_emulator.logging_config import configure_logging
from iap_emulator.models.purchase import (
    AcknowledgementState,
    ConsumptionState,
    ProductPurchaseRecord,
    PurchaseState,
)
from iap_emulator.models.subscription import (
    PaymentState,
    SubscriptionRecord,
    SubscriptionState,
)


@pytest.fixture(scope="module")
def setup_logging():
    """Configure logging for all tests in this module."""
    log_level = os.getenv("LOG_LEVEL", "INFO")
    log_format = os.getenv("LOG_FORMAT", "console")
    json_mode = log_format.lower() == "json"

    configure_logging(log_level=log_level, json_format=json_mode)
    yield


@pytest.fixture
def subscription():
    """Create a test subscription for testing."""
    now_millis = int(time.time() * 1000)
    return SubscriptionRecord(
        token="emulator_sub_abc123xyz789",
        subscription_id="premium.personal.yearly",
        package_name="com.example.app",
        user_id="user-12345",
        start_time_millis=now_millis,
        expiry_time_millis=now_millis + (365 * 24 * 60 * 60 * 1000),
        purchase_time_millis=now_millis,
        order_id="GPA.1234-5678-9012",
        price_amount_micros=29990000,
    )


@pytest.fixture
def purchase():
    """Create a test purchase for testing."""
    now_millis = int(time.time() * 1000)
    return ProductPurchaseRecord(
        token="emulator_purchase_xyz789abc123",
        product_id="coins_1000",
        package_name="com.example.game",
        user_id="user-67890",
        purchase_time_millis=now_millis,
        order_id="GPA.9876-5432-1098",
        price_amount_micros=4990000,
    )


class TestSubscriptionStateChanges:
    """Test subscription state transitions."""

    def test_change_to_canceled(self, setup_logging, subscription):
        """Test changing subscription to canceled state."""
        initial_state = subscription.state
        subscription.set_state(SubscriptionState.CANCELED, reason="user_requested")

        assert subscription.state == SubscriptionState.CANCELED
        assert subscription.state != initial_state

    def test_disable_auto_renew(self, setup_logging, subscription):
        """Test disabling auto-renewal."""
        assert subscription.auto_renewing is True  # Default
        subscription.set_auto_renewing(False, reason="user_disabled")

        assert subscription.auto_renewing is False

    def test_enable_auto_renew(self, setup_logging, subscription):
        """Test enabling auto-renewal."""
        subscription.auto_renewing = False
        subscription.set_auto_renewing(True, reason="user_enabled")

        assert subscription.auto_renewing is True

    def test_payment_failure_to_grace_period(self, setup_logging, subscription):
        """Test payment failure leading to grace period."""
        subscription.set_payment_state(
            PaymentState.PAYMENT_FAILED, reason="insufficient_funds"
        )
        subscription.set_state(
            SubscriptionState.IN_GRACE_PERIOD, reason="payment_failed"
        )

        assert subscription.payment_state == PaymentState.PAYMENT_FAILED
        assert subscription.state == SubscriptionState.IN_GRACE_PERIOD

    def test_payment_recovery(self, setup_logging, subscription):
        """Test payment recovery from grace period."""
        # First fail
        subscription.set_payment_state(
            PaymentState.PAYMENT_FAILED, reason="insufficient_funds"
        )
        subscription.set_state(
            SubscriptionState.IN_GRACE_PERIOD, reason="payment_failed"
        )

        # Then recover
        subscription.set_payment_state(
            PaymentState.PAYMENT_RECEIVED, reason="payment_recovered"
        )
        subscription.set_state(SubscriptionState.ACTIVE, reason="payment_recovered")

        assert subscription.payment_state == PaymentState.PAYMENT_RECEIVED
        assert subscription.state == SubscriptionState.ACTIVE

    def test_extend_expiry(self, setup_logging, subscription):
        """Test extending subscription expiry time."""
        original_expiry = subscription.expiry_time_millis
        new_expiry = original_expiry + (365 * 24 * 60 * 60 * 1000)

        subscription.extend_expiry(new_expiry, reason="subscription_renewed")

        assert subscription.expiry_time_millis == new_expiry
        assert subscription.expiry_time_millis > original_expiry

    def test_enter_account_hold(self, setup_logging, subscription):
        """Test entering account hold state."""
        subscription.set_payment_state(
            PaymentState.PAYMENT_FAILED, reason="card_declined"
        )
        subscription.set_state(SubscriptionState.ON_HOLD, reason="grace_period_expired")

        assert subscription.payment_state == PaymentState.PAYMENT_FAILED
        assert subscription.state == SubscriptionState.ON_HOLD

    def test_subscription_expires(self, setup_logging, subscription):
        """Test subscription expiration."""
        subscription.set_state(
            SubscriptionState.EXPIRED, reason="max_hold_time_exceeded"
        )

        assert subscription.state == SubscriptionState.EXPIRED


class TestPurchaseStateChanges:
    """Test purchase state transitions."""

    def test_initial_purchase_state(self, setup_logging, purchase):
        """Test initial purchase state."""
        assert purchase.purchase_state == PurchaseState.PURCHASED
        assert purchase.consumption_state == ConsumptionState.NOT_CONSUMED
        assert purchase.acknowledgement_state == AcknowledgementState.NOT_ACKNOWLEDGED

    def test_acknowledge_purchase(self, setup_logging, purchase):
        """Test acknowledging a purchase."""
        assert purchase.acknowledgement_state == AcknowledgementState.NOT_ACKNOWLEDGED

        purchase.acknowledge()

        assert purchase.acknowledgement_state == AcknowledgementState.ACKNOWLEDGED

    def test_consume_purchase(self, setup_logging, purchase):
        """Test consuming a purchase."""
        assert purchase.consumption_state == ConsumptionState.NOT_CONSUMED

        purchase.consume()

        assert purchase.consumption_state == ConsumptionState.CONSUMED

    def test_acknowledge_then_consume(self, setup_logging, purchase):
        """Test acknowledging then consuming a purchase."""
        purchase.acknowledge()
        assert purchase.acknowledgement_state == AcknowledgementState.ACKNOWLEDGED

        purchase.consume()
        assert purchase.consumption_state == ConsumptionState.CONSUMED

    def test_cancel_purchase(self, setup_logging, purchase):
        """Test canceling a purchase (refund)."""
        purchase.set_purchase_state(PurchaseState.CANCELED, reason="user_refund_request")

        assert purchase.purchase_state == PurchaseState.CANCELED

    def test_pending_to_purchased(self, setup_logging, purchase):
        """Test transition from pending to purchased."""
        purchase.set_purchase_state(PurchaseState.PENDING, reason="payment_processing")
        assert purchase.purchase_state == PurchaseState.PENDING

        purchase.set_purchase_state(PurchaseState.PURCHASED, reason="payment_completed")
        assert purchase.purchase_state == PurchaseState.PURCHASED

    def test_consume_acknowledged_purchase(self, setup_logging, purchase):
        """Test consuming an acknowledged purchase."""
        purchase.acknowledge()
        purchase.consume()

        assert purchase.acknowledgement_state == AcknowledgementState.ACKNOWLEDGED
        assert purchase.consumption_state == ConsumptionState.CONSUMED


class TestPurchaseConsumptionPatterns:
    """Test different purchase consumption patterns."""

    def test_immediate_consumption(self, setup_logging, purchase):
        """Test immediate consumption without acknowledgement."""
        purchase.consume()
        assert purchase.consumption_state == ConsumptionState.CONSUMED

    def test_acknowledge_without_consume(self, setup_logging, purchase):
        """Test acknowledging without consuming (non-consumable)."""
        purchase.acknowledge()

        assert purchase.acknowledgement_state == AcknowledgementState.ACKNOWLEDGED
        assert purchase.consumption_state == ConsumptionState.NOT_CONSUMED

    def test_multiple_state_changes(self, setup_logging, purchase):
        """Test multiple state changes in sequence."""
        # Start as pending
        purchase.set_purchase_state(PurchaseState.PENDING, reason="payment_processing")
        assert purchase.purchase_state == PurchaseState.PENDING

        # Complete purchase
        purchase.set_purchase_state(PurchaseState.PURCHASED, reason="payment_completed")
        assert purchase.purchase_state == PurchaseState.PURCHASED

        # Consume immediately
        purchase.consume()
        assert purchase.consumption_state == ConsumptionState.CONSUMED


class TestSubscriptionLifecycle:
    """Test full subscription lifecycle scenarios."""

    def test_active_to_expired_lifecycle(self, setup_logging):
        """Test complete lifecycle from active to expired."""
        now_millis = int(time.time() * 1000)
        month_millis = 30 * 24 * 60 * 60 * 1000

        sub = SubscriptionRecord(
            token="emulator_lifecycle_test",
            subscription_id="premium.monthly",
            package_name="com.example.app",
            user_id="user-lifecycle",
            start_time_millis=now_millis,
            expiry_time_millis=now_millis + month_millis,
            purchase_time_millis=now_millis,
            order_id="GPA.LIFECYCLE-001",
            price_amount_micros=9990000,
        )

        # Month 1: Active
        assert sub.state == SubscriptionState.ACTIVE
        assert sub.auto_renewing is True

        # Month 2: Renewal
        sub.extend_expiry(sub.expiry_time_millis + month_millis, reason="subscription_renewed")
        sub.renewal_count += 1
        assert sub.renewal_count == 1

        # Month 3: Payment fails
        sub.set_payment_state(PaymentState.PAYMENT_FAILED, reason="card_expired")
        sub.set_state(SubscriptionState.IN_GRACE_PERIOD, reason="payment_failed")
        assert sub.state == SubscriptionState.IN_GRACE_PERIOD

        # Month 3 (mid): Payment recovered
        sub.set_payment_state(
            PaymentState.PAYMENT_RECEIVED, reason="updated_payment_method"
        )
        sub.set_state(SubscriptionState.ACTIVE, reason="payment_recovered")
        sub.extend_expiry(
            sub.expiry_time_millis + month_millis, reason="subscription_renewed"
        )
        sub.renewal_count += 1
        assert sub.renewal_count == 2

        # Month 4: User cancels
        sub.set_auto_renewing(False, reason="user_canceled")
        sub.set_state(SubscriptionState.CANCELED, reason="user_canceled")
        sub.canceled_time_millis = int(time.time() * 1000)
        assert sub.state == SubscriptionState.CANCELED
        assert sub.auto_renewing is False

        # Expiry time reached
        sub.set_state(SubscriptionState.EXPIRED, reason="expiry_time_reached")
        assert sub.state == SubscriptionState.EXPIRED

    def test_payment_failure_to_hold_to_expired(self, setup_logging):
        """Test payment failure through hold to expiration."""
        now_millis = int(time.time() * 1000)

        sub = SubscriptionRecord(
            token="emulator_hold_test",
            subscription_id="premium.personal.yearly",
            package_name="com.example.app",
            user_id="user-hold-test",
            start_time_millis=now_millis,
            expiry_time_millis=now_millis + (365 * 24 * 60 * 60 * 1000),
            purchase_time_millis=now_millis,
            order_id="GPA.HOLD-001",
            price_amount_micros=29990000,
        )

        # Payment fails
        sub.set_payment_state(PaymentState.PAYMENT_FAILED, reason="insufficient_funds")
        sub.set_state(SubscriptionState.IN_GRACE_PERIOD, reason="payment_failed")

        # Grace period expires, enter hold
        sub.set_state(SubscriptionState.ON_HOLD, reason="grace_period_expired")
        assert sub.state == SubscriptionState.ON_HOLD

        # Hold expires
        sub.set_state(SubscriptionState.EXPIRED, reason="max_hold_time_exceeded")
        assert sub.state == SubscriptionState.EXPIRED

    def test_immediate_cancellation(self, setup_logging):
        """Test immediate cancellation after creation."""
        now_millis = int(time.time() * 1000)

        sub = SubscriptionRecord(
            token="emulator_cancel_test",
            subscription_id="premium.monthly",
            package_name="com.example.app",
            user_id="user-cancel-test",
            start_time_millis=now_millis,
            expiry_time_millis=now_millis + (30 * 24 * 60 * 60 * 1000),
            purchase_time_millis=now_millis,
            order_id="GPA.CANCEL-001",
            price_amount_micros=9990000,
        )

        # Immediately cancel
        sub.set_auto_renewing(False, reason="user_canceled")
        sub.set_state(SubscriptionState.CANCELED, reason="user_canceled")

        assert sub.state == SubscriptionState.CANCELED
        assert sub.auto_renewing is False


class TestPaymentStateTransitions:
    """Test payment state transitions."""

    def test_payment_pending_to_received(self, setup_logging, subscription):
        """Test payment transition from pending to received."""
        subscription.set_payment_state(
            PaymentState.PAYMENT_PENDING, reason="processing"
        )
        assert subscription.payment_state == PaymentState.PAYMENT_PENDING

        subscription.set_payment_state(
            PaymentState.PAYMENT_RECEIVED, reason="completed"
        )
        assert subscription.payment_state == PaymentState.PAYMENT_RECEIVED

    def test_payment_pending_to_failed(self, setup_logging, subscription):
        """Test payment transition from pending to failed."""
        subscription.set_payment_state(
            PaymentState.PAYMENT_PENDING, reason="processing"
        )
        assert subscription.payment_state == PaymentState.PAYMENT_PENDING

        subscription.set_payment_state(
            PaymentState.PAYMENT_FAILED, reason="insufficient_funds"
        )
        assert subscription.payment_state == PaymentState.PAYMENT_FAILED

    def test_payment_failed_to_received(self, setup_logging, subscription):
        """Test payment recovery from failed state."""
        subscription.set_payment_state(
            PaymentState.PAYMENT_FAILED, reason="card_declined"
        )
        assert subscription.payment_state == PaymentState.PAYMENT_FAILED

        subscription.set_payment_state(
            PaymentState.PAYMENT_RECEIVED, reason="retry_succeeded"
        )
        assert subscription.payment_state == PaymentState.PAYMENT_RECEIVED


class TestSubscriptionRenewals:
    """Test subscription renewal scenarios."""

    def test_successful_renewal(self, setup_logging, subscription):
        """Test successful subscription renewal."""
        original_expiry = subscription.expiry_time_millis
        original_renewals = subscription.renewal_count

        new_expiry = original_expiry + (365 * 24 * 60 * 60 * 1000)
        subscription.extend_expiry(new_expiry, reason="subscription_renewed")
        subscription.renewal_count += 1

        assert subscription.expiry_time_millis > original_expiry
        assert subscription.renewal_count == original_renewals + 1

    def test_multiple_renewals(self, setup_logging, subscription):
        """Test multiple consecutive renewals."""
        year_millis = 365 * 24 * 60 * 60 * 1000

        for i in range(3):
            original_expiry = subscription.expiry_time_millis
            new_expiry = original_expiry + year_millis
            subscription.extend_expiry(new_expiry, reason="subscription_renewed")
            subscription.renewal_count += 1

        assert subscription.renewal_count == 3

    def test_renewal_with_auto_renew_disabled(self, setup_logging, subscription):
        """Test that renewal tracking works even with auto-renew disabled."""
        subscription.set_auto_renewing(False, reason="user_disabled")
        original_expiry = subscription.expiry_time_millis

        # Manual renewal
        new_expiry = original_expiry + (365 * 24 * 60 * 60 * 1000)
        subscription.extend_expiry(new_expiry, reason="manual_renewal")

        assert subscription.expiry_time_millis > original_expiry
        assert subscription.auto_renewing is False


class TestStateChangeReasons:
    """Test that state change reasons are properly handled."""

    def test_state_change_with_reason(self, setup_logging, subscription):
        """Test state change with explicit reason."""
        subscription.set_state(SubscriptionState.CANCELED, reason="user_requested")
        assert subscription.state == SubscriptionState.CANCELED

    def test_state_change_without_reason(self, setup_logging, subscription):
        """Test state change without reason (should still work)."""
        subscription.set_state(SubscriptionState.CANCELED)
        assert subscription.state == SubscriptionState.CANCELED

    def test_payment_state_with_reason(self, setup_logging, subscription):
        """Test payment state change with reason."""
        subscription.set_payment_state(
            PaymentState.PAYMENT_FAILED, reason="insufficient_funds"
        )
        assert subscription.payment_state == PaymentState.PAYMENT_FAILED

    def test_auto_renew_change_with_reason(self, setup_logging, subscription):
        """Test auto-renew change with reason."""
        subscription.set_auto_renewing(False, reason="user_disabled")
        assert subscription.auto_renewing is False


# Parametrized tests for subscription states
@pytest.mark.parametrize(
    "target_state,reason",
    [
        (SubscriptionState.ACTIVE, "payment_received"),
        (SubscriptionState.CANCELED, "user_canceled"),
        (SubscriptionState.IN_GRACE_PERIOD, "payment_failed"),
        (SubscriptionState.ON_HOLD, "grace_period_expired"),
        (SubscriptionState.PAUSED, "user_paused"),
        (SubscriptionState.EXPIRED, "expiry_time_reached"),
    ],
)
def test_subscription_state_transitions(setup_logging, subscription, target_state, reason):
    """Test various subscription state transitions."""
    subscription.set_state(target_state, reason=reason)
    assert subscription.state == target_state


@pytest.mark.parametrize(
    "target_payment_state,reason",
    [
        (PaymentState.PAYMENT_RECEIVED, "payment_completed"),
        (PaymentState.PAYMENT_PENDING, "payment_processing"),
        (PaymentState.PAYMENT_FAILED, "card_declined"),
        (PaymentState.FREE_TRIAL, "trial_period"),
    ],
)
def test_payment_state_transitions(
    setup_logging, subscription, target_payment_state, reason
):
    """Test various payment state transitions."""
    subscription.set_payment_state(target_payment_state, reason=reason)
    assert subscription.payment_state == target_payment_state


@pytest.mark.parametrize(
    "target_purchase_state,reason",
    [
        (PurchaseState.PURCHASED, "payment_completed"),
        (PurchaseState.PENDING, "payment_processing"),
        (PurchaseState.CANCELED, "user_refund"),
    ],
)
def test_purchase_state_transitions(setup_logging, purchase, target_purchase_state, reason):
    """Test various purchase state transitions."""
    purchase.set_purchase_state(target_purchase_state, reason=reason)
    assert purchase.purchase_state == target_purchase_state


@pytest.mark.parametrize("auto_renew_value", [True, False])
def test_auto_renew_values(setup_logging, subscription, auto_renew_value):
    """Test setting auto-renew to different values."""
    subscription.set_auto_renewing(auto_renew_value, reason="test")
    assert subscription.auto_renewing == auto_renew_value
