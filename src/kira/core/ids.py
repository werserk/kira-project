"""ID generation and management for Vault entities (ADR-008).

Provides stable, unique identifiers following naming conventions
and preventing collisions.

ID Format (ADR-008): <kind>-YYYYMMDD-HHmm-<slug>
Example: task-20250115-1430-fix-auth-bug
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

__all__ = [
    "AliasTracker",
    "CollisionDetector",
    "EntityId",
    "generate_entity_id",
    "is_valid_entity_id",
    "parse_entity_id",
    "validate_entity_id",
    "sanitize_filename",
]


class EntityId:
    """Structured entity ID with type and unique identifier.

    Format: {type}-{unique_part}
    Examples: task-2025-01-15-urgent-meeting, note-4f3a2b1c, event-daily-standup
    """

    def __init__(self, entity_type: str, unique_part: str) -> None:
        """Initialize entity ID.

        Parameters
        ----------
        entity_type
            Type of entity (task, note, event, etc.)
        unique_part
            Unique identifier part
        """
        self.entity_type = entity_type
        self.unique_part = unique_part

    def __str__(self) -> str:
        """Return full entity ID string."""
        return f"{self.entity_type}-{self.unique_part}"

    def __repr__(self) -> str:
        """Return representation."""
        return f"EntityId(type={self.entity_type!r}, unique={self.unique_part!r})"

    def __eq__(self, other: object) -> bool:
        """Check equality."""
        if isinstance(other, EntityId):
            return self.entity_type == other.entity_type and self.unique_part == other.unique_part
        if isinstance(other, str):
            return str(self) == other
        return False

    def __hash__(self) -> int:
        """Hash for use in sets/dicts."""
        return hash((self.entity_type, self.unique_part))


def generate_entity_id(
    entity_type: str,
    *,
    title: str | None = None,
    timestamp: datetime | None = None,
    tz: ZoneInfo | str | None = None,
    custom_suffix: str | None = None,
) -> str:
    """Generate unique entity ID following ADR-008 conventions.

    Format: <kind>-YYYYMMDD-HHmm-<slug>
    Example: task-20250115-1430-fix-bug-in-auth

    Parameters
    ----------
    entity_type
        Type of entity (task, note, event, etc.)
    title
        Optional title to incorporate into ID
    timestamp
        Optional timestamp (default: now in configured timezone)
    tz
        Timezone for timestamp (default: from config, fallback to Europe/Brussels)
    custom_suffix
        Optional custom suffix instead of generated one

    Returns
    -------
    str
        Generated entity ID

    Example
    -------
    >>> generate_entity_id("task", title="Fix bug in auth")
    'task-20250115-1430-fix-bug-in-auth'
    >>> generate_entity_id("note", title="Meeting notes")
    'note-20250115-1430-meeting-notes'
    """
    if not _is_valid_entity_type(entity_type):
        raise ValueError(f"Invalid entity type: {entity_type}")

    # Get timezone
    if tz is None:
        from .time import get_default_timezone

        tz_obj = get_default_timezone()
    elif isinstance(tz, str):
        tz_obj = ZoneInfo(tz)
    else:
        tz_obj = tz

    # Get timestamp in local timezone
    if timestamp is None:
        ts = datetime.now(tz_obj)
    else:
        # Convert to specified timezone
        ts = timestamp.astimezone(tz_obj)

    # Format timestamp: YYYYMMDD-HHmm (ADR-008)
    timestamp_part = ts.strftime("%Y%m%d-%H%M")

    if custom_suffix:
        # Use custom suffix directly
        slug = _slugify(custom_suffix)
    elif title:
        # Generate slug from title
        slug = _slugify(title)[:50]  # Limit length for filesystem safety
    else:
        # Generate short unique suffix
        slug = str(uuid.uuid4()).replace("-", "")[:8]

    # Assemble ID: <kind>-YYYYMMDD-HHmm-<slug>
    if slug:
        entity_id = f"{entity_type}-{timestamp_part}-{slug}"
    else:
        # Fallback if slug is empty
        entity_id = f"{entity_type}-{timestamp_part}-{str(uuid.uuid4())[:8]}"

    # Ensure ID doesn't exceed filesystem limits (100 chars per ADR-008)
    if len(entity_id) > 100:
        # Truncate slug part
        max_slug_len = 100 - len(f"{entity_type}-{timestamp_part}-")
        slug = slug[:max_slug_len]
        entity_id = f"{entity_type}-{timestamp_part}-{slug}"

    return entity_id


def parse_entity_id(entity_id: str) -> EntityId:
    """Parse entity ID into components.

    Parameters
    ----------
    entity_id
        Entity ID string

    Returns
    -------
    EntityId
        Parsed entity ID

    Raises
    ------
    ValueError
        If ID format is invalid
    """
    if not isinstance(entity_id, str):
        raise ValueError(f"Entity ID must be string, got: {type(entity_id)}")

    parts = entity_id.split("-", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid entity ID format: {entity_id}")

    entity_type, unique_part = parts

    if not _is_valid_entity_type(entity_type):
        raise ValueError(f"Invalid entity type in ID: {entity_type}")

    if not unique_part:
        raise ValueError(f"Empty unique part in ID: {entity_id}")

    return EntityId(entity_type, unique_part)


def is_valid_entity_id(entity_id: str) -> bool:
    """Check if entity ID is valid.

    Parameters
    ----------
    entity_id
        Entity ID to validate

    Returns
    -------
    bool
        True if valid
    """
    try:
        parse_entity_id(entity_id)
        return True
    except ValueError:
        return False


def validate_entity_id(entity_id: str) -> str:
    """Validate entity ID and return normalized version.

    Parameters
    ----------
    entity_id
        Entity ID to validate

    Returns
    -------
    str
        Normalized entity ID

    Raises
    ------
    ValueError
        If ID is invalid
    """
    parsed = parse_entity_id(entity_id)
    return str(parsed)


def _is_valid_entity_type_format(entity_type: str) -> bool:
    """Check if entity type format is valid.

    Parameters
    ----------
    entity_type
        Entity type to check

    Returns
    -------
    bool
        True if format is valid
    """
    if not entity_type:
        return False

    # Must be lowercase letters/numbers, 2-20 chars
    return bool(re.match(r"^[a-z][a-z0-9]{1,19}$", entity_type))


def _is_valid_entity_type(entity_type: str) -> bool:
    """Check if entity type is valid (both format and registered).

    Parameters
    ----------
    entity_type
        Entity type to check

    Returns
    -------
    bool
        True if valid
    """
    if not entity_type:
        return False

    # Must be in known entity types and match format
    if entity_type not in KNOWN_ENTITY_TYPES:
        return False

    return _is_valid_entity_type_format(entity_type)


def _slugify(text: str) -> str:
    """Convert text to URL-safe slug.

    Parameters
    ----------
    text
        Text to slugify

    Returns
    -------
    str
        Slugified text
    """
    if not text:
        return ""

    # Convert to lowercase
    slug = text.lower()

    # Replace spaces and special chars with hyphens
    slug = re.sub(r"[^a-z0-9]+", "-", slug)

    # Remove leading/trailing hyphens
    slug = slug.strip("-")

    # Collapse multiple hyphens
    slug = re.sub(r"-+", "-", slug)

    return slug


def generate_short_id(length: int = 8) -> str:
    """Generate short random ID.

    Parameters
    ----------
    length
        Length of ID (default: 8)

    Returns
    -------
    str
        Short random ID
    """
    return str(uuid.uuid4()).replace("-", "")[:length]


def generate_timestamp_id() -> str:
    """Generate timestamp-based ID.

    Returns
    -------
    str
        Timestamp ID (YYYYMMDDTHHMMSSZ format)
    """
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


# Registry of known entity types
KNOWN_ENTITY_TYPES = {
    "task",
    "note",
    "event",
    "meeting",
    "project",
    "contact",
    "resource",
    "template",
    "reference",
    "idea",
}


def get_known_entity_types() -> set[str]:
    """Get set of known entity types.

    Returns
    -------
    set[str]
        Known entity types
    """
    return KNOWN_ENTITY_TYPES.copy()


def register_entity_type(entity_type: str) -> None:
    """Register new entity type.

    Parameters
    ----------
    entity_type
        Entity type to register

    Raises
    ------
    ValueError
        If entity type is invalid
    """
    if not _is_valid_entity_type_format(entity_type):
        raise ValueError(f"Invalid entity type: {entity_type}")

    KNOWN_ENTITY_TYPES.add(entity_type)


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe filesystem use.

    Parameters
    ----------
    filename
        Filename to sanitize

    Returns
    -------
    str
        Sanitized filename
    """
    # Remove/replace unsafe characters
    safe = re.sub(r'[<>:"/\\|?*]', "-", filename)

    # Remove control characters
    safe = re.sub(r"[\x00-\x1f\x7f]", "", safe)

    # Collapse multiple hyphens
    safe = re.sub(r"-+", "-", safe)

    # Trim hyphens from ends
    safe = safe.strip("-")

    # Ensure not empty
    if not safe:
        safe = "unnamed"

    # Limit length
    if len(safe) > 200:
        safe = safe[:200]

    return safe


