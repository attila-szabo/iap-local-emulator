"""Subscription store - in-memory storage for subscription state.

Manages subscription records, renewal dates, and state transitions.
"""

import threading
from typing import Dict, List, Optional

from iap_emulator.models.subscription import SubscriptionRecord, SubscriptionState


class SubscriptionNotFoundError(Exception):
    """Raised when a subscription is not found in the store."""

    pass


class SubscriptionStore:
    """In-memory storage for subscription records.

    Thread-safe storage with lookup by token, user_id, package_name, subscription_id,
    and subscription state. Supports time-based queries for renewals and expirations.
    """

    def __init__(self):
        """Initialize subscription store with empty storage."""
        self._subscriptions: Dict[str, SubscriptionRecord] = {}
        self._lock = threading.RLock()

    def add(self, subscription: SubscriptionRecord) -> None:
        """Add a subscription to the store.

        Args:
            subscription: SubscriptionRecord to store

        Raises:
            ValueError: If subscription token already exists
        """
        with self._lock:
            if subscription.token in self._subscriptions:
                raise ValueError(
                    f"Subscription with token '{subscription.token}' already exists"
                )
            self._subscriptions[subscription.token] = subscription

    def get_by_token(self, token: str) -> SubscriptionRecord:
        """Get subscription by token.

        Args:
            token: Subscription token

        Returns:
            SubscriptionRecord

        Raises:
            SubscriptionNotFoundError: If token not found
        """
        with self._lock:
            subscription = self._subscriptions.get(token)
            if subscription is None:
                raise SubscriptionNotFoundError(
                    f"Subscription not found for token: {token}"
                )
            return subscription

    def find_by_token(self, token: str) -> Optional[SubscriptionRecord]:
        """Find subscription by token (returns None if not found).

        Args:
            token: Subscription token

        Returns:
            SubscriptionRecord if found, None otherwise
        """
        with self._lock:
            return self._subscriptions.get(token)

    def get_by_user(self, user_id: str) -> List[SubscriptionRecord]:
        """Get all subscriptions for a specific user.

        Args:
            user_id: User identifier

        Returns:
            List of SubscriptionRecord objects for the user
        """
        with self._lock:
            return [s for s in self._subscriptions.values() if s.user_id == user_id]

    def get_by_package(self, package_name: str) -> List[SubscriptionRecord]:
        """Get all subscriptions for a specific package.

        Args:
            package_name: Android package name

        Returns:
            List of SubscriptionRecord objects for the package
        """
        with self._lock:
            return [
                s for s in self._subscriptions.values() if s.package_name == package_name
            ]

    def get_by_subscription_id(self, subscription_id: str) -> List[SubscriptionRecord]:
        """Get all subscriptions for a specific subscription product.

        Args:
            subscription_id: Subscription product ID (e.g., "premium.personal.yearly")

        Returns:
            List of SubscriptionRecord objects for the subscription product
        """
        with self._lock:
            return [
                s
                for s in self._subscriptions.values()
                if s.subscription_id == subscription_id
            ]

    def get_user_subscription(
        self, user_id: str, subscription_id: str, package_name: str
    ) -> Optional[SubscriptionRecord]:
        """Get a specific user's subscription for a subscription product and package.

        Args:
            user_id: User identifier
            subscription_id: Subscription product ID
            package_name: Android package name

        Returns:
            SubscriptionRecord if found, None otherwise
        """
        with self._lock:
            for subscription in self._subscriptions.values():
                if (
                    subscription.user_id == user_id
                    and subscription.subscription_id == subscription_id
                    and subscription.package_name == package_name
                ):
                    return subscription
            return None

    def get_by_state(self, state: SubscriptionState) -> List[SubscriptionRecord]:
        """Get all subscriptions in a specific state.

        Args:
            state: SubscriptionState to filter by

        Returns:
            List of SubscriptionRecord objects in the specified state
        """
        with self._lock:
            return [s for s in self._subscriptions.values() if s.state == state]

    def get_active_subscriptions(self) -> List[SubscriptionRecord]:
        """Get all active subscriptions.

        Returns:
            List of SubscriptionRecord objects in ACTIVE state
        """
        return self.get_by_state(SubscriptionState.ACTIVE)

    def get_expiring_soon(self, before_millis: int) -> List[SubscriptionRecord]:
        """Get subscriptions expiring before a specific time.

        Args:
            before_millis: Unix timestamp in milliseconds

        Returns:
            List of SubscriptionRecord objects expiring before the given time
        """
        with self._lock:
            return [
                s
                for s in self._subscriptions.values()
                if s.expiry_time_millis <= before_millis
            ]

    def get_renewals_due(self, at_time_millis: int) -> List[SubscriptionRecord]:
        """Get subscriptions due for renewal at a specific time.

        Returns active, auto-renewing subscriptions expiring at or before the given time.

        Args:
            at_time_millis: Unix timestamp in milliseconds

        Returns:
            List of SubscriptionRecord objects due for renewal
        """
        with self._lock:
            return [
                s
                for s in self._subscriptions.values()
                if s.state == SubscriptionState.ACTIVE
                and s.auto_renewing
                and s.expiry_time_millis <= at_time_millis
            ]

    def get_in_trial(self) -> List[SubscriptionRecord]:
        """Get all subscriptions currently in trial period.

        Returns:
            List of SubscriptionRecord objects in trial
        """
        with self._lock:
            return [s for s in self._subscriptions.values() if s.in_trial]

    def get_in_grace_period(self) -> List[SubscriptionRecord]:
        """Get all subscriptions in grace period.

        Returns:
            List of SubscriptionRecord objects in grace period state
        """
        return self.get_by_state(SubscriptionState.IN_GRACE_PERIOD)

    def get_on_hold(self) -> List[SubscriptionRecord]:
        """Get all subscriptions on account hold.

        Returns:
            List of SubscriptionRecord objects in on hold state
        """
        return self.get_by_state(SubscriptionState.ON_HOLD)

    def update(self, subscription: SubscriptionRecord) -> None:
        """Update an existing subscription.

        Args:
            subscription: Updated SubscriptionRecord

        Raises:
            SubscriptionNotFoundError: If subscription token not found
        """
        with self._lock:
            if subscription.token not in self._subscriptions:
                raise SubscriptionNotFoundError(
                    f"Subscription not found for token: {subscription.token}"
                )
            self._subscriptions[subscription.token] = subscription

    def upsert(self, subscription: SubscriptionRecord) -> None:
        """Add or update a subscription (insert or update).

        Args:
            subscription: SubscriptionRecord to store
        """
        with self._lock:
            self._subscriptions[subscription.token] = subscription

    def remove(self, token: str) -> None:
        """Remove a subscription from the store.

        Args:
            token: Subscription token to remove

        Raises:
            SubscriptionNotFoundError: If token not found
        """
        with self._lock:
            if token not in self._subscriptions:
                raise SubscriptionNotFoundError(
                    f"Subscription not found for token: {token}"
                )
            del self._subscriptions[token]

    def delete_by_token(self, token: str) -> bool:
        """Delete a subscription by token (returns success status).

        Args:
            token: Subscription token

        Returns:
            True if subscription was deleted, False if not found
        """
        with self._lock:
            if token in self._subscriptions:
                del self._subscriptions[token]
                return True
            return False

    def exists(self, token: str) -> bool:
        """Check if subscription token exists.

        Args:
            token: Subscription token

        Returns:
            True if subscription exists, False otherwise
        """
        with self._lock:
            return token in self._subscriptions

    def get_all(self) -> List[SubscriptionRecord]:
        """Get all subscriptions in the store.

        Returns:
            List of all SubscriptionRecord objects
        """
        with self._lock:
            return list(self._subscriptions.values())

    def get_all_tokens(self) -> List[str]:
        """Get all subscription tokens.

        Returns:
            List of all subscription tokens
        """
        with self._lock:
            return list(self._subscriptions.keys())

    def count(self) -> int:
        """Get total number of subscriptions.

        Returns:
            Count of subscriptions
        """
        with self._lock:
            return len(self._subscriptions)

    def count_by_user(self, user_id: str) -> int:
        """Get count of subscriptions for a specific user.

        Args:
            user_id: User identifier

        Returns:
            Count of subscriptions for the user
        """
        with self._lock:
            return sum(1 for s in self._subscriptions.values() if s.user_id == user_id)

    def count_by_state(self, state: SubscriptionState) -> int:
        """Get count of subscriptions in a specific state.

        Args:
            state: SubscriptionState to count

        Returns:
            Count of subscriptions in the specified state
        """
        with self._lock:
            return sum(1 for s in self._subscriptions.values() if s.state == state)

    def clear(self) -> None:
        """Clear all subscriptions from the store.

        Warning: This removes all data. Use with caution.
        """
        with self._lock:
            self._subscriptions.clear()

    def get_statistics(self) -> Dict[str, int]:
        """Get subscription store statistics.

        Returns:
            Dictionary with statistics:
            - total_subscriptions: Total number of subscriptions
            - unique_users: Number of unique users
            - unique_subscription_ids: Number of unique subscription products
            - unique_packages: Number of unique packages
            - active: Count of active subscriptions
            - canceled: Count of canceled subscriptions
            - expired: Count of expired subscriptions
            - in_grace_period: Count in grace period
            - on_hold: Count on account hold
            - paused: Count of paused subscriptions
            - in_trial: Count in trial period
            - auto_renewing: Count with auto-renew enabled
        """
        with self._lock:
            subscriptions = list(self._subscriptions.values())
            return {
                "total_subscriptions": len(subscriptions),
                "unique_users": len(set(s.user_id for s in subscriptions)),
                "unique_subscription_ids": len(
                    set(s.subscription_id for s in subscriptions)
                ),
                "unique_packages": len(set(s.package_name for s in subscriptions)),
                "active": sum(1 for s in subscriptions if s.state == SubscriptionState.ACTIVE),
                "canceled": sum(1 for s in subscriptions if s.state == SubscriptionState.CANCELED),
                "expired": sum(1 for s in subscriptions if s.state == SubscriptionState.EXPIRED),
                "in_grace_period": sum(
                    1 for s in subscriptions if s.state == SubscriptionState.IN_GRACE_PERIOD
                ),
                "on_hold": sum(1 for s in subscriptions if s.state == SubscriptionState.ON_HOLD),
                "paused": sum(1 for s in subscriptions if s.state == SubscriptionState.PAUSED),
                "in_trial": sum(1 for s in subscriptions if s.in_trial),
                "auto_renewing": sum(1 for s in subscriptions if s.auto_renewing),
            }

    def __len__(self) -> int:
        """Get number of subscriptions in store."""
        return self.count()

    def __contains__(self, token: str) -> bool:
        """Check if token exists in store."""
        return self.exists(token)

    def __repr__(self) -> str:
        """String representation of store."""
        return f"SubscriptionStore(subscriptions={self.count()})"


# Global store instance
_store_instance: Optional[SubscriptionStore] = None
_store_lock = threading.Lock()


def get_subscription_store() -> SubscriptionStore:
    """Get global subscription store instance (singleton).

    Returns:
        SubscriptionStore instance
    """
    global _store_instance
    if _store_instance is None:
        with _store_lock:
            if _store_instance is None:
                _store_instance = SubscriptionStore()
    return _store_instance


def reset_subscription_store() -> None:
    """Reset global subscription store (clears all data).

    Warning: This removes all subscription data. Use with caution.
    """
    global _store_instance
    store = get_subscription_store()
    store.clear()
