"""Tests for token generation utilities."""

import re
import time

import pytest

from iap_emulator.utils.token_generator import (
    extract_token_timestamp,
    extract_token_type,
    generate_order_id,
    generate_purchase_token,
    generate_subscription_token,
    is_purchase_token,
    is_subscription_token,
    validate_order_id,
    validate_token,
)


class TestPurchaseTokenGeneration:
    """Test purchase token generation."""

    def test_generate_purchase_token_format(self):
        """Test that purchase token has correct format."""
        token = generate_purchase_token()

        # Should contain '_purchase_'
        assert "_purchase_" in token

        # Should match pattern: prefix_purchase_uuid_timestamp
        pattern = r'^[a-zA-Z0-9_-]+_purchase_[a-f0-9]{16}_\d{13}$'
        assert re.match(pattern, token)

    def test_generate_purchase_token_uniqueness(self):
        """Test that generated tokens are unique."""
        tokens = [generate_purchase_token() for _ in range(100)]

        # All tokens should be unique
        assert len(tokens) == len(set(tokens))

    def test_generate_purchase_token_with_custom_prefix(self):
        """Test purchase token generation with custom prefix."""
        token = generate_purchase_token(prefix="custom")

        assert token.startswith("custom_purchase_")

    def test_generate_purchase_token_with_default_prefix(self):
        """Test purchase token uses config default prefix."""
        token = generate_purchase_token()

        # Should start with emulator (from config)
        assert token.startswith("emulator_purchase_")

    def test_generate_purchase_token_timestamp(self):
        """Test that token contains current timestamp."""
        before = int(time.time() * 1000)
        token = generate_purchase_token()
        after = int(time.time() * 1000)

        # Extract timestamp from token
        timestamp = int(token.split("_")[-1])

        # Should be within the time window
        assert before <= timestamp <= after


class TestSubscriptionTokenGeneration:
    """Test subscription token generation."""

    def test_generate_subscription_token_format(self):
        """Test that subscription token has correct format."""
        token = generate_subscription_token()

        # Should contain '_sub_'
        assert "_sub_" in token

        # Should match pattern: prefix_sub_uuid_timestamp
        pattern = r'^[a-zA-Z0-9_-]+_sub_[a-f0-9]{16}_\d{13}$'
        assert re.match(pattern, token)

    def test_generate_subscription_token_uniqueness(self):
        """Test that generated tokens are unique."""
        tokens = [generate_subscription_token() for _ in range(100)]

        # All tokens should be unique
        assert len(tokens) == len(set(tokens))

    def test_generate_subscription_token_with_custom_prefix(self):
        """Test subscription token generation with custom prefix."""
        token = generate_subscription_token(prefix="custom")

        assert token.startswith("custom_sub_")

    def test_generate_subscription_token_with_default_prefix(self):
        """Test subscription token uses config default prefix."""
        token = generate_subscription_token()

        # Should start with emulator (from config)
        assert token.startswith("emulator_sub_")

    def test_generate_subscription_token_timestamp(self):
        """Test that token contains current timestamp."""
        before = int(time.time() * 1000)
        token = generate_subscription_token()
        after = int(time.time() * 1000)

        # Extract timestamp from token
        timestamp = int(token.split("_")[-1])

        # Should be within the time window
        assert before <= timestamp <= after


class TestOrderIDGeneration:
    """Test order ID generation."""

    def test_generate_order_id_format(self):
        """Test that order ID has correct format."""
        order_id = generate_order_id()

        # Should match pattern: GPA.NNNN-NNNN-NNNN-NNNN
        pattern = r'^GPA\.\d{4}-\d{4}-\d{4}-\d{4}$'
        assert re.match(pattern, order_id)

    def test_generate_order_id_uniqueness(self):
        """Test that generated order IDs are mostly unique."""
        order_ids = [generate_order_id() for _ in range(100)]

        # Most should be unique (with 10000^4 possibilities, collisions are rare)
        assert len(set(order_ids)) >= 95  # Allow for some collisions

    def test_generate_order_id_with_custom_prefix(self):
        """Test order ID generation with custom prefix."""
        order_id = generate_order_id(prefix="TEST")

        assert order_id.startswith("TEST.")

    def test_generate_order_id_default_prefix(self):
        """Test order ID uses GPA prefix by default."""
        order_id = generate_order_id()

        assert order_id.startswith("GPA.")

    def test_generate_order_id_number_ranges(self):
        """Test that order ID numbers are 4 digits."""
        order_id = generate_order_id()

        # Extract the numbers
        parts = order_id.split(".")[1].split("-")

        assert len(parts) == 4
        for part in parts:
            num = int(part)
            assert 1000 <= num <= 9999


