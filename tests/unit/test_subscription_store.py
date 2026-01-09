"""Tests for SubscriptionStore - in-memory subscription storage."""

import time
from threading import Thread

import pytest

from iap_emulator.models.subscription import (
    SubscriptionRecord,
    SubscriptionState,
)
from iap_emulator.repositories.subscription_store import (
    SubscriptionNotFoundError,
    SubscriptionStore,
    get_subscription_store,
    reset_subscription_store,
)


@pytest.fixture
def store():
    """Create a fresh SubscriptionStore instance for testing."""
    store = SubscriptionStore()
    yield store
    store.clear()


@pytest.fixture
def sample_subscription():
    """Create a sample subscription for testing."""
    now_millis = int(time.time() * 1000)
    year_millis = 365 * 24 * 60 * 60 * 1000
    return SubscriptionRecord(
        token="emulator_test_sub_123",
        subscription_id="premium.personal.yearly",
        package_name="com.example.app",
        user_id="user-123",
        start_time_millis=now_millis,
        expiry_time_millis=now_millis + year_millis,
        purchase_time_millis=now_millis,
        order_id="GPA.1234-5678-9012",
        price_amount_micros=29990000,
    )


@pytest.fixture
def sample_subscription_2():
    """Create a second sample subscription for testing."""
    now_millis = int(time.time() * 1000)
    month_millis = 30 * 24 * 60 * 60 * 1000
    return SubscriptionRecord(
        token="emulator_test_sub_456",
        subscription_id="premium.family.monthly",
        package_name="com.example.app",
        user_id="user-456",
        start_time_millis=now_millis,
        expiry_time_millis=now_millis + month_millis,
        purchase_time_millis=now_millis,
        order_id="GPA.9876-5432-1098",
        price_amount_micros=14990000,
    )


class TestSubscriptionStoreBasics:
    """Test basic store functionality."""

    def test_store_initializes_empty(self, store):
        """Test that new store is empty."""
        assert store.count() == 0
        assert len(store) == 0
        assert store.get_all() == []

    def test_add_subscription(self, store, sample_subscription):
        """Test adding a subscription to the store."""
        store.add(sample_subscription)
        assert store.count() == 1
        assert store.exists(sample_subscription.token)

    def test_add_duplicate_token_raises_error(self, store, sample_subscription):
        """Test that adding duplicate token raises ValueError."""
        store.add(sample_subscription)
        with pytest.raises(ValueError) as exc_info:
            store.add(sample_subscription)
        assert "already exists" in str(exc_info.value)

    def test_repr(self, store, sample_subscription):
        """Test string representation."""
        assert "SubscriptionStore" in repr(store)
        assert "subscriptions=0" in repr(store)

        store.add(sample_subscription)
        assert "subscriptions=1" in repr(store)


class TestSubscriptionLookup:
    """Test subscription lookup methods."""

    def test_get_by_token_success(self, store, sample_subscription):
        """Test successful lookup by token."""
        store.add(sample_subscription)
        retrieved = store.get_by_token(sample_subscription.token)

        assert retrieved.token == sample_subscription.token
        assert retrieved.subscription_id == sample_subscription.subscription_id
        assert retrieved.user_id == sample_subscription.user_id

    def test_get_by_token_not_found_raises_error(self, store):
        """Test that get_by_token raises error when not found."""
        with pytest.raises(SubscriptionNotFoundError) as exc_info:
            store.get_by_token("non_existent_token")
        assert "not found" in str(exc_info.value).lower()

    def test_find_by_token_returns_none_when_not_found(self, store):
        """Test that find_by_token returns None when not found."""
        result = store.find_by_token("non_existent_token")
        assert result is None

    def test_find_by_token_success(self, store, sample_subscription):
        """Test successful find_by_token."""
        store.add(sample_subscription)
        result = store.find_by_token(sample_subscription.token)

        assert result is not None
        assert result.token == sample_subscription.token

    def test_exists_method(self, store, sample_subscription):
        """Test the exists() method."""
        assert store.exists(sample_subscription.token) is False

        store.add(sample_subscription)
        assert store.exists(sample_subscription.token) is True

    def test_contains_operator(self, store, sample_subscription):
        """Test the 'in' operator (contains)."""
        assert sample_subscription.token not in store

        store.add(sample_subscription)
        assert sample_subscription.token in store


