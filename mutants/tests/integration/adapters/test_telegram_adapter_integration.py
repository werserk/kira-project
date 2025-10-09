"""Integration tests for Telegram adapter.

Tests verify:
- Telegram confirmation flow works
- Idempotency is preserved for duplicate messages
- Briefing generation works with vault data
"""

import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kira.adapters.telegram.adapter import BriefingScheduler, TelegramAdapter, TelegramAdapterConfig, TelegramMessage
from kira.core.events import EventBus
from kira.core.host import create_host_api


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


@pytest.fixture
def test_vault():
    """Create test vault with host API."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir) / "vault"
        host_api = create_host_api(vault_path)
        yield host_api


class TestTelegramConfirmationFlow:
    """Test Telegram confirmation flow (E2E minimal adapter)."""

    def test_confirmation_flow(self, test_telegram_env):
        """Minimal E2E confirmation flow works, idempotency preserved.

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


class TestTelegramIdempotency:
    """Test Telegram message idempotency."""

    def test_message_idempotency(self, test_telegram_env):
        """Idempotency preserved for duplicate Telegram messages.

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


class TestTelegramBriefing:
    """Test Telegram briefing generation."""

    def test_briefing_generation(self, test_vault):
        """Briefing generator works with vault data.

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


class TestTelegramAcceptance:
    """Acceptance tests for Telegram integration."""

    def test_acceptance_e2e_flow(self, test_telegram_env):
        """Telegram E2E confirmation flow works."""
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


pytestmark = pytest.mark.integration

