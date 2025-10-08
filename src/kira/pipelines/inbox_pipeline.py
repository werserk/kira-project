"""Inbox Pipeline - thin orchestration for inbox processing (ADR-009).

This pipeline coordinates the flow from inbox folder scanning to plugin-based
normalization. It contains NO business logic - only routing, retry, and telemetry.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..core.events import EventBus

__all__ = [
    "InboxPipeline",
    "InboxPipelineConfig",
    "InboxPipelineResult",
    "create_inbox_pipeline",
]


@dataclass
class InboxPipelineConfig:
    """Configuration for inbox pipeline."""

    vault_path: Path
    inbox_folder: str = "inbox"
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_backoff: float = 2.0
    max_items_per_run: int = 100
    log_path: Path | None = None


@dataclass
class InboxPipelineResult:
    """Result of pipeline execution."""

    success: bool
    items_scanned: int
    items_processed: int
    items_failed: int
    duration_ms: float
    trace_id: str
    errors: list[str] = field(default_factory=list)


class InboxPipeline:
    """Thin orchestration pipeline for inbox processing.

    Responsibilities (ADR-009):
    - Scan inbox folder for new items
    - Publish events for each item (plugins handle processing)
    - Retry failed items with backoff
    - Emit structured JSONL logs with trace IDs
    - NO business logic (normalization is in plugins)

    Example:
        >>> from kira.core.events import create_event_bus
        >>> from kira.pipelines.inbox_pipeline import create_inbox_pipeline
        >>> event_bus = create_event_bus()
        >>> pipeline = create_inbox_pipeline(
        ...     vault_path=Path("vault"),
        ...     event_bus=event_bus
        ... )
        >>> result = pipeline.run()
        >>> print(f"Processed {result.items_processed} items")
    """

    def __init__(
        self,
        config: InboxPipelineConfig,
        *,
        event_bus: EventBus | None = None,
        logger: Any = None,
    ) -> None:
        """Initialize inbox pipeline.

        Parameters
        ----------
        config
            Pipeline configuration
        event_bus
            Event bus for publishing events (ADR-005)
        logger
            Optional structured logger
        """
        self.config = config
        self.event_bus = event_bus
        self.logger = logger
        self.inbox_path = config.vault_path / config.inbox_folder
        self.inbox_path.mkdir(parents=True, exist_ok=True)

    def scan_inbox_items(self) -> list[Path]:
        """Scan inbox folder for items to process.

        Returns
        -------
        list[Path]
            List of file paths in inbox
        """
        if not self.inbox_path.exists():
            return []

        # Scan for markdown and text files
        items: list[Path] = []
        for pattern in ["*.md", "*.txt"]:
            items.extend(self.inbox_path.glob(pattern))

        # Limit to max items
        items = sorted(items, key=lambda p: p.stat().st_mtime)
        return items[: self.config.max_items_per_run]

    def process_item(self, item_path: Path, trace_id: str, attempt: int = 1) -> bool:
        """Process single inbox item by publishing event.

        This is THIN orchestration - just routing to plugins via events.
        Plugins handle actual normalization logic.

        Parameters
        ----------
        item_path
            Path to inbox item
        trace_id
            Trace ID for correlation
        attempt
            Retry attempt number

        Returns
        -------
        bool
            True if successful
        """
        start_time = time.time()

        try:
            # Read item content
            content = item_path.read_text(encoding="utf-8")

            # Determine event type based on file extension
            if item_path.suffix == ".md":
                event_name = "file.dropped"
                payload = {
                    "file_path": str(item_path),
                    "content": content,
                    "mime_type": "text/markdown",
                    "source": "inbox_scan",
                }
            else:
                event_name = "message.received"
                payload = {
                    "message": content,
                    "source": "inbox_file",
                    "file_path": str(item_path),
                }

            # Add trace context
            payload["trace_id"] = trace_id
            payload["attempt"] = str(attempt)
            payload["timestamp"] = datetime.now(UTC).isoformat()

            # Publish event to plugins (thin orchestration - no business logic)
            if self.event_bus:
                self.event_bus.publish(event_name, payload)

            duration_ms = (time.time() - start_time) * 1000

            # Log success
            self._log_event(
                "item_processed",
                {
                    "trace_id": trace_id,
                    "file_path": str(item_path),
                    "event_name": event_name,
                    "attempt": attempt,
                    "duration_ms": duration_ms,
                    "outcome": "success",
                },
            )

            return True

        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000

            # Log failure
            self._log_event(
                "item_failed",
                {
                    "trace_id": trace_id,
                    "file_path": str(item_path),
                    "attempt": attempt,
                    "duration_ms": duration_ms,
                    "outcome": "failure",
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
            )

            # Retry with backoff
            if attempt < self.config.max_retries:
                delay = self.config.retry_delay * (self.config.retry_backoff ** (attempt - 1))
                time.sleep(delay)
                return self.process_item(item_path, trace_id, attempt + 1)

            return False

    def run(self) -> InboxPipelineResult:
        """Execute inbox pipeline.

        Returns
        -------
        InboxPipelineResult
            Execution result with metrics
        """
        trace_id = str(uuid.uuid4())
        start_time = time.time()

        self._log_event(
            "pipeline_started",
            {
                "trace_id": trace_id,
                "pipeline": "inbox",
                "inbox_path": str(self.inbox_path),
            },
        )

        # Scan inbox
        items = self.scan_inbox_items()
        items_scanned = len(items)

        # Process each item
        items_processed = 0
        items_failed = 0
        errors = []

        for item_path in items:
            success = self.process_item(item_path, trace_id)
            if success:
                items_processed += 1
            else:
                items_failed += 1
                errors.append(f"Failed to process {item_path.name}")

        duration_ms = (time.time() - start_time) * 1000

        result = InboxPipelineResult(
            success=(items_failed == 0),
            items_scanned=items_scanned,
            items_processed=items_processed,
            items_failed=items_failed,
            duration_ms=duration_ms,
            trace_id=trace_id,
            errors=errors,
        )

        # Log completion
        self._log_event(
            "pipeline_completed",
            {
                "trace_id": trace_id,
                "pipeline": "inbox",
                "items_scanned": items_scanned,
                "items_processed": items_processed,
                "items_failed": items_failed,
                "duration_ms": duration_ms,
                "outcome": "success" if result.success else "partial_failure",
            },
        )

        return result

    def _log_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Emit structured JSONL log entry.

        Parameters
        ----------
        event_type
            Type of log event
        data
            Event data (must be JSON-serializable)
        """
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "component": "pipeline",
            "pipeline": "inbox",
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
            if data.get("outcome") == "failure":
                self.logger.error(f"{event_type}: {json.dumps(data)}")
            else:
                self.logger.info(f"{event_type}: {json.dumps(data)}")


def create_inbox_pipeline(
    vault_path: Path | str,
    *,
    event_bus: EventBus | None = None,
    logger: Any = None,
    log_path: Path | str | None = None,
    **config_kwargs: Any,
) -> InboxPipeline:
    """Factory function to create inbox pipeline.

    Parameters
    ----------
    vault_path
        Path to vault directory
    event_bus
        Event bus for publishing events
    logger
        Optional logger instance
    log_path
        Optional path for JSONL logs
    **config_kwargs
        Additional configuration options

    Returns
    -------
    InboxPipeline
        Configured pipeline instance

    Example:
        >>> pipeline = create_inbox_pipeline(
        ...     Path("vault"),
        ...     event_bus=event_bus,
        ...     max_retries=5,
        ...     log_path=Path("logs/pipelines/inbox.jsonl")
        ... )
    """
    vault_path = Path(vault_path) if isinstance(vault_path, str) else vault_path

    if log_path:
        log_path = Path(log_path) if isinstance(log_path, str) else log_path
        config_kwargs["log_path"] = log_path

    config = InboxPipelineConfig(vault_path=vault_path, **config_kwargs)

    return InboxPipeline(config, event_bus=event_bus, logger=logger)
