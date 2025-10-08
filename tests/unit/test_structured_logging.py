"""Tests for structured logging and tracing (Phase 5, Point 14).

DoD: One can reconstruct the full processing path from logs.
Tests structured logging with correlation by event_id/uid.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from kira.observability.logging import (
    LogEntry,
    StructuredLogger,
    create_logger,
    log_conflict,
    log_ingress,
    log_quarantine,
    log_upsert,
    log_validation_failure,
    log_validation_success,
)


class TestLogEntry:
    """Test log entry structure."""
    
    def test_log_entry_to_json(self):
        """Test log entry converts to JSON."""
        entry = LogEntry(
            timestamp="2025-10-08T12:00:00+00:00",
            level="INFO",
            event_type="test",
            message="Test message",
            correlation_id="test-123",
            entity_id="task-001",
            event_id="evt-001",
            source="cli",
            metadata={"key": "value"}
        )
        
        json_str = entry.to_json()
        data = json.loads(json_str)
        
        assert data["timestamp"] == "2025-10-08T12:00:00+00:00"
        assert data["level"] == "INFO"
        assert data["event_type"] == "test"
        assert data["message"] == "Test message"
        assert data["correlation_id"] == "test-123"
        assert data["entity_id"] == "task-001"
        assert data["event_id"] == "evt-001"
        assert data["source"] == "cli"
        assert data["metadata"] == {"key": "value"}


class TestStructuredLogger:
    """Test structured logger (Phase 5, Point 14)."""
    
    def test_create_logger(self):
        """Test creating structured logger."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = create_logger(
                name="test",
                log_file=log_file,
                level="INFO"
            )
            
            assert logger.name == "test"
            assert logger.log_file == log_file
            assert logger.level == "INFO"
    
    def test_logger_writes_to_file(self):
        """Test logger writes to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = StructuredLogger("test", log_file=log_file)
            
            logger.info("test_event", "Test message", correlation_id="test-123")
            
            assert log_file.exists()
            content = log_file.read_text()
            assert "test_event" in content
            assert "Test message" in content
    
    def test_logger_json_format(self):
        """Test logger outputs JSON format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = StructuredLogger("test", log_file=log_file)
            
            logger.info(
                "test_event",
                "Test message",
                correlation_id="test-123",
                entity_id="task-001"
            )
            
            # Read and parse JSON
            content = log_file.read_text().strip()
            data = json.loads(content)
            
            assert data["event_type"] == "test_event"
            assert data["message"] == "Test message"
            assert data["correlation_id"] == "test-123"
            assert data["entity_id"] == "task-001"
    
    def test_logger_includes_timestamp(self):
        """Test logger includes ISO-8601 UTC timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = StructuredLogger("test", log_file=log_file)
            
            logger.info("test_event", "Test message")
            
            content = log_file.read_text().strip()
            data = json.loads(content)
            
            # Should have timestamp with UTC offset
            assert "timestamp" in data
            assert ("+00:00" in data["timestamp"] or data["timestamp"].endswith("Z"))


class TestCorrelationLogging:
    """Test correlation by event_id/uid (Phase 5, Point 14 DoD)."""
    
    def test_correlation_by_event_id(self):
        """Test events can be correlated by event_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = StructuredLogger("test", log_file=log_file)
            
            event_id = "evt-12345"
            
            # Log multiple events with same correlation_id
            logger.info("ingress", "Event received", correlation_id=event_id, event_id=event_id)
            logger.info("validation", "Event validated", correlation_id=event_id, event_id=event_id)
            logger.info("processing", "Event processed", correlation_id=event_id, event_id=event_id)
            
            # Parse logs
            lines = log_file.read_text().strip().split("\n")
            events = [json.loads(line) for line in lines]
            
            # All events should have same correlation_id
            assert len(events) == 3
            assert all(e["correlation_id"] == event_id for e in events)
            
            # Events describe processing chain
            assert events[0]["event_type"] == "ingress"
            assert events[1]["event_type"] == "validation"
            assert events[2]["event_type"] == "processing"
    
    def test_correlation_by_entity_id(self):
        """Test events can be correlated by entity_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = StructuredLogger("test", log_file=log_file)
            
            entity_id = "task-001"
            
            # Log entity lifecycle
            logger.info("validation", "Entity validated", entity_id=entity_id, correlation_id=entity_id)
            logger.info("upsert", "Entity created", entity_id=entity_id, correlation_id=entity_id)
            logger.info("update", "Entity updated", entity_id=entity_id, correlation_id=entity_id)
            
            # Parse logs
            lines = log_file.read_text().strip().split("\n")
            events = [json.loads(line) for line in lines]
            
            # All events should reference same entity
            assert len(events) == 3
            assert all(e["entity_id"] == entity_id for e in events)
            assert all(e["correlation_id"] == entity_id for e in events)


class TestProcessingPathReconstruction:
    """Test reconstruction of processing path (Phase 5, Point 14 DoD)."""
    
    def test_reconstruct_ingress_to_upsert(self):
        """Test can reconstruct full path from ingress to upsert."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = StructuredLogger("test", log_file=log_file)
            
            event_id = "evt-12345"
            entity_id = "task-001"
            
            # Simulate full processing chain
            logger.info("ingress", "Event received from telegram", 
                       event_id=event_id, source="telegram", correlation_id=event_id)
            logger.info("validation_success", "Entity validated", 
                       entity_id=entity_id, correlation_id=event_id)
            logger.info("upsert", "Entity created", 
                       entity_id=entity_id, correlation_id=event_id, 
                       metadata={"operation": "create"})
            
            # Parse logs
            lines = log_file.read_text().strip().split("\n")
            events = [json.loads(line) for line in lines]
            
            # Reconstruct chain
            assert len(events) == 3
            
            # Event 1: Ingress
            assert events[0]["event_type"] == "ingress"
            assert events[0]["source"] == "telegram"
            assert events[0]["correlation_id"] == event_id
            
            # Event 2: Validation
            assert events[1]["event_type"] == "validation_success"
            assert events[1]["entity_id"] == entity_id
            assert events[1]["correlation_id"] == event_id
            
            # Event 3: Upsert
            assert events[2]["event_type"] == "upsert"
            assert events[2]["entity_id"] == entity_id
            assert events[2]["correlation_id"] == event_id
            assert events[2]["metadata"]["operation"] == "create"
    
    def test_reconstruct_validation_failure_to_quarantine(self):
        """Test can reconstruct path when validation fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = StructuredLogger("test", log_file=log_file)
            
            entity_id = "task-bad"
            
            # Simulate failure path
            logger.info("ingress", "Event received", entity_id=entity_id, correlation_id=entity_id)
            logger.warning("validation_failure", "Validation failed", 
                          entity_id=entity_id, correlation_id=entity_id,
                          metadata={"errors": ["Missing required field"]})
            logger.error("quarantine", "Entity quarantined", 
                        entity_id=entity_id, correlation_id=entity_id,
                        metadata={"reason": "Validation failed"})
            
            # Parse logs
            lines = log_file.read_text().strip().split("\n")
            events = [json.loads(line) for line in lines]
            
            # Verify failure chain
            assert len(events) == 3
            assert events[0]["event_type"] == "ingress"
            assert events[1]["event_type"] == "validation_failure"
            assert events[2]["event_type"] == "quarantine"
            
            # All correlated by entity_id
            assert all(e["correlation_id"] == entity_id for e in events)


class TestHelperFunctions:
    """Test helper logging functions (Phase 5, Point 14)."""
    
    def test_log_ingress(self):
        """Test log_ingress helper."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            create_logger("test", log_file=log_file)
            
            log_ingress("telegram", "evt-123", "Message received", metadata={"user": "alice"})
            
            content = log_file.read_text().strip()
            data = json.loads(content)
            
            assert data["event_type"] == "ingress"
            assert data["source"] == "telegram"
            assert data["event_id"] == "evt-123"
            assert data["metadata"]["user"] == "alice"
    
    def test_log_validation_success(self):
        """Test log_validation_success helper."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            create_logger("test", log_file=log_file)
            
            log_validation_success("task-001", "task")
            
            content = log_file.read_text().strip()
            data = json.loads(content)
            
            assert data["event_type"] == "validation_success"
            assert data["entity_id"] == "task-001"
            assert data["correlation_id"] == "task-001"
    
    def test_log_validation_failure(self):
        """Test log_validation_failure helper."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            create_logger("test", log_file=log_file)
            
            errors = ["Missing title", "Invalid status"]
            log_validation_failure("task-002", "task", errors)
            
            content = log_file.read_text().strip()
            data = json.loads(content)
            
            assert data["event_type"] == "validation_failure"
            assert data["level"] == "WARNING"
            assert data["entity_id"] == "task-002"
            assert data["metadata"]["errors"] == errors
    
    def test_log_upsert(self):
        """Test log_upsert helper."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            create_logger("test", log_file=log_file)
            
            log_upsert("task-003", "task", "create")
            
            content = log_file.read_text().strip()
            data = json.loads(content)
            
            assert data["event_type"] == "upsert"
            assert data["entity_id"] == "task-003"
            assert data["metadata"]["operation"] == "create"
    
    def test_log_conflict(self):
        """Test log_conflict helper."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            create_logger("test", log_file=log_file)
            
            log_conflict("task-004", "concurrent_update", "latest_wins")
            
            content = log_file.read_text().strip()
            data = json.loads(content)
            
            assert data["event_type"] == "conflict"
            assert data["level"] == "WARNING"
            assert data["entity_id"] == "task-004"
            assert data["metadata"]["conflict_type"] == "concurrent_update"
            assert data["metadata"]["resolution"] == "latest_wins"
    
    def test_log_quarantine(self):
        """Test log_quarantine helper."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            create_logger("test", log_file=log_file)
            
            quarantine_path = Path("/tmp/quarantine/task-005.json")
            log_quarantine("task-005", "Invalid schema", quarantine_path)
            
            content = log_file.read_text().strip()
            data = json.loads(content)
            
            assert data["event_type"] == "quarantine"
            assert data["level"] == "ERROR"
            assert data["entity_id"] == "task-005"
            assert data["metadata"]["reason"] == "Invalid schema"


class TestLogLevels:
    """Test different log levels."""
    
    def test_debug_level(self):
        """Test DEBUG level logging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = StructuredLogger("test", log_file=log_file, level="DEBUG")
            
            logger.debug("test_event", "Debug message")
            
            content = log_file.read_text().strip()
            data = json.loads(content)
            
            assert data["level"] == "DEBUG"
    
    def test_info_level(self):
        """Test INFO level logging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = StructuredLogger("test", log_file=log_file, level="INFO")
            
            logger.info("test_event", "Info message")
            
            content = log_file.read_text().strip()
            data = json.loads(content)
            
            assert data["level"] == "INFO"
    
    def test_warning_level(self):
        """Test WARNING level logging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = StructuredLogger("test", log_file=log_file, level="WARNING")
            
            logger.warning("test_event", "Warning message")
            
            content = log_file.read_text().strip()
            data = json.loads(content)
            
            assert data["level"] == "WARNING"
    
    def test_error_level(self):
        """Test ERROR level logging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = StructuredLogger("test", log_file=log_file, level="ERROR")
            
            logger.error("test_event", "Error message")
            
            content = log_file.read_text().strip()
            data = json.loads(content)
            
            assert data["level"] == "ERROR"
    
    def test_critical_level(self):
        """Test CRITICAL level logging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = StructuredLogger("test", log_file=log_file, level="CRITICAL")
            
            logger.critical("test_event", "Critical message")
            
            content = log_file.read_text().strip()
            data = json.loads(content)
            
            assert data["level"] == "CRITICAL"


