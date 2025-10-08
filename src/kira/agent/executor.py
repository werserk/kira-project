"""Agent executor with Plan → Dry-Run → Execute → Verify workflow."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ..adapters.llm import LLMAdapter, Message, Tool
from .config import AgentConfig
from .prompts import get_system_prompt
from .tools import ToolRegistry, ToolResult

__all__ = [
    "AgentExecutor",
    "ExecutionPlan",
    "ExecutionResult",
    "ExecutionStep",
]


@dataclass
class ExecutionStep:
    """Single step in execution plan."""

    tool: str
    args: dict[str, Any]
    dry_run: bool = False


@dataclass
class ExecutionPlan:
    """Execution plan from LLM."""

    steps: list[ExecutionStep]
    reasoning: str = ""
    plan_description: list[str] = field(default_factory=list)


@dataclass
class ExecutionResult:
    """Result of execution."""

    status: str  # "ok", "error", "partial"
    results: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {
            "status": self.status,
            "results": self.results,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
        }
        if self.error:
            result["error"] = self.error
        return result


class AgentExecutor:
    """Executes agent workflow: Plan → Dry-Run → Execute → Verify."""

    def __init__(
        self,
        llm_adapter: LLMAdapter,
        tool_registry: ToolRegistry,
        config: AgentConfig,
    ) -> None:
        """Initialize executor.

        Parameters
        ----------
        llm_adapter
            LLM adapter for planning
        tool_registry
            Tool registry
        config
            Agent configuration
        """
        self.llm_adapter = llm_adapter
        self.tool_registry = tool_registry
        self.config = config

    def _parse_plan(self, llm_response: str) -> ExecutionPlan:
        """Parse LLM response into execution plan.

        Parameters
        ----------
        llm_response
            LLM response text

        Returns
        -------
        ExecutionPlan
            Parsed execution plan

        Raises
        ------
        ValueError
            If response cannot be parsed
        """
        try:
            data = json.loads(llm_response)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse LLM response as JSON: {e}") from e

        steps = []
        for step_data in data.get("tool_calls", []):
            steps.append(
                ExecutionStep(
                    tool=step_data["tool"],
                    args=step_data.get("args", {}),
                    dry_run=step_data.get("dry_run", False),
                )
            )

        return ExecutionPlan(
            steps=steps,
            reasoning=data.get("reasoning", ""),
            plan_description=data.get("plan", []),
        )

    def plan(self, user_request: str) -> ExecutionPlan:
        """Generate execution plan from user request.

        Parameters
        ----------
        user_request
            Natural language request

        Returns
        -------
        ExecutionPlan
            Generated execution plan
        """
        tools_desc = self.tool_registry.get_tools_description()
        system_prompt = get_system_prompt(
            max_tool_calls=self.config.max_tool_calls,
            tools_description=tools_desc,
        )

        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_request),
        ]

        response = self.llm_adapter.chat(
            messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            timeout=self.config.timeout,
        )

        return self._parse_plan(response.content)

    def execute_step(self, step: ExecutionStep, *, trace_id: str) -> ToolResult:
        """Execute a single step.

        Parameters
        ----------
        step
            Execution step
        trace_id
            Trace ID for logging

        Returns
        -------
        ToolResult
            Step result
        """
        tool = self.tool_registry.get(step.tool)
        if not tool:
            return ToolResult.error(f"Tool not found: {step.tool}")

        try:
            result = tool.execute(step.args, dry_run=step.dry_run)
            result.meta["trace_id"] = trace_id
            result.meta["tool"] = step.tool
            result.meta["dry_run"] = step.dry_run
            return result
        except Exception as e:
            return ToolResult.error(str(e), meta={"trace_id": trace_id, "tool": step.tool})

    def execute_plan(self, plan: ExecutionPlan, *, trace_id: str | None = None) -> ExecutionResult:
        """Execute a plan.

        Parameters
        ----------
        plan
            Execution plan
        trace_id
            Optional trace ID

        Returns
        -------
        ExecutionResult
            Execution result
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())

        results = []
        has_error = False

        for step in plan.steps:
            result = self.execute_step(step, trace_id=trace_id)
            results.append(result.to_dict())

            if result.status == "error":
                has_error = True
                # Stop on first error
                break

        if has_error:
            status = "error"
        elif len(results) < len(plan.steps):
            status = "partial"
        else:
            status = "ok"

        return ExecutionResult(
            status=status,
            results=results,
            trace_id=trace_id,
        )

    def chat_and_execute(self, user_request: str) -> ExecutionResult:
        """Full workflow: plan → execute.

        Parameters
        ----------
        user_request
            Natural language request

        Returns
        -------
        ExecutionResult
            Execution result
        """
        trace_id = str(uuid.uuid4())

        try:
            plan = self.plan(user_request)
            return self.execute_plan(plan, trace_id=trace_id)
        except Exception as e:
            return ExecutionResult(
                status="error",
                error=str(e),
                trace_id=trace_id,
            )
