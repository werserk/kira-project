"""Tests for structured logging and tracing (Phase 5, Point 17)."""

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


def test_log_entry_creation():
    """Test creating log entry."""
    entry = LogEntry(
        timestamp="2025-10-08T12:00:00+00:00",
        level="INFO",
        event_type="test",
        message="Test message",
        correlation_id="test-123",
    )
    
    assert entry.timestamp == "2025-10-08T12:00:00+00:00"
    assert entry.level == "INFO"
    assert entry.event_type == "test"
    assert entry.message == "Test message"
    assert entry.correlation_id == "test-123"


def test_log_entry_to_json():
    """Test converting log entry to JSON."""
    entry = LogEntry(
        timestamp="2025-10-08T12:00:00+00:00",
        level="INFO",
        event_type="test",
        message="Test",
        entity_id="entity-123",
        metadata={"key": "value"},
    )
    
    json_str = entry.to_json()
    data = json.loads(json_str)
    
    assert data["level"] == "INFO"
    assert data["event_type"] == "test"
    assert data["entity_id"] == "entity-123"
    assert data["metadata"]["key"] == "value"


def test_structured_logger_initialization():
    """Test initializing structured logger."""
    logger = StructuredLogger("test")
    
    assert logger.name == "test"
    assert logger.level == "INFO"


def test_structured_logger_with_file():
    """Test logger with file output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"
        
        logger = StructuredLogger("test", log_file=log_file)
        logger.info("test_event", "Test message")
        
        # File should exist and contain log
        assert log_file.exists()
        content = log_file.read_text()
        assert "test_event" in content


def test_structured_logger_log_levels():
    """Test different log levels."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"
        logger = StructuredLogger("test", log_file=log_file)
        
        logger.debug("debug_event", "Debug message")
        logger.info("info_event", "Info message")
        logger.warning("warn_event", "Warning message")
        logger.error("error_event", "Error message")
        logger.critical("critical_event", "Critical message")
        
        content = log_file.read_text()
        
        # All levels should be logged (default is INFO, but file gets all)
        assert "info_event" in content
        assert "warn_event" in content
        assert "error_event" in content


def test_structured_logger_correlation_id():
    """Test DoD: Correlation by event_id/uid."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"
        logger = StructuredLogger("test", log_file=log_file)
        
        # Log with correlation ID
        logger.info(
            "test_event",
            "Message 1",
            correlation_id="corr-123",
            entity_id="entity-456",
        )
        
        logger.info(
            "test_event",
            "Message 2",
            correlation_id="corr-123",
            entity_id="entity-456",
        )
        
        content = log_file.read_text()
        
        # Both entries should have same correlation_id
        lines = content.strip().split("\n")
        entry1 = json.loads(lines[0])
        entry2 = json.loads(lines[1])
        
        assert entry1["correlation_id"] == "corr-123"
        assert entry2["correlation_id"] == "corr-123"
        assert entry1["entity_id"] == "entity-456"


def test_log_ingress():
    """Test DoD: Log ingress events."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"
        create_logger("test", log_file=log_file)
        
        log_ingress(
            source="telegram",
            event_id="evt-123",
            message="Received message",
            metadata={"user_id": "user-456"},
        )
        
        content = log_file.read_text()
        entry = json.loads(content)
        
        assert entry["event_type"] == "ingress"
        assert entry["source"] == "telegram"
        assert entry["event_id"] == "evt-123"
        assert entry["correlation_id"] == "evt-123"
        assert entry["metadata"]["user_id"] == "user-456"


def test_log_validation_success():
    """Test DoD: Log validation success."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"
        create_logger("test", log_file=log_file)
        
        log_validation_success(
            entity_id="task-123",
            entity_type="task",
        )
        
        content = log_file.read_text()
        entry = json.loads(content)
        
        assert entry["event_type"] == "validation_success"
        assert entry["entity_id"] == "task-123"
        assert entry["correlation_id"] == "task-123"
        assert "validated successfully" in entry["message"]


def test_log_validation_failure():
    """Test DoD: Log validation failures."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"
        create_logger("test", log_file=log_file)
        
        log_validation_failure(
            entity_id="task-456",
            entity_type="task",
            errors=["Missing required field: title", "Invalid status"],
        )
        
        content = log_file.read_text()
        entry = json.loads(content)
        
        assert entry["event_type"] == "validation_failure"
        assert entry["level"] == "WARNING"
        assert entry["entity_id"] == "task-456"
        assert "validation failed" in entry["message"]


def test_log_upsert():
    """Test DoD: Log upsert operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"
        create_logger("test", log_file=log_file)
        
        log_upsert(
            entity_id="task-789",
            entity_type="task",
            operation="create",
        )
        
        content = log_file.read_text()
        entry = json.loads(content)
        
        assert entry["event_type"] == "upsert"
        assert entry["entity_id"] == "task-789"
        assert entry["metadata"]["operation"] == "create"


def test_log_conflict():
    """Test DoD: Log conflicts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"
        create_logger("test", log_file=log_file)
        
        log_conflict(
            entity_id="event-123",
            conflict_type="sync",
            resolution="latest-wins",
        )
        
        content = log_file.read_text()
        entry = json.loads(content)
        
        assert entry["event_type"] == "conflict"
        assert entry["level"] == "WARNING"
        assert entry["entity_id"] == "event-123"
        assert "resolved" in entry["message"]


