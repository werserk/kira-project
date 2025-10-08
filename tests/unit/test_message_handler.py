"""Tests for message handler (Event Bus → Agent integration)."""

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest

from kira.agent.message_handler import MessageHandler, create_message_handler
from kira.core.events import Event


@dataclass
class MockExecutionResult:
    """Mock execution result."""

    status: str
    results: list[dict[str, Any]] | None = None
    error: str | None = None


class TestMessageHandler:
    """Test MessageHandler integration."""

    def test_create_message_handler(self) -> None:
        """Test factory function."""
        executor = Mock()
        callback = Mock()

        handler = create_message_handler(executor, callback)

        assert isinstance(handler, MessageHandler)
        assert handler.executor == executor
        assert handler.response_callback == callback

    def test_handle_message_received_success(self) -> None:
        """Test successful message handling."""
        # Setup
        executor = Mock()
        callback = Mock()
        handler = MessageHandler(executor, callback)

        # Mock successful execution
        mock_result = MockExecutionResult(
            status="ok",
            results=[
                {
                    "status": "ok",
                    "tool": "task_create",
                    "data": {"id": "task-123", "title": "Test Task"},
                }
            ],
        )
        executor.chat_and_execute.return_value = mock_result

        # Create event
        event = Event(
            name="message.received",
            payload={
                "message": "Create a task for testing",
                "source": "telegram",
                "chat_id": 123456,
                "trace_id": "test-trace",
            },
        )

        # Execute
        handler.handle_message_received(event)

        # Verify executor called
        executor.chat_and_execute.assert_called_once_with(
            "Create a task for testing", trace_id="test-trace"
        )

        # Verify callback called with formatted response
        callback.assert_called_once()
        args = callback.call_args[0]
        assert args[0] == "telegram"  # source
        assert args[1] == "123456"  # chat_id
        assert "✅" in args[2]  # response contains success marker
        assert "task_create" in args[2]  # response contains tool name

    def test_handle_message_received_error(self) -> None:
        """Test message handling with execution error."""
        # Setup
        executor = Mock()
        callback = Mock()
        handler = MessageHandler(executor, callback)

        # Mock error execution
        mock_result = MockExecutionResult(status="error", error="LLM API unavailable")
        executor.chat_and_execute.return_value = mock_result

        # Create event
        event = Event(
            name="message.received",
            payload={
                "message": "Do something",
                "source": "telegram",
                "chat_id": 123456,
            },
        )

        # Execute
        handler.handle_message_received(event)

        # Verify error response sent
        callback.assert_called_once()
        args = callback.call_args[0]
        assert "❌" in args[2]
        assert "LLM API unavailable" in args[2]

    def test_handle_message_received_exception(self) -> None:
        """Test message handling with exception."""
        # Setup
        executor = Mock()
        callback = Mock()
        handler = MessageHandler(executor, callback)

        # Mock exception
        executor.chat_and_execute.side_effect = RuntimeError("Network error")

        # Create event
        event = Event(
            name="message.received",
            payload={
                "message": "Test",
                "source": "telegram",
                "chat_id": 123456,
            },
        )

        # Execute (should not raise)
        handler.handle_message_received(event)

        # Verify error callback
        callback.assert_called_once()
        args = callback.call_args[0]
        assert "❌" in args[2]
        assert "Network error" in args[2]

    def test_handle_message_received_empty_message(self) -> None:
        """Test handling event with empty message."""
        # Setup
        executor = Mock()
        callback = Mock()
        handler = MessageHandler(executor, callback)

        # Create event with empty message
        event = Event(
            name="message.received",
            payload={
                "message": "",
                "source": "telegram",
                "chat_id": 123456,
            },
        )

        # Execute
        handler.handle_message_received(event)

        # Verify nothing called (early return)
        executor.chat_and_execute.assert_not_called()
        callback.assert_not_called()

    def test_handle_message_received_no_payload(self) -> None:
        """Test handling event with no payload."""
        # Setup
        executor = Mock()
        callback = Mock()
        handler = MessageHandler(executor, callback)

        # Create event with no payload
        event = Event(name="message.received", payload=None)

        # Execute
        handler.handle_message_received(event)

        # Verify nothing called (early return)
        executor.chat_and_execute.assert_not_called()
        callback.assert_not_called()

    def test_handle_message_received_no_callback(self) -> None:
        """Test handling without response callback."""
        # Setup
        executor = Mock()
        handler = MessageHandler(executor, response_callback=None)

        # Mock successful execution
        mock_result = MockExecutionResult(status="ok", results=[])
        executor.chat_and_execute.return_value = mock_result

        # Create event
        event = Event(
            name="message.received",
            payload={
                "message": "Test",
                "source": "telegram",
                "chat_id": 123456,
            },
        )

        # Execute (should not raise even without callback)
        handler.handle_message_received(event)

        # Verify executor still called
        executor.chat_and_execute.assert_called_once()

    def test_format_response_with_multiple_steps(self) -> None:
        """Test response formatting with multiple execution steps."""
        # Setup
        executor = Mock()
        callback = Mock()
        handler = MessageHandler(executor, callback)

        # Mock multi-step execution
        mock_result = MockExecutionResult(
            status="ok",
            results=[
                {
                    "status": "ok",
                    "tool": "task_create",
                    "data": {"id": "task-1", "title": "Task 1"},
                },
                {
                    "status": "ok",
                    "tool": "task_create",
                    "data": {"id": "task-2", "title": "Task 2"},
                },
                {"status": "error", "error": "Failed to create task 3"},
            ],
        )
        executor.chat_and_execute.return_value = mock_result

        # Create event
        event = Event(
            name="message.received",
            payload={
                "message": "Create 3 tasks",
                "source": "telegram",
                "chat_id": 123456,
            },
        )

        # Execute
        handler.handle_message_received(event)

        # Verify response includes all steps
        callback.assert_called_once()
        response = callback.call_args[0][2]
        assert "Шаг 1" in response
        assert "Шаг 2" in response
        assert "Шаг 3" in response
        assert response.count("✅") == 2  # Two successful steps
        assert "❌" in response  # One failed step

    def test_summarize_dict_with_task_data(self) -> None:
        """Test dict summarization for task data."""
        executor = Mock()
        handler = MessageHandler(executor, None)

        # Test with task-like data
        summary = handler._summarize_dict({"id": "task-1", "title": "Test Task"})
        assert "task-1" in summary
        assert "Test Task" in summary

    def test_summarize_dict_with_count(self) -> None:
        """Test dict summarization with count."""
        executor = Mock()
        handler = MessageHandler(executor, None)

        summary = handler._summarize_dict({"count": 5, "items": []})
        assert "5" in summary

    def test_summarize_dict_with_message(self) -> None:
        """Test dict summarization with message field."""
        executor = Mock()
        handler = MessageHandler(executor, None)

        summary = handler._summarize_dict({"message": "Operation completed"})
        assert "Operation completed" in summary

    def test_summarize_dict_fallback(self) -> None:
        """Test dict summarization fallback for unknown structure."""
        executor = Mock()
        handler = MessageHandler(executor, None)

        summary = handler._summarize_dict({"foo": "bar", "baz": 123, "qux": []})
        assert "foo" in summary or "baz" in summary or "qux" in summary

    def test_trace_id_generation(self) -> None:
        """Test trace_id generation from source and chat_id."""
        executor = Mock()
        callback = Mock()
        handler = MessageHandler(executor, callback)

        mock_result = MockExecutionResult(status="ok", results=[])
        executor.chat_and_execute.return_value = mock_result

        # Event without trace_id
        event = Event(
            name="message.received",
            payload={
                "message": "Test",
                "source": "telegram",
                "chat_id": 999,
            },
        )

        handler.handle_message_received(event)

        # Verify trace_id was generated from source and chat_id
        call_args = executor.chat_and_execute.call_args
        assert call_args[1]["trace_id"] == "telegram-999"
