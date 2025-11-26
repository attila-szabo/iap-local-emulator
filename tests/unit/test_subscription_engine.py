"""Unit tests for SubscriptionEngine service."""

import time
from unittest.mock import MagicMock, patch

import pytest

from iap_emulator.models.product import ProductDefinition
from iap_emulator.models.subscription import (
    CancelReason,
    PaymentState,
    SubscriptionState,
)
from iap_emulator.repositories.product_repository import ProductRepository
from iap_emulator.repositories.subscription_store import SubscriptionStore
from iap_emulator.services.subscription_engine import (
    InvalidSubscriptionStateError,
    SubscriptionEngine,
    SubscriptionError,
)
from iap_emulator.utils.billing_period import parse_billing_period


@pytest.fixture
def mock_config():
    """Mock configuration."""
    config = MagicMock()
    config.default_package_name = "com.example.test"
    config.emulator_settings.token_prefix = "test"
    return config


@pytest.fixture
def product_repo():
    """Create a product repository with test products."""
    # Create mock config with products
    mock_config = MagicMock()
    mock_config.products.subscriptions = [
        ProductDefinition(
            id="premium.monthly",
            type="subs",
            title="Premium Monthly",
            description="Monthly subscription",
            price_micros=9990000,
            currency="USD",
            billing_period="P1M",
            trial_period="P7D",
            grace_period="P3D",
        ),
        ProductDefinition(
            id="premium.yearly",
            type="subs",
            title="Premium Yearly",
            description="Yearly subscription",
            price_micros=99990000,
            currency="USD",
            billing_period="P1Y",
            trial_period="P30D",
        ),
    ]
    return ProductRepository(config=mock_config)


@pytest.fixture
def subscription_store():
    """Create a fresh subscription store for each test."""
    store = SubscriptionStore()
    yield store
    store.clear()


@pytest.fixture
def engine(subscription_store, product_repo, mock_config):
    """Create a subscription engine with test dependencies."""
    with patch("iap_emulator.services.subscription_engine.get_config", return_value=mock_config):
        engine = SubscriptionEngine(
            subscription_store=subscription_store,
            product_repository=product_repo,
        )
        yield engine


