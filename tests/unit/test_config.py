"""Tests for configuration loading and management."""

import pytest

from iap_emulator.config import Config, get_config


@pytest.fixture
def config():
    """Create a Config instance for testing."""
    return Config()


class TestConfigurationLoading:
    """Test basic configuration loading."""

    def test_config_loads_successfully(self, config):
        """Test that configuration loads without errors."""
        assert config is not None
        assert config.config_path.exists()

    def test_config_path_is_set(self, config):
        """Test that config path is set correctly."""
        assert config.config_path is not None
        assert str(config.config_path).endswith("products.yaml")

    def test_products_config_is_loaded(self, config):
        """Test that products configuration is loaded."""
        assert config.products is not None

    def test_config_has_subscriptions(self, config):
        """Test that configuration contains subscriptions."""
        assert len(config.products.subscriptions) > 0


class TestPubSubConfiguration:
    """Test Pub/Sub configuration access."""

    def test_pubsub_direct_access(self, config):
        """Test direct access to Pub/Sub config via config.products.pubsub."""
        pubsub = config.products.pubsub
        assert pubsub is not None
        assert pubsub.project_id is not None
        assert pubsub.topic is not None
        assert pubsub.default_subscription is not None

    def test_pubsub_project_id_accessor(self, config):
        """Test convenient accessor for Pub/Sub project ID."""
        project_id = config.pubsub_project_id
        assert project_id is not None
        assert isinstance(project_id, str)
        assert len(project_id) > 0

    def test_pubsub_topic_accessor(self, config):
        """Test convenient accessor for Pub/Sub topic."""
        topic = config.pubsub_topic
        assert topic is not None
        assert isinstance(topic, str)
        assert len(topic) > 0

    def test_pubsub_subscription_accessor(self, config):
        """Test convenient accessor for Pub/Sub subscription."""
        subscription = config.pubsub_subscription
        assert subscription is not None
        assert isinstance(subscription, str)
        assert len(subscription) > 0

    def test_pubsub_accessor_matches_direct_access(self, config):
        """Test that accessors return same values as direct access."""
        pubsub = config.products.pubsub
        assert config.pubsub_project_id == pubsub.project_id
        assert config.pubsub_topic == pubsub.topic
        assert config.pubsub_subscription == pubsub.default_subscription


class TestEmulatorConfiguration:
    """Test emulator configuration access."""

    def test_emulator_direct_access(self, config):
        """Test direct access to emulator config via config.products.emulator."""
        emulator = config.products.emulator
        assert emulator is not None
        assert hasattr(emulator, "auto_renew_enabled")
        assert hasattr(emulator, "rtdn_enabled")
        assert hasattr(emulator, "token_prefix")
        assert hasattr(emulator, "token_length")

    def test_emulator_settings_accessor(self, config):
        """Test convenient accessor for emulator settings."""
        emulator = config.emulator_settings
        assert emulator is not None
        assert hasattr(emulator, "auto_renew_enabled")
        assert hasattr(emulator, "rtdn_enabled")
        assert hasattr(emulator, "simulate_payment_failures")
        assert hasattr(emulator, "payment_failure_rate")

    def test_emulator_accessor_matches_direct_access(self, config):
        """Test that emulator_settings accessor returns same object."""
        direct = config.products.emulator
        accessor = config.emulator_settings
        assert accessor.auto_renew_enabled == direct.auto_renew_enabled
        assert accessor.rtdn_enabled == direct.rtdn_enabled
        assert accessor.token_prefix == direct.token_prefix
        assert accessor.token_length == direct.token_length

    def test_emulator_auto_renew_enabled_is_bool(self, config):
        """Test that auto_renew_enabled is a boolean."""
        assert isinstance(config.emulator_settings.auto_renew_enabled, bool)

    def test_emulator_rtdn_enabled_is_bool(self, config):
        """Test that rtdn_enabled is a boolean."""
        assert isinstance(config.emulator_settings.rtdn_enabled, bool)

    def test_emulator_token_prefix_is_string(self, config):
        """Test that token_prefix is a string."""
        assert isinstance(config.emulator_settings.token_prefix, str)

    def test_emulator_token_length_is_positive(self, config):
        """Test that token_length is a positive integer."""
        assert isinstance(config.emulator_settings.token_length, int)
        assert config.emulator_settings.token_length > 0


class TestPackageConfiguration:
    """Test package configuration access."""

    def test_default_package_name_accessor(self, config):
        """Test convenient accessor for default package name."""
        package_name = config.default_package_name
        assert package_name is not None
        assert isinstance(package_name, str)
        assert len(package_name) > 0


