# Manual Testing Guide - RTDN Events

This guide provides step-by-step instructions for manually testing Real-Time Developer Notifications (RTDN) event publishing and delivery.

## Overview

The IAP Emulator publishes RTDN events to Google Cloud Pub/Sub when subscription lifecycle events occur. This folder contains scripts to test the end-to-end event flow.

## Prerequisites

1. **Pub/Sub Emulator** running on `localhost:8085`:
   ```bash
   docker run -d --name pubsub-emulator \
     -p 8085:8085 \
     gcr.io/google.com/cloudsdktool/google-cloud-cli:emulators \
     gcloud beta emulators pubsub start --host-port=0.0.0.0:8085 --project=emulator-project
   ```

2. **Python environment** with dependencies:
   ```bash
   source .venv/bin/activate
   pip install google-cloud-pubsub
   ```

## Quick Start

### 1. Start the IAP Emulator

**IMPORTANT**: The emulator must be started with `PUBSUB_EMULATOR_HOST` set:

```bash
# Activate virtual environment
source .venv/bin/activate

# Start emulator with Pub/Sub configuration
PUBSUB_EMULATOR_HOST=localhost:8085 python -m iap_emulator
```

The emulator will automatically:
- Create Pub/Sub topic: `projects/emulator-project/topics/iap_rtdn`
- Create subscription: `projects/emulator-project/subscriptions/iap_rtdn_sub`

Verify initialization in the logs:
```
{"event": "pubsub_topic_exists", "topic": "iap_rtdn"}
{"event": "pubsub_subscription_created", "subscription": "iap_rtdn_sub"}
{"event": "pubsub_enabled", "message": "Event dispatcher initialized and ready"}
```

### 2. Verify Pub/Sub Setup

```bash
# Set environment variable
export PUBSUB_EMULATOR_HOST=localhost:8085

# Check Pub/Sub resources
python tests/manual/check_pubsub.py
```

Expected output:
```
✓ Pub/Sub Emulator: localhost:8085
✓ Topic: projects/emulator-project/topics/iap_rtdn
✓ Subscription: projects/emulator-project/subscriptions/iap_rtdn_sub
```

### 3. Subscribe to RTDN Events

In a separate terminal:

```bash
source .venv/bin/activate
export PUBSUB_EMULATOR_HOST=localhost:8085
python tests/manual/rtdn_subscriber.py
```

You should see:
```
🎧 Listening for RTDN events...
   Project: emulator-project
   Topic: iap_rtdn
   Subscription: iap_rtdn_sub
   Press Ctrl+C to stop
```

### 4. Trigger Events

In another terminal, create a subscription to trigger an event:

```bash
curl -X POST http://localhost:8080/emulator/subscriptions \
  -H "Content-Type: application/json" \
  -d '{
    "package_name": "com.example.app",
    "subscription_id": "premium.personal.yearly",
    "user_id": "user-001"
  }'
```

The subscriber should display:
```
━━━ RTDN Event Received ━━━
Package: com.example.app
Type: SUBSCRIPTION_PURCHASED (4)
Subscription: premium.personal.yearly
Token: emulator_sub_...
✓ Acknowledged
```

## Test Scenarios

### Scenario 1: Subscription Purchase

```bash
curl -X POST http://localhost:8080/emulator/subscriptions \
  -H "Content-Type: application/json" \
  -d '{
    "package_name": "com.example.app",
    "subscription_id": "premium.personal.yearly",
    "user_id": "user-test-001"
  }'
```

**Expected Event**: `SUBSCRIPTION_PURCHASED (4)`

### Scenario 2: Manual Renewal

```bash
# Save the token from the previous response
TOKEN="emulator_sub_..."

# Trigger renewal
curl -X POST "http://localhost:8080/emulator/subscriptions/${TOKEN}/renew"
```

**Expected Event**: `SUBSCRIPTION_RENEWED (2)`

### Scenario 3: Subscription Cancellation

```bash
curl -X POST "http://localhost:8080/emulator/subscriptions/${TOKEN}/cancel" \
  -H "Content-Type: application/json" \
  -d '{"immediate": false}'
```

**Expected Event**: `SUBSCRIPTION_CANCELED (3)`

### Scenario 4: Payment Failure & Recovery

```bash
# Trigger payment failure
curl -X POST "http://localhost:8080/emulator/subscriptions/${TOKEN}/payment-failed"

# Expected event: SUBSCRIPTION_IN_GRACE_PERIOD (6)

# Recover payment
curl -X POST "http://localhost:8080/emulator/subscriptions/${TOKEN}/payment-recovered"

# Expected event: SUBSCRIPTION_RECOVERED (1)
```

### Scenario 5: Pause & Resume

```bash
# Pause subscription
curl -X POST "http://localhost:8080/emulator/subscriptions/${TOKEN}/pause"

# Expected event: SUBSCRIPTION_PAUSED (10)

# Resume subscription
curl -X POST "http://localhost:8080/emulator/subscriptions/${TOKEN}/resume"

# Expected event: SUBSCRIPTION_RESTARTED (7)
```

### Scenario 6: Subscription Acknowledgement

