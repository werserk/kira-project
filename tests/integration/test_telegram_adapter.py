"""Integration tests for telegram adapter (ADR-011)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kira.adapters.telegram.adapter import (
    BriefingScheduler,
    ConfirmationRequest,
    TelegramAdapter,
    TelegramAdapterConfig,
    TelegramMessage,
    TelegramUpdate,
    create_telegram_adapter,
)
from kira.core.events import create_event_bus
from kira.core.scheduler import create_scheduler


class TestTelegramAdapterConfig:
    """Test TelegramAdapterConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = TelegramAdapterConfig(bot_token="test_token")

        assert config.bot_token == "test_token"
        assert config.polling_timeout == 30
        assert config.polling_interval == 1.0
        assert config.daily_briefing_time == "09:00"
        assert config.weekly_briefing_day == 1  # Monday

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = TelegramAdapterConfig(
            bot_token="test_token",
            allowed_chat_ids=[123, 456],
            daily_briefing_time="08:30",
            weekly_briefing_day=5,  # Friday
        )

        assert config.allowed_chat_ids == [123, 456]
        assert config.daily_briefing_time == "08:30"
        assert config.weekly_briefing_day == 5


class TestConfirmationRequest:
    """Test ConfirmationRequest."""

    def test_confirmation_request_creation(self) -> None:
        """Test creation of confirmation request."""
        request = ConfirmationRequest(
            request_id="test-123",
            chat_id=12345,
            message="Test message",
            options=[{"text": "Yes", "callback_data": "yes"}],
            command="test.command",
        )

        assert request.request_id == "test-123"
        assert request.chat_id == 12345
        assert request.message == "Test message"
        assert len(request.options) == 1

    def test_confirmation_request_expiration(self) -> None:
        """Test expiration check."""
        import time

        # Not expired
        request = ConfirmationRequest(
            request_id="test-123",
            chat_id=12345,
            message="Test",
            options=[],
            command="test",
            expires_at=time.time() + 3600,
        )
        assert not request.is_expired()

        # Expired
        expired_request = ConfirmationRequest(
            request_id="test-123",
            chat_id=12345,
            message="Test",
            options=[],
            command="test",
            expires_at=time.time() - 1,
        )
        assert expired_request.is_expired()

    def test_get_inline_keyboard(self) -> None:
        """Test inline keyboard generation."""
        request = ConfirmationRequest(
            request_id="test-123",
            chat_id=12345,
            message="Test",
            options=[
                {"text": "Yes", "callback_data": "yes"},
                {"text": "No", "callback_data": "no"},
            ],
            command="test",
        )

        keyboard = request.get_inline_keyboard()
        assert "inline_keyboard" in keyboard
        assert len(keyboard["inline_keyboard"][0]) == 2


class TestTelegramMessage:
    """Test TelegramMessage."""

    def test_message_creation(self) -> None:
        """Test message creation."""
        msg = TelegramMessage(
            message_id=1,
            chat_id=123,
            user_id=456,
            text="Hello",
            timestamp=1234567890,
        )

        assert msg.message_id == 1
        assert msg.chat_id == 123
        assert msg.user_id == 456
        assert msg.text == "Hello"

    def test_idempotency_key(self) -> None:
        """Test idempotency key generation."""
        msg = TelegramMessage(
            message_id=1,
            chat_id=123,
            user_id=456,
        )

        key = msg.get_idempotency_key()
        assert key == "123:1"


