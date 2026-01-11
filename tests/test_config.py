"""Tests for configuration module."""

import logging
from pathlib import Path

import pytest
import yaml

from src.config.settings import AzureSettings, DatabaseSettings, LoggingSettings, Settings, StorageSettings, get_settings


class TestAzureSettings:
    """Tests for AzureSettings."""

    def test_default_values(self):
        """Test AzureSettings with default values."""
        settings = AzureSettings()
        assert settings.client_id == ""
        assert settings.tenant == "common"
        assert len(settings.scopes) == 3
        assert "https://graph.microsoft.com/Mail.Read" in settings.scopes
        assert "https://graph.microsoft.com/User.Read" in settings.scopes
        assert "offline_access" in settings.scopes

    def test_custom_values(self):
        """Test AzureSettings with custom values."""
        settings = AzureSettings(
            client_id="test-client-id",
            tenant="test-tenant",
            scopes=["custom-scope"],
        )
        assert settings.client_id == "test-client-id"
        assert settings.tenant == "test-tenant"
        assert settings.scopes == ["custom-scope"]

    def test_env_override(self, monkeypatch):
        """Test AzureSettings with environment variable override."""
        monkeypatch.setenv("AZURE_CLIENT_ID", "env-client-id")
        monkeypatch.setenv("AZURE_TENANT", "env-tenant")
        settings = AzureSettings()
        assert settings.client_id == "env-client-id"
        assert settings.tenant == "env-tenant"


class TestDatabaseSettings:
    """Tests for DatabaseSettings."""

    def test_default_values(self):
        """Test DatabaseSettings with default values."""
        settings = DatabaseSettings()
        assert settings.url.startswith("sqlite:///")
        assert str(Path.home()) in settings.url

    def test_expand_sqlite_path(self):
        """Test path expansion for SQLite URLs."""
        settings = DatabaseSettings(url="sqlite:///~/test/db.sqlite")
        assert settings.url == f"sqlite:///{Path.home()}/test/db.sqlite"

    def test_non_sqlite_url(self):
        """Test non-SQLite URL remains unchanged."""
        url = "postgresql://user:pass@localhost/db"
        settings = DatabaseSettings(url=url)
        assert settings.url == url

    def test_env_override(self, monkeypatch):
        """Test DatabaseSettings with environment variable override."""
        monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
        settings = DatabaseSettings()
        assert settings.url == "sqlite:///test.db"


class TestStorageSettings:
    """Tests for StorageSettings."""

    def test_default_values(self):
        """Test StorageSettings with default values."""
        settings = StorageSettings()
        assert str(Path.home()) in settings.attachments_dir
        assert str(Path.home()) in settings.token_file
        assert settings.attachments_dir.endswith("attachments")
        assert settings.token_file.endswith("tokens.json")

    def test_expand_paths(self):
        """Test path expansion in storage settings."""
        settings = StorageSettings(
            attachments_dir="~/test/attachments",
            token_file="~/test/tokens.json",
        )
        assert settings.attachments_dir == str(Path.home() / "test" / "attachments")
        assert settings.token_file == str(Path.home() / "test" / "tokens.json")

    def test_env_override(self, monkeypatch):
        """Test StorageSettings with environment variable override."""
        monkeypatch.setenv("STORAGE_ATTACHMENTS_DIR", "/tmp/attachments")
        monkeypatch.setenv("STORAGE_TOKEN_FILE", "/tmp/tokens.json")
        settings = StorageSettings()
        assert settings.attachments_dir == "/tmp/attachments"
        assert settings.token_file == "/tmp/tokens.json"