class TestTokenValidation:
    """Test token validation."""

    def test_validate_token_valid_purchase_token(self):
        """Test validation of valid purchase token."""
        token = generate_purchase_token()
        assert validate_token(token) is True

    def test_validate_token_valid_subscription_token(self):
        """Test validation of valid subscription token."""
        token = generate_subscription_token()
        assert validate_token(token) is True

    def test_validate_token_with_type_purchase(self):
        """Test validation with specific purchase type."""
        purchase_token = generate_purchase_token()
        sub_token = generate_subscription_token()

        assert validate_token(purchase_token, token_type="purchase") is True
        assert validate_token(sub_token, token_type="purchase") is False

    def test_validate_token_with_type_subscription(self):
        """Test validation with specific subscription type."""
        purchase_token = generate_purchase_token()
        sub_token = generate_subscription_token()

        assert validate_token(purchase_token, token_type="subscription") is False
        assert validate_token(sub_token, token_type="subscription") is True

    def test_validate_token_invalid_format(self):
        """Test validation of invalid token formats."""
        invalid_tokens = [
            "",
            "not_a_token",
            "emulator_purchase_",
            "emulator_purchase_tooshort_123",
            "emulator_purchase_invalid_uuid_1234567890123",
            "emulator_purchase_1234567890123456_notanumber",
            None,
            123,
        ]

        for token in invalid_tokens:
            assert validate_token(token) is False

    def test_validate_token_missing_parts(self):
        """Test validation of tokens with missing parts."""
        invalid_tokens = [
            "emulator_purchase",
            "emulator_purchase_abc123",
            "purchase_abc1234567890123_1234567890123",
        ]

        for token in invalid_tokens:
            assert validate_token(token) is False


class TestOrderIDValidation:
    """Test order ID validation."""

    def test_validate_order_id_valid(self):
        """Test validation of valid order ID."""
        order_id = generate_order_id()
        assert validate_order_id(order_id) is True

    def test_validate_order_id_custom_prefix(self):
        """Test validation of order ID with custom prefix."""
        order_id = "TEST.1234-5678-9012-3456"
        assert validate_order_id(order_id) is True

    def test_validate_order_id_invalid_format(self):
        """Test validation of invalid order ID formats."""
        invalid_order_ids = [
            "",
            "not_an_order_id",
            "GPA.123-456-789-012",  # Too few digits
            "GPA.12345-67890-12345-67890",  # Too many digits
            "GPA-1234-5678-9012-3456",  # Wrong separator
            "gpa.1234-5678-9012-3456",  # Lowercase prefix
            None,
            123,
        ]

        for order_id in invalid_order_ids:
            assert validate_order_id(order_id) is False


class TestTokenExtraction:
    """Test token information extraction."""

    def test_extract_token_timestamp_purchase(self):
        """Test extracting timestamp from purchase token."""
        before = int(time.time() * 1000)
        token = generate_purchase_token()
        after = int(time.time() * 1000)

        timestamp = extract_token_timestamp(token)

        assert timestamp is not None
        assert before <= timestamp <= after

    def test_extract_token_timestamp_subscription(self):
        """Test extracting timestamp from subscription token."""
        before = int(time.time() * 1000)
        token = generate_subscription_token()
        after = int(time.time() * 1000)

        timestamp = extract_token_timestamp(token)

        assert timestamp is not None
        assert before <= timestamp <= after

    def test_extract_token_timestamp_invalid(self):
        """Test extracting timestamp from invalid token."""
        timestamp = extract_token_timestamp("invalid_token")
        assert timestamp is None

    def test_extract_token_type_purchase(self):
        """Test extracting type from purchase token."""
        token = generate_purchase_token()
        token_type = extract_token_type(token)

        assert token_type == "purchase"

    def test_extract_token_type_subscription(self):
        """Test extracting type from subscription token."""
        token = generate_subscription_token()
        token_type = extract_token_type(token)

        assert token_type == "subscription"

    def test_extract_token_type_invalid(self):
        """Test extracting type from invalid token."""
        token_type = extract_token_type("invalid_token")
        assert token_type is None


