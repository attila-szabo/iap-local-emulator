"""Purchase Manager - handles purchase creation, validation, and lifecycle.

Manages one-time product purchases including creation, acknowledgment, and consumption.
"""

import time
from typing import Optional

from iap_emulator.models.purchase import (
    AcknowledgementState,
    ConsumptionState,
    ProductPurchaseRecord,
    PurchaseState,
)
from iap_emulator.repositories.product_repository import (
    ProductNotFoundError,
    ProductRepository,
    get_product_repository,
)
from iap_emulator.repositories.purchase_store import (
    PurchaseNotFoundError,
    PurchaseStore,
    get_purchase_store,
)
from iap_emulator.utils.token_generator import (
    generate_order_id,
    generate_purchase_token,
    validate_token,
)


class PurchaseManagerError(Exception):
    """Base exception for purchase manager errors."""

    pass


class InvalidPurchaseStateError(PurchaseManagerError):
    """Raised when purchase is in invalid state for requested operation."""

    pass


class PurchaseAlreadyConsumedError(InvalidPurchaseStateError):
    """Raised when attempting to consume an already consumed purchase."""

    pass


class PurchaseAlreadyAcknowledgedError(InvalidPurchaseStateError):
    """Raised when attempting to acknowledge an already acknowledged purchase."""

    pass