class TestSubscriptionQueryMethods:
    """Test query methods for filtering subscriptions."""

    def test_get_by_user(self, store, sample_subscription, sample_subscription_2):
        """Test getting subscriptions by user_id."""
        store.add(sample_subscription)
        store.add(sample_subscription_2)

        user_123_subs = store.get_by_user("user-123")
        assert len(user_123_subs) == 1
        assert user_123_subs[0].user_id == "user-123"

        user_456_subs = store.get_by_user("user-456")
        assert len(user_456_subs) == 1
        assert user_456_subs[0].user_id == "user-456"

    def test_get_by_user_no_results(self, store, sample_subscription):
        """Test get_by_user with no matching subscriptions."""
        store.add(sample_subscription)
        result = store.get_by_user("non_existent_user")
        assert result == []

    def test_get_by_package(self, store, sample_subscription, sample_subscription_2):
        """Test getting subscriptions by package_name."""
        store.add(sample_subscription)
        store.add(sample_subscription_2)

        package_subs = store.get_by_package("com.example.app")
        assert len(package_subs) == 2
        assert all(s.package_name == "com.example.app" for s in package_subs)

    def test_get_by_subscription_id(self, store, sample_subscription):
        """Test getting subscriptions by subscription_id."""
        store.add(sample_subscription)

        subs = store.get_by_subscription_id("premium.personal.yearly")
        assert len(subs) == 1
        assert subs[0].subscription_id == "premium.personal.yearly"

    def test_get_user_subscription(self, store, sample_subscription):
        """Test getting a specific user's subscription."""
        store.add(sample_subscription)

        result = store.get_user_subscription(
            user_id="user-123",
            subscription_id="premium.personal.yearly",
            package_name="com.example.app",
        )

        assert result is not None
        assert result.user_id == "user-123"
        assert result.subscription_id == "premium.personal.yearly"

    def test_get_user_subscription_not_found(self, store, sample_subscription):
        """Test get_user_subscription when not found."""
        store.add(sample_subscription)

        result = store.get_user_subscription(
            user_id="user-999",
            subscription_id="premium.personal.yearly",
            package_name="com.example.app",
        )

        assert result is None


class TestStateBasedQueries:
    """Test state-based query methods."""

    def test_get_by_state(self, store, sample_subscription):
        """Test getting subscriptions by state."""
        store.add(sample_subscription)

        active_subs = store.get_by_state(SubscriptionState.ACTIVE)
        assert len(active_subs) == 1
        assert active_subs[0].state == SubscriptionState.ACTIVE

    def test_get_active_subscriptions(self, store, sample_subscription):
        """Test getting active subscriptions."""
        store.add(sample_subscription)

        active_subs = store.get_active_subscriptions()
        assert len(active_subs) == 1
        assert active_subs[0].state == SubscriptionState.ACTIVE

    def test_get_active_subscriptions_mixed_states(self, store):
        """Test get_active_subscriptions with mixed states."""
        now_millis = int(time.time() * 1000)

        # Create subscriptions in different states
        for i, state in enumerate([
            SubscriptionState.ACTIVE,
            SubscriptionState.CANCELED,
            SubscriptionState.ACTIVE,
            SubscriptionState.EXPIRED,
        ]):
            sub = SubscriptionRecord(
                token=f"token_{i}",
                subscription_id="premium.monthly",
                package_name="com.example.app",
                user_id=f"user-{i}",
                start_time_millis=now_millis,
                expiry_time_millis=now_millis + 1000000,
                purchase_time_millis=now_millis,
                order_id=f"GPA.{i}",
                price_amount_micros=9990000,
                state=state,
            )
            store.add(sub)

        active_subs = store.get_active_subscriptions()
        assert len(active_subs) == 2
        assert all(s.state == SubscriptionState.ACTIVE for s in active_subs)

    def test_get_in_grace_period(self, store):
        """Test getting subscriptions in grace period."""
        now_millis = int(time.time() * 1000)

        sub = SubscriptionRecord(
            token="grace_token",
            subscription_id="premium.monthly",
            package_name="com.example.app",
            user_id="user-grace",
            start_time_millis=now_millis,
            expiry_time_millis=now_millis + 1000000,
            purchase_time_millis=now_millis,
            order_id="GPA.GRACE",
            price_amount_micros=9990000,
            state=SubscriptionState.IN_GRACE_PERIOD,
        )
        store.add(sub)

        grace_subs = store.get_in_grace_period()
        assert len(grace_subs) == 1
        assert grace_subs[0].state == SubscriptionState.IN_GRACE_PERIOD

    def test_get_on_hold(self, store):
        """Test getting subscriptions on account hold."""
        now_millis = int(time.time() * 1000)

        sub = SubscriptionRecord(
            token="hold_token",
            subscription_id="premium.monthly",
            package_name="com.example.app",
            user_id="user-hold",
            start_time_millis=now_millis,
            expiry_time_millis=now_millis + 1000000,
            purchase_time_millis=now_millis,
            order_id="GPA.HOLD",
            price_amount_micros=9990000,
            state=SubscriptionState.ON_HOLD,
        )
        store.add(sub)

        hold_subs = store.get_on_hold()
        assert len(hold_subs) == 1
        assert hold_subs[0].state == SubscriptionState.ON_HOLD