class CollisionDetector:
    """Detects and prevents ID collisions (ADR-008)."""

    def __init__(self) -> None:
        """Initialize collision detector."""
        self._used_ids: set[str] = set()
        self._id_counts: dict[str, int] = {}

    def register_id(self, entity_id: str) -> None:
        """Register ID as used.

        Parameters
        ----------
        entity_id
            Entity ID to register
        """
        self._used_ids.add(entity_id)

        # Track base ID for collision detection
        base = self._get_base_id(entity_id)
        self._id_counts[base] = self._id_counts.get(base, 0) + 1

    def is_collision(self, entity_id: str) -> bool:
        """Check if ID collides with existing IDs.

        Parameters
        ----------
        entity_id
            Entity ID to check

        Returns
        -------
        bool
            True if collision detected
        """
        return entity_id in self._used_ids

    def generate_unique_id(
        self,
        entity_type: str,
        title: str,
        timestamp: datetime | None = None,
        tz: ZoneInfo | str | None = None,
    ) -> str:
        """Generate unique ID, adding suffix if collision detected.

        Parameters
        ----------
        entity_type
            Entity type
        title
            Entity title
        timestamp
            Optional timestamp
        tz
            Optional timezone

        Returns
        -------
        str
            Unique entity ID
        """
        # Generate base ID
        base_id = generate_entity_id(entity_type, title=title, timestamp=timestamp, tz=tz)

        if not self.is_collision(base_id):
            return base_id

        # Collision detected - add numeric suffix
        attempt = 2
        while True:
            candidate_id = f"{base_id}-{attempt}"

            if not self.is_collision(candidate_id):
                return candidate_id

            attempt += 1

            if attempt > 100:
                # Safety: fall back to UUID
                return f"{base_id}-{str(uuid.uuid4())[:8]}"

    def _get_base_id(self, entity_id: str) -> str:
        """Get base ID without numeric suffix.

        Parameters
        ----------
        entity_id
            Entity ID

        Returns
        -------
        str
            Base ID
        """
        # Remove numeric suffix if present
        match = re.match(r"^(.+)-(\d+)$", entity_id)
        if match:
            return match.group(1)
        return entity_id

    def get_collision_count(self, base_id: str) -> int:
        """Get number of IDs based on this base.

        Parameters
        ----------
        base_id
            Base entity ID

        Returns
        -------
        int
            Collision count
        """
        return self._id_counts.get(base_id, 0)


