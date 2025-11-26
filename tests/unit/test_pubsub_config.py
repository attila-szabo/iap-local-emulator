"""Tests for Pub/Sub configuration loading and access.

Tests the loading, validation, and access patterns for Pub/Sub settings
including project ID, topic, and subscription configuration.
"""

import pytest

from iap_emulator.config import get_config


@pytest.fixture
def config():
    """Get config instance for testing."""
    return get_config()


@pytest.fixture
def pubsub_config(config):
    """Get Pub/Sub config for testing."""
    return config.products.pubsub


class TestPubSubConfigLoading:
    """Test basic Pub/Sub configuration loading."""

    def test_config_loads_successfully(self, config):
        """Test that configuration loads without errors."""
        assert config is not None
        assert config.config_path.exists()

    def test_pubsub_config_accessible(self, config):
        """Test that Pub/Sub config is accessible."""
        pubsub = config.products.pubsub
        assert pubsub is not None

    def test_pubsub_config_has_required_fields(self, pubsub_config):
        """Test that Pub/Sub config has all required fields."""
        assert hasattr(pubsub_config, "project_id")
        assert hasattr(pubsub_config, "topic")
        assert hasattr(pubsub_config, "default_subscription")


class TestPubSubDirectAccess:
    """Test direct access to Pub/Sub settings."""

    def test_direct_access_via_products_pubsub(self, config):
        """Test accessing Pub/Sub config via config.products.pubsub."""
        pubsub = config.products.pubsub
        assert pubsub is not None
        assert pubsub.project_id is not None
        assert pubsub.topic is not None
        assert pubsub.default_subscription is not None

    def test_project_id_via_direct_access(self, pubsub_config):
        """Test accessing project_id directly."""
        assert pubsub_config.project_id is not None
        assert isinstance(pubsub_config.project_id, str)
        assert len(pubsub_config.project_id) > 0

    def test_topic_via_direct_access(self, pubsub_config):
        """Test accessing topic directly."""
        assert pubsub_config.topic is not None
        assert isinstance(pubsub_config.topic, str)
        assert len(pubsub_config.topic) > 0

    def test_default_subscription_via_direct_access(self, pubsub_config):
        """Test accessing default_subscription directly."""
        assert pubsub_config.default_subscription is not None
        assert isinstance(pubsub_config.default_subscription, str)
        assert len(pubsub_config.default_subscription) > 0


class TestPubSubConvenienceProperties:
    """Test convenient property accessors for Pub/Sub settings."""

    def test_pubsub_project_id_property(self, config):
        """Test config.pubsub_project_id convenience property."""
        project_id = config.pubsub_project_id
        assert project_id is not None
        assert isinstance(project_id, str)
        assert len(project_id) > 0

    def test_pubsub_topic_property(self, config):
        """Test config.pubsub_topic convenience property."""
        topic = config.pubsub_topic
        assert topic is not None
        assert isinstance(topic, str)
        assert len(topic) > 0

    def test_pubsub_subscription_property(self, config):
        """Test config.pubsub_subscription convenience property."""
        subscription = config.pubsub_subscription
        assert subscription is not None
        assert isinstance(subscription, str)
        assert len(subscription) > 0

    def test_convenience_properties_match_direct_access(self, config):
        """Test that convenience properties return same values as direct access."""
        pubsub = config.products.pubsub

        assert config.pubsub_project_id == pubsub.project_id
        assert config.pubsub_topic == pubsub.topic
        assert config.pubsub_subscription == pubsub.default_subscription


class TestPubSubExpectedValues:
    """Test that Pub/Sub settings match expected values from products.yaml."""

    def test_project_id_matches_expected(self, config):
        """Test that project ID matches expected value."""
        expected_project = "emulator-project"
        assert config.pubsub_project_id == expected_project

    def test_topic_matches_expected(self, config):
        """Test that topic matches expected value."""
        expected_topic = "google-play-rtdn"
        assert config.pubsub_topic == expected_topic

    def test_subscription_matches_expected(self, config):
        """Test that subscription matches expected value."""
        expected_sub = "google-play-rtdn-sub"
        assert config.pubsub_subscription == expected_sub

    def test_all_expected_values(self, config):
        """Test all expected Pub/Sub values together."""
        assert config.pubsub_project_id == "emulator-project"
        assert config.pubsub_topic == "google-play-rtdn"
        assert config.pubsub_subscription == "google-play-rtdn-sub"


class TestPubSubResourcePaths:
    """Test Pub/Sub resource path formatting."""

    def test_topic_path_format(self, config):
        """Test that topic path can be formatted correctly."""
        topic_path = f"projects/{config.pubsub_project_id}/topics/{config.pubsub_topic}"

        assert "projects/" in topic_path
        assert "/topics/" in topic_path
        assert config.pubsub_project_id in topic_path
        assert config.pubsub_topic in topic_path

    def test_subscription_path_format(self, config):
        """Test that subscription path can be formatted correctly."""
        sub_path = f"projects/{config.pubsub_project_id}/subscriptions/{config.pubsub_subscription}"

        assert "projects/" in sub_path
        assert "/subscriptions/" in sub_path
        assert config.pubsub_project_id in sub_path
        assert config.pubsub_subscription in sub_path

    def test_topic_path_structure(self, config):
        """Test topic path follows GCP structure."""
        topic_path = f"projects/{config.pubsub_project_id}/topics/{config.pubsub_topic}"

        # Should be: projects/PROJECT_ID/topics/TOPIC_NAME
        parts = topic_path.split("/")
        assert len(parts) == 4
        assert parts[0] == "projects"
        assert parts[2] == "topics"

    def test_subscription_path_structure(self, config):
        """Test subscription path follows GCP structure."""
        sub_path = f"projects/{config.pubsub_project_id}/subscriptions/{config.pubsub_subscription}"

        # Should be: projects/PROJECT_ID/subscriptions/SUBSCRIPTION_NAME
        parts = sub_path.split("/")
        assert len(parts) == 4
        assert parts[0] == "projects"
        assert parts[2] == "subscriptions"


