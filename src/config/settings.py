"""Configuration settings for OutMyLook."""

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AzureSettings(BaseSettings):
    """Azure AD configuration settings."""

    client_id: str = Field(
        default="",
        description="Azure AD application (client) ID",
    )
    tenant: str = Field(
        default="common",
        description="Azure AD tenant ID or 'common' for personal accounts",
    )
    scopes: List[str] = Field(
        default_factory=lambda: [
            "https://graph.microsoft.com/Mail.Read",
            "https://graph.microsoft.com/User.Read",
            "offline_access",
        ],
        description="Microsoft Graph API scopes",
    )

    model_config = SettingsConfigDict(env_prefix="AZURE_")


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""

    url: str = Field(
        default="sqlite:///~/.outmylook/emails.db",
        description="Database connection URL",
    )

    @field_validator("url")
    @classmethod
    def expand_path(cls, v: str) -> str:
        """Expand user home directory in database URL."""
        if v.startswith("sqlite:///~/"):
            expanded = v.replace("sqlite:///~/", f"sqlite:///{Path.home()}/")
            return expanded
        return v

    model_config = SettingsConfigDict(env_prefix="DATABASE_")


class StorageSettings(BaseSettings):
    """Storage configuration settings."""

    attachments_dir: str = Field(
        default="~/.outmylook/attachments",
        description="Directory for storing email attachments",
    )
    token_file: str = Field(
        default="~/.outmylook/tokens.json",
        description="File for storing authentication tokens",
    )

    @field_validator("attachments_dir", "token_file")
    @classmethod
    def expand_path(cls, v: str) -> str:
        """Expand user home directory in paths."""
        return str(Path(v).expanduser())

    model_config = SettingsConfigDict(env_prefix="STORAGE_")


class LoggingSettings(BaseSettings):
    """Logging configuration settings."""

    level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Validate logging level."""
        v_upper = v.upper()
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid logging level: {v}. Must be one of {valid_levels}")
        return v_upper

    model_config = SettingsConfigDict(env_prefix="LOGGING_")


class Settings(BaseSettings):
    """Main application settings."""

    azure: AzureSettings = Field(default_factory=AzureSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    @classmethod
    def from_yaml(cls, config_path: Optional[Path] = None) -> "Settings":
        """Load settings from YAML file.

        Args:
            config_path: Path to YAML config file. If None, uses default locations.

        Returns:
            Settings instance loaded from YAML file.

        Raises:
            FileNotFoundError: If config file not found and no default exists.
        """
        if config_path is None:
            # Try default locations
            possible_paths = [
                Path("config/config.yaml"),
                Path.home() / ".outmylook" / "config.yaml",
            ]
            for path in possible_paths:
                if path.exists():
                    config_path = path
                    break

        if config_path is None or not config_path.exists():
            # Return default settings if no config file found
            return cls(
                azure=AzureSettings(),
                database=DatabaseSettings(),
                storage=StorageSettings(),
                logging=LoggingSettings(),
            )

        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f)

        if config_data is None:
            config_data = {}

        # Create nested settings objects
        azure_settings = AzureSettings(**config_data.get("azure", {}))
        database_settings = DatabaseSettings(**config_data.get("database", {}))
        storage_settings = StorageSettings(**config_data.get("storage", {}))
        logging_settings = LoggingSettings(**config_data.get("logging", {}))

        return cls(
            azure=azure_settings,
            database=database_settings,
            storage=storage_settings,
            logging=logging_settings,
        )

    def setup_logging(self) -> None:
        """Configure logging based on settings."""
        logging.basicConfig(
            level=getattr(logging, self.logging.level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def ensure_directories(self) -> None:
        """Ensure required directories exist."""
        # Create attachments directory
        Path(self.storage.attachments_dir).mkdir(parents=True, exist_ok=True)

        # Create directory for token file
        Path(self.storage.token_file).parent.mkdir(parents=True, exist_ok=True)

        # Create directory for database file if using SQLite
        if self.database.url.startswith("sqlite:///"):
            db_path = self.database.url.replace("sqlite:///", "")
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings(config_path: Optional[Path] = None) -> Settings:
    """Get cached settings instance.

    Args:
        config_path: Optional path to config file.

    Returns:
        Cached Settings instance.
    """
    # Check for config path in environment variable
    env_config_path = os.getenv("OUTMYLOOK_CONFIG")
    if env_config_path:
        config_path = Path(env_config_path)

    return Settings.from_yaml(config_path)
