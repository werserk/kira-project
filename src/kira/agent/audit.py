"""Audit trail for agent execution.

Phase 3, Item 13: Tracing & audit.
Emits JSONL events per node for full path reconstruction.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["AuditEvent", "AuditLogger", "create_audit_logger"]


@dataclass
class AuditEvent:
    """Single audit event for agent execution.

    Attributes
    ----------
    trace_id
        Trace identifier for correlating events
    node
        Node name that generated event
    timestamp
        ISO 8601 timestamp
    input_data
        Input to the node
    output_data
        Output from the node
    elapsed_ms
        Execution time in milliseconds
    error
        Error message if node failed
    metadata
        Additional metadata
    """

    trace_id: str
    node: str
    timestamp: str
    input_data: dict[str, Any] | None = None
    output_data: dict[str, Any] | None = None
    elapsed_ms: int | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSONL serialization.

        Returns
        -------
        dict
            Event data
        """
        data: dict[str, Any] = {
            "trace_id": self.trace_id,
            "node": self.node,
            "timestamp": self.timestamp,
        }

        if self.input_data is not None:
            data["input"] = self.input_data

        if self.output_data is not None:
            data["output"] = self.output_data

        if self.elapsed_ms is not None:
            data["elapsed_ms"] = self.elapsed_ms

        if self.error:
            data["error"] = self.error

        if self.metadata:
            data["metadata"] = self.metadata

        return data

    def to_jsonl(self) -> str:
        """Convert to JSONL string.

        Returns
        -------
        str
            Single-line JSON string
        """
        return json.dumps(self.to_dict(), ensure_ascii=False)


class AuditLogger:
    """Audit logger for agent execution events.

    Writes JSONL events to artifacts/audit/agent/*.jsonl.
    Correlates with existing Kira tool audit via shared trace_id.
    """

    def __init__(self, audit_path: Path, enable_audit: bool = True) -> None:
        """Initialize audit logger.

        Parameters
        ----------
        audit_path
            Path to audit log directory
        enable_audit
            Enable/disable audit logging
        """
        self.audit_path = audit_path
        self.enable_audit = enable_audit

        if enable_audit:
            self.audit_path.mkdir(parents=True, exist_ok=True)

    def _get_log_file(self) -> Path:
        """Get current log file path (date-based rotation).

        Returns
        -------
        Path
            Log file path
        """
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        return self.audit_path / f"agent-{date_str}.jsonl"

    def log_event(self, event: AuditEvent) -> None:
        """Log an audit event.

        Parameters
        ----------
        event
            Audit event to log
        """
        if not self.enable_audit:
            return

        try:
            log_file = self._get_log_file()
            jsonl_line = event.to_jsonl()

            with log_file.open("a") as f:
                f.write(jsonl_line + "\n")

            logger.debug(f"Logged audit event: {event.node} for trace {event.trace_id}")

        except Exception as e:
            logger.error(f"Failed to write audit event: {e}", exc_info=True)

    def log_node_execution(
        self,
        trace_id: str,
        node: str,
        input_data: dict[str, Any] | None = None,
        output_data: dict[str, Any] | None = None,
        elapsed_ms: int | None = None,
        error: str | None = None,
        **metadata: Any,
    ) -> None:
        """Log a node execution event.

        Parameters
        ----------
        trace_id
            Trace identifier
        node
            Node name
        input_data
            Input to node
        output_data
            Output from node
        elapsed_ms
            Execution time in milliseconds
        error
            Error message if failed
        **metadata
            Additional metadata
        """
        event = AuditEvent(
            trace_id=trace_id,
            node=node,
            timestamp=datetime.now(UTC).isoformat(),
            input_data=input_data,
            output_data=output_data,
            elapsed_ms=elapsed_ms,
            error=error,
            metadata=metadata,
        )

        self.log_event(event)

    def read_events(self, trace_id: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        """Read audit events from log files.

        Parameters
        ----------
        trace_id
            Optional trace ID to filter by
        limit
            Maximum number of events to return

        Returns
        -------
        list[dict]
            List of audit events
        """
        if not self.enable_audit:
            return []

        events = []

        try:
            # Read all JSONL files
            for log_file in sorted(self.audit_path.glob("agent-*.jsonl")):
                with log_file.open() as f:
                    for line in f:
                        if not line.strip():
                            continue

                        try:
                            event_data = json.loads(line)

                            # Filter by trace_id if provided
                            if trace_id and event_data.get("trace_id") != trace_id:
                                continue

                            events.append(event_data)

                            # Check limit
                            if limit and len(events) >= limit:
                                return events

                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON line in {log_file}: {line[:100]}")

        except Exception as e:
            logger.error(f"Failed to read audit events: {e}", exc_info=True)

        return events

    def reconstruct_path(self, trace_id: str) -> list[dict[str, Any]]:
        """Reconstruct full execution path for a trace.

        Parameters
        ----------
        trace_id
            Trace identifier

        Returns
        -------
        list[dict]
            Ordered list of events for trace
        """
        events = self.read_events(trace_id=trace_id)

        # Sort by timestamp
        events.sort(key=lambda e: e.get("timestamp", ""))

        return events

    def get_statistics(self, trace_id: str | None = None) -> dict[str, Any]:
        """Get execution statistics from audit log.

        Parameters
        ----------
        trace_id
            Optional trace ID to filter by

        Returns
        -------
        dict
            Statistics including node counts, errors, timings
        """
        events = self.read_events(trace_id=trace_id)

        stats: dict[str, Any] = {
            "total_events": len(events),
            "traces": set(),
            "nodes": {},
            "errors": 0,
            "total_elapsed_ms": 0,
        }

        for event in events:
            # Track traces
            if "trace_id" in event:
                stats["traces"].add(event["trace_id"])

            # Count nodes
            node = event.get("node", "unknown")
            if node not in stats["nodes"]:
                stats["nodes"][node] = {"count": 0, "errors": 0, "elapsed_ms": 0}

            stats["nodes"][node]["count"] += 1

            # Count errors
            if event.get("error"):
                stats["errors"] += 1
                stats["nodes"][node]["errors"] += 1

            # Sum elapsed time
            elapsed = event.get("elapsed_ms", 0)
            if elapsed:
                stats["total_elapsed_ms"] += elapsed
                stats["nodes"][node]["elapsed_ms"] += elapsed

        stats["traces"] = len(stats["traces"])
        return stats


def create_audit_logger(
    audit_path: Path | None = None,
    enable_audit: bool = True,
) -> AuditLogger:
    """Factory function to create audit logger.

    Parameters
    ----------
    audit_path
        Path to audit log directory
    enable_audit
        Enable/disable audit logging

    Returns
    -------
    AuditLogger
        Configured audit logger
    """
    if audit_path is None:
        audit_path = Path.cwd() / "artifacts" / "audit" / "agent"

    logger.info(f"Created audit logger: path={audit_path}, enabled={enable_audit}")
    return AuditLogger(audit_path, enable_audit)

