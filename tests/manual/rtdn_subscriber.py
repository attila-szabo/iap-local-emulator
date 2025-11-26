#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Subscribe to RTDN events from the IAP Emulator.

This script listens for Real-Time Developer Notifications published by the
IAP Emulator to Google Cloud Pub/Sub and displays them in real-time.

Usage:
    export PUBSUB_EMULATOR_HOST=localhost:8085
    python tests/manual/rtdn_subscriber.py
"""

import json
import os
import sys
from datetime import datetime
from typing import Any, Dict

try:
    from google.cloud import pubsub_v1
except ImportError:
    print("Error: google-cloud-pubsub is not installed")
    print("Install it with: pip install google-cloud-pubsub")
    sys.exit(1)


# Configuration
PROJECT_ID = os.environ.get("PUBSUB_PROJECT_ID", "emulator-project")
TOPIC_NAME = os.environ.get("PUBSUB_TOPIC_NAME", "iap_rtdn")
SUBSCRIPTION_NAME = os.environ.get("PUBSUB_SUBSCRIPTION_NAME", "iap_rtdn_sub")

# Event type names for display
NOTIFICATION_TYPES = {
    1: "SUBSCRIPTION_RECOVERED",
    2: "SUBSCRIPTION_RENEWED",
    3: "SUBSCRIPTION_CANCELED",
    4: "SUBSCRIPTION_PURCHASED",
    5: "SUBSCRIPTION_ON_HOLD",
    6: "SUBSCRIPTION_IN_GRACE_PERIOD",
    7: "SUBSCRIPTION_RESTARTED",
    8: "SUBSCRIPTION_PRICE_CHANGE_CONFIRMED",
    9: "SUBSCRIPTION_DEFERRED",
    10: "SUBSCRIPTION_PAUSED",
    11: "SUBSCRIPTION_PAUSE_SCHEDULE_CHANGED",
    12: "SUBSCRIPTION_REVOKED",
    13: "SUBSCRIPTION_EXPIRED",
}


def format_notification(data: Dict[str, Any]) -> str:
    """Format notification for pretty printing."""
    lines = []

    # Package and timestamp
    package = data.get('package_name', 'N/A')
    event_time = data.get('event_time_millis', 0)
    timestamp = datetime.fromtimestamp(event_time / 1000).strftime('%Y-%m-%d %H:%M:%S')

    lines.append(f"Package: {package}")
    lines.append(f"Time: {timestamp}")

    # Subscription notification
    if 'subscription_notification' in data and data['subscription_notification']:
        sub = data['subscription_notification']
        notification_type = sub.get('notification_type', 0)
        type_name = NOTIFICATION_TYPES.get(notification_type, f"UNKNOWN_{notification_type}")

        lines.append(f"Type: {type_name} ({notification_type})")
        lines.append(f"Subscription: {sub.get('subscription_id', 'N/A')}")

        token = sub.get('purchase_token', '')
        if len(token) > 40:
            lines.append(f"Token: {token[:40]}...")
        else:
            lines.append(f"Token: {token}")

    # One-time product notification
    elif 'one_time_product_notification' in data and data['one_time_product_notification']:
        product = data['one_time_product_notification']
        notification_type = product.get('notification_type', 0)

        lines.append(f"Type: ONE_TIME_PRODUCT ({notification_type})")
        lines.append(f"Product: {product.get('sku', 'N/A')}")

        token = product.get('purchase_token', '')
        if len(token) > 40:
            lines.append(f"Token: {token[:40]}...")
        else:
            lines.append(f"Token: {token}")

    return "\n".join(lines)


def callback(message: Any) -> None:
    """Process received RTDN message."""
    try:
        # Parse message data
        data = json.loads(message.data.decode('utf-8'))

        # Print formatted notification
        print(f"\n{'━' * 50}")
        print("RTDN Event Received")
        print('━' * 50)
        print(format_notification(data))

        # Acknowledge the message
        message.ack()
        print("✓ Acknowledged")

    except Exception as e:
        print(f"\n✗ Error processing message: {e}")
        print(f"   Message data: {message.data}")
        # Still acknowledge to avoid redelivery
        message.ack()


def main() -> None:
    """Main subscriber loop."""
    # Check if emulator host is set
    emulator_host = os.environ.get("PUBSUB_EMULATOR_HOST")
    if not emulator_host:
        print("✗ ERROR: PUBSUB_EMULATOR_HOST not set!")
        print("\nSet it with:")
        print("  export PUBSUB_EMULATOR_HOST=localhost:8085")
        sys.exit(1)

    print("🎧 Listening for RTDN events...")
    print(f"   Project: {PROJECT_ID}")
    print(f"   Topic: {TOPIC_NAME}")
    print(f"   Subscription: {SUBSCRIPTION_NAME}")
    print(f"   Emulator: {emulator_host}")
    print("   Press Ctrl+C to stop\n")
    print("=" * 50)

    # Create subscriber client
    subscriber = pubsub_v1.SubscriberClient()
    subscription_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_NAME)

    # Start listening for messages
    streaming_pull_future = subscriber.subscribe(
        subscription_path,
        callback=callback
    )

    try:
        # Keep the subscriber running
        streaming_pull_future.result()
    except KeyboardInterrupt:
        print("\n\n✓ Stopping subscriber...")
        streaming_pull_future.cancel()
        streaming_pull_future.result()  # Wait for cancellation
        print("   Subscriber stopped")
    except Exception as e:
        print(f"\n\n✗ Subscriber error: {e}")
        streaming_pull_future.cancel()
        sys.exit(1)


if __name__ == "__main__":
    main()
