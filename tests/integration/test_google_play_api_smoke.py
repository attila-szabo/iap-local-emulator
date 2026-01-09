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


def test_acknowledge_subscription_success(client, subscription_engine):
    """Test POST acknowledge subscription - happy path."""
    # Create a test subscription
    subscription = subscription_engine.create_subscription(
        subscription_id="premium.personal.yearly",
        package_name="com.example.secureapp",
        user_id="test-user-999",
    )

    # Verify initial state
    assert subscription.acknowledgement_state == 0  # NOT_ACKNOWLEDGED

    # Acknowledge via API
    response = client.post(
        f"/androidpublisher/v3/applications/com.example.secureapp/purchases/subscriptions/premium.personal.yearly/tokens/{subscription.token}:acknowledge"
    )

    # Verify response
    assert response.status_code == 204  # No Content
    assert response.text == ""

    # Verify subscription was acknowledged
    updated_subscription = subscription_engine.get_subscription(subscription.token)
    assert updated_subscription.acknowledgement_state == 1  # ACKNOWLEDGED


def test_acknowledge_subscription_idempotent(client, subscription_engine):
    """Test that acknowledging a subscription multiple times is safe (idempotent)."""
    # Create a test subscription
    subscription = subscription_engine.create_subscription(
        subscription_id="premium.personal.yearly",
        package_name="com.example.secureapp",
        user_id="test-user-idempotent",
    )

    # Acknowledge first time
    response1 = client.post(
        f"/androidpublisher/v3/applications/com.example.secureapp/purchases/subscriptions/premium.personal.yearly/tokens/{subscription.token}:acknowledge"
    )
    assert response1.status_code == 204

    # Acknowledge second time (should still succeed)
    response2 = client.post(
        f"/androidpublisher/v3/applications/com.example.secureapp/purchases/subscriptions/premium.personal.yearly/tokens/{subscription.token}:acknowledge"
    )
    assert response2.status_code == 204

    # Verify subscription is still acknowledged
    updated_subscription = subscription_engine.get_subscription(subscription.token)
    assert updated_subscription.acknowledgement_state == 1  # ACKNOWLEDGED


def test_acknowledge_subscription_not_found(client):
    """Test acknowledging a non-existent subscription returns 404."""
    response = client.post(
        "/androidpublisher/v3/applications/com.example.secureapp/purchases/subscriptions/premium.personal.yearly/tokens/nonexistent_token:acknowledge"
    )

    assert response.status_code == 404
    data = response.json()
    assert data["detail"]["error"]["code"] == 404
    assert data["detail"]["error"]["status"] == "NOT_FOUND"
    assert "not found" in data["detail"]["error"]["message"].lower()


def test_acknowledge_subscription_package_mismatch(client, subscription_engine):
    """Test acknowledging with wrong package name returns 404."""
    # Create a test subscription
    subscription = subscription_engine.create_subscription(
        subscription_id="premium.personal.yearly",
        package_name="com.example.secureapp",
        user_id="test-user-mismatch",
    )

    # Try to acknowledge with wrong package name
    response = client.post(
        f"/androidpublisher/v3/applications/com.wrong.package/purchases/subscriptions/premium.personal.yearly/tokens/{subscription.token}:acknowledge"
    )

    assert response.status_code == 404
    data = response.json()
    assert data["detail"]["error"]["code"] == 404
    assert "package" in data["detail"]["error"]["message"].lower()


def test_acknowledge_subscription_product_mismatch(client, subscription_engine):
    """Test acknowledging with wrong subscription ID returns 404."""
    # Create a test subscription
    subscription = subscription_engine.create_subscription(
        subscription_id="premium.personal.yearly",
        package_name="com.example.secureapp",
        user_id="test-user-product-mismatch",
    )

    # Try to acknowledge with wrong subscription ID
    response = client.post(
        f"/androidpublisher/v3/applications/com.example.secureapp/purchases/subscriptions/wrong.subscription.id/tokens/{subscription.token}:acknowledge"
    )

    assert response.status_code == 404
    data = response.json()
    assert data["detail"]["error"]["code"] == 404
    assert "product" in data["detail"]["error"]["message"].lower()


