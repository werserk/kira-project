"""Ingress normalization & shape validation (Phase 2, Point 8).

Adapters normalize payloads and drop malformed ones BEFORE publishing to the bus.
Invalid ingress never reaches consumers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from ..observability.logging import log_ingress

__all__ = [
    "IngressResult",
    "IngressValidator",
    "normalize_cli_payload",
    "normalize_gcal_payload",
    "normalize_telegram_payload",
]

logger = logging.getLogger(__name__)


@dataclass
class IngressResult:
    """Result of ingress normalization/validation.

    Attributes
    ----------
    valid : bool
        Whether payload is valid
    normalized_payload : dict | None
        Normalized payload (if valid)
    errors : list[str]
        Validation errors (if invalid)
    source : str
        Event source
    """

    valid: bool
    normalized_payload: dict[str, Any] | None
    errors: list[str]
    source: str

    def __bool__(self) -> bool:
        """Boolean conversion."""
        return self.valid


class IngressValidator:
    """Validates and normalizes ingress payloads (Phase 2, Point 8).

    Drop malformed payloads BEFORE publishing to event bus.
    Invalid ingress never reaches consumers.
    """

    def __init__(self, *, log_rejections: bool = True) -> None:
        """Initialize validator.

        Parameters
        ----------
        log_rejections
            Whether to log rejected payloads
        """
        self.log_rejections = log_rejections
        self._rejected_count = 0
        self._accepted_count = 0

    def validate_and_normalize(
        self,
        source: str,
        payload: dict[str, Any],
    ) -> IngressResult:
        """Validate and normalize ingress payload.

        Parameters
        ----------
        source
            Event source (telegram, gcal, cli)
        payload
            Raw payload from adapter

        Returns
        -------
        IngressResult
            Validation result with normalized payload or errors
        """
        errors = []

        # Basic shape validation
        if not isinstance(payload, dict):
            errors.append(f"Payload must be dict, got {type(payload)}")
            return self._reject(source, payload, errors)

        # Source-specific normalization
        if source == "telegram":
            return self._normalize_telegram(payload)
        if source == "gcal":
            return self._normalize_gcal(payload)
        if source == "cli":
            return self._normalize_cli(payload)
        # Generic normalization
        return self._normalize_generic(source, payload)

    def _normalize_telegram(self, payload: dict[str, Any]) -> IngressResult:
        """Normalize Telegram payload."""
        normalized = normalize_telegram_payload(payload)
        
        # Phase 5, Point 17: Log ingress
        if normalized.get("external_id"):
            log_ingress(
                source="telegram",
                event_id=normalized["external_id"],
                message=f"Telegram message ingress: {normalized.get('text', '')[:50]}",
                metadata={"user_id": normalized.get("user_id"), "message_id": normalized.get("message_id")},
            )
        
        return IngressResult(
            valid=True,
            normalized_payload=normalized,
            errors=[],
            source="telegram",
        )

    def _normalize_gcal(self, payload: dict[str, Any]) -> IngressResult:
        """Normalize Google Calendar payload."""
        normalized = normalize_gcal_payload(payload)
        
        # Phase 5, Point 17: Log ingress
        if normalized.get("external_id"):
            log_ingress(
                source="gcal",
                event_id=normalized["external_id"],
                message=f"GCal event ingress: {normalized.get('title', '')[:50]}",
                metadata={"start_time": normalized.get("start_time"), "end_time": normalized.get("end_time")},
            )
        
        return IngressResult(
            valid=True,
            normalized_payload=normalized,
            errors=[],
            source="gcal",
        )

    def _normalize_cli(self, payload: dict[str, Any]) -> IngressResult:
        """Normalize CLI payload."""
        normalized = normalize_cli_payload(payload)
        
        # Phase 5, Point 17: Log ingress
        if normalized.get("external_id"):
            log_ingress(
                source="cli",
                event_id=normalized["external_id"],
                message=f"CLI command ingress: {normalized.get('type', '')}",
                metadata={"command": normalized.get("command"), "trace_id": normalized.get("trace_id")},
            )
        
        return IngressResult(
            valid=True,
            normalized_payload=normalized,
            errors=[],
            source="cli",
        )

    def _normalize_generic(self, source: str, payload: dict[str, Any]) -> IngressResult:
        """Normalize generic payload."""
        errors = []

        # Required fields check
        if "type" not in payload:
            errors.append("Missing required field: type")

        if errors:
            return self._reject(source, payload, errors)

        # Add standard fields
        normalized = payload.copy()
        normalized.setdefault("source", source)

        self._accepted_count += 1

        return IngressResult(
            valid=True,
            normalized_payload=normalized,
            errors=[],
            source=source,
        )

    def _reject(
        self,
        source: str,
        payload: dict[str, Any],
        errors: list[str],
    ) -> IngressResult:
        """Reject invalid payload."""
        self._rejected_count += 1

        if self.log_rejections:
            logger.warning(
                f"Rejected {source} ingress: {'; '.join(errors)}",
                extra={
                    "source": source,
                    "errors": errors,
                    "payload_keys": list(payload.keys()) if isinstance(payload, dict) else None,
                },
            )

        return IngressResult(
            valid=False,
            normalized_payload=None,
            errors=errors,
            source=source,
        )

    def get_stats(self) -> dict[str, Any]:
        """Get ingress validation statistics.

        Returns
        -------
        dict[str, Any]
            Statistics including accepted/rejected counts
        """
        total = self._accepted_count + self._rejected_count

        return {
            "total_processed": total,
            "accepted": self._accepted_count,
            "rejected": self._rejected_count,
            "rejection_rate": self._rejected_count / total if total > 0 else 0.0,
        }


def normalize_telegram_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize Telegram message payload (Phase 2, Point 8).

    Parameters
    ----------
    payload
        Raw Telegram payload

    Returns
    -------
    dict[str, Any]
        Normalized payload
    """
    normalized = {}

    # Extract message text
    message = payload.get("message", {})
    if isinstance(message, dict):
        normalized["text"] = message.get("text", "")
        normalized["message_id"] = message.get("message_id")
        normalized["date"] = message.get("date")

        # User info
        from_user = message.get("from", {})
        if isinstance(from_user, dict):
            normalized["user_id"] = from_user.get("id")
            normalized["username"] = from_user.get("username")
            normalized["first_name"] = from_user.get("first_name")

    # Add source
    normalized["source"] = "telegram"
    normalized["type"] = "message"

    # Preserve original if needed for debugging
    if "message_id" in normalized:
        normalized["external_id"] = f"tg-{normalized['message_id']}"

    return normalized