class TestSubscriptionCreation:
    """Tests for subscription creation."""

    def test_create_basic_subscription(self, engine):
        """Test creating a basic subscription without trial."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-123",
        )

        assert subscription.token is not None
        assert subscription.subscription_id == "premium.monthly"
        assert subscription.user_id == "user-123"
        assert subscription.package_name == "com.example.test"
        assert subscription.state == SubscriptionState.ACTIVE
        assert subscription.payment_state == PaymentState.PAYMENT_RECEIVED
        assert subscription.auto_renewing is True
        assert subscription.in_trial is False
        assert subscription.renewal_count == 0
        assert subscription.price_amount_micros == 9990000
        assert subscription.price_currency_code == "USD"

        # Check expiry time is approximately 1 month from now
        expected_duration = parse_billing_period("P1M")
        actual_duration = subscription.expiry_time_millis - subscription.start_time_millis
        assert abs(actual_duration - expected_duration) < 1000  # Within 1 second

    def test_create_subscription_with_trial(self, engine):
        """Test creating a subscription with trial period."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-456",
            with_trial=True,
        )

        assert subscription.in_trial is True
        assert subscription.payment_state == PaymentState.FREE_TRIAL
        assert subscription.trial_expiry_millis is not None

        # Check expiry is at trial end
        expected_trial_duration = parse_billing_period("P7D")
        actual_duration = subscription.expiry_time_millis - subscription.start_time_millis
        assert abs(actual_duration - expected_trial_duration) < 1000

    def test_create_subscription_custom_start_time(self, engine):
        """Test creating a subscription with custom start time."""
        custom_start = int(time.time() * 1000) - 86400000  # 1 day ago

        subscription = engine.create_subscription(
            subscription_id="premium.yearly",
            user_id="user-789",
            start_time_millis=custom_start,
        )

        assert subscription.start_time_millis == custom_start
        assert subscription.purchase_time_millis == custom_start

        # Expiry should be 1 year from custom start
        expected_duration = parse_billing_period("P1Y")
        actual_duration = subscription.expiry_time_millis - custom_start
        assert abs(actual_duration - expected_duration) < 1000

    def test_create_subscription_custom_package_name(self, engine):
        """Test creating a subscription with custom package name."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-custom",
            package_name="com.custom.app",
        )

        assert subscription.package_name == "com.custom.app"

    def test_create_subscription_duplicate_user(self, engine):
        """Test that creating duplicate subscription for same user fails."""
        # Create first subscription
        engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-duplicate",
        )

        # Attempt to create duplicate should fail
        with pytest.raises(SubscriptionError, match="already has an active subscription"):
            engine.create_subscription(
                subscription_id="premium.monthly",
                user_id="user-duplicate",
            )

    def test_create_subscription_after_expired(self, engine):
        """Test that user can create new subscription after previous expired."""
        # Create and expire first subscription
        sub1 = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-renew",
        )
        sub1.state = SubscriptionState.EXPIRED
        engine.store.update(sub1)

        # Should be able to create new subscription
        sub2 = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-renew",
        )

        assert sub2.token != sub1.token
        assert sub2.state == SubscriptionState.ACTIVE

    def test_create_subscription_invalid_product(self, engine):
        """Test creating subscription with invalid product ID."""
        from iap_emulator.repositories.product_repository import ProductNotFoundError

        with pytest.raises(ProductNotFoundError):
            engine.create_subscription(
                subscription_id="invalid.product",
                user_id="user-invalid",
            )


class TestSubscriptionCancellation:
    """Tests for subscription cancellation."""

    def test_cancel_subscription_at_period_end(self, engine):
        """Test canceling subscription at period end (default behavior)."""
        # Create subscription
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-cancel",
        )
        original_expiry = subscription.expiry_time_millis

        # Cancel subscription
        canceled = engine.cancel_subscription(subscription.token)

        assert canceled.state == SubscriptionState.CANCELED
        assert canceled.auto_renewing is False
        assert canceled.cancel_reason == CancelReason.USER_CANCELED
        assert canceled.canceled_time_millis is not None
        assert canceled.expiry_time_millis == original_expiry  # Unchanged

    def test_cancel_subscription_immediately(self, engine):
        """Test canceling subscription with immediate expiry."""
        # Create subscription
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-cancel-immediate",
        )
        original_expiry = subscription.expiry_time_millis

        # Cancel immediately
        canceled = engine.cancel_subscription(
            subscription.token,
            immediate=True,
        )

        assert canceled.state == SubscriptionState.EXPIRED
        assert canceled.auto_renewing is False
        assert canceled.cancel_reason == CancelReason.USER_CANCELED
        assert canceled.expiry_time_millis < original_expiry  # Moved to now

    def test_cancel_with_custom_reason(self, engine):
        """Test canceling subscription with custom reason."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-cancel-dev",
        )

        canceled = engine.cancel_subscription(
            subscription.token,
            cancel_reason=CancelReason.DEVELOPER_CANCELED,
        )

        assert canceled.cancel_reason == CancelReason.DEVELOPER_CANCELED

    def test_cancel_paused_subscription(self, engine):
        """Test canceling a paused subscription."""
        # Create and pause
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-cancel-paused",
        )
        engine.pause_subscription(subscription.token, pause_duration_millis=7 * 86400000)

        # Cancel should work
        canceled = engine.cancel_subscription(subscription.token)
        assert canceled.state == SubscriptionState.CANCELED

    def test_cancel_already_canceled_fails(self, engine):
        """Test that canceling an already canceled subscription fails."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-double-cancel",
        )

        # First cancellation
        engine.cancel_subscription(subscription.token)

        # Second cancellation should fail
        with pytest.raises(InvalidSubscriptionStateError):
            engine.cancel_subscription(subscription.token)

    def test_cancel_expired_subscription_fails(self, engine):
        """Test that canceling an expired subscription fails."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-cancel-expired",
        )

        # Mark as expired
        subscription.state = SubscriptionState.EXPIRED
        engine.store.update(subscription)

        # Cancellation should fail
        with pytest.raises(InvalidSubscriptionStateError):
            engine.cancel_subscription(subscription.token)


