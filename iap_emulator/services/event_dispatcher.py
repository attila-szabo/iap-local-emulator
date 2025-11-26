"""RTDN event publishing to Google Cloud Pub/Sub.

Responsibilities:
- Format DeveloperNotification messages
- Publish to Pub/Sub topic
- Handle all 13 RTDN notification types
- Manage Pub/Sub client lifecycle
"""

import json
from typing import Optional
from threading import RLock

from google.cloud import pubsub_v1
from google.api_core import retry
from google.api_core.exceptions import GoogleAPIError

from iap_emulator.logging_config import get_logger
from iap_emulator.models.events import DeveloperNotification, SubscriptionNotification, OneTimeProductNotification
from iap_emulator.models.subscription import NotificationType
from iap_emulator.repositories.product_repository import get_product_repository
from iap_emulator.services.time_controller import get_time_controller

logger = get_logger(__name__)


class EventDispatcher:
    """Dispatches RTDN events to Google Cloud Pub/Sub.

    This service publishes Real-Time Developer Notifications to configured
    Pub/Sub topics. It handles connection management, error handling, and
    retry logic.

    Thread-safe singleton pattern.
    """

    def __init__(self):
        """initialize event dispatcher"""
        self._lock = RLock()
        self._publisher: Optional[pubsub_v1.PublisherClient] = None
        self._topic_path: Optional[str] = None
        self._enabled = False
        self._product_repo = get_product_repository()
        self._time_controller = get_time_controller()

        self._initialize()

    def _initialize(self) -> None:
        """Init pub/sub publisher from config"""
        from iap_emulator.config import get_config
        config = get_config()

        self._enabled = config.emulator_settings.rtdn_enabled
        if not self._enabled:
            logger.info("event_dispatcher_disabled", message="RTDN notifications are disabled in config")
            return

        try:
            self._publisher = pubsub_v1.PublisherClient()

            project_id = config.pubsub_project_id
            topic_name = config.pubsub_topic
            self._topic_path = self._publisher.topic_path(project_id, topic_name)

            # Auto-create topic if it doesn't exist
            self._ensure_topic_exists(project_id, topic_name)

            # Auto-create default subscription if it doesn't exist
            subscription_name = config.pubsub_subscription
            self._ensure_subscription_exists(project_id, topic_name, subscription_name)

            logger.info(
                "event_dispatcher_initialized",
                project_id=project_id,
                topic=topic_name,
                topic_path=self._topic_path,
            )

        except Exception as e:
            logger.error(
                "event_dispatcher_init_failed",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            # Disable dispatcher if initialization fails
            self._enabled = False

    def _ensure_topic_exists(self, project_id: str, topic_name: str) -> None:
        """Ensure Pub/Sub topic exists, create if it doesn't.

        Args:
            project_id: GCP project ID
            topic_name: Topic name (without project path)
        """
        if not self._publisher:
            return

        topic_path = self._publisher.topic_path(project_id, topic_name)

        try:
            # Try to get the topic first
            self._publisher.get_topic(request={"topic": topic_path})
            logger.info(
                "pubsub_topic_exists",
                topic=topic_name,
                topic_path=topic_path,
            )
        except Exception:
            # Topic doesn't exist, create it
            try:
                topic = self._publisher.create_topic(request={"name": topic_path})
                logger.info(
                    "pubsub_topic_created",
                    topic=topic_name,
                    topic_path=topic.name,
                )
            except Exception as e:
                logger.error(
                    "pubsub_topic_create_failed",
                    topic=topic_name,
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                )
                raise

    def _ensure_subscription_exists(self, project_id: str, topic_name: str, subscription_name: str) -> None:
        """Ensure Pub/Sub subscription exists, create if it doesn't.

        Args:
            project_id: GCP project ID
            topic_name: Topic name (without project path)
            subscription_name: Subscription name (without project path)
        """
        if not self._publisher:
            return

        subscriber = pubsub_v1.SubscriberClient()
        topic_path = self._publisher.topic_path(project_id, topic_name)
        subscription_path = subscriber.subscription_path(project_id, subscription_name)

        try:
            # Try to get the subscription first
            subscriber.get_subscription(request={"subscription": subscription_path})
            logger.info(
                "pubsub_subscription_exists",
                subscription=subscription_name,
                subscription_path=subscription_path,
            )
        except Exception:
            # Subscription doesn't exist, create it
            try:
                subscription = subscriber.create_subscription(
                    request={
                        "name": subscription_path,
                        "topic": topic_path,
                    }
                )
                logger.info(
                    "pubsub_subscription_created",
                    subscription=subscription_name,
                    subscription_path=subscription.name,
                    topic=topic_path,
                )
            except Exception as e:
                logger.error(
                    "pubsub_subscription_create_failed",
                    subscription=subscription_name,
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                )
                raise

    def is_enabled(self) -> bool:
        """Check if event dispatcher is enabled.

        Returns:
            True if RTDN notifications are enabled and client is initialized
        """
        return self._enabled and self._publisher is not None

    def publish_subscription_event(
            self,
            notification_type: NotificationType,
            purchase_token: str,
            subscription_id: str,
            package_name: str,
    ) -> bool:
        """Publish a subscription lifecycle event.

        Args:
            notification_type: Type of subscription event
            purchase_token: Subscription purchase token
            subscription_id: Subscription product ID
            package_name: Android package name

        Returns:
            True if published successfully, False otherwise
        """
        if not self.is_enabled():
            logger.debug("event_dispatcher_disabled", message="Skipping event publication")
            return False

        with self._lock:
            try:
                # Get current time
                current_time = self._time_controller.get_current_time_millis()

                # Create subscription notification
                sub_notification = SubscriptionNotification(
                    version="1.0",
                    notification_type=notification_type.value,
                    purchase_token=purchase_token,
                    subscription_id=subscription_id,
                )

                # Create developer notification
                dev_notification = DeveloperNotification(
                    version="1.0",
                    package_name=package_name,
                    event_time_millis=current_time,
                    subscription_notification=sub_notification,
                )

                # Publish to Pub/Sub
                self._publish_notification(dev_notification)

                logger.info(
                    "subscription_event_published",
                    notification_type=notification_type.name,
                    notification_type_value=notification_type.value,
                    subscription_id=subscription_id,
                    token=purchase_token[:16] + "...",
                )

                return True

            except Exception as e:
                logger.error(
                    "subscription_event_publish_failed",
                    notification_type=notification_type.name,
                    subscription_id=subscription_id,
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                )
                return False

    def publish_product_event(
            self,
            notification_type: int,
            purchase_token: str,
            product_id: str,
            package_name: str,
    ) -> bool:
        """Publish a one-time product event.

        Args:
            notification_type: Type of product event (1-4)
            purchase_token: Product purchase token
            product_id: Product SKU/ID
            package_name: Android package name

        Returns:
            True if published successfully, False otherwise
        """
        if not self.is_enabled():
            logger.debug("event_dispatcher_disabled", message="Skipping event publication")
            return False

        with self._lock:
            try:
                # Get current time
                current_time = self._time_controller.get_current_time_millis()

                # Create product notification
                product_notification = OneTimeProductNotification(
                    version="1.0",
                    notification_type=notification_type,
                    purchase_token=purchase_token,
                    sku=product_id,
                )

                # Create developer notification
                dev_notification = DeveloperNotification(
                    version="1.0",
                    package_name=package_name,
                    event_time_millis=current_time,
                    one_time_product_notification=product_notification,
                )

                # Publish to Pub/Sub
                self._publish_notification(dev_notification)

                logger.info(
                    "product_event_published",
                    notification_type=notification_type,
                    product_id=product_id,
                    token=purchase_token[:16] + "...",
                )

                return True

            except Exception as e:
                logger.error(
                    "product_event_publish_failed",
                    notification_type=notification_type,
                    product_id=product_id,
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                )
                return False

    def _publish_notification(self, notification: DeveloperNotification):
        """Publish a developer notification to Pub/Sub.

        Args:
            notification: Developer notification to publish

        Raises:
            GoogleAPIError: If publication fails after retries
        """
        if not self._publisher or not self._topic_path:
            raise RuntimeError("Publisher is not initialized")

        # convert to json bytes
        message_data = notification.model_dump_json().encode("utf-8")

        # publish with retry logic (automatic retries on transient errors
        # Publish with retry logic (automatic retries on transient errors)
        future = self._publisher.publish(
            self._topic_path,
            message_data,
            # Add attributes for filtering
            notification_type=str(notification.subscription_notification.notification_type
                                  if notification.subscription_notification
                                  else notification.one_time_product_notification.notification_type
            if notification.one_time_product_notification
            else 0),
            package_name=notification.package_name,
        )

        # Wait for publish to complete (with timeout)
        try:
            message_id = future.result(timeout=5.0)
            logger.debug("pubsub_message_published", message_id=message_id)
        except Exception as e:
            logger.error(
                "pubsub_publish_failed",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            raise

    def shutdown(self) -> None:
        """Shutdown the event dispatcher and close connections."""
        with self._lock:
            if self._publisher:
                logger.info("event_dispatcher_shutting_down")
                # Note: PublisherClient doesn't have explicit close in v1
                self._publisher = None
                self._topic_path = None
                logger.info("event_dispatcher_shutdown_complete")

_event_dispatcher: Optional[EventDispatcher] = None
_dispatcher_lock = RLock()

def get_event_dispatcher() -> EventDispatcher:
    """Get or create the singleton EventDispatcher instance.

    Returns:
        EventDispatcher singleton instance
    """
    global _event_dispatcher
    if _event_dispatcher is None:
        with _dispatcher_lock:
            if _event_dispatcher is None:
                _event_dispatcher = EventDispatcher()
    return _event_dispatcher

def reset_event_dispatcher() -> None:
    """Reset the singleton EventDispatcher instance (for testing)."""
    global _event_dispatcher

    with _dispatcher_lock:
        if _event_dispatcher is not None:
            _event_dispatcher.shutdown()
            _event_dispatcher = None
