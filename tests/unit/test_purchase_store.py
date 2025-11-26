"""Tests for PurchaseStore - in-memory purchase storage."""

import time
from threading import Thread

import pytest

from iap_emulator.models.purchase import (
    AcknowledgementState,
    ConsumptionState,
    ProductPurchaseRecord,
    PurchaseState,
)
from iap_emulator.repositories.purchase_store import (
    PurchaseNotFoundError,
    PurchaseStore,
    get_purchase_store,
    reset_purchase_store,
)


@pytest.fixture
def store():
    """Create a fresh PurchaseStore instance for testing."""
    store = PurchaseStore()
    yield store
    store.clear()


@pytest.fixture
def sample_purchase():
    """Create a sample purchase for testing."""
    now_millis = int(time.time() * 1000)
    return ProductPurchaseRecord(
        token="emulator_test_token_123",
        product_id="coins_1000",
        package_name="com.example.game",
        user_id="user-123",
        purchase_time_millis=now_millis,
        order_id="GPA.1234-5678-9012",
        price_amount_micros=4990000,
    )


@pytest.fixture
def sample_purchase_2():
    """Create a second sample purchase for testing."""
    now_millis = int(time.time() * 1000)
    return ProductPurchaseRecord(
        token="emulator_test_token_456",
        product_id="premium_unlock",
        package_name="com.example.game",
        user_id="user-456",
        purchase_time_millis=now_millis,
        order_id="GPA.9876-5432-1098",
        price_amount_micros=9990000,
    )


class TestPurchaseStoreBasics:
    """Test basic store functionality."""

    def test_store_initializes_empty(self, store):
        """Test that new store is empty."""
        assert store.count() == 0
        assert len(store) == 0
        assert store.get_all() == []

    def test_add_purchase(self, store, sample_purchase):
        """Test adding a purchase to the store."""
        store.add(sample_purchase)
        assert store.count() == 1
        assert store.exists(sample_purchase.token)

    def test_add_duplicate_token_raises_error(self, store, sample_purchase):
        """Test that adding duplicate token raises ValueError."""
        store.add(sample_purchase)
        with pytest.raises(ValueError) as exc_info:
            store.add(sample_purchase)
        assert "already exists" in str(exc_info.value)

    def test_repr(self, store, sample_purchase):
        """Test string representation."""
        assert "PurchaseStore" in repr(store)
        assert "purchases=0" in repr(store)

        store.add(sample_purchase)
        assert "purchases=1" in repr(store)


class TestPurchaseLookup:
    """Test purchase lookup methods."""

    def test_get_by_token_success(self, store, sample_purchase):
        """Test successful lookup by token."""
        store.add(sample_purchase)
        retrieved = store.get_by_token(sample_purchase.token)

        assert retrieved.token == sample_purchase.token
        assert retrieved.product_id == sample_purchase.product_id
        assert retrieved.user_id == sample_purchase.user_id

    def test_get_by_token_not_found_raises_error(self, store):
        """Test that get_by_token raises error when not found."""
        with pytest.raises(PurchaseNotFoundError) as exc_info:
            store.get_by_token("non_existent_token")
        assert "not found" in str(exc_info.value).lower()

    def test_find_by_token_returns_none_when_not_found(self, store):
        """Test that find_by_token returns None when not found."""
        result = store.find_by_token("non_existent_token")
        assert result is None

    def test_find_by_token_success(self, store, sample_purchase):
        """Test successful find_by_token."""
        store.add(sample_purchase)
        result = store.find_by_token(sample_purchase.token)

        assert result is not None
        assert result.token == sample_purchase.token

    def test_exists_method(self, store, sample_purchase):
        """Test the exists() method."""
        assert store.exists(sample_purchase.token) is False

        store.add(sample_purchase)
        assert store.exists(sample_purchase.token) is True

    def test_contains_operator(self, store, sample_purchase):
        """Test the 'in' operator (contains)."""
        assert sample_purchase.token not in store

        store.add(sample_purchase)
        assert sample_purchase.token in store