def normalize_gcal_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize Google Calendar event payload (Phase 2, Point 8).

    Parameters
    ----------
    payload
        Raw GCal event payload

    Returns
    -------
    dict[str, Any]
        Normalized payload
    """
    normalized = {}

    # Event details
    normalized["title"] = payload.get("summary", "")
    normalized["description"] = payload.get("description")
    normalized["location"] = payload.get("location")

    # Time fields
    start = payload.get("start", {})
    end = payload.get("end", {})

    if isinstance(start, dict):
        normalized["start_time"] = start.get("dateTime") or start.get("date")

    if isinstance(end, dict):
        normalized["end_time"] = end.get("dateTime") or end.get("date")

    # Attendees
    attendees = payload.get("attendees", [])
    if isinstance(attendees, list):
        normalized["attendees"] = [att.get("email") for att in attendees if isinstance(att, dict) and att.get("email")]

    # Add source
    normalized["source"] = "gcal"
    normalized["type"] = "event"

    # External ID
    if "id" in payload:
        normalized["external_id"] = f"gcal-{payload['id']}"

    return normalized


def normalize_cli_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize CLI command payload (Phase 2, Point 8).

    Parameters
    ----------
    payload
        Raw CLI payload

    Returns
    -------
    dict[str, Any]
        Normalized payload
    """
    normalized = payload.copy()

    # Add source if not present
    normalized.setdefault("source", "cli")

    # Normalize command field
    if "command" in normalized:
        normalized["type"] = f"cli.{normalized['command']}"
    else:
        normalized.setdefault("type", "cli.unknown")

    # External ID from timestamp or generate
    if "timestamp" in normalized:
        normalized.setdefault("external_id", f"cli-{normalized['timestamp']}")

    return normalized


def validate_shape(payload: dict[str, Any], required_fields: list[str]) -> list[str]:
    """Validate payload shape has required fields.

    Parameters
    ----------
    payload
        Payload to validate
    required_fields
        List of required field names

    Returns
    -------
    list[str]
        List of errors (empty if valid)
    """
    errors = []

    for field in required_fields:
        if field not in payload:
            errors.append(f"Missing required field: {field}")
        elif payload[field] is None:
            errors.append(f"Field '{field}' cannot be null")

    return errors


def validate_types(
    payload: dict[str, Any],
    type_specs: dict[str, type],
) -> list[str]:
    """Validate field types in payload.

    Parameters
    ----------
    payload
        Payload to validate
    type_specs
        Dict mapping field names to expected types

    Returns
    -------
    list[str]
        List of errors (empty if valid)
    """
    errors = []

    for field, expected_type in type_specs.items():
        if field in payload:
            value = payload[field]
            if value is not None and not isinstance(value, expected_type):
                errors.append(
                    f"Field '{field}' has wrong type: " f"expected {expected_type.__name__}, got {type(value).__name__}"
                )

    return errors
