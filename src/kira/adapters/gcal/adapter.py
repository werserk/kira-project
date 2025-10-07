"""Google Calendar adapter for Kira (ADR-012).

Provides two-way synchronization between Vault entities and Google Calendar,
with support for event mapping, conflict resolution, and timeboxing.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...core.events import EventBus

__all__ = [
    "GCalAdapter",
    "GCalAdapterConfig",
    "GCalEvent",
    "EventMapping",
    "SyncResult",
    "create_gcal_adapter",
]


@dataclass
class GCalEvent:
    """Google Calendar event representation."""

    id: str
    summary: str
    start: datetime
    end: datetime
    description: str | None = None
    location: str | None = None
    attendees: list[str] = field(default_factory=list)
    all_day: bool = False
    updated: datetime | None = None
    recurring_event_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API calls."""
        event_dict = {
            "summary": self.summary,
            "start": {
                "dateTime": self.start.isoformat() if not self.all_day else None,
                "date": self.start.date().isoformat() if self.all_day else None,
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": self.end.isoformat() if not self.all_day else None,
                "date": self.end.date().isoformat() if self.all_day else None,
                "timeZone": "UTC",
            },
        }

        if self.description:
            event_dict["description"] = self.description
        if self.location:
            event_dict["location"] = self.location
        if self.attendees:
            event_dict["attendees"] = [{"email": email} for email in self.attendees]

        return event_dict

    @classmethod
    def from_vault_entity(cls, entity: Any) -> GCalEvent:
        """Create GCal event from Vault entity.

        Parameters
        ----------
        entity
            Vault entity (event or task)

        Returns
        -------
        GCalEvent
            Google Calendar event
        """
        metadata = entity.metadata
        entity_id = metadata.get("id", "unknown")
        title = entity.get_title()

        # Determine if all-day event
        all_day = metadata.get("all_day", False)

        # Parse start/end times
        start_str = metadata.get("start") or metadata.get("due")
        if not start_str:
            # Default to today
            start = datetime.now(timezone.utc).replace(hour=9, minute=0, second=0, microsecond=0)
        else:
            try:
                start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            except Exception:
                start = datetime.now(timezone.utc)

        # Calculate end time
        end_str = metadata.get("end")
        if end_str:
            try:
                end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
            except Exception:
                end = start + timedelta(hours=1)
        else:
            # Use time_hint if available (for tasks)
            time_hint = metadata.get("time_hint", 60)  # Default 1 hour
            if isinstance(time_hint, str):
                # Parse formats like "2h", "30m"
                if time_hint.endswith("h"):
                    time_hint = int(time_hint[:-1]) * 60
                elif time_hint.endswith("m"):
                    time_hint = int(time_hint[:-1])
                else:
                    time_hint = 60
            end = start + timedelta(minutes=int(time_hint))

        # Build description with Vault link
        description = metadata.get("description", "")
        vault_link = f"\n\n[View in Vault: {entity_id}]"
        if description:
            description = f"{description}{vault_link}"
        else:
            description = f"Synced from Vault{vault_link}"

        # Get GCal ID if already synced
        gcal_id = metadata.get("gcal_id", f"vault-{entity_id}")

        return cls(
            id=gcal_id,
            summary=title,
            start=start,
            end=end,
            description=description,
            location=metadata.get("location"),
            attendees=metadata.get("attendees", []),
            all_day=all_day,
        )


@dataclass
class EventMapping:
    """Mapping between Vault entity and GCal event."""

    vault_id: str
    gcal_id: str
    vault_updated: datetime
    gcal_updated: datetime
    last_synced: datetime
    sync_direction: str  # "vault_to_gcal", "gcal_to_vault", "bidirectional"


@dataclass
class SyncResult:
    """Result of synchronization operation."""

    pulled: int = 0
    pushed: int = 0
    conflicts: int = 0
    errors: int = 0
    skipped: int = 0
    duration_ms: float = 0
    error_messages: list[str] = field(default_factory=list)


@dataclass
class GCalAdapterConfig:
    """Configuration for Google Calendar adapter."""

    credentials_path: Path | None = None
    token_path: Path | None = None
    calendar_id: str = "primary"
    sync_days_past: int = 7
    sync_days_future: int = 30
    rate_limit_delay: float = 0.1
    max_retries: int = 3
    retry_delay: float = 2.0
    log_path: Path | None = None


