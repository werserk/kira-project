"""Integration tests for Google Calendar sync (ADR-012)."""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kira.adapters.gcal.adapter import (
    EventMapping,
    GCalAdapter,
    GCalAdapterConfig,
    GCalEvent,
    SyncResult,
    create_gcal_adapter,
)
from kira.core.events import create_event_bus


class TestGCalEvent:
    """Test GCalEvent dataclass."""

    def test_event_creation(self) -> None:
        """Test creating a GCal event."""
        start = datetime.now(UTC)
        end = start + timedelta(hours=1)

        event = GCalEvent(
            id="test-123",
            summary="Test Event",
            start=start,
            end=end,
            description="Test description",
        )

        assert event.id == "test-123"
        assert event.summary == "Test Event"
        assert event.start == start
        assert event.end == end

    def test_event_to_dict(self) -> None:
        """Test converting event to dictionary."""
        start = datetime.now(UTC)
        end = start + timedelta(hours=1)

        event = GCalEvent(
            id="test-123",
            summary="Test Event",
            start=start,
            end=end,
            description="Test description",
            location="Test Location",
            attendees=["user@example.com"],
        )

        event_dict = event.to_dict()

        assert event_dict["summary"] == "Test Event"
        assert "start" in event_dict
        assert "end" in event_dict
        assert event_dict["description"] == "Test description"
        assert event_dict["location"] == "Test Location"
        assert len(event_dict["attendees"]) == 1

    def test_all_day_event(self) -> None:
        """Test all-day event format."""
        start = datetime.now(UTC).replace(hour=0, minute=0, second=0)
        end = start + timedelta(days=1)

        event = GCalEvent(
            id="test-123",
            summary="All Day Event",
            start=start,
            end=end,
            all_day=True,
        )

        event_dict = event.to_dict()

        assert event_dict["start"]["date"] is not None
        assert event_dict["start"]["dateTime"] is None

    def test_from_vault_entity(self) -> None:
        """Test creating GCal event from Vault entity."""
        # Mock Vault entity
        entity = MagicMock()
        entity.id = "task-123"
        entity.get_title.return_value = "Test Task"
        entity.metadata = {
            "id": "task-123",
            "start": "2025-10-07T10:00:00+00:00",
            "end": "2025-10-07T11:00:00+00:00",
            "description": "Task description",
        }

        event = GCalEvent.from_vault_entity(entity)

        assert event.summary == "Test Task"
        assert "Vault" in event.description
        assert event.id.startswith("vault-task-123")

    def test_from_vault_task_with_time_hint(self) -> None:
        """Test creating event from task with time_hint."""
        entity = MagicMock()
        entity.id = "task-123"
        entity.get_title.return_value = "Task with Time Hint"
        entity.metadata = {
            "id": "task-123",
            "due": "2025-10-07T10:00:00+00:00",
            "time_hint": "2h",  # 2 hours
        }

        event = GCalEvent.from_vault_entity(entity)

        # Should have 2 hour duration
        duration = (event.end - event.start).total_seconds()
        assert duration == 7200  # 2 hours in seconds


class TestSyncResult:
    """Test SyncResult dataclass."""

    def test_result_creation(self) -> None:
        """Test creating sync result."""
        result = SyncResult(
            pulled=10,
            pushed=5,
            conflicts=2,
            errors=1,
        )

        assert result.pulled == 10
        assert result.pushed == 5
        assert result.conflicts == 2
        assert result.errors == 1


class TestGCalAdapterConfig:
    """Test GCalAdapterConfig."""

    def test_default_config(self) -> None:
        """Test default configuration."""
        config = GCalAdapterConfig()

        assert config.calendar_id == "primary"
        assert config.sync_days_past == 7
        assert config.sync_days_future == 30
        assert config.rate_limit_delay == 0.1

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = GCalAdapterConfig(
            calendar_id="custom@calendar.com",
            sync_days_past=14,
            sync_days_future=60,
        )

        assert config.calendar_id == "custom@calendar.com"
        assert config.sync_days_past == 14
        assert config.sync_days_future == 60