class TestSubscriptionPause:
    """Tests for subscription pause functionality."""

    def test_pause_active_subscription(self, engine):
        """Test pausing an active subscription."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-pause",
        )
        original_expiry = subscription.expiry_time_millis

        # Pause for 7 days
        pause_duration = 7 * 86400000  # 7 days in milliseconds
        paused = engine.pause_subscription(subscription.token, pause_duration)

        assert paused.state == SubscriptionState.PAUSED
        assert paused.pause_start_millis is not None
        assert paused.pause_end_millis is not None
        assert paused.pause_end_millis - paused.pause_start_millis == pause_duration
        # Expiry should be extended by pause duration
        assert paused.expiry_time_millis == original_expiry + pause_duration

    def test_pause_extends_expiry(self, engine):
        """Test that pausing extends the subscription expiry."""
        subscription = engine.create_subscription(
            subscription_id="premium.yearly",
            user_id="user-pause-extend",
        )
        original_expiry = subscription.expiry_time_millis

        # Pause for 30 days
        pause_duration = 30 * 86400000
        paused = engine.pause_subscription(subscription.token, pause_duration)

        # Expiry should be exactly original + pause duration
        assert paused.expiry_time_millis == original_expiry + pause_duration

    def test_pause_non_active_subscription_fails(self, engine):
        """Test that pausing a non-active subscription fails."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-pause-canceled",
        )

        # Cancel the subscription
        engine.cancel_subscription(subscription.token)

        # Pause should fail
        with pytest.raises(InvalidSubscriptionStateError, match="Only ACTIVE"):
            engine.pause_subscription(subscription.token, 7 * 86400000)

    def test_pause_with_invalid_duration_fails(self, engine):
        """Test that pausing with invalid duration fails."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-pause-invalid",
        )

        # Zero duration
        with pytest.raises(ValueError, match="must be positive"):
            engine.pause_subscription(subscription.token, 0)

        # Negative duration
        with pytest.raises(ValueError, match="must be positive"):
            engine.pause_subscription(subscription.token, -1000)


class TestSubscriptionResume:
    """Tests for subscription resume functionality."""

    def test_resume_paused_subscription(self, engine):
        """Test resuming a paused subscription."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-resume",
        )

        # Pause then resume
        paused = engine.pause_subscription(subscription.token, 7 * 86400000)
        assert paused.state == SubscriptionState.PAUSED

        resumed = engine.resume_subscription(subscription.token)

        assert resumed.state == SubscriptionState.ACTIVE
        assert resumed.pause_start_millis is None
        assert resumed.pause_end_millis is None
        # Expiry remains extended (doesn't revert)

    def test_resume_active_subscription_fails(self, engine):
        """Test that resuming an active subscription fails."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-resume-active",
        )

        # Try to resume without pausing
        with pytest.raises(InvalidSubscriptionStateError, match="Only PAUSED"):
            engine.resume_subscription(subscription.token)

    def test_resume_canceled_subscription_fails(self, engine):
        """Test that resuming a canceled subscription fails."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-resume-canceled",
        )

        # Cancel the subscription
        engine.cancel_subscription(subscription.token)

        # Resume should fail
        with pytest.raises(InvalidSubscriptionStateError, match="Only PAUSED"):
            engine.resume_subscription(subscription.token)

    def test_pause_resume_cycle(self, engine):
        """Test multiple pause-resume cycles."""
        subscription = engine.create_subscription(
            subscription_id="premium.yearly",
            user_id="user-cycle",
        )
        original_expiry = subscription.expiry_time_millis

        # First pause-resume cycle
        engine.pause_subscription(subscription.token, 10 * 86400000)
        sub = engine.resume_subscription(subscription.token)
        assert sub.state == SubscriptionState.ACTIVE
        expiry_after_first = sub.expiry_time_millis

        # Second pause-resume cycle
        engine.pause_subscription(subscription.token, 5 * 86400000)
        sub = engine.resume_subscription(subscription.token)
        assert sub.state == SubscriptionState.ACTIVE
        expiry_after_second = sub.expiry_time_millis

        # Total extension should be 10 + 5 = 15 days
        total_extension = expiry_after_second - original_expiry
        expected_extension = (10 + 5) * 86400000
        assert abs(total_extension - expected_extension) < 1000  # Within 1 second


