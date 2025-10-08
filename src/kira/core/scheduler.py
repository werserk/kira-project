"""Scheduler implementation for periodic and one-time tasks (ADR-005).

Supports interval, at (datetime), and cron triggers with fault handling,
cancellation, and idempotent scheduling.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "Job",
    "JobStatus",
    "Scheduler",
    "Trigger",
    "TriggerType",
    "create_scheduler",
]


class TriggerType(Enum):
    """Type of scheduling trigger."""

    INTERVAL = "interval"
    AT = "at"
    CRON = "cron"


@dataclass
class Trigger:
    """Trigger configuration for scheduled jobs."""

    type: TriggerType
    interval_seconds: float | None = None
    target_datetime: datetime | None = None
    cron_expression: str | None = None

    @classmethod
    def interval(cls, seconds: float) -> Trigger:
        """Create interval trigger."""
        return cls(type=TriggerType.INTERVAL, interval_seconds=seconds)

    @classmethod
    def at(cls, target: datetime | str) -> Trigger:
        """Create one-time trigger at specific datetime.

        Parameters
        ----------
        target
            Target datetime (datetime object or ISO format string)
        """
        if isinstance(target, str):
            target = datetime.fromisoformat(target)

        # Ensure timezone aware
        if target.tzinfo is None:
            target = target.replace(tzinfo=UTC)

        return cls(type=TriggerType.AT, target_datetime=target)

    @classmethod
    def cron(cls, expression: str) -> Trigger:
        """Create cron trigger.

        Parameters
        ----------
        expression
            Cron expression (e.g., "0 */2 * * *" for every 2 hours)
        """
        return cls(type=TriggerType.CRON, cron_expression=expression)


class JobStatus(Enum):
    """Status of scheduled job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """Scheduled job container."""

    job_id: str
    name: str
    trigger: Trigger
    callable: Callable[[], Any]
    status: JobStatus = JobStatus.PENDING
    created_at: float = field(default_factory=time.time)
    last_run_at: float | None = None
    next_run_at: float | None = None
    run_count: int = 0
    error_count: int = 0
    last_error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def should_run_now(self) -> bool:
        """Check if job should run now."""
        if self.status in (JobStatus.CANCELLED, JobStatus.COMPLETED):
            return False

        if self.next_run_at is None:
            return False

        return time.time() >= self.next_run_at

    def calculate_next_run(self) -> float | None:
        """Calculate next run time based on trigger.

        Returns
        -------
        float or None
            Unix timestamp for next run, or None if no more runs
        """
        if self.trigger.type == TriggerType.INTERVAL:
            if self.last_run_at is None:
                return time.time()
            return self.last_run_at + (self.trigger.interval_seconds or 0)

        if self.trigger.type == TriggerType.AT:
            # One-time job
            if self.last_run_at is not None:
                return None
            target_dt = self.trigger.target_datetime
            if target_dt is None:
                return None
            return target_dt.timestamp()

        # TriggerType.CRON
        # Cron scheduling (simplified)
        return self._calculate_cron_next_run()

    def _calculate_cron_next_run(self) -> float | None:
        """Calculate next run for cron trigger.

        This is a simplified implementation. For production, use croniter library.
        """
        if not self.trigger.cron_expression:
            return None

        # Simplified: parse basic cron expressions
        # Full implementation would use croniter
        try:
            from croniter import croniter  # type: ignore[import-untyped]

            base_time = datetime.fromtimestamp(self.last_run_at or time.time(), tz=UTC)
            cron = croniter(self.trigger.cron_expression, base_time)
            return float(cron.get_next())
        except ImportError:
            # Fallback: treat as hourly if we can't parse
            if self.last_run_at is None:
                return time.time() + 3600
            return self.last_run_at + 3600