class TestGCalAdapter:
    """Integration tests for GCalAdapter."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.config = GCalAdapterConfig()
        self.event_bus = create_event_bus()
        self.adapter = GCalAdapter(self.config, event_bus=self.event_bus)

    def test_adapter_initialization(self) -> None:
        """Test adapter initialization."""
        assert self.adapter is not None
        assert self.adapter.config == self.config
        assert self.adapter.event_bus == self.event_bus

    def test_pull_operation(self) -> None:
        """Test pull operation."""
        result = self.adapter.pull()

        assert isinstance(result, SyncResult)
        assert result.duration_ms > 0

    def test_pull_with_custom_calendar(self) -> None:
        """Test pull with custom calendar ID."""
        result = self.adapter.pull(calendar_id="custom@calendar.com", days=14)

        assert isinstance(result, SyncResult)

    def test_push_operation(self) -> None:
        """Test push operation."""
        # Create mock entities
        entity1 = MagicMock()
        entity1.id = "task-1"
        entity1.get_title.return_value = "Task 1"
        entity1.metadata = {
            "id": "task-1",
            "start": "2025-10-07T10:00:00+00:00",
            "time_hint": 60,
        }
        entity1.updated_at = datetime.now(UTC)

        entities = [entity1]
        result = self.adapter.push(entities)

        assert isinstance(result, SyncResult)
        assert result.pushed >= 0

    def test_push_dry_run(self) -> None:
        """Test push with dry_run flag."""
        entity = MagicMock()
        entity.id = "task-1"
        entity.get_title.return_value = "Task 1"
        entity.metadata = {
            "id": "task-1",
            "start": "2025-10-07T10:00:00+00:00",
        }
        entity.updated_at = datetime.now(UTC)

        result = self.adapter.push([entity], dry_run=True)

        assert isinstance(result, SyncResult)
        # In dry_run, nothing should be pushed
        assert result.pushed == 0

    def test_reconcile_operation(self) -> None:
        """Test reconcile operation."""
        # Create mock entities
        entity = MagicMock()
        entity.id = "event-1"
        entity.get_title.return_value = "Event 1"
        entity.metadata = {
            "id": "event-1",
            "gcal_id": "gcal-123",
            "start": "2025-10-07T10:00:00+00:00",
        }
        entity.updated_at = datetime.now(UTC)

        result = self.adapter.reconcile([entity])

        assert isinstance(result, SyncResult)
        assert result.duration_ms > 0

    def test_create_timebox(self) -> None:
        """Test creating timebox for task."""
        task = MagicMock()
        task.id = "task-123"
        task.get_title.return_value = "Important Task"
        task.metadata = {
            "id": "task-123",
            "start": datetime.now(UTC).isoformat(),
            "time_hint": 120,  # 2 hours
        }

        event_id = self.adapter.create_timebox(task)

        assert event_id is not None
        assert isinstance(event_id, str)

    def test_should_push_entity_new(self) -> None:
        """Test should_push_entity for new entity."""
        entity = MagicMock()
        entity.metadata = {
            "start": "2025-10-07T10:00:00+00:00",
        }
        entity.updated_at = datetime.now(UTC)

        should_push = self.adapter._should_push_entity(entity)
        assert should_push

    def test_should_push_entity_no_start(self) -> None:
        """Test should_push_entity without start/due."""
        entity = MagicMock()
        entity.metadata = {}
        entity.updated_at = datetime.now(UTC)

        should_push = self.adapter._should_push_entity(entity)
        assert not should_push

    def test_should_push_entity_recently_synced(self) -> None:
        """Test should_push_entity for recently synced entity."""
        now = datetime.now(UTC)
        entity = MagicMock()
        entity.metadata = {
            "start": "2025-10-07T10:00:00+00:00",
            "gcal_id": "gcal-123",
            "gcal_last_synced": now.isoformat(),
        }
        entity.updated_at = now - timedelta(hours=1)  # Updated before last sync

        should_push = self.adapter._should_push_entity(entity)
        assert not should_push

    def test_event_received_published(self) -> None:
        """Test event.received is published."""
        events_received = []

        def handler(event) -> None:
            events_received.append(event)

        self.event_bus.subscribe("event.received", handler)

        gcal_event = GCalEvent(
            id="test-123",
            summary="Test Event",
            start=datetime.now(UTC),
            end=datetime.now(UTC) + timedelta(hours=1),
        )

        self.adapter._publish_event_received(gcal_event, "trace-123")

        assert len(events_received) == 1
        assert events_received[0].payload["gcal_id"] == "test-123"
        assert events_received[0].payload["source"] == "gcal"

    def test_logging_to_file(self) -> None:
        """Test logging to file."""
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "gcal.jsonl"

            config = GCalAdapterConfig(log_path=log_path)
            adapter = GCalAdapter(config)

            adapter._log_event("test_event", {"key": "value"})

            assert log_path.exists()
            with open(log_path) as f:
                lines = f.readlines()

            assert len(lines) == 1
            log_entry = json.loads(lines[0])

            assert log_entry["event_type"] == "test_event"
            assert log_entry["adapter"] == "gcal"
            assert log_entry["key"] == "value"


class TestGCalAdapterFactory:
    """Test factory function."""

    def test_create_adapter(self) -> None:
        """Test adapter factory."""
        adapter = create_gcal_adapter()

        assert adapter is not None
        assert isinstance(adapter, GCalAdapter)

    def test_create_adapter_with_event_bus(self) -> None:
        """Test adapter with event bus."""
        event_bus = create_event_bus()
        adapter = create_gcal_adapter(event_bus=event_bus)

        assert adapter.event_bus == event_bus

    def test_create_adapter_with_config(self) -> None:
        """Test adapter with custom config."""
        adapter = create_gcal_adapter(
            calendar_id="test@calendar.com",
            sync_days_past=14,
        )

        assert adapter.config.calendar_id == "test@calendar.com"
        assert adapter.config.sync_days_past == 14


class TestCalendarPlugin:
    """Test calendar plugin functionality."""

    def test_plugin_activation(self) -> None:
        """Test plugin activation."""
        from kira.plugin_sdk.context import PluginContext
        from kira.plugins.calendar.src.kira_plugin_calendar.plugin import activate

        # Mock context
        context = MagicMock(spec=PluginContext)
        context.logger = MagicMock()
        context.events = create_event_bus()

        result = activate(context)

        assert result["status"] == "ok"
        assert result["plugin"] == "kira-calendar"

    def test_event_handlers_registered(self) -> None:
        """Test event handlers are registered."""
        from kira.plugin_sdk.context import PluginContext
        from kira.plugins.calendar.src.kira_plugin_calendar.plugin import CalendarPlugin

        context = MagicMock(spec=PluginContext)
        context.logger = MagicMock()
        context.events = create_event_bus()

        CalendarPlugin(context)

        # Check that handlers are registered
        subscriptions = context.events.get_subscriptions()
        assert len(subscriptions) > 0

    def test_handle_task_enter_doing(self) -> None:
        """Test handling task.enter_doing event."""
        from kira.plugin_sdk.context import PluginContext
        from kira.plugins.calendar.src.kira_plugin_calendar.plugin import CalendarPlugin

        context = MagicMock(spec=PluginContext)
        context.logger = MagicMock()
        context.events = create_event_bus()

        plugin = CalendarPlugin(context)

        # Trigger task.enter_doing
        event = MagicMock()
        event.payload = {
            "task_id": "task-123",
            "time_hint": 120,
        }

        plugin._handle_task_enter_doing(event)

        # Should create mapping
        assert "task-123" in plugin._mappings


class TestEventMapping:
    """Test EventMapping dataclass."""

    def test_mapping_creation(self) -> None:
        """Test creating event mapping."""
        now = datetime.now(UTC)

        mapping = EventMapping(
            vault_id="event-123",
            gcal_id="gcal-456",
            vault_updated=now,
            gcal_updated=now,
            last_synced=now,
            sync_direction="bidirectional",
        )

        assert mapping.vault_id == "event-123"
        assert mapping.gcal_id == "gcal-456"
        assert mapping.sync_direction == "bidirectional"


class TestTimeboxing:
    """Test timeboxing functionality."""

    def test_timebox_creation_flow(self) -> None:
        """Test complete timeboxing flow."""
        event_bus = create_event_bus()
        adapter = create_gcal_adapter(event_bus=event_bus)

        # Create task
        task = MagicMock()
        task.id = "task-123"
        task.get_title.return_value = "Important Task"
        task.metadata = {
            "id": "task-123",
            "start": datetime.now(UTC).isoformat(),
            "time_hint": "2h",
        }

        # Create timebox
        event_id = adapter.create_timebox(task)

        assert event_id is not None

    def test_timebox_with_default_duration(self) -> None:
        """Test timebox with default duration."""
        event_bus = create_event_bus()
        adapter = create_gcal_adapter(event_bus=event_bus)

        task = MagicMock()
        task.id = "task-456"
        task.get_title.return_value = "Task without time_hint"
        task.metadata = {
            "id": "task-456",
            "start": datetime.now(UTC).isoformat(),
            # No time_hint - should use default
        }

        event_id = adapter.create_timebox(task)

        assert event_id is not None


class TestConflictResolution:
    """Test conflict resolution."""

    def test_last_writer_wins(self) -> None:
        """Test last-writer-wins conflict resolution."""
        adapter = create_gcal_adapter()

        # Mock entities with different timestamps
        now = datetime.now(UTC)

        vault_entity = MagicMock()
        vault_entity.id = "event-123"
        vault_entity.updated_at = now  # Newer
        vault_entity.metadata = {
            "gcal_id": "gcal-123",
            "start": "2025-10-07T10:00:00+00:00",
        }

        result = adapter.reconcile([vault_entity])

        # Reconciliation should handle conflicts
        assert isinstance(result, SyncResult)


class TestRateLimiting:
    """Test rate limiting."""

    def test_rate_limit_delay(self) -> None:
        """Test rate limiting delay is applied."""
        import time

        config = GCalAdapterConfig(rate_limit_delay=0.01)
        adapter = GCalAdapter(config)

        entity = MagicMock()
        entity.id = "task-1"
        entity.get_title.return_value = "Task 1"
        entity.metadata = {
            "id": "task-1",
            "start": "2025-10-07T10:00:00+00:00",
        }
        entity.updated_at = datetime.now(UTC)

        start_time = time.time()
        adapter.push([entity, entity])
        duration = time.time() - start_time

        # Should have delays
        assert duration >= 0.01


class TestErrorHandling:
    """Test error handling."""

    def test_pull_with_exception(self) -> None:
        """Test pull handles exceptions gracefully."""
        adapter = create_gcal_adapter()

        # Pull should not raise exception
        result = adapter.pull()

        assert isinstance(result, SyncResult)
        # May have errors but should complete

    def test_push_with_invalid_entity(self) -> None:
        """Test push handles invalid entities."""
        adapter = create_gcal_adapter()

        # Entity without required fields
        invalid_entity = MagicMock()
        invalid_entity.id = "invalid"
        invalid_entity.get_title.side_effect = Exception("Error")
        invalid_entity.metadata = {}

        result = adapter.push([invalid_entity])

        assert isinstance(result, SyncResult)
        assert result.errors > 0
