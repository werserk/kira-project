"""Integration tests for calendar sync."""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kira.adapters.gcal.adapter import GCalAdapter


class TestCalendarSyncIntegration:
    """Integration tests for calendar sync."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.config = {
            "gcal": {
                "credentials_path": "/tmp/test_credentials.json",
                "default_calendar": "primary",
            }
        }
        self.adapter = GCalAdapter(self.config)

    def test_adapter_initialization(self) -> None:
        """Test that adapter initializes correctly."""
        assert self.adapter is not None
        assert self.adapter.config == self.config

    def test_pull_returns_structured_data(self) -> None:
        """Test that pull method returns structured data."""
        result = self.adapter.pull()
        assert isinstance(result, dict)
        assert "events_count" in result
        assert "processed_count" in result
        assert isinstance(result["events_count"], int)
        assert isinstance(result["processed_count"], int)

    def test_pull_with_parameters(self) -> None:
        """Test pull method with different parameters."""
        # Test with default parameters
        result1 = self.adapter.pull()
        assert isinstance(result1, dict)

        # Test with custom calendar_id
        result2 = self.adapter.pull(calendar_id="test@example.com")
        assert isinstance(result2, dict)

        # Test with custom days
        result3 = self.adapter.pull(days=7)
        assert isinstance(result3, dict)

    def test_push_returns_structured_data(self) -> None:
        """Test that push method returns structured data."""
        result = self.adapter.push()
        assert isinstance(result, dict)
        assert "events_count" in result
        assert "sent_count" in result
        assert isinstance(result["events_count"], int)
        assert isinstance(result["sent_count"], int)

    def test_push_dry_run_mode(self) -> None:
        """Test push method in dry-run mode."""
        result = self.adapter.push(dry_run=True)
        assert isinstance(result, dict)
        assert "events_count" in result
        assert "sent_count" in result
        assert result["sent_count"] == 0  # Should be 0 in dry-run mode

    def test_push_with_parameters(self) -> None:
        """Test push method with different parameters."""
        # Test with default parameters
        result1 = self.adapter.push()
        assert isinstance(result1, dict)

        # Test with custom calendar_id
        result2 = self.adapter.push(calendar_id="test@example.com")
        assert isinstance(result2, dict)

        # Test dry-run mode
        result3 = self.adapter.push(dry_run=True)
        assert isinstance(result3, dict)

    def test_adapter_with_different_configs(self) -> None:
        """Test adapter with different configuration options."""
        configs = [
            {"gcal": {"credentials_path": "/tmp/creds1.json"}},
            {
                "gcal": {
                    "credentials_path": "/tmp/creds2.json",
                    "default_calendar": "work",
                }
            },
            {"gcal": {"credentials_path": "/tmp/creds3.json", "timeout": 30}},
        ]

        for config in configs:
            adapter = GCalAdapter(config)
            assert adapter.config == config
            result = adapter.pull()
            assert isinstance(result, dict)
