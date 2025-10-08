"""Integration tests for sync pipeline orchestration.

Tests verify that:
- Sync pipeline publishes sync.tick events for adapters
- Pipeline can be scheduled for periodic execution
- Pipeline retries failed adapter syncs
- Pipeline contains no adapter logic (thin orchestration)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from kira.core.events import create_event_bus
from kira.core.scheduler import create_scheduler
from kira.pipelines.sync_pipeline import create_sync_pipeline


class TestSyncPipelineOrchestration:
    """Test sync pipeline orchestration."""

    def test_publishes_tick_events(self, tmp_path):
        """Sync pipeline publishes sync.tick events for adapters."""
        event_bus = create_event_bus()
        events_published = []

        def capture_sync(event) -> None:
            events_published.append((event.name, event.payload))

        event_bus.subscribe("sync.tick", capture_sync)

        pipeline = create_sync_pipeline(
            event_bus=event_bus,
            adapters=["gcal", "telegram"],
        )

        result = pipeline.run()

        # Verify tick events published
        assert result.success
        assert result.adapters_synced == 2
        assert len(events_published) == 2

        # Check payload structure
        for _, payload in events_published:
            assert "adapter" in payload
            assert "trace_id" in payload
            assert payload["trace_id"] == result.trace_id

    def test_scheduled_execution(self, tmp_path):
        """Sync pipeline can be scheduled for periodic execution."""
        event_bus = create_event_bus()
        scheduler = create_scheduler()

        pipeline = create_sync_pipeline(
            event_bus=event_bus,
            scheduler=scheduler,
            sync_interval_seconds=1,
        )

        # Schedule periodic sync
        job_id = pipeline.schedule_periodic_sync()
        assert job_id is not None

        # Cancel it
        success = pipeline.cancel_periodic_sync()
        assert success

    def test_adapter_retry(self, tmp_path):
        """Sync pipeline retries failed adapter syncs."""
        event_bus = create_event_bus()
        call_counts = {"gcal": 0}

        def failing_handler(event) -> None:
            adapter = event.payload.get("adapter")
            if adapter == "gcal":
                call_counts[adapter] += 1
                if call_counts[adapter] < 2:
                    raise RuntimeError("Sync failed")

        event_bus.subscribe("sync.tick", failing_handler)

        pipeline = create_sync_pipeline(
            event_bus=event_bus,
            adapters=["gcal"],
            max_retries=3,
            retry_delay=0.05,
        )

        result = pipeline.run()

        # Should have retried
        assert call_counts["gcal"] == 2
        assert result.adapters_synced == 1


class TestSyncPipelineThinness:
    """Test that sync pipeline contains NO business logic."""

    def test_no_adapter_logic(self):
        """Sync pipeline should NOT contain adapter sync logic."""
        # Pipeline only publishes sync.tick events
        # Adapters subscribe and handle their own sync logic
        event_bus = create_event_bus()
        pipeline = create_sync_pipeline(event_bus=event_bus, adapters=["test"])

        # Pipeline knows nothing about how adapters sync
        result = pipeline.run(["test"])
        assert result.adapters_synced == 1


pytestmark = pytest.mark.integration