class TestLoggingSettings:
    """Tests for LoggingSettings."""

    def test_default_values(self):
        """Test LoggingSettings with default values."""
        settings = LoggingSettings()
        assert settings.level == "INFO"

    def test_valid_levels(self):
        """Test all valid logging levels."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        for level in valid_levels:
            settings = LoggingSettings(level=level)
            assert settings.level == level

    def test_case_insensitive(self):
        """Test logging level is case insensitive."""
        settings = LoggingSettings(level="info")
        assert settings.level == "INFO"

        settings = LoggingSettings(level="DeBuG")
        assert settings.level == "DEBUG"

    def test_invalid_level(self):
        """Test invalid logging level raises error."""
        with pytest.raises(ValueError, match="Invalid logging level"):
            LoggingSettings(level="INVALID")

    def test_env_override(self, monkeypatch):
        """Test LoggingSettings with environment variable override."""
        monkeypatch.setenv("LOGGING_LEVEL", "DEBUG")
        settings = LoggingSettings()
        assert settings.level == "DEBUG"


class TestSettings:
    """Tests for main Settings class."""

    def test_default_values(self):
        """Test Settings with default values."""
        settings = Settings()
        assert isinstance(settings.azure, AzureSettings)
        assert isinstance(settings.database, DatabaseSettings)
        assert isinstance(settings.storage, StorageSettings)
        assert isinstance(settings.logging, LoggingSettings)

    def test_from_yaml_no_file(self, tmp_path):
        """Test from_yaml with no config file returns defaults."""
        # Create a temporary directory without config file
        non_existent = tmp_path / "nonexistent.yaml"
        settings = Settings.from_yaml(non_existent)
        assert isinstance(settings, Settings)
        assert settings.azure.client_id == ""

    def test_from_yaml_empty_file(self, tmp_path):
        """Test from_yaml with empty config file."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        settings = Settings.from_yaml(config_file)
        assert isinstance(settings, Settings)

    def test_from_yaml_with_data(self, tmp_path):
        """Test from_yaml with valid config data."""
        config_file = tmp_path / "config.yaml"
        config_data = {
            "azure": {
                "client_id": "test-id",
                "tenant": "test-tenant",
            },
            "database": {
                "url": "sqlite:///test.db",
            },
            "storage": {
                "attachments_dir": "/tmp/attachments",
                "token_file": "/tmp/tokens.json",
            },
            "logging": {
                "level": "DEBUG",
            },
        }
        config_file.write_text(yaml.dump(config_data))

        settings = Settings.from_yaml(config_file)
        assert settings.azure.client_id == "test-id"
        assert settings.azure.tenant == "test-tenant"
        assert settings.database.url == "sqlite:///test.db"
        assert settings.storage.attachments_dir == "/tmp/attachments"
        assert settings.storage.token_file == "/tmp/tokens.json"
        assert settings.logging.level == "DEBUG"

    def test_from_yaml_default_locations(self, tmp_path, monkeypatch):
        """Test from_yaml checks default locations."""
        # Change to temp directory
        monkeypatch.chdir(tmp_path)

        # Create config in default location
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        config_file = config_dir / "config.yaml"
        config_data = {"azure": {"client_id": "default-location-id"}}
        config_file.write_text(yaml.dump(config_data))

        settings = Settings.from_yaml()
        assert settings.azure.client_id == "default-location-id"

    def test_setup_logging(self, caplog):
        """Test setup_logging configures logging correctly."""
        settings = Settings(logging=LoggingSettings(level="DEBUG"))
        settings.setup_logging()

        # Verify logging is configured
        logger = logging.getLogger(__name__)
        with caplog.at_level(logging.DEBUG):
            logger.debug("Test debug message")
            assert "Test debug message" in caplog.text

    def test_ensure_directories(self, tmp_path):
        """Test ensure_directories creates required directories."""
        settings = Settings(
            storage=StorageSettings(
                attachments_dir=str(tmp_path / "attachments"),
                token_file=str(tmp_path / "tokens" / "tokens.json"),
            ),
            database=DatabaseSettings(url=f"sqlite:///{tmp_path}/db/emails.db"),
        )

        settings.ensure_directories()

        assert (tmp_path / "attachments").exists()
        assert (tmp_path / "tokens").exists()
        assert (tmp_path / "db").exists()

    def test_env_nested_override(self, monkeypatch):
        """Test nested environment variable override."""
        monkeypatch.setenv("AZURE__CLIENT_ID", "nested-id")
        monkeypatch.setenv("DATABASE__URL", "sqlite:///nested.db")
        settings = Settings()
        assert settings.azure.client_id == "nested-id"
        assert settings.database.url == "sqlite:///nested.db"


class TestGetSettings:
    """Tests for get_settings function."""

    def test_get_settings_cached(self):
        """Test get_settings returns cached instance."""
        # Clear cache first
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_get_settings_with_env_config(self, tmp_path, monkeypatch):
        """Test get_settings uses OUTMYLOOK_CONFIG environment variable."""
        # Clear cache
        get_settings.cache_clear()

        config_file = tmp_path / "env_config.yaml"
        config_data = {"azure": {"client_id": "env-config-id"}}
        config_file.write_text(yaml.dump(config_data))

        monkeypatch.setenv("OUTMYLOOK_CONFIG", str(config_file))
        settings = get_settings()
        assert settings.azure.client_id == "env-config-id"

        # Clear cache for other tests
        get_settings.cache_clear()

    def test_get_settings_with_path(self, tmp_path):
        """Test get_settings with explicit path."""
        # Clear cache
        get_settings.cache_clear()

        config_file = tmp_path / "custom_config.yaml"
        config_data = {"azure": {"client_id": "custom-path-id"}}
        config_file.write_text(yaml.dump(config_data))

        settings = get_settings(config_file)
        assert settings.azure.client_id == "custom-path-id"

        # Clear cache for other tests
        get_settings.cache_clear()


@pytest.fixture(autouse=True)
def cleanup_cache():
    """Clear get_settings cache before each test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
