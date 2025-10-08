"""Integration tests for Phase 7 - Post-release Integrations.

Phase 7 DoD:
22. GCal import-only: no duplicates, TZ correct, x-kira metadata
23. GCal two-way: echo-break, conflict resolution (latest last_write_ts wins)
24. Telegram E2E: confirmation flow works, idempotency preserved
"""

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from kira.adapters.gcal.adapter import GCalAdapter, GCalAdapterConfig
from kira.adapters.telegram.adapter import (
    BriefingScheduler,
    TelegramAdapter,
    TelegramAdapterConfig,
    TelegramMessage,
)
from kira.core.events import EventBus
from kira.core.host import create_host_api
from kira.sync.contract import create_kira_sync_contract, create_remote_sync_contract, get_sync_version
from kira.sync.ledger import SyncLedger, resolve_conflict, should_import_remote_update


@pytest.fixture
def test_vault():
    """Create test vault with host API."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"
        host_api = create_host_api(vault_path)
        yield host_api


@pytest.fixture
def test_gcal_env():
    """Create test environment with GCal adapter and sync ledger."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"
        host_api = create_host_api(vault_path)

        ledger_path = vault_path / "artifacts" / "sync_ledger.db"
        ledger = SyncLedger(ledger_path)

        config = GCalAdapterConfig(
            calendar_id="test-calendar",
            log_path=vault_path / "logs" / "gcal.jsonl",
        )
        adapter = GCalAdapter(config)

        yield host_api, ledger, adapter

        ledger.close()


