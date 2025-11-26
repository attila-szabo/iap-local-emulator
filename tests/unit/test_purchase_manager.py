"""Tests for Purchase Manager."""

import time
from unittest.mock import MagicMock

import pytest

from iap_emulator.models.product import ProductDefinition
from iap_emulator.models.purchase import (
    AcknowledgementState,
    ConsumptionState,
    ProductPurchaseRecord,
    PurchaseState,
)
from iap_emulator.repositories.product_repository import (
    ProductNotFoundError,
    ProductRepository,
)
from iap_emulator.repositories.purchase_store import (
    PurchaseNotFoundError,
    PurchaseStore,
)
from iap_emulator.services.purchase_manager import (
    PurchaseAlreadyAcknowledgedError,
    PurchaseAlreadyConsumedError,
    PurchaseManager,
)


@pytest.fixture
def purchase_store():
    """Create a fresh purchase store for each test."""
    return PurchaseStore()


@pytest.fixture
def product_repository():
    """Create a product repository with test products."""
    # Create mock repository
    repo = MagicMock(spec=ProductRepository)

    # Define test products
    test_product = ProductDefinition(
        id="coins_1000",
        type="consumable",
        title="1000 Coins",
        description="Pack of 1000 coins",
        price_micros=4_990_000,
        currency="USD",
    )

    premium_product = ProductDefinition(
        id="premium_unlock",
        type="non_consumable",
        title="Premium Unlock",
        description="Unlock premium features",
        price_micros=9_990_000,
        currency="USD",
    )

    # Configure mock
    def get_by_id_mock(product_id):
        if product_id == "coins_1000":
            return test_product
        elif product_id == "premium_unlock":
            return premium_product
        else:
            raise ProductNotFoundError(f"Product not found: {product_id}")

    repo.get_by_id.side_effect = get_by_id_mock

    return repo


@pytest.fixture
def purchase_manager(purchase_store, product_repository):
    """Create purchase manager with test dependencies."""
    return PurchaseManager(
        purchase_store=purchase_store,
        product_repository=product_repository,
    )


class TestPurchaseCreation:
    """Test purchase creation."""

    def test_create_purchase_success(self, purchase_manager):
        """Test creating a purchase successfully."""
        purchase = purchase_manager.create_purchase(
            product_id="coins_1000",
            package_name="com.example.game",
            user_id="user-123",
        )

        assert purchase is not None
        assert purchase.product_id == "coins_1000"
        assert purchase.package_name == "com.example.game"
        assert purchase.user_id == "user-123"
        assert purchase.purchase_state == PurchaseState.PURCHASED
        assert purchase.consumption_state == ConsumptionState.NOT_CONSUMED
        assert purchase.acknowledgement_state == AcknowledgementState.NOT_ACKNOWLEDGED

    def test_create_purchase_generates_token(self, purchase_manager):
        """Test that purchase creation generates a valid token."""
        purchase = purchase_manager.create_purchase(
            product_id="coins_1000",
            package_name="com.example.game",
            user_id="user-123",
        )

        assert purchase.token is not None
        assert "_purchase_" in purchase.token
        assert len(purchase.token) > 20

    def test_create_purchase_generates_order_id(self, purchase_manager):
        """Test that purchase creation generates a valid order ID."""
        purchase = purchase_manager.create_purchase(
            product_id="coins_1000",
            package_name="com.example.game",
            user_id="user-123",
        )

        assert purchase.order_id is not None
        assert purchase.order_id.startswith("GPA.")
        assert len(purchase.order_id) > 10

    def test_create_purchase_sets_timestamp(self, purchase_manager):
        """Test that purchase creation sets current timestamp."""
        before = int(time.time() * 1000)
        purchase = purchase_manager.create_purchase(
            product_id="coins_1000",
            package_name="com.example.game",
            user_id="user-123",
        )
        after = int(time.time() * 1000)

        assert before <= purchase.purchase_time_millis <= after

    def test_create_purchase_parses_price(self, purchase_manager):
        """Test that purchase creation parses price correctly."""
        purchase = purchase_manager.create_purchase(
            product_id="coins_1000",
            package_name="com.example.game",
            user_id="user-123",
        )

        # $4.99 = 4990000 micros
        assert purchase.price_amount_micros == 4_990_000
        assert purchase.price_currency_code == "USD"

    def test_create_purchase_with_developer_payload(self, purchase_manager):
        """Test creating purchase with developer payload."""
        purchase = purchase_manager.create_purchase(
            product_id="coins_1000",
            package_name="com.example.game",
            user_id="user-123",
            developer_payload="custom_data_123",
        )

        assert purchase.developer_payload == "custom_data_123"

    def test_create_purchase_with_custom_prefix(self, purchase_manager):
        """Test creating purchase with custom token prefix."""
        purchase = purchase_manager.create_purchase(
            product_id="coins_1000",
            package_name="com.example.game",
            user_id="user-123",
            token_prefix="custom",
        )

        assert purchase.token.startswith("custom_purchase_")

    def test_create_purchase_invalid_product(self, purchase_manager):
        """Test creating purchase with invalid product ID."""
        with pytest.raises(ProductNotFoundError):
            purchase_manager.create_purchase(
                product_id="invalid_product",
                package_name="com.example.game",
                user_id="user-123",
            )

    def test_create_purchase_stores_in_store(
        self, purchase_manager, purchase_store
    ):
        """Test that created purchase is stored in purchase store."""
        purchase = purchase_manager.create_purchase(
            product_id="coins_1000",
            package_name="com.example.game",
            user_id="user-123",
        )

        # Should be able to retrieve from store
        stored_purchase = purchase_store.get_by_token(purchase.token)
        assert stored_purchase == purchase


