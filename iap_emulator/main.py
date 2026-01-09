"""FastAPI application entry point and lifecycle management."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from iap_emulator.logging_config import configure_logging, get_logger
from iap_emulator.middleware import ContextMiddleware, RequestLoggingMiddleware

# Initialize logger
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan context manager.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info("emulator_starting", version="0.1.0")

    try:
        # TODO: Initialize Pub/Sub publisher
        # TODO: Load product definitions
        from iap_emulator.services.event_dispatcher import get_event_dispatcher

        dispatcher = get_event_dispatcher()
        if dispatcher.is_enabled():
            logger.info("pubsub_enabled", message="Event dispatcher initialized and ready")
        else:
            logger.info(
                "pubsub_disabled", message="Event dispatcher is disabled or failed to initialize"
            )

        logger.info("emulator_started", status="ready")
        yield
    finally:
        # Shutdown
        logger.info("emulator_shutting_down")
        # cleanup
        from iap_emulator.services.event_dispatcher import get_event_dispatcher

        dispatcher = get_event_dispatcher()
        dispatcher.shutdown()
        logger.info("emulator_stopped")


def create_app() -> FastAPI:
    """Create and configure FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    # Configure logging
    log_level = os.getenv("LOG_LEVEL", "INFO")
    json_format = os.getenv("LOG_FORMAT", "json").lower() == "json"
    configure_logging(log_level=log_level, json_format=json_format)

    # Create FastAPI app
    app = FastAPI(
        title="Google IAP Emulator",
        description="Local emulator for Google Play In-App Purchases and Subscriptions",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Add CORS middleware (allow all for local development)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add logging middleware
    include_request_details = os.getenv("LOG_REQUEST_DETAILS", "true").lower() == "true"
    app.add_middleware(RequestLoggingMiddleware, include_request_details=include_request_details)
    app.add_middleware(ContextMiddleware)

    # Register routers
    from iap_emulator.api.control import router as control_router
    from iap_emulator.api.google_play import router as google_play_router

    app.include_router(google_play_router)
    app.include_router(control_router)

    # Root endpoint
    @app.get("/")
    async def root() -> dict[str, str]:
        """Health check endpoint."""
        logger.debug("root_endpoint_called")
        return {
            "service": "iap-local-emulator",
            "status": "running",
            "version": "0.1.0",
        }

    # Health check endpoint
    @app.get("/health")
    async def health() -> dict[str, str]:
        """Detailed health check."""
        from iap_emulator.repositories.product_repository import get_product_repository
        from iap_emulator.services.event_dispatcher import get_event_dispatcher

        dispatcher = get_event_dispatcher()
        product_repo = get_product_repository()
        pubsub_status = "connected" if dispatcher.is_enabled() else "disabled"
        config_status = f"loaded ({product_repo.get_subscription_count()} total products)"

        return {
            "status": "healthy",
            "pubsub": pubsub_status,
            "config": config_status,
        }

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc: Exception) -> JSONResponse:
        """Handle uncaught exceptions."""
        logger.error(
            "unhandled_exception",
            error=str(exc),
            error_type=type(exc).__name__,
            path=request.url.path,
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "message": "An unexpected error occurred",
            },
        )

    logger.info("app_created", endpoints=len(app.routes))
    return app


# Create app instance
app = create_app()
