"""Tests for subscription groups, tiers and replacement chains."""

import pytest

from iap_emulator.models.product import ProductDefinition
from iap_emulator.models.subscription import PendingChange, SubscriptionRecord


def make_product(**overrides) -> ProductDefinition:
    fields = {
        "id": "premium.personal.yearly",
        "type": "subs",
        "title": "Premium",
        "description": "Premium plan",
        "price_micros": 29990000,
        "billing_period": "P1Y",
    }
    return ProductDefinition(**(fields | overrides))


def make_record(token: str = "token-1", **overrides) -> SubscriptionRecord:
    fields = {
        "token": token,
        "subscription_id": "premium.personal.yearly",
        "package_name": "com.example.app",
        "user_id": "user-1",
        "start_time_millis": 1_000,
        "expiry_time_millis": 2_000,
        "purchase_time_millis": 1_000,
        "order_id": f"GPA.{token}",
        "price_amount_micros": 29990000,
    }
    return SubscriptionRecord(**(fields | overrides))


class TestCatalogMetadata:
    def test_existing_catalog_entry_without_group_is_valid(self):
        product = make_product()

        assert product.subscription_group_id is None
        assert product.tier is None

    def test_missing_group_defaults_to_sku_id(self):
        assert make_product().effective_group_id == "premium.personal.yearly"

    def test_explicit_group_and_tier_are_kept(self):
        product = make_product(subscription_group_id="premium", tier=2)

        assert product.effective_group_id == "premium"
        assert product.tier == 2

    def test_negative_tier_is_rejected(self):
        with pytest.raises(ValueError):
            make_product(tier=-1)


class TestRecordChainFields:
    def test_record_defaults_to_single_sku_group_and_own_chain(self):
        record = make_record()

        assert record.subscription_group_id == "premium.personal.yearly"
        assert record.original_token == "token-1"
        assert record.predecessor_token is None
        assert record.successor_token is None
        assert record.pending_change is None

    def test_explicit_group_and_original_token_are_kept(self):
        record = make_record(
            "token-2", subscription_group_id="premium", original_token="token-1"
        )

        assert record.subscription_group_id == "premium"
        assert record.original_token == "token-1"

    def test_pending_change_holds_target_and_time(self):
        change = PendingChange(
            target_subscription_id="premium.family.yearly", effective_time_millis=5_000
        )

        assert make_record(pending_change=change).pending_change.mode == "deferred"
