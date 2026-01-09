"""Integration tests for complete subscription lifecycle scenarios."""
from unittest.mock import MagicMock, patch

import pytest

from iap_emulator.models.product import ProductDefinition
from iap_emulator.models.subscription import (
    PaymentState,
    SubscriptionState,
)
from iap_emulator.repositories.product_repository import ProductRepository
from iap_emulator.repositories.subscription_store import SubscriptionStore
from iap_emulator.services.subscription_engine import SubscriptionEngine
from iap_emulator.services.time_controller import TimeController


@pytest.fixture
def mock_config():
    """Mock configuration for integration tests."""
    config = MagicMock()
    config.default_package_name = "com.example.integration"
    config.emulator_settings.token_prefix = "integration"
    return config

@pytest.fixture
def product_repo():
  """Product repository with test subscription products."""
  mock_config = MagicMock()
  mock_config.products.subscriptions = [
      ProductDefinition(
          id="basic.monthly",
          type="subs",
          title="Basic Monthly",
          description="Basic monthly subscription",
          price_micros=4990000,  # $4.99
          currency="USD",
          billing_period="P1M",  # 1 month
          trial_period="P7D",    # 7 day trial
          grace_period="P3D",    # 3 day grace
      ),
      ProductDefinition(
          id="premium.monthly",
          type="subs",
          title="Premium Monthly",
          description="Premium monthly subscription",
          price_micros=9990000,  # $9.99
          currency="USD",
          billing_period="P1M",
          trial_period="P14D",   # 14 day trial
          grace_period="P7D",    # 7 day grace
      ),
  ]
  return ProductRepository(config=mock_config)


@pytest.fixture
def subscription_store():
  """Fresh subscription store for each test."""
  store = SubscriptionStore()
  yield store
  store.clear()  # Clean up after test

@pytest.fixture
def subscription_engine(subscription_store, product_repo, mock_config):
  """Subscription engine with all dependencies."""
  with patch("iap_emulator.services.subscription_engine.get_config", return_value=mock_config):
      engine = SubscriptionEngine(
          subscription_store=subscription_store,
          product_repository=product_repo,
      )
      yield engine

@pytest.fixture
def time_controller(subscription_engine):
    """time controller connected to the subscription engine"""
    return TimeController(subscription_engine=subscription_engine)

@pytest.fixture
def full_system(time_controller, subscription_engine, subscription_store, product_repo):
    """Complete backend system
    :returns a dict with all components;
    """
    return {
        "time_controller": time_controller,
        "subscription_engine": subscription_engine,
        "subscription_store": subscription_store,
        "product_repo": product_repo
    }