```bash
# Create subscription (save token)
RESPONSE=$(curl -X POST http://localhost:8080/emulator/subscriptions \
  -H "Content-Type: application/json" \
  -d '{
    "package_name": "com.example.app",
    "subscription_id": "premium.personal.yearly",
    "user_id": "user-ack-test"
  }')

# Extract token from response
TOKEN=$(echo $RESPONSE | jq -r '.token')

# Get subscription details (check acknowledgement_state = 0)
curl -X GET "http://localhost:8080/androidpublisher/v3/applications/com.example.app/purchases/subscriptions/premium.personal.yearly/tokens/${TOKEN}"

# Acknowledge the subscription
curl -X POST "http://localhost:8080/androidpublisher/v3/applications/com.example.app/purchases/subscriptions/premium.personal.yearly/tokens/${TOKEN}:acknowledge"

# Get subscription details again (check acknowledgement_state = 1)
curl -X GET "http://localhost:8080/androidpublisher/v3/applications/com.example.app/purchases/subscriptions/premium.personal.yearly/tokens/${TOKEN}"

# Acknowledge again (should succeed - idempotent)
curl -X POST "http://localhost:8080/androidpublisher/v3/applications/com.example.app/purchases/subscriptions/premium.personal.yearly/tokens/${TOKEN}:acknowledge"
```

**Expected Behavior**:
- Initial GET returns `"acknowledgementState": 0`
- POST returns `204 No Content`
- Second GET returns `"acknowledgementState": 1`
- Second POST returns `204 No Content` (idempotent)

**Error Cases**:
```bash
# Wrong package name (404)
curl -X POST "http://localhost:8080/androidpublisher/v3/applications/com.wrong.package/purchases/subscriptions/premium.personal.yearly/tokens/${TOKEN}:acknowledge"

# Wrong subscription ID (404)
curl -X POST "http://localhost:8080/androidpublisher/v3/applications/com.example.app/purchases/subscriptions/wrong.subscription/tokens/${TOKEN}:acknowledge"

# Non-existent token (404)
curl -X POST "http://localhost:8080/androidpublisher/v3/applications/com.example.app/purchases/subscriptions/premium.personal.yearly/tokens/invalid_token:acknowledge"
```

### Scenario 7: Auto-Renewal via Time Advancement

```bash
# Create subscription (save token)
curl -X POST http://localhost:8080/emulator/subscriptions \
  -H "Content-Type: application/json" \
  -d '{
    "package_name": "com.example.app",
    "subscription_id": "premium.personal.yearly",
    "user_id": "user-time-test"
  }'

# Advance time by 366 days to trigger renewal
curl -X POST http://localhost:8080/emulator/time/advance \
  -H "Content-Type: application/json" \
  -d '{"days": 366}'
```

**Expected Events**:
1. `SUBSCRIPTION_PURCHASED (4)` - from creation
2. `SUBSCRIPTION_RENEWED (2)` - from time advancement

## Troubleshooting

### Problem: "PUBSUB_EMULATOR_HOST not set"

**Solution**: Export the environment variable before running scripts:
```bash
export PUBSUB_EMULATOR_HOST=localhost:8085
```

### Problem: No events received by subscriber

**Checks**:
1. Verify emulator was started with `PUBSUB_EMULATOR_HOST` set
2. Check emulator logs for `"event": "subscription_event_published"`
3. Restart the emulator if it was started without the env var

### Problem: "Invalid [topics] name" error

**Cause**: The Pub/Sub emulator rejects topic names starting with "google" (reserved namespace).

**Solution**: The topic name has been changed to `iap_rtdn` in the configuration.

### Problem: Emulator can't connect to Pub/Sub

**Checks**:
1. Verify Pub/Sub emulator is running:
   ```bash
   docker ps | grep pubsub
   ```
2. Test connection:
   ```bash
   export PUBSUB_EMULATOR_HOST=localhost:8085
   python tests/manual/check_pubsub.py
   ```

## Scripts Reference

- **`rtdn_subscriber.py`** - Subscribes to RTDN events and displays them in real-time
- **`check_pubsub.py`** - Diagnostic tool to verify Pub/Sub resources exist

## RTDN Event Types

| Event Type | Code | Description |
|------------|------|-------------|
| SUBSCRIPTION_RECOVERED | 1 | Payment recovered after failure |
| SUBSCRIPTION_RENEWED | 2 | Subscription auto-renewed |
| SUBSCRIPTION_CANCELED | 3 | Subscription canceled (deferred) |
| SUBSCRIPTION_PURCHASED | 4 | New subscription created |
| SUBSCRIPTION_ON_HOLD | 5 | Grace period expired, on hold |
| SUBSCRIPTION_IN_GRACE_PERIOD | 6 | Payment failed, in grace period |
| SUBSCRIPTION_RESTARTED | 7 | Subscription resumed |
| SUBSCRIPTION_PRICE_CHANGE_CONFIRMED | 8 | Not implemented |
| SUBSCRIPTION_DEFERRED | 9 | Renewal deferred |
| SUBSCRIPTION_PAUSED | 10 | Subscription paused |
| SUBSCRIPTION_PAUSE_SCHEDULE_CHANGED | 11 | Not implemented |
| SUBSCRIPTION_REVOKED | 12 | Subscription revoked |
| SUBSCRIPTION_EXPIRED | 13 | Subscription expired (immediate) |

## Cleanup

```bash
# Stop subscriber (Ctrl+C in subscriber terminal)

# Stop IAP emulator (Ctrl+C in emulator terminal)

# Stop Pub/Sub emulator
docker stop pubsub-emulator
docker rm pubsub-emulator
```
