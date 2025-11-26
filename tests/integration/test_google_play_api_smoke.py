"""Smoke tests for Google Play API endpoints.

Quick validation tests to ensure basic functionality works.
"""

import pytest
from fastapi.testclient import TestClient

from iap_emulator.main import create_app
from iap_emulator.repositories.purchase_store import get_purchase_store
from iap_emulator.repositories.subscription_store import get_subscription_store
from iap_emulator.services.purchase_manager import PurchaseManager
from iap_emulator.services.subscription_engine import SubscriptionEngine


@pytest.fixture(autouse=True)
def reset_stores():
    """Clear all stores before and after each test."""
    purchase_store = get_purchase_store()
    subscription_store = get_subscription_store()

    purchase_store.clear()
    subscription_store.clear()

    yield

    purchase_store.clear()
    subscription_store.clear()


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def purchase_manager():
    """Get purchase manager instance."""
    return PurchaseManager()


@pytest.fixture
def subscription_engine():
    """Get subscription engine instance."""
    return SubscriptionEngine()


def test_get_product_purchase_success(client, purchase_manager):
    """Test GET product purchase - happy path."""
    # Create a test purchase (using existing subscription product as one-time purchase)
    purchase = purchase_manager.create_purchase(
        product_id="premium.personal.yearly",
        package_name="com.example.secureapp",
        user_id="test-user-123",
        developer_payload="test-payload",
    )

    # Query the purchase via API
    response = client.get(
        f"/androidpublisher/v3/applications/com.example.secureapp/purchases/products/premium.personal.yearly/tokens/{purchase.token}"
    )

    # Verify response
    assert response.status_code == 200
    data = response.json()

    assert data["kind"] == "androidpublisher#productPurchase"
    assert data["productId"] == "premium.personal.yearly"
    assert data["purchaseToken"] == purchase.token
    assert data["orderId"] == purchase.order_id
    assert data["purchaseState"] == 0  # PURCHASED
    assert data["consumptionState"] == 0  # NOT_CONSUMED
    assert data["acknowledgementState"] == 0  # NOT_ACKNOWLEDGED
    assert data["quantity"] == 1
    assert data["regionCode"] == "US"
    assert data["developerPayload"] == "test-payload"


def test_get_subscription_purchase_success(client, subscription_engine):
    """Test GET subscription purchase - happy path."""
    # Create a test subscription
    subscription = subscription_engine.create_subscription(
        subscription_id="premium.personal.yearly",
        package_name="com.example.secureapp",
        user_id="test-user-456",
    )

    # Query the subscription via API
    response = client.get(
        f"/androidpublisher/v3/applications/com.example.secureapp/purchases/subscriptions/premium.personal.yearly/tokens/{subscription.token}"
    )

    # Verify response
    assert response.status_code == 200
    data = response.json()

    assert data["kind"] == "androidpublisher#subscriptionPurchase"
    assert data["purchaseToken"] == subscription.token
    assert data["orderId"] == subscription.order_id
    assert data["autoRenewing"] is True  # ACTIVE and auto-renewing
    assert data["priceCurrencyCode"] == "USD"
    assert data["countryCode"] == "US"
    assert data["acknowledgementState"] == 0


def test_acknowledge_product_success(client, purchase_manager):
    """Test POST acknowledge product - happy path."""
    # Create a test purchase
    purchase = purchase_manager.create_purchase(
        product_id="premium.personal.yearly",
        package_name="com.example.secureapp",
        user_id="test-user-789",
    )

    # Verify initial state
    assert purchase.acknowledgement_state.value == 0  # NOT_ACKNOWLEDGED

    # Acknowledge via API
    response = client.post(
        f"/androidpublisher/v3/applications/com.example.secureapp/purchases/products/premium.personal.yearly/tokens/{purchase.token}:acknowledge"
    )

    # Verify response
    assert response.status_code == 204  # No Content
    assert response.text == ""

    # Verify purchase was acknowledged
    updated_purchase = purchase_manager.get_purchase(purchase.token)
    assert updated_purchase.acknowledgement_state.value == 1  # ACKNOWLEDGED
