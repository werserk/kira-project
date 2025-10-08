"""Sync Pipeline - thin orchestration for calendar/adapter synchronization (ADR-009).

This pipeline coordinates periodic sync operations by publishing sync.tick events.
Adapters and plugins subscribe to these events and perform their sync logic.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..core.events import EventBus
    from ..core.scheduler import Scheduler

__all__ = [
    "SyncPipeline",
    "SyncPipelineConfig",
    "SyncPipelineResult",
    "create_sync_pipeline",
]


@dataclass
class SyncPipelineConfig:
    """Configuration for sync pipeline."""

    sync_interval_seconds: int = 300  # 5 minutes default
    max_retries: int = 3
    retry_delay: float = 2.0
    retry_backoff: float = 2.0
    log_path: Path | None = None
    adapters: list[str] = field(default_factory=lambda: ["gcal", "telegram"])


@dataclass
class SyncPipelineResult:
    """Result of sync execution."""

    success: bool
    adapters_synced: int
    adapters_failed: int
    duration_ms: float
    trace_id: str
    errors: list[str] = field(default_factory=list)


class SyncPipeline:
    """Thin orchestration pipeline for adapter synchronization.

    Responsibilities (ADR-009):
    - Publish sync.tick events on schedule
    - Coordinate sync start/completion
    - Retry failed syncs with backoff
    - Emit structured JSONL logs with trace IDs
    - NO business logic (adapters handle sync details)

    Example:
        >>> from kira.core.events import create_event_bus
        >>> from kira.core.scheduler import create_scheduler
        >>> from kira.pipelines.sync_pipeline import create_sync_pipeline
        >>>
        >>> event_bus = create_event_bus()
        >>> scheduler = create_scheduler()
        >>> pipeline = create_sync_pipeline(
        ...     event_bus=event_bus,
        ...     scheduler=scheduler
        ... )
        >>> job_id = pipeline.schedule_periodic_sync()
        >>> result = pipeline.run()  # Or run via scheduler
    """

    def __init__(
        self,
        config: SyncPipelineConfig,
        *,
        event_bus: EventBus | None = None,
        scheduler: Scheduler | None = None,
        logger: Any = None,
    ) -> None:
        """Initialize sync pipeline.

        Parameters
        ----------
        config
            Pipeline configuration
        event_bus
            Event bus for publishing sync events (ADR-005)
        scheduler
            Scheduler for periodic sync (ADR-005)
        logger
            Optional structured logger
        """
        self.config = config
        self.event_bus = event_bus
        self.scheduler = scheduler
        self.logger = logger
        self._job_id: str | None = None

    def schedule_periodic_sync(self) -> str | None:
        """Schedule periodic sync execution.

        Returns
        -------
        str or None
            Job ID if scheduled, None if scheduler not available
        """
        if not self.scheduler:
            if self.logger:
                self.logger.warning("Scheduler not available, cannot schedule periodic sync")
            return None

        # Schedule recurring sync
        job_id = self.scheduler.schedule_interval(
            name="sync_pipeline_periodic",
            interval_seconds=self.config.sync_interval_seconds,
            callable=lambda: self.run(),
        )

        self._job_id = job_id

        self._log_event(
            "sync_scheduled",
            {
                "job_id": job_id,
                "interval_seconds": self.config.sync_interval_seconds,
            },
        )

        return job_id

    def cancel_periodic_sync(self) -> bool:
        """Cancel periodic sync if scheduled.

        Returns
        -------
        bool
            True if cancelled successfully
        """
        if not self._job_id or not self.scheduler:
            return False

        success = self.scheduler.cancel(self._job_id)

        if success:
            self._log_event("sync_cancelled", {"job_id": self._job_id})

        self._job_id = None
        return success

    def run(self, adapters: list[str] | None = None) -> SyncPipelineResult:
        """Execute sync pipeline.

        Parameters
        ----------
        adapters
            Optional list of adapters to sync (defaults to config.adapters)

        Returns
        -------
        SyncPipelineResult
            Execution result with metrics
        """
        trace_id = str(uuid.uuid4())
        start_time = time.time()

        adapters_to_sync = adapters or self.config.adapters

        self._log_event(
            "pipeline_started",
            {
                "trace_id": trace_id,
                "pipeline": "sync",
                "adapters": adapters_to_sync,
            },
        )

        # Publish sync.tick event for each adapter
        # Thin orchestration: adapters subscribe and handle their own sync logic
        adapters_synced = 0
        adapters_failed = 0
        errors = []

        for adapter_name in adapters_to_sync:
            success = self._sync_adapter(adapter_name, trace_id)
            if success:
                adapters_synced += 1
            else:
                adapters_failed += 1
                errors.append(f"Adapter {adapter_name} sync failed")

        duration_ms = (time.time() - start_time) * 1000

        result = SyncPipelineResult(
            success=(adapters_failed == 0),
            adapters_synced=adapters_synced,
            adapters_failed=adapters_failed,
            duration_ms=duration_ms,
            trace_id=trace_id,
            errors=errors,
        )

        # Log completion
        self._log_event(
            "pipeline_completed",
            {
                "trace_id": trace_id,
                "pipeline": "sync",
                "adapters_synced": adapters_synced,
                "adapters_failed": adapters_failed,
                "duration_ms": duration_ms,
                "outcome": "success" if result.success else "partial_failure",
            },
        )

        return result

    def _sync_adapter(self, adapter_name: str, trace_id: str, attempt: int = 1) -> bool:
        """Sync single adapter by publishing sync.tick event.

        Thin orchestration - adapter handles actual sync logic via event subscription.

        Parameters
        ----------
        adapter_name
            Name of adapter to sync
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
            # Publish sync.tick event (adapters subscribe and handle sync)
            if self.event_bus:
                payload = {
                    "adapter": adapter_name,
                    "trace_id": trace_id,
                    "attempt": str(attempt),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                self.event_bus.publish("sync.tick", payload)

            duration_ms = (time.time() - start_time) * 1000

            # Log success
            self._log_event(
                "adapter_synced",
                {
                    "trace_id": trace_id,
                    "adapter": adapter_name,
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
                "adapter_sync_failed",
                {
                    "trace_id": trace_id,
                    "adapter": adapter_name,
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
                return self._sync_adapter(adapter_name, trace_id, attempt + 1)

            return False

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
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": "pipeline",
            "pipeline": "sync",
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


def create_sync_pipeline(
    *,
    event_bus: EventBus | None = None,
    scheduler: Scheduler | None = None,
    logger: Any = None,
    log_path: Path | str | None = None,
    **config_kwargs: Any,
) -> SyncPipeline:
    """Factory function to create sync pipeline.

    Parameters
    ----------
    event_bus
        Event bus for publishing sync events
    scheduler
        Scheduler for periodic sync
    logger
        Optional logger instance
    log_path
        Optional path for JSONL logs
    **config_kwargs
        Additional configuration options

    Returns
    -------
    SyncPipeline
        Configured pipeline instance

    Example:
        >>> pipeline = create_sync_pipeline(
        ...     event_bus=event_bus,
        ...     scheduler=scheduler,
        ...     sync_interval_seconds=600,
        ...     log_path=Path("logs/pipelines/sync.jsonl")
        ... )
    """
    if log_path:
        log_path = Path(log_path) if isinstance(log_path, str) else log_path
        config_kwargs["log_path"] = log_path

    config = SyncPipelineConfig(**config_kwargs)

    return SyncPipeline(config, event_bus=event_bus, scheduler=scheduler, logger=logger)
