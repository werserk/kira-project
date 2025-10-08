"""Tests for structured logging and telemetry (ADR-015)."""

import json
import logging
import tempfile
from pathlib import Path

from kira.core.telemetry import (
    StructuredFormatter,
    TelemetryLogger,
    create_logger,
    create_span_id,
    create_trace_id,
)


class TestTraceIdGeneration:
    """Test trace and span ID generation."""

    def test_create_trace_id(self):
        """Test trace ID creation."""
        trace_id = create_trace_id()

        assert isinstance(trace_id, str)
        assert len(trace_id) > 0
        # Should be UUID format
        assert "-" in trace_id

    def test_trace_ids_are_unique(self):
        """Test trace IDs are unique."""
        trace_ids = [create_trace_id() for _ in range(100)]

        assert len(set(trace_ids)) == 100

    def test_create_span_id(self):
        """Test span ID creation."""
        span_id = create_span_id()

        assert isinstance(span_id, str)
        assert len(span_id) == 8  # Short span ID

    def test_span_ids_are_unique(self):
        """Test span IDs are unique (mostly)."""
        span_ids = [create_span_id() for _ in range(100)]

        # Should have high uniqueness (may have collisions but unlikely)
        assert len(set(span_ids)) >= 95


class TestStructuredFormatter:
    """Test JSONL formatter."""

    def setup_method(self):
        """Setup test fixtures."""
        self.formatter = StructuredFormatter()

    def test_format_basic_record(self):
        """Test formatting basic log record."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        record.component = "test-component"

        result = self.formatter.format(record)

        # Parse JSON
        log_entry = json.loads(result)

        assert log_entry["level"] == "INFO"
        assert log_entry["component"] == "test-component"
        assert log_entry["message"] == "Test message"
        assert "timestamp" in log_entry

    def test_format_with_trace_id(self):
        """Test formatting with trace ID."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )

        record.component = "test"
        record.trace_id = "trace-123"
        record.span_id = "span-456"

        result = self.formatter.format(record)
        log_entry = json.loads(result)

        assert log_entry["trace_id"] == "trace-123"
        assert log_entry["span_id"] == "span-456"

    def test_format_with_latency(self):
        """Test formatting with latency."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Operation completed",
            args=(),
            exc_info=None,
        )

        record.component = "test"
        record.latency_ms = 123.45
        record.outcome = "success"

        result = self.formatter.format(record)
        log_entry = json.loads(result)

        assert log_entry["latency_ms"] == 123.45
        assert log_entry["outcome"] == "success"

    def test_format_with_context_fields(self):
        """Test formatting with context fields."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )

        record.component = "test"
        record.plugin = "test-plugin"
        record.entity_id = "task-123"
        record.chat_id = "chat-456"

        result = self.formatter.format(record)
        log_entry = json.loads(result)

        assert log_entry["plugin"] == "test-plugin"
        assert log_entry["entity_id"] == "task-123"
        assert log_entry["chat_id"] == "chat-456"

    def test_format_with_error(self):
        """Test formatting with error."""
        try:
            raise ValueError("Test error")
        except ValueError:
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error occurred",
                args=(),
                exc_info=True,
            )

            record.component = "test"

            result = self.formatter.format(record)
            log_entry = json.loads(result)

            assert "error" in log_entry
            assert log_entry["error"]["type"] == "ValueError"
            assert log_entry["error"]["message"] == "Test error"
            assert "stack" in log_entry["error"]

    def test_format_with_refs(self):
        """Test formatting with references."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )

        record.component = "test"
        record.refs = ["task-1", "task-2", "event-3"]

        result = self.formatter.format(record)
        log_entry = json.loads(result)

        assert log_entry["refs"] == ["task-1", "task-2", "event-3"]


class TestTelemetryLogger:
    """Test telemetry logger."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_dir = Path(self.temp_dir)

    def test_logger_initialization(self):
        """Test logger initialization."""
        logger = TelemetryLogger(
            component="test-component",
            log_dir=self.log_dir,
        )

        assert logger.component == "test-component"
        assert logger.log_dir == self.log_dir

    def test_logger_creates_log_file(self):
        """Test logger creates log file."""
        logger = TelemetryLogger(
            component="test-component",
            log_dir=self.log_dir,
        )

        logger.info("Test message")

        # Check file was created
        log_files = list(self.log_dir.rglob("*.jsonl"))
        assert len(log_files) > 0

    def test_logger_writes_jsonl(self):
        """Test logger writes JSONL format."""
        logger = TelemetryLogger(
            component="test-component",
            log_dir=self.log_dir,
        )

        logger.info("Test message", trace_id="test-trace")

        # Read log file
        log_files = list(self.log_dir.rglob("*.jsonl"))
        log_file = log_files[0]

        with open(log_file) as f:
            line = f.readline()

        log_entry = json.loads(line)

        assert log_entry["message"] == "Test message"
        assert log_entry["trace_id"] == "test-trace"

    def test_logger_categorizes_core(self):
        """Test logger categorizes core components."""
        logger = TelemetryLogger(
            component="kira-core",
            log_dir=self.log_dir,
        )

        logger.info("Test")

        # Should create in core/
        assert (self.log_dir / "core").exists()

    def test_logger_categorizes_adapter(self):
        """Test logger categorizes adapters."""
        logger = TelemetryLogger(
            component="telegram-adapter",
            log_dir=self.log_dir,
        )

        logger.info("Test")

        # Should create in adapters/
        assert (self.log_dir / "adapters").exists()

    def test_logger_categorizes_plugin(self):
        """Test logger categorizes plugins."""
        logger = TelemetryLogger(
            component="inbox-plugin",
            log_dir=self.log_dir,
        )

        logger.info("Test")

        # Should create in plugins/
        assert (self.log_dir / "plugins").exists()

    def test_logger_categorizes_pipeline(self):
        """Test logger categorizes pipelines."""
        logger = TelemetryLogger(
            component="sync-pipeline",
            log_dir=self.log_dir,
        )

        logger.info("Test")

        # Should create in pipelines/
        assert (self.log_dir / "pipelines").exists()

    def test_info_logging(self):
        """Test info level logging."""
        logger = TelemetryLogger(
            component="test",
            log_dir=self.log_dir,
        )

        logger.info("Info message", entity_id="task-123")

        log_files = list(self.log_dir.rglob("*.jsonl"))
        with open(log_files[0]) as f:
            log_entry = json.loads(f.readline())

        assert log_entry["level"] == "INFO"
        assert log_entry["message"] == "Info message"
        assert log_entry["entity_id"] == "task-123"

    def test_error_logging(self):
        """Test error level logging."""
        logger = TelemetryLogger(
            component="test",
            log_dir=self.log_dir,
        )

        logger.error(
            "Error message",
            error={"type": "ValueError", "message": "Bad value"},
        )

        log_files = list(self.log_dir.rglob("*.jsonl"))
        with open(log_files[0]) as f:
            log_entry = json.loads(f.readline())

        assert log_entry["level"] == "ERROR"
        assert log_entry["error"]["type"] == "ValueError"

    def test_warning_logging(self):
        """Test warning level logging."""
        logger = TelemetryLogger(
            component="test",
            log_dir=self.log_dir,
        )

        logger.warning("Warning message")

        log_files = list(self.log_dir.rglob("*.jsonl"))
        with open(log_files[0]) as f:
            log_entry = json.loads(f.readline())

        assert log_entry["level"] == "WARNING"

    def test_debug_logging(self):
        """Test debug level logging."""
        logger = TelemetryLogger(
            component="test",
            log_dir=self.log_dir,
            level=logging.DEBUG,
        )

        logger.debug("Debug message")

        log_files = list(self.log_dir.rglob("*.jsonl"))
        with open(log_files[0]) as f:
            log_entry = json.loads(f.readline())

        assert log_entry["level"] == "DEBUG"

    def test_default_trace_id(self):
        """Test default trace ID for logger."""
        logger = TelemetryLogger(
            component="test",
            log_dir=self.log_dir,
            trace_id="default-trace",
        )

        logger.info("Message")

        log_files = list(self.log_dir.rglob("*.jsonl"))
        with open(log_files[0]) as f:
            log_entry = json.loads(f.readline())

        assert log_entry["trace_id"] == "default-trace"

    def test_override_trace_id(self):
        """Test overriding trace ID."""
        logger = TelemetryLogger(
            component="test",
            log_dir=self.log_dir,
            trace_id="default-trace",
        )

        logger.info("Message", trace_id="override-trace")

        log_files = list(self.log_dir.rglob("*.jsonl"))
        with open(log_files[0]) as f:
            log_entry = json.loads(f.readline())

        assert log_entry["trace_id"] == "override-trace"