class AliasTracker:
    """Tracks entity ID aliases for migration (ADR-008).

    Maintains mapping of old IDs to new IDs for backward compatibility
    during migration.
    """

    def __init__(self, aliases_file: Path | None = None) -> None:
        """Initialize alias tracker.

        Parameters
        ----------
        aliases_file
            Optional file to persist aliases
        """
        self.aliases_file = aliases_file
        self._aliases: dict[str, str] = {}  # old_id -> new_id
        self._reverse_aliases: dict[str, list[str]] = {}  # new_id -> [old_ids]

        if aliases_file and aliases_file.exists():
            self._load_aliases()

    def add_alias(self, old_id: str, new_id: str) -> None:
        """Add ID alias mapping.

        Parameters
        ----------
        old_id
            Old entity ID
        new_id
            New entity ID
        """
        self._aliases[old_id] = new_id

        if new_id not in self._reverse_aliases:
            self._reverse_aliases[new_id] = []

        if old_id not in self._reverse_aliases[new_id]:
            self._reverse_aliases[new_id].append(old_id)

    def resolve_id(self, entity_id: str) -> str:
        """Resolve ID to current ID (follow aliases).

        Parameters
        ----------
        entity_id
            Entity ID (may be old or current)

        Returns
        -------
        str
            Current entity ID
        """
        return self._aliases.get(entity_id, entity_id)

    def get_aliases(self, entity_id: str) -> list[str]:
        """Get all aliases for entity ID.

        Parameters
        ----------
        entity_id
            Current entity ID

        Returns
        -------
        list[str]
            List of old IDs (aliases)
        """
        return self._reverse_aliases.get(entity_id, [])

    def save_aliases(self) -> None:
        """Save aliases to file."""
        if not self.aliases_file:
            return

        import json

        data = {
            "aliases": self._aliases,
            "reverse": self._reverse_aliases,
        }

        self.aliases_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.aliases_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load_aliases(self) -> None:
        """Load aliases from file."""
        import json

        if not self.aliases_file:
            return

        try:
            with open(self.aliases_file, encoding="utf-8") as f:
                data = json.load(f)

            self._aliases = data.get("aliases", {})
            self._reverse_aliases = data.get("reverse", {})

        except Exception:
            # If loading fails, start with empty aliases
            self._aliases = {}
            self._reverse_aliases = {}