@pytest.fixture
def test_telegram_env():
    """Create test environment with Telegram adapter."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"
        host_api = create_host_api(vault_path)

        event_bus = EventBus()

        config = TelegramAdapterConfig(
            bot_token="test-token",
            allowed_chat_ids=[12345],
            log_path=vault_path / "logs" / "telegram.jsonl",
        )
        adapter = TelegramAdapter(config, event_bus=event_bus)

        yield host_api, event_bus, adapter


# =============================================================================
# Phase 7, Point 22: GCal Import-Only Mode
# =============================================================================


def test_gcal_import_only_mode_no_duplicates(test_gcal_env):
    """DoD: GCal import creates event with x-kira metadata, no duplicates on re-import.

    Scenario:
    1. Import GCal event with remote_id=gcal-123
    2. Record in ledger
    3. Import same event again
    4. Verify ledger prevents duplicate
    """
    host_api, ledger, _adapter = test_gcal_env

    gcal_event_id = "gcal-event-import-test"

    # Step 1: First import from GCal
    metadata = {
        "title": "Team Standup",
        "start_time": datetime.now(UTC).isoformat(),
        "end_time": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        "tags": ["work"],
    }

    # Create with remote sync contract (x-kira metadata)
    metadata_v1 = create_remote_sync_contract(
        metadata,
        source="gcal",
        remote_id=gcal_event_id,
        etag="etag-v1",
    )

    # Verify x-kira metadata
    assert "x-kira" in metadata_v1
    assert metadata_v1["x-kira"]["source"] == "gcal"
    assert metadata_v1["x-kira"]["remote_id"] == gcal_event_id
    assert metadata_v1["x-kira"]["version"] == 1
    assert "last_write_ts" in metadata_v1["x-kira"]

    # Create event in vault
    entity = host_api.create_entity("event", metadata_v1)
    entity_id = entity.id

    # Step 2: Record in ledger
    ledger.record_sync(
        remote_id=gcal_event_id,
        version=1,
        etag="etag-v1",
        entity_id=entity_id,
    )

    # Step 3: Attempt re-import (same version)
    should_import = ledger.should_import(gcal_event_id, remote_version=1, remote_etag="etag-v1")

    # Step 4: Verify no duplicate import
    assert should_import is False, "Ledger should prevent duplicate import"

    # Verify only one event exists
    events = list(host_api.list_entities("event"))
    assert len(events) == 1


def test_gcal_import_timezone_correctness(test_gcal_env):
    """DoD: GCal import preserves UTC timestamps correctly.

    Scenario:
    1. Import GCal event with specific UTC timestamp
    2. Verify stored timestamp is in UTC
    3. Verify no timezone conversion errors
    """
    host_api, ledger, _adapter = test_gcal_env

    # Create event with explicit UTC timestamp
    start_utc = datetime(2025, 10, 15, 14, 30, 0, tzinfo=UTC)
    end_utc = datetime(2025, 10, 15, 15, 30, 0, tzinfo=UTC)

    metadata = {
        "title": "Timezone Test Event",
        "start_time": start_utc.isoformat(),
        "end_time": end_utc.isoformat(),
        "tags": ["test"],
    }

    metadata_synced = create_remote_sync_contract(
        metadata,
        source="gcal",
        remote_id="gcal-tz-test",
        etag="etag-tz",
    )

    # Create event
    entity = host_api.create_entity("event", metadata_synced)

    # Verify timestamps are preserved in UTC
    assert entity.metadata["start_time"] == start_utc.isoformat()
    assert entity.metadata["end_time"] == end_utc.isoformat()

    # Verify x-kira metadata includes correct last_write_ts
    last_write_ts_str = entity.metadata["x-kira"]["last_write_ts"]
    last_write_ts = datetime.fromisoformat(last_write_ts_str.replace("Z", "+00:00"))

    # Should be recent and in UTC
    assert last_write_ts.tzinfo == UTC
    assert abs((datetime.now(UTC) - last_write_ts).total_seconds()) < 5

    # Record in ledger
    ledger.record_sync("gcal-tz-test", version=1, etag="etag-tz", entity_id=entity.id)


def test_gcal_import_ledger_tracking(test_gcal_env):
    """DoD: Ledger tracks remote_id→version_seen/etag for import deduplication.

    Scenario:
    1. Import event with version 1
    2. Check ledger has recorded version
    3. Import same event with version 2 (actual change)
    4. Verify ledger allows import
    """
    _host_api, ledger, _adapter = test_gcal_env

    gcal_event_id = "gcal-ledger-test"

    # Step 1: Record version 1
    ledger.record_sync(gcal_event_id, version=1, etag="etag-v1")

    # Step 2: Verify version recorded
    entry = ledger.get_entry(gcal_event_id)
    assert entry is not None
    assert entry.version_seen == 1
    assert entry.etag_seen == "etag-v1"

    # Step 3: Check if version 2 should be imported (actual change)
    should_import_v2 = ledger.should_import(gcal_event_id, remote_version=2, remote_etag="etag-v2")

    # Step 4: Verify import allowed for new version
    assert should_import_v2 is True, "Ledger should allow import of new version"

    # Update ledger
    ledger.record_sync(gcal_event_id, version=2, etag="etag-v2")

    # Verify updated
    entry_updated = ledger.get_entry(gcal_event_id)
    assert entry_updated.version_seen == 2
    assert entry_updated.etag_seen == "etag-v2"


# =============================================================================
# Phase 7, Point 23: GCal Two-Way Sync with Echo-Break
# =============================================================================


def test_gcal_twoway_echo_break(test_gcal_env):
    """DoD: Kira→GCal→Kira test yields single authoritative state, no echo loops.

    Scenario:
    1. Kira writes event (version 1, source=kira)
    2. Export to GCal (version 2, source=kira)
    3. Record export in ledger
    4. GCal echoes back (version 2, no change)
    5. Verify echo detected, no re-import
    """
    host_api, ledger, _adapter = test_gcal_env

    gcal_event_id = "gcal-echo-test"

    # Step 1: Kira creates event
    metadata = {
        "title": "My Meeting",
        "start_time": datetime.now(UTC).isoformat(),
        "end_time": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        "tags": ["personal"],
    }

    metadata_v1 = create_kira_sync_contract(metadata)
    entity = host_api.create_entity("event", metadata_v1)

    assert get_sync_version(metadata_v1) == 1
    assert metadata_v1["x-kira"]["source"] == "kira"

    # Step 2: Export to GCal (simulate GCal assigning ID and incrementing version)
    metadata_v2 = create_kira_sync_contract(
        metadata_v1,
        remote_id=gcal_event_id,
    )
    assert get_sync_version(metadata_v2) == 2

    # Update entity
    host_api.update_entity(entity.id, metadata_v2)

    # Step 3: Record export in ledger
    ledger.record_sync(
        remote_id=gcal_event_id,
        version=2,
        etag="etag-export-v2",
        entity_id=entity.id,
    )

    # Step 4: GCal echoes back (same version, no actual change)
    is_echo = ledger.is_echo(gcal_event_id, remote_version=2)
    should_import = ledger.should_import(gcal_event_id, remote_version=2, remote_etag="etag-export-v2")

    # Step 5: Verify echo detected
    assert is_echo is True, "Echo loop not detected!"
    assert should_import is False, "Echo should not be imported!"

    # Verify only one event exists (no duplicate)
    events = list(host_api.list_entities("event"))
    assert len(events) == 1


def test_gcal_conflict_resolution_latest_wins(test_gcal_env):
    """DoD: Conflicts resolved by latest(last_write_ts).

    Scenario:
    1. Event in Vault: last_write_ts = T1
    2. Event in GCal: last_write_ts = T2 (later)
    3. Resolve conflict
    4. Verify GCal version wins (T2 > T1)
    """
    host_api, _ledger, _adapter = test_gcal_env

    # Create vault entity with earlier timestamp
    t1 = datetime.now(UTC) - timedelta(minutes=10)
    vault_metadata = {
        "title": "Vault Version",
        "start_time": datetime.now(UTC).isoformat(),
        "tags": ["vault"],
        "x-kira": {
            "source": "kira",
            "version": 1,
            "last_write_ts": t1.isoformat(),
        },
    }
    vault_entity = host_api.create_entity("event", vault_metadata)

    # Simulate GCal version with later timestamp (ensure later than t1)
    t2 = datetime.now(UTC) + timedelta(seconds=1)
    gcal_metadata = {
        "title": "GCal Version (Newer)",
        "start_time": datetime.now(UTC).isoformat(),
        "tags": ["gcal"],
        "x-kira": {
            "source": "gcal",
            "version": 2,
            "last_write_ts": t2.isoformat(),
            "remote_id": "gcal-conflict-test",
        },
    }

    # Resolve conflict
    resolution = resolve_conflict(
        local_last_write_ts=vault_metadata["x-kira"]["last_write_ts"],
        remote_last_write_ts=gcal_metadata["x-kira"]["last_write_ts"],
    )

    # Verify GCal version wins (latest timestamp)
    assert resolution == "remote", f"Expected 'remote' to win, got '{resolution}'"
    assert gcal_metadata["x-kira"]["last_write_ts"] > vault_metadata["x-kira"]["last_write_ts"]


def test_gcal_kira_writes_increment_version(test_gcal_env):
    """DoD: Kira writes increment version when pushing to GCal.

    Scenario:
    1. Import event from GCal (version 1)
    2. Kira edits event
    3. Verify version incremented to 2
    4. Push to GCal
    5. Verify version is 3
    """
    host_api, ledger, _adapter = test_gcal_env

    gcal_event_id = "gcal-version-test"

    # Step 1: Import from GCal (version 1)
    metadata = {
        "title": "Original",
        "start_time": datetime.now(UTC).isoformat(),
        "tags": [],
    }
    metadata_v1 = create_remote_sync_contract(
        metadata,
        source="gcal",
        remote_id=gcal_event_id,
    )
    entity = host_api.create_entity("event", metadata_v1)

    assert get_sync_version(metadata_v1) == 1

    # Record in ledger
    ledger.record_sync(gcal_event_id, version=1, entity_id=entity.id)

    # Step 2: Kira edits event
    metadata_v2 = create_kira_sync_contract(
        metadata_v1,
        remote_id=gcal_event_id,
    )
    metadata_v2["title"] = "Edited by Kira"

    # Step 3: Verify version incremented
    assert get_sync_version(metadata_v2) == 2
    assert metadata_v2["x-kira"]["source"] == "kira"

    # Update entity
    updated_entity = host_api.update_entity(entity.id, metadata_v2)

    # Step 4: Push to GCal (would increment version again in real scenario)
    metadata_v3 = create_kira_sync_contract(
        metadata_v2,
        remote_id=gcal_event_id,
    )

    # Step 5: Verify version is 3
    assert get_sync_version(metadata_v3) == 3

    # Update final version
    host_api.update_entity(updated_entity.id, metadata_v3)

    # Record final push
    ledger.record_sync(gcal_event_id, version=3, entity_id=entity.id)


def test_gcal_round_trip_yields_authoritative_state(test_gcal_env):
    """DoD: Full Kira→GCal→Kira round-trip yields single authoritative state.

    Scenario:
    1. Kira creates event
    2. Push to GCal
    3. GCal modifies and echoes back
    4. Verify single authoritative state (no duplicates)
    """
    host_api, ledger, _adapter = test_gcal_env

    gcal_event_id = "gcal-roundtrip-test"

    # Step 1: Kira creates event
    metadata = {
        "title": "Round Trip Event",
        "start_time": datetime.now(UTC).isoformat(),
        "end_time": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        "tags": ["test"],
    }
    metadata_v1 = create_kira_sync_contract(metadata)
    entity = host_api.create_entity("event", metadata_v1)

    # Step 2: Push to GCal (assign remote_id)
    metadata_v2 = create_kira_sync_contract(
        metadata_v1,
        remote_id=gcal_event_id,
    )
    host_api.update_entity(entity.id, metadata_v2)
    ledger.record_sync(gcal_event_id, version=2, entity_id=entity.id)

    # Step 3: GCal echoes back (same version = echo)
    should_import = should_import_remote_update(
        ledger=ledger,
        remote_id=gcal_event_id,
        remote_version=2,
    )

    # Step 4: Verify no import (echo detected)
    assert should_import is False, "Echo should be ignored"

    # Verify single event exists
    events = list(host_api.list_entities("event"))
    assert len(events) == 1
    assert events[0].id == entity.id


# =============================================================================
# Phase 7, Point 24: Telegram E2E Minimal Adapter
# =============================================================================


def test_telegram_confirmation_flow(test_telegram_env):
    """DoD: Minimal E2E confirmation flow works, idempotency preserved.

    Scenario:
    1. Telegram message received
    2. Request confirmation
    3. User confirms
    4. Callback handler executed
    5. Verify idempotency (duplicate message ignored)
    """
    host_api, _event_bus, adapter = test_telegram_env

    # Step 1: Simulate message received
    message = TelegramMessage(
        message_id=101,
        chat_id=12345,
        user_id=67890,
        text="Create task: Fix bug",
        timestamp=int(datetime.now(UTC).timestamp()),
    )

    # Track if handler was called
    handler_called = {"count": 0, "context": None}

    def confirmation_handler(context):
        handler_called["count"] += 1
        handler_called["context"] = context

        # Create task in vault
        if context["choice"] == "yes":
            host_api.create_entity(
                "task",
                {
                    "title": context["title"],
                    "status": "todo",
                    "tags": ["telegram"],
                },
            )

    # Step 2: Register handler and request confirmation
    adapter.register_command_handler("inbox.confirm_task", confirmation_handler)

    request_id = adapter.request_confirmation(
        chat_id=12345,
        message="Create task: 'Fix bug'?",
        options=[
            {"text": "✅ Yes", "callback_data": "yes"},
            {"text": "❌ No", "callback_data": "no"},
        ],
        command="inbox.confirm_task",
        context={"title": "Fix bug", "message_id": 101},
    )

    assert request_id.startswith("req-")

    # Step 3: Simulate user confirmation (callback)
    confirmation = adapter._pending_confirmations[request_id]
    signed_callback = confirmation.options[0]["callback_data"]  # First option (Yes)

    # Parse signed callback
    parts = signed_callback.split(":", 2)
    assert len(parts) == 3
    _req_id, _choice, _signature = parts

    # Simulate callback query
    callback_data = {
        "id": "callback-123",
        "data": signed_callback,
        "message": {"chat": {"id": 12345}},
        "from": {"id": 67890},
    }

    # Step 4: Handle callback (this executes the handler)
    adapter._handle_callback_query(callback_data, trace_id="test-trace")

    # Verify handler was called
    assert handler_called["count"] == 1
    assert handler_called["context"]["choice"] == "yes"
    assert handler_called["context"]["title"] == "Fix bug"

    # Verify task created
    tasks = list(host_api.list_entities("task"))
    assert len(tasks) == 1
    assert tasks[0].metadata["title"] == "Fix bug"

    # Step 5: Test idempotency - process same message again
    idempotency_key = message.get_idempotency_key()
    adapter._processed_updates.add(idempotency_key)

    # Try to process duplicate
    adapter._handle_message(message, trace_id="test-trace-2")

    # Handler should NOT be called again (already processed)
    assert handler_called["count"] == 1, "Duplicate message should be ignored"


def test_telegram_message_idempotency(test_telegram_env):
    """DoD: Idempotency preserved for duplicate Telegram messages.

    Scenario:
    1. Process message A
    2. Publish event.received
    3. Process message A again (duplicate)
    4. Verify no duplicate event published
    """
    _host_api, event_bus, adapter = test_telegram_env

    events_received = []

    def on_message_received(payload):
        events_received.append(payload)

    event_bus.subscribe("message.received", on_message_received)

    # Step 1: Process first message
    message = TelegramMessage(
        message_id=202,
        chat_id=12345,
        user_id=67890,
        text="Test message",
        timestamp=int(datetime.now(UTC).timestamp()),
    )

    adapter._handle_message(message, trace_id="trace-1")

    # Step 2: Verify event published
    assert len(events_received) == 1
    assert events_received[0].payload["message"] == "Test message"

    # Step 3: Process duplicate message
    adapter._handle_message(message, trace_id="trace-2")

    # Step 4: Verify no duplicate event
    assert len(events_received) == 1, "Duplicate message should be ignored by idempotency"


def test_telegram_briefing_generation(test_vault):
    """DoD: Briefing generator works with vault data.

    Scenario:
    1. Create tasks in vault
    2. Generate daily briefing
    3. Verify briefing contains task count
    """
    host_api = test_vault

    # Step 1: Create tasks
    today = datetime.now(UTC).date()
    due_today = datetime.combine(today, datetime.min.time(), tzinfo=UTC)

    for i in range(3):
        host_api.create_entity(
            "task",
            {
                "title": f"Task {i + 1}",
                "status": "todo",
                "due": due_today.isoformat(),
                "tags": ["work"],
            },
        )

    # Step 2: Generate briefing
    briefing_scheduler = BriefingScheduler(host_api=host_api)
    daily_briefing = briefing_scheduler.generate_daily_briefing()

    # Step 3: Verify briefing content
    assert "Good Morning" in daily_briefing
    assert "Tasks Due Today" in daily_briefing
    assert "3" in daily_briefing or "Task 1" in daily_briefing

    # Test weekly briefing
    weekly_briefing = briefing_scheduler.generate_weekly_briefing()
    assert "Weekly Summary" in weekly_briefing


# =============================================================================
# Phase 7 Acceptance Tests
# =============================================================================


def test_phase7_acceptance_gcal_import_mode(test_gcal_env):
    """Phase 7 Acceptance: GCal import-only mode works end-to-end."""
    host_api, ledger, _adapter = test_gcal_env

    # Import multiple events
    for i in range(3):
        gcal_id = f"gcal-event-{i}"
        metadata = {
            "title": f"Event {i}",
            "start_time": (datetime.now(UTC) + timedelta(hours=i)).isoformat(),
            "tags": ["imported"],
        }

        metadata_synced = create_remote_sync_contract(
            metadata,
            source="gcal",
            remote_id=gcal_id,
        )

        entity = host_api.create_entity("event", metadata_synced)
        ledger.record_sync(gcal_id, version=1, entity_id=entity.id)

    # Verify all imported
    events = list(host_api.list_entities("event"))
    assert len(events) == 3

    # Verify no duplicates on re-import
    for i in range(3):
        gcal_id = f"gcal-event-{i}"
        should_import = ledger.should_import(gcal_id, remote_version=1)
        assert should_import is False

    # All events have x-kira metadata
    for event in events:
        assert "x-kira" in event.metadata
        assert event.metadata["x-kira"]["source"] == "gcal"


def test_phase7_acceptance_telegram_e2e(test_telegram_env):
    """Phase 7 Acceptance: Telegram E2E confirmation flow works."""
    host_api, _event_bus, adapter = test_telegram_env

    confirmed_tasks = []

    def task_handler(context):
        if context["choice"] == "yes":
            task = host_api.create_entity(
                "task",
                {
                    "title": context["title"],
                    "status": "todo",
                    "tags": ["telegram"],
                },
            )
            confirmed_tasks.append(task)

    adapter.register_command_handler("create.task", task_handler)

    # Request confirmation
    request_id = adapter.request_confirmation(
        chat_id=12345,
        message="Create task?",
        options=[
            {"text": "Yes", "callback_data": "yes"},
            {"text": "No", "callback_data": "no"},
        ],
        command="create.task",
        context={"title": "Test Task"},
    )

    # Simulate confirmation
    confirmation = adapter._pending_confirmations[request_id]
    callback_data = {
        "id": "cb-1",
        "data": confirmation.options[0]["callback_data"],
        "message": {"chat": {"id": 12345}},
        "from": {"id": 67890},
    }

    adapter._handle_callback_query(callback_data, "trace")

    # Verify task created
    assert len(confirmed_tasks) == 1
    assert confirmed_tasks[0].metadata["title"] == "Test Task"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