class TestSubscriptionQueries:
    """Tests for subscription query methods."""

    def test_get_subscription(self, engine):
        """Test getting subscription by token."""
        created = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-get",
        )

        retrieved = engine.get_subscription(created.token)

        assert retrieved.token == created.token
        assert retrieved.user_id == created.user_id

    def test_get_subscription_not_found(self, engine):
        """Test getting non-existent subscription."""
        from iap_emulator.repositories.subscription_store import SubscriptionNotFoundError

        with pytest.raises(SubscriptionNotFoundError):
            engine.get_subscription("invalid_token")

    def test_get_user_subscriptions(self, engine):
        """Test getting all subscriptions for a user."""
        # Create multiple subscriptions for same user
        sub1 = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-multi",
        )
        sub2 = engine.create_subscription(
            subscription_id="premium.yearly",
            user_id="user-multi",
            package_name="com.different.app",
        )

        # Get all subscriptions for user
        user_subs = engine.get_user_subscriptions("user-multi")

        assert len(user_subs) == 2
        tokens = [s.token for s in user_subs]
        assert sub1.token in tokens
        assert sub2.token in tokens

    def test_get_user_subscriptions_filtered_by_package(self, engine):
        """Test getting user subscriptions filtered by package."""
        # Create subscriptions for different packages
        sub1 = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-filter",
            package_name="com.app1",
        )
        sub2 = engine.create_subscription(
            subscription_id="premium.yearly",
            user_id="user-filter",
            package_name="com.app2",
        )

        # Get subscriptions for specific package
        app1_subs = engine.get_user_subscriptions("user-filter", package_name="com.app1")

        assert len(app1_subs) == 1
        assert app1_subs[0].token == sub1.token

    def test_has_active_subscription(self, engine):
        """Test checking if user has active subscription."""
        # Initially no subscription
        assert not engine.has_active_subscription(
            user_id="user-check",
            subscription_id="premium.monthly",
        )

        # Create subscription
        engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-check",
        )

        # Now has active subscription
        assert engine.has_active_subscription(
            user_id="user-check",
            subscription_id="premium.monthly",
        )

    def test_has_active_subscription_after_cancel(self, engine):
        """Test that canceled subscription is not considered active."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-check-cancel",
        )

        # Cancel subscription
        engine.cancel_subscription(subscription.token)

        # Should not be active
        assert not engine.has_active_subscription(
            user_id="user-check-cancel",
            subscription_id="premium.monthly",
        )

    def test_has_active_subscription_in_grace_period(self, engine):
        """Test that subscription in grace period is considered active."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-grace",
        )

        # Set to grace period
        subscription.state = SubscriptionState.IN_GRACE_PERIOD
        engine.store.update(subscription)

        # Should still be active
        assert engine.has_active_subscription(
            user_id="user-grace",
            subscription_id="premium.monthly",
        )

    def test_has_active_subscription_paused(self, engine):
        """Test that paused subscription is considered active."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-pause-active",
        )

        # Pause subscription
        engine.pause_subscription(subscription.token, 7 * 86400000)

        # Should still be active
        assert engine.has_active_subscription(
            user_id="user-pause-active",
            subscription_id="premium.monthly",
        )


class TestSubscriptionEngineIntegration:
    """Integration tests for subscription engine."""

    def test_complete_subscription_lifecycle(self, engine):
        """Test complete subscription lifecycle: create -> pause -> resume -> cancel."""
        # Create subscription
        subscription = engine.create_subscription(
            subscription_id="premium.yearly",
            user_id="user-lifecycle",
        )
        assert subscription.state == SubscriptionState.ACTIVE

        # Pause subscription
        paused = engine.pause_subscription(subscription.token, 14 * 86400000)
        assert paused.state == SubscriptionState.PAUSED

        # Resume subscription
        resumed = engine.resume_subscription(subscription.token)
        assert resumed.state == SubscriptionState.ACTIVE

        # Cancel subscription
        canceled = engine.cancel_subscription(subscription.token)
        assert canceled.state == SubscriptionState.CANCELED
        assert not canceled.auto_renewing

    def test_token_uniqueness(self, engine):
        """Test that each subscription gets a unique token."""
        tokens = set()

        for i in range(10):
            sub = engine.create_subscription(
                subscription_id="premium.monthly",
                user_id=f"user-{i}",
            )
            assert sub.token not in tokens
            tokens.add(sub.token)

        assert len(tokens) == 10

    def test_multiple_users_same_product(self, engine):
        """Test multiple users can have same subscription product."""
        sub1 = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-a",
        )
        sub2 = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-b",
        )

        assert sub1.token != sub2.token
        assert sub1.subscription_id == sub2.subscription_id
        assert sub1.user_id != sub2.user_id


class TestSubscriptionRenewal:
    """Tests for subscription renewal functionality."""

    def test_renew_active_subscription(self, engine):
        """Test renewing an active subscription."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-renew",
        )
        original_expiry = subscription.expiry_time_millis
        assert subscription.renewal_count == 0

        # Renew subscription
        renewed = engine.renew_subscription(subscription.token)

        assert renewed.renewal_count == 1
        assert renewed.state == SubscriptionState.ACTIVE
        assert renewed.payment_state == PaymentState.PAYMENT_RECEIVED

        # Expiry should be extended by one billing period
        expected_duration = parse_billing_period("P1M")
        actual_extension = renewed.expiry_time_millis - original_expiry
        assert abs(actual_extension - expected_duration) < 1000

    def test_renew_with_custom_renewal_time(self, engine):
        """Test renewing subscription with custom renewal time."""
        subscription = engine.create_subscription(
            subscription_id="premium.yearly",
            user_id="user-renew-custom",
        )

        # Set custom renewal time (e.g., early renewal)
        custom_renewal_time = subscription.expiry_time_millis - (7 * 86400000)  # 7 days before expiry

        renewed = engine.renew_subscription(
            subscription.token,
            renewal_time_millis=custom_renewal_time,
        )

        # New expiry should be custom_renewal_time + billing_period
        expected_duration = parse_billing_period("P1Y")
        expected_expiry = custom_renewal_time + expected_duration
        assert abs(renewed.expiry_time_millis - expected_expiry) < 1000

    def test_renew_trial_to_paid(self, engine):
        """Test renewing subscription from trial to paid."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-trial-renew",
            with_trial=True,
        )

        assert subscription.in_trial is True
        assert subscription.payment_state == PaymentState.FREE_TRIAL
        trial_expiry = subscription.expiry_time_millis

        # Renew (trial to paid transition)
        renewed = engine.renew_subscription(subscription.token)

        assert renewed.in_trial is False
        assert renewed.payment_state == PaymentState.PAYMENT_RECEIVED
        assert renewed.renewal_count == 1

        # Expiry should be trial_expiry + billing_period
        expected_duration = parse_billing_period("P1M")
        expected_expiry = trial_expiry + expected_duration
        assert abs(renewed.expiry_time_millis - expected_expiry) < 1000

    def test_renew_canceled_subscription_reactivates(self, engine):
        """Test renewing a canceled subscription reactivates it."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-renew-canceled",
        )

        # Cancel subscription
        canceled = engine.cancel_subscription(subscription.token)
        assert canceled.state == SubscriptionState.CANCELED
        assert canceled.auto_renewing is False

        # Renew should reactivate
        renewed = engine.renew_subscription(subscription.token)

        assert renewed.state == SubscriptionState.ACTIVE
        assert renewed.auto_renewing is True
        assert renewed.cancel_reason is None
        assert renewed.canceled_time_millis is None
        assert renewed.renewal_count == 1

    def test_renew_without_auto_renewing_fails(self, engine):
        """Test that renewing without auto_renewing enabled fails."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-no-auto-renew",
        )

        # Disable auto-renewing
        subscription.set_auto_renewing(False, reason="User disabled")
        engine.store.update(subscription)

        # Renewal should fail
        with pytest.raises(SubscriptionError, match="auto_renewing=False"):
            engine.renew_subscription(subscription.token)

    def test_renew_paused_subscription_fails(self, engine):
        """Test that renewing a paused subscription fails."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-renew-paused",
        )

        # Pause subscription
        engine.pause_subscription(subscription.token, 7 * 86400000)

        # Renewal should fail
        with pytest.raises(InvalidSubscriptionStateError):
            engine.renew_subscription(subscription.token)

    def test_renew_expired_subscription_fails(self, engine):
        """Test that renewing an expired subscription fails."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-renew-expired",
        )

        # Mark as expired
        subscription.state = SubscriptionState.EXPIRED
        engine.store.update(subscription)

        # Renewal should fail
        with pytest.raises(InvalidSubscriptionStateError):
            engine.renew_subscription(subscription.token)

    def test_multiple_renewals(self, engine):
        """Test multiple successive renewals."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-multi-renew",
        )
        original_expiry = subscription.expiry_time_millis

        # Renew 3 times
        for i in range(1, 4):
            renewed = engine.renew_subscription(subscription.token)
            assert renewed.renewal_count == i

        # Total extension should be 3 billing periods
        expected_duration = parse_billing_period("P1M") * 3
        total_extension = renewed.expiry_time_millis - original_expiry
        assert abs(total_extension - expected_duration) < 1000


