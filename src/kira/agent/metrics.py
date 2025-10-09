"""Health checks and metrics for agent.

Phase 3, Item 14: Health & metrics.
Exposes health endpoint and Prometheus-compatible metrics.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["HealthCheck", "MetricsCollector", "create_metrics_collector"]


@dataclass
class HealthCheck:
    """Health check result.

    Attributes
    ----------
    status
        Health status: "healthy", "degraded", "unhealthy"
    timestamp
        Check timestamp
    checks
        Individual check results
    metadata
        Additional metadata
    """

    status: str = "healthy"
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    checks: dict[str, dict[str, Any]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns
        -------
        dict
            Health check data
        """
        return {
            "status": self.status,
            "timestamp": self.timestamp,
            "checks": self.checks,
            "metadata": self.metadata,
        }


class MetricsCollector:
    """Collects and exposes agent metrics.

    Metrics:
    - agent_steps_total: Total steps executed
    - agent_failures_total: Total failures
    - agent_runtime_seconds: Execution time histogram
    - tool_executions_total: Per-tool execution count
    - tool_latency_seconds: Per-tool latency
    """

    def __init__(self) -> None:
        """Initialize metrics collector."""
        self.reset()

    def reset(self) -> None:
        """Reset all metrics."""
        self.steps_total = 0
        self.failures_total = 0
        self.successes_total = 0

        # Per-tool metrics
        self.tool_executions: dict[str, int] = defaultdict(int)
        self.tool_failures: dict[str, int] = defaultdict(int)
        self.tool_latencies: dict[str, list[float]] = defaultdict(list)

        # Runtime histogram buckets (in seconds)
        self.runtime_buckets = {
            0.1: 0,
            0.5: 0,
            1.0: 0,
            5.0: 0,
            10.0: 0,
            30.0: 0,
            60.0: 0,
            float("inf"): 0,
        }

        self.start_time = time.time()

    def record_step(self, success: bool = True) -> None:
        """Record a step execution.

        Parameters
        ----------
        success
            Whether step succeeded
        """
        self.steps_total += 1
        if success:
            self.successes_total += 1
        else:
            self.failures_total += 1

    def record_tool_execution(
        self,
        tool_name: str,
        latency_seconds: float,
        success: bool = True,
    ) -> None:
        """Record a tool execution.

        Parameters
        ----------
        tool_name
            Tool name
        latency_seconds
            Execution time in seconds
        success
            Whether execution succeeded
        """
        self.tool_executions[tool_name] += 1
        self.tool_latencies[tool_name].append(latency_seconds)

        if not success:
            self.tool_failures[tool_name] += 1

    def record_runtime(self, runtime_seconds: float) -> None:
        """Record a runtime measurement.

        Parameters
        ----------
        runtime_seconds
            Runtime in seconds
        """
        # Update histogram buckets
        for bucket_limit in sorted(self.runtime_buckets.keys()):
            if runtime_seconds <= bucket_limit:
                self.runtime_buckets[bucket_limit] += 1
                break

    def get_health(self) -> HealthCheck:
        """Get current health status.

        Returns
        -------
        HealthCheck
            Health check result
        """
        checks = {}

        # Check if we have any recent activity
        uptime = time.time() - self.start_time
        checks["uptime"] = {
            "status": "pass",
            "seconds": round(uptime, 2),
        }

        # Check failure rate
        total_ops = self.steps_total
        if total_ops > 0:
            failure_rate = self.failures_total / total_ops
            checks["failure_rate"] = {
                "status": "pass" if failure_rate < 0.5 else "fail",
                "rate": round(failure_rate, 3),
                "failures": self.failures_total,
                "total": total_ops,
            }
        else:
            checks["failure_rate"] = {
                "status": "pass",
                "rate": 0.0,
                "message": "No operations yet",
            }

        # Determine overall status
        failed_checks = sum(1 for check in checks.values() if check.get("status") == "fail")
        if failed_checks == 0:
            status = "healthy"
        elif failed_checks <= 1:
            status = "degraded"
        else:
            status = "unhealthy"

        return HealthCheck(
            status=status,
            checks=checks,
            metadata={
                "steps_total": self.steps_total,
                "failures_total": self.failures_total,
                "successes_total": self.successes_total,
            },
        )

    def get_prometheus_metrics(self) -> str:
        """Get metrics in Prometheus text format.

        Returns
        -------
        str
            Prometheus-formatted metrics
        """
        lines = []

        # agent_steps_total
        lines.append("# HELP agent_steps_total Total number of agent steps executed")
        lines.append("# TYPE agent_steps_total counter")
        lines.append(f"agent_steps_total {self.steps_total}")

        # agent_failures_total
        lines.append("# HELP agent_failures_total Total number of agent failures")
        lines.append("# TYPE agent_failures_total counter")
        lines.append(f"agent_failures_total {self.failures_total}")

        # agent_successes_total
        lines.append("# HELP agent_successes_total Total number of agent successes")
        lines.append("# TYPE agent_successes_total counter")
        lines.append(f"agent_successes_total {self.successes_total}")

        # agent_runtime_seconds histogram
        lines.append("# HELP agent_runtime_seconds Agent execution runtime histogram")
        lines.append("# TYPE agent_runtime_seconds histogram")
        cumulative = 0
        for bucket_limit, count in sorted(self.runtime_buckets.items()):
            cumulative += count
            lines.append(f'agent_runtime_seconds_bucket{{le="{bucket_limit}"}} {cumulative}')

        # tool_executions_total per tool
        lines.append("# HELP tool_executions_total Total tool executions by tool name")
        lines.append("# TYPE tool_executions_total counter")
        for tool_name, count in self.tool_executions.items():
            lines.append(f'tool_executions_total{{tool="{tool_name}"}} {count}')

        # tool_failures_total per tool
        lines.append("# HELP tool_failures_total Total tool failures by tool name")
        lines.append("# TYPE tool_failures_total counter")
        for tool_name, count in self.tool_failures.items():
            lines.append(f'tool_failures_total{{tool="{tool_name}"}} {count}')

        # tool_latency_seconds per tool (average)
        lines.append("# HELP tool_latency_seconds Average tool latency by tool name")
        lines.append("# TYPE tool_latency_seconds gauge")
        for tool_name, latencies in self.tool_latencies.items():
            if latencies:
                avg_latency = sum(latencies) / len(latencies)
                lines.append(f'tool_latency_seconds{{tool="{tool_name}"}} {avg_latency:.6f}')

        return "\n".join(lines) + "\n"

    def get_summary(self) -> dict[str, Any]:
        """Get metrics summary.

        Returns
        -------
        dict
            Metrics summary
        """
        summary: dict[str, Any] = {
            "steps_total": self.steps_total,
            "failures_total": self.failures_total,
            "successes_total": self.successes_total,
            "uptime_seconds": round(time.time() - self.start_time, 2),
        }

        if self.steps_total > 0:
            summary["success_rate"] = round(self.successes_total / self.steps_total, 3)
            summary["failure_rate"] = round(self.failures_total / self.steps_total, 3)

        # Per-tool summary
        tool_summary = {}
        for tool_name in self.tool_executions:
            latencies = self.tool_latencies[tool_name]
            tool_summary[tool_name] = {
                "executions": self.tool_executions[tool_name],
                "failures": self.tool_failures.get(tool_name, 0),
                "avg_latency_ms": round(sum(latencies) / len(latencies) * 1000, 2) if latencies else 0,
                "min_latency_ms": round(min(latencies) * 1000, 2) if latencies else 0,
                "max_latency_ms": round(max(latencies) * 1000, 2) if latencies else 0,
            }

        summary["tools"] = tool_summary
        return summary


def create_metrics_collector() -> MetricsCollector:
    """Factory function to create metrics collector.

    Returns
    -------
    MetricsCollector
        Configured metrics collector
    """
    collector = MetricsCollector()
    logger.info("Created metrics collector")
    return collector

