"""Integration tests for agent audit logging."""

import json
import tempfile
from pathlib import Path

import pytest

from kira.agent.service import AuditLogger


class TestAuditLogger:
    """Tests for audit logging."""

    def test_logger_initialization(self):
        """Test audit logger initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_dir = Path(tmpdir) / "audit"
            logger = AuditLogger(audit_dir)

            assert logger.audit_dir.exists()

    def test_log_event(self):
        """Test logging an event."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_dir = Path(tmpdir) / "audit"
            logger = AuditLogger(audit_dir)

            event = {
                "event": "test_event",
                "data": {"key": "value"},
            }

            logger.log(event)

            # Verify log file was created
            log_files = list(audit_dir.glob("audit-*.jsonl"))
            assert len(log_files) == 1

            # Verify content
            with log_files[0].open() as f:
                lines = f.readlines()
                assert len(lines) == 1

                logged_event = json.loads(lines[0])
                assert logged_event["event"] == "test_event"
                assert "timestamp" in logged_event

    def test_log_multiple_events(self):
        """Test logging multiple events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_dir = Path(tmpdir) / "audit"
            logger = AuditLogger(audit_dir)

            events = [
                {"event": "event1", "data": {"value": 1}},
                {"event": "event2", "data": {"value": 2}},
                {"event": "event3", "data": {"value": 3}},
            ]

            for event in events:
                logger.log(event)

            # Verify all events were logged
            log_files = list(audit_dir.glob("audit-*.jsonl"))
            assert len(log_files) == 1

            with log_files[0].open() as f:
                lines = f.readlines()
                assert len(lines) == 3

                for i, line in enumerate(lines):
                    logged_event = json.loads(line)
                    assert logged_event["event"] == f"event{i+1}"

    def test_log_trace_id(self):
        """Test logging with trace_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_dir = Path(tmpdir) / "audit"
            logger = AuditLogger(audit_dir)

            event = {
                "event": "agent_execute",
                "trace_id": "test-trace-123",
                "tool": "task_create",
                "args": {"title": "Test"},
            }

            logger.log(event)

            # Verify trace_id was logged
            log_files = list(audit_dir.glob("audit-*.jsonl"))
            with log_files[0].open() as f:
                logged_event = json.loads(f.read())
                assert logged_event["trace_id"] == "test-trace-123"
