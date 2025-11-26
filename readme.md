# Google Play IAP Emulator

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](docker-compose.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](pyproject.toml)

Local emulator for Google Play in-app purchases and subscriptions. Test IAP flows without cloud setup.

- Emulator for Google Play Android Publisher API v3
- Real-Time Developer Notifications via Pub/Sub
- Virtual time control - fast-forward months in seconds
- Works with official Google SDKs (.NET, Python)

## Why This Exists

Testing Google Play subscriptions requires cloud setup and authentication. This emulator runs everything locally in Docker with zero config.

## Quick Start

```bash
# Start emulator
docker-compose up

# Create subscription
curl -X POST http://localhost:8080/emulator/subscriptions \
  -H "Content-Type: application/json" \
  -d '{"subscription_id": "premium.personal.yearly", "user_id": "user-124", "package_name": "com.example.app"}'

# Fast-forward 1 year
curl -X POST http://localhost:8080/emulator/time/advance \
  -H "Content-Type: application/json" \
  -d '{"days": 365}'

# Your app receives SUBSCRIPTION_RENEWED event via Pub/Sub
```

**Point your app at localhost:**

```python
import os
from google.cloud import pubsub_v1

os.environ["PUBSUB_EMULATOR_HOST"] = "localhost:8085"
subscriber = pubsub_v1.SubscriberClient()
# ... rest of your code unchanged
```

**Query subscription details:**

```bash
curl http://localhost:8080/androidpublisher/v3/applications/com.example.app/purchases/subscriptions/premium.personal.yearly/tokens/{token}
```

## How It Works

```
Client App (real SDKs)
    │
    ├─→ HTTP :8080 ────→ IAP API Emulator
    │                        └─→ Publishes events
    │
    └─→ gRPC :8085 ────→ Pub/Sub Emulator
                             └─→ Delivers to Client App
```

## Examples

**[.NET Example](examples/dotnet/)** - Complete C# demo with subscription lifecycle and RTDN listener

```bash
cd examples/dotnet
dotnet run          # Run API demo
dotnet run listen   # Listen for RTDN events
```

## API Endpoints

**Google Play API (compatible):**

- `GET .../purchases/subscriptions/{subscriptionId}/tokens/{token}` - Get subscription
- `POST .../purchases/subscriptions/{subscriptionId}/tokens/{token}:cancel` - Cancel
- `POST .../purchases/subscriptions/{subscriptionId}/tokens/{token}:defer` - Defer
- `POST .../purchases/subscriptions/{subscriptionId}/tokens/{token}:revoke` - Revoke

**Control API (testing):**

- `POST /emulator/subscriptions` - Create subscription
- `POST /emulator/subscriptions/{token}/payment-failed` - Simulate payment failure
- `POST /emulator/subscriptions/{token}/payment-recovered` - Recover payment
- `POST /emulator/time/advance` - Fast-forward time
- `GET /emulator/debug/subscriptions` - List all subscriptions

See [`examples/dotnet/README.md`](examples/dotnet/README.md) for complete API reference.

## Configuration

Edit `config/products.yaml` to define your products and subscriptions:

```yaml
subscriptions:
  - id: "premium.personal.yearly"
    billing_period: "P1Y"
    price_micros: 29990000
    currency: "USD"
```

## Contributing

See **[CONTRIBUTING.md](contributing.md)** for build instructions, development setup, and testing.

## Limitations

- No authentication/security
- In-memory storage (no persistence layer)
- Simplified business logic to manage subscription events

## License

MIT - see [LICENSE](LICENSE)