class TestTokenHelpers:
    """Test token helper functions."""

    def test_is_purchase_token_valid(self):
        """Test is_purchase_token with valid purchase token."""
        token = generate_purchase_token()
        assert is_purchase_token(token) is True

    def test_is_purchase_token_subscription(self):
        """Test is_purchase_token with subscription token."""
        token = generate_subscription_token()
        assert is_purchase_token(token) is False

    def test_is_purchase_token_invalid(self):
        """Test is_purchase_token with invalid token."""
        assert is_purchase_token("invalid") is False

    def test_is_subscription_token_valid(self):
        """Test is_subscription_token with valid subscription token."""
        token = generate_subscription_token()
        assert is_subscription_token(token) is True

    def test_is_subscription_token_purchase(self):
        """Test is_subscription_token with purchase token."""
        token = generate_purchase_token()
        assert is_subscription_token(token) is False

    def test_is_subscription_token_invalid(self):
        """Test is_subscription_token with invalid token."""
        assert is_subscription_token("invalid") is False


class TestTokenDifferences:
    """Test differences between purchase and subscription tokens."""

    def test_purchase_and_subscription_tokens_are_different(self):
        """Test that purchase and subscription tokens are distinguishable."""
        purchase = generate_purchase_token()
        subscription = generate_subscription_token()

        # Tokens should be different
        assert purchase != subscription

        # Should have different types
        assert "_purchase_" in purchase
        assert "_sub_" in subscription

        # Validation should distinguish them
        assert is_purchase_token(purchase)
        assert not is_subscription_token(purchase)

        assert is_subscription_token(subscription)
        assert not is_purchase_token(subscription)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_validate_token_none(self):
        """Test validating None token."""
        assert validate_token(None) is False

    def test_validate_token_empty_string(self):
        """Test validating empty string token."""
        assert validate_token("") is False

    def test_validate_token_wrong_type(self):
        """Test validating non-string token."""
        assert validate_token(123) is False
        assert validate_token([]) is False
        assert validate_token({}) is False

    def test_validate_order_id_none(self):
        """Test validating None order ID."""
        assert validate_order_id(None) is False

    def test_validate_order_id_empty_string(self):
        """Test validating empty string order ID."""
        assert validate_order_id("") is False

    def test_validate_order_id_wrong_type(self):
        """Test validating non-string order ID."""
        assert validate_order_id(123) is False

    def test_extract_timestamp_malformed_token(self):
        """Test extracting timestamp from malformed token."""
        malformed_tokens = [
            "emulator_purchase_abc",
            "emulator_purchase_abc_notanumber",
            "",
            None,
        ]

        for token in malformed_tokens:
            assert extract_token_timestamp(token) is None

    def test_extract_type_malformed_token(self):
        """Test extracting type from malformed token."""
        malformed_tokens = [
            "emulator_unknown_abc_123",
            "invalid",
            "",
            None,
        ]

        for token in malformed_tokens:
            assert extract_token_type(token) is None


# Parametrized tests
@pytest.mark.parametrize("prefix", ["emulator", "test", "custom", "my_app"])
def test_purchase_token_with_various_prefixes(prefix):
    """Test purchase token generation with various prefixes."""
    token = generate_purchase_token(prefix=prefix)
    assert token.startswith(f"{prefix}_purchase_")
    assert validate_token(token)


@pytest.mark.parametrize("prefix", ["emulator", "test", "custom", "my_app"])
def test_subscription_token_with_various_prefixes(prefix):
    """Test subscription token generation with various prefixes."""
    token = generate_subscription_token(prefix=prefix)
    assert token.startswith(f"{prefix}_sub_")
    assert validate_token(token)


@pytest.mark.parametrize("prefix", ["GPA", "TEST", "DEV", "PROD"])
def test_order_id_with_various_prefixes(prefix):
    """Test order ID generation with various prefixes."""
    order_id = generate_order_id(prefix=prefix)
    assert order_id.startswith(f"{prefix}.")
    assert validate_order_id(order_id)


@pytest.mark.parametrize("count", [10, 50, 100])
def test_token_uniqueness_at_scale(count):
    """Test token uniqueness with different scales."""
    purchase_tokens = [generate_purchase_token() for _ in range(count)]
    sub_tokens = [generate_subscription_token() for _ in range(count)]

    # All should be unique
    assert len(purchase_tokens) == len(set(purchase_tokens))
    assert len(sub_tokens) == len(set(sub_tokens))

    # Purchase and subscription tokens should never overlap
    assert len(set(purchase_tokens) & set(sub_tokens)) == 0