class TestPurchaseRetrieval:
    """Test purchase retrieval."""

    def test_get_purchase_success(self, purchase_manager):
        """Test getting a purchase by token."""
        # Create purchase
        purchase = purchase_manager.create_purchase(
            product_id="coins_1000",
            package_name="com.example.game",
            user_id="user-123",
        )

        # Retrieve purchase
        retrieved = purchase_manager.get_purchase(purchase.token)
        assert retrieved == purchase

    def test_get_purchase_not_found(self, purchase_manager):
        """Test getting purchase with invalid token raises exception."""
        with pytest.raises(PurchaseNotFoundError):
            purchase_manager.get_purchase("invalid_token")

    def test_find_purchase_success(self, purchase_manager):
        """Test finding a purchase by token."""
        # Create purchase
        purchase = purchase_manager.create_purchase(
            product_id="coins_1000",
            package_name="com.example.game",
            user_id="user-123",
        )

        # Find purchase
        found = purchase_manager.find_purchase(purchase.token)
        assert found == purchase

    def test_find_purchase_not_found(self, purchase_manager):
        """Test finding purchase with invalid token returns None."""
        found = purchase_manager.find_purchase("invalid_token")
        assert found is None


class TestPurchaseValidation:
    """Test purchase validation."""

    def test_validate_purchase_valid(self, purchase_manager):
        """Test validating a valid purchase token."""
        purchase = purchase_manager.create_purchase(
            product_id="coins_1000",
            package_name="com.example.game",
            user_id="user-123",
        )

        is_valid = purchase_manager.validate_purchase(purchase.token)
        assert is_valid is True

    def test_validate_purchase_invalid_token_format(self, purchase_manager):
        """Test validating invalid token format."""
        is_valid = purchase_manager.validate_purchase("invalid_token")
        assert is_valid is False

    def test_validate_purchase_not_found(self, purchase_manager):
        """Test validating token that doesn't exist."""
        # Valid format but doesn't exist
        fake_token = "emulator_purchase_abc123def456_1234567890123"
        is_valid = purchase_manager.validate_purchase(fake_token)
        assert is_valid is False

    def test_validate_purchase_canceled(self, purchase_manager):
        """Test validating a canceled purchase."""
        purchase = purchase_manager.create_purchase(
            product_id="coins_1000",
            package_name="com.example.game",
            user_id="user-123",
        )

        # Cancel purchase
        purchase_manager.cancel_purchase(purchase.token)

        # Should not be valid anymore
        is_valid = purchase_manager.validate_purchase(purchase.token)
        assert is_valid is False


