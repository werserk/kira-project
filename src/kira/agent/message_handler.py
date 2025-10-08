"""Message handler for connecting adapters to Agent via Event Bus.

Subscribes to message.received events and routes them to AgentExecutor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from ..core.events import Event

if TYPE_CHECKING:
    from .executor import AgentExecutor

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
        executor: AgentExecutor,
        response_callback: Callable[[str, str, str], None] | None = None,
    ) -> None:
        """Initialize message handler.

        Parameters
        ----------
        executor
            Agent executor to process messages
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
            return

        message_text = payload.get("message", "")
        source = payload.get("source", "unknown")
        chat_id = str(payload.get("chat_id", ""))
        trace_id = payload.get("trace_id", f"{source}-{chat_id}")

        if not message_text:
            return

        try:
            # Execute request through agent
            result = self.executor.chat_and_execute(message_text, trace_id=trace_id)

            # Format response
            response_text = self._format_response(result)

            # Send response back via callback
            if self.response_callback:
                self.response_callback(source, chat_id, response_text)

        except Exception as e:
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
        if not hasattr(result, "status"):
            return str(result)

        if result.status == "ok":
            if result.results:
                response_parts = []
                for i, step_result in enumerate(result.results, 1):
                    if step_result.get("status") == "ok":
                        data = step_result.get("data", {})
                        tool_name = step_result.get("tool", "action")
                        response_parts.append(f"✅ Шаг {i}: {tool_name}")

                        # Show summary of data
                        if data:
                            if isinstance(data, dict):
                                summary = self._summarize_dict(data)
                                response_parts.append(f"   {summary}")
                            else:
                                summary = str(data)[:200]
                                response_parts.append(f"   {summary}")
                    else:
                        error = step_result.get("error", "Неизвестная ошибка")
                        response_parts.append(f"❌ Шаг {i}: {error}")

                return "\n".join(response_parts)
            else:
                return "✅ Запрос выполнен успешно"

        elif result.status == "error":
            error = getattr(result, "error", "Неизвестная ошибка")
            return f"❌ Ошибка: {error}"

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
    executor: AgentExecutor,
    response_callback: Callable[[str, str, str], None] | None = None,
) -> MessageHandler:
    """Factory function to create message handler.

    Parameters
    ----------
    executor
        Agent executor
    response_callback
        Optional callback for sending responses

    Returns
    -------
    MessageHandler
        Configured message handler
    """
    return MessageHandler(executor, response_callback)