class TestPurchaseQueryMethods:
    """Test query methods for filtering purchases."""

    def test_get_by_user(self, store, sample_purchase, sample_purchase_2):
        """Test getting purchases by user_id."""
        store.add(sample_purchase)
        store.add(sample_purchase_2)

        user_123_purchases = store.get_by_user("user-123")
        assert len(user_123_purchases) == 1
        assert user_123_purchases[0].user_id == "user-123"

        user_456_purchases = store.get_by_user("user-456")
        assert len(user_456_purchases) == 1
        assert user_456_purchases[0].user_id == "user-456"

    def test_get_by_user_no_results(self, store, sample_purchase):
        """Test get_by_user with no matching purchases."""
        store.add(sample_purchase)
        result = store.get_by_user("non_existent_user")
        assert result == []

    def test_get_by_package(self, store, sample_purchase, sample_purchase_2):
        """Test getting purchases by package_name."""
        store.add(sample_purchase)
        store.add(sample_purchase_2)

        package_purchases = store.get_by_package("com.example.game")
        assert len(package_purchases) == 2
        assert all(p.package_name == "com.example.game" for p in package_purchases)

    def test_get_by_product_id(self, store, sample_purchase):
        """Test getting purchases by product_id."""
        store.add(sample_purchase)

        product_purchases = store.get_by_product_id("coins_1000")
        assert len(product_purchases) == 1
        assert product_purchases[0].product_id == "coins_1000"

    def test_get_user_purchase(self, store, sample_purchase):
        """Test getting a specific user's purchase."""
        store.add(sample_purchase)

        result = store.get_user_purchase(
            user_id="user-123",
            product_id="coins_1000",
            package_name="com.example.game",
        )

        assert result is not None
        assert result.user_id == "user-123"
        assert result.product_id == "coins_1000"

    def test_get_user_purchase_not_found(self, store, sample_purchase):
        """Test get_user_purchase when not found."""
        store.add(sample_purchase)

        result = store.get_user_purchase(
            user_id="user-999",
            product_id="coins_1000",
            package_name="com.example.game",
        )

        assert result is None


class TestPurchaseModification:
    """Test purchase update and delete operations."""

    def test_update_purchase(self, store, sample_purchase):
        """Test updating an existing purchase."""
        store.add(sample_purchase)

        # Modify the purchase
        sample_purchase.consumption_state = ConsumptionState.CONSUMED
        store.update(sample_purchase)

        # Verify update
        retrieved = store.get_by_token(sample_purchase.token)
        assert retrieved.consumption_state == ConsumptionState.CONSUMED

    def test_update_nonexistent_purchase_raises_error(self, store, sample_purchase):
        """Test that updating nonexistent purchase raises error."""
        with pytest.raises(PurchaseNotFoundError):
            store.update(sample_purchase)

    def test_upsert_new_purchase(self, store, sample_purchase):
        """Test upsert with new purchase (insert)."""
        store.upsert(sample_purchase)
        assert store.exists(sample_purchase.token)

    def test_upsert_existing_purchase(self, store, sample_purchase):
        """Test upsert with existing purchase (update)."""
        store.add(sample_purchase)
        assert store.count() == 1

        # Modify and upsert
        sample_purchase.consumption_state = ConsumptionState.CONSUMED
        store.upsert(sample_purchase)

        assert store.count() == 1
        retrieved = store.get_by_token(sample_purchase.token)
        assert retrieved.consumption_state == ConsumptionState.CONSUMED

    def test_remove_purchase(self, store, sample_purchase):
        """Test removing a purchase."""
        store.add(sample_purchase)
        assert store.exists(sample_purchase.token)

        store.remove(sample_purchase.token)
        assert not store.exists(sample_purchase.token)

    def test_remove_nonexistent_purchase_raises_error(self, store):
        """Test that removing nonexistent purchase raises error."""
        with pytest.raises(PurchaseNotFoundError):
            store.remove("non_existent_token")

    def test_delete_by_token_success(self, store, sample_purchase):
        """Test delete_by_token returns True on success."""
        store.add(sample_purchase)
        result = store.delete_by_token(sample_purchase.token)

        assert result is True
        assert not store.exists(sample_purchase.token)

    def test_delete_by_token_not_found(self, store):
        """Test delete_by_token returns False when not found."""
        result = store.delete_by_token("non_existent_token")
        assert result is False