class TestSpanContext:
    """Test span context manager."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_dir = Path(self.temp_dir)
        self.logger = TelemetryLogger(
            component="test",
            log_dir=self.log_dir,
        )

    def test_span_context_success(self):
        """Test span context for successful operation."""
        with self.logger.span("test_operation", trace_id="test-trace"):
            pass

        # Read logs
        log_files = list(self.log_dir.rglob("*.jsonl"))
        with open(log_files[0]) as f:
            lines = f.readlines()

        assert len(lines) == 2  # Start and complete

        start_log = json.loads(lines[0])
        complete_log = json.loads(lines[1])

        assert "Started: test_operation" in start_log["message"]
        assert "Completed: test_operation" in complete_log["message"]
        assert complete_log["outcome"] == "success"
        assert "latency_ms" in complete_log

    def test_span_context_failure(self):
        """Test span context for failed operation."""
        try:
            with self.logger.span("test_operation"):
                raise ValueError("Test error")
        except ValueError:
            pass

        # Read logs
        log_files = list(self.log_dir.rglob("*.jsonl"))
        with open(log_files[0]) as f:
            lines = f.readlines()

        complete_log = json.loads(lines[-1])

        assert "Failed: test_operation" in complete_log["message"]
        assert complete_log["outcome"] == "failure"
        assert complete_log["error"]["type"] == "ValueError"

    def test_span_generates_span_id(self):
        """Test span generates span ID."""
        with self.logger.span("test_operation") as span:
            assert span.span_id is not None
            assert len(span.span_id) == 8

    def test_span_propagates_trace_id(self):
        """Test span propagates trace ID."""
        with self.logger.span("test_operation", trace_id="my-trace") as span:
            assert span.trace_id == "my-trace"

        log_files = list(self.log_dir.rglob("*.jsonl"))
        with open(log_files[0]) as f:
            log_entry = json.loads(f.readline())

        assert log_entry["trace_id"] == "my-trace"

    def test_span_with_context_fields(self):
        """Test span with additional context."""
        with self.logger.span(
            "test_operation",
            entity_id="task-123",
            user_id="user-456",
        ):
            pass

        log_files = list(self.log_dir.rglob("*.jsonl"))
        with open(log_files[0]) as f:
            log_entry = json.loads(f.readline())

        assert log_entry["entity_id"] == "task-123"
        assert log_entry["user_id"] == "user-456"

    def test_span_set_outcome(self):
        """Test setting span outcome explicitly."""
        with self.logger.span("test_operation") as span:
            span.set_outcome("timeout")

        log_files = list(self.log_dir.rglob("*.jsonl"))
        with open(log_files[0]) as f:
            lines = f.readlines()

        complete_log = json.loads(lines[-1])
        assert complete_log["outcome"] == "timeout"

    def test_nested_spans(self):
        """Test nested span contexts."""
        with self.logger.span("outer_operation") as outer_span:
            outer_trace = outer_span.trace_id

            with self.logger.span("inner_operation", trace_id=outer_trace):
                pass

        # Both operations should share trace ID
        log_files = list(self.log_dir.rglob("*.jsonl"))
        with open(log_files[0]) as f:
            lines = f.readlines()

        logs = [json.loads(line) for line in lines]

        assert len(logs) == 4  # 2 starts + 2 completes
        assert all(log["trace_id"] == outer_trace for log in logs)


class TestFactoryFunction:
    """Test create_logger factory function."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_dir = Path(self.temp_dir)

    def test_create_logger(self):
        """Test factory creates logger."""
        logger = create_logger(
            component="test-component",
            log_dir=self.log_dir,
        )

        assert isinstance(logger, TelemetryLogger)
        assert logger.component == "test-component"

    def test_create_logger_with_defaults(self):
        """Test factory with default arguments."""
        logger = create_logger(component="test")

        assert isinstance(logger, TelemetryLogger)
        assert logger.component == "test"

    def test_create_logger_with_trace_id(self):
        """Test factory with trace ID."""
        logger = create_logger(
            component="test",
            trace_id="test-trace",
            log_dir=self.log_dir,
        )

        assert logger.trace_id == "test-trace"


