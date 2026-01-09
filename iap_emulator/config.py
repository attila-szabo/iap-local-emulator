"""Configuration management - loads products.yaml and environment variables."""

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import ValidationError

from iap_emulator.models import ProductsConfig


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""

    pass


class Config:
    """Application configuration loader and manager.

    Loads products.yaml and provides validated access to:
    - Product definitions
    - Pub/Sub configuration
    - Emulator settings
    """

    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration loader.

        Args:
            config_path: Path to products.yaml file. If not provided, uses CONFIG_PATH env var
                        or defaults to ./config/products.yaml
        """
        self._config_path = self._resolve_config_path(config_path)
        self._products_config: Optional[ProductsConfig] = None
        self._load_config()

    def _resolve_config_path(self, config_path: Optional[str]) -> Path:
        """Resolve configuration file path from argument, env var, or default."""
        if config_path:
            return Path(config_path)

        # Try environment variable
        env_path = os.getenv("CONFIG_PATH")
        if env_path:
            return Path(env_path)

        # Default to ./config/products.yaml
        return Path("config/products.yaml")

    def _load_config(self) -> None:
        """Load and validate products.yaml configuration."""
        if not self._config_path.exists():
            raise ConfigurationError(
                f"Configuration file not found: {self._config_path}\n"
                f"Please create config/products.yaml or set CONFIG_PATH environment variable"
            )

        try:
            with open(self._config_path, encoding="utf-8") as f:
                raw_config = yaml.safe_load(f)

            if not raw_config:
                raise ConfigurationError(f"Configuration file is empty: {self._config_path}")

            # Validate with Pydantic
            self._products_config = ProductsConfig(**raw_config)

        except yaml.YAMLError as e:
            raise ConfigurationError(f"Failed to parse YAML configuration: {e}")
        except ValidationError as e:
            raise ConfigurationError(f"Configuration validation failed:\n{e}")
        except Exception as e:
            raise ConfigurationError(f"Unexpected error loading configuration: {e}")

    @property
    def products(self) -> ProductsConfig:
        """Get validated products configuration."""
        if self._products_config is None:
            raise ConfigurationError("Configuration not loaded")
        return self._products_config

    @property
    def config_path(self) -> Path:
        """Get path to configuration file."""
        return self._config_path

    def get_product_by_id(self, product_id: str):
        """Get product definition by ID.

        Args:
            product_id: Product or subscription ID (e.g., "premium.personal.yearly")

        Returns:
            ProductDefinition if found, None otherwise
        """
        for product in self.products.subscriptions:
            if product.id == product_id:
                return product
        return None

    def get_all_subscription_ids(self) -> list[str]:
        """Get list of all subscription IDs."""
        return [sub.id for sub in self.products.subscriptions]

    @property
    def pubsub_project_id(self) -> str:
        """Get Pub/Sub project ID.

        Returns:
            Pub/Sub project ID (e.g., "emulator-project")
        """
        return self.products.pubsub.project_id

    @property
    def pubsub_topic(self) -> str:
        """Get Pub/Sub topic name.

        Returns:
            Pub/Sub topic name (e.g., "google-play-rtdn")
        """
        return self.products.pubsub.topic

    @property
    def pubsub_subscription(self) -> str:
        """Get default Pub/Sub subscription name.

        Returns:
            Default subscription name (e.g., "google-play-rtdn-sub")
        """
        return self.products.pubsub.default_subscription

    @property
    def default_package_name(self) -> str:
        """Get default Android package name.

        Returns:
            Package name (e.g., "com.example.secureapp")
        """
        return self.products.default_package_name

    @property
    def emulator_settings(self):
        """Get emulator configuration settings.

        Returns:
            EmulatorConfig object with all emulator settings
        """
        return self.products.emulator

    def reload(self) -> None:
        """Reload configuration from disk.

        Useful for development when products.yaml is modified.
        """
        self._load_config()


# Global configuration instance
_config_instance: Optional[Config] = None


def get_config(config_path: Optional[str] = None) -> Config:
    """Get global configuration instance (singleton).

    Args:
        config_path: Optional path to configuration file (only used on first call)

    Returns:
        Config instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config(config_path)
    return _config_instance


def reload_config() -> None:
    """Reload global configuration from disk."""
    global _config_instance
    if _config_instance:
        _config_instance.reload()
    else:
        _config_instance = Config()