class PurchaseManager:
    """Manages one-time product purchases.

    Handles purchase creation, validation, acknowledgment, and consumption.
    Thread-safe through underlying store.
    """

    def __init__(
        self,
        purchase_store: Optional[PurchaseStore] = None,
        product_repository: Optional[ProductRepository] = None,
    ):
        """Initialize purchase manager.

        Args:
            purchase_store: Purchase store instance (uses global if not provided)
            product_repository: Product repository instance (uses global if not provided)
        """
        self._purchase_store = (
            purchase_store if purchase_store is not None else get_purchase_store()
        )
        self._product_repository = (
            product_repository
            if product_repository is not None
            else get_product_repository()
        )

    def create_purchase(
        self,
        product_id: str,
        package_name: str,
        user_id: str,
        developer_payload: Optional[str] = None,
        token_prefix: Optional[str] = None,
        order_id_prefix: str = "GPA",
    ) -> ProductPurchaseRecord:
        """Create a new purchase for a one-time product.

        Args:
            product_id: Product ID to purchase
            package_name: Android package name
            user_id: User identifier
            developer_payload: Optional developer-specified payload
            token_prefix: Optional token prefix (defaults to config)
            order_id_prefix: Order ID prefix (default: "GPA")

        Returns:
            ProductPurchaseRecord

        Raises:
            ProductNotFoundError: If product_id not found
            ValueError: If invalid parameters
        """
        # Validate product exists
        product = self._product_repository.get_by_id(product_id)

        # Generate unique identifiers
        token = generate_purchase_token(prefix=token_prefix)
        order_id = generate_order_id(prefix=order_id_prefix)

        # Get current time
        purchase_time_millis = int(time.time() * 1000)

        # Get price from product definition
        price_amount_micros = product.price_micros
        price_currency_code = product.currency

        # Create purchase record
        purchase = ProductPurchaseRecord(
            token=token,
            product_id=product_id,
            package_name=package_name,
            user_id=user_id,
            purchase_state=PurchaseState.PURCHASED,
            consumption_state=ConsumptionState.NOT_CONSUMED,
            acknowledgement_state=AcknowledgementState.NOT_ACKNOWLEDGED,
            purchase_time_millis=purchase_time_millis,
            order_id=order_id,
            price_amount_micros=price_amount_micros,
            price_currency_code=price_currency_code,
            developer_payload=developer_payload,
        )

        # Store purchase
        self._purchase_store.add(purchase)

        return purchase

    def get_purchase(self, token: str) -> ProductPurchaseRecord:
        """Get purchase by token.

        Args:
            token: Purchase token

        Returns:
            ProductPurchaseRecord

        Raises:
            PurchaseNotFoundError: If purchase not found
        """
        return self._purchase_store.get_by_token(token)

    def find_purchase(self, token: str) -> Optional[ProductPurchaseRecord]:
        """Find purchase by token (returns None if not found).

        Args:
            token: Purchase token

        Returns:
            ProductPurchaseRecord if found, None otherwise
        """
        return self._purchase_store.find_by_token(token)

    def validate_purchase(self, token: str) -> bool:
        """Validate that a purchase token is valid and active.

        Args:
            token: Purchase token to validate

        Returns:
            True if purchase is valid and in PURCHASED state
        """
        # Validate token format
        if not validate_token(token, token_type="purchase"):
            return False

        # Check if purchase exists
        purchase = self._purchase_store.find_by_token(token)
        if purchase is None:
            return False

        # Check if purchase is in valid state
        return purchase.purchase_state == PurchaseState.PURCHASED

    def acknowledge_purchase(
        self, token: str, raise_if_already_acknowledged: bool = True
    ) -> ProductPurchaseRecord:
        """Acknowledge a purchase.

        Args:
            token: Purchase token
            raise_if_already_acknowledged: If True, raise exception if already acknowledged

        Returns:
            Updated ProductPurchaseRecord

        Raises:
            PurchaseNotFoundError: If purchase not found
            PurchaseAlreadyAcknowledgedError: If already acknowledged and raise_if_already_acknowledged=True
        """
        purchase = self._purchase_store.get_by_token(token)

        # Check if already acknowledged
        if purchase.acknowledgement_state == AcknowledgementState.ACKNOWLEDGED:
            if raise_if_already_acknowledged:
                raise PurchaseAlreadyAcknowledgedError(
                    f"Purchase {token} is already acknowledged"
                )
            return purchase

        # Acknowledge purchase
        purchase.acknowledge()

        return purchase

    def consume_purchase(
        self, token: str, raise_if_already_consumed: bool = True
    ) -> ProductPurchaseRecord:
        """Consume a purchase.

        A purchase can only be consumed once. Consumed purchases cannot be consumed again.

        Args:
            token: Purchase token
            raise_if_already_consumed: If True, raise exception if already consumed

        Returns:
            Updated ProductPurchaseRecord

        Raises:
            PurchaseNotFoundError: If purchase not found
            PurchaseAlreadyConsumedError: If already consumed and raise_if_already_consumed=True
        """
        purchase = self._purchase_store.get_by_token(token)

        # Check if already consumed
        if purchase.consumption_state == ConsumptionState.CONSUMED:
            if raise_if_already_consumed:
                raise PurchaseAlreadyConsumedError(
                    f"Purchase {token} is already consumed"
                )
            return purchase

        # Consume purchase
        purchase.consume()

        return purchase

    def cancel_purchase(
        self, token: str, reason: Optional[str] = None
    ) -> ProductPurchaseRecord:
        """Cancel a purchase.

        Args:
            token: Purchase token
            reason: Reason for cancellation

        Returns:
            Updated ProductPurchaseRecord

        Raises:
            PurchaseNotFoundError: If purchase not found
        """
        purchase = self._purchase_store.get_by_token(token)

        # Update purchase state
        purchase.set_purchase_state(PurchaseState.CANCELED, reason=reason)

        return purchase

    def get_user_purchases(self, user_id: str) -> list[ProductPurchaseRecord]:
        """Get all purchases for a user.

        Args:
            user_id: User identifier

        Returns:
            List of ProductPurchaseRecord
        """
        return self._purchase_store.get_by_user(user_id)

    def get_package_purchases(self, package_name: str) -> list[ProductPurchaseRecord]:
        """Get all purchases for a package.

        Args:
            package_name: Package name

        Returns:
            List of ProductPurchaseRecord
        """
        return self._purchase_store.get_by_package(package_name)


# Global instance
_purchase_manager: Optional[PurchaseManager] = None


def get_purchase_manager() -> PurchaseManager:
    """Get global purchase manager instance.

    Returns:
        PurchaseManager singleton instance
    """
    global _purchase_manager
    if _purchase_manager is None:
        _purchase_manager = PurchaseManager()
    return _purchase_manager


def reset_purchase_manager() -> None:
    """Reset global purchase manager instance (useful for testing)."""
    global _purchase_manager
    _purchase_manager = None
