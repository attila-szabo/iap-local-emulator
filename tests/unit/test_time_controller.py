"""Unit tests for TimeController service."""
import time
from unittest.mock import MagicMock, patch

import pytest

from iap_emulator.models.product import ProductDefinition
from iap_emulator.repositories.product_repository import ProductRepository
from iap_emulator.repositories.subscription_store import SubscriptionStore
from iap_emulator.services.subscription_engine import SubscriptionEngine
from iap_emulator.services.time_controller import TimeController
from iap_emulator.utils.billing_period import parse_billing_period


@pytest.fixture
def mock_config():
    """Mock configuration for tests."""
    config = MagicMock()
    config.default_package_name = "com.example.test"
    config.emulator_settings.token_prefix = "test"
    return config

@pytest.fixture
def product_repo():
    """create a product repository with test products"""
    mock_config= MagicMock()
    mock_config.products.subscriptions = [
        ProductDefinition(
            id="premium.monthly",
            type="subs",
            title="Premium Monthly",
            description="Monthly Subscription",
            price_micros=99990000,
            currency="USD",
            billing_period="P1M",
            trial_period="P7D",
            grace_period="P3D"
        ),
        ProductDefinition(
            id="premium.yearly",
            type="subs",
            title="Premium Yearly",
            description="Yearly Subscription",
            price_micros=99990000,
            currency="USD",
            billing_period="P1Y",
            trial_period="P30D",
            grace_period="P7D"
        )
    ]
    return ProductRepository(config=mock_config)

@pytest.fixture
def subscription_store():
    """create a subscription store for each test"""
    store = SubscriptionStore()
    yield store
    store.clear()

@pytest.fixture
def subscription_engine(subscription_store, product_repo, mock_config):
    with patch("iap_emulator.services.subscription_engine.get_config", return_value=mock_config):
        engine = SubscriptionEngine(
            subscription_store=subscription_store,
            product_repository=product_repo
        )
        yield engine

@pytest.fixture
def time_controller(subscription_engine):
  """Create a time controller with test subscription engine."""
  controller = TimeController(subscription_engine=subscription_engine)
  return controller


class TestTimeControllerBasics:
    """Tests for basic time controller functionality"""

    def test_init_with_current_time(self, time_controller):
        """test that time controller starts with current real time"""
        # act: get the virtual time
        virtual_time = time_controller.get_current_time_millis()
        real_time = int(time.time() * 1000)

        # assert should be close to real time
        time_diff = abs(virtual_time - real_time)
        assert time_diff < 1000, f'virtual time should start near real time, diff: {time_diff}'

    def test_get_current_time_is_consistent(self, time_controller):
      """Test that getting time multiple times returns same value. We're using a virtual clock, not real time!"""
      # Act - get time twice
      time1 = time_controller.get_current_time_millis()
      time2 = time_controller.get_current_time_millis()

      # Assert - should be the same (no auto-advancement)
      assert time1 == time2, "Time should not change unless explicitly advanced"

    def test_advance_time_by_days(self, time_controller):
        """test time movement"""

        # arrange
        old_time = time_controller.get_current_time_millis()

        # act
        result = time_controller.advance_time(days=30)
        new_time = time_controller.get_current_time_millis()

        # assert
        expected_advance = 30 * 24 * 60 * 60 * 1000  # 30 days in ms
        actual_advance = new_time - old_time

        assert actual_advance == expected_advance
        assert result["time_advanced_millis"] == expected_advance
        assert result["old_time_millis"] == old_time
        assert result["new_time_millis"] == new_time

class TestTimeControllerWithSubscriptions:
    """Integration tests for TC with subscription"""

    def test_advance_time_renews_subscription(
            self,
            time_controller,
            subscription_engine
    ):
        """test that advancing time automatically renews subs"""
        # arrange, create a monthly sub
        subscription = subscription_engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-time-test"
        )

        original_expiry = subscription.expiry_time_millis
        assert subscription.renewal_count == 0

        # act
        result = time_controller.advance_time(days=31)

        # assert

        renewed_sub = subscription_engine.get_subscription(subscription.token)

        assert renewed_sub.renewal_count == 1, "should have renewed once"
        assert len(result["renewals_processed"]) == 1
        assert subscription.token in result["renewals_processed"]

        # new expiry check
        billing_period = parse_billing_period("P1M")
        expected_new_expiry = original_expiry + billing_period
        assert abs(renewed_sub.expiry_time_millis - expected_new_expiry) < 1000

    def test_advance_time_multiple_renewals(
            self,
            time_controller,
            subscription_engine
    ):
        """test advancing time by a long period renews the subscriptions multiple times"""
        subscription = subscription_engine.create_subscription(
            subscription_id="premium.monthly",
            user_id="user-multi-renew"
        )

        time_controller.advance_time(days=35) # 1st renewal
        time_controller.advance_time(days=35) # 2nd renewal
        time_controller.advance_time(days=35) # 3rd renewal

        renewed_sub = subscription_engine.get_subscription(subscription.token)

        assert renewed_sub.renewal_count == 3, "should renew 3x by incremental renewal"
