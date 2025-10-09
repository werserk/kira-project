"""LangGraph topology for Kira agent.

Builds the execution graph: plan → reflect? → tool → verify → (done | plan)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from .state import AgentState
    from .tools import ToolRegistry
    from ..adapters.llm import LLMAdapter

logger = logging.getLogger(__name__)

__all__ = ["build_agent_graph", "AgentGraph"]


def build_agent_graph(
    llm_adapter: LLMAdapter,
    tool_registry: ToolRegistry,
    tools_description: str,
) -> AgentGraph:
    """Build the LangGraph state graph for agent execution.

    Parameters
    ----------
    llm_adapter
        LLM adapter for planning and reflection
    tool_registry
        Registry of available tools
    tools_description
        Description of available tools for prompts

    Returns
    -------
    AgentGraph
        Compiled agent graph ready for execution
    """
    try:
        from langgraph.graph import StateGraph, END  # type: ignore[import-untyped]
    except ImportError as e:
        raise ImportError(
            "LangGraph is not installed. Install with: pip install kira[agent] or poetry install --extras agent"
        ) from e

    from .nodes import plan_node, reflect_node, tool_node, verify_node, route_node
    from .state import AgentState

    # Create state graph
    graph = StateGraph(AgentState)

    # Add nodes with partial application of dependencies
    def _plan_node(state: AgentState) -> dict[str, Any]:
        return plan_node(state, llm_adapter, tools_description)

    def _reflect_node(state: AgentState) -> dict[str, Any]:
        return reflect_node(state, llm_adapter)

    def _tool_node(state: AgentState) -> dict[str, Any]:
        return tool_node(state, tool_registry)

    def _verify_node(state: AgentState) -> dict[str, Any]:
        return verify_node(state, tool_registry)

    graph.add_node("plan", _plan_node)
    graph.add_node("reflect", _reflect_node)
    graph.add_node("tool", _tool_node)
    graph.add_node("verify", _verify_node)

    # Set entry point
    graph.set_entry_point("plan")

    # Add conditional edges based on routing logic
    def route_after_plan(state: AgentState) -> str:
        """Route after planning."""
        if state.error or state.status == "error":
            return "halt"
        if state.flags.enable_reflection:
            return "reflect"
        return "tool"

    def route_after_reflect(state: AgentState) -> str:
        """Route after reflection."""
        if state.error or state.status == "error":
            return "halt"
        return "tool"

    def route_after_tool(state: AgentState) -> str:
        """Route after tool execution."""
        if state.budget.is_exceeded():
            return "halt"
        if state.error or state.status == "error":
            if state.retry_count < 2:
                return "plan"
            return "halt"
        if state.flags.enable_verification:
            return "verify"
        # Check if more steps remain
        if state.current_step < len(state.plan):
            return "tool"
        return "done"

    def route_after_verify(state: AgentState) -> str:
        """Route after verification."""
        if state.budget.is_exceeded():
            return "halt"
        if state.error or state.status == "error":
            return "halt"
        # Check if more steps remain
        if state.current_step < len(state.plan):
            return "tool"
        return "done"

    # Add conditional edges
    graph.add_conditional_edges(
        "plan",
        route_after_plan,
        {
            "reflect": "reflect",
            "tool": "tool",
            "halt": END,
        },
    )

    graph.add_conditional_edges(
        "reflect",
        route_after_reflect,
        {
            "tool": "tool",
            "halt": END,
        },
    )

    graph.add_conditional_edges(
        "tool",
        route_after_tool,
        {
            "verify": "verify",
            "tool": "tool",
            "plan": "plan",
            "done": END,
            "halt": END,
        },
    )

    graph.add_conditional_edges(
        "verify",
        route_after_verify,
        {
            "tool": "tool",
            "done": END,
            "halt": END,
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
            # LangGraph returns the final state
            final_state: AgentState = self.graph.invoke(state)  # type: ignore[no-untyped-call]
            logger.info(f"[{state.trace_id}] Graph execution completed: status={final_state.status}")
            return final_state
        except Exception as e:
            logger.error(f"[{state.trace_id}] Graph execution failed: {e}", exc_info=True)
            state.error = str(e)
            state.status = "error"
            return state

    def stream(self, state: AgentState) -> Any:  # type: ignore[misc]
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
            for node_name, updated_state in self.graph.stream(state):
                logger.debug(f"[{state.trace_id}] Node '{node_name}' completed")
                yield node_name, updated_state
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
            result: str = self.graph.get_graph().draw_mermaid()  # type: ignore[no-untyped-call]
            return result
        except Exception as e:
            logger.warning(f"Could not generate graph visualization: {e}")
            return "Graph visualization not available"