class TestBulkOperations:
    """Test bulk operations on store."""

    def test_get_all(self, store, sample_purchase, sample_purchase_2):
        """Test getting all purchases."""
        store.add(sample_purchase)
        store.add(sample_purchase_2)

        all_purchases = store.get_all()
        assert len(all_purchases) == 2
        tokens = [p.token for p in all_purchases]
        assert sample_purchase.token in tokens
        assert sample_purchase_2.token in tokens

    def test_get_all_tokens(self, store, sample_purchase, sample_purchase_2):
        """Test getting all purchase tokens."""
        store.add(sample_purchase)
        store.add(sample_purchase_2)

        tokens = store.get_all_tokens()
        assert len(tokens) == 2
        assert sample_purchase.token in tokens
        assert sample_purchase_2.token in tokens

    def test_clear(self, store, sample_purchase, sample_purchase_2):
        """Test clearing all purchases."""
        store.add(sample_purchase)
        store.add(sample_purchase_2)
        assert store.count() == 2

        store.clear()
        assert store.count() == 0
        assert store.get_all() == []


class TestStatistics:
    """Test statistics and counting methods."""

    def test_count(self, store, sample_purchase, sample_purchase_2):
        """Test counting purchases."""
        assert store.count() == 0

        store.add(sample_purchase)
        assert store.count() == 1

        store.add(sample_purchase_2)
        assert store.count() == 2

    def test_count_by_user(self, store):
        """Test counting purchases by user."""
        # Add multiple purchases for same user
        for i in range(3):
            purchase = ProductPurchaseRecord(
                token=f"token_{i}",
                product_id=f"product_{i}",
                package_name="com.example.game",
                user_id="user-123",
                purchase_time_millis=int(time.time() * 1000),
                order_id=f"GPA.{i}",
                price_amount_micros=1000000,
            )
            store.add(purchase)

        assert store.count_by_user("user-123") == 3
        assert store.count_by_user("user-456") == 0

    def test_get_statistics(self, store):
        """Test getting store statistics."""
        # Add purchases for different users, products, packages
        purchases = [
            ProductPurchaseRecord(
                token="token_1",
                product_id="product_a",
                package_name="com.example.app1",
                user_id="user-1",
                purchase_time_millis=int(time.time() * 1000),
                order_id="GPA.1",
                price_amount_micros=1000000,
            ),
            ProductPurchaseRecord(
                token="token_2",
                product_id="product_a",
                package_name="com.example.app1",
                user_id="user-2",
                purchase_time_millis=int(time.time() * 1000),
                order_id="GPA.2",
                price_amount_micros=1000000,
            ),
            ProductPurchaseRecord(
                token="token_3",
                product_id="product_b",
                package_name="com.example.app2",
                user_id="user-1",
                purchase_time_millis=int(time.time() * 1000),
                order_id="GPA.3",
                price_amount_micros=1000000,
            ),
        ]

        for purchase in purchases:
            store.add(purchase)

        stats = store.get_statistics()
        assert stats["total_purchases"] == 3
        assert stats["unique_users"] == 2
        assert stats["unique_products"] == 2
        assert stats["unique_packages"] == 2

    def test_statistics_empty_store(self, store):
        """Test statistics on empty store."""
        stats = store.get_statistics()
        assert stats["total_purchases"] == 0
        assert stats["unique_users"] == 0
        assert stats["unique_products"] == 0
        assert stats["unique_packages"] == 0