class TestPaymentFailure:
    """Tests for payment failure handling."""

    def test_simulate_payment_failure(self, engine):
        """Test simulating a payment failure."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-payment-fail",
        )

        assert subscription.state == SubscriptionState.ACTIVE
        assert subscription.payment_state == PaymentState.PAYMENT_RECEIVED

        # Simulate payment failure
        failed = engine.simulate_payment_failure(subscription.token)

        assert failed.state == SubscriptionState.IN_GRACE_PERIOD
        assert failed.payment_state == PaymentState.PAYMENT_FAILED
        assert failed.grace_period_end_millis is not None

        # Grace period should be 3 days (from product definition)
        grace_period_duration = parse_billing_period("P3D")
        actual_grace_duration = failed.grace_period_end_millis - int(time.time() * 1000)
        assert abs(actual_grace_duration - grace_period_duration) < 2000  # Within 2 seconds

    def test_payment_failure_with_custom_time(self, engine):
        """Test payment failure with custom failure time."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-payment-fail-custom",
        )

        custom_failure_time = int(time.time() * 1000) + (86400000)  # Tomorrow

        failed = engine.simulate_payment_failure(
            subscription.token,
            failure_time_millis=custom_failure_time,
        )

        grace_period_duration = parse_billing_period("P3D")
        expected_grace_end = custom_failure_time + grace_period_duration
        assert abs(failed.grace_period_end_millis - expected_grace_end) < 1000

    def test_payment_failure_on_non_active_fails(self, engine):
        """Test that payment failure on non-active subscription fails."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-fail-canceled",
        )

        # Cancel subscription
        engine.cancel_subscription(subscription.token)

        # Payment failure should fail
        with pytest.raises(InvalidSubscriptionStateError, match="Only ACTIVE"):
            engine.simulate_payment_failure(subscription.token)

    def test_payment_failure_without_grace_period_configured(self, engine):
        """Test payment failure on product without grace period."""
        # Create product without grace period
        subscription = engine.create_subscription(
            subscription_id="premium.yearly",  # This has no grace_period in fixture
            user_id="user-no-grace",
        )

        # Should fail because product has no grace_period
        with pytest.raises(SubscriptionError, match="no grace_period configured"):
            engine.simulate_payment_failure(subscription.token)


class TestGracePeriodToAccountHold:
    """Tests for grace period to account hold transition."""

    def test_transition_to_account_hold(self, engine):
        """Test transitioning from grace period to account hold."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-hold",
        )

        # Enter grace period
        failed = engine.simulate_payment_failure(subscription.token)
        assert failed.state == SubscriptionState.IN_GRACE_PERIOD
        grace_end = failed.grace_period_end_millis

        # Transition to hold
        on_hold = engine.transition_to_account_hold(subscription.token)

        assert on_hold.state == SubscriptionState.ON_HOLD
        assert on_hold.account_hold_start_millis is not None
        assert on_hold.grace_period_end_millis is None  # Cleared

    def test_transition_to_hold_with_custom_time(self, engine):
        """Test transitioning to hold with custom time."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-hold-custom",
        )

        engine.simulate_payment_failure(subscription.token)

        custom_hold_time = int(time.time() * 1000) + (86400000)  # Tomorrow
        on_hold = engine.transition_to_account_hold(
            subscription.token,
            hold_time_millis=custom_hold_time,
        )

        assert abs(on_hold.account_hold_start_millis - custom_hold_time) < 1000

    def test_transition_to_hold_from_non_grace_fails(self, engine):
        """Test that transitioning to hold from non-grace state fails."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-hold-active",
        )

        # Try to transition active subscription to hold
        with pytest.raises(InvalidSubscriptionStateError, match="Must be IN_GRACE_PERIOD"):
            engine.transition_to_account_hold(subscription.token)

    def test_process_grace_period_expirations(self, engine):
        """Test processing multiple grace period expirations."""
        # Clear any existing subscriptions
        engine.store.clear()

        # Create multiple subscriptions in grace period
        tokens = []
        for i in range(3):
            sub = engine.create_subscription(
                subscription_id="premium.monthly",
                user_id=f"user-grace-expire-{i}",
            )
            failed = engine.simulate_payment_failure(sub.token)
            tokens.append(failed.token)

        # Fast forward past grace period
        future_time = int(time.time() * 1000) + (4 * 86400000)  # 4 days later

        # Process expirations
        transitioned = engine.process_grace_period_expirations(future_time)

        # All 3 should have transitioned to hold
        assert len(transitioned) == 3
        for sub in transitioned:
            assert sub.state == SubscriptionState.ON_HOLD

    def test_process_grace_period_expirations_partial(self, engine):
        """Test processing grace periods where only some have expired."""
        # Create subscription with grace period that has expired
        sub1 = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-grace-old",
        )
        old_failure_time = int(time.time() * 1000) - (5 * 86400000)  # 5 days ago
        engine.simulate_payment_failure(sub1.token, failure_time_millis=old_failure_time)

        # Create subscription with grace period that hasn't expired
        sub2 = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-grace-new",
        )
        engine.simulate_payment_failure(sub2.token)  # Just now

        # Process at current time
        current_time = int(time.time() * 1000)
        transitioned = engine.process_grace_period_expirations(current_time)

        # Only sub1 should have transitioned
        assert len(transitioned) == 1
        assert transitioned[0].token == sub1.token
        assert transitioned[0].state == SubscriptionState.ON_HOLD

        # sub2 should still be in grace period
        sub2_updated = engine.get_subscription(sub2.token)
        assert sub2_updated.state == SubscriptionState.IN_GRACE_PERIOD