class TestProductDefinitions:
    """Test product definitions."""

    def test_has_product_subscriptions(self, config):
        """Test that configuration has subscription products."""
        subscriptions = config.products.subscriptions
        assert isinstance(subscriptions, list)
        assert len(subscriptions) > 0

    def test_subscriptions_have_required_fields(self, config):
        """Test that all subscriptions have required fields."""
        for product in config.products.subscriptions:
            assert hasattr(product, "id")
            assert hasattr(product, "title")
            assert hasattr(product, "type")
            assert hasattr(product, "price_micros")
            assert hasattr(product, "currency")
            assert hasattr(product, "billing_period")
            assert hasattr(product, "base_plan_id")

    def test_subscription_ids_are_unique(self, config):
        """Test that all subscription IDs are unique."""
        ids = [sub.id for sub in config.products.subscriptions]
        assert len(ids) == len(set(ids))

    def test_subscription_prices_are_positive(self, config):
        """Test that all subscription prices are positive."""
        for product in config.products.subscriptions:
            assert product.price_micros > 0


class TestProductLookup:
    """Test product lookup methods."""

    def test_get_product_by_id_success(self, config):
        """Test successful product lookup by ID."""
        product = config.get_product_by_id("premium.personal.yearly")
        assert product is not None
        assert product.id == "premium.personal.yearly"
        assert hasattr(product, "title")

    def test_get_product_by_id_not_found_returns_none(self, config):
        """Test that get_product_by_id returns None when not found."""
        product = config.get_product_by_id("non.existent.product")
        assert product is None

    def test_get_all_subscription_ids(self, config):
        """Test getting all subscription IDs."""
        sub_ids = config.get_all_subscription_ids()
        assert isinstance(sub_ids, list)
        assert len(sub_ids) > 0
        assert all(isinstance(sid, str) for sid in sub_ids)

    def test_get_all_subscription_ids_matches_subscriptions(self, config):
        """Test that subscription IDs match actual subscriptions."""
        sub_ids = config.get_all_subscription_ids()
        subscriptions = config.products.subscriptions
        assert len(sub_ids) == len(subscriptions)

    def test_can_lookup_all_subscriptions_by_id(self, config):
        """Test that all subscriptions can be looked up by their ID."""
        for sub_id in config.get_all_subscription_ids():
            product = config.get_product_by_id(sub_id)
            assert product is not None
            assert product.id == sub_id


class TestConfigReload:
    """Test configuration reload functionality."""

    def test_reload_method_exists(self, config):
        """Test that reload method exists."""
        assert hasattr(config, "reload")
        assert callable(config.reload)

    def test_reload_does_not_raise_error(self, config):
        """Test that calling reload doesn't raise an error."""
        config.reload()  # Should not raise


class TestGetConfigSingleton:
    """Test get_config singleton pattern."""

    def test_get_config_returns_instance(self):
        """Test that get_config returns a Config instance."""
        config = get_config()
        assert isinstance(config, Config)

    def test_get_config_returns_same_instance(self):
        """Test that get_config returns the same instance (singleton)."""
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2


class TestConfigurationFields:
    """Test specific configuration field values."""

    def test_pubsub_project_id_format(self, config):
        """Test that Pub/Sub project ID has expected format."""
        project_id = config.pubsub_project_id
        # Should be a non-empty string
        assert isinstance(project_id, str)
        assert len(project_id) > 0

    def test_pubsub_topic_format(self, config):
        """Test that Pub/Sub topic has expected format."""
        topic = config.pubsub_topic
        # Should be a non-empty string
        assert isinstance(topic, str)
        assert len(topic) > 0

    def test_default_package_name_format(self, config):
        """Test that default package name has expected format."""
        package_name = config.default_package_name
        # Should be a non-empty string, typically with dots
        assert isinstance(package_name, str)
        assert len(package_name) > 0


# Parametrized tests for known products
@pytest.mark.parametrize("product_id", [
    "premium.personal.yearly",
    "premium.family.yearly",
])
def test_known_products_can_be_found(product_id):
    """Test that known products can be found by ID."""
    config = get_config()
    product = config.get_product_by_id(product_id)
    assert product is not None
    assert product.id == product_id


@pytest.mark.parametrize("invalid_id", [
    "non.existent.product",
    "invalid_id",
    "",
])
def test_invalid_product_ids_return_none(invalid_id):
    """Test that invalid product IDs return None."""
    config = get_config()
    product = config.get_product_by_id(invalid_id)
    assert product is None