class TestTimeBasedQueries:
    """Test time-based query methods."""

    def test_get_expiring_soon(self, store):
        """Test getting subscriptions expiring soon."""
        now_millis = int(time.time() * 1000)
        day_millis = 24 * 60 * 60 * 1000

        # Subscription expiring in 1 day
        sub1 = SubscriptionRecord(
            token="expiring_1",
            subscription_id="premium.monthly",
            package_name="com.example.app",
            user_id="user-1",
            start_time_millis=now_millis,
            expiry_time_millis=now_millis + day_millis,
            purchase_time_millis=now_millis,
            order_id="GPA.1",
            price_amount_micros=9990000,
        )

        # Subscription expiring in 10 days
        sub2 = SubscriptionRecord(
            token="expiring_2",
            subscription_id="premium.monthly",
            package_name="com.example.app",
            user_id="user-2",
            start_time_millis=now_millis,
            expiry_time_millis=now_millis + (10 * day_millis),
            purchase_time_millis=now_millis,
            order_id="GPA.2",
            price_amount_micros=9990000,
        )

        store.add(sub1)
        store.add(sub2)

        # Get subscriptions expiring within 5 days
        expiring = store.get_expiring_soon(now_millis + (5 * day_millis))
        assert len(expiring) == 1
        assert expiring[0].token == "expiring_1"

    def test_get_renewals_due(self, store):
        """Test getting subscriptions due for renewal."""
        now_millis = int(time.time() * 1000)
        day_millis = 24 * 60 * 60 * 1000

        # Active, auto-renewing, expiring soon
        sub1 = SubscriptionRecord(
            token="renewal_1",
            subscription_id="premium.monthly",
            package_name="com.example.app",
            user_id="user-1",
            start_time_millis=now_millis,
            expiry_time_millis=now_millis + day_millis,
            purchase_time_millis=now_millis,
            order_id="GPA.1",
            price_amount_micros=9990000,
            state=SubscriptionState.ACTIVE,
            auto_renewing=True,
        )

        # Canceled, should not be renewed
        sub2 = SubscriptionRecord(
            token="renewal_2",
            subscription_id="premium.monthly",
            package_name="com.example.app",
            user_id="user-2",
            start_time_millis=now_millis,
            expiry_time_millis=now_millis + day_millis,
            purchase_time_millis=now_millis,
            order_id="GPA.2",
            price_amount_micros=9990000,
            state=SubscriptionState.CANCELED,
            auto_renewing=False,
        )

        store.add(sub1)
        store.add(sub2)

        renewals = store.get_renewals_due(now_millis + (2 * day_millis))
        assert len(renewals) == 1
        assert renewals[0].token == "renewal_1"
        assert renewals[0].auto_renewing is True


class TestTrialQueries:
    """Test trial period queries."""

    def test_get_in_trial(self, store):
        """Test getting subscriptions in trial period."""
        now_millis = int(time.time() * 1000)

        # In trial
        sub1 = SubscriptionRecord(
            token="trial_1",
            subscription_id="premium.monthly",
            package_name="com.example.app",
            user_id="user-1",
            start_time_millis=now_millis,
            expiry_time_millis=now_millis + 1000000,
            purchase_time_millis=now_millis,
            order_id="GPA.1",
            price_amount_micros=9990000,
            in_trial=True,
        )

        # Not in trial
        sub2 = SubscriptionRecord(
            token="trial_2",
            subscription_id="premium.monthly",
            package_name="com.example.app",
            user_id="user-2",
            start_time_millis=now_millis,
            expiry_time_millis=now_millis + 1000000,
            purchase_time_millis=now_millis,
            order_id="GPA.2",
            price_amount_micros=9990000,
            in_trial=False,
        )

        store.add(sub1)
        store.add(sub2)

        trial_subs = store.get_in_trial()
        assert len(trial_subs) == 1
        assert trial_subs[0].in_trial is True