def test_log_quarantine():
    """Test DoD: Log quarantine events."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"
        quarantine_path = Path(tmpdir) / "quarantine" / "bad.json"
        create_logger("test", log_file=log_file)
        
        log_quarantine(
            entity_id="task-bad",
            reason="Invalid schema",
            quarantine_path=quarantine_path,
        )
        
        content = log_file.read_text()
        entry = json.loads(content)
        
        assert entry["event_type"] == "quarantine"
        assert entry["level"] == "ERROR"
        assert entry["entity_id"] == "task-bad"
        assert "quarantined" in entry["message"]


def test_dod_reconstruct_processing_chain():
    """Test DoD: Reconstruct full processing chain from logs.
    
    Scenario:
    1. Ingress from Telegram
    2. Validation success
    3. Upsert (create)
    
    Should be able to trace entire flow via correlation_id.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"
        create_logger("test", log_file=log_file)
        
        correlation_id = "task-20251008-123"
        
        # Step 1: Ingress
        log_ingress(
            source="telegram",
            event_id="evt-tg-456",
            message="Received task from Telegram",
        )
        
        # Step 2: Validation
        log_validation_success(
            entity_id=correlation_id,
            entity_type="task",
        )
        
        # Step 3: Upsert
        log_upsert(
            entity_id=correlation_id,
            entity_type="task",
            operation="create",
        )
        
        # Reconstruct chain by correlation_id
        content = log_file.read_text()
        lines = content.strip().split("\n")
        
        # Parse all entries
        entries = [json.loads(line) for line in lines]
        
        # Filter by correlation_id
        chain = [e for e in entries if e.get("correlation_id") == correlation_id]
        
        # Should have 2 entries (validation + upsert)
        assert len(chain) == 2
        assert chain[0]["event_type"] == "validation_success"
        assert chain[1]["event_type"] == "upsert"
        
        # Full processing chain reconstructed!


def test_dod_reconstruct_with_failure():
    """Test reconstructing chain with validation failure → quarantine."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"
        create_logger("test", log_file=log_file)
        
        entity_id = "task-bad-123"
        
        # Ingress
        log_ingress(source="cli", event_id="evt-cli-1", message="CLI input")
        
        # Validation failure
        log_validation_failure(
            entity_id=entity_id,
            entity_type="task",
            errors=["Missing title"],
        )
        
        # Quarantine
        log_quarantine(
            entity_id=entity_id,
            reason="Validation failed",
            quarantine_path=Path("/tmp/quarantine/task-bad-123.json"),
        )
        
        # Reconstruct failure chain
        content = log_file.read_text()
        entries = [json.loads(line) for line in content.strip().split("\n")]
        chain = [e for e in entries if e.get("entity_id") == entity_id]
        
        # Should have 2 entries (validation_failure + quarantine)
        assert len(chain) == 2
        assert chain[0]["event_type"] == "validation_failure"
        assert chain[1]["event_type"] == "quarantine"


def test_structured_logger_metadata():
    """Test metadata in log entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"
        logger = StructuredLogger("test", log_file=log_file)
        
        logger.info(
            "test",
            "Message",
            metadata={
                "key1": "value1",
                "key2": 42,
                "nested": {"a": "b"},
            },
        )
        
        content = log_file.read_text()
        entry = json.loads(content)
        
        assert entry["metadata"]["key1"] == "value1"
        assert entry["metadata"]["key2"] == 42
        assert entry["metadata"]["nested"]["a"] == "b"


def test_create_logger_factory():
    """Test factory function for creating logger."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"
        
        logger = create_logger("factory_test", log_file=log_file, level="DEBUG")
        
        assert logger.name == "factory_test"
        assert logger.level == "DEBUG"


def test_log_entry_with_all_fields():
    """Test log entry with all fields populated."""
    entry = LogEntry(
        timestamp="2025-10-08T12:00:00+00:00",
        level="INFO",
        event_type="test",
        message="Complete entry",
        correlation_id="corr-1",
        entity_id="entity-1",
        event_id="event-1",
        source="test_source",
        metadata={"extra": "data"},
    )
    
    json_str = entry.to_json()
    data = json.loads(json_str)
    
    assert data["correlation_id"] == "corr-1"
    assert data["entity_id"] == "entity-1"
    assert data["event_id"] == "event-1"
    assert data["source"] == "test_source"


def test_multiple_loggers():
    """Test multiple independent loggers."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log1 = Path(tmpdir) / "log1.log"
        log2 = Path(tmpdir) / "log2.log"
        
        logger1 = StructuredLogger("logger1", log_file=log1)
        logger2 = StructuredLogger("logger2", log_file=log2)
        
        logger1.info("event1", "Message 1")
        logger2.info("event2", "Message 2")
        
        content1 = log1.read_text()
        content2 = log2.read_text()
        
        assert "event1" in content1
        assert "event2" in content2
        assert "event2" not in content1
        assert "event1" not in content2


def test_json_parseable():
    """Test all log entries are valid JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"
        logger = StructuredLogger("test", log_file=log_file)
        
        logger.info("event1", "Message 1")
        logger.warning("event2", "Message 2", entity_id="e1")
        logger.error("event3", "Message 3", metadata={"k": "v"})
        
        content = log_file.read_text()
        lines = content.strip().split("\n")
        
        # All lines should be valid JSON
        for line in lines:
            entry = json.loads(line)  # Should not raise
            assert "timestamp" in entry
            assert "level" in entry
            assert "event_type" in entry