class TestPurchaseAcknowledgment:
    """Test purchase acknowledgment."""

    def test_acknowledge_purchase_success(self, purchase_manager):
        """Test acknowledging a purchase."""
        purchase = purchase_manager.create_purchase(
            product_id="coins_1000",
            package_name="com.example.game",
            user_id="user-123",
        )

        # Acknowledge
        acknowledged = purchase_manager.acknowledge_purchase(purchase.token)

        assert acknowledged.acknowledgement_state == AcknowledgementState.ACKNOWLEDGED

    def test_acknowledge_purchase_already_acknowledged_raises(
        self, purchase_manager
    ):
        """Test acknowledging already acknowledged purchase raises error."""
        purchase = purchase_manager.create_purchase(
            product_id="coins_1000",
            package_name="com.example.game",
            user_id="user-123",
        )

        # Acknowledge first time
        purchase_manager.acknowledge_purchase(purchase.token)

        # Second acknowledge should raise
        with pytest.raises(PurchaseAlreadyAcknowledgedError):
            purchase_manager.acknowledge_purchase(purchase.token)

    def test_acknowledge_purchase_already_acknowledged_no_raise(
        self, purchase_manager
    ):
        """Test acknowledging already acknowledged purchase doesn't raise if flag is False."""
        purchase = purchase_manager.create_purchase(
            product_id="coins_1000",
            package_name="com.example.game",
            user_id="user-123",
        )

        # Acknowledge first time
        purchase_manager.acknowledge_purchase(purchase.token)

        # Second acknowledge should not raise
        acknowledged = purchase_manager.acknowledge_purchase(
            purchase.token, raise_if_already_acknowledged=False
        )
        assert acknowledged.acknowledgement_state == AcknowledgementState.ACKNOWLEDGED

    def test_acknowledge_purchase_not_found(self, purchase_manager):
        """Test acknowledging non-existent purchase raises error."""
        with pytest.raises(PurchaseNotFoundError):
            purchase_manager.acknowledge_purchase("invalid_token")


class TestPurchaseConsumption:
    """Test purchase consumption."""

    def test_consume_purchase_success(self, purchase_manager):
        """Test consuming a purchase."""
        purchase = purchase_manager.create_purchase(
            product_id="coins_1000",
            package_name="com.example.game",
            user_id="user-123",
        )

        # Consume
        consumed = purchase_manager.consume_purchase(purchase.token)

        assert consumed.consumption_state == ConsumptionState.CONSUMED

    def test_consume_purchase_already_consumed_raises(self, purchase_manager):
        """Test consuming already consumed purchase raises error."""
        purchase = purchase_manager.create_purchase(
            product_id="coins_1000",
            package_name="com.example.game",
            user_id="user-123",
        )

        # Consume first time
        purchase_manager.consume_purchase(purchase.token)

        # Second consume should raise
        with pytest.raises(PurchaseAlreadyConsumedError):
            purchase_manager.consume_purchase(purchase.token)

    def test_consume_purchase_already_consumed_no_raise(self, purchase_manager):
        """Test consuming already consumed purchase doesn't raise if flag is False."""
        purchase = purchase_manager.create_purchase(
            product_id="coins_1000",
            package_name="com.example.game",
            user_id="user-123",
        )

        # Consume first time
        purchase_manager.consume_purchase(purchase.token)

        # Second consume should not raise
        consumed = purchase_manager.consume_purchase(
            purchase.token, raise_if_already_consumed=False
        )
        assert consumed.consumption_state == ConsumptionState.CONSUMED

    def test_consume_purchase_not_found(self, purchase_manager):
        """Test consuming non-existent purchase raises error."""
        with pytest.raises(PurchaseNotFoundError):
            purchase_manager.consume_purchase("invalid_token")


