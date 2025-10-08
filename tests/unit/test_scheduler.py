"""Tests for Scheduler implementation (ADR-005)."""

from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kira.core.scheduler import Job, JobStatus, Scheduler, Trigger, TriggerType, create_scheduler


class TestTrigger:
    def test_interval_trigger(self):
        """Test creating interval trigger."""
        trigger = Trigger.interval(60)

        assert trigger.type == TriggerType.INTERVAL
        assert trigger.interval_seconds == 60

    def test_at_trigger_datetime(self):
        """Test creating at trigger with datetime."""
        target = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        trigger = Trigger.at(target)

        assert trigger.type == TriggerType.AT
        assert trigger.target_datetime == target

    def test_at_trigger_string(self):
        """Test creating at trigger with ISO string."""
        target_str = "2025-01-01T12:00:00+00:00"
        trigger = Trigger.at(target_str)

        assert trigger.type == TriggerType.AT
        assert trigger.target_datetime is not None

    def test_cron_trigger(self):
        """Test creating cron trigger."""
        trigger = Trigger.cron("0 */2 * * *")

        assert trigger.type == TriggerType.CRON
        assert trigger.cron_expression == "0 */2 * * *"


class TestJob:
    def test_job_creation(self):
        """Test creating job."""
        trigger = Trigger.interval(60)
        job = Job(
            job_id="test-job",
            name="Test Job",
            trigger=trigger,
            callable=lambda: None,
        )

        assert job.job_id == "test-job"
        assert job.name == "Test Job"
        assert job.status == JobStatus.PENDING
        assert job.run_count == 0

    def test_should_run_now_pending(self):
        """Test should_run_now for pending job."""
        job = Job(
            job_id="test",
            name="Test",
            trigger=Trigger.interval(60),
            callable=lambda: None,
            next_run_at=time.time() - 1,  # Past time
        )

        assert job.should_run_now() is True

    def test_should_run_now_future(self):
        """Test should_run_now for future job."""
        job = Job(
            job_id="test",
            name="Test",
            trigger=Trigger.interval(60),
            callable=lambda: None,
            next_run_at=time.time() + 3600,  # Future time
        )

        assert job.should_run_now() is False

    def test_should_run_now_cancelled(self):
        """Test should_run_now for cancelled job."""
        job = Job(
            job_id="test",
            name="Test",
            trigger=Trigger.interval(60),
            callable=lambda: None,
            status=JobStatus.CANCELLED,
            next_run_at=time.time() - 1,
        )

        assert job.should_run_now() is False

    def test_calculate_next_run_interval(self):
        """Test calculating next run for interval trigger."""
        job = Job(
            job_id="test",
            name="Test",
            trigger=Trigger.interval(60),
            callable=lambda: None,
        )

        next_run = job.calculate_next_run()
        assert next_run is not None
        assert next_run <= time.time() + 1

        job.last_run_at = time.time()
        next_run = job.calculate_next_run()
        assert next_run is not None
        assert next_run > time.time() + 59

    def test_calculate_next_run_at(self):
        """Test calculating next run for at trigger."""
        target = datetime.now(timezone.utc) + timedelta(hours=1)
        job = Job(
            job_id="test",
            name="Test",
            trigger=Trigger.at(target),
            callable=lambda: None,
        )

        next_run = job.calculate_next_run()
        assert next_run is not None
        assert next_run == target.timestamp()

        # After execution, no more runs
        job.last_run_at = time.time()
        next_run = job.calculate_next_run()
        assert next_run is None


