"""Product repository - loads and provides access to product definitions.

Loads from config/products.yaml and provides lookup methods.
"""

from typing import Dict, List, Optional

from iap_emulator.config import Config, get_config
from iap_emulator.models import ProductDefinition


class ProductNotFoundError(Exception):
    """Raised when a product is not found in the repository."""

    pass


class ProductRepository:
    """Repository for product and subscription definitions.

    Loads product definitions from configuration and provides fast lookup.
    Thread-safe for read operations.
    """

    def __init__(self, config: Optional[Config] = None):
        """Initialize product repository.

        Args:
            config: Configuration instance. If not provided, uses global config.
        """
        self._config = config or get_config()
        self._products_by_id: Dict[str, ProductDefinition] = {}
        self._load_products()

    def _load_products(self) -> None:
        """Load product definitions from configuration into indexed dictionary."""
        self._products_by_id.clear()

        # Index one-time products by ID for fast lookup
        for product in self._config.products.products:
            self._products_by_id[product.id] = product

        # Index subscriptions by ID for fast lookup
        for product in self._config.products.subscriptions:
            self._products_by_id[product.id] = product

    def get_by_id(self, product_id: str) -> ProductDefinition:
        """Get product definition by ID.

        Args:
            product_id: Product or subscription ID (e.g., "premium.personal.yearly")

        Returns:
            ProductDefinition

        Raises:
            ProductNotFoundError: If product ID not found
        """
        product = self._products_by_id.get(product_id)
        if product is None:
            raise ProductNotFoundError(
                f"Product not found: {product_id}. "
                f"Available products: {list(self._products_by_id.keys())}"
            )
        return product

    def find_by_id(self, product_id: str) -> Optional[ProductDefinition]:
        """Find product definition by ID (returns None if not found).

        Args:
            product_id: Product or subscription ID

        Returns:
            ProductDefinition if found, None otherwise
        """
        return self._products_by_id.get(product_id)

    def get_all_subscriptions(self) -> List[ProductDefinition]:
        """Get all subscription definitions.

        Returns:
            List of all ProductDefinition objects
        """
        return list(self._products_by_id.values())

    def get_all_subscription_ids(self) -> List[str]:
        """Get list of all subscription IDs.

        Returns:
            List of subscription IDs
        """
        return list(self._products_by_id.keys())

    def exists(self, product_id: str) -> bool:
        """Check if product ID exists.

        Args:
            product_id: Product or subscription ID

        Returns:
            True if product exists, False otherwise
        """
        return product_id in self._products_by_id

    def get_subscription_count(self) -> int:
        """Get total number of subscriptions.

        Returns:
            Count of subscriptions
        """
        return len(self._products_by_id)

    def get_subscriptions_by_type(self, product_type: str) -> List[ProductDefinition]:
        """Get subscriptions filtered by type.

        Args:
            product_type: Product type ("inapp" or "subs")

        Returns:
            List of matching ProductDefinition objects
        """
        return [p for p in self._products_by_id.values() if p.type == product_type]

    def get_subscriptions_by_base_plan(self, base_plan_id: str) -> List[ProductDefinition]:
        """Get subscriptions with a specific base plan ID.

        Args:
            base_plan_id: Base plan identifier

        Returns:
            List of matching ProductDefinition objects
        """
        return [p for p in self._products_by_id.values() if p.base_plan_id == base_plan_id]

    def reload(self) -> None:
        """Reload product definitions from configuration.

        Useful when configuration file has been modified.
        """
        self._config.reload()
        self._load_products()

    def __len__(self) -> int:
        """Get number of products in repository."""
        return len(self._products_by_id)

    def __contains__(self, product_id: str) -> bool:
        """Check if product_id exists in repository."""
        return product_id in self._products_by_id

    def __repr__(self) -> str:
        """String representation of repository."""
        return f"ProductRepository(products={len(self._products_by_id)})"


# Global repository instance
_repository_instance: Optional[ProductRepository] = None


def get_product_repository(config: Optional[Config] = None) -> ProductRepository:
    """Get global product repository instance (singleton).

    Args:
        config: Optional configuration instance (only used on first call)

    Returns:
        ProductRepository instance
    """
    global _repository_instance
    if _repository_instance is None:
        _repository_instance = ProductRepository(config)
    return _repository_instance


def reload_product_repository() -> None:
    """Reload global product repository from configuration."""
    global _repository_instance
    if _repository_instance:
        _repository_instance.reload()
    else:
        _repository_instance = ProductRepository()