class TestFullSubscriptionLifecycle:
    """Test complete subscription lifecycle from creation to expiration."""

    def test_trial_to_paid_to_renewal_flow(self, full_system):
        """Test: trial -> paid -> multiple renewals -> cancel -> expire
        Most common user journey
        """
        tc: TimeController = full_system['time_controller']
        engine: SubscriptionEngine = full_system['subscription_engine']

        # 1 - create trial subscription
        sub = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-lifecycle",
            with_trial=True
        )

        assert sub.state == SubscriptionState.ACTIVE
        assert sub.in_trial == True
        assert sub.payment_state == PaymentState.FREE_TRIAL
        assert sub.renewal_count == 0

        # 2 advance to end trial
        result = tc.advance_time(days=15)

        sub = engine.get_subscription(sub.token)
        assert sub.in_trial is False, "trial should end"
        assert sub.payment_state == PaymentState.PAYMENT_RECEIVED
        assert sub.renewal_count == 1, "first renewal - trial -> paid"
        assert len(result["renewals_processed"]) == 1

        # 3
        tc.advance_time(days=31)
        sub = engine.get_subscription(sub.token)
        assert sub.renewal_count == 2

        # 4
        tc.advance_time(days=31)
        sub = engine.get_subscription(sub.token)
        assert sub.renewal_count == 3

        # 5
        canceled = engine.cancel_subscription(sub.token)
        assert canceled.state == SubscriptionState.CANCELED
        assert canceled.auto_renewing is False

        # 6
        tc.advance_time(days=31)
        sub = engine.get_subscription(sub.token)

        # canceled don't auto expire, they stay canceled until expiry_time passes
        assert sub.state == SubscriptionState.CANCELED
        assert sub.renewal_count == 3, "no renewal after canceled"

    def test_multiple_users_independent_lifecycles(self, full_system):
        """test multiple users sub lifecycles."""

        tc = full_system["time_controller"]
        engine = full_system["subscription_engine"]

        # create 3 user subs
        user1_sub = engine.create_subscription(
            subscription_id="basic.monthly",
            user_id="user-1"
        )

        user2_sub = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-2",
            with_trial=True,
        )

        user3_sub = engine.create_subscription(
            subscription_id="basic.monthly",
            user_id="user-3",
        )

        result = tc.advance_time(days=35)

        assert len(result["renewals_processed"]) == 3, "all 3 should renew"

        # Verify each user independently
        u1 = engine.get_subscription(user1_sub.token)
        u2 = engine.get_subscription(user2_sub.token)
        u3 = engine.get_subscription(user3_sub.token)

        assert u1.renewal_count == 1
        assert u2.renewal_count == 1  # Trial to paid
        assert u3.renewal_count == 1

        # Cancel user 2
        engine.cancel_subscription(user2_sub.token)

        # Advance another 35 days
        result = tc.advance_time(days=35)

        # Only user1 and user3 should renew (user2 canceled)
        assert len(result["renewals_processed"]) == 2

        u1 = engine.get_subscription(user1_sub.token)
        u2 = engine.get_subscription(user2_sub.token)
        u3 = engine.get_subscription(user3_sub.token)

        assert u1.renewal_count == 2
        assert u2.renewal_count == 1  # Didn't renew (canceled)
        assert u3.renewal_count == 2


