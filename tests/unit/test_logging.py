"""Tests for structured logging functionality.

Tests logging configuration, context binding, and various logging scenarios.
"""

import os
import time

import pytest

from iap_emulator.logging_config import (
    bind_context,
    clear_context,
    configure_logging,
    get_logger,
)


@pytest.fixture(scope="module")
def setup_logging():
    """Configure logging for all tests in this module."""
    log_level = os.getenv("LOG_LEVEL", "INFO")
    log_format = os.getenv("LOG_FORMAT", "console")
    json_mode = log_format.lower() == "json"

    configure_logging(log_level=log_level, json_format=json_mode)
    yield
    # Cleanup after all tests


@pytest.fixture(autouse=True)
def cleanup_context():
    """Ensure context is cleared before and after each test."""
    clear_context()
    yield
    clear_context()


class TestBasicLogging:
    """Test basic logging at different levels."""

    def test_debug_logging(self, setup_logging):
        """Test debug level logging."""
        logger = get_logger("test.basic")
        logger.debug("This is a debug message", detail="Only visible in DEBUG mode")
        # No assertion - just verify it doesn't raise

    def test_info_logging(self, setup_logging):
        """Test info level logging."""
        logger = get_logger("test.basic")
        logger.info("Application started", version="0.1.0", environment="test")

    def test_warning_logging(self, setup_logging):
        """Test warning level logging."""
        logger = get_logger("test.basic")
        logger.warning("Configuration missing", key="api_key", using_default=True)

    def test_error_logging(self, setup_logging):
        """Test error level logging."""
        logger = get_logger("test.basic")
        logger.error("Failed to connect", host="pubsub-emulator", port=8085, retry_count=3)

    def test_all_levels(self, setup_logging):
        """Test logging at all levels in sequence."""
        logger = get_logger("test.basic")

        logger.debug("Debug message", level="debug")
        logger.info("Info message", level="info")
        logger.warning("Warning message", level="warning")
        logger.error("Error message", level="error")


class TestContextualLogging:
    """Test logging with bound context."""

    def test_logging_without_context(self, setup_logging):
        """Test logging without bound context."""
        logger = get_logger("test.context")
        logger.info("Processing request")

    def test_bind_context(self, setup_logging):
        """Test binding context to logs."""
        logger = get_logger("test.context")

        # Bind context
        bind_context(
            request_id="req-12345",
            user_id="user-789",
            subscription_id="premium.yearly",
        )

        # All subsequent logs will include context
        logger.info("Subscription lookup started")
        logger.info("Subscription found", status="active", expiry="2025-12-31")
        logger.info("Processing renewal")

    def test_clear_context(self, setup_logging):
        """Test clearing context."""
        logger = get_logger("test.context")

        # Bind and then clear
        bind_context(request_id="req-12345")
        logger.info("With context")

        clear_context()
        logger.info("Without context")

    def test_multiple_context_bindings(self, setup_logging):
        """Test multiple context bindings."""
        logger = get_logger("test.context")

        bind_context(request_id="req-1")
        logger.info("First request")

        bind_context(request_id="req-2", user_id="user-2")
        logger.info("Second request with user")


class TestStructuredData:
    """Test logging with structured data."""

    def test_nested_dict_logging(self, setup_logging):
        """Test logging with nested dictionaries."""
        logger = get_logger("test.structured")

        logger.info(
            "subscription_created",
            subscription={
                "id": "premium.monthly",
                "price": {"amount": 9.99, "currency": "USD"},
                "billing_period": "P1M",
            },
            user={"id": "user-456", "email": "test@example.com"},
        )

    def test_list_logging(self, setup_logging):
        """Test logging with lists."""
        logger = get_logger("test.structured")

        logger.info("processing_batch", items=["item1", "item2", "item3"], total_count=3)

    def test_mixed_types_logging(self, setup_logging):
        """Test logging with mixed data types."""
        logger = get_logger("test.structured")

        logger.info(
            "mixed_data",
            string_val="test",
            int_val=42,
            float_val=3.14,
            bool_val=True,
            none_val=None,
            list_val=[1, 2, 3],
            dict_val={"key": "value"},
        )


class TestExceptionLogging:
    """Test exception logging."""

    def test_exception_logging_with_traceback(self, setup_logging):
        """Test logging exceptions with stack traces."""
        logger = get_logger("test.exceptions")

        try:
            result = 1 / 0
        except ZeroDivisionError as e:
            logger.error(
                "calculation_failed",
                operation="division",
                error=str(e),
                exc_info=True,  # Include stack trace
            )

    def test_exception_logging_without_traceback(self, setup_logging):
        """Test logging exceptions without stack traces."""
        logger = get_logger("test.exceptions")

        try:
            result = 1 / 0
        except ZeroDivisionError as e:
            logger.error(
                "calculation_failed",
                operation="division",
                error=str(e),
            )

    def test_multiple_exception_types(self, setup_logging):
        """Test logging different exception types."""
        logger = get_logger("test.exceptions")

        # ZeroDivisionError
        try:
            _ = 1 / 0
        except ZeroDivisionError as e:
            logger.error("zero_division", error=str(e))

        # KeyError
        try:
            _ = {"a": 1}["b"]
        except KeyError as e:
            logger.error("key_error", error=str(e))

        # ValueError
        try:
            _ = int("not_a_number")
        except ValueError as e:
            logger.error("value_error", error=str(e))


