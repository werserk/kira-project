"""Integration tests for rollup pipeline orchestration.

Tests verify that:
- Rollup pipeline creates daily/weekly rollups via Host API
- Pipeline publishes rollup.requested events
- Trace IDs are included in created entities
- Pipeline aggregates but doesn't generate content (thin orchestration)
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from kira.core.events import create_event_bus
from kira.core.host import create_host_api
from kira.pipelines.rollup_pipeline import create_rollup_pipeline


class TestRollupPipelineOrchestration:
    """Test rollup pipeline orchestration."""

    def test_daily_creation(self, tmp_path):
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

    def test_weekly_creation(self, tmp_path):
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

    def test_publishes_request_event(self, tmp_path):
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

    def test_trace_in_entity(self, tmp_path):
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


class TestRollupPipelineThinness:
    """Test that rollup pipeline contains NO business logic."""

    def test_no_content_generation(self, tmp_path):
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


pytestmark = pytest.mark.integration

