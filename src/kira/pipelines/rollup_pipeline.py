"""Rollup Pipeline - thin orchestration for report generation (ADR-009).

This pipeline coordinates rollup generation by publishing rollup.requested events.
Plugins subscribe and contribute their rollup sections. Pipeline aggregates and publishes.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..core.events import EventBus
    from ..core.host import HostAPI

__all__ = [
    "RollupPipeline",
    "RollupPipelineConfig",
    "RollupPipelineResult",
    "create_rollup_pipeline",
]


@dataclass
class RollupPipelineConfig:
    """Configuration for rollup pipeline."""

    vault_path: Path
    rollup_folder: str = "journal"
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_backoff: float = 2.0
    log_path: Path | None = None


@dataclass
class RollupPipelineResult:
    """Result of rollup generation."""

    success: bool
    rollup_type: str  # daily, weekly, monthly
    period_start: date
    period_end: date
    entity_id: str | None
    sections_count: int
    duration_ms: float
    trace_id: str
    errors: list[str] = field(default_factory=list)


class RollupPipeline:
    """Thin orchestration pipeline for rollup generation.

    Responsibilities (ADR-009):
    - Publish rollup.requested events for target period
    - Collect rollup sections from plugins
    - Aggregate sections and create rollup entity
    - Emit structured JSONL logs with trace IDs
    - NO business logic (plugins generate their sections)

    Example:
        >>> from kira.core.events import create_event_bus
        >>> from kira.core.host import create_host_api
        >>> from kira.pipelines.rollup_pipeline import create_rollup_pipeline
        >>>
        >>> event_bus = create_event_bus()
        >>> host_api = create_host_api(Path("vault"))
        >>> pipeline = create_rollup_pipeline(
        ...     vault_path=Path("vault"),
        ...     event_bus=event_bus,
        ...     host_api=host_api
        ... )
        >>> result = pipeline.create_daily_rollup(date.today())
    """

    def __init__(
        self,
        config: RollupPipelineConfig,
        *,
        event_bus: EventBus | None = None,
        host_api: HostAPI | None = None,
        logger: Any = None,
    ) -> None:
        """Initialize rollup pipeline.

        Parameters
        ----------
        config
            Pipeline configuration
        event_bus
            Event bus for publishing events (ADR-005)
        host_api
            Host API for creating rollup entities (ADR-006)
        logger
            Optional structured logger
        """
        self.config = config
        self.event_bus = event_bus
        self.host_api = host_api
        self.logger = logger
        self.rollup_path = config.vault_path / config.rollup_folder
        self.rollup_path.mkdir(parents=True, exist_ok=True)

    def create_daily_rollup(
        self,
        target_date: date | None = None,
    ) -> RollupPipelineResult:
        """Create daily rollup for specified date.

        Parameters
        ----------
        target_date
            Date to create rollup for (default: today)

        Returns
        -------
        RollupPipelineResult
            Execution result
        """
        if target_date is None:
            target_date = date.today()

        return self._generate_rollup(
            rollup_type="daily",
            period_start=target_date,
            period_end=target_date,
        )

    def create_weekly_rollup(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> RollupPipelineResult:
        """Create weekly rollup for specified week.

        Parameters
        ----------
        start_date
            Week start date (default: last Monday)
        end_date
            Week end date (default: last Sunday)

        Returns
        -------
        RollupPipelineResult
            Execution result
        """
        if start_date is None:
            # Default to current week (Monday to Sunday)
            today = date.today()
            start_date = today - timedelta(days=today.weekday())

        if end_date is None:
            end_date = start_date + timedelta(days=6)

        return self._generate_rollup(
            rollup_type="weekly",
            period_start=start_date,
            period_end=end_date,
        )

    def create_monthly_rollup(
        self,
        year: int | None = None,
        month: int | None = None,
    ) -> RollupPipelineResult:
        """Create monthly rollup.

        Parameters
        ----------
        year
            Year (default: current year)
        month
            Month (default: current month)

        Returns
        -------
        RollupPipelineResult
            Execution result
        """
        today = date.today()
        if year is None:
            year = today.year
        if month is None:
            month = today.month

        # First day of month
        start_date = date(year, month, 1)

        # Last day of month
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        return self._generate_rollup(
            rollup_type="monthly",
            period_start=start_date,
            period_end=end_date,
        )

    def _generate_rollup(
        self,
        rollup_type: str,
        period_start: date,
        period_end: date,
    ) -> RollupPipelineResult:
        """Generate rollup by publishing events and aggregating responses.

        Thin orchestration: plugins contribute sections, pipeline aggregates.

        Parameters
        ----------
        rollup_type
            Type of rollup (daily, weekly, monthly)
        period_start
            Period start date
        period_end
            Period end date

        Returns
        -------
        RollupPipelineResult
            Generation result
        """
        trace_id = str(uuid.uuid4())
        start_time = time.time()

        self._log_event(
            "pipeline_started",
            {
                "trace_id": trace_id,
                "pipeline": "rollup",
                "rollup_type": rollup_type,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
            },
        )

        # Publish rollup.requested event (thin orchestration)
        # Plugins subscribe and contribute their rollup sections
        sections = self._collect_rollup_sections(rollup_type, period_start, period_end, trace_id)

        # Create rollup entity via Host API
        entity_id = None
        if self.host_api:
            try:
                entity_id = self._create_rollup_entity(rollup_type, period_start, period_end, sections, trace_id)
            except Exception as exc:
                self._log_event(
                    "entity_creation_failed",
                    {
                        "trace_id": trace_id,
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                    },
                )

        duration_ms = (time.time() - start_time) * 1000

        result = RollupPipelineResult(
            success=(entity_id is not None),
            rollup_type=rollup_type,
            period_start=period_start,
            period_end=period_end,
            entity_id=entity_id,
            sections_count=len(sections),
            duration_ms=duration_ms,
            trace_id=trace_id,
            errors=[] if entity_id else ["Failed to create rollup entity"],
        )

        # Log completion
        self._log_event(
            "pipeline_completed",
            {
                "trace_id": trace_id,
                "pipeline": "rollup",
                "rollup_type": rollup_type,
                "entity_id": entity_id,
                "sections_count": len(sections),
                "duration_ms": duration_ms,
                "outcome": "success" if result.success else "failure",
            },
        )

        return result

    def _collect_rollup_sections(
        self,
        rollup_type: str,
        period_start: date,
        period_end: date,
        trace_id: str,
    ) -> list[dict[str, Any]]:
        """Collect rollup sections from plugins via events.

        Parameters
        ----------
        rollup_type
            Type of rollup
        period_start
            Period start
        period_end
            Period end
        trace_id
            Trace ID

        Returns
        -------
        list[dict]
            List of section contributions from plugins
        """
        sections: list[dict[str, Any]] = []

        if self.event_bus:
            # Publish rollup.requested event
            payload = {
                "rollup_type": rollup_type,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # TODO: Implement event response collection mechanism
            # For now, return empty sections (plugins will be updated to respond)
            self.event_bus.publish("rollup.requested", payload)

        return sections

    def _create_rollup_entity(
        self,
        rollup_type: str,
        period_start: date,
        period_end: date,
        sections: list[dict[str, Any]],
        trace_id: str,
    ) -> str:
        """Create rollup entity via Host API.

        Parameters
        ----------
        rollup_type
            Type of rollup
        period_start
            Period start
        period_end
            Period end
        sections
            Rollup sections from plugins
        trace_id
            Trace ID

        Returns
        -------
        str
            Created entity ID
        """
        if not self.host_api:
            raise RuntimeError("Host API not available")

        # Generate rollup title
        if rollup_type == "daily":
            title = f"Daily Rollup {period_start.isoformat()}"
        elif rollup_type == "weekly":
            title = f"Weekly Rollup {period_start.isoformat()} to {period_end.isoformat()}"
        else:
            title = f"Monthly Rollup {period_start.strftime('%Y-%m')}"

        # Generate rollup content
        content_parts = [f"# {title}\n"]

        if sections:
            for section in sections:
                section_title = section.get("title", "Untitled Section")
                section_content = section.get("content", "")
                content_parts.append(f"\n## {section_title}\n\n{section_content}\n")
        else:
            content_parts.append("\n*No sections contributed by plugins*\n")

        content = "\n".join(content_parts)

        # Create entity
        entity = self.host_api.create_entity(
            "note",
            {
                "title": title,
                "type": "rollup",
                "rollup_type": rollup_type,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "sections_count": len(sections),
                "trace_id": trace_id,
            },
            content=content,
        )

        return entity.id

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
            "pipeline": "rollup",
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


def create_rollup_pipeline(
    vault_path: Path | str,
    *,
    event_bus: EventBus | None = None,
    host_api: HostAPI | None = None,
    logger: Any = None,
    log_path: Path | str | None = None,
    **config_kwargs: Any,
) -> RollupPipeline:
    """Factory function to create rollup pipeline.

    Parameters
    ----------
    vault_path
        Path to vault directory
    event_bus
        Event bus for publishing rollup events
    host_api
        Host API for creating rollup entities
    logger
        Optional logger instance
    log_path
        Optional path for JSONL logs
    **config_kwargs
        Additional configuration options

    Returns
    -------
    RollupPipeline
        Configured pipeline instance

    Example:
        >>> pipeline = create_rollup_pipeline(
        ...     Path("vault"),
        ...     event_bus=event_bus,
        ...     host_api=host_api,
        ...     log_path=Path("logs/pipelines/rollup.jsonl")
        ... )
    """
    vault_path = Path(vault_path) if isinstance(vault_path, str) else vault_path

    if log_path:
        log_path = Path(log_path) if isinstance(log_path, str) else log_path
        config_kwargs["log_path"] = log_path

    config = RollupPipelineConfig(vault_path=vault_path, **config_kwargs)

    return RollupPipeline(config, event_bus=event_bus, host_api=host_api, logger=logger)
