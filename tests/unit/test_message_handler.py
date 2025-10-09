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
        # New human-friendly format should contain task title
        assert "Test Task" in args[2]  # response contains task title

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
        # New format shows tool names and summaries instead of "Шаг X"
        assert "task_create" in response or "Task 1" in response or "Task 2" in response
        assert response.count("✅") == 2  # Two successful steps
        assert "❌" in response  # One failed step
        assert "Failed to create task 3" in response  # Error message present

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

    def test_handle_message_with_llm_timeout(self) -> None:
        """Test handling when LLM request times out.
        
        Simulates real-world scenario where LLM API takes too long to respond.
        User should receive clear error message about timeout.
        """
        # Setup
        executor = Mock()
        callback = Mock()
        handler = MessageHandler(executor, callback)

        # Simulate timeout exception from LLM
        executor.chat_and_execute.side_effect = TimeoutError("The read operation timed out")

        # Create realistic event
        event = Event(
            name="message.received",
            payload={
                "message": "Создай задачу: Проверить почту завтра в 10:00",
                "source": "telegram",
                "chat_id": 916542313,
                "trace_id": "timeout-test-trace",
            },
        )

        # Execute
        handler.handle_message_received(event)

        # Verify error callback was called
        callback.assert_called_once()
        args = callback.call_args[0]
        
        # Check response format
        assert args[0] == "telegram"  # source
        assert args[1] == "916542313"  # chat_id
        assert "❌" in args[2]  # error marker
        assert "timed out" in args[2].lower()  # timeout mentioned

    def test_handle_message_with_long_response_time(self) -> None:
        """Test handling when LLM takes a very long time but eventually responds.
        
        This tests the scenario where the LLM doesn't timeout but takes 20-30 seconds,
        which should still succeed.
        """
        import time
        
        # Setup
        executor = Mock()
        callback = Mock()
        handler = MessageHandler(executor, callback)

        # Simulate slow but successful LLM response
        def slow_execution(*args, **kwargs):
            time.sleep(0.1)  # Simulate delay (reduced for test speed)
            return MockExecutionResult(
                status="ok",
                results=[
                    {
                        "status": "ok",
                        "tool": "task_create",
                        "data": {"id": "task-slow-123", "title": "Проверить почту"},
                    }
                ],
            )

        executor.chat_and_execute.side_effect = slow_execution

        # Create event
        event = Event(
            name="message.received",
            payload={
                "message": "Создай задачу: Проверить почту",
                "source": "telegram",
                "chat_id": 123456,
            },
        )

        # Execute (should not timeout in test)
        handler.handle_message_received(event)

        # Verify success response sent
        callback.assert_called_once()
        args = callback.call_args[0]
        assert "✅" in args[2]  # success marker
        assert "Проверить почту" in args[2]

    def test_handle_message_with_connection_error(self) -> None:
        """Test handling when LLM API connection fails completely.
        
        Simulates network issues or API being down.
        """
        # Setup
        executor = Mock()
        callback = Mock()
        handler = MessageHandler(executor, callback)

        # Simulate connection error
        executor.chat_and_execute.side_effect = ConnectionError("Failed to connect to LLM API")

        # Create event
        event = Event(
            name="message.received",
            payload={
                "message": "Завтра мне нужно помыть полы. Поставь задачу",
                "source": "telegram",
                "chat_id": 916542313,
            },
        )

        # Execute
        handler.handle_message_received(event)

        # Verify error callback
        callback.assert_called_once()
        args = callback.call_args[0]
        assert "❌" in args[2]
        assert "Failed to connect" in args[2] or "LLM API" in args[2]

    def test_handle_complex_message_with_date(self) -> None:
        """Test handling message with date/time information.
        
        Real user query: 'Завтра мне нужно помыть полы. Поставь задачу'
        Should successfully create task with due date.
        """
        # Setup
        executor = Mock()
        callback = Mock()
        handler = MessageHandler(executor, callback)

        # Mock successful execution with due date
        mock_result = MockExecutionResult(
            status="ok",
            results=[
                {
                    "status": "ok",
                    "tool": "task_create",
                    "data": {
                        "id": "task-20251010-0001",
                        "title": "Помыть полы",
                        "due_ts": "2025-10-10T00:00:00Z",
                    },
                }
            ],
        )
        executor.chat_and_execute.return_value = mock_result

        # Create event
        event = Event(
            name="message.received",
            payload={
                "message": "Завтра мне нужно помыть полы. Поставь задачу",
                "source": "telegram",
                "chat_id": 916542313,
                "trace_id": "date-task-trace",
            },
        )

        # Execute
        handler.handle_message_received(event)

        # Verify success
        callback.assert_called_once()
        args = callback.call_args[0]
        assert "✅" in args[2]
        assert "Помыть полы" in args[2]