class TestSubscriptionModification:
    """Test subscription update and delete operations."""

    def test_update_subscription(self, store, sample_subscription):
        """Test updating an existing subscription."""
        store.add(sample_subscription)

        # Modify the subscription
        sample_subscription.state = SubscriptionState.CANCELED
        store.update(sample_subscription)

        # Verify update
        retrieved = store.get_by_token(sample_subscription.token)
        assert retrieved.state == SubscriptionState.CANCELED

    def test_update_nonexistent_subscription_raises_error(self, store, sample_subscription):
        """Test that updating nonexistent subscription raises error."""
        with pytest.raises(SubscriptionNotFoundError):
            store.update(sample_subscription)

    def test_upsert_new_subscription(self, store, sample_subscription):
        """Test upsert with new subscription (insert)."""
        store.upsert(sample_subscription)
        assert store.exists(sample_subscription.token)

    def test_upsert_existing_subscription(self, store, sample_subscription):
        """Test upsert with existing subscription (update)."""
        store.add(sample_subscription)
        assert store.count() == 1

        # Modify and upsert
        sample_subscription.state = SubscriptionState.CANCELED
        store.upsert(sample_subscription)

        assert store.count() == 1
        retrieved = store.get_by_token(sample_subscription.token)
        assert retrieved.state == SubscriptionState.CANCELED

    def test_remove_subscription(self, store, sample_subscription):
        """Test removing a subscription."""
        store.add(sample_subscription)
        assert store.exists(sample_subscription.token)

        store.remove(sample_subscription.token)
        assert not store.exists(sample_subscription.token)

    def test_remove_nonexistent_subscription_raises_error(self, store):
        """Test that removing nonexistent subscription raises error."""
        with pytest.raises(SubscriptionNotFoundError):
            store.remove("non_existent_token")

    def test_delete_by_token_success(self, store, sample_subscription):
        """Test delete_by_token returns True on success."""
        store.add(sample_subscription)
        result = store.delete_by_token(sample_subscription.token)

        assert result is True
        assert not store.exists(sample_subscription.token)

    def test_delete_by_token_not_found(self, store):
        """Test delete_by_token returns False when not found."""
        result = store.delete_by_token("non_existent_token")
        assert result is False


class TestBulkOperations:
    """Test bulk operations on store."""

    def test_get_all(self, store, sample_subscription, sample_subscription_2):
        """Test getting all subscriptions."""
        store.add(sample_subscription)
        store.add(sample_subscription_2)

        all_subs = store.get_all()
        assert len(all_subs) == 2
        tokens = [s.token for s in all_subs]
        assert sample_subscription.token in tokens
        assert sample_subscription_2.token in tokens

    def test_get_all_tokens(self, store, sample_subscription, sample_subscription_2):
        """Test getting all subscription tokens."""
        store.add(sample_subscription)
        store.add(sample_subscription_2)

        tokens = store.get_all_tokens()
        assert len(tokens) == 2
        assert sample_subscription.token in tokens
        assert sample_subscription_2.token in tokens

    def test_clear(self, store, sample_subscription, sample_subscription_2):
        """Test clearing all subscriptions."""
        store.add(sample_subscription)
        store.add(sample_subscription_2)
        assert store.count() == 2

        store.clear()
        assert store.count() == 0
        assert store.get_all() == []


