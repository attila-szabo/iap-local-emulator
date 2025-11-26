"""FastAPI middleware for request/response logging and correlation."""

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from iap_emulator.logging_config import bind_context, clear_context, get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses with correlation IDs.

    Features:
    - Generates unique request_id for each request
    - Logs request method, path, client IP
    - Logs response status code and duration
    - Binds request_id to all logs within request context
    """

    def __init__(self, app: ASGIApp, include_request_details: bool = True):
        """Initialize middleware.

        Args:
            app: ASGI application
            include_request_details: If True, log full request details
        """
        super().__init__(app)
        self.include_request_details = include_request_details

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and add logging context.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            HTTP response
        """
        # Generate unique request ID
        request_id = str(uuid.uuid4())

        # Bind request context for all logs in this request
        bind_context(request_id=request_id)

        # Extract client info
        client_host = request.client.host if request.client else "unknown"

        # Log incoming request
        if self.include_request_details:
            logger.info(
                "request_started",
                method=request.method,
                path=request.url.path,
                query_params=str(request.query_params) if request.query_params else None,
                client_host=client_host,
                user_agent=request.headers.get("user-agent"),
            )
        else:
            logger.info(
                "request_started",
                method=request.method,
                path=request.url.path,
            )

        # Track request duration
        start_time = time.time()

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Log response
            logger.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )

            # Add request ID to response headers for client correlation
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as exc:
            # Calculate duration even for errors
            duration_ms = (time.time() - start_time) * 1000

            # Log error
            logger.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration_ms, 2),
                error=str(exc),
                error_type=type(exc).__name__,
                exc_info=True,
            )

            raise

        finally:
            # Clear context to prevent memory leaks
            clear_context()


class ContextMiddleware(BaseHTTPMiddleware):
    """Middleware for extracting and binding business context from requests.

    Extracts common IAP parameters from path/query and binds them to logging context:
    - package_name
    - product_id / subscription_id
    - token
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Extract business context from request.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            HTTP response
        """
        # Extract package name from path if present
        if "applications" in request.url.path:
            parts = request.url.path.split("/")
            try:
                app_index = parts.index("applications")
                if len(parts) > app_index + 1:
                    package_name = parts[app_index + 1]
                    bind_context(package_name=package_name)
            except (ValueError, IndexError):
                pass

        # Extract product/subscription ID from path
        if "products" in request.url.path:
            parts = request.url.path.split("/")
            try:
                prod_index = parts.index("products")
                if len(parts) > prod_index + 1:
                    product_id = parts[prod_index + 1]
                    bind_context(product_id=product_id)
            except (ValueError, IndexError):
                pass

        if "subscriptions" in request.url.path:
            parts = request.url.path.split("/")
            try:
                sub_index = parts.index("subscriptions")
                if len(parts) > sub_index + 1:
                    subscription_id = parts[sub_index + 1]
                    bind_context(subscription_id=subscription_id)
            except (ValueError, IndexError):
                pass

        # Extract token from path
        if "tokens" in request.url.path:
            parts = request.url.path.split("/")
            try:
                token_index = parts.index("tokens")
                if len(parts) > token_index + 1:
                    token = parts[token_index + 1]
                    # Only log first 12 chars of token for security
                    bind_context(token=f"{token[:12]}...")
            except (ValueError, IndexError):
                pass

        # Process request
        response = await call_next(request)

        return response
