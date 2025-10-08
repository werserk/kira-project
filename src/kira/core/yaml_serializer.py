"""Deterministic YAML serialization for front-matter (Phase 0, Point 2).

This module provides deterministic serialization with:
- Fixed key ordering for consistent output
- ISO-8601 UTC timestamps
- Consistent quoting and formatting
- Round-trip guarantee: serialize → parse → serialize yields identical output
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

import yaml

__all__ = [
    "serialize_frontmatter",
    "parse_frontmatter",
    "normalize_timestamps_to_utc",
    "get_canonical_key_order",
]


# Canonical key ordering for deterministic output (Phase 0, Point 2)
# Keys appear in this order; unlisted keys appear alphabetically at the end
CANONICAL_KEY_ORDER = [
    # Core identity
    "id",
    "title",
    # Entity metadata
    "type",
    "status",
    "state",
    "priority",
    # Timestamps (always UTC ISO-8601)
    "created",
    "updated",
    "due_date",
    "start_time",
    "end_time",
    "done_ts",
    "start_ts",
    # Classification
    "tags",
    "category",
    # Relationships
    "relates_to",
    "depends_on",
    "blocks",
    "parent",
    "links",
    # Optional fields
    "description",
    "assignee",
    "estimate",
    "location",
    "attendees",
    "calendar",
    "source",
    "reopen_reason",
    # Kira sync metadata
    "x-kira",
]


def get_canonical_key_order(keys: list[str]) -> list[str]:
    """Get keys in canonical order.

    Parameters
    ----------
    keys
        Keys to order

    Returns
    -------
    list[str]
        Keys in canonical order
    """
    # Separate known and unknown keys
    known_keys = []
    unknown_keys = []

    for key in keys:
        if key in CANONICAL_KEY_ORDER:
            known_keys.append(key)
        else:
            unknown_keys.append(key)

    # Sort known keys by canonical order
    known_keys.sort(key=lambda k: CANONICAL_KEY_ORDER.index(k))

    # Sort unknown keys alphabetically
    unknown_keys.sort()

    return known_keys + unknown_keys


def normalize_timestamps_to_utc(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize timestamp fields to ISO-8601 UTC format.

    Phase 1, Point 3: Ensures all timestamps are in ISO-8601 UTC format,
    including nested timestamps (e.g., in x-kira metadata).

    Parameters
    ----------
    data
        Data with potential timestamp fields

    Returns
    -------
    dict[str, Any]
        Data with normalized timestamps (deep copy)
    """
    result = {}

    # Timestamp fields that should be normalized (including nested ones like last_write_ts)
    timestamp_fields = {
        "created",
        "updated",
        "due_date",
        "start_time",
        "end_time",
        "done_ts",
        "start_ts",
        "created_ts",
        "updated_ts",
        "due_ts",
        "last_write_ts",  # For x-kira metadata
    }

    for key, value in data.items():
        if key in timestamp_fields and value is not None:
            if isinstance(value, datetime):
                # Convert datetime to ISO-8601 UTC
                if value.tzinfo is None:
                    # Naive datetime - assume UTC
                    value = value.replace(tzinfo=timezone.utc)
                else:
                    # Convert to UTC
                    value = value.astimezone(timezone.utc)

                result[key] = value.isoformat()
            elif isinstance(value, str):
                # Ensure string timestamps are in ISO-8601 UTC format
                try:
                    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    else:
                        dt = dt.astimezone(timezone.utc)
                    result[key] = dt.isoformat()
                except (ValueError, AttributeError):
                    # Keep as-is if can't parse
                    result[key] = value
            else:
                result[key] = value
        # Recursively handle nested dicts (like x-kira)
        elif isinstance(value, dict):
            result[key] = normalize_timestamps_to_utc(value)
        elif isinstance(value, list):
            # Copy lists as-is
            result[key] = value.copy() if hasattr(value, "copy") else list(value)
        else:
            result[key] = value

    return result


