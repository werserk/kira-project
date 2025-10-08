"""Structured logging and tracing (Phase 5, Point 17).

Provides structured logging with correlation by event_id/uid.
Logs full processing chain: ingress → validation → upsert → conflicts → quarantine.

DoD: One can reconstruct the full processing chain from logs for any entity.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from ..core.time import format_utc_iso8601, get_current_utc

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "LogLevel",
    "StructuredLogger",
    "create_logger",
    "log_conflict",
    "log_ingress",
    "log_quarantine",
    "log_upsert",
    "log_validation_failure",
    "log_validation_success",
]

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


@dataclass
class LogEntry:
    """Structured log entry (Phase 5, Point 17).

    Attributes
    ----------
    timestamp : str
        ISO-8601 UTC timestamp
    level : str
        Log level
    event_type : str
        Type of event (ingress, validation, upsert, etc.)
    message : str
        Human-readable message
    correlation_id : str | None
        event_id or uid for correlation
    entity_id : str | None
        Entity UID (if applicable)
    event_id : str | None
        Event ID (if applicable)
    trace_id : str | None
        Trace ID from CLI or pipeline (for full chain correlation)
    source : str | None
        Source of event
    metadata : dict[str, Any]
        Additional structured data
    """

    timestamp: str
    level: str
    event_type: str
    message: str
    correlation_id: str | None = None
    entity_id: str | None = None
    event_id: str | None = None
    trace_id: str | None = None
    source: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Convert to JSON string.

        Returns
        -------
        str
            JSON representation
        """
        data = asdict(self)
        return json.dumps(data, sort_keys=True)


