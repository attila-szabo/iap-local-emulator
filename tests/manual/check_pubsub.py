#!/usr/bin/env python3
"""Verify Pub/Sub resources for RTDN testing.

This script checks that the required Pub/Sub topic and subscription exist
in the emulator.

Usage:
    export PUBSUB_EMULATOR_HOST=localhost:8085
    python tests/manual/check_pubsub.py
"""

import os
import sys

try:
    from google.cloud import pubsub_v1
except ImportError:
    print("✗ Error: google-cloud-pubsub is not installed")
    print("\nInstall it with:")
    print("  pip install google-cloud-pubsub")
    sys.exit(1)

# Configuration
PROJECT_ID = os.environ.get("PUBSUB_PROJECT_ID", "emulator-project")
EXPECTED_TOPIC = "iap_rtdn"
EXPECTED_SUBSCRIPTION = "iap_rtdn_sub"


def main():
    """Check Pub/Sub resources."""
    # Check if emulator host is set
    emulator_host = os.environ.get("PUBSUB_EMULATOR_HOST")
    if not emulator_host:
        print("✗ ERROR: PUBSUB_EMULATOR_HOST not set!")
        print("\nSet it with:")
        print("  export PUBSUB_EMULATOR_HOST=localhost:8085")
        sys.exit(1)

    print(f"Pub/Sub Emulator: {emulator_host}")
    print(f"Project: {PROJECT_ID}\n")

    # Create clients
    publisher = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()
    project_path = f"projects/{PROJECT_ID}"

    # Check topics
    print("Checking topics...")
    try:
        topics = list(publisher.list_topics(request={"project": project_path}))
        if topics:
            expected_topic_path = f"projects/{PROJECT_ID}/topics/{EXPECTED_TOPIC}"
            found_expected = False

            for topic in topics:
                if topic.name == expected_topic_path:
                    print(f"  ✓ {topic.name}")
                    found_expected = True
                else:
                    print(f"    {topic.name}")

            if not found_expected:
                print(f"\n  ✗ Expected topic not found: {expected_topic_path}")
                print("    The IAP emulator should create this on startup.")
                sys.exit(1)
        else:
            print("  ✗ No topics found")
            print(f"    Expected: projects/{PROJECT_ID}/topics/{EXPECTED_TOPIC}")
            print("    Make sure the IAP emulator is running with PUBSUB_EMULATOR_HOST set")
            sys.exit(1)
    except Exception as e:
        print(f"  ✗ Error listing topics: {e}")
        sys.exit(1)

    # Check subscriptions
    print("\nChecking subscriptions...")
    try:
        subscriptions = list(subscriber.list_subscriptions(request={"project": project_path}))
        if subscriptions:
            expected_sub_path = f"projects/{PROJECT_ID}/subscriptions/{EXPECTED_SUBSCRIPTION}"
            found_expected = False

            for sub in subscriptions:
                if sub.name == expected_sub_path:
                    print(f"  ✓ {sub.name}")
                    print(f"    → {sub.topic}")
                    found_expected = True
                else:
                    print(f"    {sub.name} → {sub.topic}")

            if not found_expected:
                print(f"\n  ✗ Expected subscription not found: {expected_sub_path}")
                print("    The IAP emulator should create this on startup.")
                sys.exit(1)
        else:
            print("  ✗ No subscriptions found")
            print(f"    Expected: projects/{PROJECT_ID}/subscriptions/{EXPECTED_SUBSCRIPTION}")
            print("    Make sure the IAP emulator is running with PUBSUB_EMULATOR_HOST set")
            sys.exit(1)
    except Exception as e:
        print(f"  ✗ Error listing subscriptions: {e}")
        sys.exit(1)

    print("\n✅ All required Pub/Sub resources exist!")
    print("\nYou can now run:")
    print("  python tests/manual/rtdn_subscriber.py")


if __name__ == "__main__":
    main()