def serialize_frontmatter(data: dict[str, Any], *, normalize_timestamps: bool = True) -> str:
    """Serialize frontmatter to deterministic YAML.

    Produces consistent output with:
    - Fixed key ordering per CANONICAL_KEY_ORDER
    - ISO-8601 UTC timestamps
    - Consistent quoting and formatting

    Parameters
    ----------
    data
        Frontmatter data
    normalize_timestamps
        Normalize timestamps to UTC

    Returns
    -------
    str
        YAML string
    """
    # Normalize timestamps to UTC
    if normalize_timestamps:
        data = normalize_timestamps_to_utc(data)

    # Order keys canonically
    # Use OrderedDict to preserve order during iteration, then convert to dict
    # for YAML serialization (avoids Python-specific tags)
    key_order = get_canonical_key_order(list(data.keys()))

    # Build ordered dict as regular dict to avoid Python-specific YAML tags
    # We'll write keys in order manually
    result_lines = []

    for key in key_order:
        if key in data:
            value = data[key]

            # Serialize each key-value pair
            if isinstance(value, dict):
                # Nested dict (like x-kira)
                result_lines.append(f"{key}:")
                nested_yaml = yaml.dump(value, default_flow_style=False, allow_unicode=True, sort_keys=False)
                # Indent nested YAML
                for line in nested_yaml.rstrip().split("\n"):
                    result_lines.append(f"  {line}")
            elif isinstance(value, list):
                # List (Phase 1, Point 3: proper escaping for list items)
                if not value:
                    result_lines.append(f"{key}: []")
                else:
                    result_lines.append(f"{key}:")
                    for item in value:
                        # Proper YAML list serialization
                        if isinstance(item, str):
                            # Handle special characters in strings
                            # Wiki-style links [[...]] and other special chars need quoting
                            needs_quoting = (
                                any(c in item for c in [":", "#", "|", ">", "&", "*", "!", "%", "@"])
                                or "\n" in item
                                or item.startswith((" ", "-", "[", "{"))
                                or item.startswith("[[")
                            )
                            if needs_quoting:
                                # Use quoted string - remove document separators
                                dumped = yaml.dump(item, default_flow_style=True).strip()
                                # Remove document start/end markers
                                dumped = dumped.replace("...", "").replace("---", "").strip()
                                result_lines.append(f"  - {dumped}")
                            else:
                                result_lines.append(f"  - {item}")
                        else:
                            dumped = yaml.dump(item, default_flow_style=True).strip()
                            dumped = dumped.replace("...", "").replace("---", "").strip()
                            result_lines.append(f"  - {dumped}")
            elif value is None:
                result_lines.append(f"{key}: null")
            elif isinstance(value, bool):
                result_lines.append(f"{key}: {str(value).lower()}")
            elif isinstance(value, (int, float)):
                result_lines.append(f"{key}: {value}")
            elif isinstance(value, str):
                # Handle special characters in strings (Phase 1, Point 3: proper escaping)
                # Strings starting with [ or { need quoting to avoid YAML flow collection parsing
                needs_quoting = (
                    any(c in value for c in [":", "#", "|", ">", "&", "*", "!", "%", "@"])
                    or "\n" in value
                    or value.startswith((" ", "-", "[", "{"))
                    or value.startswith("[[")  # Wiki-style links need quoting
                )
                if needs_quoting:
                    # Use YAML's dump for proper quoting/escaping - remove document separators
                    dumped = yaml.dump(value, default_flow_style=True, allow_unicode=True).strip()
                    dumped = dumped.replace("...", "").replace("---", "").strip()
                    result_lines.append(f"{key}: {dumped}")
                else:
                    result_lines.append(f"{key}: {value}")
            else:
                # Fallback: use YAML dump for the value - remove document separators
                dumped = yaml.dump(value, default_flow_style=True, allow_unicode=True).strip()
                dumped = dumped.replace("...", "").replace("---", "").strip()
                result_lines.append(f"{key}: {dumped}")

    return "\n".join(result_lines)


def parse_frontmatter(yaml_str: str) -> dict[str, Any]:
    """Parse YAML frontmatter.

    Parameters
    ----------
    yaml_str
        YAML string

    Returns
    -------
    dict[str, Any]
        Parsed data

    Raises
    ------
    ValueError
        If parsing fails
    """
    try:
        data = yaml.safe_load(yaml_str)

        if data is None:
            return {}

        if not isinstance(data, dict):
            raise ValueError(f"Frontmatter must be a dictionary, got: {type(data)}")

        return data
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML frontmatter: {exc}") from exc


def validate_strict_schema(entity_type: str, data: dict[str, Any]) -> list[str]:
    """Validate entity against strict schema requirements (Phase 0, Point 2).

    Required keys: uid (id), title, created_ts (created), updated_ts (updated)
    Required for tasks/projects: state/status
    Optional keys: tags[]

    Parameters
    ----------
    entity_type
        Type of entity
    data
        Entity data

    Returns
    -------
    list[str]
        List of validation errors (empty if valid)
    """
    errors = []

    # Check required keys (common to all entities)
    required_keys = {
        "id": ["id", "uid"],  # Either 'id' or 'uid'
        "title": ["title"],
        "created": ["created", "created_ts"],
        "updated": ["updated", "updated_ts"],
    }

    for field_name, possible_keys in required_keys.items():
        if not any(key in data for key in possible_keys):
            errors.append(f"Missing required field: {field_name} (tried: {', '.join(possible_keys)})")

    # Check status/state only for tasks and projects
    if entity_type in ["task", "project"]:
        if not any(key in data for key in ["state", "status"]):
            errors.append("Missing required field: state (tried: state, status)")

    # Ensure tags is a list if present
    tags_key = None
    for key in ["tags"]:
        if key in data:
            tags_key = key
            break

    if tags_key and data[tags_key] is not None:
        if not isinstance(data[tags_key], list):
            errors.append(f"Field '{tags_key}' must be a list, got: {type(data[tags_key])}")

    # Ensure timestamps are ISO-8601 UTC if present
    timestamp_fields = ["created", "updated", "due_date", "start_time", "end_time"]
    for field in timestamp_fields:
        if field in data and data[field]:
            value = data[field]
            if isinstance(value, str):
                try:
                    datetime.fromisoformat(value.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    errors.append(f"Field '{field}' is not valid ISO-8601: {value}")

    return errors
