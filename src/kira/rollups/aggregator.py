"""Entity rollup aggregation (Phase 7, Point 22).

Aggregate entities by time windows with validation filtering.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from ..core.time import parse_utc_iso8601
from ..core.validation import validate_entity
from .time_windows import TimeWindow, compute_boundaries_utc

if TYPE_CHECKING:
    from datetime import datetime

    from ..core.host import HostAPI

__all__ = [
    "RollupSummary",
    "aggregate_entities",
    "compute_rollup",
]


class RollupSummary:
    """Summary of entities in a time window.

    Attributes
    ----------
    window_type : str
        Type of window ("day", "week", "month")
    start_utc : str
        Window start (ISO-8601 UTC)
    end_utc : str
        Window end (ISO-8601 UTC)
    local_date : str
        Representative local date
    timezone : str
        Timezone used
    entity_counts : dict
        Count by entity type
    validated_count : int
        Number of validated entities
    total_count : int
        Total entities in window
    entities : list
        List of entity IDs in window
    """

    def __init__(
        self,
        window_type: str,
        start_utc: str,
        end_utc: str,
        local_date: str,
        timezone: str,
    ) -> None:
        self.window_type = window_type
        self.start_utc = start_utc
        self.end_utc = end_utc
        self.local_date = local_date
        self.timezone = timezone

        self.entity_counts: dict[str, int] = defaultdict(int)
        self.validated_count = 0
        self.total_count = 0
        self.entities: list[str] = []

    def add_entity(self, entity_id: str, entity_type: str, is_valid: bool) -> None:
        """Add entity to summary."""
        self.entities.append(entity_id)
        self.entity_counts[entity_type] += 1
        self.total_count += 1
        if is_valid:
            self.validated_count += 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "window_type": self.window_type,
            "start_utc": self.start_utc,
            "end_utc": self.end_utc,
            "local_date": self.local_date,
            "timezone": self.timezone,
            "entity_counts": dict(self.entity_counts),
            "validated_count": self.validated_count,
            "total_count": self.total_count,
            "entity_count_by_type": dict(self.entity_counts),
        }


def is_entity_in_window(
    entity: Any,
    start_utc: str,
    end_utc: str,
) -> bool:
    """Check if entity falls within time window.

    Parameters
    ----------
    entity
        Entity to check
    start_utc
        Window start (ISO-8601 UTC)
    end_utc
        Window end (ISO-8601 UTC)

    Returns
    -------
    bool
        True if entity is in window
    """
    # Try to get entity timestamp
    entity_ts_str = None

    # Try created_at/updated_at attributes first
    if hasattr(entity, "created_at"):
        entity_ts_str = entity.created_at.isoformat()
    elif hasattr(entity, "updated_at"):
        entity_ts_str = entity.updated_at.isoformat()
    # Try metadata dict (keys: "created", "updated", "created_ts", "updated_ts")
    elif hasattr(entity, "metadata"):
        entity_ts_str = (
            entity.metadata.get("created")
            or entity.metadata.get("updated")
            or entity.metadata.get("created_ts")
            or entity.metadata.get("updated_ts")
        )

    if not entity_ts_str:
        return False

    try:
        entity_ts = parse_utc_iso8601(entity_ts_str)
        start_dt = parse_utc_iso8601(start_utc)
        end_dt = parse_utc_iso8601(end_utc)

        # Check if entity is in [start, end) range
        return start_dt <= entity_ts < end_dt
    except (ValueError, AttributeError):
        return False


def compute_rollup(
    host_api: HostAPI,
    local_date: datetime,
    window: TimeWindow,
    timezone_str: str = "UTC",
    entity_types: list[str] | None = None,
    validated_only: bool = True,
) -> RollupSummary:
    """Compute rollup for a time window (Phase 7, Point 22).

    DoD: Include only validated entities.
    DoD: Weeks with DST changes yield correct boundaries.

    Parameters
    ----------
    host_api
        Host API for accessing entities
    local_date
        Date in local timezone
    window
        Type of window ("day", "week", "month")
    timezone_str
        Timezone name
    entity_types
        List of entity types to include (None = all)
    validated_only
        If True, include only validated entities

    Returns
    -------
    RollupSummary
        Aggregated summary
    """
    # Compute UTC boundaries from local time
    start_utc, end_utc = compute_boundaries_utc(local_date, window, timezone_str)

    # Create summary
    summary = RollupSummary(
        window_type=window,
        start_utc=start_utc,
        end_utc=end_utc,
        local_date=local_date.strftime("%Y-%m-%d"),
        timezone=timezone_str,
    )

    # Get entity types to process
    types_to_process = entity_types or ["task", "note", "event"]

    # Aggregate entities
    for entity_type in types_to_process:
        try:
            entities = list(host_api.list_entities(entity_type))

            for entity in entities:
                # Check if in time window
                if not is_entity_in_window(entity, start_utc, end_utc):
                    continue

                # Validate if required
                is_valid = True
                if validated_only:
                    try:
                        validation_result = validate_entity(entity_type, entity.metadata)
                        is_valid = validation_result.valid
                    except Exception:
                        is_valid = False

                # Add to summary (only if valid when validated_only=True)
                if not validated_only or is_valid:
                    summary.add_entity(entity.id, entity_type, is_valid)

        except Exception:
            # Skip entity types that don't exist or have errors
            continue

    return summary


def aggregate_entities(
    host_api: HostAPI,
    date_range: list[datetime],
    window: TimeWindow,
    timezone_str: str = "UTC",
) -> list[RollupSummary]:
    """Aggregate entities across multiple time windows.

    Parameters
    ----------
    host_api
        Host API for accessing entities
    date_range
        List of dates to compute rollups for
    window
        Type of window
    timezone_str
        Timezone name

    Returns
    -------
    list[RollupSummary]
        List of summaries, one per date
    """
    summaries = []

    for date in date_range:
        summary = compute_rollup(host_api, date, window, timezone_str)
        summaries.append(summary)

    return summaries