class StructuredLogger:
    """Structured logger with correlation support (Phase 5, Point 17).

    Logs events with correlation IDs (event_id/uid) for tracing.
    All logs are structured JSON for easy parsing and analysis.

    DoD: Reconstruct full processing chain from logs.
    """

    def __init__(
        self,
        name: str,
        *,
        log_file: Path | None = None,
        level: str = "INFO",
    ) -> None:
        """Initialize structured logger.

        Parameters
        ----------
        name
            Logger name
        log_file
            Optional log file path
        level
            Minimum log level
        """
        self.name = name
        self.log_file = log_file
        self.level = level.upper()

        # Set up Python logger
        self._logger = logging.getLogger(name)
        self._logger.setLevel(getattr(logging, self.level))

        # Console handler (JSON)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        self._logger.addHandler(console_handler)

        # File handler (JSON)
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(file_handler)

    def log(
        self,
        level: str,
        event_type: str,
        message: str,
        *,
        correlation_id: str | None = None,
        entity_id: str | None = None,
        event_id: str | None = None,
        trace_id: str | None = None,
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log structured entry (Phase 5, Point 17).

        Parameters
        ----------
        level
            Log level
        event_type
            Type of event (ingress, validation, upsert, etc.)
        message
            Human-readable message
        correlation_id
            Correlation ID (event_id or uid)
        entity_id
            Entity UID
        event_id
            Event ID
        trace_id
            Trace ID from CLI or pipeline (for full chain correlation)
        source
            Source of event
        metadata
            Additional structured data
        """
        entry = LogEntry(
            timestamp=format_utc_iso8601(get_current_utc()),
            level=level.upper(),
            event_type=event_type,
            message=message,
            correlation_id=correlation_id,
            entity_id=entity_id,
            event_id=event_id,
            trace_id=trace_id,
            source=source,
            metadata=metadata or {},
        )

        # Log as JSON
        log_json = entry.to_json()

        # Use appropriate log level
        log_method = getattr(self._logger, level.lower(), self._logger.info)
        log_method(log_json)

    def debug(self, event_type: str, message: str, **kwargs) -> None:
        """Log DEBUG entry."""
        self.log("DEBUG", event_type, message, **kwargs)

    def info(self, event_type: str, message: str, **kwargs) -> None:
        """Log INFO entry."""
        self.log("INFO", event_type, message, **kwargs)

    def warning(self, event_type: str, message: str, **kwargs) -> None:
        """Log WARNING entry."""
        self.log("WARNING", event_type, message, **kwargs)

    def error(self, event_type: str, message: str, **kwargs) -> None:
        """Log ERROR entry."""
        self.log("ERROR", event_type, message, **kwargs)

    def critical(self, event_type: str, message: str, **kwargs) -> None:
        """Log CRITICAL entry."""
        self.log("CRITICAL", event_type, message, **kwargs)


# Global logger instance
_default_logger: StructuredLogger | None = None


def create_logger(
    name: str = "kira",
    *,
    log_file: Path | None = None,
    level: str = "INFO",
) -> StructuredLogger:
    """Create structured logger.

    Parameters
    ----------
    name
        Logger name
    log_file
        Optional log file path
    level
        Minimum log level

    Returns
    -------
    StructuredLogger
        Configured logger
    """
    global _default_logger
    logger = StructuredLogger(name, log_file=log_file, level=level)
    _default_logger = logger
    return logger


def _get_logger() -> StructuredLogger:
    """Get default logger (create if needed)."""
    global _default_logger
    if _default_logger is None:
        _default_logger = create_logger()
    return _default_logger


def log_ingress(
    source: str,
    event_id: str,
    message: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Log ingress event (Phase 5, Point 17).

    Parameters
    ----------
    source
        Source of ingress (telegram, gcal, cli, etc.)
    event_id
        Event ID
    message
        Description of ingress
    metadata
        Additional data
    """
    logger = _get_logger()
    logger.info(
        "ingress",
        message,
        event_id=event_id,
        source=source,
        correlation_id=event_id,
        metadata=metadata,
    )


def log_validation_success(
    entity_id: str,
    entity_type: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Log successful validation (Phase 5, Point 17).

    Parameters
    ----------
    entity_id
        Entity UID
    entity_type
        Type of entity
    metadata
        Additional data
    """
    logger = _get_logger()
    logger.info(
        "validation_success",
        f"Entity {entity_id} ({entity_type}) validated successfully",
        entity_id=entity_id,
        correlation_id=entity_id,
        metadata=metadata or {"entity_type": entity_type},
    )


def log_validation_failure(
    entity_id: str,
    entity_type: str,
    errors: list[str],
    *,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Log validation failure (Phase 5, Point 17).

    Parameters
    ----------
    entity_id
        Entity UID
    entity_type
        Type of entity
    errors
        Validation errors
    metadata
        Additional data
    """
    logger = _get_logger()
    logger.warning(
        "validation_failure",
        f"Entity {entity_id} ({entity_type}) validation failed: {errors}",
        entity_id=entity_id,
        correlation_id=entity_id,
        metadata=metadata or {"entity_type": entity_type, "errors": errors},
    )


def log_upsert(
    entity_id: str,
    entity_type: str,
    operation: Literal["create", "update"],
    *,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Log entity upsert (Phase 5, Point 17).

    Parameters
    ----------
    entity_id
        Entity UID
    entity_type
        Type of entity
    operation
        Create or update
    metadata
        Additional data
    """
    logger = _get_logger()
    logger.info(
        "upsert",
        f"Entity {entity_id} ({entity_type}) {operation}d",
        entity_id=entity_id,
        correlation_id=entity_id,
        metadata=metadata or {"entity_type": entity_type, "operation": operation},
    )


def log_conflict(
    entity_id: str,
    conflict_type: str,
    resolution: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Log conflict detection and resolution (Phase 5, Point 17).

    Parameters
    ----------
    entity_id
        Entity UID
    conflict_type
        Type of conflict
    resolution
        How conflict was resolved
    metadata
        Additional data
    """
    logger = _get_logger()
    logger.warning(
        "conflict",
        f"Conflict detected for {entity_id} ({conflict_type}), resolved: {resolution}",
        entity_id=entity_id,
        correlation_id=entity_id,
        metadata=metadata or {"conflict_type": conflict_type, "resolution": resolution},
    )


def log_quarantine(
    entity_id: str | None,
    reason: str,
    quarantine_path: Path,
    *,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Log entity quarantined (Phase 5, Point 17).

    Parameters
    ----------
    entity_id
        Entity UID (if known)
    reason
        Quarantine reason
    quarantine_path
        Path to quarantined file
    metadata
        Additional data
    """
    logger = _get_logger()
    logger.error(
        "quarantine",
        f"Entity {entity_id or 'unknown'} quarantined: {reason}",
        entity_id=entity_id,
        correlation_id=entity_id,
        metadata=metadata or {"reason": reason, "quarantine_path": str(quarantine_path)},
    )
