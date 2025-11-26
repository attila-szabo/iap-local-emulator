"""Token and order ID generation utilities.

Generates unique tokens and order IDs for purchases and subscriptions
in a format compatible with Google Play Billing.
"""

import random
import re
import time
import uuid
from typing import Optional

from iap_emulator.config import get_config


def generate_purchase_token(prefix: Optional[str] = None) -> str:
    """Generate a unique purchase token.

    Format: {prefix}_purchase_{uuid}_{timestamp}
    Example: emulator_purchase_a1b2c3d4e5f6g7h8_1700000000000

    Args:
        prefix: Token prefix (defaults to config.emulator_settings.token_prefix)

    Returns:
        Unique purchase token string
    """
    if prefix is None:
        config = get_config()
        prefix = config.emulator_settings.token_prefix

    # Generate UUID hex (no dashes)
    token_id = uuid.uuid4().hex[:16]  # 16 character hex string

    # Current timestamp in milliseconds
    timestamp = int(time.time() * 1000)

    return f"{prefix}_purchase_{token_id}_{timestamp}"


def generate_subscription_token(prefix: Optional[str] = None) -> str:
    """Generate a unique subscription token.

    Format: {prefix}_sub_{uuid}_{timestamp}
    Example: emulator_sub_a1b2c3d4e5f6g7h8_1700000000000

    Args:
        prefix: Token prefix (defaults to config.emulator_settings.token_prefix)

    Returns:
        Unique subscription token string
    """
    if prefix is None:
        config = get_config()
        prefix = config.emulator_settings.token_prefix

    # Generate UUID hex (no dashes)
    token_id = uuid.uuid4().hex[:16]  # 16 character hex string

    # Current timestamp in milliseconds
    timestamp = int(time.time() * 1000)

    return f"{prefix}_sub_{token_id}_{timestamp}"


def generate_order_id(prefix: str = "GPA") -> str:
    """Generate a Google Play-style order ID.

    Format: {prefix}.{rand}-{rand}-{rand}-{rand}
    Example: GPA.1234-5678-9012-3456

    Args:
        prefix: Order ID prefix (default: "GPA" for Google Play)

    Returns:
        Order ID string
    """
    # Generate 4 random 4-digit numbers
    parts = [random.randint(1000, 9999) for _ in range(4)]

    return f"{prefix}.{parts[0]}-{parts[1]}-{parts[2]}-{parts[3]}"


def validate_token(token: str, token_type: Optional[str] = None) -> bool:
    """Validate token format.

    Args:
        token: Token string to validate
        token_type: Expected type ("purchase" or "subscription"), or None for any

    Returns:
        True if token format is valid, False otherwise
    """
    if not token or not isinstance(token, str):
        return False

    # Basic pattern: prefix_type_uuid_timestamp
    # Example: emulator_purchase_a1b2c3d4e5f6g7h8_1700000000000
    pattern = r'^[a-zA-Z0-9_-]+_(purchase|sub)_[a-f0-9]{16}_\d{13}$'

    if not re.match(pattern, token):
        return False

    # If specific type requested, validate it
    if token_type:
        if token_type == "purchase" and "_purchase_" not in token:
            return False
        if token_type == "subscription" and "_sub_" not in token:
            return False

    return True


def validate_order_id(order_id: str) -> bool:
    """Validate order ID format.

    Args:
        order_id: Order ID string to validate

    Returns:
        True if order ID format is valid, False otherwise
    """
    if not order_id or not isinstance(order_id, str):
        return False

    # Pattern: PREFIX.NNNN-NNNN-NNNN-NNNN
    # Example: GPA.1234-5678-9012-3456
    pattern = r'^[A-Z]{2,4}\.\d{4}-\d{4}-\d{4}-\d{4}$'

    return bool(re.match(pattern, order_id))


def extract_token_timestamp(token: str) -> Optional[int]:
    """Extract timestamp from token.

    Args:
        token: Token string

    Returns:
        Timestamp in milliseconds, or None if invalid token
    """
    if not validate_token(token):
        return None

    try:
        # Token format: prefix_type_uuid_timestamp
        parts = token.split("_")
        timestamp = int(parts[-1])
        return timestamp
    except (IndexError, ValueError):
        return None


def extract_token_type(token: str) -> Optional[str]:
    """Extract token type from token.

    Args:
        token: Token string

    Returns:
        "purchase" or "subscription", or None if invalid token
    """
    if not validate_token(token):
        return None

    if "_purchase_" in token:
        return "purchase"
    elif "_sub_" in token:
        return "subscription"

    return None


def is_purchase_token(token: str) -> bool:
    """Check if token is a purchase token.

    Args:
        token: Token string

    Returns:
        True if token is a valid purchase token
    """
    return validate_token(token, token_type="purchase")


def is_subscription_token(token: str) -> bool:
    """Check if token is a subscription token.

    Args:
        token: Token string

    Returns:
        True if token is a valid subscription token
    """
    return validate_token(token, token_type="subscription")