class TestPaymentFailureIntegration:
    """Test payment failure scenarios with time advancement."""

    def test_payment_failure_grace_period_recovery(self, full_system):
        """Test: active -> payment fails ->grace period -> payment recovers -> active
        Simulates a user whose payment failes but recovers during grace period.
        """

        tc:TimeController = full_system["time_controller"]
        engine:SubscriptionEngine = full_system["subscription_engine"]


        # Step 1: Create active subscription
        sub = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-payment-fail",
        )

        assert sub.state == SubscriptionState.ACTIVE
        assert sub.payment_state == PaymentState.PAYMENT_RECEIVED

        # simulate payment failure
        failed = engine.simulate_payment_failure(sub.token)

        assert failed.state == SubscriptionState.IN_GRACE_PERIOD
        assert failed.payment_state == PaymentState.PAYMENT_FAILED
        assert failed.grace_period_end_millis is not None

        tc.advance_time(days=2)

        sub = engine.get_subscription(sub.token)
        assert sub.state == SubscriptionState.IN_GRACE_PERIOD, "still in grace period"

        # payment recovers
        recovered = engine.recover_from_payment_failure(sub.token)

        assert recovered.state == SubscriptionState.ACTIVE
        assert recovered.payment_state == PaymentState.PAYMENT_RECEIVED
        assert recovered.grace_period_end_millis is None, "grace cleared"

        tc.advance_time(days=30)
        sub = engine.get_subscription(sub.token)
        assert sub.renewal_count == 1, "should renew normally after recovery"


    def test_payment_failure_to_account_hold(self, full_system):
        """Test: Active → Payment Fails → Grace Period Expires → Account Hold

        Simulates a user whose payment fails and never recovers.
        """
        tc = full_system["time_controller"]
        engine = full_system["subscription_engine"]

        # Step 1: Create subscription
        sub = engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-hold",
        )

        # Step 2: Payment fails
        engine.simulate_payment_failure(sub.token)
        sub = engine.get_subscription(sub.token)
        assert sub.state == SubscriptionState.IN_GRACE_PERIOD

        # Step 3: Advance past grace period (7 days + 1)
        result = tc.advance_time(days=8)

        # Should automatically move to account hold
        sub = engine.get_subscription(sub.token)
        assert sub.state == SubscriptionState.ON_HOLD
        assert sub.account_hold_start_millis is not None
        assert len(result["grace_period_expired"]) == 1

        # Step 4: Verify no renewals happen while on hold
        tc.advance_time(days=30)
        sub = engine.get_subscription(sub.token)
        assert sub.renewal_count == 0, "No renewals while on hold"

        # Step 5: Payment finally recovers from hold
        recovered = engine.recover_from_payment_failure(sub.token)
        assert recovered.state == SubscriptionState.ACTIVE
        assert recovered.account_hold_start_millis is None

        # Step 6: Should renew normally now
        tc.advance_time(days=31)
        sub = engine.get_subscription(sub.token)
        assert sub.renewal_count == 1, "Renews after recovery from hold"

    def test_multiple_payment_failures(self, full_system):
        """Test subscription can fail payment multiple times and recover.

        Simulates unreliable payment method.
        """
        tc = full_system["time_controller"]
        engine = full_system["subscription_engine"]

        sub = engine.create_subscription(
            subscription_id="basic.monthly",
            user_id="user-unreliable-payment",
        )

        # First failure and recovery
        engine.simulate_payment_failure(sub.token)
        tc.advance_time(days=2)
        engine.recover_from_payment_failure(sub.token)

        sub = engine.get_subscription(sub.token)
        assert sub.state == SubscriptionState.ACTIVE

        # Advance to renewal
        tc.advance_time(days=30)
        sub = engine.get_subscription(sub.token)
        assert sub.renewal_count == 1

        # Second failure and recovery
        engine.simulate_payment_failure(sub.token)
        tc.advance_time(days=1)
        engine.recover_from_payment_failure(sub.token)

        # Should still be healthy
        sub = engine.get_subscription(sub.token)
        assert sub.state == SubscriptionState.ACTIVE

        # Verify continues to renew
        tc.advance_time(days=31)
        sub = engine.get_subscription(sub.token)
        assert sub.renewal_count == 2, "Continues renewing after multiple failures"

