"""Unit tests for EventDispatcher service."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from google.cloud import pubsub_v1
from iap_emulator.services.event_dispatcher import EventDispatcher, get_event_dispatcher, reset_event_dispatcher
from iap_emulator.models.subscription import NotificationType


class TestEventDispatcherInitialization:
    """Test EventDispatcher initialization and configuration."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_event_dispatcher()

    @patch('iap_emulator.services.event_dispatcher.pubsub_v1.PublisherClient')
    def test_dispatcher_initializes_when_enabled(self, mock_publisher_class):
        """Test dispatcher initializes when RTDN is enabled in config."""
        mock_publisher = Mock()
        mock_publisher.topic_path.return_value = "projects/emulator-project/topics/iap_rtdn"
        mock_publisher_class.return_value = mock_publisher

        dispatcher = EventDispatcher()

        assert dispatcher.is_enabled()
        mock_publisher_class.assert_called_once()

    def test_singleton_pattern(self):
        """Test that get_event_dispatcher returns the same instance."""
        dispatcher1 = get_event_dispatcher()
        dispatcher2 = get_event_dispatcher()

        assert dispatcher1 is dispatcher2


class TestEventPublishing:
    """Test event publishing functionality."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_event_dispatcher()

    @patch('iap_emulator.services.event_dispatcher.pubsub_v1.PublisherClient')
    def test_publish_subscription_event_success(self, mock_publisher_class):
        """successful subscription event publishing"""
        mock_publisher = Mock()
        mock_future = Mock()
        mock_future.result.return_value = "messages-id-23"
        mock_publisher.publish.return_value = mock_future
        mock_publisher.topic_path.return_value = "projects/emulator-project/topics/iap_rtdn"
        mock_publisher_class.return_value = mock_publisher

        dispatcher = EventDispatcher()

        # Publish event
        result = dispatcher.publish_subscription_event(
            notification_type=NotificationType.SUBSCRIPTION_PURCHASED,
            purchase_token="test_token_123",
            subscription_id="premium.yearly",
            package_name="com.example.app",
        )

        assert result is True
        mock_publisher.publish.assert_called_once()

    @patch('iap_emulator.services.event_dispatcher.pubsub_v1.PublisherClient')
    def test_publish_product_event_success(self, mock_publisher_class):
        """Test successful product event publishing."""
        # Setup mock
        mock_publisher = Mock()
        mock_future = Mock()
        mock_future.result.return_value = "message-id-456"
        mock_publisher.publish.return_value = mock_future
        mock_publisher.topic_path.return_value = "projects/emulator-project/topics/iap_rtdn"
        mock_publisher_class.return_value = mock_publisher

        dispatcher = EventDispatcher()

        # Publish event
        result = dispatcher.publish_product_event(
            notification_type=1,  # ONE_TIME_PRODUCT_PURCHASED
            purchase_token="test_product_token",
            product_id="coins.100",
            package_name="com.example.app",
        )

        assert result is True
        mock_publisher.publish.assert_called_once()

    @patch('iap_emulator.services.event_dispatcher.pubsub_v1.PublisherClient')
    def test_publish_event_when_disabled(self, mock_publisher_class):
        """Test publishing when dispatcher is disabled returns False."""
        mock_publisher = Mock()
        mock_publisher_class.return_value = mock_publisher

        dispatcher = EventDispatcher()
        # Force disable
        dispatcher._enabled = False

        result = dispatcher.publish_subscription_event(
            notification_type=NotificationType.SUBSCRIPTION_RENEWED,
            purchase_token="test_token",
            subscription_id="premium.yearly",
            package_name="com.example.app",
        )

        assert result is False
        mock_publisher.publish.assert_not_called()

    @patch('iap_emulator.services.event_dispatcher.pubsub_v1.PublisherClient')
    def test_publish_event_handles_exceptions(self, mock_publisher_class):
        """Test that publishing handles exceptions gracefully."""
        # Setup mock to raise exception
        mock_publisher = Mock()
        mock_future = Mock()
        mock_future.result.side_effect = Exception("Pub/Sub error")
        mock_publisher.publish.return_value = mock_future
        mock_publisher.topic_path.return_value = "projects/emulator-project/topics/iap_rtdn"
        mock_publisher_class.return_value = mock_publisher

        dispatcher = EventDispatcher()

        # Should return False but not raise exception
        result = dispatcher.publish_subscription_event(
            notification_type=NotificationType.SUBSCRIPTION_CANCELED,
            purchase_token="test_token",
            subscription_id="premium.yearly",
            package_name="com.example.app",
        )

        assert result is False


class TestEventDispatcherShutdown:
    """Test dispatcher shutdown."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_event_dispatcher()

    @patch('iap_emulator.services.event_dispatcher.pubsub_v1.PublisherClient')
    def test_shutdown_cleans_up_resources(self, mock_publisher_class):
        """Test that shutdown properly cleans up resources."""
        mock_publisher = Mock()
        mock_publisher.topic_path.return_value = "projects/emulator-project/topics/iap_rtdn"
        mock_publisher_class.return_value = mock_publisher

        dispatcher = EventDispatcher()
        assert dispatcher._publisher is not None

        dispatcher.shutdown()

        assert dispatcher._publisher is None
        assert dispatcher._topic_path is None


class TestNotificationFormat:
    """Test that notifications are formatted correctly."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_event_dispatcher()

    @patch('iap_emulator.services.event_dispatcher.pubsub_v1.PublisherClient')
    def test_subscription_notification_format(self, mock_publisher_class):
        """Test that subscription notifications have correct structure."""
        mock_publisher = Mock()
        mock_future = Mock()
        mock_future.result.return_value = "message-id"
        mock_publisher.publish.return_value = mock_future
        mock_publisher.topic_path.return_value = "projects/emulator-project/topics/iap_rtdn"
        mock_publisher_class.return_value = mock_publisher

        dispatcher = EventDispatcher()

        dispatcher.publish_subscription_event(
            notification_type=NotificationType.SUBSCRIPTION_RENEWED,
            purchase_token="test_token",
            subscription_id="premium.yearly",
            package_name="com.example.app",
        )

        # Verify publish was called
        assert mock_publisher.publish.called

        # Get the call arguments
        call_args = mock_publisher.publish.call_args

        # Verify message data is JSON
        message_data = call_args[0][1]
        assert isinstance(message_data, bytes)

        # Verify attributes
        attrs = call_args[1]
        assert "notification_type" in attrs
        assert "package_name" in attrs
        assert attrs["package_name"] == "com.example.app"
