"""LangGraph topology for Kira agent.

Builds the execution graph: plan → reflect? → tool → verify → (done | plan)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from ..adapters.llm import LLMAdapter
    from .state import AgentState
    from .tools import ToolRegistry

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
        from langgraph.graph import END, StateGraph  # type: ignore[import-untyped]
    except ImportError as e:
        raise ImportError(
            "LangGraph is not installed. Install with: pip install kira[agent] or poetry install --extras agent"
        ) from e

    from .nodes import plan_node, reflect_node, respond_node, route_node, tool_node, verify_node
    from .state import AgentState as AgentStateClass

    # Create state graph
    graph = StateGraph(AgentStateClass)

    # Add nodes with partial application of dependencies
    def _plan_node(state):  # type: ignore[no-untyped-def]
        return plan_node(state, llm_adapter, tools_description)

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
        """Route after planning."""
        if state.error or state.status == "error":
            return "halt"
        if state.flags.enable_reflection:
            return "reflect_step"
        return "tool_step"

    def route_after_reflect(state):  # type: ignore[no-untyped-def]
        """Route after reflection."""
        if state.error or state.status == "error":
            return "halt"
        return "tool_step"

    def route_after_tool(state):  # type: ignore[no-untyped-def]
        """Route after tool execution."""
        if state.budget.is_exceeded():
            return "halt"
        if state.error or state.status == "error":
            if state.retry_count < 2:
                return "plan_step"
            return "halt"
        if state.flags.enable_verification:
            return "verify_step"
        # Check if more steps remain
        if state.current_step < len(state.plan):
            return "tool_step"
        return "done"

    def route_after_verify(state):  # type: ignore[no-untyped-def]
        """Route after verification."""
        if state.budget.is_exceeded():
            return "halt"
        if state.error or state.status == "error":
            return "halt"
        # Check if more steps remain
        if state.current_step < len(state.plan):
            return "tool_step"
        return "respond_step"  # Generate NL response

    def route_after_respond(state):  # type: ignore[no-untyped-def]
        """Route after response generation."""
        return "done"

    # Add conditional edges
    graph.add_conditional_edges(
        "plan_step",
        route_after_plan,
        {
            "reflect_step": "reflect_step",
            "tool_step": "tool_step",
            "halt": END,
        },
    )

    graph.add_conditional_edges(
        "reflect_step",
        route_after_reflect,
        {
            "tool_step": "tool_step",
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
            "done": END,
            "halt": END,
        },
    )

    graph.add_conditional_edges(
        "verify_step",
        route_after_verify,
        {
            "tool_step": "tool_step",
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
            # LangGraph returns dict (AddableValuesDict), not dataclass
            result_dict = self.graph.invoke(state)  # type: ignore[no-untyped-call]

            # Convert dict back to AgentState
            final_state = AgentStateClass.from_dict(result_dict)
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

