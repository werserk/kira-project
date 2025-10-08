"""Tests for configuration and secrets management (Phase 5, Point 18)."""

import os
import tempfile
from pathlib import Path

import pytest

from kira.config.settings import (
    ConfigError,
    Settings,
    generate_example_env,
    get_settings,
    load_env_file,
    load_settings,
    parse_int_list,
)


@pytest.fixture(autouse=True)
def clean_env():
    """Clean environment variables before each test."""
    # Store original env
    original_env = os.environ.copy()

    # Clean Kira-related vars
    kira_vars = [k for k in os.environ.keys() if k.startswith("KIRA_")]
    for var in kira_vars:
        del os.environ[var]

    # Reset global settings
    import kira.config.settings as settings_module

    settings_module._settings = None

    yield

    # Restore original env
    os.environ.clear()
    os.environ.update(original_env)


def test_settings_creation():
    """Test creating settings object."""
    settings = Settings(vault_path=Path("/test/vault"))

    assert settings.vault_path == Path("/test/vault")
    assert settings.default_timezone == "UTC"
    assert settings.gcal_enabled is False


def test_settings_with_string_path():
    """Test settings converts string path to Path."""
    settings = Settings(vault_path="/test/vault")

    assert isinstance(settings.vault_path, Path)
    assert settings.vault_path == Path("/test/vault")


def test_settings_validation_missing_vault_path():
    """Test DoD: Missing config produces clear errors."""
    with pytest.raises(ConfigError, match="vault_path is required"):
        Settings(vault_path=None)


def test_load_env_file():
    """Test loading .env file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text(
            """
KIRA_VAULT_PATH=/test/vault
KIRA_DEFAULT_TZ=America/New_York
KIRA_LOG_LEVEL=DEBUG
"""
        )

        load_env_file(env_file)

        assert os.environ["KIRA_VAULT_PATH"] == "/test/vault"
        assert os.environ["KIRA_DEFAULT_TZ"] == "America/New_York"
        assert os.environ["KIRA_LOG_LEVEL"] == "DEBUG"


def test_load_env_file_with_quotes():
    """Test .env file with quoted values."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text(
            """
KIRA_VAULT_PATH="/home/user/vault"
KIRA_DEFAULT_TZ='Europe/London'
"""
        )

        load_env_file(env_file)

        # Quotes should be stripped
        assert os.environ["KIRA_VAULT_PATH"] == "/home/user/vault"
        assert os.environ["KIRA_DEFAULT_TZ"] == "Europe/London"


def test_load_env_file_skips_comments():
    """Test .env file skips comments and empty lines."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text(
            """
# This is a comment
KIRA_VAULT_PATH=/test

# Another comment
KIRA_LOG_LEVEL=INFO
"""
        )

        load_env_file(env_file)

        assert os.environ["KIRA_VAULT_PATH"] == "/test"
        assert os.environ["KIRA_LOG_LEVEL"] == "INFO"


def test_settings_from_env():
    """Test DoD: Fresh checkout boots with single .env."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text(
            """
KIRA_VAULT_PATH=/test/vault
KIRA_DEFAULT_TZ=UTC
KIRA_GCAL_ENABLED=true
KIRA_GCAL_CALENDAR_ID=test-calendar@group.calendar.google.com
KIRA_SANDBOX_MAX_CPU=60.0
KIRA_LOG_LEVEL=DEBUG
"""
        )

        settings = Settings.from_env(env_file)

        assert settings.vault_path == Path("/test/vault")
        assert settings.default_timezone == "UTC"
        assert settings.gcal_enabled is True
        assert settings.gcal_calendar_id == "test-calendar@group.calendar.google.com"
        assert settings.sandbox_max_cpu_seconds == 60.0
        assert settings.log_level == "DEBUG"