class TestStatistics:
    """Test statistics and counting methods."""

    def test_count(self, store, sample_subscription, sample_subscription_2):
        """Test counting subscriptions."""
        assert store.count() == 0

        store.add(sample_subscription)
        assert store.count() == 1

        store.add(sample_subscription_2)
        assert store.count() == 2

    def test_count_by_user(self, store):
        """Test counting subscriptions by user."""
        now_millis = int(time.time() * 1000)

        # Add multiple subscriptions for same user
        for i in range(3):
            sub = SubscriptionRecord(
                token=f"token_{i}",
                subscription_id=f"premium.plan_{i}",
                package_name="com.example.app",
                user_id="user-123",
                start_time_millis=now_millis,
                expiry_time_millis=now_millis + 1000000,
                purchase_time_millis=now_millis,
                order_id=f"GPA.{i}",
                price_amount_micros=9990000,
            )
            store.add(sub)

        assert store.count_by_user("user-123") == 3
        assert store.count_by_user("user-456") == 0

    def test_count_by_state(self, store):
        """Test counting subscriptions by state."""
        now_millis = int(time.time() * 1000)

        # Create subscriptions in different states
        states = [
            SubscriptionState.ACTIVE,
            SubscriptionState.ACTIVE,
            SubscriptionState.CANCELED,
            SubscriptionState.EXPIRED,
        ]

        for i, state in enumerate(states):
            sub = SubscriptionRecord(
                token=f"token_{i}",
                subscription_id="premium.monthly",
                package_name="com.example.app",
                user_id=f"user-{i}",
                start_time_millis=now_millis,
                expiry_time_millis=now_millis + 1000000,
                purchase_time_millis=now_millis,
                order_id=f"GPA.{i}",
                price_amount_micros=9990000,
                state=state,
            )
            store.add(sub)

        assert store.count_by_state(SubscriptionState.ACTIVE) == 2
        assert store.count_by_state(SubscriptionState.CANCELED) == 1
        assert store.count_by_state(SubscriptionState.EXPIRED) == 1

    def test_get_statistics(self, store):
        """Test getting store statistics."""
        now_millis = int(time.time() * 1000)

        # Create diverse subscriptions
        subscriptions = [
            SubscriptionRecord(
                token="token_1",
                subscription_id="premium.personal",
                package_name="com.example.app1",
                user_id="user-1",
                start_time_millis=now_millis,
                expiry_time_millis=now_millis + 1000000,
                purchase_time_millis=now_millis,
                order_id="GPA.1",
                price_amount_micros=9990000,
                state=SubscriptionState.ACTIVE,
                in_trial=True,
                auto_renewing=True,
            ),
            SubscriptionRecord(
                token="token_2",
                subscription_id="premium.personal",
                package_name="com.example.app1",
                user_id="user-2",
                start_time_millis=now_millis,
                expiry_time_millis=now_millis + 1000000,
                purchase_time_millis=now_millis,
                order_id="GPA.2",
                price_amount_micros=9990000,
                state=SubscriptionState.CANCELED,
                auto_renewing=False,
            ),
            SubscriptionRecord(
                token="token_3",
                subscription_id="premium.family",
                package_name="com.example.app2",
                user_id="user-1",
                start_time_millis=now_millis,
                expiry_time_millis=now_millis + 1000000,
                purchase_time_millis=now_millis,
                order_id="GPA.3",
                price_amount_micros=14990000,
                state=SubscriptionState.EXPIRED,
                auto_renewing=False,
            ),
        ]

        for sub in subscriptions:
            store.add(sub)

        stats = store.get_statistics()
        assert stats["total_subscriptions"] == 3
        assert stats["unique_users"] == 2
        assert stats["unique_subscription_ids"] == 2
        assert stats["unique_packages"] == 2
        assert stats["active"] == 1
        assert stats["canceled"] == 1
        assert stats["expired"] == 1
        assert stats["in_trial"] == 1
        assert stats["auto_renewing"] == 1

    def test_statistics_empty_store(self, store):
        """Test statistics on empty store."""
        stats = store.get_statistics()
        assert stats["total_subscriptions"] == 0
        assert stats["unique_users"] == 0
        assert stats["active"] == 0


