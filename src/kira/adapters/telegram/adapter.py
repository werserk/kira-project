"""Telegram adapter for Kira (ADR-011).

This adapter provides the primary UX for capturing items, confirming extractions,
and receiving briefings through Telegram Bot API.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...core.events import EventBus

__all__ = [
    "TelegramAdapter",
    "TelegramAdapterConfig",
    "TelegramMessage",
    "TelegramUpdate",
    "create_telegram_adapter",
]


@dataclass
class TelegramUpdate:
    """Telegram update container."""

    update_id: int
    message: TelegramMessage | None = None
    callback_query: dict[str, Any] | None = None


@dataclass
class TelegramMessage:
    """Telegram message container."""

    message_id: int
    chat_id: int
    user_id: int
    text: str | None = None
    photo: list[dict[str, Any]] = field(default_factory=list)
    document: dict[str, Any] | None = None
    timestamp: int = 0

    def get_idempotency_key(self) -> str:
        """Generate idempotency key for deduplication.

        Returns
        -------
        str
            Unique key based on chat_id and message_id
        """
        return f"{self.chat_id}:{self.message_id}"


@dataclass
class TelegramAdapterConfig:
    """Configuration for Telegram adapter."""

    bot_token: str
    allowed_chat_ids: list[int] = field(default_factory=list)
    allowed_user_ids: list[int] = field(default_factory=list)
    polling_timeout: int = 30
    polling_interval: float = 1.0
    max_retries: int = 3
    retry_delay: float = 2.0
    log_path: Path | None = None
    temp_dir: Path | None = None


class TelegramAdapter:
    """Telegram Bot API adapter for Kira.

    Responsibilities (ADR-011):
    - Poll for updates using long polling
    - Normalize messages and files
    - Publish message.received and file.dropped events
    - Handle inline button callbacks for confirmations
    - Send daily briefings to configured chats
    - Maintain idempotency (deduplicate messages)
    - Emit structured JSONL logs with correlation IDs

    Example:
        >>> from kira.core.events import create_event_bus
        >>> from kira.adapters.telegram import create_telegram_adapter
        >>>
        >>> event_bus = create_event_bus()
        >>> adapter = create_telegram_adapter(
        ...     bot_token="YOUR_BOT_TOKEN",
        ...     event_bus=event_bus,
        ...     allowed_chat_ids=[123456789]
        ... )
        >>> adapter.start_polling()  # Runs until stopped
    """

    def __init__(
        self,
        config: TelegramAdapterConfig,
        *,
        event_bus: EventBus | None = None,
        logger: Any = None,
    ) -> None:
        """Initialize Telegram adapter.

        Parameters
        ----------
        config
            Adapter configuration
        event_bus
            Event bus for publishing events (ADR-005)
        logger
            Optional structured logger
        """
        self.config = config
        self.event_bus = event_bus
        self.logger = logger
        self._running = False
        self._last_update_id: int = 0
        self._processed_updates: set[str] = set()  # Idempotency tracking
        self._api_base_url = f"https://api.telegram.org/bot{config.bot_token}"

        # Setup temp directory for file downloads
        if config.temp_dir:
            config.temp_dir.mkdir(parents=True, exist_ok=True)

    def start_polling(self) -> None:
        """Start long polling for updates.

        Blocks until stop_polling() is called or an error occurs.
        """
        self._running = True
        self._log_event("polling_started", {})

        while self._running:
            try:
                updates = self._get_updates()

                for update in updates:
                    self._process_update(update)

                # Small delay between polls
                if not updates:
                    time.sleep(self.config.polling_interval)

            except KeyboardInterrupt:
                self._log_event("polling_interrupted", {})
                break
            except Exception as exc:
                self._log_event(
                    "polling_error",
                    {
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                    },
                )
                time.sleep(self.config.retry_delay)

        self._log_event("polling_stopped", {})

    def stop_polling(self) -> None:
        """Stop polling loop."""
        self._running = False

    def send_message(
        self,
        chat_id: int,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
        parse_mode: str = "Markdown",
    ) -> dict[str, Any] | None:
        """Send message to chat.

        Parameters
        ----------
        chat_id
            Target chat ID
        text
            Message text
        reply_markup
            Optional inline keyboard markup
        parse_mode
            Text formatting mode

        Returns
        -------
        dict or None
            API response or None on failure
        """
        params = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }

        if reply_markup:
            params["reply_markup"] = json.dumps(reply_markup)

        try:
            response = self._api_request("sendMessage", params)
            return response
        except Exception as exc:
            self._log_event(
                "send_message_failed",
                {
                    "chat_id": chat_id,
                    "error": str(exc),
                },
            )
            return None

    def send_daily_briefing(self, chat_id: int, briefing_content: str) -> bool:
        """Send daily briefing to chat.

        Parameters
        ----------
        chat_id
            Target chat ID
        briefing_content
            Briefing content (Markdown formatted)

        Returns
        -------
        bool
            True if sent successfully
        """
        trace_id = str(uuid.uuid4())

        self._log_event(
            "briefing_sending",
            {
                "trace_id": trace_id,
                "chat_id": chat_id,
            },
        )

        response = self.send_message(chat_id, briefing_content)

        success = response is not None

        self._log_event(
            "briefing_sent" if success else "briefing_failed",
            {
                "trace_id": trace_id,
                "chat_id": chat_id,
                "outcome": "success" if success else "failure",
            },
        )

        return success

    def _get_updates(self) -> list[TelegramUpdate]:
        """Get updates from Telegram API using long polling.

        Returns
        -------
        list[TelegramUpdate]
            List of new updates
        """
        params = {
            "offset": self._last_update_id + 1,
            "timeout": self.config.polling_timeout,
            "allowed_updates": ["message", "callback_query"],
        }

        try:
            response = self._api_request("getUpdates", params)

            if not response or "result" not in response:
                return []

            updates = []
            for update_data in response["result"]:
                update = self._parse_update(update_data)
                if update:
                    updates.append(update)
                    self._last_update_id = max(self._last_update_id, update.update_id)

            return updates

        except Exception as exc:
            self._log_event(
                "get_updates_failed",
                {
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
            )
            return []

    def _parse_update(self, data: dict[str, Any]) -> TelegramUpdate | None:
        """Parse update data from API.

        Parameters
        ----------
        data
            Raw update data

        Returns
        -------
        TelegramUpdate or None
            Parsed update or None if invalid
        """
        update_id = data.get("update_id")
        if not update_id:
            return None

        message_data = data.get("message")
        message = None

        if message_data:
            message = TelegramMessage(
                message_id=message_data.get("message_id", 0),
                chat_id=message_data.get("chat", {}).get("id", 0),
                user_id=message_data.get("from", {}).get("id", 0),
                text=message_data.get("text"),
                photo=message_data.get("photo", []),
                document=message_data.get("document"),
                timestamp=message_data.get("date", 0),
            )

        callback_query = data.get("callback_query")

        return TelegramUpdate(
            update_id=update_id,
            message=message,
            callback_query=callback_query,
        )

    def _process_update(self, update: TelegramUpdate) -> None:
        """Process single update.

        Parameters
        ----------
        update
            Update to process
        """
        trace_id = str(uuid.uuid4())

        # Handle callback query (inline button clicks)
        if update.callback_query:
            self._handle_callback_query(update.callback_query, trace_id)
            return

        # Handle message
        if update.message:
            self._handle_message(update.message, trace_id)

    def _handle_message(self, message: TelegramMessage, trace_id: str) -> None:
        """Handle incoming message.

        Parameters
        ----------
        message
            Message to handle
        trace_id
            Trace ID for correlation
        """
        # Check idempotency - avoid processing duplicates
        idempotency_key = message.get_idempotency_key()
        if idempotency_key in self._processed_updates:
            self._log_event(
                "message_duplicate",
                {
                    "trace_id": trace_id,
                    "chat_id": message.chat_id,
                    "message_id": message.message_id,
                },
            )
            return

        # Check whitelist
        if not self._is_allowed(message.chat_id, message.user_id):
            self._log_event(
                "message_rejected",
                {
                    "trace_id": trace_id,
                    "chat_id": message.chat_id,
                    "user_id": message.user_id,
                    "reason": "not_whitelisted",
                },
            )
            return

        # Mark as processed
        self._processed_updates.add(idempotency_key)

        # Cleanup old entries (keep last 10000)
        if len(self._processed_updates) > 10000:
            # Remove oldest half
            to_remove = list(self._processed_updates)[:5000]
            for key in to_remove:
                self._processed_updates.discard(key)

        # Process text message
        if message.text:
            self._publish_message_received(message, trace_id)

        # Process file/photo
        if message.document or message.photo:
            self._publish_file_dropped(message, trace_id)

    def _is_allowed(self, chat_id: int, user_id: int) -> bool:
        """Check if chat/user is whitelisted.

        Parameters
        ----------
        chat_id
            Chat ID
        user_id
            User ID

        Returns
        -------
        bool
            True if allowed
        """
        # If no whitelist configured, allow all
        if not self.config.allowed_chat_ids and not self.config.allowed_user_ids:
            return True

        # Check whitelists
        if self.config.allowed_chat_ids and chat_id in self.config.allowed_chat_ids:
            return True

        if self.config.allowed_user_ids and user_id in self.config.allowed_user_ids:
            return True

        return False

    def _publish_message_received(self, message: TelegramMessage, trace_id: str) -> None:
        """Publish message.received event.

        Parameters
        ----------
        message
            Message data
        trace_id
            Trace ID
        """
        if not self.event_bus:
            return

        payload = {
            "message": message.text,
            "source": "telegram",
            "chat_id": message.chat_id,
            "user_id": message.user_id,
            "message_id": message.message_id,
            "timestamp": datetime.fromtimestamp(message.timestamp, tz=timezone.utc).isoformat(),
            "trace_id": trace_id,
        }

        self.event_bus.publish("message.received", payload)

        self._log_event(
            "message_published",
            {
                "trace_id": trace_id,
                "event": "message.received",
                "chat_id": message.chat_id,
                "message_id": message.message_id,
            },
        )

    def _publish_file_dropped(self, message: TelegramMessage, trace_id: str) -> None:
        """Publish file.dropped event.

        Parameters
        ----------
        message
            Message with file/photo
        trace_id
            Trace ID
        """
        if not self.event_bus:
            return

        # Determine file info
        file_id = None
        mime_type = None
        size = 0

        if message.document:
            file_id = message.document.get("file_id")
            mime_type = message.document.get("mime_type")
            size = message.document.get("file_size", 0)
        elif message.photo:
            # Use largest photo
            largest = max(message.photo, key=lambda p: p.get("file_size", 0))
            file_id = largest.get("file_id")
            mime_type = "image/jpeg"
            size = largest.get("file_size", 0)

        if not file_id:
            return

        payload = {
            "file_id": file_id,
            "mime_type": mime_type,
            "size": size,
            "source": "telegram",
            "chat_id": message.chat_id,
            "user_id": message.user_id,
            "message_id": message.message_id,
            "timestamp": datetime.fromtimestamp(message.timestamp, tz=timezone.utc).isoformat(),
            "trace_id": trace_id,
        }

        self.event_bus.publish("file.dropped", payload)

        self._log_event(
            "file_published",
            {
                "trace_id": trace_id,
                "event": "file.dropped",
                "chat_id": message.chat_id,
                "file_id": file_id,
                "mime_type": mime_type,
            },
        )

    def _handle_callback_query(self, callback_data: dict[str, Any], trace_id: str) -> None:
        """Handle inline button callback.

        Parameters
        ----------
        callback_data
            Callback query data
        trace_id
            Trace ID
        """
        callback_id = callback_data.get("id")
        data = callback_data.get("data", "")
        chat_id = callback_data.get("message", {}).get("chat", {}).get("id")

        self._log_event(
            "callback_received",
            {
                "trace_id": trace_id,
                "callback_id": callback_id,
                "data": data,
                "chat_id": chat_id,
            },
        )

        # Answer callback to remove "loading" state
        try:
            self._api_request("answerCallbackQuery", {"callback_query_id": callback_id})
        except Exception:
            pass

        # Publish callback event for plugins to handle
        if self.event_bus:
            payload = {
                "callback_id": callback_id,
                "data": data,
                "chat_id": chat_id,
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self.event_bus.publish("telegram.callback", payload)

    def _api_request(self, method: str, params: dict[str, Any]) -> dict[str, Any] | None:
        """Make Telegram API request.

        Parameters
        ----------
        method
            API method name
        params
            Request parameters

        Returns
        -------
        dict or None
            API response or None on failure
        """
        # Placeholder for actual HTTP implementation
        # In real implementation, use requests library:
        # import requests
        # response = requests.post(f"{self._api_base_url}/{method}", json=params)
        # return response.json()

        # For now, return empty response (will be implemented with requests library)
        return {"ok": True, "result": []}

    def _log_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit structured JSONL log entry.

        Parameters
        ----------
        event_type
            Type of log event
        data
            Event data (must be JSON-serializable)
        """
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": "adapter",
            "adapter": "telegram",
            "event_type": event_type,
            **data,
        }

        # Log to file if configured
        if self.config.log_path:
            self.config.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

        # Also log via logger if available
        if self.logger:
            if data.get("outcome") == "failure" or "error" in event_type:
                self.logger.error(f"{event_type}: {json.dumps(data)}")
            else:
                self.logger.info(f"{event_type}: {json.dumps(data)}")


def create_telegram_adapter(
    bot_token: str,
    *,
    event_bus: EventBus | None = None,
    logger: Any = None,
    log_path: Path | str | None = None,
    **config_kwargs: Any,
) -> TelegramAdapter:
    """Factory function to create Telegram adapter.

    Parameters
    ----------
    bot_token
        Telegram Bot API token
    event_bus
        Event bus for publishing events
    logger
        Optional logger instance
    log_path
        Optional path for JSONL logs
    **config_kwargs
        Additional configuration options

    Returns
    -------
    TelegramAdapter
        Configured adapter instance

    Example:
        >>> adapter = create_telegram_adapter(
        ...     "YOUR_BOT_TOKEN",
        ...     event_bus=event_bus,
        ...     allowed_chat_ids=[123456789],
        ...     log_path=Path("logs/adapters/telegram.jsonl")
        ... )
    """
    if log_path:
        log_path = Path(log_path) if isinstance(log_path, str) else log_path
        config_kwargs["log_path"] = log_path

    config = TelegramAdapterConfig(bot_token=bot_token, **config_kwargs)

    return TelegramAdapter(config, event_bus=event_bus, logger=logger)

