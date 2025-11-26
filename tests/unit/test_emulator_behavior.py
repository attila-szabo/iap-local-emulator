"""Tests for emulator behavior settings and subscription configuration.

Tests the loading and access of emulator behavior settings, including
subscription behavior configuration like grace period, account hold, and proration.
"""

import pytest

from iap_emulator.config import Config, get_config


@pytest.fixture
def config():
    """Get config instance for testing."""
    return get_config()


@pytest.fixture
def emulator_settings(config):
    """Get emulator settings for testing."""
    return config.emulator_settings


@pytest.fixture
def subscription_behavior(emulator_settings):
    """Get subscription behavior config for testing."""
    return emulator_settings.subscriptions


class TestEmulatorSettingsLoading:
    """Test basic emulator settings loading."""

    def test_config_loads_successfully(self, config):
        """Test that configuration loads without errors."""
        assert config is not None
        assert config.config_path.exists()

    def test_emulator_settings_accessible(self, config):
        """Test that emulator settings are accessible."""
        emulator = config.emulator_settings
        assert emulator is not None

    def test_emulator_settings_object_type(self, emulator_settings):
        """Test that emulator settings is the correct type."""
        assert emulator_settings is not None
        assert hasattr(emulator_settings, "auto_renew_enabled")
        assert hasattr(emulator_settings, "rtdn_enabled")
        assert hasattr(emulator_settings, "subscriptions")


class TestCoreEmulatorSettings:
    """Test core emulator configuration settings."""

    def test_auto_renew_enabled_is_bool(self, emulator_settings):
        """Test that auto_renew_enabled is a boolean."""
        assert isinstance(emulator_settings.auto_renew_enabled, bool)

    def test_rtdn_enabled_is_bool(self, emulator_settings):
        """Test that rtdn_enabled is a boolean."""
        assert isinstance(emulator_settings.rtdn_enabled, bool)

    def test_simulate_payment_failures_is_bool(self, emulator_settings):
        """Test that simulate_payment_failures is a boolean."""
        assert isinstance(emulator_settings.simulate_payment_failures, bool)

    def test_payment_failure_rate_is_float(self, emulator_settings):
        """Test that payment_failure_rate is a float."""
        assert isinstance(emulator_settings.payment_failure_rate, (int, float))
        assert 0.0 <= emulator_settings.payment_failure_rate <= 1.0

    def test_token_prefix_is_string(self, emulator_settings):
        """Test that token_prefix is a string."""
        assert isinstance(emulator_settings.token_prefix, str)
        assert len(emulator_settings.token_prefix) > 0

    def test_token_length_is_positive(self, emulator_settings):
        """Test that token_length is a positive integer."""
        assert isinstance(emulator_settings.token_length, int)
        assert emulator_settings.token_length > 0


class TestSubscriptionBehaviorConfig:
    """Test subscription behavior configuration."""

    def test_subscription_behavior_accessible(self, subscription_behavior):
        """Test that subscription behavior config is accessible."""
        assert subscription_behavior is not None

    def test_subscription_behavior_has_required_fields(self, subscription_behavior):
        """Test that subscription behavior has all required fields."""
        assert hasattr(subscription_behavior, "grace_period_behavior")
        assert hasattr(subscription_behavior, "account_hold_behavior")
        assert hasattr(subscription_behavior, "allow_changes")
        assert hasattr(subscription_behavior, "proration_mode")

    def test_grace_period_behavior_value(self, subscription_behavior):
        """Test grace_period_behavior has expected value."""
        expected = "retain_access"
        assert subscription_behavior.grace_period_behavior == expected

    def test_account_hold_behavior_value(self, subscription_behavior):
        """Test account_hold_behavior has expected value."""
        expected = "revoke_access"
        assert subscription_behavior.account_hold_behavior == expected

    def test_allow_changes_value(self, subscription_behavior):
        """Test allow_changes has expected value."""
        assert subscription_behavior.allow_changes is True

    def test_proration_mode_value(self, subscription_behavior):
        """Test proration_mode has expected value."""
        expected = "immediate_with_time_proration"
        assert subscription_behavior.proration_mode == expected


class TestSubscriptionBehaviorValidation:
    """Test subscription behavior validation."""

    def test_grace_period_behavior_is_valid(self, subscription_behavior):
        """Test that grace_period_behavior is a valid value."""
        valid_values = ["retain_access", "revoke_access"]
        assert subscription_behavior.grace_period_behavior in valid_values

    def test_account_hold_behavior_is_valid(self, subscription_behavior):
        """Test that account_hold_behavior is a valid value."""
        valid_values = ["retain_access", "revoke_access"]
        assert subscription_behavior.account_hold_behavior in valid_values

    def test_allow_changes_is_bool(self, subscription_behavior):
        """Test that allow_changes is a boolean."""
        assert isinstance(subscription_behavior.allow_changes, bool)

    def test_proration_mode_is_valid(self, subscription_behavior):
        """Test that proration_mode is a valid value."""
        valid_values = [
            "immediate_with_time_proration",
            "immediate_without_proration",
            "deferred",
        ]
        assert subscription_behavior.proration_mode in valid_values


