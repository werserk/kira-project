"""Message handler for connecting adapters to Agent via Event Bus.

Subscribes to message.received events and routes them to AgentExecutor.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from ..core.events import Event

logger = logging.getLogger(__name__)

__all__ = ["MessageHandler", "create_message_handler"]


class MessageHandler:
    """Connects incoming messages from adapters to Agent execution.

    Architecture:
        Telegram/Other Adapter → Event Bus → MessageHandler → AgentExecutor
                                              ↓
                                         Send response back via callback
    """

    def __init__(
        self,
        executor: Any,  # AgentExecutor or UnifiedExecutor
        response_callback: Callable[[str, str, str], None] | None = None,
    ) -> None:
        """Initialize message handler.

        Parameters
        ----------
        executor
            Agent executor to process messages (AgentExecutor or UnifiedExecutor)
        response_callback
            Callback to send responses back: callback(source, chat_id, response_text)
            Example: lambda source, chat_id, text: telegram_adapter.send_message(chat_id, text)
        """
        self.executor = executor
        self.response_callback = response_callback

    def handle_message_received(self, event: Event) -> None:
        """Handle message.received event from any adapter.

        Parameters
        ----------
        event
            Event with payload containing: message, source, chat_id, trace_id
        """
        payload = event.payload
        if not payload:
            logger.warning("Received event with empty payload")
            return

        message_text = payload.get("message", "")
        source = payload.get("source", "unknown")
        chat_id = str(payload.get("chat_id", ""))
        trace_id = payload.get("trace_id", f"{source}-{chat_id}")

        # Session ID для постоянной памяти (одинаковый для всех сообщений из чата)
        session_id = f"{source}:{chat_id}"

        if not message_text:
            logger.warning(f"Received empty message from {source}:{chat_id}")
            return

        logger.info(f"Processing message from {source}:{chat_id}, trace_id={trace_id}, session_id={session_id}")
        logger.debug(f"Message content: {message_text[:100]}...")

        try:
            # Execute request through agent
            logger.info(f"Executing agent request, trace_id={trace_id}")
            result = self.executor.chat_and_execute(message_text, trace_id=trace_id, session_id=session_id)
            logger.info(f"Agent execution completed, status={getattr(result, 'status', 'unknown')}")

            # Format response
            response_text = self._format_response(result)
            logger.debug(f"Formatted response: {response_text[:200]}...")

            # Send response back via callback
            if self.response_callback:
                logger.info(f"Sending response to {source}:{chat_id}")
                self.response_callback(source, chat_id, response_text)
            else:
                logger.warning("No response callback configured, response not sent")

        except Exception as e:
            logger.exception(f"Error processing message from {source}:{chat_id}: {e}")
            error_response = f"❌ Ошибка обработки запроса: {str(e)}"
            if self.response_callback:
                self.response_callback(source, chat_id, error_response)

    def _format_response(self, result: Any) -> str:
        """Format execution result for user.

        Parameters
        ----------
        result
            Execution result from AgentExecutor

        Returns
        -------
        str
            Formatted response text
        """
        logger.debug(f"Formatting response: result type={type(result)}, has status={hasattr(result, 'status')}")

        # Both executors now return .response field with natural language response
        if hasattr(result, "response"):
            # Use NL response if it's not empty
            if result.response and result.response.strip():
                logger.info(f"Using natural language response: {result.response[:100]}...")
                return result.response
            else:
                logger.warning("Empty response returned, falling back to formatter")
                # Continue to fallback formatter below

        if not hasattr(result, "status"):
            logger.debug(f"Result without status, converting to string: {result}")
            return str(result)

        logger.debug(f"Result status: {result.status}")

        if result.status == "ok":
            if hasattr(result, "results") and result.results:
                logger.debug(f"Formatting {len(result.results)} step results")

                # Check if all steps were successful
                all_success = all(r.get("status") == "ok" for r in result.results)

                if all_success and len(result.results) == 1:
                    # Single successful step - give a clean, human-friendly message
                    step_result = result.results[0]
                    data = step_result.get("data", {})
                    tool_name = step_result.get("tool", "action")

                    # Create human-friendly response based on tool
                    if "task" in tool_name.lower() and data:
                        if "dry_run" in str(data).lower():
                            response = f"✅ Понял! Готов создать задачу (режим dry-run активен)"
                        elif data.get("title"):
                            task_id = data.get("id", "")
                            response = f"✅ Создана задача: {data.get('title')}\n📋 ID: {task_id}"
                        else:
                            response = self._humanize_result(tool_name, data)
                    else:
                        response = self._humanize_result(tool_name, data)

                    logger.debug(f"Humanized single-step response: {response}")
                    return response

                # Multiple steps or mixed results - show detailed info
                response_parts = []
                for i, step_result in enumerate(result.results, 1):
                    if step_result.get("status") == "ok":
                        data = step_result.get("data", {})
                        tool_name = step_result.get("tool", "action")

                        if data and isinstance(data, dict):
                            summary = self._summarize_dict(data)
                            if "dry" not in summary.lower():
                                response_parts.append(f"✅ {tool_name}: {summary}")
                        elif i == 1:  # Only show first action if no data
                            response_parts.append(f"✅ Выполнено")
                    else:
                        error = step_result.get("error", "Неизвестная ошибка")
                        response_parts.append(f"❌ Ошибка: {error}")

                if response_parts:
                    return "\n".join(response_parts)
                return "✅ Готово"

            logger.debug("No detailed results, returning success message")
            return "✅ Запрос выполнен успешно"

        if result.status == "error":
            error = getattr(result, "error", None)
            if error is None or error == "None":
                logger.warning(f"Result has error status but error field is None/missing. Result: {result}")
                # Try to get more info from result
                if hasattr(result, "results") and result.results:
                    errors = [r.get("error") for r in result.results if r.get("error")]
                    if errors:
                        error = "; ".join(str(e) for e in errors)
                    else:
                        error = "Выполнение завершилось с ошибкой (детали не предоставлены)"
                else:
                    error = "Выполнение завершилось с ошибкой (детали не предоставлены)"

            logger.debug(f"Returning error message: {error}")
            return f"❌ Ошибка: {error}"

        logger.debug(f"Unknown status: {result.status}, returning default message")
        return "✅ Готово"

    def _humanize_result(self, tool_name: str, data: dict[str, Any]) -> str:
        """Create human-friendly response based on tool and data.

        Parameters
        ----------
        tool_name
            Name of the tool that was executed
        data
            Result data from tool

        Returns
        -------
        str
            Human-friendly message
        """
        if not data:
            return "✅ Готово"

        # Task-related responses
        if "task" in tool_name.lower():
            if data.get("title"):
                return f"✅ Создана задача: {data['title']}"
            if data.get("count") is not None:
                return f"✅ Найдено задач: {data['count']}"

        # Generic success with data summary
        if "id" in data and "title" in data:
            return f"✅ Готово: {data['title']}"
        elif "message" in data:
            return f"✅ {data['message']}"
        elif "count" in data:
            return f"✅ Найдено записей: {data['count']}"

        return "✅ Готово"

    def _summarize_dict(self, data: dict[str, Any]) -> str:
        """Create human-readable summary of dict data.

        Parameters
        ----------
        data
            Data dictionary

        Returns
        -------
        str
            Summary string
        """
        if "id" in data and "title" in data:
            # Task or entity summary
            return f"ID: {data['id']}, Заголовок: {data['title']}"
        elif "count" in data:
            return f"Найдено: {data['count']}"
        elif "message" in data:
            return str(data["message"])
        else:
            # Fallback: show first few keys
            keys = list(data.keys())[:3]
            return f"Данные: {', '.join(keys)}"


def create_message_handler(
    executor: Any,  # AgentExecutor or UnifiedExecutor
    response_callback: Callable[[str, str, str], None] | None = None,
) -> MessageHandler:
    """Factory function to create message handler.

    Parameters
    ----------
    executor
        Agent executor (AgentExecutor or UnifiedExecutor)
    response_callback
        Optional callback for sending responses

    Returns
    -------
    MessageHandler
        Configured message handler
    """
    return MessageHandler(executor, response_callback)