class Scheduler:
    """Job scheduler with interval, at, and cron triggers (ADR-005).

    Features:
    - Interval triggers (run every N seconds)
    - At triggers (run once at specific datetime)
    - Cron triggers (run on cron schedule)
    - Idempotent scheduling (duplicate job_ids update existing)
    - Cancellation support
    - Missed run handling

    Example:
        >>> scheduler = Scheduler()
        >>> def my_task():
        ...     print("Task executed")
        >>> job_id = scheduler.schedule_interval("my-task", 10, my_task)
        >>> scheduler.start()
        >>> # ... later ...
        >>> scheduler.cancel(job_id)
        >>> scheduler.stop()
    """

    def __init__(self, logger: Any = None) -> None:
        """Initialize scheduler.

        Parameters
        ----------
        logger
            Optional logger for structured logging
        """
        self._jobs: dict[str, Job] = {}
        self._logger = logger
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

    def schedule_interval(
        self,
        name: str,
        interval_seconds: float,
        callable: Callable[[], Any],
        *,
        job_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Schedule job to run at regular intervals.

        Parameters
        ----------
        name
            Human-readable job name
        interval_seconds
            Interval between runs in seconds
        callable
            Function to call (no arguments)
        job_id
            Optional stable job ID (generated if not provided)
        metadata
            Optional metadata dictionary

        Returns
        -------
        str
            Job ID for managing the job
        """
        if interval_seconds <= 0:
            raise ValueError(f"Interval must be positive, got: {interval_seconds}")

        job_id = job_id or str(uuid.uuid4())
        trigger = Trigger.interval(interval_seconds)

        return self._add_job(job_id, name, trigger, callable, metadata)

    def schedule_at(
        self,
        name: str,
        target: datetime | str,
        callable: Callable[[], Any],
        *,
        job_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Schedule job to run once at specific datetime.

        Parameters
        ----------
        name
            Human-readable job name
        target
            Target datetime (datetime object or ISO format string)
        callable
            Function to call (no arguments)
        job_id
            Optional stable job ID (generated if not provided)
        metadata
            Optional metadata dictionary

        Returns
        -------
        str
            Job ID for managing the job
        """
        job_id = job_id or str(uuid.uuid4())
        trigger = Trigger.at(target)

        return self._add_job(job_id, name, trigger, callable, metadata)

    def schedule_cron(
        self,
        name: str,
        cron_expression: str,
        callable: Callable[[], Any],
        *,
        job_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Schedule job using cron expression.

        Parameters
        ----------
        name
            Human-readable job name
        cron_expression
            Cron expression (e.g., "0 */2 * * *")
        callable
            Function to call (no arguments)
        job_id
            Optional stable job ID (generated if not provided)
        metadata
            Optional metadata dictionary

        Returns
        -------
        str
            Job ID for managing the job
        """
        job_id = job_id or str(uuid.uuid4())
        trigger = Trigger.cron(cron_expression)

        return self._add_job(job_id, name, trigger, callable, metadata)

    def _add_job(
        self,
        job_id: str,
        name: str,
        trigger: Trigger,
        callable: Callable[[], Any],
        metadata: dict[str, Any] | None,
    ) -> str:
        """Add or update job (idempotent).

        Parameters
        ----------
        job_id
            Job identifier
        name
            Job name
        trigger
            Trigger configuration
        callable
            Callable to execute
        metadata
            Optional metadata

        Returns
        -------
        str
            Job ID
        """
        with self._lock:
            job = Job(
                job_id=job_id,
                name=name,
                trigger=trigger,
                callable=callable,
                metadata=metadata or {},
            )

            # Calculate first run
            job.next_run_at = job.calculate_next_run()

            self._jobs[job_id] = job

            if self._logger:
                self._logger.info(
                    f"Job scheduled: {name} ({trigger.type.value})",
                    extra={
                        "job_id": job_id,
                        "name": name,
                        "trigger_type": trigger.type.value,
                        "next_run_at": job.next_run_at,
                    },
                )

        return job_id

    def cancel(self, job_id: str) -> bool:
        """Cancel scheduled job.

        Parameters
        ----------
        job_id
            Job identifier

        Returns
        -------
        bool
            True if job was found and cancelled
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False

            job.status = JobStatus.CANCELLED

            if self._logger:
                self._logger.info(
                    f"Job cancelled: {job.name}",
                    extra={"job_id": job_id, "name": job.name},
                )

            return True

    def get_job(self, job_id: str) -> Job | None:
        """Get job by ID.

        Parameters
        ----------
        job_id
            Job identifier

        Returns
        -------
        Job or None
            Job if found
        """
        return self._jobs.get(job_id)

    def list_jobs(self, status: JobStatus | None = None) -> list[Job]:
        """List all jobs.

        Parameters
        ----------
        status
            Optional status filter

        Returns
        -------
        list[Job]
            List of jobs
        """
        with self._lock:
            jobs = list(self._jobs.values())

        if status:
            jobs = [j for j in jobs if j.status == status]

        return jobs

    def start(self) -> None:
        """Start scheduler thread."""
        if self._running:
            return

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        if self._logger:
            self._logger.info("Scheduler started")

    def stop(self, timeout: float = 5.0) -> None:
        """Stop scheduler thread.

        Parameters
        ----------
        timeout
            Maximum time to wait for thread to stop
        """
        if not self._running:
            return

        self._running = False
        self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=timeout)
            self._thread = None

        if self._logger:
            self._logger.info("Scheduler stopped")

    def _run_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                self._tick()
            except Exception as exc:
                if self._logger:
                    self._logger.error(f"Scheduler tick error: {exc}")

            # Sleep with interruptible wait
            self._stop_event.wait(timeout=0.1)

    def _tick(self) -> None:
        """Process one scheduler tick."""
        time.time()

        # Find jobs ready to run
        jobs_to_run: list[Job] = []
        with self._lock:
            for job in self._jobs.values():
                if job.should_run_now():
                    jobs_to_run.append(job)

        # Execute jobs
        for job in jobs_to_run:
            self._execute_job(job)

    def _execute_job(self, job: Job) -> None:
        """Execute a single job.

        Parameters
        ----------
        job
            Job to execute
        """
        job.status = JobStatus.RUNNING
        start_time = time.time()

        try:
            # Call the job callable
            job.callable()

            # Update job state
            job.status = JobStatus.PENDING  # Ready for next run
            job.last_run_at = start_time
            job.run_count += 1
            job.last_error = None

            # Calculate next run
            job.next_run_at = job.calculate_next_run()

            # If no next run, mark as completed
            if job.next_run_at is None:
                job.status = JobStatus.COMPLETED

            duration_ms = (time.time() - start_time) * 1000

            if self._logger:
                self._logger.info(
                    f"Job executed: {job.name}",
                    extra={
                        "job_id": job.job_id,
                        "name": job.name,
                        "duration_ms": duration_ms,
                        "run_count": job.run_count,
                        "next_run_at": job.next_run_at,
                    },
                )

        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error_count += 1
            job.last_error = str(exc)

            # For interval jobs, calculate next run despite failure
            if job.trigger.type == TriggerType.INTERVAL:
                job.last_run_at = start_time
                job.next_run_at = job.calculate_next_run()
                job.status = JobStatus.PENDING
            else:
                job.next_run_at = None

            if self._logger:
                self._logger.error(
                    f"Job failed: {job.name}",
                    extra={
                        "job_id": job.job_id,
                        "name": job.name,
                        "error": str(exc),
                        "error_count": job.error_count,
                    },
                )

    def is_running(self) -> bool:
        """Check if scheduler is running.

        Returns
        -------
        bool
            True if scheduler thread is active
        """
        return self._running

    def __enter__(self) -> Scheduler:
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.stop()


def create_scheduler(logger: Any = None) -> Scheduler:
    """Factory function to create scheduler.

    Parameters
    ----------
    logger
        Optional logger instance

    Returns
    -------
    Scheduler
        Configured scheduler
    """
    return Scheduler(logger=logger)
