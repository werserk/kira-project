"""Integration tests for inbox pipeline."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kira.pipelines.inbox_pipeline import InboxPipeline


class TestInboxPipelineIntegration:
    """Integration tests for inbox pipeline."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = {
            "vault": {"path": str(self.temp_dir / "vault")},
            "plugins": {"inbox": {}},
        }
        self.pipeline = InboxPipeline(self.config)

    def teardown_method(self) -> None:
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_pipeline_initialization(self) -> None:
        """Test that pipeline initializes correctly."""
        assert self.pipeline is not None
        assert self.pipeline.config == self.config

    def test_scan_inbox_items_returns_list(self) -> None:
        """Test that scan_inbox_items returns a list of items."""
        items = self.pipeline.scan_inbox_items()
        assert isinstance(items, list)
        assert len(items) > 0
        assert all(isinstance(item, str) for item in items)

    def test_run_returns_processed_count(self) -> None:
        """Test that run method returns count of processed items."""
        result = self.pipeline.run()
        assert isinstance(result, int)
        assert result >= 0

    def test_run_processes_all_items(self) -> None:
        """Test that run processes all scanned items."""
        items = self.pipeline.scan_inbox_items()
        result = self.pipeline.run()
        assert result == len(items)

    def test_pipeline_with_different_configs(self) -> None:
        """Test pipeline with different configuration options."""
        configs = [
            {"vault": {"path": "/tmp/test1"}},
            {"vault": {"path": "/tmp/test2"}, "plugins": {"inbox": {"batch_size": 10}}},
            {"vault": {"path": "/tmp/test3"}, "plugins": {"inbox": {"timeout": 30}}},
        ]

        for config in configs:
            pipeline = InboxPipeline(config)
            assert pipeline.config == config
            result = pipeline.run()
            assert isinstance(result, int)
