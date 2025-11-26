"""Tests for ProductRepository - subscription loading and lookup."""

import pytest

from iap_emulator.repositories.product_repository import (
    ProductNotFoundError,
    ProductRepository,
    get_product_repository,
)


@pytest.fixture
def repo():
    """Create a ProductRepository instance for testing."""
    return ProductRepository()


class TestProductRepositoryBasics:
    """Test basic repository functionality."""

    def test_repository_loads_successfully(self, repo):
        """Test that repository loads without errors."""
        assert repo is not None
        assert len(repo) > 0

    def test_repository_has_subscriptions(self, repo):
        """Test that repository contains subscription definitions."""
        all_subs = repo.get_all_subscriptions()
        assert len(all_subs) > 0
        assert all(hasattr(sub, "id") for sub in all_subs)
        assert all(hasattr(sub, "title") for sub in all_subs)

    def test_get_all_subscription_ids(self, repo):
        """Test getting all subscription IDs."""
        sub_ids = repo.get_all_subscription_ids()
        assert isinstance(sub_ids, list)
        assert len(sub_ids) > 0
        assert all(isinstance(sid, str) for sid in sub_ids)

    def test_get_subscription_count(self, repo):
        """Test subscription count matches actual subscriptions."""
        count = repo.get_subscription_count()
        all_subs = repo.get_all_subscriptions()
        assert count == len(all_subs)


class TestProductLookup:
    """Test product lookup methods."""

    def test_get_by_id_success(self, repo):
        """Test successful lookup by ID."""
        product = repo.get_by_id("premium.personal.yearly")
        assert product is not None
        assert product.id == "premium.personal.yearly"
        assert hasattr(product, "title")
        assert hasattr(product, "price_micros")
        assert hasattr(product, "currency")
        assert hasattr(product, "billing_period")

    def test_get_by_id_not_found_raises_error(self, repo):
        """Test that get_by_id raises ProductNotFoundError when not found."""
        with pytest.raises(ProductNotFoundError) as exc_info:
            repo.get_by_id("non.existent.product")
        assert "not found" in str(exc_info.value).lower()

    def test_find_by_id_returns_none_when_not_found(self, repo):
        """Test that find_by_id returns None when product not found."""
        result = repo.find_by_id("non.existent.product")
        assert result is None

    def test_find_by_id_success(self, repo):
        """Test successful find_by_id."""
        product = repo.find_by_id("premium.personal.yearly")
        assert product is not None
        assert product.id == "premium.personal.yearly"

    def test_exists_method(self, repo):
        """Test the exists() method."""
        assert repo.exists("premium.personal.yearly") is True
        assert repo.exists("premium.family.yearly") is True
        assert repo.exists("non.existent") is False

    def test_contains_operator(self, repo):
        """Test the 'in' operator (contains)."""
        assert "premium.personal.yearly" in repo
        assert "premium.family.yearly" in repo
        assert "non.existent" not in repo


class TestProductFiltering:
    """Test product filtering methods."""

    def test_filter_by_type(self, repo):
        """Test filtering subscriptions by type."""
        subs_type = repo.get_subscriptions_by_type("subs")
        assert isinstance(subs_type, list)
        assert all(sub.type == "subs" for sub in subs_type)

    def test_filter_by_base_plan(self, repo):
        """Test filtering subscriptions by base plan."""
        personal_plans = repo.get_subscriptions_by_base_plan("personal-yearly")
        assert isinstance(personal_plans, list)
        assert all(sub.base_plan_id == "personal-yearly" for sub in personal_plans)

    def test_filter_by_base_plan_empty_result(self, repo):
        """Test filtering by non-existent base plan returns empty list."""
        result = repo.get_subscriptions_by_base_plan("non-existent-plan")
        assert result == []


class TestProductDetails:
    """Test product detail fields."""

    def test_product_has_required_fields(self, repo):
        """Test that products have all required fields."""
        product = repo.get_by_id("premium.personal.yearly")

        # Required fields
        assert product.id is not None
        assert product.title is not None
        assert product.type is not None
        assert product.price_micros > 0
        assert product.currency is not None
        assert product.billing_period is not None
        assert product.base_plan_id is not None

    def test_product_optional_fields(self, repo):
        """Test that optional fields are accessible."""
        product = repo.get_by_id("premium.personal.yearly")

        # Optional fields (may be None)
        assert hasattr(product, "trial_period")
        assert hasattr(product, "grace_period")
        assert hasattr(product, "offer_id")
        assert hasattr(product, "max_users")
        assert hasattr(product, "features")

    def test_product_features_list(self, repo):
        """Test that product features is a list."""
        product = repo.get_by_id("premium.personal.yearly")
        assert isinstance(product.features, list)


class TestSingletonPattern:
    """Test singleton pattern for repository."""

    def test_get_product_repository_returns_singleton(self):
        """Test that get_product_repository returns the same instance."""
        repo1 = get_product_repository()
        repo2 = get_product_repository()
        assert repo1 is repo2

    def test_singleton_is_functional(self):
        """Test that singleton instance is functional."""
        repo = get_product_repository()
        assert len(repo) > 0
        assert repo.get_subscription_count() > 0


class TestRepositoryLength:
    """Test repository length and iteration."""

    def test_len_operator(self, repo):
        """Test __len__ operator."""
        length = len(repo)
        count = repo.get_subscription_count()
        assert length == count

    def test_repository_not_empty(self, repo):
        """Test that repository is not empty."""
        assert len(repo) > 0


class TestMultipleProducts:
    """Test working with multiple products."""

    def test_multiple_products_exist(self, repo):
        """Test that repository contains multiple products."""
        all_subs = repo.get_all_subscriptions()
        assert len(all_subs) >= 2  # At least 2 subscriptions

    def test_products_have_unique_ids(self, repo):
        """Test that all product IDs are unique."""
        all_subs = repo.get_all_subscriptions()
        ids = [sub.id for sub in all_subs]
        assert len(ids) == len(set(ids))  # All IDs are unique

    def test_can_lookup_all_products(self, repo):
        """Test that all products can be looked up by their ID."""
        all_subs = repo.get_all_subscriptions()
        for sub in all_subs:
            found = repo.get_by_id(sub.id)
            assert found is not None
            assert found.id == sub.id


# Parametrized tests for multiple product IDs
@pytest.mark.parametrize("product_id", [
    "premium.personal.yearly",
    "premium.family.yearly",
])
def test_known_products_exist(product_id):
    """Test that known products exist in repository."""
    repo = get_product_repository()
    assert repo.exists(product_id)
    product = repo.get_by_id(product_id)
    assert product.id == product_id


@pytest.mark.parametrize("invalid_id", [
    "non.existent.product",
    "invalid_id",
    "",
    "premium.invalid.plan",
])
def test_invalid_products_not_found(invalid_id):
    """Test that invalid product IDs are not found."""
    repo = get_product_repository()
    assert repo.exists(invalid_id) is False
    assert repo.find_by_id(invalid_id) is None

    with pytest.raises(ProductNotFoundError):
        repo.get_by_id(invalid_id)