class TestThreadSafety:
    """Test thread-safe operations."""

    def test_concurrent_adds(self, store):
        """Test concurrent additions to store."""
        def add_purchases(start_index: int, count: int):
            for i in range(start_index, start_index + count):
                purchase = ProductPurchaseRecord(
                    token=f"token_{i}",
                    product_id=f"product_{i}",
                    package_name="com.example.game",
                    user_id=f"user-{i}",
                    purchase_time_millis=int(time.time() * 1000),
                    order_id=f"GPA.{i}",
                    price_amount_micros=1000000,
                )
                store.add(purchase)

        # Create threads that add purchases concurrently
        threads = [
            Thread(target=add_purchases, args=(0, 50)),
            Thread(target=add_purchases, args=(50, 50)),
            Thread(target=add_purchases, args=(100, 50)),
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert store.count() == 150

    def test_concurrent_reads(self, store, sample_purchase):
        """Test concurrent reads from store."""
        store.add(sample_purchase)

        results = []

        def read_purchase():
            purchase = store.get_by_token(sample_purchase.token)
            results.append(purchase.token)

        threads = [Thread(target=read_purchase) for _ in range(10)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert len(results) == 10
        assert all(token == sample_purchase.token for token in results)


class TestSingletonPattern:
    """Test singleton pattern for global store."""

    def test_get_purchase_store_returns_singleton(self):
        """Test that get_purchase_store returns the same instance."""
        store1 = get_purchase_store()
        store2 = get_purchase_store()
        assert store1 is store2

    def test_singleton_is_functional(self):
        """Test that singleton instance is functional."""
        store = get_purchase_store()
        initial_count = store.count()

        purchase = ProductPurchaseRecord(
            token="singleton_test_token",
            product_id="test_product",
            package_name="com.test.app",
            user_id="test-user",
            purchase_time_millis=int(time.time() * 1000),
            order_id="GPA.TEST",
            price_amount_micros=1000000,
        )

        store.add(purchase)
        assert store.count() == initial_count + 1

        # Clean up
        store.delete_by_token("singleton_test_token")

    def test_reset_purchase_store(self):
        """Test resetting the global store."""
        store = get_purchase_store()

        # Add some data
        purchase = ProductPurchaseRecord(
            token="reset_test_token",
            product_id="test_product",
            package_name="com.test.app",
            user_id="test-user",
            purchase_time_millis=int(time.time() * 1000),
            order_id="GPA.TEST",
            price_amount_micros=1000000,
        )
        store.add(purchase)

        # Reset
        reset_purchase_store()

        # Verify it's empty (except for any lingering test data)
        # Note: We can't guarantee it's completely empty since other tests may use singleton
        assert store.get_all() == []


class TestLenAndContains:
    """Test __len__ and __contains__ operators."""

    def test_len_operator(self, store, sample_purchase, sample_purchase_2):
        """Test __len__ operator."""
        assert len(store) == 0

        store.add(sample_purchase)
        assert len(store) == 1

        store.add(sample_purchase_2)
        assert len(store) == 2

    def test_contains_operator(self, store, sample_purchase):
        """Test __contains__ operator (in)."""
        assert sample_purchase.token not in store

        store.add(sample_purchase)
        assert sample_purchase.token in store

        store.remove(sample_purchase.token)
        assert sample_purchase.token not in store


# Parametrized tests
@pytest.mark.parametrize("purchase_count", [0, 1, 5, 10])
def test_store_with_different_counts(purchase_count):
    """Test store operations with different numbers of purchases."""
    store = PurchaseStore()

    for i in range(purchase_count):
        purchase = ProductPurchaseRecord(
            token=f"token_{i}",
            product_id=f"product_{i}",
            package_name="com.example.game",
            user_id=f"user-{i}",
            purchase_time_millis=int(time.time() * 1000),
            order_id=f"GPA.{i}",
            price_amount_micros=1000000,
        )
        store.add(purchase)

    assert store.count() == purchase_count
    assert len(store.get_all()) == purchase_count


@pytest.mark.parametrize(
    "state",
    [PurchaseState.PURCHASED, PurchaseState.CANCELED, PurchaseState.PENDING],
)
def test_store_with_different_purchase_states(state):
    """Test storing purchases with different states."""
    store = PurchaseStore()
    purchase = ProductPurchaseRecord(
        token="test_token",
        product_id="test_product",
        package_name="com.test.app",
        user_id="test-user",
        purchase_state=state,
        purchase_time_millis=int(time.time() * 1000),
        order_id="GPA.TEST",
        price_amount_micros=1000000,
    )

    store.add(purchase)
    retrieved = store.get_by_token("test_token")
    assert retrieved.purchase_state == state
