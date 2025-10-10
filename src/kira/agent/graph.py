"""LangGraph topology for Kira agent.

Builds the execution graph: plan → reflect? → tool → verify → (done | plan)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..adapters.llm import LLMAdapter
    from .state import AgentState
    from .tools import ToolRegistry

logger = logging.getLogger(__name__)

__all__ = ["build_agent_graph", "AgentGraph"]


# Tool classification for conditional reflection
SAFE_TOOLS = {
    # Read-only operations (no data modification)
    "task_list",
    "task_get",
    "task_search",
    "search",
    "query",
    "file_read",
    "vault_read",
    "calendar_list",
    "calendar_get",
}

DESTRUCTIVE_TOOLS = {
    # Operations that modify or delete data
    "task_delete",
    "file_delete",
    "vault_delete",
    "calendar_delete",
}

MODERATE_RISK_TOOLS = {
    # Operations that modify data but are usually safe
    "task_create",
    "task_update",
    "file_write",
    "file_update",
    "calendar_create",
    "calendar_update",
}


def should_reflect(state: AgentState) -> bool:
    """Determine if reflection is needed based on planned operations.

    Reflection is conditionally applied to save time:
    - ALWAYS for destructive operations (delete, mass operations)
    - NEVER for read-only operations (list, get, search)
    - CONDITIONAL for moderate risk operations (create, update single items)

    Parameters
    ----------
    state
        Current agent state with plan

    Returns
    -------
    bool
        True if reflection should be performed
    """
    if not state.flags.enable_reflection:
        return False

    if not state.plan:
        return False

    # Extract tool names from plan
    planned_tools = {step.get("tool") for step in state.plan if isinstance(step, dict)}

    # ALWAYS reflect on destructive operations
    if planned_tools & DESTRUCTIVE_TOOLS:
        logger.info(
            f"[{state.trace_id}] ✓ Reflection REQUIRED: Destructive operations detected: "
            f"{planned_tools & DESTRUCTIVE_TOOLS}"
        )
        return True

    # NEVER reflect on read-only operations
    if planned_tools <= SAFE_TOOLS:  # All tools are safe
        logger.info(
            f"[{state.trace_id}] ⚡ Reflection SKIPPED: All operations are read-only: "
            f"{planned_tools & SAFE_TOOLS}"
        )
        return False

    # For moderate risk operations, check if it's a single operation
    moderate_risk_planned = planned_tools & MODERATE_RISK_TOOLS
    if moderate_risk_planned:
        if len(state.plan) == 1:
            # Single create/update is usually safe
            logger.info(
                f"[{state.trace_id}] ⚡ Reflection SKIPPED: Single moderate-risk operation: "
                f"{moderate_risk_planned}"
            )
            return False
        else:
            # Multiple operations - safer to reflect
            logger.info(
                f"[{state.trace_id}] ✓ Reflection REQUIRED: Multiple moderate-risk operations: "
                f"{moderate_risk_planned}"
            )
            return True

    # Unknown tools - be conservative and reflect
    unknown_tools = planned_tools - (SAFE_TOOLS | DESTRUCTIVE_TOOLS | MODERATE_RISK_TOOLS)
    if unknown_tools:
        logger.info(
            f"[{state.trace_id}] ✓ Reflection REQUIRED: Unknown tools detected: {unknown_tools}"
        )
        return True

    # Default: skip reflection
    logger.info(f"[{state.trace_id}] ⚡ Reflection SKIPPED: No risky operations detected")
    return False


def build_agent_graph(
    llm_adapter: LLMAdapter,
    tool_registry: ToolRegistry,
) -> AgentGraph:
    """Build the LangGraph state graph for agent execution.

    Parameters
    ----------
    llm_adapter
        LLM adapter for planning and reflection
    tool_registry
        Registry of available tools (used for native function calling)

    Returns
    -------
    AgentGraph
        Compiled agent graph ready for execution
    """
    try:
        from langgraph.graph import END, StateGraph
    except ImportError as e:
        raise ImportError(
            "LangGraph is not installed. Install with: pip install kira[agent] or poetry install --extras agent"
        ) from e

    from .nodes import plan_node, reflect_node, respond_node, tool_node, verify_node
    from .state import AgentState

    # Create state graph
    graph = StateGraph(AgentState)

    # Add nodes with partial application of dependencies
    def _plan_node(state):  # type: ignore[no-untyped-def]
        return plan_node(state, llm_adapter, tool_registry)

    def _reflect_node(state):  # type: ignore[no-untyped-def]
        return reflect_node(state, llm_adapter)

    def _tool_node(state):  # type: ignore[no-untyped-def]
        return tool_node(state, tool_registry)

    def _verify_node(state):  # type: ignore[no-untyped-def]
        return verify_node(state, tool_registry)

    def _respond_node(state):  # type: ignore[no-untyped-def]
        return respond_node(state, llm_adapter)

    graph.add_node("plan_step", _plan_node)
    graph.add_node("reflect_step", _reflect_node)
    graph.add_node("tool_step", _tool_node)
    graph.add_node("verify_step", _verify_node)
    graph.add_node("respond_step", _respond_node)

    # Set entry point
    graph.set_entry_point("plan_step")

    # Add conditional edges based on routing logic
    def route_after_plan(state):  # type: ignore[no-untyped-def]
        """Route after planning with conditional reflection.

        Reflection is now applied conditionally based on operation risk:
        - Destructive operations (delete) → Always reflect
        - Read-only operations (list, get) → Skip reflection
        - Moderate risk (create, update) → Reflect only if multiple operations

        This optimization saves 4-8 seconds per request for read-only queries.
        """
        if state.error or state.status == "error":
            return "respond_step"  # Generate NL response even on planning error
        if state.status == "completed":
            return "respond_step"  # Task completed, generate final response

        # Conditional reflection based on operation risk
        if should_reflect(state):
            return "reflect_step"  # Safety check needed

        return "tool_step"  # Skip reflection, go directly to execution

    def route_after_reflect(state):  # type: ignore[no-untyped-def]
        """Route after reflection."""
        if state.error or state.status == "error":
            return "respond_step"  # Generate NL response even on reflection error
        return "tool_step"

    def route_after_tool(state):  # type: ignore[no-untyped-def]
        """Route after tool execution.

        New behavior: After successful tool execution, return to plan_step
        so LLM can see the results and plan next steps dynamically.
        """
        if state.budget.is_exceeded():
            return "respond_step"  # Generate NL response even on budget exceeded
        if state.error or state.status == "error":
            if state.retry_count < 2:
                return "plan_step"  # Replan on error
            return "respond_step"  # Generate NL response even on error
        if state.flags.enable_verification:
            return "verify_step"
        # Always return to planning after successful tool execution
        # This allows LLM to see results and decide next steps dynamically
        return "plan_step"

    def route_after_verify(state):  # type: ignore[no-untyped-def]
        """Route after verification.

        New behavior: After verification, return to planning to allow
        dynamic replanning based on results.
        """
        if state.budget.is_exceeded():
            return "respond_step"  # Generate NL response even on budget exceeded
        if state.error or state.status == "error":
            return "respond_step"  # Generate NL response even on error
        # Return to planning after verification
        return "plan_step"

    def route_after_respond(state):  # type: ignore[no-untyped-def,unused-ignore]
        """Route after response generation."""
        _ = state  # State not used but required by interface
        return "done"

    # Add conditional edges
    graph.add_conditional_edges(
        "plan_step",
        route_after_plan,
        {
            "reflect_step": "reflect_step",
            "tool_step": "tool_step",
            "respond_step": "respond_step",
            "halt": END,
        },
    )

    graph.add_conditional_edges(
        "reflect_step",
        route_after_reflect,
        {
            "tool_step": "tool_step",
            "respond_step": "respond_step",
            "halt": END,
        },
    )

    graph.add_conditional_edges(
        "tool_step",
        route_after_tool,
        {
            "verify_step": "verify_step",
            "tool_step": "tool_step",
            "plan_step": "plan_step",
            "respond_step": "respond_step",
            "done": END,
            "halt": END,
        },
    )

    graph.add_conditional_edges(
        "verify_step",
        route_after_verify,
        {
            "tool_step": "tool_step",
            "plan_step": "plan_step",
            "respond_step": "respond_step",
            "halt": END,
        },
    )

    graph.add_conditional_edges(
        "respond_step",
        route_after_respond,
        {
            "done": END,
        },
    )

    # Compile graph
    compiled_graph = graph.compile()

    logger.info("Agent graph compiled successfully")
    return AgentGraph(compiled_graph)


class AgentGraph:
    """Wrapper for LangGraph compiled graph."""

    def __init__(self, compiled_graph: Any) -> None:
        """Initialize agent graph.

        Parameters
        ----------
        compiled_graph
            Compiled LangGraph StateGraph
        """
        self.graph = compiled_graph

    def invoke(self, state: AgentState) -> AgentState:
        """Execute graph with given initial state.

        Parameters
        ----------
        state
            Initial agent state

        Returns
        -------
        AgentState
            Final state after graph execution
        """
        logger.info(f"[{state.trace_id}] Starting graph execution")

        try:
            from .state import AgentState as StateClass

            # LangGraph returns dict (AddableValuesDict), not dataclass
            result = self.graph.invoke(state)

            # Convert dict back to AgentState if needed
            if isinstance(result, dict):
                final_state = StateClass.from_dict(result)
            elif isinstance(result, StateClass):
                final_state = result
            else:
                # Unexpected type - try to convert
                logger.warning(f"Unexpected result type from graph: {type(result)}")
                final_state = StateClass.from_dict(dict(result))

            logger.info(f"[{state.trace_id}] Graph execution completed: status={final_state.status}")
            return final_state
        except Exception as e:
            logger.error(f"[{state.trace_id}] Graph execution failed: {e}", exc_info=True)
            state.error = str(e)
            state.status = "error"
            return state

    def stream(self, state: AgentState) -> Any:
        """Stream graph execution step by step.

        Parameters
        ----------
        state
            Initial agent state

        Yields
        ------
        tuple[str, AgentState]
            Node name and updated state for each step
        """
        logger.info(f"[{state.trace_id}] Starting streaming graph execution")

        try:
            for node_name_val, updated_state in self.graph.stream(state):
                logger.debug(f"[{state.trace_id}] Node '{node_name_val}' completed")
                yield node_name_val, updated_state
        except Exception as e:
            logger.error(f"[{state.trace_id}] Streaming execution failed: {e}", exc_info=True)
            state.error = str(e)
            state.status = "error"
            yield "error", state

    def get_graph_visualization(self) -> str:
        """Get Mermaid diagram of the graph.

        Returns
        -------
        str
            Mermaid diagram text
        """
        try:
            # LangGraph provides get_graph() method for visualization
            result: str = self.graph.get_graph().draw_mermaid()
            return result
        except Exception as e:
            logger.warning(f"Could not generate graph visualization: {e}")
            return "Graph visualization not available"
