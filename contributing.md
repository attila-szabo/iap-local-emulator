# Contributing to Google IAP Emulator

Thanks for your interest in contributing! This guide will help you get started with development.

## Prerequisites

- Python 3.9 or higher
- Git
- Docker (for running Pub/Sub emulator)

## Quick Start

### 1. Clone and Setup

```bash
# Clone repository
git clone https://github.com/attila-szabo/iap-local-emulator.git
cd iap-local-emulator

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies (editable mode)
pip install -e ".[dev]"

# Alternatively
pip install poetry
poetry install
```

### 2. Start Pub/Sub Emulator

```bash
# In a separate terminal
docker run -p 8085:8085 \
  gcr.io/google.com/cloudsdktool/google-cloud-cli:emulators \
  gcloud beta emulators pubsub start --host-port=0.0.0.0:8085 --project=emulator-project
```

### 3. Initialize Pub/Sub Topic and Subscription

```bash
# Install gcloud CLI if needed, or use docker exec
docker exec -it <container-id> gcloud pubsub topics create google-play-rtdn --project=emulator-project
docker exec -it <container-id> gcloud pubsub subscriptions create google-play-rtdn-sub \
  --topic=google-play-rtdn --project=emulator-project
```

Or use docker-compose for automatic setup:

```bash
docker-compose up pubsub-emulator pubsub-init
```

### 4. Run Emulator from Source

```bash
# Set environment variables
export PUBSUB_EMULATOR_HOST=localhost:8085
export PUBSUB_PROJECT_ID=emulator-project
export PUBSUB_TOPIC_NAME=google-play-rtdn
export CONFIG_PATH=./config/products.yaml

# Run the application
python -m uvicorn iap_emulator.main:app --host 0.0.0.0 --port 8080 --reload
```

The emulator is now running at:

- IAP API: http://localhost:8080
- Pub/Sub: localhost:8085

### 5. Test It Works

```bash
# Create a subscription
curl -X POST http://localhost:8080/emulator/subscriptions \
  -H "Content-Type: application/json" \
  -d '{"subscriptionId": "premium.personal.yearly", "userId": "test-user"}'

# Advance time to trigger renewal
curl -X POST http://localhost:8080/emulator/time/advance \
  -H "Content-Type: application/json" \
  -d '{"days": 365}'
```

## Development Workflow

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=iap_emulator --cov-report=html

# Run specific test file
pytest tests/test_subscriptions.py

# Run with markers
pytest -m unit  # Only unit tests
pytest -m integration  # Only integration tests
```

### Code Quality

```bash
# Format code with black
black .

# Lint with ruff
ruff check .

# Type checking with mypy
mypy iap_emulator

# Run all checks
black . && ruff check . && mypy iap_emulator && pytest
```

### Using pyenv (Optional)

If you want to test multiple Python versions:

```bash
# Install pyenv
curl https://pyenv.run | bash

# Install Python versions
pyenv install 3.9.18
pyenv install 3.10.13
pyenv install 3.11.7
pyenv install 3.12.1

# Set local Python version
pyenv local 3.11.7

# Create virtual environment
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

## Development Tips

### Hot Reload

The `--reload` flag enables auto-restart when code changes:

```bash
uvicorn iap_emulator.main:app --reload
```

### Debug Logging

```bash
# Set log level
export LOG_LEVEL=DEBUG

# Run with debug output
python -m uvicorn iap_emulator.main:app --log-level debug
```

### VS Code Debug Configuration

Add to `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "iap_emulator.main:app",
        "--reload",
        "--host",
        "0.0.0.0",
        "--port",
        "8080"
      ],
      "env": {
        "PUBSUB_EMULATOR_HOST": "localhost:8085",
        "PUBSUB_PROJECT_ID": "emulator-project",
        "PUBSUB_TOPIC_NAME": "google-play-rtdn",
        "CONFIG_PATH": "./config/products.yaml"
      },
      "jinja": true
    }
  ]
}
```

### PyCharm/IntelliJ Debug Configuration

1. Run → Edit Configurations
2. Add new Python configuration
3. Script path: `/path/to/venv/bin/uvicorn`
4. Parameters: `iap_emulator.main:app --reload --host 0.0.0.0 --port 8080`
5. Environment variables:
   ```
   PUBSUB_EMULATOR_HOST=localhost:8085
   PUBSUB_PROJECT_ID=emulator-project
   PUBSUB_TOPIC_NAME=google-play-rtdn
   CONFIG_PATH=./config/products.yaml
   ```

## Making Changes

### Before Submitting a PR

1. **Format and lint**:

   ```bash
   black .
   ruff check . --fix
   ```

2. **Type check**:

   ```bash
   mypy iap_emulator
   ```

3. **Run tests**:

   ```bash
   pytest
   ```

4. **Test Docker build**:
   ```bash
   docker build -t iap-local-emulator:test .
   docker-compose up
   ```

### Commit Messages

Follow conventional commits:

```
feat: add support for subscription pausing
fix: correct grace period calculation
docs: update API reference for new endpoints
test: add integration tests for renewals
refactor: simplify subscription state machine
```

## Common Issues

### "Module not found" errors

```bash
# Reinstall in editable mode
pip install -e ".[dev]"
```

### Pub/Sub connection errors

```bash
# Verify emulator is running
curl http://localhost:8085

# Check environment variable
echo $PUBSUB_EMULATOR_HOST
```

### Port already in use

```bash
# Find process using port 8080
lsof -i :8080

# Kill process
kill -9 <PID>
```

## Getting Help

- Open an issue for bugs or feature requests
- Check existing issues before creating new ones
- Include error messages, logs, and reproduction steps

## Code of Conduct

Be respectful and constructive. This is an educational project for the community.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