class TestScheduler:
    def test_create_scheduler(self):
        """Test creating scheduler."""
        scheduler = Scheduler()

        assert scheduler is not None
        assert scheduler.is_running() is False

    def test_schedule_interval(self):
        """Test scheduling interval job."""
        scheduler = Scheduler()
        calls: list[int] = []

        job_id = scheduler.schedule_interval("test", 1.0, lambda: calls.append(1))

        assert job_id is not None
        job = scheduler.get_job(job_id)
        assert job is not None
        assert job.name == "test"
        assert job.trigger.type == TriggerType.INTERVAL

    def test_schedule_at(self):
        """Test scheduling at job."""
        scheduler = Scheduler()
        target = datetime.now(timezone.utc) + timedelta(seconds=5)

        job_id = scheduler.schedule_at("test", target, lambda: None)

        job = scheduler.get_job(job_id)
        assert job is not None
        assert job.trigger.type == TriggerType.AT

    def test_schedule_cron(self):
        """Test scheduling cron job."""
        scheduler = Scheduler()

        job_id = scheduler.schedule_cron("test", "0 */2 * * *", lambda: None)

        job = scheduler.get_job(job_id)
        assert job is not None
        assert job.trigger.type == TriggerType.CRON

    def test_schedule_interval_invalid(self):
        """Test scheduling with invalid interval."""
        scheduler = Scheduler()

        with pytest.raises(ValueError):
            scheduler.schedule_interval("test", 0, lambda: None)

        with pytest.raises(ValueError):
            scheduler.schedule_interval("test", -1, lambda: None)

    def test_cancel_job(self):
        """Test cancelling job."""
        scheduler = Scheduler()

        job_id = scheduler.schedule_interval("test", 60, lambda: None)
        assert scheduler.cancel(job_id) is True

        job = scheduler.get_job(job_id)
        assert job.status == JobStatus.CANCELLED

    def test_cancel_nonexistent(self):
        """Test cancelling nonexistent job."""
        scheduler = Scheduler()

        assert scheduler.cancel("nonexistent") is False

    def test_list_jobs(self):
        """Test listing jobs."""
        scheduler = Scheduler()

        scheduler.schedule_interval("job1", 60, lambda: None)
        scheduler.schedule_interval("job2", 120, lambda: None)

        jobs = scheduler.list_jobs()
        assert len(jobs) == 2

    def test_list_jobs_by_status(self):
        """Test listing jobs by status."""
        scheduler = Scheduler()

        job_id1 = scheduler.schedule_interval("job1", 60, lambda: None)
        scheduler.schedule_interval("job2", 120, lambda: None)

        scheduler.cancel(job_id1)

        pending = scheduler.list_jobs(JobStatus.PENDING)
        cancelled = scheduler.list_jobs(JobStatus.CANCELLED)

        assert len(pending) == 1
        assert len(cancelled) == 1

    def test_start_stop(self):
        """Test starting and stopping scheduler."""
        scheduler = Scheduler()

        assert scheduler.is_running() is False

        scheduler.start()
        assert scheduler.is_running() is True

        scheduler.stop()
        assert scheduler.is_running() is False

    def test_job_execution(self):
        """Test job execution."""
        scheduler = Scheduler()
        calls: list[int] = []

        scheduler.schedule_interval("test", 0.1, lambda: calls.append(1))

        scheduler.start()
        time.sleep(0.3)  # Allow time for execution
        scheduler.stop()

        assert len(calls) >= 2  # Should run at least twice

    def test_job_execution_at(self):
        """Test at job execution."""
        scheduler = Scheduler()
        calls: list[int] = []

        target = datetime.now(timezone.utc) + timedelta(seconds=0.2)
        scheduler.schedule_at("test", target, lambda: calls.append(1))

        scheduler.start()
        time.sleep(0.5)
        scheduler.stop()

        assert len(calls) == 1  # Should run only once

    def test_job_failure_handling(self):
        """Test job failure handling."""
        scheduler = Scheduler()
        attempts: list[int] = []

        def failing_job() -> None:
            attempts.append(1)
            raise ValueError("Test error")

        job_id = scheduler.schedule_interval("test", 0.1, failing_job)

        scheduler.start()
        time.sleep(0.3)
        scheduler.stop()

        job = scheduler.get_job(job_id)
        assert job.error_count > 0
        assert job.last_error is not None
        # Job should continue running despite failures for interval jobs
        assert job.status == JobStatus.PENDING

    def test_context_manager(self):
        """Test scheduler as context manager."""
        calls: list[int] = []

        with Scheduler() as scheduler:
            scheduler.schedule_interval("test", 0.1, lambda: calls.append(1))
            time.sleep(0.25)

        assert len(calls) >= 2
        assert scheduler.is_running() is False

    def test_idempotent_scheduling(self):
        """Test idempotent scheduling with same job_id."""
        scheduler = Scheduler()
        calls: list[int] = []

        scheduler.schedule_interval("test", 1.0, lambda: calls.append(1), job_id="my-job")
        scheduler.schedule_interval("test", 2.0, lambda: calls.append(2), job_id="my-job")

        jobs = scheduler.list_jobs()
        assert len(jobs) == 1  # Should replace, not duplicate

        job = scheduler.get_job("my-job")
        assert job.trigger.interval_seconds == 2.0

    def test_metadata(self):
        """Test job metadata."""
        scheduler = Scheduler()

        job_id = scheduler.schedule_interval("test", 60, lambda: None, metadata={"priority": "high", "owner": "admin"})

        job = scheduler.get_job(job_id)
        assert job.metadata["priority"] == "high"
        assert job.metadata["owner"] == "admin"


class TestSchedulerFactory:
    def test_create_scheduler(self):
        """Test factory function."""
        scheduler = create_scheduler()

        assert isinstance(scheduler, Scheduler)
