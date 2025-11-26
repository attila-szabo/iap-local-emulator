# .NET Example - Google Play IAP Emulator

A simple, fully working .NET console application demonstrating how to use the Google Play IAP Emulator from C#.

## What This Example Does

This demo shows you how to:
- Create subscriptions via the emulator API
- Query subscription status
- Manipulate time to test renewals
- Simulate payment failures and recovery
- Listen to Real-Time Developer Notifications (RTDN) via Pub/Sub
- Cancel subscriptions

## Prerequisites

- .NET 8.0 SDK or later ([Download here](https://dotnet.microsoft.com/download))
  - Example tested with .NET 9.0
- Docker Desktop (for running the emulator)

## Quick Start

### 1. Start the Emulator

From the repository root:

```bash
docker-compose up
```

Wait for both services to be ready:
- IAP Emulator: http://localhost:8080
- Pub/Sub Emulator: localhost:8085

### 2. Run the API Demo

```bash
cd examples/dotnet
dotnet run
```

You'll see output like:

```
======================================================================
Google Play IAP Emulator - .NET Demo
======================================================================

1. Creating a subscription...
   ✓ Created subscription with token: emulator_sub_abc123...
   Order ID: GPA.1234-5678-9012-3456
   Expiry: 2026-11-25 03:36:59

2. Querying subscription...
   Auto-renewing: True
   Payment state: PAYMENT_RECEIVED
   Price: $29.99 USD

3. Advancing time by 366 days to trigger renewal...
   ✓ Time advanced

4. Checking subscription after renewal...
   Auto-renewing: True
   Expiry: 2027-11-25 03:36:59

5. Simulating payment failure...
   ✓ Payment failed

6. Checking subscription in grace period...
   Auto-renewing: False
   Payment state: PENDING_DEFERRED_UPGRADE_DOWNGRADE (3)

7. Recovering payment...
   ✓ Payment recovered

8. Canceling subscription...
   Auto-renewing: False
   Payment state: PAYMENT_RECEIVED

======================================================================
API Demo completed!
======================================================================
```

### 3. Run the RTDN Listener Demo

In a separate terminal:

```bash
cd examples/dotnet
PUBSUB_EMULATOR_HOST=localhost:8085 dotnet run listen
```

You'll see:

```
Starting RTDN Event Listener...
Project: emulator-project
Subscription: iap_rtdn_sub

Listening for events... (Press Ctrl+C to stop)
----------------------------------------------------------------------
```

### 4. Trigger Events

In another terminal, create a subscription:

```bash
curl -X POST http://localhost:8080/emulator/subscriptions \
  -H "Content-Type: application/json" \
  -d '{
    "package_name": "com.example.app",
    "subscription_id": "premium.personal.yearly",
    "user_id": "test-user-123"
  }'
```

The listener will display:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RTDN Event Received
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Package: com.example.app
Event: SUBSCRIPTION_PURCHASED (4)
Subscription: premium.personal.yearly
Token: emulator_sub_abc123...
Time: 2025-11-23 18:45:12
✓ Acknowledged
```

## Project Structure

```
dotnet/
├── README.md                    # This file
├── IapEmulatorDemo.csproj       # .NET project file
└── Program.cs                   # Complete demo code (~280 lines)
```

Everything is in one file (`Program.cs`) for simplicity and readability.

## Code Overview

The demo is organized into clear sections:

### API Demo (`RunApiDemo()`)

Demonstrates HTTP API operations:
1. Creating a subscription
2. Querying subscription details
3. Time manipulation (advance time)
4. Payment failure simulation
5. Grace period handling
6. Payment recovery
7. Subscription cancellation

### RTDN Listener Demo (`RunRtdnListenerDemo()`)

Demonstrates Pub/Sub event listening:
- Connects to Google Cloud Pub/Sub emulator
- Subscribes to RTDN topic
- Parses and displays subscription lifecycle events
- Acknowledges messages

### Data Models

Simple C# models for RTDN messages:
- `DeveloperNotification` - Top-level RTDN message
- `SubscriptionNotification` - Subscription event details

## Testing Scenarios

### Test Subscription Lifecycle

```bash
# 1. Create subscription
curl -X POST http://localhost:8080/emulator/subscriptions \
  -H "Content-Type: application/json" \
  -d '{
    "package_name": "com.example.app",
    "subscription_id": "premium.personal.yearly",
    "user_id": "user-001"
  }'

# Save the token from response
TOKEN="emulator_sub_..."

# 2. Fast-forward 366 days (trial + first year)
curl -X POST http://localhost:8080/emulator/time/advance \
  -H "Content-Type: application/json" \
  -d '{"days": 366}'

# Events received: SUBSCRIPTION_PURCHASED, then SUBSCRIPTION_RENEWED

# 3. Simulate payment failure
curl -X POST http://localhost:8080/emulator/subscriptions/${TOKEN}/payment-failed

# Event received: SUBSCRIPTION_IN_GRACE_PERIOD

# 4. Recover payment
curl -X POST http://localhost:8080/emulator/subscriptions/${TOKEN}/payment-recovered

# Event received: SUBSCRIPTION_RECOVERED

# 5. Cancel subscription
curl -X POST http://localhost:8080/emulator/subscriptions/${TOKEN}/cancel \
  -H "Content-Type: application/json" \
  -d '{"immediate": false}'

# Event received: SUBSCRIPTION_CANCELED
```

### Test Pause/Resume

```bash
# Pause subscription
curl -X POST http://localhost:8080/emulator/subscriptions/${TOKEN}/pause

# Event: SUBSCRIPTION_PAUSED

# Resume subscription
curl -X POST http://localhost:8080/emulator/subscriptions/${TOKEN}/resume

# Event: SUBSCRIPTION_RESTARTED
```

## Dependencies

The example uses only one NuGet package:

- **Google.Cloud.PubSub.V1** (3.15.0) - Official Google Cloud Pub/Sub client

Uses System.Text.Json (built into .NET) for JSON parsing - no additional dependencies needed!

## RTDN Event Types

| Event Type | Code | Description |
|------------|------|-------------|
| SUBSCRIPTION_RECOVERED | 1 | Payment recovered from grace period |
| SUBSCRIPTION_RENEWED | 2 | Subscription auto-renewed |
| SUBSCRIPTION_CANCELED | 3 | Subscription canceled (deferred) |
| SUBSCRIPTION_PURCHASED | 4 | New subscription created |
| SUBSCRIPTION_ON_HOLD | 5 | Grace period expired, on hold |
| SUBSCRIPTION_IN_GRACE_PERIOD | 6 | Payment failed, in grace period |
| SUBSCRIPTION_RESTARTED | 7 | Subscription resumed from pause |
| SUBSCRIPTION_DEFERRED | 9 | Subscription renewal deferred |
| SUBSCRIPTION_PAUSED | 10 | Subscription paused by user |
| SUBSCRIPTION_REVOKED | 12 | Subscription revoked immediately |
| SUBSCRIPTION_EXPIRED | 13 | Subscription expired |

## Adapting for Production

This demo uses the **real Google Cloud Pub/Sub SDK**, so the code is production-ready. To use in production:

### 1. Update Configuration

Change these constants in `Program.cs`:

```csharp
// Development
private const string EmulatorBaseUrl = "http://localhost:8080";
private const string PubSubProjectId = "emulator-project";

// Production
private const string EmulatorBaseUrl = "https://androidpublisher.googleapis.com";
private const string PubSubProjectId = "your-gcp-project-id";
```

### 2. Set Up Authentication

```bash
# Set environment variable pointing to your service account key
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

### 3. Remove Emulator Host

```csharp
// Remove this line for production:
Environment.SetEnvironmentVariable("PUBSUB_EMULATOR_HOST", "localhost:8085");
```

The Pub/Sub client will automatically connect to production Google Cloud.

## Troubleshooting

### Can't connect to Pub/Sub emulator

**Check if emulator is running:**
```bash
docker ps | grep pubsub
```

**Verify environment variable:**
```bash
echo $PUBSUB_EMULATOR_HOST  # Should show: localhost:8085
```

### No RTDN events received

**Make sure the listener is running with PUBSUB_EMULATOR_HOST set:**
```bash
PUBSUB_EMULATOR_HOST=localhost:8085 dotnet run listen
```

**Verify subscription exists:**
```bash
export PUBSUB_EMULATOR_HOST=localhost:8085
python ../tests/manual/check_pubsub.py
```

### API calls failing

**Verify IAP emulator is running:**
```bash
curl http://localhost:8080/health
```

**Check Swagger docs:**
Open http://localhost:8080/docs in your browser

## Next Steps

- Explore the [Configuration Documentation](../../docs/configuration.md)
- Learn about [Event Dispatcher](../../docs/event_dispatcher.md)
- Try the [Python examples](../) for more advanced scenarios
- Read the [API Documentation](http://localhost:8080/docs) (when emulator is running)

## Benefits of This Approach

✅ **Simple and readable** - Everything in one file
✅ **Real Google SDKs** - No mocks, production-ready code
✅ **Fast testing** - Test all subscription scenarios locally
✅ **No GCP account needed** - Full development workflow offline
✅ **Easy debugging** - Step through subscription lifecycle events
✅ **CI/CD friendly** - Run integration tests in pipelines
