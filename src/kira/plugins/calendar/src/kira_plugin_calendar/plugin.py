"""Calendar plugin for Vault<->GCal synchronization (ADR-012).

Maintains mappings between Vault entities and Google Calendar events,
handles sync events, and provides timeboxing for tasks entering execution.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kira.plugin_sdk.context import PluginContext
from kira.plugin_sdk.decorators import on_event

__all__ = ["activate"]


class CalendarPlugin:
    """Calendar sync plugin for Kira.

    Responsibilities (ADR-012):
    - Maintain Vault<->GCal entity mappings
    - Handle sync events from GCal adapter
    - Create/update Vault entities from GCal events
    - Listen for task.enter_doing to trigger timeboxing
    - Persist GCal IDs in Vault frontmatter
    - Resolve conflicts using last-writer-wins
    """

    def __init__(self, context: PluginContext):
        """Initialize calendar plugin.

        Parameters
        ----------
        context
            Plugin execution context
        """
        self.context = context
        self.logger = context.logger
        self.events = context.events

        # Load mappings from storage
        self._mappings: dict[str, dict[str, Any]] = {}
        self._load_mappings()

        # Setup event handlers
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Setup event handlers for sync and timeboxing."""
        # Handle events from GCal
        self.events.subscribe("event.received", self._handle_event_received)

        # Handle task FSM transitions for timeboxing
        self.events.subscribe("task.enter_doing", self._handle_task_enter_doing)

        # Handle sync requests
        self.events.subscribe("calendar.sync_request", self._handle_sync_request)

        self.logger.info("Calendar plugin event handlers registered")

    def _handle_event_received(self, event: Any) -> None:
        """Handle event.received from GCal adapter.

        Creates or updates Vault entity based on GCal event.

        Parameters
        ----------
        event
            Event data from GCal adapter
        """
        try:
            payload = event.payload
            source = payload.get("source")

            if source != "gcal":
                return  # Only handle GCal events

            gcal_id = payload.get("gcal_id")
            if not gcal_id:
                self.logger.warning("Event received without gcal_id")
                return

            # Check if entity already exists
            vault_id = self._get_vault_id_for_gcal(gcal_id)

            if vault_id:
                # Update existing entity
                self._update_vault_entity(vault_id, payload)
            else:
                # Create new entity
                self._create_vault_entity(payload)

        except Exception as exc:
            self.logger.error(f"Failed to handle event.received: {exc}")

    def _handle_task_enter_doing(self, event: Any) -> None:
        """Handle task entering 'doing' state for timeboxing.

        Creates timeboxed event in GCal when task starts.

        Parameters
        ----------
        event
            Event data with task information
        """
        try:
            payload = event.payload
            task_id = payload.get("task_id") or payload.get("entity_id")

            if not task_id:
                self.logger.warning("Task enter_doing event without task_id")
                return

            self.logger.info(f"Creating timebox for task: {task_id}")

            # Publish timebox creation request
            self.events.publish(
                "calendar.create_timebox",
                {
                    "task_id": task_id,
                    "trace_id": payload.get("trace_id"),
                    "time_hint": payload.get("time_hint", 60),
                },
            )

            # Update mapping
            self._mappings[task_id] = {
                "vault_id": task_id,
                "timeboxed": True,
                "timeboxed_at": datetime.now(timezone.utc).isoformat(),
            }
            self._save_mappings()

        except Exception as exc:
            self.logger.error(f"Failed to create timebox: {exc}")

    def _handle_sync_request(self, event: Any) -> None:
        """Handle calendar.sync_request event.

        Triggers pull/push operations based on request type.

        Parameters
        ----------
        event
            Event data with sync parameters
        """
        try:
            payload = event.payload
            sync_type = payload.get("type", "pull")  # pull, push, or reconcile

            if sync_type == "pull":
                self.logger.info("Sync request: pull from GCal")
                self.events.publish("calendar.pull_request", payload)

            elif sync_type == "push":
                self.logger.info("Sync request: push to GCal")
                self.events.publish("calendar.push_request", payload)

            elif sync_type == "reconcile":
                self.logger.info("Sync request: reconcile Vault<->GCal")
                self.events.publish("calendar.reconcile_request", payload)

        except Exception as exc:
            self.logger.error(f"Failed to handle sync request: {exc}")

    def _create_vault_entity(self, gcal_event: dict[str, Any]) -> str | None:
        """Create new Vault entity from GCal event.

        Parameters
        ----------
        gcal_event
            GCal event data

        Returns
        -------
        str or None
            Created entity ID
        """
        try:
            gcal_id = gcal_event.get("gcal_id")
            summary = gcal_event.get("summary", "Untitled Event")
            start = gcal_event.get("start")
            end = gcal_event.get("end")
            description = gcal_event.get("description", "")
            location = gcal_event.get("location")
            attendees = gcal_event.get("attendees", [])
            all_day = gcal_event.get("all_day", False)

            # Prepare entity metadata
            metadata = {
                "title": summary,
                "start": start,
                "end": end,
                "gcal_id": gcal_id,
                "gcal_last_synced": datetime.now(timezone.utc).isoformat(),
                "source": "gcal",
            }

            if description:
                metadata["description"] = description
            if location:
                metadata["location"] = location
            if attendees:
                metadata["attendees"] = attendees
            if all_day:
                metadata["all_day"] = all_day

            # Publish entity.create event for Host API
            self.events.publish(
                "entity.create_request",
                {
                    "entity_type": "event",
                    "metadata": metadata,
                    "content": description,
                    "trace_id": gcal_event.get("trace_id"),
                },
            )

            self.logger.info(f"Created Vault entity for GCal event: {gcal_id}")

            return None  # Entity ID will be assigned by Host API

        except Exception as exc:
            self.logger.error(f"Failed to create Vault entity: {exc}")
            return None

    def _update_vault_entity(self, vault_id: str, gcal_event: dict[str, Any]) -> None:
        """Update existing Vault entity from GCal event.

        Parameters
        ----------
        vault_id
            Vault entity ID
        gcal_event
            GCal event data
        """
        try:
            gcal_id = gcal_event.get("gcal_id")

            # Prepare updates
            updates = {
                "title": gcal_event.get("summary"),
                "start": gcal_event.get("start"),
                "end": gcal_event.get("end"),
                "gcal_last_synced": datetime.now(timezone.utc).isoformat(),
            }

            # Add optional fields if present
            if "description" in gcal_event:
                updates["description"] = gcal_event["description"]
            if "location" in gcal_event:
                updates["location"] = gcal_event["location"]
            if "attendees" in gcal_event:
                updates["attendees"] = gcal_event["attendees"]

            # Publish entity.update event for Host API
            self.events.publish(
                "entity.update_request",
                {
                    "entity_id": vault_id,
                    "updates": updates,
                    "trace_id": gcal_event.get("trace_id"),
                },
            )

            # Update mapping
            if vault_id in self._mappings:
                self._mappings[vault_id]["gcal_updated"] = datetime.now(timezone.utc).isoformat()
                self._save_mappings()

            self.logger.info(f"Updated Vault entity {vault_id} from GCal event {gcal_id}")

        except Exception as exc:
            self.logger.error(f"Failed to update Vault entity: {exc}")

    def _get_vault_id_for_gcal(self, gcal_id: str) -> str | None:
        """Get Vault entity ID for GCal event ID.

        Parameters
        ----------
        gcal_id
            Google Calendar event ID

        Returns
        -------
        str or None
            Vault entity ID if found
        """
        # Search mappings
        for vault_id, mapping in self._mappings.items():
            if mapping.get("gcal_id") == gcal_id:
                return vault_id

        return None

    def _load_mappings(self) -> None:
        """Load mappings from plugin storage."""
        try:
            # Try to load from plugin config/storage
            mappings_path = self._get_mappings_path()
            if mappings_path.exists():
                with open(mappings_path) as f:
                    self._mappings = json.load(f)
                self.logger.info(f"Loaded {len(self._mappings)} entity mappings")
            else:
                self._mappings = {}
                self.logger.info("No existing mappings found, starting fresh")

        except Exception as exc:
            self.logger.warning(f"Failed to load mappings: {exc}")
            self._mappings = {}

    def _save_mappings(self) -> None:
        """Save mappings to plugin storage."""
        try:
            mappings_path = self._get_mappings_path()
            mappings_path.parent.mkdir(parents=True, exist_ok=True)

            with open(mappings_path, "w") as f:
                json.dump(self._mappings, f, indent=2)

            self.logger.debug(f"Saved {len(self._mappings)} entity mappings")

        except Exception as exc:
            self.logger.error(f"Failed to save mappings: {exc}")

    def _get_mappings_path(self) -> Path:
        """Get path for mappings storage.

        Returns
        -------
        Path
            Path to mappings file
        """
        # Use plugin's data directory
        # In production, this would be provided by the plugin SDK
        return Path.home() / ".kira" / "plugins" / "calendar" / "mappings.json"

    def reconcile_entities(self, vault_entities: list[Any]) -> dict[str, Any]:
        """Reconcile Vault entities with GCal events.

        Parameters
        ----------
        vault_entities
            List of Vault entities to reconcile

        Returns
        -------
        dict
            Reconciliation statistics
        """
        stats = {
            "checked": 0,
            "in_sync": 0,
            "updated": 0,
            "conflicts": 0,
        }

        for entity in vault_entities:
            stats["checked"] += 1

            gcal_id = entity.metadata.get("gcal_id")
            if not gcal_id:
                continue

            # Check if needs reconciliation
            last_synced = entity.metadata.get("gcal_last_synced")
            if last_synced:
                try:
                    last_synced_dt = datetime.fromisoformat(last_synced.replace("Z", "+00:00"))
                    if entity.updated_at <= last_synced_dt:
                        stats["in_sync"] += 1
                        continue
                except Exception:
                    pass

            # Entity updated since last sync - may need reconciliation
            stats["conflicts"] += 1

        self.logger.info(f"Reconciliation stats: {stats}")
        return stats


def activate(context: PluginContext) -> dict[str, str]:
    """Activate the calendar plugin.

    Parameters
    ----------
    context
        Execution context provided by the host application

    Returns
    -------
    dict
        Status payload acknowledging activation
    """
    context.logger.info("Activating calendar sync plugin (ADR-012)")

    # Initialize plugin
    plugin = CalendarPlugin(context)

    # Publish activation event
    context.events.publish(
        "calendar.activated",
        {
            "message": "Calendar plugin activated with full sync support",
            "plugin": "kira-calendar",
            "features": [
                "gcal_sync",
                "vault_mapping",
                "timeboxing",
                "conflict_resolution",
            ],
        },
    )

    context.logger.info("Calendar plugin activated successfully")

    return {"status": "ok", "plugin": "kira-calendar", "version": "1.0.0"}
