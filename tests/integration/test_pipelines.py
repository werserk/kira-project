"""Integration tests for pipelines (ADR-009).

These tests verify that pipelines correctly orchestrate event publishing,
retry logic, trace propagation, and logging without containing business logic.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kira.core.events import create_event_bus
from kira.core.host import create_host_api
from kira.core.scheduler import create_scheduler
from kira.pipelines.inbox_pipeline import create_inbox_pipeline
from kira.pipelines.rollup_pipeline import create_rollup_pipeline
from kira.pipelines.sync_pipeline import create_sync_pipeline


class TestInboxPipeline:
    """Test inbox pipeline orchestration."""

    def test_inbox_pipeline_creates_and_scans(self, tmp_path):
        """Inbox pipeline scans inbox folder and publishes events."""
        # Create inbox with test files
        inbox_path = tmp_path / "inbox"
        inbox_path.mkdir()
        (inbox_path / "test1.md").write_text("# Test 1\n\nContent")
        (inbox_path / "test2.txt").write_text("Test message")

        # Create pipeline
        event_bus = create_event_bus()
        events_published = []

        def capture_event(event) -> None:
            events_published.append((event.name, event.payload))

        event_bus.subscribe("message.received", capture_event)
        event_bus.subscribe("file.dropped", capture_event)

        pipeline = create_inbox_pipeline(
            vault_path=tmp_path,
            event_bus=event_bus,
        )

        # Run pipeline
        result = pipeline.run()

        # Verify execution
        assert result.success
        assert result.items_scanned == 2
        assert result.items_processed == 2
        assert len(events_published) == 2

    def test_inbox_pipeline_retry_on_failure(self, tmp_path):
        """Inbox pipeline retries failed items with backoff."""
        inbox_path = tmp_path / "inbox"
        inbox_path.mkdir()
        (inbox_path / "test.md").write_text("Test content")

        event_bus = create_event_bus()
        call_count = [0]

        def failing_handler(event) -> None:
            call_count[0] += 1
            if call_count[0] < 3:  # Fail twice, succeed third time
                raise RuntimeError("Simulated failure")

        event_bus.subscribe("file.dropped", failing_handler)

        pipeline = create_inbox_pipeline(
            vault_path=tmp_path,
            event_bus=event_bus,
            max_retries=3,
            retry_delay=0.1,
        )

        result = pipeline.run()

        # Should have retried
        assert call_count[0] == 3
        assert result.items_processed == 1

    def test_inbox_pipeline_trace_propagation(self, tmp_path):
        """Inbox pipeline propagates trace IDs through events."""
        inbox_path = tmp_path / "inbox"
        inbox_path.mkdir()
        (inbox_path / "test.md").write_text("Test")

        event_bus = create_event_bus()
        trace_ids_seen = []

        def capture_trace(event) -> None:
            if event.payload and "trace_id" in event.payload:
                trace_ids_seen.append(event.payload["trace_id"])

        event_bus.subscribe("file.dropped", capture_trace)

        pipeline = create_inbox_pipeline(vault_path=tmp_path, event_bus=event_bus)
        result = pipeline.run()

        # All events should have same trace_id from pipeline run
        assert len(trace_ids_seen) == 1
        assert trace_ids_seen[0] == result.trace_id


class TestSyncPipeline:
    """Test sync pipeline orchestration."""

    def test_sync_pipeline_publishes_tick_events(self, tmp_path):
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

    def test_sync_pipeline_scheduled_execution(self, tmp_path):
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

    def test_sync_pipeline_adapter_retry(self, tmp_path):
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


class TestRollupPipeline:
    """Test rollup pipeline orchestration."""

    def test_rollup_pipeline_daily_creation(self, tmp_path):
        """Rollup pipeline creates daily rollup via Host API."""
        event_bus = create_event_bus()
        host_api = create_host_api(tmp_path)

        pipeline = create_rollup_pipeline(
            vault_path=tmp_path,
            event_bus=event_bus,
            host_api=host_api,
        )

        today = date.today()
        result = pipeline.create_daily_rollup(today)

        # Verify execution
        assert result.success
        assert result.rollup_type == "daily"
        assert result.period_start == today
        assert result.entity_id is not None

        # Verify entity created
        entity = host_api.read_entity(result.entity_id)
        assert "Daily Rollup" in entity.metadata.get("title", "")
        assert entity.metadata.get("rollup_type") == "daily"

    def test_rollup_pipeline_weekly_creation(self, tmp_path):
        """Rollup pipeline creates weekly rollup."""
        event_bus = create_event_bus()
        host_api = create_host_api(tmp_path)

        pipeline = create_rollup_pipeline(
            vault_path=tmp_path,
            event_bus=event_bus,
            host_api=host_api,
        )

        start_date = date.today() - timedelta(days=7)
        end_date = date.today()
        result = pipeline.create_weekly_rollup(start_date, end_date)

        assert result.success
        assert result.rollup_type == "weekly"
        assert result.entity_id is not None

    def test_rollup_pipeline_publishes_request_event(self, tmp_path):
        """Rollup pipeline publishes rollup.requested event."""
        event_bus = create_event_bus()
        host_api = create_host_api(tmp_path)
        events_published = []

        def capture_rollup_request(event) -> None:
            events_published.append((event.name, event.payload))

        event_bus.subscribe("rollup.requested", capture_rollup_request)

        pipeline = create_rollup_pipeline(
            vault_path=tmp_path,
            event_bus=event_bus,
            host_api=host_api,
        )

        result = pipeline.create_daily_rollup()

        # Verify request event published
        assert len(events_published) == 1
        event_name, payload = events_published[0]
        assert event_name == "rollup.requested"
        assert payload["rollup_type"] == "daily"
        assert payload["trace_id"] == result.trace_id

    def test_rollup_pipeline_trace_in_entity(self, tmp_path):
        """Rollup pipeline includes trace_id in created entity."""
        event_bus = create_event_bus()
        host_api = create_host_api(tmp_path)

        pipeline = create_rollup_pipeline(
            vault_path=tmp_path,
            event_bus=event_bus,
            host_api=host_api,
        )

        result = pipeline.create_daily_rollup()
        entity = host_api.read_entity(result.entity_id)

        # Trace ID should be in metadata
        assert entity.metadata.get("trace_id") == result.trace_id


class TestPipelineThinness:
    """Test that pipelines contain NO business logic."""

    def test_inbox_pipeline_no_normalization_logic(self, tmp_path):
        """Inbox pipeline should NOT contain normalization logic."""
        # Verify by inspecting that pipeline only routes events
        # Business logic (normalization) is in plugins
        inbox_path = tmp_path / "inbox"
        inbox_path.mkdir()
        (inbox_path / "test.md").write_text("# Business Logic Test\n\nWith tags #urgent")

        event_bus = create_event_bus()
        pipeline = create_inbox_pipeline(vault_path=tmp_path, event_bus=event_bus)

        # Pipeline should NOT extract tags or normalize
        # It should only scan and publish events
        result = pipeline.run()

        # Pipeline knows nothing about tags or normalization
        assert result.items_scanned == 1

    def test_sync_pipeline_no_adapter_logic(self):
        """Sync pipeline should NOT contain adapter sync logic."""
        # Pipeline only publishes sync.tick events
        # Adapters subscribe and handle their own sync logic
        event_bus = create_event_bus()
        pipeline = create_sync_pipeline(event_bus=event_bus, adapters=["test"])

        # Pipeline knows nothing about how adapters sync
        result = pipeline.run(["test"])
        assert result.adapters_synced == 1

    def test_rollup_pipeline_no_content_generation(self, tmp_path):
        """Rollup pipeline should NOT generate rollup content."""
        # Pipeline only aggregates sections from plugins
        # Plugins contribute sections via events
        event_bus = create_event_bus()
        host_api = create_host_api(tmp_path)
        pipeline = create_rollup_pipeline(
            vault_path=tmp_path,
            event_bus=event_bus,
            host_api=host_api,
        )

        result = pipeline.create_daily_rollup()

        # Pipeline aggregates but doesn't generate content
        # (sections_count is 0 because no plugins responded in this test)
        assert result.sections_count == 0


class TestPipelineLogging:
    """Test JSONL structured logging."""

    def test_inbox_pipeline_logs_to_file(self, tmp_path):
        """Inbox pipeline logs to JSONL file."""
        inbox_path = tmp_path / "inbox"
        inbox_path.mkdir()
        (inbox_path / "test.md").write_text("Test")

        log_path = tmp_path / "logs" / "inbox.jsonl"
        event_bus = create_event_bus()

        pipeline = create_inbox_pipeline(
            vault_path=tmp_path,
            event_bus=event_bus,
            log_path=log_path,
        )

        pipeline.run()

        # Verify log file created
        assert log_path.exists()

        # Parse log entries
        import json

        with open(log_path) as f:
            logs = [json.loads(line) for line in f]

        # Should have pipeline_started and pipeline_completed
        assert len(logs) >= 2
        assert logs[0]["event_type"] == "pipeline_started"
        assert logs[-1]["event_type"] == "pipeline_completed"

        # All logs should have trace_id
        trace_ids = [log.get("trace_id") for log in logs]
        assert all(tid == trace_ids[0] for tid in trace_ids)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