class TestPaymentRecovery:
    """Tests for payment recovery from grace period and account hold."""

    def test_recover_from_grace_period(self, engine):
        """Test recovering from grace period."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-recover-grace",
        )

        # Enter grace period
        failed = engine.simulate_payment_failure(subscription.token)
        assert failed.state == SubscriptionState.IN_GRACE_PERIOD
        assert failed.payment_state == PaymentState.PAYMENT_FAILED

        # Recover
        recovered = engine.recover_from_payment_failure(subscription.token)

        assert recovered.state == SubscriptionState.ACTIVE
        assert recovered.payment_state == PaymentState.PAYMENT_RECEIVED
        assert recovered.grace_period_end_millis is None
        assert recovered.account_hold_start_millis is None

    def test_recover_from_account_hold(self, engine):
        """Test recovering from account hold."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-recover-hold",
        )

        # Enter grace period then account hold
        engine.simulate_payment_failure(subscription.token)
        on_hold = engine.transition_to_account_hold(subscription.token)
        assert on_hold.state == SubscriptionState.ON_HOLD

        # Recover
        recovered = engine.recover_from_payment_failure(subscription.token)

        assert recovered.state == SubscriptionState.ACTIVE
        assert recovered.payment_state == PaymentState.PAYMENT_RECEIVED
        assert recovered.grace_period_end_millis is None
        assert recovered.account_hold_start_millis is None

    def test_recover_with_custom_time(self, engine):
        """Test recovery with custom recovery time."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-recover-custom",
        )

        engine.simulate_payment_failure(subscription.token)

        custom_recovery_time = int(time.time() * 1000) + (86400000)
        recovered = engine.recover_from_payment_failure(
            subscription.token,
            recovery_time_millis=custom_recovery_time,
        )

        assert recovered.state == SubscriptionState.ACTIVE

    def test_recover_from_active_fails(self, engine):
        """Test that recovering from active state fails."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-recover-active",
        )

        # Try to recover from active state
        with pytest.raises(InvalidSubscriptionStateError, match="Must be IN_GRACE_PERIOD or ON_HOLD"):
            engine.recover_from_payment_failure(subscription.token)

    def test_recover_from_canceled_fails(self, engine):
        """Test that recovering from canceled state fails."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-recover-canceled",
        )

        engine.cancel_subscription(subscription.token)

        # Try to recover from canceled state
        with pytest.raises(InvalidSubscriptionStateError):
            engine.recover_from_payment_failure(subscription.token)


class TestPaymentFailureLifecycle:
    """Integration tests for complete payment failure lifecycle."""

    def test_payment_failure_to_recovery_flow(self, engine):
        """Test complete flow: active -> payment fail -> grace -> recovery -> active."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-flow-recovery",
        )

        # 1. Start: ACTIVE
        assert subscription.state == SubscriptionState.ACTIVE

        # 2. Payment fails: ACTIVE -> IN_GRACE_PERIOD
        failed = engine.simulate_payment_failure(subscription.token)
        assert failed.state == SubscriptionState.IN_GRACE_PERIOD
        assert failed.payment_state == PaymentState.PAYMENT_FAILED

        # 3. Payment recovered: IN_GRACE_PERIOD -> ACTIVE
        recovered = engine.recover_from_payment_failure(subscription.token)
        assert recovered.state == SubscriptionState.ACTIVE
        assert recovered.payment_state == PaymentState.PAYMENT_RECEIVED

    def test_payment_failure_to_hold_to_recovery_flow(self, engine):
        """Test flow: active -> payment fail -> grace -> hold -> recovery -> active."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-flow-hold-recovery",
        )

        # 1. Start: ACTIVE
        assert subscription.state == SubscriptionState.ACTIVE

        # 2. Payment fails: ACTIVE -> IN_GRACE_PERIOD
        failed = engine.simulate_payment_failure(subscription.token)
        assert failed.state == SubscriptionState.IN_GRACE_PERIOD

        # 3. Grace expires: IN_GRACE_PERIOD -> ON_HOLD
        on_hold = engine.transition_to_account_hold(subscription.token)
        assert on_hold.state == SubscriptionState.ON_HOLD

        # 4. Payment recovered: ON_HOLD -> ACTIVE
        recovered = engine.recover_from_payment_failure(subscription.token)
        assert recovered.state == SubscriptionState.ACTIVE
        assert recovered.payment_state == PaymentState.PAYMENT_RECEIVED

    def test_payment_failure_multiple_times(self, engine):
        """Test subscription can fail payment multiple times."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-multi-fail",
        )

        # First failure and recovery
        engine.simulate_payment_failure(subscription.token)
        engine.recover_from_payment_failure(subscription.token)

        sub = engine.get_subscription(subscription.token)
        assert sub.state == SubscriptionState.ACTIVE

        # Second failure and recovery
        engine.simulate_payment_failure(subscription.token)
        engine.recover_from_payment_failure(subscription.token)

        sub = engine.get_subscription(subscription.token)
        assert sub.state == SubscriptionState.ACTIVE

    def test_renewal_after_payment_recovery(self, engine):
        """Test that subscription can be renewed after payment recovery."""
        subscription = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-renew-after-recovery",
        )

        # Payment failure and recovery
        engine.simulate_payment_failure(subscription.token)
        recovered = engine.recover_from_payment_failure(subscription.token)

        # Should be able to renew
        renewed = engine.renew_subscription(subscription.token)
        assert renewed.state == SubscriptionState.ACTIVE
        assert renewed.renewal_count == 1