class TestTelegramAdapter:
    """Integration tests for TelegramAdapter."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.config = TelegramAdapterConfig(
            bot_token="test_token",
            allowed_chat_ids=[123456789],
        )
        self.event_bus = create_event_bus()
        self.scheduler = create_scheduler()
        self.adapter = TelegramAdapter(
            self.config,
            event_bus=self.event_bus,
            scheduler=self.scheduler,
        )

    def test_adapter_initialization(self) -> None:
        """Test adapter initialization."""
        assert self.adapter is not None
        assert self.adapter.config == self.config
        assert self.adapter.event_bus == self.event_bus
        assert self.adapter.scheduler == self.scheduler
        assert not self.adapter._running

    def test_send_message(self) -> None:
        """Test sending a message."""
        # send_message uses _api_request which is a placeholder
        response = self.adapter.send_message(123456, "Test message")
        assert response is not None

    def test_send_message_with_keyboard(self) -> None:
        """Test sending message with inline keyboard."""
        keyboard = {
            "inline_keyboard": [
                [{"text": "Button 1", "callback_data": "btn1"}]
            ]
        }

        response = self.adapter.send_message(
            123456,
            "Test message",
            reply_markup=keyboard,
        )
        assert response is not None

    def test_register_command_handler(self) -> None:
        """Test registering command handler."""
        handler_called = False

        def test_handler(context: dict) -> None:
            nonlocal handler_called
            handler_called = True

        self.adapter.register_command_handler("test.command", test_handler)
        assert "test.command" in self.adapter._command_handlers

    def test_request_confirmation(self) -> None:
        """Test requesting confirmation."""
        request_id = self.adapter.request_confirmation(
            chat_id=123456,
            message="Is this correct?",
            options=[
                {"text": "✅ Yes", "callback_data": "yes"},
                {"text": "❌ No", "callback_data": "no"},
            ],
            command="test.confirm",
            context={"test_key": "test_value"},
        )

        assert request_id.startswith("req-")
        assert request_id in self.adapter._pending_confirmations

        # Verify CSRF tokens were added
        confirmation = self.adapter._pending_confirmations[request_id]
        for opt in confirmation.options:
            assert ":" in opt["callback_data"]  # Should contain signature

    def test_csrf_token_generation(self) -> None:
        """Test CSRF token generation."""
        request_id = "test-123"
        callback_data = "yes"

        token1 = self.adapter._generate_csrf_token(request_id, callback_data)
        token2 = self.adapter._generate_csrf_token(request_id, callback_data)

        # Same inputs should produce same token
        assert token1 == token2

        # Different inputs should produce different tokens
        token3 = self.adapter._generate_csrf_token(request_id, "no")
        assert token1 != token3

    def test_csrf_token_verification(self) -> None:
        """Test CSRF token verification."""
        request_id = "test-123"
        callback_data = "yes"

        token = self.adapter._generate_csrf_token(request_id, callback_data)

        # Valid token
        assert self.adapter._verify_csrf_token(request_id, callback_data, token)

        # Invalid token
        assert not self.adapter._verify_csrf_token(request_id, callback_data, "invalid")

        # Wrong callback data
        assert not self.adapter._verify_csrf_token(request_id, "no", token)

    def test_send_daily_briefing(self) -> None:
        """Test sending daily briefing."""
        success = self.adapter.send_daily_briefing(123456, "Test briefing content")
        assert success

    def test_send_daily_briefing_with_generator(self) -> None:
        """Test daily briefing with generator function."""

        def test_generator(briefing_type: str) -> str:
            return f"Generated {briefing_type} briefing"

        self.adapter.set_briefing_generator(test_generator)
        success = self.adapter.send_daily_briefing(123456)
        assert success

    def test_send_weekly_briefing(self) -> None:
        """Test sending weekly briefing."""
        success = self.adapter.send_weekly_briefing(123456, "Test weekly briefing")
        assert success

    def test_message_idempotency(self) -> None:
        """Test message deduplication."""
        message = TelegramMessage(
            message_id=1,
            chat_id=123456789,
            user_id=456,
            text="Test",
        )

        # First message should be processed
        self.adapter._handle_message(message, "trace-1")
        assert message.get_idempotency_key() in self.adapter._processed_updates

        # Duplicate should be skipped
        events_published = len(self.event_bus.get_stats())
        self.adapter._handle_message(message, "trace-2")
        # Should not publish new events
        assert len(self.event_bus.get_stats()) == events_published

    def test_whitelist_enforcement(self) -> None:
        """Test whitelist enforcement."""
        # Allowed chat
        assert self.adapter._is_allowed(123456789, 999)

        # Not allowed (config has whitelist)
        assert not self.adapter._is_allowed(999999, 999)

    def test_message_received_event(self) -> None:
        """Test message.received event publishing."""
        events_received = []

        def handler(event):
            events_received.append(event)

        self.event_bus.subscribe("message.received", handler)

        message = TelegramMessage(
            message_id=1,
            chat_id=123456789,
            user_id=456,
            text="Hello world",
            timestamp=1234567890,
        )

        self.adapter._handle_message(message, "trace-123")

        assert len(events_received) == 1
        assert events_received[0].payload["message"] == "Hello world"
        assert events_received[0].payload["source"] == "telegram"

    def test_file_dropped_event(self) -> None:
        """Test file.dropped event publishing."""
        events_received = []

        def handler(event):
            events_received.append(event)

        self.event_bus.subscribe("file.dropped", handler)

        message = TelegramMessage(
            message_id=1,
            chat_id=123456789,
            user_id=456,
            document={"file_id": "file123", "mime_type": "application/pdf", "file_size": 1024},
            timestamp=1234567890,
        )

        self.adapter._handle_message(message, "trace-123")

        assert len(events_received) == 1
        assert events_received[0].payload["file_id"] == "file123"
        assert events_received[0].payload["mime_type"] == "application/pdf"

    def test_callback_query_handling(self) -> None:
        """Test callback query handling with confirmation."""
        handler_called = []

        def test_handler(context: dict) -> None:
            handler_called.append(context)

        self.adapter.register_command_handler("test.confirm", test_handler)

        # Create confirmation request
        request_id = self.adapter.request_confirmation(
            chat_id=123456,
            message="Test?",
            options=[{"text": "Yes", "callback_data": "yes"}],
            command="test.confirm",
            context={"key": "value"},
        )

        # Get the signed callback data
        confirmation = self.adapter._pending_confirmations[request_id]
        signed_callback = confirmation.options[0]["callback_data"]

        # Simulate callback
        callback_data = {
            "id": "callback123",
            "data": signed_callback,
            "message": {"chat": {"id": 123456}},
            "from": {"id": 789},
        }

        self.adapter._handle_callback_query(callback_data, "trace-456")

        # Handler should have been called
        assert len(handler_called) == 1
        assert handler_called[0]["choice"] == "yes"
        assert handler_called[0]["key"] == "value"
        assert handler_called[0]["chat_id"] == 123456

        # Confirmation should be removed
        assert request_id not in self.adapter._pending_confirmations


class TestBriefingScheduler:
    """Test BriefingScheduler."""

    def test_daily_briefing_without_host_api(self) -> None:
        """Test daily briefing generation without host API."""
        scheduler = BriefingScheduler()
        content = scheduler.generate_daily_briefing()

        assert "Good Morning" in content
        assert "Vault integration not configured" in content

    def test_weekly_briefing_without_host_api(self) -> None:
        """Test weekly briefing generation without host API."""
        scheduler = BriefingScheduler()
        content = scheduler.generate_weekly_briefing()

        assert "Weekly Summary" in content
        assert "Vault integration not configured" in content

    def test_briefing_with_mock_host_api(self) -> None:
        """Test briefing with mock host API."""
        # Create mock host API
        mock_host = MagicMock()
        mock_task = MagicMock()
        mock_task.get_title.return_value = "Test Task"
        mock_task.metadata = {"due": "2025-10-07T12:00:00Z", "status": "todo"}
        mock_host.list_entities.return_value = iter([mock_task])

        scheduler = BriefingScheduler(host_api=mock_host)
        content = scheduler.generate_daily_briefing()

        assert "Good Morning" in content
        # Should not contain "not configured" since we have host API
        assert "Vault integration not configured" not in content


class TestTelegramAdapterFactory:
    """Test factory function."""

    def test_create_adapter(self) -> None:
        """Test adapter factory."""
        adapter = create_telegram_adapter(
            "test_token",
            allowed_chat_ids=[123],
        )

        assert adapter is not None
        assert adapter.config.bot_token == "test_token"
        assert adapter.config.allowed_chat_ids == [123]

    def test_create_adapter_with_scheduler(self) -> None:
        """Test adapter with scheduler."""
        scheduler = create_scheduler()
        adapter = create_telegram_adapter(
            "test_token",
            scheduler=scheduler,
            allowed_chat_ids=[123],
        )

        assert adapter.scheduler == scheduler

    def test_create_adapter_with_log_path(self) -> None:
        """Test adapter with log path."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "telegram.jsonl"

            adapter = create_telegram_adapter(
                "test_token",
                log_path=log_path,
            )

            assert adapter.config.log_path == log_path


class TestTelegramAdapterLogging:
    """Test structured logging."""

    def test_log_event_to_file(self) -> None:
        """Test logging to file."""
        import json
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "test.jsonl"

            config = TelegramAdapterConfig(
                bot_token="test_token",
                log_path=log_path,
            )
            adapter = TelegramAdapter(config)

            adapter._log_event("test_event", {"key": "value"})

            # Read log file
            assert log_path.exists()
            with open(log_path) as f:
                lines = f.readlines()

            assert len(lines) == 1
            log_entry = json.loads(lines[0])

            assert log_entry["event_type"] == "test_event"
            assert log_entry["component"] == "adapter"
            assert log_entry["adapter"] == "telegram"
            assert log_entry["key"] == "value"
            assert "timestamp" in log_entry