def test_settings_from_env_missing_required():
    """Test DoD: Missing config produces clear errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("# Empty config")

        with pytest.raises(ConfigError, match="KIRA_VAULT_PATH is required"):
            Settings.from_env(env_file)


def test_settings_defaults():
    """Test default values for optional settings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("KIRA_VAULT_PATH=/test/vault")

        settings = Settings.from_env(env_file)

        # Defaults
        assert settings.default_timezone == "UTC"
        assert settings.gcal_enabled is False
        assert settings.gcal_sync_interval_minutes == 15
        assert settings.sandbox_max_cpu_seconds == 30.0
        assert settings.sandbox_max_memory_mb == 256
        assert settings.sandbox_allow_network is False
        assert settings.log_level == "INFO"
        assert settings.telegram_enabled is False


def test_load_settings_function():
    """Test load_settings() function."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("KIRA_VAULT_PATH=/test/vault")

        settings = load_settings(env_file)

        assert settings.vault_path == Path("/test/vault")


def test_get_settings_not_loaded():
    """Test DoD: Missing config produces clear error."""
    # Reset global state
    import kira.config.settings as settings_module

    settings_module._settings = None

    with pytest.raises(ConfigError, match="Settings not loaded"):
        get_settings()


def test_get_settings_after_load():
    """Test get_settings() after loading."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("KIRA_VAULT_PATH=/test/vault")

        load_settings(env_file)
        settings = get_settings()

        assert settings.vault_path == Path("/test/vault")


def test_parse_int_list():
    """Test parsing comma-separated integers."""
    assert parse_int_list("1,2,3") == [1, 2, 3]
    assert parse_int_list("42") == [42]
    assert parse_int_list("") == []
    assert parse_int_list("1, 2, 3") == [1, 2, 3]  # With spaces


def test_parse_int_list_invalid():
    """Test parsing invalid integer list."""
    assert parse_int_list("abc, def") == []


def test_telegram_settings():
    """Test Telegram-specific settings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text(
            """
KIRA_VAULT_PATH=/test/vault
KIRA_TELEGRAM_ENABLED=true
KIRA_TELEGRAM_BOT_TOKEN=test-token-123
KIRA_TELEGRAM_ALLOWED_USERS=123456789,987654321
"""
        )

        settings = Settings.from_env(env_file)

        assert settings.telegram_enabled is True
        assert settings.telegram_bot_token == "test-token-123"
        assert settings.telegram_allowed_users == [123456789, 987654321]


def test_gcal_settings():
    """Test Google Calendar settings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text(
            """
KIRA_VAULT_PATH=/test/vault
KIRA_GCAL_ENABLED=true
KIRA_GCAL_CALENDAR_ID=my-calendar@group.calendar.google.com
KIRA_GCAL_SYNC_INTERVAL=30
KIRA_GCAL_CREDENTIALS_FILE=/home/user/.kira/creds.json
"""
        )

        settings = Settings.from_env(env_file)

        assert settings.gcal_enabled is True
        assert settings.gcal_calendar_id == "my-calendar@group.calendar.google.com"
        assert settings.gcal_sync_interval_minutes == 30
        assert settings.gcal_credentials_file == "/home/user/.kira/creds.json"


def test_sandbox_settings():
    """Test sandbox limit settings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text(
            """
KIRA_VAULT_PATH=/test/vault
KIRA_SANDBOX_MAX_CPU=15.5
KIRA_SANDBOX_MAX_MEMORY=512
KIRA_SANDBOX_ALLOW_NETWORK=true
"""
        )

        settings = Settings.from_env(env_file)

        assert settings.sandbox_max_cpu_seconds == 15.5
        assert settings.sandbox_max_memory_mb == 512
        assert settings.sandbox_allow_network is True


def test_logging_settings():
    """Test logging configuration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text(
            """
KIRA_VAULT_PATH=/test/vault
KIRA_LOG_LEVEL=ERROR
KIRA_LOG_FILE=/var/log/kira.log
"""
        )

        settings = Settings.from_env(env_file)

        assert settings.log_level == "ERROR"
        assert settings.log_file == Path("/var/log/kira.log")


