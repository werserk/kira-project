"""LangGraph-based executor for Kira agent.

Provides a high-level interface to the LangGraph execution engine.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..adapters.llm import LLMAdapter
    from .state import AgentState
    from .tools import ToolRegistry

logger = logging.getLogger(__name__)

__all__ = ["LangGraphExecutor", "ExecutionResult"]


class ExecutionResult:
    """Result of LangGraph execution."""

    def __init__(self, state: AgentState | dict[str, Any]) -> None:
        """Initialize from final state.

        Parameters
        ----------
        state
            Final agent state after graph execution (AgentState or dict)
        """
        # LangGraph returns dict, not dataclass
        if isinstance(state, dict):
            from .state import AgentState as AgentStateClass
            state = AgentStateClass.from_dict(state)

        self.state = state
        self.trace_id = state.trace_id
        self.status = state.status
        self.error = state.error
        self.tool_results = state.tool_results
        self.budget_used = state.budget
        self.response = state.response  # Natural language response

    @property
    def success(self) -> bool:
        """Check if execution was successful."""
        return self.status not in ("error", "halt") and self.error is None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "trace_id": self.trace_id,
            "status": self.status,
            "error": self.error,
            "tool_results": self.tool_results,
            "budget": self.budget_used.to_dict(),
            "success": self.success,
            "response": self.response,  # NL response for user
        }


class LangGraphExecutor:
    """LangGraph-based agent executor.

    This is the Phase 1 implementation of the LangGraph integration.
    It provides plan → reflect → tool → verify workflow with resource budgets.
    """

    def __init__(
        self,
        llm_adapter: LLMAdapter,
        tool_registry: ToolRegistry,
        *,
        max_steps: int = 10,
        max_tokens: int = 10000,
        max_wall_time: float = 300.0,
        enable_reflection: bool = True,
        enable_verification: bool = True,
    ) -> None:
        """Initialize LangGraph executor.

        Parameters
        ----------
        llm_adapter
            LLM adapter for planning and reflection
        tool_registry
            Registry of available tools
        max_steps
            Maximum number of tool execution steps
        max_tokens
            Maximum tokens to use
        max_wall_time
            Maximum wall time in seconds
        enable_reflection
            Enable reflection node
        enable_verification
            Enable verification node
        """
        self.llm_adapter = llm_adapter
        self.tool_registry = tool_registry
        self.max_steps = max_steps
        self.max_tokens = max_tokens
        self.max_wall_time = max_wall_time
        self.enable_reflection = enable_reflection
        self.enable_verification = enable_verification

        # Build graph on initialization
        tools_desc = tool_registry.get_tools_description()
        from .graph import build_agent_graph

        self.graph = build_agent_graph(llm_adapter, tool_registry, tools_desc)
        logger.info("LangGraph executor initialized")

    def execute(
        self,
        user_request: str,
        *,
        trace_id: str | None = None,
        user: str = "default",
        dry_run: bool = False,
    ) -> ExecutionResult:
        """Execute user request through LangGraph.

        Parameters
        ----------
        user_request
            Natural language request
        trace_id
            Optional trace ID for correlation
        user
            User identifier
        dry_run
            If True, run all tools in dry-run mode

        Returns
        -------
        ExecutionResult
            Execution result with final state
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())

        logger.info(f"[{trace_id}] Executing request: {user_request[:100]}...")

        # Create initial state
        from .state import AgentState, Budget, ContextFlags

        state = AgentState(
            trace_id=trace_id,
            user=user,
            messages=[{"role": "user", "content": user_request}],
            budget=Budget(
                max_steps=self.max_steps,
                max_tokens=self.max_tokens,
                max_wall_time_seconds=self.max_wall_time,
            ),
            flags=ContextFlags(
                dry_run=dry_run,
                enable_reflection=self.enable_reflection,
                enable_verification=self.enable_verification,
            ),
        )

        # Execute graph
        final_state = self.graph.invoke(state)

        result = ExecutionResult(final_state)
        logger.info(f"[{trace_id}] Execution completed: success={result.success}, status={result.status}")

        return result

    def stream(
        self,
        user_request: str,
        *,
        trace_id: str | None = None,
        user: str = "default",
        dry_run: bool = False,
    ) -> Any:  # type: ignore[misc]
        """Stream execution progress step by step.

        Parameters
        ----------
        user_request
            Natural language request
        trace_id
            Optional trace ID for correlation
        user
            User identifier
        dry_run
            If True, run all tools in dry-run mode

        Yields
        ------
        tuple[str, ExecutionResult]
            Node name and current execution result for each step
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())

        logger.info(f"[{trace_id}] Starting streaming execution: {user_request[:100]}...")

        # Create initial state
        from .state import AgentState, Budget, ContextFlags

        state = AgentState(
            trace_id=trace_id,
            user=user,
            messages=[{"role": "user", "content": user_request}],
            budget=Budget(
                max_steps=self.max_steps,
                max_tokens=self.max_tokens,
                max_wall_time_seconds=self.max_wall_time,
            ),
            flags=ContextFlags(
                dry_run=dry_run,
                enable_reflection=self.enable_reflection,
                enable_verification=self.enable_verification,
            ),
        )

        # Stream graph execution
        for node_name, updated_state in self.graph.stream(state):
            result = ExecutionResult(updated_state)
            yield node_name, result

    def get_graph_diagram(self) -> str:
        """Get Mermaid diagram of the execution graph.

        Returns
        -------
        str
            Mermaid diagram text
        """
        return self.graph.get_graph_visualization()

