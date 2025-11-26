"""Utility functions and helpers for the emulator."""

from iap_emulator.utils.billing_period import (
    billing_period_to_timedelta,
    compare_billing_periods,
    format_billing_period,
    get_common_billing_periods,
    parse_billing_period,
    validate_billing_period,
)
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

__all__ = [
    # Token generation
    "generate_purchase_token",
    "generate_subscription_token",
    "generate_order_id",
    # Token validation
    "validate_token",
    "validate_order_id",
    "is_purchase_token",
    "is_subscription_token",
    # Token extraction
    "extract_token_timestamp",
    "extract_token_type",
    # Billing period parsing
    "parse_billing_period",
    "billing_period_to_timedelta",
    "format_billing_period",
    "validate_billing_period",
    "get_common_billing_periods",
    "compare_billing_periods",
]
