"""Telegram adapter for Kira (ADR-011).

This adapter provides the primary UX for capturing items, confirming extractions,
and receiving briefings through Telegram Bot API.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from ...core.events import EventBus
    from ...core.scheduler import Scheduler

__all__ = [
    "BriefingScheduler",
    "ConfirmationRequest",
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
class ConfirmationRequest:
    """Request for user confirmation via inline buttons."""

    request_id: str
    chat_id: int
    message: str
    options: list[dict[str, str]]  # [{"text": "Yes", "callback_data": "confirm_yes"}, ...]
    command: str  # Plugin command to trigger on selection
    context: dict[str, Any] = field(default_factory=dict)
    expires_at: float = field(default_factory=lambda: time.time() + 3600)  # 1 hour TTL

    def is_expired(self) -> bool:
        """Check if confirmation request has expired."""
        return time.time() > self.expires_at

    def get_inline_keyboard(self) -> dict[str, Any]:
        """Generate inline keyboard markup for Telegram.

        Returns
        -------
        dict
            Telegram inline keyboard markup
        """
        return {
            "inline_keyboard": [[{"text": opt["text"], "callback_data": opt["callback_data"]} for opt in self.options]]
        }


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
    csrf_secret: str = field(default_factory=lambda: str(uuid.uuid4()))
    daily_briefing_time: str = "09:00"  # HH:MM format
    weekly_briefing_day: int = 1  # Monday = 0
    weekly_briefing_time: str = "09:00"


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
        scheduler: Scheduler | None = None,
        logger: Any = None,
    ) -> None:
        """Initialize Telegram adapter.

        Parameters
        ----------
        config
            Adapter configuration
        event_bus
            Event bus for publishing events (ADR-005)
        scheduler
            Optional scheduler for briefings (ADR-005)
        logger
            Optional structured logger
        """
        self.config = config
        self.event_bus = event_bus
        self.scheduler = scheduler
        self.logger = logger
        self._running = False
        self._last_update_id: int = 0
        self._processed_updates: set[str] = set()  # Idempotency tracking
        self._api_base_url = f"https://api.telegram.org/bot{config.bot_token}"
        self._pending_confirmations: dict[str, ConfirmationRequest] = {}
        self._command_handlers: dict[str, Callable[[dict[str, Any]], None]] = {}
        self._briefing_generator: Callable[[str], str] | None = None

        # Setup temp directory for file downloads
        if config.temp_dir:
            config.temp_dir.mkdir(parents=True, exist_ok=True)

        # Setup scheduled briefings if scheduler provided
        if self.scheduler:
            self._setup_briefing_schedules()

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
            return self._api_request("sendMessage", params)
        except Exception as exc:
            self._log_event(
                "send_message_failed",
                {
                    "chat_id": chat_id,
                    "error": str(exc),
                },
            )
            return None

    def register_command_handler(self, command: str, handler: Callable[[dict[str, Any]], None]) -> None:
        """Register handler for plugin command triggered by confirmation.

        Parameters
        ----------
        command
            Command name (e.g., "inbox.confirm_task")
        handler
            Handler function receiving context dict
        """
        self._command_handlers[command] = handler
        self._log_event("command_handler_registered", {"command": command})

    def set_briefing_generator(self, generator: Callable[[str], str]) -> None:
        """Set briefing content generator function.

        Parameters
        ----------
        generator
            Function that takes briefing type ("daily" or "weekly") and returns formatted content
        """
        self._briefing_generator = generator

    def request_confirmation(
        self,
        chat_id: int,
        message: str,
        options: list[dict[str, str]],
        command: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Request user confirmation via inline buttons.

        Parameters
        ----------
        chat_id
            Target chat ID
        message
            Confirmation message
        options
            List of options with text and callback_data
        command
            Plugin command to execute on selection
        context
            Optional context data to pass to command handler

        Returns
        -------
        str
            Request ID for tracking

        Example
        -------
        >>> adapter.request_confirmation(
        ...     chat_id=123456,
        ...     message="Is this a task?\\n\\n'Fix bug in auth'",
        ...     options=[
        ...         {"text": "✅ Yes", "callback_data": "yes"},
        ...         {"text": "❌ No", "callback_data": "no"}
        ...     ],
        ...     command="inbox.confirm_task",
        ...     context={"entity_id": "task-123", "title": "Fix bug in auth"}
        ... )
        'req-abc123'
        """
        request_id = f"req-{uuid.uuid4().hex[:12]}"
        trace_id = str(uuid.uuid4())

        # Create confirmation request
        confirmation = ConfirmationRequest(
            request_id=request_id,
            chat_id=chat_id,
            message=message,
            options=options,
            command=command,
            context=context or {},
        )

        # Add CSRF tokens to callback data
        signed_options = []
        for opt in options:
            callback_data = opt["callback_data"]
            # Sign: request_id:callback_data:signature
            signature = self._generate_csrf_token(request_id, callback_data)
            signed_callback = f"{request_id}:{callback_data}:{signature}"
            signed_options.append({"text": opt["text"], "callback_data": signed_callback})

        confirmation.options = signed_options
        self._pending_confirmations[request_id] = confirmation

        # Send message with inline keyboard
        keyboard = confirmation.get_inline_keyboard()
        response = self.send_message(chat_id, message, reply_markup=keyboard)

        success = response is not None

        self._log_event(
            "confirmation_requested" if success else "confirmation_request_failed",
            {
                "trace_id": trace_id,
                "request_id": request_id,
                "chat_id": chat_id,
                "command": command,
                "outcome": "success" if success else "failure",
            },
        )

        return request_id

    def send_daily_briefing(self, chat_id: int, briefing_content: str | None = None) -> bool:
        """Send daily briefing to chat.

        Parameters
        ----------
        chat_id
            Target chat ID
        briefing_content
            Optional briefing content (Markdown formatted).
            If not provided, uses briefing_generator.

        Returns
        -------
        bool
            True if sent successfully
        """
        trace_id = str(uuid.uuid4())

        # Generate content if not provided
        if briefing_content is None:
            if self._briefing_generator:
                try:
                    briefing_content = self._briefing_generator("daily")
                except Exception as exc:
                    self._log_event(
                        "briefing_generation_failed",
                        {
                            "trace_id": trace_id,
                            "chat_id": chat_id,
                            "error": str(exc),
                        },
                    )
                    briefing_content = "❌ Failed to generate daily briefing"
            else:
                briefing_content = "ℹ️ Daily briefing not configured"

        self._log_event(
            "briefing_sending",
            {
                "trace_id": trace_id,
                "chat_id": chat_id,
                "briefing_type": "daily",
            },
        )

        response = self.send_message(chat_id, f"📅 *Daily Briefing*\n\n{briefing_content}")

        success = response is not None

        self._log_event(
            "briefing_sent" if success else "briefing_failed",
            {
                "trace_id": trace_id,
                "chat_id": chat_id,
                "briefing_type": "daily",
                "outcome": "success" if success else "failure",
            },
        )

        return success

    def send_weekly_briefing(self, chat_id: int, briefing_content: str | None = None) -> bool:
        """Send weekly briefing to chat.

        Parameters
        ----------
        chat_id
            Target chat ID
        briefing_content
            Optional briefing content (Markdown formatted).
            If not provided, uses briefing_generator.

        Returns
        -------
        bool
            True if sent successfully
        """
        trace_id = str(uuid.uuid4())

        # Generate content if not provided
        if briefing_content is None:
            if self._briefing_generator:
                try:
                    briefing_content = self._briefing_generator("weekly")
                except Exception as exc:
                    self._log_event(
                        "briefing_generation_failed",
                        {
                            "trace_id": trace_id,
                            "chat_id": chat_id,
                            "error": str(exc),
                        },
                    )
                    briefing_content = "❌ Failed to generate weekly briefing"
            else:
                briefing_content = "ℹ️ Weekly briefing not configured"

        self._log_event(
            "briefing_sending",
            {
                "trace_id": trace_id,
                "chat_id": chat_id,
                "briefing_type": "weekly",
            },
        )

        response = self.send_message(chat_id, f"📊 *Weekly Briefing*\n\n{briefing_content}")

        success = response is not None

        self._log_event(
            "briefing_sent" if success else "briefing_failed",
            {
                "trace_id": trace_id,
                "chat_id": chat_id,
                "briefing_type": "weekly",
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

        return bool(self.config.allowed_user_ids and user_id in self.config.allowed_user_ids)

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
            "timestamp": datetime.fromtimestamp(message.timestamp, tz=UTC).isoformat(),
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
            "timestamp": datetime.fromtimestamp(message.timestamp, tz=UTC).isoformat(),
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
        """Handle inline button callback with CSRF verification.

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
        user_id = callback_data.get("from", {}).get("id")

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
        with contextlib.suppress(Exception):
            self._api_request("answerCallbackQuery", {"callback_query_id": callback_id})

        # Parse signed callback data: request_id:callback_data:signature
        parts = data.split(":", 2)
        if len(parts) == 3:
            request_id, choice, signature = parts

            # Verify CSRF token
            if not self._verify_csrf_token(request_id, choice, signature):
                self._log_event(
                    "callback_csrf_failed",
                    {
                        "trace_id": trace_id,
                        "request_id": request_id,
                        "reason": "invalid_signature",
                    },
                )
                self.send_message(chat_id, "❌ Invalid confirmation token. Please try again.")
                return

            # Get confirmation request
            confirmation = self._pending_confirmations.get(request_id)
            if not confirmation:
                self._log_event(
                    "callback_confirmation_not_found",
                    {
                        "trace_id": trace_id,
                        "request_id": request_id,
                    },
                )
                self.send_message(chat_id, "❌ Confirmation request not found or expired.")
                return

            # Check expiration
            if confirmation.is_expired():
                self._log_event(
                    "callback_confirmation_expired",
                    {
                        "trace_id": trace_id,
                        "request_id": request_id,
                    },
                )
                self.send_message(chat_id, "❌ Confirmation request expired. Please try again.")
                del self._pending_confirmations[request_id]
                return

            # Execute command handler
            handler = self._command_handlers.get(confirmation.command)
            if handler:
                try:
                    # Prepare context
                    context = confirmation.context.copy()
                    context["choice"] = choice
                    context["chat_id"] = chat_id
                    context["user_id"] = user_id
                    context["trace_id"] = trace_id

                    # Call handler
                    handler(context)

                    self._log_event(
                        "callback_command_executed",
                        {
                            "trace_id": trace_id,
                            "request_id": request_id,
                            "command": confirmation.command,
                            "choice": choice,
                        },
                    )

                    # Send success message
                    self.send_message(chat_id, f"✅ Confirmed: {choice}")

                except Exception as exc:
                    self._log_event(
                        "callback_command_failed",
                        {
                            "trace_id": trace_id,
                            "request_id": request_id,
                            "command": confirmation.command,
                            "error": str(exc),
                        },
                    )
                    self.send_message(chat_id, f"❌ Failed to process confirmation: {exc}")
            else:
                self._log_event(
                    "callback_handler_not_found",
                    {
                        "trace_id": trace_id,
                        "request_id": request_id,
                        "command": confirmation.command,
                    },
                )

            # Remove processed confirmation
            del self._pending_confirmations[request_id]

        else:
            # Legacy callback without signature - publish generic event
            if self.event_bus:
                payload = {
                    "callback_id": callback_id,
                    "data": data,
                    "chat_id": chat_id,
                    "trace_id": trace_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
                self.event_bus.publish("telegram.callback", payload)

    def _api_request(self, _method: str, _params: dict[str, Any]) -> dict[str, Any] | None:
        """Make Telegram API request.

        Parameters
        ----------
        _method
            API method name
        _params
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

    def _generate_csrf_token(self, request_id: str, callback_data: str) -> str:
        """Generate CSRF token for callback data.

        Parameters
        ----------
        request_id
            Request ID
        callback_data
            Callback data to sign

        Returns
        -------
        str
            HMAC signature (hex)
        """
        message = f"{request_id}:{callback_data}"
        return hmac.new(
            self.config.csrf_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()[
            :16
        ]  # Use first 16 chars to keep callback data short

    def _verify_csrf_token(self, request_id: str, callback_data: str, signature: str) -> bool:
        """Verify CSRF token.

        Parameters
        ----------
        request_id
            Request ID
        callback_data
            Callback data
        signature
            Provided signature

        Returns
        -------
        bool
            True if signature is valid
        """
        expected = self._generate_csrf_token(request_id, callback_data)
        return hmac.compare_digest(expected, signature)

    def _setup_briefing_schedules(self) -> None:
        """Setup scheduled briefings using scheduler."""
        if not self.scheduler:
            return

        # Parse daily briefing time
        try:
            hour, minute = map(int, self.config.daily_briefing_time.split(":"))

            # Schedule daily briefing for each allowed chat
            for chat_id in self.config.allowed_chat_ids:
                self.scheduler.schedule_cron(
                    f"daily_briefing_{chat_id}",
                    f"{minute} {hour} * * *",  # Daily at specified time
                    lambda cid=chat_id: self.send_daily_briefing(cid),
                    job_id=f"telegram_daily_briefing_{chat_id}",
                    metadata={"chat_id": chat_id, "type": "daily_briefing"},
                )

            self._log_event(
                "daily_briefing_scheduled",
                {
                    "time": self.config.daily_briefing_time,
                    "chat_count": len(self.config.allowed_chat_ids),
                },
            )
        except Exception as exc:
            self._log_event(
                "daily_briefing_schedule_failed",
                {"error": str(exc)},
            )

        # Parse weekly briefing time
        try:
            hour, minute = map(int, self.config.weekly_briefing_time.split(":"))
            day = self.config.weekly_briefing_day

            # Schedule weekly briefing for each allowed chat
            for chat_id in self.config.allowed_chat_ids:
                self.scheduler.schedule_cron(
                    f"weekly_briefing_{chat_id}",
                    f"{minute} {hour} * * {day}",  # Weekly on specified day
                    lambda cid=chat_id: self.send_weekly_briefing(cid),
                    job_id=f"telegram_weekly_briefing_{chat_id}",
                    metadata={"chat_id": chat_id, "type": "weekly_briefing"},
                )

            self._log_event(
                "weekly_briefing_scheduled",
                {
                    "time": self.config.weekly_briefing_time,
                    "day": day,
                    "chat_count": len(self.config.allowed_chat_ids),
                },
            )
        except Exception as exc:
            self._log_event(
                "weekly_briefing_schedule_failed",
                {"error": str(exc)},
            )

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
            "timestamp": datetime.now(UTC).isoformat(),
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


class BriefingScheduler:
    """Helper class for generating briefing content from Vault data.

    This integrates with HostAPI to pull summaries and format them for Telegram.
    """

    def __init__(self, host_api: Any = None) -> None:
        """Initialize briefing scheduler.

        Parameters
        ----------
        host_api
            Host API instance for Vault access
        """
        self.host_api = host_api

    def generate_daily_briefing(self) -> str:
        """Generate daily briefing content.

        Returns
        -------
        str
            Formatted briefing content (Markdown)
        """
        sections = []

        # Today's summary
        sections.append("*🌅 Good Morning!*\n")
        sections.append("Here's what's on your agenda today:")

        # Tasks due today
        if self.host_api:
            try:
                tasks = list(self.host_api.list_entities("task", limit=20))
                due_today = [t for t in tasks if self._is_due_today(t)]

                if due_today:
                    sections.append(f"\n📋 *Tasks Due Today ({len(due_today)}):*")
                    for task in due_today[:5]:
                        title = task.get_title()
                        sections.append(f"  • {title}")
                    if len(due_today) > 5:
                        sections.append(f"  ... and {len(due_today) - 5} more")
                else:
                    sections.append("\n📋 *Tasks:* No tasks due today! 🎉")
            except Exception:
                sections.append("\n📋 *Tasks:* Unable to fetch tasks")

            # Events today
            try:
                events = list(self.host_api.list_entities("event", limit=10))
                today_events = [e for e in events if self._is_today(e)]

                if today_events:
                    sections.append(f"\n📅 *Events Today ({len(today_events)}):*")
                    for event in today_events[:3]:
                        title = event.get_title()
                        sections.append(f"  • {title}")
                    if len(today_events) > 3:
                        sections.append(f"  ... and {len(today_events) - 3} more")
            except Exception:
                pass
        else:
            sections.append("\n_Vault integration not configured_")

        sections.append("\n✨ *Have a productive day!*")

        return "\n".join(sections)

    def generate_weekly_briefing(self) -> str:
        """Generate weekly briefing content.

        Returns
        -------
        str
            Formatted briefing content (Markdown)
        """
        sections = []

        # Week summary
        sections.append("*📊 Weekly Summary*\n")
        sections.append("Here's your week at a glance:")

        if self.host_api:
            try:
                tasks = list(self.host_api.list_entities("task", limit=50))

                # Completed this week
                completed = [t for t in tasks if self._completed_this_week(t)]
                sections.append(f"\n✅ *Completed:* {len(completed)} tasks")

                # In progress
                in_progress = [t for t in tasks if t.metadata.get("status") == "doing"]
                sections.append(f"⏳ *In Progress:* {len(in_progress)} tasks")

                # Due this week
                due_this_week = [t for t in tasks if self._is_due_this_week(t)]
                if due_this_week:
                    sections.append(f"\n📋 *Due This Week ({len(due_this_week)}):*")
                    for task in due_this_week[:5]:
                        title = task.get_title()
                        status = task.metadata.get("status", "unknown")
                        sections.append(f"  • [{status}] {title}")
                    if len(due_this_week) > 5:
                        sections.append(f"  ... and {len(due_this_week) - 5} more")

            except Exception:
                sections.append("\n_Unable to fetch Vault data_")
        else:
            sections.append("\n_Vault integration not configured_")

        sections.append("\n🚀 *Keep up the great work!*")

        return "\n".join(sections)

    def _is_due_today(self, entity: Any) -> bool:
        """Check if entity is due today (UTC)."""
        due = entity.metadata.get("due")
        if not due:
            return False
        try:
            due_date = datetime.fromisoformat(due.replace("Z", "+00:00")).date()
            today_utc = datetime.now(UTC).date()
            return due_date == today_utc
        except Exception:
            return False

    def _is_today(self, entity: Any) -> bool:
        """Check if entity is scheduled for today (UTC)."""
        start = entity.metadata.get("start")
        if not start:
            return False
        try:
            start_date = datetime.fromisoformat(start.replace("Z", "+00:00")).date()
            today_utc = datetime.now(UTC).date()
            return start_date == today_utc
        except Exception:
            return False

    def _is_due_this_week(self, entity: Any) -> bool:
        """Check if entity is due this week."""
        due = entity.metadata.get("due")
        if not due:
            return False
        try:
            from datetime import date, timedelta

            due_date = datetime.fromisoformat(due.replace("Z", "+00:00")).date()
            today = date.today()
            week_end = today + timedelta(days=7)
            return today <= due_date <= week_end
        except Exception:
            return False

    def _completed_this_week(self, entity: Any) -> bool:
        """Check if entity was completed this week."""
        status = entity.metadata.get("status")
        if status != "done":
            return False

        completed_at = entity.metadata.get("completed_at") or entity.updated_at
        if not completed_at:
            return False

        try:
            from datetime import date, timedelta

            if isinstance(completed_at, str):
                completed_date = datetime.fromisoformat(completed_at.replace("Z", "+00:00")).date()
            else:
                completed_date = completed_at.date()

            today = date.today()
            week_start = today - timedelta(days=today.weekday())
            return week_start <= completed_date <= today
        except Exception:
            return False


def create_telegram_adapter(
    bot_token: str,
    *,
    event_bus: EventBus | None = None,
    scheduler: Scheduler | None = None,
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
    scheduler
        Optional scheduler for automatic briefings
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
        ...     scheduler=scheduler,
        ...     allowed_chat_ids=[123456789],
        ...     log_path=Path("logs/adapters/telegram.jsonl")
        ... )
    """
    if log_path:
        log_path = Path(log_path) if isinstance(log_path, str) else log_path
        config_kwargs["log_path"] = log_path

    config = TelegramAdapterConfig(bot_token=bot_token, **config_kwargs)

    return TelegramAdapter(config, event_bus=event_bus, scheduler=scheduler, logger=logger)
