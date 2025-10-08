"""Quarantine for bad inputs (Phase 1, Point 6).

Persists rejected payloads and reasons for later inspection.
Every validation failure produces a quarantined artifact with timestamp + reason.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .time import format_utc_iso8601, get_current_utc

__all__ = [
    "QuarantineRecord",
    "get_quarantine_stats",
    "list_quarantined_items",
    "quarantine_invalid_entity",
]


class QuarantineRecord:
    """Record of a quarantined entity.

    Attributes
    ----------
    timestamp : str
        UTC timestamp when quarantined
    entity_type : str
        Type of entity
    reason : str
        Reason for quarantine
    errors : list[str]
        List of validation errors
    payload : dict
        Original payload
    file_path : Path
        Path to quarantined file
    """

    def __init__(
        self,
        timestamp: str,
        entity_type: str,
        reason: str,
        errors: list[str],
        payload: dict[str, Any],
        file_path: Path,
    ) -> None:
        self.timestamp = timestamp
        self.entity_type = entity_type
        self.reason = reason
        self.errors = errors
        self.payload = payload
        self.file_path = file_path


def quarantine_invalid_entity(
    entity_type: str,
    payload: dict[str, Any],
    errors: list[str],
    reason: str,
    *,
    quarantine_dir: Path | None = None,
) -> QuarantineRecord:
    """Quarantine an invalid entity (Phase 1, Point 6).

    Persists rejected payload and reasons under artifacts/quarantine/
    for later inspection.

    Parameters
    ----------
    entity_type
        Type of entity (task, note, event)
    payload
        Original entity payload (that failed validation)
    errors
        List of validation errors
    reason
        High-level reason for quarantine
    quarantine_dir
        Optional custom quarantine directory

    Returns
    -------
    QuarantineRecord
        Record of quarantined entity

    Example
    -------
    >>> payload = {"title": "", "status": "invalid"}
    >>> errors = ["Title cannot be empty", "Invalid status"]
    >>> record = quarantine_invalid_entity(
    ...     "task",
    ...     payload,
    ...     errors,
    ...     "Validation failed"
    ... )
    """
    # Get current UTC time
    now = get_current_utc()
    timestamp_str = format_utc_iso8601(now)

    # Determine quarantine directory
    if quarantine_dir is None:
        # Default: artifacts/quarantine/ in current directory
        quarantine_dir = Path("artifacts/quarantine")

    # Ensure directory exists
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename with timestamp
    # Format: {entity_type}_{timestamp}_{id_or_hash}.json
    timestamp_compact = now.strftime("%Y%m%d_%H%M%S_%f")
    entity_id = payload.get("id", "unknown")
    # Sanitize entity_id for filename
    safe_id = entity_id.replace("/", "_").replace("\\", "_")[:50]
    filename = f"{entity_type}_{timestamp_compact}_{safe_id}.json"
    file_path = quarantine_dir / filename

    # Create quarantine record
    record_data = {
        "timestamp": timestamp_str,
        "entity_type": entity_type,
        "reason": reason,
        "errors": errors,
        "payload": payload,
        "metadata": {
            "quarantined_at_utc": timestamp_str,
            "payload_size_bytes": len(json.dumps(payload)),
        },
    }

    # Write to file
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(record_data, f, indent=2, ensure_ascii=False)

    # Create and return record
    return QuarantineRecord(
        timestamp=timestamp_str,
        entity_type=entity_type,
        reason=reason,
        errors=errors,
        payload=payload,
        file_path=file_path,
    )


def list_quarantined_items(
    quarantine_dir: Path | None = None,
    *,
    entity_type: str | None = None,
    limit: int | None = None,
) -> list[QuarantineRecord]:
    """List quarantined items.

    Parameters
    ----------
    quarantine_dir
        Quarantine directory (default: artifacts/quarantine)
    entity_type
        Optional filter by entity type
    limit
        Optional maximum number of items to return

    Returns
    -------
    list[QuarantineRecord]
        List of quarantined items (sorted by timestamp, newest first)
    """
    if quarantine_dir is None:
        quarantine_dir = Path("artifacts/quarantine")

    if not quarantine_dir.exists():
        return []

    records = []

    # Find all .json files
    pattern = f"{entity_type}_*.json" if entity_type else "*.json"
    for file_path in quarantine_dir.glob(pattern):
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            record = QuarantineRecord(
                timestamp=data["timestamp"],
                entity_type=data["entity_type"],
                reason=data["reason"],
                errors=data["errors"],
                payload=data["payload"],
                file_path=file_path,
            )
            records.append(record)
        except (json.JSONDecodeError, KeyError, OSError):
            # Skip malformed files
            continue

    # Sort by timestamp (newest first)
    records.sort(key=lambda r: r.timestamp, reverse=True)

    # Apply limit
    if limit:
        records = records[:limit]

    return records


def get_quarantine_stats(quarantine_dir: Path | None = None) -> dict[str, Any]:
    """Get statistics about quarantined items.

    Parameters
    ----------
    quarantine_dir
        Quarantine directory (default: artifacts/quarantine)

    Returns
    -------
    dict[str, Any]
        Statistics including counts by entity type
    """
    if quarantine_dir is None:
        quarantine_dir = Path("artifacts/quarantine")

    if not quarantine_dir.exists():
        return {
            "total_quarantined": 0,
            "by_entity_type": {},
            "quarantine_dir": str(quarantine_dir),
        }

    stats = {
        "total_quarantined": 0,
        "by_entity_type": {},
        "quarantine_dir": str(quarantine_dir),
    }

    for file_path in quarantine_dir.glob("*.json"):
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            entity_type = data.get("entity_type", "unknown")
            stats["total_quarantined"] += 1
            stats["by_entity_type"][entity_type] = stats["by_entity_type"].get(entity_type, 0) + 1
        except (json.JSONDecodeError, OSError):
            continue

    return stats


def cleanup_old_quarantine(
    quarantine_dir: Path | None = None,
    *,
    days_old: int = 30,
) -> int:
    """Clean up old quarantined items.

    Parameters
    ----------
    quarantine_dir
        Quarantine directory (default: artifacts/quarantine)
    days_old
        Delete items older than this many days

    Returns
    -------
    int
        Number of items deleted
    """
    if quarantine_dir is None:
        quarantine_dir = Path("artifacts/quarantine")

    if not quarantine_dir.exists():
        return 0

    now = datetime.now(UTC)
    deleted_count = 0

    for file_path in quarantine_dir.glob("*.json"):
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            timestamp_str = data.get("timestamp")
            if not timestamp_str:
                continue

            # Parse timestamp
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

            # Check age
            age_days = (now - timestamp).days

            if age_days > days_old:
                file_path.unlink()
                deleted_count += 1
        except (json.JSONDecodeError, OSError, ValueError):
            continue

    return deleted_count