class TestMetadataLogging:
    """Test metadata logging."""
    
    def test_log_with_metadata(self):
        """Test logging with custom metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = StructuredLogger("test", log_file=log_file)
            
            metadata = {
                "duration_ms": 42,
                "user": "alice",
                "tags": ["urgent", "bug"]
            }
            logger.info("test_event", "Test message", metadata=metadata)
            
            content = log_file.read_text().strip()
            data = json.loads(content)
            
            assert data["metadata"]["duration_ms"] == 42
            assert data["metadata"]["user"] == "alice"
            assert data["metadata"]["tags"] == ["urgent", "bug"]


class TestEndToEndLoggingScenarios:
    """Test end-to-end logging scenarios (Phase 5, Point 14 DoD)."""
    
    def test_successful_task_creation_chain(self):
        """Test complete logging chain for successful task creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            create_logger("test", log_file=log_file)
            
            event_id = "evt-123"
            entity_id = "task-001"
            
            # Simulate complete workflow
            log_ingress("cli", event_id, "Task creation requested", metadata={"user": "alice"})
            log_validation_success(entity_id, "task")
            log_upsert(entity_id, "task", "create")
            
            # Parse and verify
            lines = log_file.read_text().strip().split("\n")
            events = [json.loads(line) for line in lines]
            
            assert len(events) == 3
            
            # Verify chain structure
            assert events[0]["event_type"] == "ingress"
            assert events[1]["event_type"] == "validation_success"
            assert events[2]["event_type"] == "upsert"
            
            # Verify correlation
            assert events[1]["entity_id"] == entity_id
            assert events[2]["entity_id"] == entity_id
    
    def test_failed_task_creation_with_quarantine(self):
        """Test logging chain when task creation fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            create_logger("test", log_file=log_file)
            
            event_id = "evt-456"
            entity_id = "task-bad"
            
            # Simulate failure workflow
            log_ingress("telegram", event_id, "Invalid task received")
            log_validation_failure(entity_id, "task", ["Missing title", "Invalid status"])
            log_quarantine(entity_id, "Validation failed", Path("/tmp/quarantine/task-bad.json"))
            
            # Parse and verify
            lines = log_file.read_text().strip().split("\n")
            events = [json.loads(line) for line in lines]
            
            assert len(events) == 3
            
            # Verify failure chain
            assert events[0]["event_type"] == "ingress"
            assert events[1]["event_type"] == "validation_failure"
            assert events[1]["level"] == "WARNING"
            assert events[2]["event_type"] == "quarantine"
            assert events[2]["level"] == "ERROR"
    
    def test_concurrent_update_conflict_resolution(self):
        """Test logging for concurrent update conflict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            create_logger("test", log_file=log_file)
            
            entity_id = "task-001"
            
            # Simulate conflict scenario
            log_upsert(entity_id, "task", "update", metadata={"source": "user1"})
            log_conflict(entity_id, "concurrent_update", "latest_wins", 
                        metadata={"conflicting_source": "user2"})
            log_upsert(entity_id, "task", "update", metadata={"source": "user2", "final": True})
            
            # Parse and verify
            lines = log_file.read_text().strip().split("\n")
            events = [json.loads(line) for line in lines]
            
            assert len(events) == 3
            
            # Verify conflict handling chain
            assert events[0]["event_type"] == "upsert"
            assert events[1]["event_type"] == "conflict"
            assert events[2]["event_type"] == "upsert"
            
            # All events reference same entity
            assert all(e["entity_id"] == entity_id for e in events)
