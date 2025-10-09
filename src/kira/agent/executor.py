"""Agent executor with Plan → Dry-Run → Execute → Verify workflow."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ..adapters.llm import LLMAdapter, Message, Tool
from .config import AgentConfig
from .memory import ConversationMemory
from .prompts import get_system_prompt
from .rag import RAGStore
from .tools import ToolRegistry, ToolResult

logger = logging.getLogger(__name__)

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
        *,
        rag_store: RAGStore | None = None,
        memory: ConversationMemory | None = None,
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
        rag_store
            Optional RAG store for context enhancement
        memory
            Optional conversation memory
        """
        self.llm_adapter = llm_adapter
        self.tool_registry = tool_registry
        self.config = config
        self.rag_store = rag_store
        self.memory = memory or ConversationMemory()

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
        logger.debug(f"Parsing LLM response: {llm_response[:500]}...")
        try:
            data = json.loads(llm_response)
            logger.debug(f"Parsed JSON data: {data}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            raise ValueError(f"Failed to parse LLM response as JSON: {e}") from e

        steps = []
        for step_data in data.get("tool_calls", []):
            tool_name = step_data["tool"]
            logger.debug(f"Parsing tool call: {tool_name} with args {step_data.get('args', {})}")
            steps.append(
                ExecutionStep(
                    tool=tool_name,
                    args=step_data.get("args", {}),
                    dry_run=step_data.get("dry_run", False),
                )
            )

        logger.info(f"Parsed {len(steps)} steps from LLM response")
        return ExecutionPlan(
            steps=steps,
            reasoning=data.get("reasoning", ""),
            plan_description=data.get("plan", []),
        )

    def plan(self, user_request: str, *, trace_id: str | None = None) -> ExecutionPlan:
        """Generate execution plan from user request.

        Parameters
        ----------
        user_request
            Natural language request
        trace_id
            Optional trace ID for memory context

        Returns
        -------
        ExecutionPlan
            Generated execution plan
        """
        logger.info(f"Planning for user request: {user_request}")
        tools_desc = self.tool_registry.get_tools_description()
        logger.debug(f"Available tools description:\n{tools_desc}")

        # Enhance with RAG context if available
        context_snippets = []
        if self.rag_store:
            results = self.rag_store.search(user_request, top_k=3)
            for result in results:
                context_snippets.append(f"- {result.document.content[:200]}")

        rag_context = "\n".join(context_snippets) if context_snippets else ""
        if rag_context:
            tools_desc += f"\n\nRelevant context:\n{rag_context}"
            logger.debug(f"RAG context added: {len(context_snippets)} snippets")

        system_prompt = get_system_prompt(
            max_tool_calls=self.config.max_tool_calls,
            tools_description=tools_desc,
        )

        messages = [Message(role="system", content=system_prompt)]

        # Add conversation history if available
        if trace_id and self.memory.has_context(trace_id):
            context_messages = self.memory.get_context_messages(trace_id)
            messages.extend(context_messages)
            logger.debug(f"Added {len(context_messages)} messages from conversation history")

        messages.append(Message(role="user", content=user_request))

        logger.debug("Calling LLM for plan generation...")
        response = self.llm_adapter.chat(
            messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            timeout=self.config.timeout,
        )
        logger.debug(f"LLM response received: {response.content[:500]}...")

        return self._parse_plan(response.content)

    def _find_similar_tool(self, requested_tool: str) -> str | None:
        """Try to find a similar tool name if exact match not found.
        
        Handles common mistakes like:
        - create_task → task_create
        - update_task → task_update
        
        Parameters
        ----------
        requested_tool
            Tool name requested by LLM
            
        Returns
        -------
        str | None
            Corrected tool name or None if no match found
        """
        available_tools = [t.name for t in self.tool_registry.list_tools()]
        
        # Check for reversed underscore patterns (create_task → task_create)
        if "_" in requested_tool:
            parts = requested_tool.split("_")
            if len(parts) == 2:
                reversed_name = f"{parts[1]}_{parts[0]}"
                if reversed_name in available_tools:
                    logger.warning(
                        f"Tool '{requested_tool}' not found, but '{reversed_name}' exists. "
                        "Auto-correcting tool name."
                    )
                    return reversed_name
        
        # Check for similar names (fuzzy match)
        for tool_name in available_tools:
            # Simple heuristic: same words but different order or format
            requested_words = set(requested_tool.lower().replace("_", " ").split())
            tool_words = set(tool_name.lower().replace("_", " ").split())
            if requested_words == tool_words:
                logger.warning(
                    f"Tool '{requested_tool}' not found, but '{tool_name}' has same words. "
                    "Auto-correcting tool name."
                )
                return tool_name
        
        return None
    
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
        logger.debug(f"Executing step: tool={step.tool}, args={step.args}, dry_run={step.dry_run}")
        tool = self.tool_registry.get(step.tool)
        
        # Try to auto-correct if tool not found
        if not tool:
            corrected_name = self._find_similar_tool(step.tool)
            if corrected_name:
                logger.info(f"Auto-corrected '{step.tool}' to '{corrected_name}'")
                step.tool = corrected_name
                tool = self.tool_registry.get(corrected_name)
        
        if not tool:
            available_tools = [t.name for t in self.tool_registry.list_tools()]
            logger.error(f"Tool '{step.tool}' not found. Available tools: {available_tools}")
            return ToolResult.error(
                f"Tool not found: {step.tool}. Available tools: {', '.join(available_tools)}"
            )

        try:
            logger.debug(f"Calling tool {step.tool}")
            result = tool.execute(step.args, dry_run=step.dry_run)
            result.meta["trace_id"] = trace_id
            result.meta["tool"] = step.tool
            result.meta["dry_run"] = step.dry_run
            logger.debug(f"Tool {step.tool} executed successfully: {result.status}")
            return result
        except Exception as e:
            logger.error(f"Tool {step.tool} execution failed: {e}", exc_info=True)
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

    def chat_and_execute(self, user_request: str, *, trace_id: str | None = None) -> ExecutionResult:
        """Full workflow: plan → execute.

        Parameters
        ----------
        user_request
            Natural language request
        trace_id
            Optional trace ID for memory context

        Returns
        -------
        ExecutionResult
            Execution result
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())

        try:
            plan = self.plan(user_request, trace_id=trace_id)
            result = self.execute_plan(plan, trace_id=trace_id)

            # Store in memory if successful
            if result.status == "ok" and result.results:
                assistant_message = f"Executed {len(result.results)} steps successfully"
                self.memory.add_turn(trace_id, user_request, assistant_message)

            return result
        except Exception as e:
            return ExecutionResult(
                status="error",
                error=str(e),
                trace_id=trace_id,
            )