class GCalAdapter:
    """Google Calendar adapter for two-way sync (ADR-012).

    Responsibilities:
    - Pull events from Google Calendar
    - Push Vault entities to Google Calendar
    - Map Vault entities to GCal events
    - Handle conflict resolution
    - Emit structured logs with correlation IDs

    Example:
        >>> adapter = create_gcal_adapter(
        ...     credentials_path=Path("credentials.json"),
        ...     event_bus=event_bus,
        ... )
        >>> result = adapter.pull()
        >>> print(f"Pulled {result.pulled} events")
    """

    def __init__(
        self,
        config: GCalAdapterConfig,
        *,
        event_bus: EventBus | None = None,
        logger: Any = None,
    ) -> None:
        """Initialize Google Calendar adapter.

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
        self._service = None  # Google Calendar API service (lazy init)
        self._mappings: dict[str, EventMapping] = {}  # vault_id -> mapping

    def pull(
        self,
        calendar_id: str | None = None,
        days: int | None = None,
    ) -> SyncResult:
        """Pull events from Google Calendar.

        Parameters
        ----------
        calendar_id
            Calendar ID (default: from config)
        days
            Days to fetch (default: from config)

        Returns
        -------
        SyncResult
            Sync operation result
        """
        calendar_id = calendar_id or self.config.calendar_id
        days = days or (self.config.sync_days_past + self.config.sync_days_future)

        trace_id = str(uuid.uuid4())
        start_time = time.time()

        self._log_event(
            "gcal_pull_started",
            {
                "trace_id": trace_id,
                "calendar_id": calendar_id,
                "days": days,
            },
        )

        result = SyncResult()

        try:
            # Fetch events from GCal
            events = self._fetch_events(calendar_id, days)

            # Publish events for plugin processing
            for event in events:
                self._publish_event_received(event, trace_id)
                result.pulled += 1

                # Small delay to respect rate limits
                time.sleep(self.config.rate_limit_delay)

        except Exception as exc:
            result.errors += 1
            result.error_messages.append(str(exc))
            self._log_event(
                "gcal_pull_failed",
                {
                    "trace_id": trace_id,
                    "error": str(exc),
                },
            )

        result.duration_ms = (time.time() - start_time) * 1000

        self._log_event(
            "gcal_pull_completed",
            {
                "trace_id": trace_id,
                "pulled": result.pulled,
                "errors": result.errors,
                "duration_ms": result.duration_ms,
            },
        )

        return result

    def push(
        self,
        entities: list[Any],
        calendar_id: str | None = None,
        dry_run: bool = False,
    ) -> SyncResult:
        """Push Vault entities to Google Calendar.

        Parameters
        ----------
        entities
            List of Vault entities to push
        calendar_id
            Calendar ID (default: from config)
        dry_run
            If True, don't actually push

        Returns
        -------
        SyncResult
            Sync operation result
        """
        calendar_id = calendar_id or self.config.calendar_id

        trace_id = str(uuid.uuid4())
        start_time = time.time()

        self._log_event(
            "gcal_push_started",
            {
                "trace_id": trace_id,
                "calendar_id": calendar_id,
                "entity_count": len(entities),
                "dry_run": dry_run,
            },
        )

        result = SyncResult()

        try:
            for entity in entities:
                try:
                    # Convert to GCal event
                    gcal_event = GCalEvent.from_vault_entity(entity)

                    # Check if needs update
                    if self._should_push_entity(entity):
                        if not dry_run:
                            self._push_event(calendar_id, gcal_event)
                        result.pushed += 1
                    else:
                        result.skipped += 1

                    # Small delay to respect rate limits
                    time.sleep(self.config.rate_limit_delay)

                except Exception as exc:
                    result.errors += 1
                    result.error_messages.append(f"{entity.id}: {exc}")
                    self._log_event(
                        "gcal_push_entity_failed",
                        {
                            "trace_id": trace_id,
                            "entity_id": entity.id,
                            "error": str(exc),
                        },
                    )

        except Exception as exc:
            result.errors += 1
            result.error_messages.append(str(exc))
            self._log_event(
                "gcal_push_failed",
                {
                    "trace_id": trace_id,
                    "error": str(exc),
                },
            )

        result.duration_ms = (time.time() - start_time) * 1000

        self._log_event(
            "gcal_push_completed",
            {
                "trace_id": trace_id,
                "pushed": result.pushed if not dry_run else 0,
                "skipped": result.skipped,
                "errors": result.errors,
                "duration_ms": result.duration_ms,
                "dry_run": dry_run,
            },
        )

        return result

    def reconcile(
        self,
        vault_entities: list[Any],
        calendar_id: str | None = None,
    ) -> SyncResult:
        """Reconcile differences between Vault and GCal.

        Uses last-writer-wins strategy based on updated timestamps.

        Parameters
        ----------
        vault_entities
            List of Vault entities
        calendar_id
            Calendar ID (default: from config)

        Returns
        -------
        SyncResult
            Reconciliation result
        """
        calendar_id = calendar_id or self.config.calendar_id

        trace_id = str(uuid.uuid4())
        start_time = time.time()

        self._log_event(
            "gcal_reconcile_started",
            {
                "trace_id": trace_id,
                "vault_entity_count": len(vault_entities),
            },
        )

        result = SyncResult()

        try:
            # Fetch current GCal events
            gcal_events = self._fetch_events(calendar_id, self.config.sync_days_future)

            # Build mapping by ID
            gcal_by_id = {evt.id: evt for evt in gcal_events}
            vault_by_id = {ent.id: ent for ent in vault_entities}

            # Check for conflicts
            for entity in vault_entities:
                gcal_id = entity.metadata.get("gcal_id")
                if not gcal_id:
                    continue

                if gcal_id in gcal_by_id:
                    gcal_event = gcal_by_id[gcal_id]

                    # Compare timestamps
                    vault_updated = entity.updated_at
                    gcal_updated = gcal_event.updated or datetime.now(timezone.utc)

                    if abs((vault_updated - gcal_updated).total_seconds()) > 60:
                        # Conflict detected
                        result.conflicts += 1

                        # Last-writer-wins
                        if vault_updated > gcal_updated:
                            # Vault is newer - push to GCal
                            self._push_event(calendar_id, GCalEvent.from_vault_entity(entity))
                            result.pushed += 1
                        else:
                            # GCal is newer - publish for Vault update
                            self._publish_event_received(gcal_event, trace_id)
                            result.pulled += 1

                        self._log_event(
                            "gcal_conflict_resolved",
                            {
                                "trace_id": trace_id,
                                "entity_id": entity.id,
                                "gcal_id": gcal_id,
                                "resolution": "vault_newer" if vault_updated > gcal_updated else "gcal_newer",
                            },
                        )

        except Exception as exc:
            result.errors += 1
            result.error_messages.append(str(exc))
            self._log_event(
                "gcal_reconcile_failed",
                {
                    "trace_id": trace_id,
                    "error": str(exc),
                },
            )

        result.duration_ms = (time.time() - start_time) * 1000

        self._log_event(
            "gcal_reconcile_completed",
            {
                "trace_id": trace_id,
                "conflicts": result.conflicts,
                "pulled": result.pulled,
                "pushed": result.pushed,
                "duration_ms": result.duration_ms,
            },
        )

        return result

    def create_timebox(
        self,
        task: Any,
        calendar_id: str | None = None,
    ) -> str | None:
        """Create timeboxed event in GCal for task.

        Parameters
        ----------
        task
            Vault task entity
        calendar_id
            Calendar ID (default: from config)

        Returns
        -------
        str or None
            GCal event ID if created
        """
        calendar_id = calendar_id or self.config.calendar_id
        trace_id = str(uuid.uuid4())

        try:
            # Convert task to GCal event
            gcal_event = GCalEvent.from_vault_entity(task)

            # Add timeboxing indicators
            gcal_event.summary = f"🔲 {gcal_event.summary}"
            gcal_event.description = f"[TIMEBOX] {gcal_event.description}"

            # Push to GCal
            event_id = self._push_event(calendar_id, gcal_event)

            self._log_event(
                "timebox_created",
                {
                    "trace_id": trace_id,
                    "task_id": task.id,
                    "gcal_id": event_id,
                },
            )

            return event_id

        except Exception as exc:
            self._log_event(
                "timebox_creation_failed",
                {
                    "trace_id": trace_id,
                    "task_id": task.id,
                    "error": str(exc),
                },
            )
            return None

    def _fetch_events(self, calendar_id: str, days: int) -> list[GCalEvent]:
        """Fetch events from Google Calendar API.

        Parameters
        ----------
        calendar_id
            Calendar ID
        days
            Number of days to fetch

        Returns
        -------
        list[GCalEvent]
            List of events
        """
        # Placeholder for actual Google Calendar API implementation
        # In production, this would use google-api-python-client:
        #
        # from googleapiclient.discovery import build
        # service = build('calendar', 'v3', credentials=creds)
        # events_result = service.events().list(
        #     calendarId=calendar_id,
        #     timeMin=time_min.isoformat(),
        #     timeMax=time_max.isoformat(),
        #     singleEvents=True,
        #     orderBy='startTime'
        # ).execute()
        #
        # return [self._parse_gcal_event(evt) for evt in events_result.get('items', [])]

        # For now, return empty list (will be implemented with google-api-python-client)
        return []

    def _push_event(self, calendar_id: str, event: GCalEvent) -> str:
        """Push event to Google Calendar.

        Parameters
        ----------
        calendar_id
            Calendar ID
        event
            Event to push

        Returns
        -------
        str
            GCal event ID
        """
        # Placeholder for actual Google Calendar API implementation
        # In production:
        #
        # service = self._get_service()
        # event_dict = event.to_dict()
        #
        # if event.id.startswith('vault-'):
        #     # Create new event
        #     result = service.events().insert(calendarId=calendar_id, body=event_dict).execute()
        # else:
        #     # Update existing event
        #     result = service.events().update(
        #         calendarId=calendar_id,
        #         eventId=event.id,
        #         body=event_dict
        #     ).execute()
        #
        # return result['id']

        # For now, return a placeholder ID
        return event.id if not event.id.startswith("vault-") else f"gcal-{uuid.uuid4().hex[:12]}"

    def _should_push_entity(self, entity: Any) -> bool:
        """Check if entity should be pushed to GCal.

        Parameters
        ----------
        entity
            Vault entity

        Returns
        -------
        bool
            True if should push
        """
        # Check if entity has required fields
        if not entity.metadata.get("start") and not entity.metadata.get("due"):
            return False

        # Check if already synced recently
        gcal_id = entity.metadata.get("gcal_id")
        last_synced = entity.metadata.get("gcal_last_synced")

        if gcal_id and last_synced:
            try:
                last_synced_dt = datetime.fromisoformat(last_synced.replace("Z", "+00:00"))
                # Only push if updated since last sync
                return entity.updated_at > last_synced_dt
            except Exception:
                pass

        return True

    def _publish_event_received(self, event: GCalEvent, trace_id: str) -> None:
        """Publish event.received event to bus.

        Parameters
        ----------
        event
            GCal event
        trace_id
            Trace ID for correlation
        """
        if not self.event_bus:
            return

        payload = {
            "source": "gcal",
            "gcal_id": event.id,
            "summary": event.summary,
            "start": event.start.isoformat(),
            "end": event.end.isoformat(),
            "description": event.description,
            "location": event.location,
            "attendees": event.attendees,
            "all_day": event.all_day,
            "trace_id": trace_id,
        }

        self.event_bus.publish("event.received", payload, correlation_id=trace_id)

    def _log_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit structured JSONL log entry.

        Parameters
        ----------
        event_type
            Type of log event
        data
            Event data
        """
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": "adapter",
            "adapter": "gcal",
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
            if data.get("outcome") == "failure" or "error" in event_type or "failed" in event_type:
                self.logger.error(f"{event_type}: {json.dumps(data)}")
            else:
                self.logger.info(f"{event_type}: {json.dumps(data)}")


