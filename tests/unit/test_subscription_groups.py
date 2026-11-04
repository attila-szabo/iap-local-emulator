"""Tests for subscription groups, tiers and replacement chains."""

from unittest.mock import MagicMock, patch

import pytest

from iap_emulator.models.product import ProductDefinition
from iap_emulator.models.subscription import (
    PendingChange,
    SubscriptionRecord,
    SubscriptionState,
)
from iap_emulator.repositories.product_repository import ProductRepository
from iap_emulator.repositories.subscription_store import (
    ConflictingEntitlementError,
    SubscriptionNotFoundError,
    SubscriptionStore,
)
from iap_emulator.services.subscription_engine import (
    SubscriptionEngine,
    SubscriptionError,
)


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


@pytest.fixture
def store():
    return SubscriptionStore()


class TestGroupEntitlement:
    def test_unrelated_groups_coexist_for_one_user(self, store):
        store.add(make_record("a", subscription_id="app.one"))
        store.add(make_record("b", subscription_id="app.two"))

        assert store.get_current_in_group("com.example.app", "user-1", "app.one").token == "a"
        assert store.get_current_in_group("com.example.app", "user-1", "app.two").token == "b"

    def test_same_group_different_user_or_package_does_not_conflict(self, store):
        store.add(make_record("a"))
        store.add(make_record("b", user_id="user-2"))
        store.add(make_record("c", package_name="com.other.app"))

    def test_second_current_entitlement_in_group_is_rejected(self, store):
        store.add(make_record("a", subscription_group_id="premium"))

        with pytest.raises(ConflictingEntitlementError):
            store.add(
                make_record(
                    "b", subscription_id="premium.family", subscription_group_id="premium"
                )
            )

    def test_canceled_subscription_still_blocks_its_group(self, store):
        store.add(make_record("a", state=SubscriptionState.CANCELED))

        with pytest.raises(ConflictingEntitlementError):
            store.add(make_record("b"))

    def test_expired_subscription_does_not_block_its_group(self, store):
        store.add(make_record("a", state=SubscriptionState.EXPIRED))

        store.add(make_record("b"))

        assert store.get_current_in_group("com.example.app", "user-1", "premium.personal.yearly").token == "b"

    def test_no_current_entitlement_returns_none(self, store):
        assert store.get_current_in_group("com.example.app", "user-1", "none") is None


class TestReplacementChain:
    def build_chain(self, store):
        store.add(make_record("a", subscription_group_id="premium"))
        store.add(
            make_record(
                "b",
                subscription_group_id="premium",
                original_token="a",
                predecessor_token="a",
            )
        )
        store.add(
            make_record(
                "c",
                subscription_group_id="premium",
                original_token="a",
                predecessor_token="b",
            )
        )

    def test_replacement_links_successor_and_becomes_current(self, store):
        self.build_chain(store)

        assert store.get_by_token("a").successor_token == "b"
        assert store.get_by_token("b").successor_token == "c"
        current = store.get_current_in_group("com.example.app", "user-1", "premium")
        assert current.token == "c"

    @pytest.mark.parametrize("token", ["a", "b", "c"])
    def test_lineage_is_queryable_from_any_token(self, store, token):
        self.build_chain(store)

        assert [s.token for s in store.get_lineage(token)] == ["a", "b", "c"]

    def test_lineage_of_unreplaced_subscription_is_itself(self, store):
        store.add(make_record("solo"))

        assert [s.token for s in store.get_lineage("solo")] == ["solo"]

    def test_lineage_of_unknown_token_raises(self, store):
        with pytest.raises(SubscriptionNotFoundError):
            store.get_lineage("missing")

    def test_replacing_a_non_current_subscription_is_rejected(self, store):
        self.build_chain(store)

        with pytest.raises(ConflictingEntitlementError):
            store.add(
                make_record(
                    "d",
                    subscription_group_id="premium",
                    original_token="a",
                    predecessor_token="a",
                )
            )

    def test_unknown_predecessor_raises(self, store):
        with pytest.raises(SubscriptionNotFoundError):
            store.add(make_record("b", predecessor_token="ghost"))


class TestPendingAndCanceledQueries:
    def test_pending_change_query_returns_only_flagged_subscriptions(self, store):
        change = PendingChange(
            target_subscription_id="premium.family.yearly", effective_time_millis=5_000
        )
        store.add(make_record("a", subscription_id="app.one", pending_change=change))
        store.add(make_record("b", subscription_id="app.two"))

        assert [s.token for s in store.get_with_pending_changes()] == ["a"]

    def test_canceled_due_respects_expiry_and_state(self, store):
        store.add(make_record("due", subscription_id="a", state=SubscriptionState.CANCELED))
        store.add(
            make_record(
                "later",
                subscription_id="b",
                state=SubscriptionState.CANCELED,
                expiry_time_millis=9_000,
            )
        )
        store.add(make_record("active", subscription_id="c"))

        assert [s.token for s in store.get_canceled_due(2_000)] == ["due"]


@pytest.fixture
def engine(store):
    config = MagicMock()
    config.products.subscriptions = [
        make_product(id="premium.personal", subscription_group_id="premium", tier=1),
        make_product(id="premium.family", subscription_group_id="premium", tier=2),
        make_product(id="other.plan"),
    ]
    config.default_package_name = "com.example.app"
    with patch("iap_emulator.services.subscription_engine.get_config", return_value=config):
        yield SubscriptionEngine(
            subscription_store=store, product_repository=ProductRepository(config=config)
        )


class TestEngineGroups:
    def test_created_subscription_carries_catalog_group(self, engine):
        assert engine.create_subscription("premium.personal", "u").subscription_group_id == "premium"
        assert engine.create_subscription("other.plan", "u").subscription_group_id == "other.plan"

    def test_other_sku_of_same_group_is_rejected(self, engine):
        engine.create_subscription("premium.personal", "u")

        with pytest.raises(SubscriptionError, match="already has an active subscription"):
            engine.create_subscription("premium.family", "u")

    def test_unrelated_group_coexists(self, engine):
        engine.create_subscription("premium.personal", "u")

        assert engine.create_subscription("other.plan", "u").state == SubscriptionState.ACTIVE

    def test_replaces_token_extends_chain(self, engine):
        first = engine.create_subscription("premium.personal", "u")

        second = engine.create_subscription(
            "premium.family", "u", replaces_token=first.token
        )

        assert second.predecessor_token == first.token
        assert second.original_token == first.token
        assert engine.get_subscription(first.token).successor_token == second.token
