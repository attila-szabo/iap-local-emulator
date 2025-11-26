"""Tests for billing period parsing utilities."""

from datetime import timedelta

import pytest

from iap_emulator.utils.billing_period import (
    MILLIS_PER_DAY,
    MILLIS_PER_MONTH,
    MILLIS_PER_WEEK,
    MILLIS_PER_YEAR,
    billing_period_to_timedelta,
    compare_billing_periods,
    format_billing_period,
    get_common_billing_periods,
    parse_billing_period,
    validate_billing_period,
)


class TestParseBillingPeriod:
    """Test parse_billing_period function."""

    def test_parse_daily_period(self):
        """Test parsing daily periods."""
        assert parse_billing_period("P1D") == MILLIS_PER_DAY
        assert parse_billing_period("P7D") == 7 * MILLIS_PER_DAY
        assert parse_billing_period("P30D") == 30 * MILLIS_PER_DAY

    def test_parse_weekly_period(self):
        """Test parsing weekly periods."""
        assert parse_billing_period("P1W") == MILLIS_PER_WEEK
        assert parse_billing_period("P2W") == 2 * MILLIS_PER_WEEK
        assert parse_billing_period("P4W") == 4 * MILLIS_PER_WEEK

    def test_parse_monthly_period(self):
        """Test parsing monthly periods."""
        assert parse_billing_period("P1M") == MILLIS_PER_MONTH
        assert parse_billing_period("P3M") == 3 * MILLIS_PER_MONTH
        assert parse_billing_period("P6M") == 6 * MILLIS_PER_MONTH
        assert parse_billing_period("P12M") == 12 * MILLIS_PER_MONTH

    def test_parse_yearly_period(self):
        """Test parsing yearly periods."""
        assert parse_billing_period("P1Y") == MILLIS_PER_YEAR
        assert parse_billing_period("P2Y") == 2 * MILLIS_PER_YEAR

    def test_parse_case_insensitive(self):
        """Test that parsing is case insensitive."""
        assert parse_billing_period("p1d") == MILLIS_PER_DAY
        assert parse_billing_period("p1m") == MILLIS_PER_MONTH
        assert parse_billing_period("p1y") == MILLIS_PER_YEAR

    def test_parse_with_whitespace(self):
        """Test parsing with leading/trailing whitespace."""
        assert parse_billing_period(" P1M ") == MILLIS_PER_MONTH
        assert parse_billing_period("\tP1Y\n") == MILLIS_PER_YEAR

    def test_parse_invalid_empty_string(self):
        """Test parsing empty string raises ValueError."""
        with pytest.raises(ValueError, match="must be a non-empty string"):
            parse_billing_period("")

    def test_parse_invalid_none(self):
        """Test parsing None raises ValueError."""
        with pytest.raises(ValueError, match="must be a non-empty string"):
            parse_billing_period(None)

    def test_parse_invalid_no_p_prefix(self):
        """Test parsing without 'P' prefix raises ValueError."""
        with pytest.raises(ValueError, match="Must start with 'P'"):
            parse_billing_period("1M")

    def test_parse_invalid_no_duration(self):
        """Test parsing 'P' only raises ValueError."""
        with pytest.raises(ValueError, match="No duration specified"):
            parse_billing_period("P")

    def test_parse_invalid_format(self):
        """Test parsing invalid formats raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported period format"):
            parse_billing_period("P1X")

        with pytest.raises(ValueError, match="Unsupported period format"):
            parse_billing_period("P1M2D")

    def test_parse_zero_number(self):
        """Test parsing zero number raises ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            parse_billing_period("P0D")

    def test_parse_negative_number(self):
        """Test parsing negative number raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported period format"):
            parse_billing_period("P-1D")

    def test_parse_large_numbers(self):
        """Test parsing large numbers."""
        assert parse_billing_period("P365D") == 365 * MILLIS_PER_DAY
        assert parse_billing_period("P100M") == 100 * MILLIS_PER_MONTH


class TestBillingPeriodToTimedelta:
    """Test billing_period_to_timedelta function."""

    def test_convert_to_timedelta_days(self):
        """Test conversion to timedelta for days."""
        td = billing_period_to_timedelta("P1D")
        assert td == timedelta(days=1)

        td = billing_period_to_timedelta("P7D")
        assert td == timedelta(days=7)

    def test_convert_to_timedelta_weeks(self):
        """Test conversion to timedelta for weeks."""
        td = billing_period_to_timedelta("P1W")
        assert td == timedelta(weeks=1)

    def test_convert_to_timedelta_months(self):
        """Test conversion to timedelta for months."""
        td = billing_period_to_timedelta("P1M")
        # 1 month = 30 days
        assert td == timedelta(days=30)

    def test_convert_to_timedelta_years(self):
        """Test conversion to timedelta for years."""
        td = billing_period_to_timedelta("P1Y")
        # 1 year = 365 days
        assert td == timedelta(days=365)

    def test_convert_invalid_period(self):
        """Test conversion with invalid period raises ValueError."""
        with pytest.raises(ValueError):
            billing_period_to_timedelta("invalid")


class TestFormatBillingPeriod:
    """Test format_billing_period function."""

    def test_format_years(self):
        """Test formatting years."""
        assert format_billing_period(MILLIS_PER_YEAR) == "P1Y"
        assert format_billing_period(2 * MILLIS_PER_YEAR) == "P2Y"

    def test_format_months(self):
        """Test formatting months."""
        assert format_billing_period(MILLIS_PER_MONTH) == "P1M"
        assert format_billing_period(3 * MILLIS_PER_MONTH) == "P3M"
        assert format_billing_period(6 * MILLIS_PER_MONTH) == "P6M"

    def test_format_weeks(self):
        """Test formatting weeks."""
        assert format_billing_period(MILLIS_PER_WEEK) == "P1W"
        assert format_billing_period(2 * MILLIS_PER_WEEK) == "P2W"

    def test_format_days(self):
        """Test formatting days."""
        assert format_billing_period(MILLIS_PER_DAY) == "P1D"
        assert format_billing_period(7 * MILLIS_PER_DAY) == "P1W"  # Exact week
        assert format_billing_period(10 * MILLIS_PER_DAY) == "P10D"

    def test_format_zero(self):
        """Test formatting zero."""
        assert format_billing_period(0) == "P0D"

    def test_format_negative(self):
        """Test formatting negative value raises ValueError."""
        with pytest.raises(ValueError, match="must be non-negative"):
            format_billing_period(-1)

    def test_format_partial_day(self):
        """Test formatting partial days rounds down."""
        # Not exactly 1 day, should format as days
        partial_day = MILLIS_PER_DAY + 1000  # 1 day + 1 second
        result = format_billing_period(partial_day)
        assert result == "P1D"  # Rounds down


class TestValidateBillingPeriod:
    """Test validate_billing_period function."""

    def test_validate_valid_periods(self):
        """Test validating valid periods."""
        assert validate_billing_period("P1D") is True
        assert validate_billing_period("P1W") is True
        assert validate_billing_period("P1M") is True
        assert validate_billing_period("P1Y") is True
        assert validate_billing_period("P7D") is True

    def test_validate_invalid_periods(self):
        """Test validating invalid periods."""
        assert validate_billing_period("invalid") is False
        assert validate_billing_period("") is False
        assert validate_billing_period("P1X") is False
        assert validate_billing_period("1M") is False

    def test_validate_none(self):
        """Test validating None."""
        assert validate_billing_period(None) is False

    def test_validate_wrong_type(self):
        """Test validating wrong type."""
        assert validate_billing_period(123) is False
        assert validate_billing_period([]) is False


class TestGetCommonBillingPeriods:
    """Test get_common_billing_periods function."""

    def test_get_common_periods(self):
        """Test getting common billing periods."""
        periods = get_common_billing_periods()

        # Check it's a dict
        assert isinstance(periods, dict)

        # Check common periods are present
        assert "P1D" in periods
        assert "P1W" in periods
        assert "P1M" in periods
        assert "P1Y" in periods

        # Check values are correct
        assert periods["P1D"] == MILLIS_PER_DAY
        assert periods["P1W"] == MILLIS_PER_WEEK
        assert periods["P1M"] == MILLIS_PER_MONTH
        assert periods["P1Y"] == MILLIS_PER_YEAR

    def test_common_periods_count(self):
        """Test that we have expected number of common periods."""
        periods = get_common_billing_periods()
        # Should have at least these common periods
        assert len(periods) >= 9


class TestCompareBillingPeriods:
    """Test compare_billing_periods function."""

    def test_compare_equal_periods(self):
        """Test comparing equal periods."""
        assert compare_billing_periods("P1M", "P1M") == 0
        assert compare_billing_periods("P1Y", "P1Y") == 0

    def test_compare_less_than(self):
        """Test comparing less than."""
        assert compare_billing_periods("P1D", "P1W") == -1
        assert compare_billing_periods("P1W", "P1M") == -1
        assert compare_billing_periods("P1M", "P1Y") == -1

    def test_compare_greater_than(self):
        """Test comparing greater than."""
        assert compare_billing_periods("P1W", "P1D") == 1
        assert compare_billing_periods("P1M", "P1W") == 1
        assert compare_billing_periods("P1Y", "P1M") == 1

    def test_compare_equivalent_periods(self):
        """Test comparing equivalent periods."""
        # 7 days = 1 week
        assert compare_billing_periods("P7D", "P1W") == 0

        # 30 days = 1 month (our approximation)
        assert compare_billing_periods("P30D", "P1M") == 0

        # 365 days = 1 year (our approximation)
        assert compare_billing_periods("P365D", "P1Y") == 0

    def test_compare_invalid_period(self):
        """Test comparing with invalid period raises ValueError."""
        with pytest.raises(ValueError):
            compare_billing_periods("P1M", "invalid")

        with pytest.raises(ValueError):
            compare_billing_periods("invalid", "P1M")


class TestBillingPeriodConstants:
    """Test billing period constants."""

    def test_milliseconds_per_day(self):
        """Test MILLIS_PER_DAY constant."""
        assert MILLIS_PER_DAY == 24 * 60 * 60 * 1000
        assert MILLIS_PER_DAY == 86400000

    def test_milliseconds_per_week(self):
        """Test MILLIS_PER_WEEK constant."""
        assert MILLIS_PER_WEEK == 7 * MILLIS_PER_DAY
        assert MILLIS_PER_WEEK == 604800000

    def test_milliseconds_per_month(self):
        """Test MILLIS_PER_MONTH constant."""
        # 30 days approximation
        assert MILLIS_PER_MONTH == 30 * MILLIS_PER_DAY
        assert MILLIS_PER_MONTH == 2592000000

    def test_milliseconds_per_year(self):
        """Test MILLIS_PER_YEAR constant."""
        # 365 days approximation
        assert MILLIS_PER_YEAR == 365 * MILLIS_PER_DAY
        assert MILLIS_PER_YEAR == 31536000000


class TestRoundTripConversion:
    """Test round-trip conversion (parse -> format)."""

    def test_round_trip_days(self):
        """Test round-trip conversion for days."""
        original = "P1D"
        millis = parse_billing_period(original)
        formatted = format_billing_period(millis)
        assert formatted == original

    def test_round_trip_weeks(self):
        """Test round-trip conversion for weeks."""
        original = "P1W"
        millis = parse_billing_period(original)
        formatted = format_billing_period(millis)
        assert formatted == original

    def test_round_trip_months(self):
        """Test round-trip conversion for months."""
        original = "P1M"
        millis = parse_billing_period(original)
        formatted = format_billing_period(millis)
        assert formatted == original

    def test_round_trip_years(self):
        """Test round-trip conversion for years."""
        original = "P1Y"
        millis = parse_billing_period(original)
        formatted = format_billing_period(millis)
        assert formatted == original


class TestGooglePlayPeriods:
    """Test Google Play-specific billing periods."""

    def test_google_play_weekly_subscription(self):
        """Test 1 week subscription period."""
        millis = parse_billing_period("P1W")
        assert millis == 604800000

    def test_google_play_monthly_subscription(self):
        """Test 1 month subscription period."""
        millis = parse_billing_period("P1M")
        assert millis == 2592000000

    def test_google_play_quarterly_subscription(self):
        """Test 3 month subscription period."""
        millis = parse_billing_period("P3M")
        assert millis == 3 * MILLIS_PER_MONTH

    def test_google_play_biannual_subscription(self):
        """Test 6 month subscription period."""
        millis = parse_billing_period("P6M")
        assert millis == 6 * MILLIS_PER_MONTH

    def test_google_play_yearly_subscription(self):
        """Test 1 year subscription period."""
        millis = parse_billing_period("P1Y")
        assert millis == 31536000000


# Parametrized tests
@pytest.mark.parametrize(
    "period,expected_millis",
    [
        ("P1D", 86400000),
        ("P7D", 604800000),
        ("P1W", 604800000),
        ("P2W", 1209600000),
        ("P1M", 2592000000),
        ("P3M", 7776000000),
        ("P6M", 15552000000),
        ("P1Y", 31536000000),
    ],
)
def test_parse_common_periods(period, expected_millis):
    """Test parsing common billing periods."""
    assert parse_billing_period(period) == expected_millis


@pytest.mark.parametrize(
    "invalid_period",
    [
        "",
        "P",
        "1M",
        "P1X",
        "P1M2D",
        "P0D",
        "P-1D",
        "invalid",
        "M1P",
    ],
)
def test_parse_invalid_periods(invalid_period):
    """Test parsing invalid periods raises ValueError."""
    with pytest.raises(ValueError):
        parse_billing_period(invalid_period)


@pytest.mark.parametrize(
    "millis,expected_format",
    [
        (86400000, "P1D"),
        (604800000, "P1W"),
        (2592000000, "P1M"),
        (31536000000, "P1Y"),
        (0, "P0D"),
        (2 * 86400000, "P2D"),
        (2 * 604800000, "P2W"),
    ],
)
def test_format_common_millis(millis, expected_format):
    """Test formatting common millisecond values."""
    assert format_billing_period(millis) == expected_format


@pytest.mark.parametrize(
    "period1,period2,expected",
    [
        ("P1D", "P1W", -1),
        ("P1W", "P1M", -1),
        ("P1M", "P1Y", -1),
        ("P1Y", "P1M", 1),
        ("P1M", "P1W", 1),
        ("P1W", "P1D", 1),
        ("P1M", "P1M", 0),
        ("P7D", "P1W", 0),
        ("P30D", "P1M", 0),
    ],
)
def test_compare_periods(period1, period2, expected):
    """Test comparing billing periods."""
    assert compare_billing_periods(period1, period2) == expected