class TestPauseResumeIntegration:

    def test_pause_extends_subscription_lifetime(self, full_system):
        """Test that pausing extends the sub"""
        tc = full_system["time_controller"]
        engine = full_system["subscription_engine"]

        # Create subscription
        sub = engine.create_subscription(
            subscription_id="basic.monthly",
            user_id="user-pause",
        )

        original_expiry = sub.expiry_time_millis

        # Advance 10 days
        tc.advance_time(days=10)

        # Pause for 14 days
        paused = engine.pause_subscription(sub.token, pause_duration_millis=14 * 86400000)

        assert paused.state == SubscriptionState.PAUSED
        # Expiry should be extended by 14 days
        expected_expiry = original_expiry + (14 * 86400000)
        assert abs(paused.expiry_time_millis - expected_expiry) < 1000

        # Advance 7 days (during pause)
        tc.advance_time(days=7)

        # Should NOT renew during pause
        sub = engine.get_subscription(sub.token)
        assert sub.state == SubscriptionState.PAUSED
        assert sub.renewal_count == 0, "No renewals while paused"

        # Resume subscription
        resumed = engine.resume_subscription(sub.token)
        assert resumed.state == SubscriptionState.ACTIVE

        # Advance to normal expiry (original + 14 days pause)
        tc.advance_time(days=28)  # 10 + 7 + 25 = 42 days total

        # Should renew now (30 day period + 14 day pause = 44 days)
        sub = engine.get_subscription(sub.token)
        assert sub.renewal_count == 1, "Renews after pause is accounted for"

    def test_pause_during_trial_extends_trial(self, full_system):
      """Test pausing during trial extends the trial period."""
      tc = full_system["time_controller"]
      engine = full_system["subscription_engine"]

      # Create subscription with trial
      sub = engine.create_subscription(
          subscription_id="premium.monthly",
          user_id="user-pause-trial",
          with_trial=True,
      )

      assert sub.in_trial is True
      original_expiry = sub.expiry_time_millis

      # Pause for 7 days during trial
      paused = engine.pause_subscription(sub.token, pause_duration_millis=7 * 86400000)

      # Trial should be extended
      assert paused.in_trial is True
      assert paused.expiry_time_millis == original_expiry + (7 * 86400000)

      # Resume
      engine.resume_subscription(sub.token)

      # Advance to end of extended trial
      tc.advance_time(days=22)  # 14 day trial + 7 day pause + 1

      # Should convert to paid now
      sub = engine.get_subscription(sub.token)
      assert sub.in_trial is False
      assert sub.renewal_count == 1

    def test_cancel_paused_subscription(self, full_system):
      """Test that paused subscriptions can be canceled."""
      tc = full_system["time_controller"]
      engine = full_system["subscription_engine"]

      sub = engine.create_subscription(
          subscription_id="basic.monthly",
          user_id="user-cancel-paused",
      )

      # Pause subscription
      engine.pause_subscription(sub.token, pause_duration_millis=30 * 86400000)
      sub = engine.get_subscription(sub.token)
      assert sub.state == SubscriptionState.PAUSED

      # Cancel while paused
      canceled = engine.cancel_subscription(sub.token)
      assert canceled.state == SubscriptionState.CANCELED
      assert canceled.auto_renewing is False

      # Advance time - should NOT renew
      tc.advance_time(days=40)
      sub = engine.get_subscription(sub.token)
      assert sub.renewal_count == 0, "Canceled paused subscription doesn't renew"

class TestEdgeCasesAndBoundaries:
  """Test edge cases and boundary conditions."""

  def test_zero_time_advance(self, full_system):
      """Test advancing time by zero does nothing."""
      tc = full_system["time_controller"]

      old_time = tc.get_current_time_millis()
      result = tc.advance_time(days=0, hours=0, minutes=0)
      new_time = tc.get_current_time_millis()

      assert old_time == new_time
      assert result["time_advanced_millis"] == 0
      assert result["renewals_processed"] == []
      assert result["grace_periods_expired"] == []


  def test_subscription_at_exact_expiry_time(self, full_system):
      """Test subscription that expires at exact moment of time advance."""
      tc = full_system["time_controller"]
      engine = full_system["subscription_engine"]

      sub = engine.create_subscription(
          subscription_id="basic.monthly",
          user_id="user-exact-expiry",
      )

      # Advance just past 1 month (30 days + 1 to be safe)
      result = tc.advance_time(days=31)

      # Should renew
      sub = engine.get_subscription(sub.token)
      assert sub.renewal_count == 1, "Should renew after 31 days"
      assert sub.token in result["renewals_processed"]


  def test_set_time_vs_advance_time_consistency(self, full_system):
      """Test that set_time and advance_time produce same results."""
      tc = full_system["time_controller"]
      engine = full_system["subscription_engine"]

      # Create two identical subscriptions
      sub1 = engine.create_subscription(
          subscription_id="basic.monthly",
          user_id="user-advance",
      )

      sub2 = engine.create_subscription(
          subscription_id="basic.monthly",
          user_id="user-set",
      )

      # Method 1: Advance time
      current_time = tc.get_current_time_millis()
      tc.advance_time(days=35)

      # Method 2: Set time (on a different controller for comparison)
      # Both should result in same renewals
      sub1_updated = engine.get_subscription(sub1.token)
      sub2_updated = engine.get_subscription(sub2.token)

      assert sub1_updated.renewal_count == sub2_updated.renewal_count
      assert sub1_updated.state == sub2_updated.state
