"""Canonical event registry for the system (ADR-005).

Defines standard events emitted by core components, adapters, and pipelines.
Extensions should be documented via ADR or registry updates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = [
    "CANONICAL_EVENTS",
    "EventDefinition",
    "get_event_definition",
    "is_canonical_event",
]


@dataclass
class EventDefinition:
    """Definition of a canonical event."""

    name: str
    category: str
    description: str
    payload_schema: dict[str, str] | None = None
    emitted_by: list[str] | None = None

    def __post_init__(self) -> None:
        """Initialize default values."""
        if self.payload_schema is None:
            self.payload_schema = {}
        if self.emitted_by is None:
            self.emitted_by = []


# Adapter Events
MESSAGE_RECEIVED = EventDefinition(
    name="message.received",
    category="adapter",
    description="Message received from external source (e.g., Telegram)",
    payload_schema={
        "message": "str - Message text",
        "source": "str - Source adapter (telegram, email, etc.)",
        "chat_id": "str - Optional chat/conversation ID",
        "user_id": "str - Optional user identifier",
        "timestamp": "str - ISO 8601 timestamp",
    },
    emitted_by=["telegram_adapter", "email_adapter"],
)

FILE_DROPPED = EventDefinition(
    name="file.dropped",
    category="adapter",
    description="File dropped into inbox or upload location",
    payload_schema={
        "file_path": "str - Path to the file",
        "file_name": "str - Original file name",
        "mime_type": "str - MIME type",
        "size_bytes": "int - File size in bytes",
        "source": "str - Source adapter",
    },
    emitted_by=["filesystem_adapter", "telegram_adapter"],
)

SYNC_TICK = EventDefinition(
    name="sync.tick",
    category="adapter",
    description="Periodic synchronization tick from external system",
    payload_schema={
        "adapter": "str - Adapter name",
        "tick_type": "str - Type of sync (pull, push, bidirectional)",
    },
    emitted_by=["gcal_adapter", "sync_scheduler"],
)

# Entity Events
ENTITY_CREATED = EventDefinition(
    name="entity.created",
    category="vault",
    description="Entity created in vault via Host API",
    payload_schema={
        "entity_id": "str - Unique entity identifier",
        "entity_type": "str - Type of entity (task, note, event, etc.)",
        "path": "str - Vault path",
        "metadata": "dict - Entity metadata",
    },
    emitted_by=["host_api"],
)

ENTITY_UPDATED = EventDefinition(
    name="entity.updated",
    category="vault",
    description="Entity updated in vault via Host API",
    payload_schema={
        "entity_id": "str - Unique entity identifier",
        "entity_type": "str - Type of entity",
        "path": "str - Vault path",
        "changes": "dict - Changed fields",
    },
    emitted_by=["host_api"],
)

ENTITY_DELETED = EventDefinition(
    name="entity.deleted",
    category="vault",
    description="Entity deleted from vault via Host API",
    payload_schema={
        "entity_id": "str - Unique entity identifier",
        "entity_type": "str - Type of entity",
        "path": "str - Former vault path",
    },
    emitted_by=["host_api"],
)

# Task Events
TASK_CREATED = EventDefinition(
    name="task.created",
    category="task",
    description="Task created in system",
    payload_schema={
        "task_id": "str - Task identifier",
        "title": "str - Task title",
        "priority": "str - Priority (low, medium, high)",
        "due_date": "str - Optional due date (ISO 8601)",
    },
    emitted_by=["inbox_plugin", "task_plugin"],
)

TASK_DUE_SOON = EventDefinition(
    name="task.due_soon",
    category="task",
    description="Task is approaching due date",
    payload_schema={
        "task_id": "str - Task identifier",
        "title": "str - Task title",
        "due_date": "str - Due date (ISO 8601)",
        "hours_remaining": "int - Hours until due",
    },
    emitted_by=["deadlines_plugin", "scheduler"],
)

TASK_ENTER_DOING = EventDefinition(
    name="task.enter_doing",
    category="task",
    description="Task transitioned to 'doing' state (ADR-014)",
    payload_schema={
        "task_id": "str - Task identifier",
        "title": "str - Task title",
        "time_hint": "int - Optional timeboxing hint in minutes",
    },
    emitted_by=["task_fsm"],
)

TASK_ENTER_REVIEW = EventDefinition(
    name="task.enter_review",
    category="task",
    description="Task transitioned to 'review' state (ADR-014)",
    payload_schema={
        "task_id": "str - Task identifier",
        "title": "str - Task title",
        "reviewer": "str - Optional reviewer identifier",
    },
    emitted_by=["task_fsm"],
)

TASK_ENTER_DONE = EventDefinition(
    name="task.enter_done",
    category="task",
    description="Task completed (ADR-014)",
    payload_schema={
        "task_id": "str - Task identifier",
        "title": "str - Task title",
        "completed_at": "str - Completion timestamp (ISO 8601)",
    },
    emitted_by=["task_fsm"],
)

TASK_ENTER_BLOCKED = EventDefinition(
    name="task.enter_blocked",
    category="task",
    description="Task became blocked (ADR-014)",
    payload_schema={
        "task_id": "str - Task identifier",
        "title": "str - Task title",
        "blocked_reason": "str - Reason for blocking",
    },
    emitted_by=["task_fsm"],
)

# Calendar Events
EVENT_RECEIVED = EventDefinition(
    name="event.received",
    category="calendar",
    description="Calendar event received from external calendar",
    payload_schema={
        "event_id": "str - Event identifier",
        "title": "str - Event title",
        "start_time": "str - Start time (ISO 8601)",
        "end_time": "str - End time (ISO 8601)",
        "calendar": "str - Calendar name/ID",
    },
    emitted_by=["gcal_adapter"],
)

MEETING_FINISHED = EventDefinition(
    name="meeting.finished",
    category="calendar",
    description="Scheduled meeting has finished",
    payload_schema={
        "event_id": "str - Event identifier",
        "title": "str - Meeting title",
        "duration_minutes": "int - Actual duration",
    },
    emitted_by=["calendar_plugin"],
)

# Inbox Events
INBOX_NORMALIZED = EventDefinition(
    name="inbox.normalized",
    category="inbox",
    description="Inbox item normalized and processed (ADR-013)",
    payload_schema={
        "entity_id": "str - Created entity ID",
        "entity_type": "str - Type of entity created",
        "source": "str - Original source",
        "confidence": "float - Confidence score (0-1)",
    },
    emitted_by=["inbox_plugin"],
)

# Plugin Events
PLUGIN_ACTIVATED = EventDefinition(
    name="plugin.activated",
    category="plugin",
    description="Plugin successfully activated",
    payload_schema={
        "plugin_name": "str - Plugin identifier",
        "version": "str - Plugin version",
    },
    emitted_by=["plugin_loader"],
)

PLUGIN_FAILED = EventDefinition(
    name="plugin.failed",
    category="plugin",
    description="Plugin failed to load or execute",
    payload_schema={
        "plugin_name": "str - Plugin identifier",
        "error": "str - Error message",
    },
    emitted_by=["plugin_loader", "sandbox"],
)

# Calendar/Timeboxing Events
CALENDAR_ACTIVATE = EventDefinition(
    name="calendar.activate",
    category="calendar",
    description="Calendar plugin activated",
    payload_schema={
        "message": "str - Activation message",
        "plugin": "str - Plugin name",
    },
    emitted_by=["calendar_plugin"],
)

CODE_ACTIVATE = EventDefinition(
    name="code.activate",
    category="code",
    description="Code assistant plugin activated",
    payload_schema={
        "message": "str - Activation message",
        "plugin": "str - Plugin name",
    },
    emitted_by=["code_plugin"],
)


# Registry of all canonical events
CANONICAL_EVENTS: dict[str, EventDefinition] = {
    # Adapter events
    "message.received": MESSAGE_RECEIVED,
    "file.dropped": FILE_DROPPED,
    "sync.tick": SYNC_TICK,
    # Entity events
    "entity.created": ENTITY_CREATED,
    "entity.updated": ENTITY_UPDATED,
    "entity.deleted": ENTITY_DELETED,
    # Task events
    "task.created": TASK_CREATED,
    "task.due_soon": TASK_DUE_SOON,
    "task.enter_doing": TASK_ENTER_DOING,
    "task.enter_review": TASK_ENTER_REVIEW,
    "task.enter_done": TASK_ENTER_DONE,
    "task.enter_blocked": TASK_ENTER_BLOCKED,
    # Calendar events
    "event.received": EVENT_RECEIVED,
    "meeting.finished": MEETING_FINISHED,
    # Inbox events
    "inbox.normalized": INBOX_NORMALIZED,
    # Plugin events
    "plugin.activated": PLUGIN_ACTIVATED,
    "plugin.failed": PLUGIN_FAILED,
    # Plugin-specific events
    "calendar.activate": CALENDAR_ACTIVATE,
    "code.activate": CODE_ACTIVATE,
}


def get_event_definition(event_name: str) -> EventDefinition | None:
    """Get definition for canonical event.

    Parameters
    ----------
    event_name
        Event name

    Returns
    -------
    EventDefinition or None
        Event definition if found
    """
    return CANONICAL_EVENTS.get(event_name)


def is_canonical_event(event_name: str) -> bool:
    """Check if event name is canonical.

    Parameters
    ----------
    event_name
        Event name to check

    Returns
    -------
    bool
        True if event is canonical
    """
    return event_name in CANONICAL_EVENTS


def get_events_by_category(category: str) -> list[EventDefinition]:
    """Get all canonical events in category.

    Parameters
    ----------
    category
        Category name (adapter, vault, task, calendar, inbox, plugin)

    Returns
    -------
    list[EventDefinition]
        List of events in category
    """
    return [event for event in CANONICAL_EVENTS.values() if event.category == category]