def test_get_subscription_returns_acknowledgement_state(client, subscription_engine):
    """Test that GET subscription returns the acknowledgement state."""
    # Create and acknowledge a subscription
    subscription = subscription_engine.create_subscription(
        subscription_id="premium.personal.yearly",
        package_name="com.example.secureapp",
        user_id="test-user-get-ack",
    )

    # Get subscription before acknowledgement
    response1 = client.get(
        f"/androidpublisher/v3/applications/com.example.secureapp/purchases/subscriptions/premium.personal.yearly/tokens/{subscription.token}"
    )
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["acknowledgementState"] == 0  # NOT_ACKNOWLEDGED

    # Acknowledge the subscription
    subscription_engine.acknowledge_subscription(subscription.token)

    # Get subscription after acknowledgement
    response2 = client.get(
        f"/androidpublisher/v3/applications/com.example.secureapp/purchases/subscriptions/premium.personal.yearly/tokens/{subscription.token}"
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["acknowledgementState"] == 1  # ACKNOWLEDGED


def test_refund_product_purchase_success(client, purchase_manager):
    """Test POST refund order for product purchase - happy path."""
    # Create a test purchase
    purchase = purchase_manager.create_purchase(
        product_id="premium.personal.yearly",
        package_name="com.example.secureapp",
        user_id="test-user-refund-product",
    )

    # Verify initial state
    assert purchase.purchase_state.value == 0  # PURCHASED

    # Refund via API
    response = client.post(
        f"/androidpublisher/v3/applications/com.example.secureapp/orders/{purchase.order_id}:refund"
    )

    # Verify response
    assert response.status_code == 204  # No Content
    assert response.text == ""

    # Verify purchase was refunded (state changed to CANCELED)
    updated_purchase = purchase_manager.get_purchase(purchase.token)
    assert updated_purchase.purchase_state.value == 1  # CANCELED


def test_refund_subscription_success(client, subscription_engine):
    """Test POST refund order for subscription - happy path."""
    from iap_emulator.models.subscription import SubscriptionState

    # Create a test subscription
    subscription = subscription_engine.create_subscription(
        subscription_id="premium.personal.yearly",
        package_name="com.example.secureapp",
        user_id="test-user-refund-subscription",
    )

    # Verify initial state
    assert subscription.state == SubscriptionState.ACTIVE

    # Refund via API
    response = client.post(
        f"/androidpublisher/v3/applications/com.example.secureapp/orders/{subscription.order_id}:refund"
    )

    # Verify response
    assert response.status_code == 204  # No Content
    assert response.text == ""

    # Verify subscription was refunded (revoked - state changed to EXPIRED)
    updated_subscription = subscription_engine.get_subscription(subscription.token)
    assert updated_subscription.state == SubscriptionState.EXPIRED


def test_refund_order_not_found(client):
    """Test refunding a non-existent order returns 404."""
    response = client.post(
        "/androidpublisher/v3/applications/com.example.secureapp/orders/nonexistent_order_id:refund"
    )

    assert response.status_code == 404
    data = response.json()
    assert data["detail"]["error"]["code"] == 404
    assert data["detail"]["error"]["status"] == "NOT_FOUND"
    assert "not found" in data["detail"]["error"]["message"].lower()


def test_refund_order_package_mismatch(client, purchase_manager):
    """Test refunding with wrong package name returns 404."""
    # Create a test purchase
    purchase = purchase_manager.create_purchase(
        product_id="premium.personal.yearly",
        package_name="com.example.secureapp",
        user_id="test-user-refund-mismatch",
    )

    # Try to refund with wrong package name
    response = client.post(
        f"/androidpublisher/v3/applications/com.wrong.package/orders/{purchase.order_id}:refund"
    )

    assert response.status_code == 404
    data = response.json()
    assert data["detail"]["error"]["code"] == 404
    assert "package" in data["detail"]["error"]["message"].lower()


def test_refund_order_with_revoke_parameter(client, subscription_engine):
    """Test refunding with revoke parameter (subscriptions)."""
    from iap_emulator.models.subscription import SubscriptionState

    # Create a test subscription
    subscription = subscription_engine.create_subscription(
        subscription_id="premium.personal.yearly",
        package_name="com.example.secureapp",
        user_id="test-user-refund-revoke",
    )

    # Refund via API with revoke=true
    response = client.post(
        f"/androidpublisher/v3/applications/com.example.secureapp/orders/{subscription.order_id}:refund?revoke=true"
    )

    # Verify response
    assert response.status_code == 204  # No Content

    # Verify subscription was revoked
    updated_subscription = subscription_engine.get_subscription(subscription.token)
    assert updated_subscription.state == SubscriptionState.EXPIRED