class TestEndToEndTraceability:
    """Test end-to-end traceability (ADR-015 requirement)."""

    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_dir = Path(self.temp_dir)

    def test_trace_through_multiple_components(self):
        """Test tracing request through multiple components."""
        trace_id = create_trace_id()

        # Component 1: Core
        core_logger = create_logger(
            component="kira-core",
            log_dir=self.log_dir,
        )

        with core_logger.span("process_request", trace_id=trace_id):
            core_logger.info("Request received", trace_id=trace_id)

        # Component 2: Plugin
        plugin_logger = create_logger(
            component="inbox-plugin",
            log_dir=self.log_dir,
        )

        with plugin_logger.span("normalize_content", trace_id=trace_id):
            plugin_logger.info("Content normalized", trace_id=trace_id)

        # Component 3: Adapter
        adapter_logger = create_logger(
            component="telegram-adapter",
            log_dir=self.log_dir,
        )

        with adapter_logger.span("send_response", trace_id=trace_id):
            adapter_logger.info("Response sent", trace_id=trace_id)

        # Collect all logs with this trace_id
        all_logs = []

        for log_file in self.log_dir.rglob("*.jsonl"):
            with open(log_file) as f:
                for line in f:
                    log = json.loads(line)
                    if log.get("trace_id") == trace_id:
                        all_logs.append(log)

        # Should have logs from all 3 components
        assert len(all_logs) >= 6  # 3 spans × 2 logs (start + complete)

        components = {log["component"] for log in all_logs}
        assert "kira-core" in components
        assert "inbox-plugin" in components
        assert "telegram-adapter" in components

        # All logs should have the same trace_id
        assert all(log["trace_id"] == trace_id for log in all_logs)

    def test_reconstruct_request_flow(self):
        """Test reconstructing complete request flow from logs."""
        trace_id = create_trace_id()

        logger = create_logger(component="test", log_dir=self.log_dir)

        # Simulate request flow
        with logger.span("handle_request", trace_id=trace_id, request_id="req-1"):
            logger.info("Validating input", trace_id=trace_id)

            with logger.span("validate", trace_id=trace_id):
                pass

            logger.info("Processing", trace_id=trace_id)

            with logger.span("process", trace_id=trace_id):
                pass

            logger.info("Responding", trace_id=trace_id)

        # Read all logs
        log_files = list(self.log_dir.rglob("*.jsonl"))
        with open(log_files[0]) as f:
            all_logs = [json.loads(line) for line in f.readlines()]

        # Filter by trace_id
        trace_logs = [log for log in all_logs if log.get("trace_id") == trace_id]

        # Should be able to reconstruct flow
        assert len(trace_logs) >= 7
        assert trace_logs[0]["message"].startswith("Started: handle_request")
        assert trace_logs[-1]["message"].startswith("Completed: handle_request")
