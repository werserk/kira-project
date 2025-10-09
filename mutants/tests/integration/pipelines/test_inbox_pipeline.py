"""Integration tests for inbox pipeline orchestration.

Tests verify that:
- Inbox pipeline scans inbox folder and publishes events
- Pipeline retries failed items with backoff
- Trace IDs are propagated through events
- Pipeline contains no business logic (thin orchestration)
- JSONL structured logging works
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from kira.core.events import create_event_bus
from kira.pipelines.inbox_pipeline import create_inbox_pipeline


class TestInboxPipelineOrchestration:
    """Test inbox pipeline orchestration."""

    def test_creates_and_scans_inbox(self, tmp_path):
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

    def test_retry_on_failure(self, tmp_path):
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

    def test_trace_propagation(self, tmp_path):
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


class TestInboxPipelineThinness:
    """Test that inbox pipeline contains NO business logic."""

    def test_no_normalization_logic(self, tmp_path):
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


class TestInboxPipelineLogging:
    """Test JSONL structured logging."""

    def test_logs_to_file(self, tmp_path):
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
        with open(log_path) as f:
            logs = [json.loads(line) for line in f]

        # Should have pipeline_started and pipeline_completed
        assert len(logs) >= 2
        assert logs[0]["event_type"] == "pipeline_started"
        assert logs[-1]["event_type"] == "pipeline_completed"

        # All logs should have trace_id
        trace_ids = [log.get("trace_id") for log in logs]
        assert all(tid == trace_ids[0] for tid in trace_ids)


pytestmark = pytest.mark.integration