class TestPurchaseCancellation:
    """Test purchase cancellation."""

    def test_cancel_purchase_success(self, purchase_manager):
        """Test canceling a purchase."""
        purchase = purchase_manager.create_purchase(
            product_id="coins_1000",
            package_name="com.example.game",
            user_id="user-123",
        )

        # Cancel
        canceled = purchase_manager.cancel_purchase(purchase.token)

        assert canceled.purchase_state == PurchaseState.CANCELED

    def test_cancel_purchase_with_reason(self, purchase_manager):
        """Test canceling purchase with reason."""
        purchase = purchase_manager.create_purchase(
            product_id="coins_1000",
            package_name="com.example.game",
            user_id="user-123",
        )

        # Cancel with reason
        canceled = purchase_manager.cancel_purchase(
            purchase.token, reason="user_requested"
        )

        assert canceled.purchase_state == PurchaseState.CANCELED

    def test_cancel_purchase_not_found(self, purchase_manager):
        """Test canceling non-existent purchase raises error."""
        with pytest.raises(PurchaseNotFoundError):
            purchase_manager.cancel_purchase("invalid_token")


class TestPurchaseQueries:
    """Test purchase query methods."""

    def test_get_user_purchases(self, purchase_manager):
        """Test getting all purchases for a user."""
        # Create multiple purchases for user
        purchase1 = purchase_manager.create_purchase(
            product_id="coins_1000",
            package_name="com.example.game",
            user_id="user-123",
        )
        purchase2 = purchase_manager.create_purchase(
            product_id="premium_unlock",
            package_name="com.example.game",
            user_id="user-123",
        )

        # Create purchase for different user
        purchase_manager.create_purchase(
            product_id="coins_1000",
            package_name="com.example.game",
            user_id="user-456",
        )

        # Get purchases for user-123
        user_purchases = purchase_manager.get_user_purchases("user-123")

        assert len(user_purchases) == 2
        assert purchase1 in user_purchases
        assert purchase2 in user_purchases

    def test_get_package_purchases(self, purchase_manager):
        """Test getting all purchases for a package."""
        # Create purchases for package
        purchase1 = purchase_manager.create_purchase(
            product_id="coins_1000",
            package_name="com.example.game",
            user_id="user-123",
        )
        purchase2 = purchase_manager.create_purchase(
            product_id="premium_unlock",
            package_name="com.example.game",
            user_id="user-456",
        )

        # Create purchase for different package
        purchase_manager.create_purchase(
            product_id="coins_1000",
            package_name="com.other.app",
            user_id="user-123",
        )

        # Get purchases for com.example.game
        package_purchases = purchase_manager.get_package_purchases("com.example.game")

        assert len(package_purchases) == 2
        assert purchase1 in package_purchases
        assert purchase2 in package_purchases


class TestPurchaseLifecycle:
    """Test complete purchase lifecycle."""

    def test_full_purchase_lifecycle(self, purchase_manager):
        """Test full purchase lifecycle: create -> acknowledge -> consume."""
        # Create purchase
        purchase = purchase_manager.create_purchase(
            product_id="coins_1000",
            package_name="com.example.game",
            user_id="user-123",
        )

        assert purchase.purchase_state == PurchaseState.PURCHASED
        assert purchase.acknowledgement_state == AcknowledgementState.NOT_ACKNOWLEDGED
        assert purchase.consumption_state == ConsumptionState.NOT_CONSUMED

        # Acknowledge purchase
        purchase_manager.acknowledge_purchase(purchase.token)
        purchase = purchase_manager.get_purchase(purchase.token)
        assert purchase.acknowledgement_state == AcknowledgementState.ACKNOWLEDGED

        # Consume purchase
        purchase_manager.consume_purchase(purchase.token)
        purchase = purchase_manager.get_purchase(purchase.token)
        assert purchase.consumption_state == ConsumptionState.CONSUMED