class TestConfigAccessPatterns:
    """Test different ways to access configuration."""

    def test_access_via_emulator_settings(self, config):
        """Test accessing via config.emulator_settings."""
        grace = config.emulator_settings.subscriptions.grace_period_behavior
        assert grace == "retain_access"

    def test_access_via_products_emulator(self, config):
        """Test accessing via config.products.emulator."""
        hold = config.products.emulator.subscriptions.account_hold_behavior
        assert hold == "revoke_access"

    def test_access_via_stored_reference(self, config):
        """Test accessing via stored reference."""
        sub_config = config.emulator_settings.subscriptions
        can_change = sub_config.allow_changes
        assert can_change is True

    def test_all_access_patterns_return_same_values(self, config):
        """Test that all access patterns return the same values."""
        # Via emulator_settings
        grace1 = config.emulator_settings.subscriptions.grace_period_behavior

        # Via products.emulator
        grace2 = config.products.emulator.subscriptions.grace_period_behavior

        # Should be the same
        assert grace1 == grace2


class TestIntegrationScenarios:
    """Test integration scenarios using emulator behavior settings."""

    def test_grace_period_scenario(self, subscription_behavior):
        """Test grace period access behavior."""
        if subscription_behavior.grace_period_behavior == "retain_access":
            # User should retain access during grace period
            assert subscription_behavior.grace_period_behavior == "retain_access"
        else:
            # User should lose access during grace period
            assert subscription_behavior.grace_period_behavior == "revoke_access"

    def test_account_hold_scenario(self, subscription_behavior):
        """Test account hold access behavior."""
        if subscription_behavior.account_hold_behavior == "revoke_access":
            # User should lose access during account hold
            assert subscription_behavior.account_hold_behavior == "revoke_access"
        else:
            # User should retain access during account hold
            assert subscription_behavior.account_hold_behavior == "retain_access"

    def test_subscription_change_scenario(self, subscription_behavior):
        """Test subscription change behavior."""
        if subscription_behavior.allow_changes:
            # Changes are allowed, check proration mode
            assert subscription_behavior.proration_mode is not None
            assert len(subscription_behavior.proration_mode) > 0
        else:
            # Changes not allowed
            assert subscription_behavior.allow_changes is False

    def test_proration_applied_when_changes_allowed(self, subscription_behavior):
        """Test that proration mode is set when changes are allowed."""
        if subscription_behavior.allow_changes:
            assert subscription_behavior.proration_mode in [
                "immediate_with_time_proration",
                "immediate_without_proration",
                "deferred",
            ]


class TestEmulatorConfigStructure:
    """Test complete emulator configuration structure."""

    def test_emulator_has_all_core_fields(self, emulator_settings):
        """Test that emulator config has all core fields."""
        assert hasattr(emulator_settings, "auto_renew_enabled")
        assert hasattr(emulator_settings, "rtdn_enabled")
        assert hasattr(emulator_settings, "simulate_payment_failures")
        assert hasattr(emulator_settings, "payment_failure_rate")
        assert hasattr(emulator_settings, "token_prefix")
        assert hasattr(emulator_settings, "token_length")
        assert hasattr(emulator_settings, "subscriptions")

    def test_subscription_behavior_nested_correctly(self, emulator_settings):
        """Test that subscription behavior is nested under emulator settings."""
        sub_behavior = emulator_settings.subscriptions
        assert sub_behavior is not None
        assert hasattr(sub_behavior, "grace_period_behavior")
        assert hasattr(sub_behavior, "account_hold_behavior")
        assert hasattr(sub_behavior, "allow_changes")
        assert hasattr(sub_behavior, "proration_mode")


class TestBehaviorLogic:
    """Test behavior logic for different scenarios."""

    def test_grace_period_retains_access(self, subscription_behavior):
        """Test that grace period behavior is set to retain access."""
        # Based on products.yaml configuration
        assert subscription_behavior.grace_period_behavior == "retain_access"

    def test_account_hold_revokes_access(self, subscription_behavior):
        """Test that account hold behavior revokes access."""
        # Based on products.yaml configuration
        assert subscription_behavior.account_hold_behavior == "revoke_access"

    def test_changes_allowed_with_proration(self, subscription_behavior):
        """Test that changes are allowed with time proration."""
        assert subscription_behavior.allow_changes is True
        assert subscription_behavior.proration_mode == "immediate_with_time_proration"


# Parametrized tests for behavior scenarios
@pytest.mark.parametrize("behavior_field,expected_value", [
    ("grace_period_behavior", "retain_access"),
    ("account_hold_behavior", "revoke_access"),
    ("allow_changes", True),
    ("proration_mode", "immediate_with_time_proration"),
])
def test_subscription_behavior_values(behavior_field, expected_value):
    """Test individual subscription behavior values."""
    config = get_config()
    sub_behavior = config.emulator_settings.subscriptions
    actual_value = getattr(sub_behavior, behavior_field)
    assert actual_value == expected_value


@pytest.mark.parametrize("core_field", [
    "auto_renew_enabled",
    "rtdn_enabled",
    "simulate_payment_failures",
    "payment_failure_rate",
    "token_prefix",
    "token_length",
])
def test_core_emulator_fields_exist(core_field):
    """Test that core emulator fields exist."""
    config = get_config()
    emulator = config.emulator_settings
    assert hasattr(emulator, core_field)
