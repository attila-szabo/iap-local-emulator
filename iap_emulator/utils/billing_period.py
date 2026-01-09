"""Billing period parsing utilities.

Parses ISO 8601 duration strings used in Google Play subscriptions
and converts them to milliseconds for time calculations.
"""

import re
from datetime import timedelta

# Milliseconds in common time units
MILLIS_PER_SECOND = 1000
MILLIS_PER_MINUTE = 60 * MILLIS_PER_SECOND
MILLIS_PER_HOUR = 60 * MILLIS_PER_MINUTE
MILLIS_PER_DAY = 24 * MILLIS_PER_HOUR
MILLIS_PER_WEEK = 7 * MILLIS_PER_DAY
MILLIS_PER_MONTH = 30 * MILLIS_PER_DAY  # Standard approximation for billing
MILLIS_PER_YEAR = 365 * MILLIS_PER_DAY  # Standard approximation for billing


def parse_billing_period(period: str) -> int:
    """Parse ISO 8601 duration string to milliseconds.

    Supports common billing period formats used by Google Play:
    - P[n]D - days (e.g., P7D = 7 days)
    - P[n]W - weeks (e.g., P1W = 1 week)
    - P[n]M - months (e.g., P1M = 1 month = 30 days)
    - P[n]Y - years (e.g., P1Y = 1 year = 365 days)

    Note: Months are approximated as 30 days and years as 365 days,
    consistent with Google Play billing calculations.

    Args:
        period: ISO 8601 duration string (e.g., "P1M", "P1Y", "P7D")

    Returns:
        Duration in milliseconds

    Raises:
        ValueError: If the period string is invalid or unsupported

    Examples:
        >>> parse_billing_period("P1D")
        86400000  # 1 day in milliseconds

        >>> parse_billing_period("P1W")
        604800000  # 1 week in milliseconds

        >>> parse_billing_period("P1M")
        2592000000  # 1 month (30 days) in milliseconds

        >>> parse_billing_period("P1Y")
        31536000000  # 1 year (365 days) in milliseconds
    """
    if not period or not isinstance(period, str):
        raise ValueError("Period must be a non-empty string")

    period = period.strip().upper()

    if not period.startswith("P"):
        raise ValueError(f"Invalid period format: '{period}'. Must start with 'P'")

    # Remove the 'P' prefix
    duration_str = period[1:]

    if not duration_str:
        raise ValueError(f"Invalid period format: '{period}'. No duration specified")

    # Pattern for simple periods: P[n]D, P[n]W, P[n]M, P[n]Y
    # where [n] is an optional number (defaults to 1)
    pattern = r'^(\d+)?([DWMY])$'
    match = re.match(pattern, duration_str)

    if not match:
        raise ValueError(
            f"Unsupported period format: '{period}'. "
            "Supported formats: P[n]D, P[n]W, P[n]M, P[n]Y"
        )

    # Extract number and unit
    number_str, unit = match.groups()
    number = int(number_str) if number_str else 1

    if number <= 0:
        raise ValueError(f"Period number must be positive, got: {number}")

    # Convert to milliseconds
    if unit == "D":
        return number * MILLIS_PER_DAY
    elif unit == "W":
        return number * MILLIS_PER_WEEK
    elif unit == "M":
        return number * MILLIS_PER_MONTH
    elif unit == "Y":
        return number * MILLIS_PER_YEAR
    else:
        # Should never reach here due to regex pattern
        raise ValueError(f"Unsupported unit: {unit}")


def billing_period_to_timedelta(period: str) -> timedelta:
    """Convert ISO 8601 duration string to Python timedelta.

    Args:
        period: ISO 8601 duration string (e.g., "P1M", "P1Y")

    Returns:
        timedelta object representing the duration

    Raises:
        ValueError: If the period string is invalid

    Examples:
        >>> billing_period_to_timedelta("P1D")
        timedelta(days=1)

        >>> billing_period_to_timedelta("P1M")
        timedelta(days=30)
    """
    millis = parse_billing_period(period)
    # Convert milliseconds to seconds for timedelta
    seconds = millis / 1000
    return timedelta(seconds=seconds)


def format_billing_period(millis: int) -> str:
    """Convert milliseconds back to ISO 8601 duration string.

    Attempts to format as the most appropriate unit:
    - Exact years -> P[n]Y
    - Exact months -> P[n]M
    - Exact weeks -> P[n]W
    - Otherwise -> P[n]D

    Args:
        millis: Duration in milliseconds

    Returns:
        ISO 8601 duration string

    Raises:
        ValueError: If milliseconds is negative

    Examples:
        >>> format_billing_period(86400000)
        'P1D'

        >>> format_billing_period(2592000000)
        'P1M'

        >>> format_billing_period(31536000000)
        'P1Y'
    """
    if millis < 0:
        raise ValueError("Milliseconds must be non-negative")

    if millis == 0:
        return "P0D"

    # Try to format as years
    if millis % MILLIS_PER_YEAR == 0:
        years = millis // MILLIS_PER_YEAR
        return f"P{years}Y"

    # Try to format as months
    if millis % MILLIS_PER_MONTH == 0:
        months = millis // MILLIS_PER_MONTH
        return f"P{months}M"

    # Try to format as weeks
    if millis % MILLIS_PER_WEEK == 0:
        weeks = millis // MILLIS_PER_WEEK
        return f"P{weeks}W"

    # Format as days
    days = millis // MILLIS_PER_DAY
    return f"P{days}D"


def validate_billing_period(period: str) -> bool:
    """Validate that a string is a valid billing period format.

    Args:
        period: String to validate

    Returns:
        True if valid, False otherwise

    Examples:
        >>> validate_billing_period("P1M")
        True

        >>> validate_billing_period("invalid")
        False
    """
    try:
        parse_billing_period(period)
        return True
    except (ValueError, TypeError):
        return False


def get_common_billing_periods() -> dict[str, int]:
    """Get common billing periods and their millisecond values.

    Returns:
        Dictionary mapping period strings to milliseconds

    Examples:
        >>> periods = get_common_billing_periods()
        >>> periods["P1W"]
        604800000
    """
    return {
        "P1D": MILLIS_PER_DAY,
        "P7D": 7 * MILLIS_PER_DAY,
        "P1W": MILLIS_PER_WEEK,
        "P2W": 2 * MILLIS_PER_WEEK,
        "P1M": MILLIS_PER_MONTH,
        "P2M": 2 * MILLIS_PER_MONTH,
        "P3M": 3 * MILLIS_PER_MONTH,
        "P6M": 6 * MILLIS_PER_MONTH,
        "P1Y": MILLIS_PER_YEAR,
    }


def compare_billing_periods(period1: str, period2: str) -> int:
    """Compare two billing periods.

    Args:
        period1: First period string
        period2: Second period string

    Returns:
        -1 if period1 < period2
         0 if period1 == period2
         1 if period1 > period2

    Raises:
        ValueError: If either period is invalid

    Examples:
        >>> compare_billing_periods("P1M", "P1Y")
        -1

        >>> compare_billing_periods("P1M", "P1M")
        0
    """
    millis1 = parse_billing_period(period1)
    millis2 = parse_billing_period(period2)

    if millis1 < millis2:
        return -1
    elif millis1 > millis2:
        return 1
    else:
        return 0
