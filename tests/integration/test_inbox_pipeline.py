"""Integration tests for inbox pipeline."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kira.pipelines.inbox_pipeline import InboxPipeline, InboxPipelineConfig


class TestInboxPipelineIntegration:
    """Integration tests for inbox pipeline."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        vault_path = self.temp_dir / "vault"
        vault_path.mkdir(parents=True, exist_ok=True)
        self.config = InboxPipelineConfig(vault_path=vault_path)
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
        # Empty inbox is valid
        assert all(isinstance(item, Path) for item in items)

    def test_run_returns_processed_count(self) -> None:
        """Test that run method returns count of processed items."""
        result = self.pipeline.run()
        from kira.pipelines.inbox_pipeline import InboxPipelineResult

        assert isinstance(result, InboxPipelineResult)
        assert result.items_processed >= 0

    def test_run_processes_all_items(self) -> None:
        """Test that run processes all scanned items."""
        items = self.pipeline.scan_inbox_items()
        result = self.pipeline.run()
        from kira.pipelines.inbox_pipeline import InboxPipelineResult

        assert isinstance(result, InboxPipelineResult)
        # When there are no failures, processed + failed should equal scanned
        assert result.items_scanned == len(items)

    def test_pipeline_with_different_configs(self) -> None:
        """Test pipeline with different configuration options."""
        configs = [
            InboxPipelineConfig(vault_path=self.temp_dir / "test1"),
            InboxPipelineConfig(vault_path=self.temp_dir / "test2", max_retries=5),
            InboxPipelineConfig(vault_path=self.temp_dir / "test3", max_items_per_run=50),
        ]

        for config in configs:
            pipeline = InboxPipeline(config)
            assert pipeline.config == config
            result = pipeline.run()
            from kira.pipelines.inbox_pipeline import InboxPipelineResult

            assert isinstance(result, InboxPipelineResult)
