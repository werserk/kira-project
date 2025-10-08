"""Domain validation for entities (Phase 1, Point 5).

Comprehensive validation before entities are written to Vault.
Invalid entities never touch disk; errors are surfaced to callers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .yaml_serializer import validate_strict_schema

__all__ = [
    "ValidationError",
    "ValidationResult",
    "validate_entity",
    "validate_event_specific",
    "validate_note_specific",
    "validate_task_specific",
]


class ValidationError(Exception):
    """Raised when entity validation fails (Phase 1, Point 5).

    Invalid entities never touch disk.
    """

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or []


class ValidationResult:
    """Result of entity validation."""

    def __init__(self, valid: bool, errors: list[str] | None = None) -> None:
        self.valid = valid
        self.errors = errors or []

    def __bool__(self) -> bool:
        """Boolean conversion."""
        return self.valid

    def __str__(self) -> str:
        """String representation."""
        if self.valid:
            return "Valid"
        return f"Invalid: {'; '.join(self.errors)}"

    def add_error(self, error: str) -> None:
        """Add validation error."""
        self.errors.append(error)
        self.valid = False


def validate_entity(entity_type: str, data: dict[str, Any]) -> ValidationResult:
    """Validate entity against all rules (Phase 1, Point 5).

    Runs comprehensive validation:
    1. Strict schema validation (required keys)
    2. Entity-specific business rules
    3. Data integrity checks

    Invalid entities never touch disk.

    Parameters
    ----------
    entity_type
        Type of entity (task, note, event)
    data
        Entity metadata

    Returns
    -------
    ValidationResult
        Validation result with collected errors
    """
    result = ValidationResult(valid=True)

    # 1. Strict schema validation (Phase 0, Point 2)
    schema_errors = validate_strict_schema(entity_type, data)
    for error in schema_errors:
        result.add_error(f"Schema: {error}")

    # 2. Entity-specific validation
    if entity_type == "task":
        task_errors = validate_task_specific(data)
        for error in task_errors:
            result.add_error(f"Task: {error}")
    elif entity_type == "note":
        note_errors = validate_note_specific(data)
        for error in note_errors:
            result.add_error(f"Note: {error}")
    elif entity_type == "event":
        event_errors = validate_event_specific(data)
        for error in event_errors:
            result.add_error(f"Event: {error}")

    # 3. Common validation rules
    common_errors = _validate_common_rules(data)
    for error in common_errors:
        result.add_error(f"Common: {error}")

    return result


def validate_task_specific(data: dict[str, Any]) -> list[str]:
    """Validate task-specific business rules.

    Parameters
    ----------
    data
        Task metadata

    Returns
    -------
    list[str]
        List of validation errors
    """
    errors = []

    # Status must be valid
    valid_statuses = ["todo", "doing", "review", "done", "blocked"]
    status = data.get("status") or data.get("state")
    if status and status not in valid_statuses:
        errors.append(f"Invalid status: {status}. Must be one of: {', '.join(valid_statuses)}")

    # Priority must be valid if present
    valid_priorities = ["low", "medium", "high", "urgent"]
    priority = data.get("priority")
    if priority and priority not in valid_priorities:
        errors.append(f"Invalid priority: {priority}. Must be one of: {', '.join(valid_priorities)}")

    # If blocked, must have blocked_reason
    if status == "blocked" and not data.get("blocked_reason"):
        errors.append("Blocked tasks must have 'blocked_reason'")

    # If done, should have done_ts
    if status == "done" and not data.get("done_ts"):
        errors.append("Done tasks must have 'done_ts' timestamp")

    # Estimate must be reasonable if present
    estimate = data.get("estimate")
    if estimate and not _is_valid_estimate(estimate):
        errors.append(f"Invalid estimate format: {estimate}. Use format like '2h', '30m', '1d'")

    # Due date must be in future or recent past if present
    due_date = data.get("due_date") or data.get("due_ts")
    if due_date:
        due_errors = _validate_due_date(due_date)
        errors.extend(due_errors)

    return errors


def validate_note_specific(data: dict[str, Any]) -> list[str]:
    """Validate note-specific business rules.

    Parameters
    ----------
    data
        Note metadata

    Returns
    -------
    list[str]
        List of validation errors
    """
    errors = []

    # Notes should have either category or tags for better organization
    has_category = bool(data.get("category"))
    has_tags = "tags" in data  # Check if tags key exists, even if empty list

    if not has_category and not has_tags:
        errors.append("Notes should have either 'category' or 'tags' for organization")

    return errors


def validate_event_specific(data: dict[str, Any]) -> list[str]:
    """Validate event-specific business rules.

    Parameters
    ----------
    data
        Event metadata

    Returns
    -------
    list[str]
        List of validation errors
    """
    errors = []

    # start_time is required
    if not data.get("start_time"):
        errors.append("Events must have 'start_time'")

    # If end_time exists, it must be after start_time
    start_time = data.get("start_time")
    end_time = data.get("end_time")

    if start_time and end_time:
        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

            if end_dt <= start_dt:
                errors.append(f"end_time ({end_time}) must be after start_time ({start_time})")
        except (ValueError, AttributeError) as exc:
            errors.append(f"Invalid datetime format: {exc}")

    return errors


def _validate_common_rules(data: dict[str, Any]) -> list[str]:
    """Validate rules common to all entities.

    Parameters
    ----------
    data
        Entity metadata

    Returns
    -------
    list[str]
        List of validation errors
    """
    errors = []

    # Title must not be empty
    title = data.get("title")
    if title is not None and not str(title).strip():
        errors.append("Title cannot be empty")

    # Title must not be too long
    if title and len(str(title)) > 200:
        errors.append(f"Title too long: {len(str(title))} characters (max 200)")

    # Links must reference valid entity IDs if present
    for link_field in ["relates_to", "depends_on", "blocks", "links"]:
        links = data.get(link_field)
        if links:
            if not isinstance(links, list):
                errors.append(f"Field '{link_field}' must be a list")
            else:
                for link in links:
                    if not isinstance(link, str):
                        errors.append(f"Link in '{link_field}' must be string, got: {type(link)}")
                    elif not _is_valid_entity_id_format(link):
                        errors.append(f"Invalid entity ID format in '{link_field}': {link}")

    return errors


def _is_valid_estimate(estimate: str) -> bool:
    """Check if estimate format is valid.

    Valid formats: "2h", "30m", "1d", "1.5h"

    Parameters
    ----------
    estimate
        Estimate string

    Returns
    -------
    bool
        True if valid format
    """
    import re

    # Pattern: number (optional decimal) + unit (h/m/d)
    pattern = r"^\d+(\.\d+)?[hmd]$"
    return bool(re.match(pattern, estimate.lower()))


def _validate_due_date(due_date: str) -> list[str]:
    """Validate due date is reasonable.

    Parameters
    ----------
    due_date
        Due date ISO-8601 string

    Returns
    -------
    list[str]
        List of errors
    """
    errors = []

    try:
        due_dt = datetime.fromisoformat(due_date.replace("Z", "+00:00"))
        now = datetime.now(due_dt.tzinfo or due_dt.tzinfo)

        # Check if due date is too far in the past (> 1 year)
        if (now - due_dt).days > 365:
            errors.append(f"Due date is too far in the past: {due_date}")

        # Check if due date is too far in the future (> 10 years)
        if (due_dt - now).days > 3650:
            errors.append(f"Due date is too far in the future: {due_date}")

    except (ValueError, AttributeError) as exc:
        errors.append(f"Invalid due_date format: {exc}")

    return errors


def _is_valid_entity_id_format(entity_id: str) -> bool:
    """Check if entity ID has valid format.

    Valid format: {type}-{timestamp}-{slug} or {type}-{uuid}

    Parameters
    ----------
    entity_id
        Entity ID string

    Returns
    -------
    bool
        True if valid format
    """
    import re

    # Pattern: type-rest (where type is lowercase letters)
    pattern = r"^[a-z]+-[a-z0-9-]+$"
    return bool(re.match(pattern, entity_id))
