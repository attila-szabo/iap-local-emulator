#!/usr/bin/env bash
# Convenience launcher for the Google Play IAP emulator.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export PUBSUB_EMULATOR_HOST="${PUBSUB_EMULATOR_HOST:-localhost:8085}"
export PUBSUB_PROJECT_ID="${PUBSUB_PROJECT_ID:-emulator-project}"
export PUBSUB_TOPIC_NAME="${PUBSUB_TOPIC_NAME:-google-play-rtdn}"
export CONFIG_PATH="${CONFIG_PATH:-./config/products.yaml}"

exec python -m uvicorn iap_emulator.main:app --host 0.0.0.0 --port 8081 --reload