def create_gcal_adapter(
    *,
    event_bus: EventBus | None = None,
    logger: Any = None,
    credentials_path: Path | str | None = None,
    log_path: Path | str | None = None,
    **config_kwargs: Any,
) -> GCalAdapter:
    """Factory function to create Google Calendar adapter.

    Parameters
    ----------
    event_bus
        Event bus for publishing events
    logger
        Optional logger instance
    credentials_path
        Path to Google Calendar credentials JSON
    log_path
        Optional path for JSONL logs
    **config_kwargs
        Additional configuration options

    Returns
    -------
    GCalAdapter
        Configured adapter instance

    Example:
        >>> adapter = create_gcal_adapter(
        ...     event_bus=event_bus,
        ...     credentials_path=Path("credentials.json"),
        ...     log_path=Path("logs/adapters/gcal.jsonl")
        ... )
    """
    if credentials_path:
        credentials_path = Path(credentials_path) if isinstance(credentials_path, str) else credentials_path
        config_kwargs["credentials_path"] = credentials_path

    if log_path:
        log_path = Path(log_path) if isinstance(log_path, str) else log_path
        config_kwargs["log_path"] = log_path

    config = GCalAdapterConfig(**config_kwargs)

    return GCalAdapter(config, event_bus=event_bus, logger=logger)
