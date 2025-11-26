"""Entry point for running the emulator as a module."""

import argparse
import os
import sys

import uvicorn


def main() -> None:
    """Main entry point for the IAP emulator."""
    parser = argparse.ArgumentParser(
        description="Google Play IAP Emulator - Local testing environment for in-app purchases"
    )
    parser.add_argument(
        "--host",
        default=os.getenv("HOST", "0.0.0.0"),
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", "8080")),
        help="Port to bind to (default: 8080)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=os.getenv("LOG_LEVEL", "INFO"),
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--log-format",
        choices=["json", "console"],
        default=os.getenv("LOG_FORMAT", "json"),
        help="Log output format (default: json)",
    )
    parser.add_argument(
        "--config",
        default=os.getenv("CONFIG_PATH", "config/products.yaml"),
        help="Path to products.yaml configuration file (default: config/products.yaml)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=os.getenv("RELOAD", "false").lower() == "true",
        help="Enable auto-reload for development (default: false)",
    )

    args = parser.parse_args()

    # Set environment variables for application
    os.environ["LOG_LEVEL"] = args.log_level
    os.environ["LOG_FORMAT"] = args.log_format
    os.environ["CONFIG_PATH"] = args.config

    # Print startup banner
    if args.log_format == "console":
        print("=" * 60)
        print("Google Play IAP Emulator v0.1.0")
        print("=" * 60)
        print(f"Host: {args.host}")
        print(f"Port: {args.port}")
        print(f"Log Level: {args.log_level}")
        print(f"Config: {args.config}")
        print("=" * 60)

    # Run uvicorn server
    try:
        uvicorn.run(
            "iap_emulator.main:app",
            host=args.host,
            port=args.port,
            log_level=args.log_level.lower(),
            reload=args.reload,
            access_log=False,  # We use our own middleware for access logs
        )
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        print(f"Failed to start emulator: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