class TestPubSubEmulatorIntegration:
    """Test Pub/Sub integration with emulator settings."""

    def test_rtdn_enabled_in_emulator_settings(self, config):
        """Test that RTDN enabled flag is accessible."""
        emulator = config.emulator_settings
        assert hasattr(emulator, "rtdn_enabled")
        assert isinstance(emulator.rtdn_enabled, bool)

    def test_pubsub_and_rtdn_integration(self, config):
        """Test that Pub/Sub config works with RTDN settings."""
        emulator = config.emulator_settings

        # If RTDN is enabled, Pub/Sub settings should be available
        if emulator.rtdn_enabled:
            assert config.pubsub_topic is not None
            assert config.pubsub_subscription is not None

    def test_event_publishing_settings(self, config):
        """Test settings needed for event publishing."""
        emulator = config.emulator_settings

        # All settings needed for event publishing should be present
        assert config.pubsub_project_id is not None
        assert config.pubsub_topic is not None
        assert emulator.rtdn_enabled is not None


class TestPubSubConfigStructure:
    """Test complete Pub/Sub configuration structure."""

    def test_pubsub_nested_under_products(self, config):
        """Test that Pub/Sub config is nested under products."""
        assert hasattr(config, "products")
        assert hasattr(config.products, "pubsub")

    def test_convenience_accessors_available(self, config):
        """Test that convenience accessors are available at config level."""
        assert hasattr(config, "pubsub_project_id")
        assert hasattr(config, "pubsub_topic")
        assert hasattr(config, "pubsub_subscription")

    def test_all_pubsub_fields_accessible(self, config):
        """Test that all Pub/Sub fields are accessible."""
        # Direct access
        pubsub_direct = config.products.pubsub
        assert pubsub_direct.project_id is not None
        assert pubsub_direct.topic is not None
        assert pubsub_direct.default_subscription is not None

        # Convenience access
        assert config.pubsub_project_id is not None
        assert config.pubsub_topic is not None
        assert config.pubsub_subscription is not None


class TestPubSubAccessPatterns:
    """Test different access patterns for Pub/Sub configuration."""

    def test_access_pattern_direct(self, config):
        """Test direct access pattern."""
        pubsub = config.products.pubsub
        project_id = pubsub.project_id
        assert project_id == "emulator-project"

    def test_access_pattern_convenience(self, config):
        """Test convenience property access pattern."""
        project_id = config.pubsub_project_id
        assert project_id == "emulator-project"

    def test_access_pattern_stored_reference(self, config):
        """Test storing reference and accessing."""
        pubsub = config.products.pubsub
        project = pubsub.project_id
        topic = pubsub.topic
        sub = pubsub.default_subscription

        assert project is not None
        assert topic is not None
        assert sub is not None

    def test_multiple_access_patterns_consistent(self, config):
        """Test that multiple access patterns return consistent values."""
        # Pattern 1: Direct
        direct = config.products.pubsub.project_id

        # Pattern 2: Convenience
        convenience = config.pubsub_project_id

        # Should be the same
        assert direct == convenience


class TestPubSubFieldValidation:
    """Test validation of Pub/Sub field values."""

    def test_project_id_format(self, config):
        """Test that project ID has valid format."""
        project_id = config.pubsub_project_id

        # Should be non-empty string
        assert isinstance(project_id, str)
        assert len(project_id) > 0
        # Should not contain invalid characters
        assert "/" not in project_id

    def test_topic_format(self, config):
        """Test that topic has valid format."""
        topic = config.pubsub_topic

        # Should be non-empty string
        assert isinstance(topic, str)
        assert len(topic) > 0
        # Should not contain invalid characters
        assert "/" not in topic

    def test_subscription_format(self, config):
        """Test that subscription has valid format."""
        subscription = config.pubsub_subscription

        # Should be non-empty string
        assert isinstance(subscription, str)
        assert len(subscription) > 0
        # Should not contain invalid characters
        assert "/" not in subscription


# Parametrized tests
@pytest.mark.parametrize("field_name,expected_value", [
    ("pubsub_project_id", "emulator-project"),
    ("pubsub_topic", "google-play-rtdn"),
    ("pubsub_subscription", "google-play-rtdn-sub"),
])
def test_pubsub_field_values(field_name, expected_value):
    """Test individual Pub/Sub field values."""
    config = get_config()
    actual_value = getattr(config, field_name)
    assert actual_value == expected_value


@pytest.mark.parametrize("field_name", [
    "project_id",
    "topic",
    "default_subscription",
])
def test_pubsub_direct_fields_exist(field_name):
    """Test that direct Pub/Sub fields exist."""
    config = get_config()
    pubsub = config.products.pubsub
    assert hasattr(pubsub, field_name)
    assert getattr(pubsub, field_name) is not None


@pytest.mark.parametrize("convenience_property", [
    "pubsub_project_id",
    "pubsub_topic",
    "pubsub_subscription",
])
def test_convenience_properties_exist(convenience_property):
    """Test that convenience properties exist."""
    config = get_config()
    assert hasattr(config, convenience_property)
    assert getattr(config, convenience_property) is not None