def test_generate_example_env():
    """Test generating example .env file."""
    example = generate_example_env()

    # Should contain all settings
    assert "KIRA_VAULT_PATH" in example
    assert "KIRA_DEFAULT_TZ" in example
    assert "KIRA_GCAL_ENABLED" in example
    assert "KIRA_SANDBOX_MAX_CPU" in example
    assert "KIRA_LOG_LEVEL" in example
    assert "KIRA_TELEGRAM_ENABLED" in example


def test_generate_example_env_to_file():
    """Test writing example .env to file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "example.env"

        generate_example_env(output_path)

        assert output_path.exists()
        content = output_path.read_text()
        assert "KIRA_VAULT_PATH" in content


def test_dod_fresh_checkout():
    """Test DoD: Fresh checkout boots with single .env."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Simulate fresh checkout
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("KIRA_VAULT_PATH=/home/user/vault")

        # Should load without errors
        settings = load_settings(env_file)

        assert settings.vault_path == Path("/home/user/vault")
        # All other settings should have sensible defaults
        assert settings.default_timezone == "UTC"
        assert settings.log_level == "INFO"


def test_dod_clear_error_messages():
    """Test DoD: Missing config produces clear errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text("# No KIRA_VAULT_PATH")

        with pytest.raises(ConfigError) as exc_info:
            Settings.from_env(env_file)

        # Error message should be clear
        error_msg = str(exc_info.value)
        assert "KIRA_VAULT_PATH" in error_msg
        assert "required" in error_msg.lower()


def test_boolean_parsing():
    """Test boolean value parsing from strings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text(
            """
KIRA_VAULT_PATH=/test
KIRA_GCAL_ENABLED=true
KIRA_TELEGRAM_ENABLED=false
KIRA_SANDBOX_ALLOW_NETWORK=True
"""
        )

        settings = Settings.from_env(env_file)

        assert settings.gcal_enabled is True
        assert settings.telegram_enabled is False
        assert settings.sandbox_allow_network is True


def test_settings_immutability():
    """Test settings can be modified after creation (for testing)."""
    settings = Settings(vault_path=Path("/test"))

    # Should be able to modify (dataclass is mutable by default)
    settings.log_level = "DEBUG"
    assert settings.log_level == "DEBUG"


def test_comprehensive_settings():
    """Test loading all settings together."""
    with tempfile.TemporaryDirectory() as tmpdir:
        env_file = Path(tmpdir) / ".env"
        env_file.write_text(
            """
# Core
KIRA_VAULT_PATH=/home/user/vault
KIRA_DEFAULT_TZ=America/Los_Angeles

# GCal
KIRA_GCAL_ENABLED=true
KIRA_GCAL_CALENDAR_ID=work@group.calendar.google.com
KIRA_GCAL_SYNC_INTERVAL=20
KIRA_GCAL_CREDENTIALS_FILE=/home/user/.kira/gcal.json

# Sandbox
KIRA_SANDBOX_MAX_CPU=45.0
KIRA_SANDBOX_MAX_MEMORY=512
KIRA_SANDBOX_ALLOW_NETWORK=false

# Logging
KIRA_LOG_LEVEL=WARNING
KIRA_LOG_FILE=/var/log/kira/app.log

# Telegram
KIRA_TELEGRAM_ENABLED=true
KIRA_TELEGRAM_BOT_TOKEN=1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ
KIRA_TELEGRAM_ALLOWED_USERS=111,222,333
"""
        )

        settings = Settings.from_env(env_file)

        # Verify all settings
        assert settings.vault_path == Path("/home/user/vault")
        assert settings.default_timezone == "America/Los_Angeles"
        assert settings.gcal_enabled is True
        assert settings.gcal_calendar_id == "work@group.calendar.google.com"
        assert settings.gcal_sync_interval_minutes == 20
        assert settings.sandbox_max_cpu_seconds == 45.0
        assert settings.sandbox_max_memory_mb == 512
        assert settings.log_level == "WARNING"
        assert settings.log_file == Path("/var/log/kira/app.log")
        assert settings.telegram_enabled is True
        assert len(settings.telegram_allowed_users) == 3
