"""Purchase store - in-memory storage for active purchases and tokens.

Thread-safe dictionary-based storage.
"""

import threading
from typing import Dict, List, Optional

from iap_emulator.models.purchase import ProductPurchaseRecord


class PurchaseNotFoundError(Exception):
    """Raised when a purchase is not found in the store."""

    pass


class PurchaseStore:
    """In-memory storage for one-time product purchases.

    Thread-safe storage with lookup by token, user_id, package_name, and product_id.
    """

    def __init__(self):
        """Initialize purchase store with empty storage."""
        self._purchases: Dict[str, ProductPurchaseRecord] = {}
        self._lock = threading.RLock()

    def add(self, purchase: ProductPurchaseRecord) -> None:
        """Add a purchase to the store.

        Args:
            purchase: ProductPurchaseRecord to store

        Raises:
            ValueError: If purchase token already exists
        """
        with self._lock:
            if purchase.token in self._purchases:
                raise ValueError(
                    f"Purchase with token '{purchase.token}' already exists"
                )
            self._purchases[purchase.token] = purchase

    def get_by_token(self, token: str) -> ProductPurchaseRecord:
        """Get purchase by token.

        Args:
            token: Purchase token

        Returns:
            ProductPurchaseRecord

        Raises:
            PurchaseNotFoundError: If token not found
        """
        with self._lock:
            purchase = self._purchases.get(token)
            if purchase is None:
                raise PurchaseNotFoundError(
                    f"Purchase not found for token: {token}"
                )
            return purchase

    def find_by_token(self, token: str) -> Optional[ProductPurchaseRecord]:
        """Find purchase by token (returns None if not found).

        Args:
            token: Purchase token

        Returns:
            ProductPurchaseRecord if found, None otherwise
        """
        with self._lock:
            return self._purchases.get(token)

    def get_by_user(self, user_id: str) -> List[ProductPurchaseRecord]:
        """Get all purchases for a specific user.

        Args:
            user_id: User identifier

        Returns:
            List of ProductPurchaseRecord objects for the user
        """
        with self._lock:
            return [p for p in self._purchases.values() if p.user_id == user_id]

    def get_by_package(self, package_name: str) -> List[ProductPurchaseRecord]:
        """Get all purchases for a specific package.

        Args:
            package_name: Android package name

        Returns:
            List of ProductPurchaseRecord objects for the package
        """
        with self._lock:
            return [
                p for p in self._purchases.values() if p.package_name == package_name
            ]

    def get_by_product_id(self, product_id: str) -> List[ProductPurchaseRecord]:
        """Get all purchases for a specific product.

        Args:
            product_id: Product ID

        Returns:
            List of ProductPurchaseRecord objects for the product
        """
        with self._lock:
            return [p for p in self._purchases.values() if p.product_id == product_id]

    def get_by_order_id(self, order_id: str) -> ProductPurchaseRecord:
        """Get purchase by order ID.

        Args:
            order_id: Order ID

        Returns:
            ProductPurchaseRecord

        Raises:
            PurchaseNotFoundError: If order ID not found
        """
        with self._lock:
            for purchase in self._purchases.values():
                if purchase.order_id == order_id:
                    return purchase
            raise PurchaseNotFoundError(f"Purchase not found for order ID: {order_id}")

    def find_by_order_id(self, order_id: str) -> Optional[ProductPurchaseRecord]:
        """Find purchase by order ID (returns None if not found).

        Args:
            order_id: Order ID

        Returns:
            ProductPurchaseRecord if found, None otherwise
        """
        with self._lock:
            for purchase in self._purchases.values():
                if purchase.order_id == order_id:
                    return purchase
            return None

    def get_user_purchase(
        self, user_id: str, product_id: str, package_name: str
    ) -> Optional[ProductPurchaseRecord]:
        """Get a specific user's purchase for a product and package.

        Args:
            user_id: User identifier
            product_id: Product ID
            package_name: Android package name

        Returns:
            ProductPurchaseRecord if found, None otherwise
        """
        with self._lock:
            for purchase in self._purchases.values():
                if (
                    purchase.user_id == user_id
                    and purchase.product_id == product_id
                    and purchase.package_name == package_name
                ):
                    return purchase
            return None

    def update(self, purchase: ProductPurchaseRecord) -> None:
        """Update an existing purchase.

        Args:
            purchase: Updated ProductPurchaseRecord

        Raises:
            PurchaseNotFoundError: If purchase token not found
        """
        with self._lock:
            if purchase.token not in self._purchases:
                raise PurchaseNotFoundError(
                    f"Purchase not found for token: {purchase.token}"
                )
            self._purchases[purchase.token] = purchase

    def upsert(self, purchase: ProductPurchaseRecord) -> None:
        """Add or update a purchase (insert or update).

        Args:
            purchase: ProductPurchaseRecord to store
        """
        with self._lock:
            self._purchases[purchase.token] = purchase

    def remove(self, token: str) -> None:
        """Remove a purchase from the store.

        Args:
            token: Purchase token to remove

        Raises:
            PurchaseNotFoundError: If token not found
        """
        with self._lock:
            if token not in self._purchases:
                raise PurchaseNotFoundError(f"Purchase not found for token: {token}")
            del self._purchases[token]

    def delete_by_token(self, token: str) -> bool:
        """Delete a purchase by token (returns success status).

        Args:
            token: Purchase token

        Returns:
            True if purchase was deleted, False if not found
        """
        with self._lock:
            if token in self._purchases:
                del self._purchases[token]
                return True
            return False

    def exists(self, token: str) -> bool:
        """Check if purchase token exists.

        Args:
            token: Purchase token

        Returns:
            True if purchase exists, False otherwise
        """
        with self._lock:
            return token in self._purchases

    def get_all(self) -> List[ProductPurchaseRecord]:
        """Get all purchases in the store.

        Returns:
            List of all ProductPurchaseRecord objects
        """
        with self._lock:
            return list(self._purchases.values())

    def get_all_tokens(self) -> List[str]:
        """Get all purchase tokens.

        Returns:
            List of all purchase tokens
        """
        with self._lock:
            return list(self._purchases.keys())

    def count(self) -> int:
        """Get total number of purchases.

        Returns:
            Count of purchases
        """
        with self._lock:
            return len(self._purchases)

    def count_by_user(self, user_id: str) -> int:
        """Get count of purchases for a specific user.

        Args:
            user_id: User identifier

        Returns:
            Count of purchases for the user
        """
        with self._lock:
            return sum(1 for p in self._purchases.values() if p.user_id == user_id)

    def clear(self) -> None:
        """Clear all purchases from the store.

        Warning: This removes all data. Use with caution.
        """
        with self._lock:
            self._purchases.clear()

    def get_statistics(self) -> Dict[str, int]:
        """Get purchase store statistics.

        Returns:
            Dictionary with statistics:
            - total_purchases: Total number of purchases
            - unique_users: Number of unique users
            - unique_products: Number of unique products
            - unique_packages: Number of unique packages
        """
        with self._lock:
            purchases = list(self._purchases.values())
            return {
                "total_purchases": len(purchases),
                "unique_users": len(set(p.user_id for p in purchases)),
                "unique_products": len(set(p.product_id for p in purchases)),
                "unique_packages": len(set(p.package_name for p in purchases)),
            }

    def __len__(self) -> int:
        """Get number of purchases in store."""
        return self.count()

    def __contains__(self, token: str) -> bool:
        """Check if token exists in store."""
        return self.exists(token)

    def __repr__(self) -> str:
        """String representation of store."""
        return f"PurchaseStore(purchases={self.count()})"


# Global store instance
_store_instance: Optional[PurchaseStore] = None
_store_lock = threading.Lock()


def get_purchase_store() -> PurchaseStore:
    """Get global purchase store instance (singleton).

    Returns:
        PurchaseStore instance
    """
    global _store_instance
    if _store_instance is None:
        with _store_lock:
            if _store_instance is None:
                _store_instance = PurchaseStore()
    return _store_instance


def reset_purchase_store() -> None:
    """Reset global purchase store (clears all data).

    Warning: This removes all purchase data. Use with caution.
    """
    global _store_instance
    store = get_purchase_store()
    store.clear()