class TestPerformanceLogging:
    """Test performance/timing logging."""

    def test_duration_logging(self, setup_logging):
        """Test logging with duration measurements."""
        logger = get_logger("test.performance")

        start_time = time.time()
        time.sleep(0.01)  # Small sleep for testing
        duration_ms = (time.time() - start_time) * 1000

        logger.info(
            "operation_completed",
            operation="subscription_renewal",
            duration_ms=round(duration_ms, 2),
            success=True,
        )

        # Assert duration is positive
        assert duration_ms > 0

    def test_performance_metrics(self, setup_logging):
        """Test logging performance metrics."""
        logger = get_logger("test.performance")

        logger.info(
            "performance_metrics",
            requests_per_second=150.5,
            avg_latency_ms=25.3,
            p95_latency_ms=45.8,
            error_rate=0.02,
        )


class TestBusinessEvents:
    """Test logging business events."""

    def test_subscription_created_event(self, setup_logging):
        """Test logging subscription creation event."""
        logger = get_logger("subscription_engine")

        bind_context(
            token="emulator_abc123xyz789",
            subscription_id="premium.personal.yearly",
            user_id="user-12345",
        )

        logger.info(
            "subscription_created",
            package_name="com.example.app",
            start_time="2024-11-20T10:00:00Z",
            expiry_time="2025-11-20T10:00:00Z",
            auto_renew=True,
        )

    def test_subscription_renewed_event(self, setup_logging):
        """Test logging subscription renewal event."""
        logger = get_logger("subscription_engine")

        bind_context(
            token="emulator_abc123xyz789",
            subscription_id="premium.personal.yearly",
            user_id="user-12345",
        )

        logger.info(
            "subscription_renewed",
            new_expiry="2026-11-20T10:00:00Z",
            billing_cycle=1,
            payment_status="success",
        )

    def test_payment_failed_event(self, setup_logging):
        """Test logging payment failure event."""
        logger = get_logger("subscription_engine")

        bind_context(
            token="emulator_abc123xyz789",
            subscription_id="premium.personal.yearly",
            user_id="user-12345",
        )

        logger.warning(
            "subscription_payment_failed",
            reason="insufficient_funds",
            grace_period_end="2026-12-03T10:00:00Z",
        )

    def test_complete_subscription_lifecycle(self, setup_logging):
        """Test logging complete subscription lifecycle."""
        logger = get_logger("subscription_engine")

        bind_context(
            token="emulator_lifecycle_test",
            subscription_id="premium.monthly",
            user_id="user-lifecycle",
        )

        # Created
        logger.info("subscription_created", status="active")

        # Renewed
        logger.info("subscription_renewed", billing_cycle=1)

        # Payment failed
        logger.warning("payment_failed", reason="card_expired")

        # Recovered
        logger.info("payment_recovered", method="updated_card")

        # Canceled
        logger.info("subscription_canceled", reason="user_requested")

        # Expired
        logger.info("subscription_expired", final_state="canceled")


class TestLoggerInstances:
    """Test logger instance management."""

    def test_get_logger_returns_logger(self, setup_logging):
        """Test that get_logger returns a logger instance."""
        logger = get_logger("test.instance")
        assert logger is not None

    def test_different_logger_names(self, setup_logging):
        """Test getting loggers with different names."""
        logger1 = get_logger("test.logger1")
        logger2 = get_logger("test.logger2")

        assert logger1 is not None
        assert logger2 is not None

    def test_logger_has_logging_methods(self, setup_logging):
        """Test that logger has all logging methods."""
        logger = get_logger("test.methods")

        assert hasattr(logger, "debug")
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")
        assert callable(logger.debug)
        assert callable(logger.info)
        assert callable(logger.warning)
        assert callable(logger.error)


# Parametrized test for different log levels
@pytest.mark.parametrize("level,message", [
    ("debug", "Debug message"),
    ("info", "Info message"),
    ("warning", "Warning message"),
    ("error", "Error message"),
])
def test_log_levels(setup_logging, level, message):
    """Test logging at different levels with parametrization."""
    logger = get_logger("test.parametrized")
    log_method = getattr(logger, level)
    log_method(message, level=level)


# Parametrized test for context values
@pytest.mark.parametrize("context_key,context_value", [
    ("request_id", "req-123"),
    ("user_id", "user-456"),
    ("subscription_id", "premium.yearly"),
    ("token", "emulator_abc123"),
])
def test_context_binding(setup_logging, cleanup_context, context_key, context_value):
    """Test binding different context values."""
    logger = get_logger("test.context_param")

    bind_context(**{context_key: context_value})
    logger.info("test_message", test_context=context_key)
