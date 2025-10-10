"""Observability module for Kira.

Provides logging, tracing, and timing instrumentation.
"""

from .logging import (
                      StructuredLogger,
                      create_logger,
                      log_conflict,
                      log_ingress,
                      log_quarantine,
                      log_upsert,
                      log_validation_failure,
                      log_validation_success,
)
from .loguru_config import (
                      TimingLogger,
                      configure_loguru,
                      get_logger,
                      get_timing_logger,
                      log_process_end,
                      log_process_start,
                      log_timing,
                      timing_context,
)

__all__ = [
    # Loguru (new)
    "configure_loguru",
    "get_logger",
    "get_timing_logger",
    "timing_context",
    "log_timing",
    "log_process_start",
    "log_process_end",
    "TimingLogger",
    # Legacy structured logger
    "StructuredLogger",
    "create_logger",
    "log_ingress",
    "log_validation_success",
    "log_validation_failure",
    "log_upsert",
    "log_conflict",
    "log_quarantine",
]