class TestThreadSafety:
    """Test thread-safe operations."""

    def test_concurrent_adds(self, store):
        """Test concurrent additions to store."""
        def add_subscriptions(start_index: int, count: int):
            now_millis = int(time.time() * 1000)
            for i in range(start_index, start_index + count):
                sub = SubscriptionRecord(
                    token=f"token_{i}",
                    subscription_id=f"premium.plan_{i}",
                    package_name="com.example.app",
                    user_id=f"user-{i}",
                    start_time_millis=now_millis,
                    expiry_time_millis=now_millis + 1000000,
                    purchase_time_millis=now_millis,
                    order_id=f"GPA.{i}",
                    price_amount_micros=9990000,
                )
                store.add(sub)

        # Create threads that add subscriptions concurrently
        threads = [
            Thread(target=add_subscriptions, args=(0, 50)),
            Thread(target=add_subscriptions, args=(50, 50)),
            Thread(target=add_subscriptions, args=(100, 50)),
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert store.count() == 150

    def test_concurrent_reads(self, store, sample_subscription):
        """Test concurrent reads from store."""
        store.add(sample_subscription)

        results = []

        def read_subscription():
            sub = store.get_by_token(sample_subscription.token)
            results.append(sub.token)

        threads = [Thread(target=read_subscription) for _ in range(10)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert len(results) == 10
        assert all(token == sample_subscription.token for token in results)


class TestSingletonPattern:
    """Test singleton pattern for global store."""

    def test_get_subscription_store_returns_singleton(self):
        """Test that get_subscription_store returns the same instance."""
        store1 = get_subscription_store()
        store2 = get_subscription_store()
        assert store1 is store2

    def test_singleton_is_functional(self):
        """Test that singleton instance is functional."""
        store = get_subscription_store()
        initial_count = store.count()

        now_millis = int(time.time() * 1000)
        sub = SubscriptionRecord(
            token="singleton_test_token",
            subscription_id="test_subscription",
            package_name="com.test.app",
            user_id="test-user",
            start_time_millis=now_millis,
            expiry_time_millis=now_millis + 1000000,
            purchase_time_millis=now_millis,
            order_id="GPA.TEST",
            price_amount_micros=9990000,
        )

        store.add(sub)
        assert store.count() == initial_count + 1

        # Clean up
        store.delete_by_token("singleton_test_token")

    def test_reset_subscription_store(self):
        """Test resetting the global store."""
        store = get_subscription_store()

        # Add some data
        now_millis = int(time.time() * 1000)
        sub = SubscriptionRecord(
            token="reset_test_token",
            subscription_id="test_subscription",
            package_name="com.test.app",
            user_id="test-user",
            start_time_millis=now_millis,
            expiry_time_millis=now_millis + 1000000,
            purchase_time_millis=now_millis,
            order_id="GPA.TEST",
            price_amount_micros=9990000,
        )
        store.add(sub)

        # Reset
        reset_subscription_store()

        # Verify it's empty
        assert store.get_all() == []


class TestLenAndContains:
    """Test __len__ and __contains__ operators."""

    def test_len_operator(self, store, sample_subscription, sample_subscription_2):
        """Test __len__ operator."""
        assert len(store) == 0

        store.add(sample_subscription)
        assert len(store) == 1

        store.add(sample_subscription_2)
        assert len(store) == 2

    def test_contains_operator(self, store, sample_subscription):
        """Test __contains__ operator (in)."""
        assert sample_subscription.token not in store

        store.add(sample_subscription)
        assert sample_subscription.token in store

        store.remove(sample_subscription.token)
        assert sample_subscription.token not in store


# Parametrized tests
@pytest.mark.parametrize("subscription_count", [0, 1, 5, 10])
def test_store_with_different_counts(subscription_count):
    """Test store operations with different numbers of subscriptions."""
    store = SubscriptionStore()
    now_millis = int(time.time() * 1000)

    for i in range(subscription_count):
        sub = SubscriptionRecord(
            token=f"token_{i}",
            subscription_id=f"premium.plan_{i}",
            package_name="com.example.app",
            user_id=f"user-{i}",
            start_time_millis=now_millis,
            expiry_time_millis=now_millis + 1000000,
            purchase_time_millis=now_millis,
            order_id=f"GPA.{i}",
            price_amount_micros=9990000,
        )
        store.add(sub)

    assert store.count() == subscription_count
    assert len(store.get_all()) == subscription_count


@pytest.mark.parametrize(
    "state",
    [
        SubscriptionState.ACTIVE,
        SubscriptionState.CANCELED,
        SubscriptionState.IN_GRACE_PERIOD,
        SubscriptionState.ON_HOLD,
        SubscriptionState.PAUSED,
        SubscriptionState.EXPIRED,
    ],
)
def test_store_with_different_states(state):
    """Test storing subscriptions with different states."""
    store = SubscriptionStore()
    now_millis = int(time.time() * 1000)

    sub = SubscriptionRecord(
        token="test_token",
        subscription_id="test_subscription",
        package_name="com.test.app",
        user_id="test-user",
        start_time_millis=now_millis,
        expiry_time_millis=now_millis + 1000000,
        purchase_time_millis=now_millis,
        order_id="GPA.TEST",
        price_amount_micros=9990000,
        state=state,
    )

    store.add(sub)
    retrieved = store.get_by_token("test_token")
    assert retrieved.state == state
